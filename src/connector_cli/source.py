"""Paginated REST acquisition with bounded retries and origin-safe navigation."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from collections.abc import Callable, Generator, Mapping
from datetime import UTC
from email.utils import parsedate_to_datetime
from typing import NoReturn

import httpx

from connector_cli.config import Source, is_integer
from connector_cli.interfaces import ExecutionError, Record, Value, field_value

_RETRYABLE = {408, 429, 500, 502, 503, 504}


def _reject_constant(_: str) -> NoReturn:
    raise ValueError("non-finite JSON value")


class RestSource:
    def __init__(
        self,
        config: Source,
        *,
        transport: httpx.BaseTransport | None = None,
        environ: Mapping[str, str] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.config = config
        self.transport = transport
        self.sleep = sleep
        self.clock = clock
        env = os.environ if environ is None else environ

        def credential(name: str | None) -> str:
            if not name or not env.get(name):
                raise ExecutionError(
                    "source.auth: required environment variable is missing or empty"
                )
            return env[name]

        auth = config.auth
        authorization: str | None = None
        secrets: tuple[str, ...] = ()
        if auth.type == "bearer":
            token = credential(auth.token_env)
            if any(ord(char) < 33 or ord(char) > 126 for char in token):
                raise ExecutionError(
                    "source.auth: bearer token must be printable ASCII without spaces"
                )
            authorization = f"Bearer {token}"
            secrets = (token, authorization)
        elif auth.type == "basic":
            username = credential(auth.username_env)
            password = credential(auth.password_env)
            if ":" in username:
                raise ExecutionError("source.auth: Basic username must not contain a colon")
            encoded = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
            authorization = f"Basic {encoded}"
            secrets = (username, password, encoded, authorization)
        self.secrets = secrets
        self.headers = {"Accept": "application/json", **config.headers}
        if authorization is not None:
            self.headers["Authorization"] = authorization

    def _delay(self, response: httpx.Response | None, attempt: int) -> float:
        maximum = self.config.max_retry_delay_seconds
        if response is None or "Retry-After" not in response.headers:
            return min(2**attempt, maximum)
        header = response.headers["Retry-After"]
        try:
            if header.isascii() and header.isdigit():
                delay = float(header)
            else:
                date = parsedate_to_datetime(header)
                if date.tzinfo is None:
                    date = date.replace(tzinfo=UTC)
                delay = max(0.0, date.timestamp() - self.clock())
        except (ValueError, TypeError, OverflowError):
            raise ExecutionError("source: invalid Retry-After header") from None
        if delay > maximum:
            raise ExecutionError("source: Retry-After exceeds max_retry_delay_seconds")
        return delay

    def _fetch(self, client: httpx.Client, request: httpx.Request) -> httpx.Response:
        for attempt in range(self.config.retries + 1):
            try:
                response = client.send(request)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
                if attempt == self.config.retries:
                    raise ExecutionError("source: GET failed after bounded retries") from None
                self.sleep(self._delay(None, attempt))
                continue
            except httpx.RequestError:
                raise ExecutionError("source: GET failed; extraction incomplete") from None
            if response.status_code in _RETRYABLE and attempt < self.config.retries:
                delay = self._delay(response, attempt)
                response.close()
                self.sleep(delay)
                continue
            if response.status_code != 200:
                raise ExecutionError(
                    f"source: HTTP {response.status_code}; extraction incomplete "
                    "(redirects are not followed)"
                )
            return response
        raise ExecutionError("source: retry budget exhausted")

    def _next_url(self, current: httpx.URL, link: str) -> httpx.URL:
        try:
            target = current.join(link)
        except httpx.InvalidURL:
            raise ExecutionError("source.pagination: invalid next link") from None
        origin = httpx.URL(self.config.url)
        if (
            (target.scheme, target.host, target.port) != (origin.scheme, origin.host, origin.port)
            or target.userinfo
            or target.fragment
        ):
            raise ExecutionError("source.pagination: unsafe next-link target refused")
        return target

    def records(self, limit: int | None) -> Generator[Record, None, None]:
        if limit is not None and (not is_integer(limit) or limit < 1):
            raise ExecutionError("source: record limit must be a positive integer")
        config = self.config
        pagination = config.pagination
        url = httpx.URL(config.url, params=config.query)
        page = pagination.start
        if pagination.type == "page":
            url = url.copy_set_param(pagination.param, page)
        seen_requests: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
        seen_pages: set[bytes] = set()
        count = 0
        with httpx.Client(
            transport=self.transport,
            headers=self.headers,
            timeout=config.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            while True:
                request = client.build_request("GET", url)
                identity = (
                    str(request.url).partition("?")[0],
                    tuple(sorted(request.url.params.multi_items())),
                )
                if identity in seen_requests:
                    raise ExecutionError("source.pagination: request did not advance")
                seen_requests.add(identity)
                response = self._fetch(client, request)
                try:
                    payload: Value = json.loads(response.content, parse_constant=_reject_constant)
                except (ValueError, RecursionError):
                    raise ExecutionError("source: response is not valid JSON") from None
                items = field_value(payload, config.records_path)
                if not isinstance(items, list):
                    raise ExecutionError(
                        "source.records_path: response must contain a record array"
                    )
                if items:
                    fingerprint = hashlib.sha256(
                        json.dumps(items, sort_keys=True, ensure_ascii=True).encode()
                    ).digest()
                    if fingerprint in seen_pages:
                        raise ExecutionError("source.pagination: repeated record page")
                    seen_pages.add(fingerprint)
                for item in items:
                    if pagination.max_records is not None and count >= pagination.max_records:
                        raise ExecutionError(
                            "source.pagination: result cap prevents requested extraction"
                        )
                    if not isinstance(item, dict):
                        raise ExecutionError("source: each record must be an object")
                    count += 1
                    yield item
                    if limit is not None and count >= limit:
                        return
                if pagination.type == "none":
                    return
                if pagination.type == "cursor":
                    more = field_value(payload, pagination.has_more_path)
                    if not isinstance(more, bool):
                        raise ExecutionError(
                            "source.pagination: has_more_path must contain a boolean"
                        )
                    if not more:
                        return
                    cursor = field_value(items[-1], pagination.cursor_path) if items else None
                    if (
                        not isinstance(cursor, (str, int))
                        or isinstance(cursor, bool)
                        or cursor == ""
                    ):
                        raise ExecutionError("source.pagination: missing or invalid cursor")
                    url = url.copy_set_param(pagination.param, cursor)
                elif pagination.type == "page":
                    if pagination.total_pages_path:
                        total = field_value(payload, pagination.total_pages_path)
                        if not is_integer(total) or not isinstance(total, int) or total < 0:
                            raise ExecutionError(
                                "source.pagination: total pages must be a nonnegative integer"
                            )
                        if total == 0 and items:
                            raise ExecutionError(
                                "source.pagination: records contradict total pages"
                            )
                        if page - pagination.start + 1 >= total:
                            return
                        if not items:
                            raise ExecutionError("source.pagination: empty page before completion")
                    elif not items:
                        return
                    page += 1
                    url = url.copy_set_param(pagination.param, page)
                else:
                    link = field_value(payload, pagination.next_path)
                    if link is None:
                        return
                    if not isinstance(link, str) or not link or not items:
                        raise ExecutionError("source.pagination: invalid continuation")
                    url = self._next_url(request.url, link)
                if pagination.max_records is not None and count >= pagination.max_records:
                    raise ExecutionError(
                        "source.pagination: result cap prevents requested extraction"
                    )
