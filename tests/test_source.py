from email.utils import formatdate

import httpx
import pytest

from connector_cli.config import parse
from connector_cli.interfaces import ExecutionError
from connector_cli.source import RestSource


def source_for(definition, handler, **kwargs):
    return RestSource(
        parse(definition).source,
        transport=httpx.MockTransport(handler),
        environ=kwargs.pop("environ", {}),
        sleep=kwargs.pop("sleep", lambda _: None),
        **kwargs,
    )


def test_cursor_pagination_and_record_limit(definition):
    definition["source"]["pagination"] = {
        "type": "cursor",
        "param": "after",
        "cursor_path": "id",
        "has_more_path": "has_more",
    }
    requests = []

    def handler(request):
        requests.append(request)
        if "after" not in request.url.params:
            return httpx.Response(200, json={"data": [{"id": "a"}, {"id": "b"}], "has_more": True})
        assert request.url.params["after"] == "b"
        return httpx.Response(200, json={"data": [{"id": "c"}, {"id": "d"}], "has_more": False})

    assert list(source_for(definition, handler).records(3)) == [
        {"id": "a"},
        {"id": "b"},
        {"id": "c"},
    ]
    assert len(requests) == 2
    requests.clear()
    assert len(list(source_for(definition, handler).records(1))) == 1
    assert len(requests) == 1
    requests.clear()
    assert len(list(source_for(definition, handler).records(None))) == 4
    assert len(requests) == 2


@pytest.mark.parametrize("start", [0, 1])
def test_numbered_pages_without_total_metadata(definition, start):
    definition["source"]["pagination"] = {"type": "page", "param": "page", "start": start}
    pages = []

    def handler(request):
        page = int(request.url.params["page"])
        pages.append(page)
        return httpx.Response(200, json={"data": [{"id": page}] if page < start + 2 else []})

    records = list(source_for(definition, handler).records(None))
    assert records == [{"id": start}, {"id": start + 1}]
    assert pages == [start, start + 1, start + 2]


def test_numbered_pages_with_metadata_avoid_extra_request(definition):
    definition["source"]["pagination"] = {
        "type": "page",
        "param": "page",
        "total_pages_path": "meta.total",
    }
    pages = []

    def handler(request):
        page = int(request.url.params["page"])
        pages.append(page)
        return httpx.Response(200, json={"data": [{"id": page}], "meta": {"total": 2}})

    assert len(list(source_for(definition, handler).records(None))) == 2
    assert pages == [0, 1]


def test_next_link_preserves_relative_query_and_initial_filters(definition):
    definition["source"].update(
        query={"active": True},
        auth={"type": "bearer", "token_env": "TOKEN"},
        pagination={"type": "next_link", "next_path": "links.next"},
    )
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer example-test-token"
        if len(requests) == 1:
            assert request.url.params["active"] == "true"
            return httpx.Response(200, json={"data": [{"id": 1}], "links": {"next": "?page=2"}})
        assert request.url.params["page"] == "2"
        return httpx.Response(200, json={"data": [{"id": 2}], "links": {"next": None}})

    source = source_for(definition, handler, environ={"TOKEN": "example-test-token"})
    assert list(source.records(None)) == [{"id": 1}, {"id": 2}]
    assert len(requests) == 2


@pytest.mark.parametrize(
    "link",
    [
        "http://example.test/items?page=2",
        "https://other.test/items",
        "//other.test/items",
        "https://example.test:444/items",
        "https://user:example@example.test/items",
        "https://example.test/items#fragment",
        "https://example.test:bad/items",
    ],
)
def test_next_link_refuses_unsafe_targets_before_request(definition, link):
    definition["source"]["pagination"] = {"type": "next_link", "next_path": "next"}
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"data": [{"id": 1}], "next": link})

    with pytest.raises(ExecutionError, match=r"unsafe|invalid"):
        list(source_for(definition, handler).records(None))
    assert len(requests) == 1


def test_nonadvancing_cursor_and_repeated_pages(definition):
    definition["source"]["pagination"] = {
        "type": "cursor",
        "param": "after",
        "cursor_path": "id",
        "has_more_path": "more",
    }
    calls = []

    def changing_records_with_same_cursor(request):
        calls.append(request)
        return httpx.Response(200, json={"data": [{"id": "a", "value": len(calls)}], "more": True})

    with pytest.raises(ExecutionError, match="request did not advance"):
        list(source_for(definition, changing_records_with_same_cursor).records(None))
    assert len(calls) == 2
    definition["source"]["pagination"] = {"type": "page", "param": "page"}
    with pytest.raises(ExecutionError, match="repeated record page"):
        list(
            source_for(
                definition, lambda _: httpx.Response(200, json={"data": [{"id": 1}]})
            ).records(None)
        )


def test_result_cap_is_not_successful_completion(definition):
    definition["source"]["pagination"] = {
        "type": "page",
        "param": "page",
        "total_pages_path": "pages",
        "max_records": 2,
    }

    def handler(_):
        return httpx.Response(200, json={"data": [{"id": 1}, {"id": 2}], "pages": 2})

    source = source_for(definition, handler)
    with pytest.raises(ExecutionError, match="result cap"):
        list(source.records(None))
    assert len(list(source.records(2))) == 2
    definition["source"]["pagination"]["max_records"] = 1
    with pytest.raises(ExecutionError, match="result cap"):
        list(source_for(definition, handler).records(None))


@pytest.mark.parametrize("status", [400, 401, 403, 404, 301, 302])
def test_permanent_failures_and_redirects_are_not_retried(definition, status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status, text="example-secret-value", headers={"Location": "https://other.test"}
        )

    with pytest.raises(ExecutionError, match=f"HTTP {status}") as error:
        list(source_for(definition, handler).records(None))
    assert "example-secret-value" not in str(error.value)
    assert len(calls) == 1


def test_transient_statuses_retry_with_backoff_and_retry_after(definition):
    statuses = iter([503, 429, 200])
    sleeps = []

    def handler(request):
        status = next(statuses)
        return httpx.Response(
            status, json={"data": []}, headers={"Retry-After": "3"} if status == 429 else {}
        )

    assert list(source_for(definition, handler, sleep=sleeps.append).records(None)) == []
    assert sleeps == [1, 3]


def test_http_date_retry_after(definition):
    statuses = iter([503, 200])
    sleeps = []
    now = 1_700_000_000

    def handler(_):
        return httpx.Response(
            next(statuses),
            json={"data": []},
            headers={"Retry-After": formatdate(now + 4, usegmt=True)},
        )

    assert (
        list(source_for(definition, handler, sleep=sleeps.append, clock=lambda: now).records(None))
        == []
    )
    assert sleeps == [4]


@pytest.mark.parametrize("header", ["not-a-date", "99999"])
def test_invalid_or_excessive_retry_after_fails_explicitly(definition, header):
    with pytest.raises(ExecutionError, match="Retry-After"):
        list(
            source_for(
                definition,
                lambda _: httpx.Response(429, headers={"Retry-After": header}),
            ).records(None)
        )


def test_retry_budget_exhaustion(definition):
    definition["source"]["retries"] = 2
    sleeps = []
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503)

    with pytest.raises(ExecutionError, match="HTTP 503"):
        list(source_for(definition, handler, sleep=sleeps.append).records(None))
    assert len(calls) == 3
    assert sleeps == [1, 2]


@pytest.mark.parametrize(
    "error_type",
    [httpx.ReadTimeout, httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError],
)
def test_transient_transport_errors_retry_without_leaking_details(definition, error_type):
    definition["source"]["retries"] = 1
    calls = []

    def handler(request):
        calls.append(request)
        raise error_type("example-secret-value")

    with pytest.raises(ExecutionError, match="bounded retries") as error:
        list(source_for(definition, handler).records(None))
    assert len(calls) == 2
    assert "example-secret-value" not in str(error.value)


def test_nonretryable_request_error(definition):
    def handler(request):
        raise httpx.UnsupportedProtocol("example-secret-value")

    with pytest.raises(ExecutionError, match="GET failed; extraction incomplete"):
        list(source_for(definition, handler).records(None))


@pytest.mark.parametrize(
    ("pagination", "payload", "message"),
    [
        ({}, {"data": {}}, "record array"),
        ({}, {"data": [1]}, "record must be an object"),
        (
            {"type": "cursor", "param": "after", "cursor_path": "id", "has_more_path": "more"},
            {"data": [{"id": "a"}], "more": "true"},
            "boolean",
        ),
        (
            {"type": "cursor", "param": "after", "cursor_path": "id", "has_more_path": "more"},
            {"data": [], "more": True},
            "cursor",
        ),
        (
            {"type": "cursor", "param": "after", "cursor_path": "id", "has_more_path": "more"},
            {"data": [{"id": False}], "more": True},
            "cursor",
        ),
        (
            {"type": "page", "param": "page", "total_pages_path": "total"},
            {"data": [], "total": True},
            "nonnegative integer",
        ),
        (
            {"type": "page", "param": "page", "total_pages_path": "total"},
            {"data": [], "total": 2},
            "empty page",
        ),
        (
            {"type": "page", "param": "page", "total_pages_path": "total"},
            {"data": [{"id": 1}], "total": 0},
            "contradict",
        ),
        (
            {"type": "next_link", "next_path": "next"},
            {"data": [], "next": "?page=2"},
            "continuation",
        ),
    ],
)
def test_invalid_response_shapes(definition, pagination, payload, message):
    definition["source"]["pagination"] = pagination
    with pytest.raises(ExecutionError, match=message):
        list(source_for(definition, lambda _: httpx.Response(200, json=payload)).records(None))


@pytest.mark.parametrize("content", [b"not-json", b"\xff", b'{"data":[{"value":NaN}]}'])
def test_invalid_json_does_not_echo_response(definition, content):
    with pytest.raises(ExecutionError, match="not valid JSON"):
        list(source_for(definition, lambda _: httpx.Response(200, content=content)).records(None))


def test_root_record_array_and_empty_page_metadata(definition):
    definition["source"]["records_path"] = ""
    assert list(
        source_for(definition, lambda _: httpx.Response(200, json=[{"id": 1}])).records(None)
    ) == [{"id": 1}]
    definition["source"].update(
        records_path="data",
        pagination={"type": "page", "param": "page", "total_pages_path": "pages"},
    )
    assert (
        list(
            source_for(
                definition, lambda _: httpx.Response(200, json={"data": [], "pages": 0})
            ).records(None)
        )
        == []
    )


def test_credentials_and_invalid_limit(definition):
    definition["source"]["auth"] = {"type": "bearer", "token_env": "TOKEN"}

    def handler(_):
        return httpx.Response(200, json={"data": []})

    with pytest.raises(ExecutionError, match="missing or empty"):
        source_for(definition, handler)
    with pytest.raises(ExecutionError, match="printable ASCII"):
        source_for(definition, handler, environ={"TOKEN": "bad\ntoken"})
    source = source_for(definition, handler, environ={"TOKEN": "example-test-token"})
    with pytest.raises(ExecutionError, match="positive integer"):
        list(source.records(0))
    definition["source"]["auth"] = {
        "type": "basic",
        "username_env": "USER",
        "password_env": "PASSWORD",
    }
    with pytest.raises(ExecutionError, match="colon"):
        source_for(definition, handler, environ={"USER": "bad:user", "PASSWORD": "test"})
