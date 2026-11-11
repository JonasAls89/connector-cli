"""Versioned connector definitions and offline, value-safe validation."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import yaml


class ConfigError(Exception):
    """Validation errors naming field paths, without echoing configuration values."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


class _StrictSafeLoader(yaml.SafeLoader):
    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        self.flatten_mapping(node)
        seen: set[str] = set()
        for key, _ in node.value:
            if isinstance(key, yaml.ScalarNode) and key.tag == "tag:yaml.org,2002:str":
                if key.value in seen:
                    raise yaml.constructor.ConstructorError(problem="duplicate mapping key")
                seen.add(key.value)
        return super().construct_mapping(node, deep=deep)


@dataclass
class Auth:
    type: str = "none"
    token_env: str | None = None
    username_env: str | None = None
    password_env: str | None = None


@dataclass
class Pagination:
    type: str = "none"
    param: str = ""
    start: int = 0
    cursor_path: str = ""
    has_more_path: str = ""
    total_pages_path: str = ""
    next_path: str = ""
    max_records: int | None = None


@dataclass
class Source:
    type: str
    url: str
    records_path: str = ""
    query: dict[str, str | int | float | bool] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    auth: Auth = field(default_factory=Auth)
    pagination: Pagination = field(default_factory=Pagination)
    timeout_seconds: int = 15
    retries: int = 3
    max_retry_delay_seconds: int = 60


@dataclass
class Pipeline:
    type: str = "records"
    select: list[str] | None = None
    rename: dict[str, str] = field(default_factory=dict)
    flatten: bool = False
    format: str = "jsonl"
    columns: list[str] = field(default_factory=list)
    json_cells: bool = False


@dataclass
class Sink:
    type: str
    path: str


@dataclass
class Connector:
    schema_version: int
    source: Source
    pipeline: Pipeline
    sink: Sink
    limit: int | None = None
    name: str | None = None
    display_name: str | None = None
    version: str | None = None


def is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


class _Validator:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def err(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def section(
        self, data: Any, path: str, required: tuple[str, ...], optional: tuple[str, ...] = ()
    ) -> dict[str, Any]:
        if not isinstance(data, dict):
            self.err(path or "<root>", "must be a mapping")
            return {}
        for key in data:
            if not isinstance(key, str):
                self.err(path, "keys must be strings")
            elif key not in required and key not in optional:
                self.err(f"{path}.{key}" if path else key, "unknown key")
        for key in required:
            if key not in data:
                self.err(f"{path}.{key}" if path else key, "required key is missing")
        return data

    def string(
        self, data: dict[str, Any], key: str, path: str, default: str = "", *, empty: bool = False
    ) -> str:
        value = data.get(key, default)
        if (
            not isinstance(value, str)
            or (not value and not empty)
            or any(ord(char) < 32 for char in value)
        ):
            self.err(f"{path}.{key}", "must be a non-empty string without control characters")
            return default
        return value

    def choice(self, data: dict[str, Any], key: str, path: str, choices: tuple[str, ...]) -> str:
        value = self.string(data, key, path, choices[0])
        if value not in choices:
            self.err(f"{path}.{key}", f"must be one of {', '.join(choices)}")
            return choices[0]
        return value

    def integer(
        self, data: dict[str, Any], key: str, path: str, default: int, minimum: int, maximum: int
    ) -> int:
        value = data.get(key, default)
        if not is_integer(value) or not minimum <= value <= maximum:
            self.err(f"{path}.{key}", f"must be an integer between {minimum} and {maximum}")
            return default
        return value

    def boolean(self, data: dict[str, Any], key: str, path: str) -> bool:
        value = data.get(key, False)
        if not isinstance(value, bool):
            self.err(f"{path}.{key}", "must be a boolean")
            return False
        return value

    def path(self, data: dict[str, Any], key: str, path: str, *, root: bool = False) -> str:
        value = self.string(data, key, path, empty=root)
        if value and any(not part for part in value.split(".")):
            self.err(f"{path}.{key}", "must be a dot-separated field path")
        return value

    def strings(self, data: dict[str, Any], key: str, path: str) -> list[str]:
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(s, str) and s for s in value):
            self.err(f"{path}.{key}", "must be a list of non-empty strings")
            return []
        if len(set(value)) != len(value):
            self.err(f"{path}.{key}", "must not contain duplicates")
        return value

    def string_map(self, data: dict[str, Any], key: str, path: str) -> dict[str, str]:
        value = data.get(key, {})
        if not isinstance(value, dict) or not all(
            isinstance(k, str) and k and isinstance(v, str) and v for k, v in value.items()
        ):
            self.err(f"{path}.{key}", "must be a mapping of non-empty strings")
            return {}
        return value

    def auth(self, data: Any) -> Auth:
        path = "source.auth"
        d = self.section(data, path, (), ("type", "token_env", "username_env", "password_env"))
        kind = self.choice(d, "type", path, ("none", "bearer", "basic"))
        required = {"none": (), "bearer": ("token_env",), "basic": ("username_env", "password_env")}
        result = Auth(type=kind)
        for key in ("token_env", "username_env", "password_env"):
            if key in required[kind]:
                value = self.string(d, key, path)
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
                    self.err(f"{path}.{key}", "must name an environment variable")
                setattr(result, key, value)
            elif key in d:
                self.err(f"{path}.{key}", "not used by this authentication type")
        return result

    def pagination(self, data: Any) -> Pagination:
        path = "source.pagination"
        if not isinstance(data, dict):
            self.err(path, "must be a mapping")
            return Pagination()
        kind = self.choice(data, "type", path, ("none", "page", "cursor", "next_link"))
        required = {
            "none": (),
            "page": ("param",),
            "cursor": ("param", "cursor_path", "has_more_path"),
            "next_link": ("next_path",),
        }
        optional = {
            "none": (),
            "page": ("start", "total_pages_path", "max_records"),
            "cursor": ("max_records",),
            "next_link": ("max_records",),
        }
        d = self.section(data, path, required[kind], ("type", *optional[kind]))
        result = Pagination(type=kind)
        if "param" in required[kind]:
            result.param = self.string(d, "param", path)
        for key in ("cursor_path", "has_more_path", "total_pages_path", "next_path"):
            if key in d or key in required[kind]:
                setattr(result, key, self.path(d, key, path))
        if kind == "page":
            result.start = self.integer(d, "start", path, 0, 0, 1)
        if "max_records" in d:
            result.max_records = self.integer(d, "max_records", path, 1, 1, 2**63 - 1)
        return result

    def source(self, data: Any) -> Source:
        d = self.section(
            data,
            "source",
            ("type", "url"),
            (
                "records_path",
                "query",
                "headers",
                "auth",
                "pagination",
                "timeout_seconds",
                "retries",
                "max_retry_delay_seconds",
            ),
        )
        source = Source(
            type=self.string(d, "type", "source"),
            url=self.string(d, "url", "source"),
            records_path=self.path(d, "records_path", "source", root=True),
            headers=self.string_map(d, "headers", "source"),
            auth=self.auth(d.get("auth", {})),
            pagination=self.pagination(d.get("pagination", {})),
            timeout_seconds=self.integer(d, "timeout_seconds", "source", 15, 1, 3600),
            retries=self.integer(d, "retries", "source", 3, 0, 10),
            max_retry_delay_seconds=self.integer(
                d, "max_retry_delay_seconds", "source", 60, 1, 3600
            ),
        )
        try:
            url = httpx.URL(source.url)
            if (
                url.scheme not in {"http", "https"}
                or not url.host
                or url.userinfo
                or url.fragment
                or url.query
            ):
                self.err(
                    "source.url",
                    "must be an absolute HTTP(S) URL without credentials/query/fragment",
                )
            if source.auth.type != "none" and url.scheme != "https":
                self.err("source.url", "authentication requires HTTPS")
        except httpx.InvalidURL:
            self.err("source.url", "must be a valid HTTP(S) URL")
        query = d.get("query", {})
        if not isinstance(query, dict) or not all(
            isinstance(k, str)
            and k
            and isinstance(v, (str, int, float, bool))
            and (not isinstance(v, float) or math.isfinite(v))
            for k, v in query.items()
        ):
            self.err("source.query", "must map non-empty names to finite scalar values")
        else:
            source.query = query
        if source.pagination.param in source.query:
            self.err("source.query", "must not set the pagination-owned parameter")
        for key, value in source.headers.items():
            if (
                not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key)
                or any(ord(char) < 32 or ord(char) > 126 for char in value)
                or key.lower() in {"authorization", "proxy-authorization", "cookie", "host"}
            ):
                self.err("source.headers", "invalid or reserved header; use auth for credentials")
        return source

    def pipeline(self, data: Any) -> Pipeline:
        d = self.section(
            data, "pipeline", (), ("type", "select", "rename", "flatten", "format", "csv")
        )
        pipe = Pipeline(
            type=self.string(d, "type", "pipeline", "records"),
            select=self.strings(d, "select", "pipeline") if "select" in d else None,
            rename=self.string_map(d, "rename", "pipeline"),
            flatten=self.boolean(d, "flatten", "pipeline"),
            format=self.choice(d, "format", "pipeline", ("jsonl", "csv")),
        )
        if pipe.select is not None:
            for name in pipe.select:
                self.path({"field": name}, "field", "pipeline.select")
            if set(pipe.rename) - set(pipe.select):
                self.err("pipeline.rename", "keys must refer to selected fields")
            outputs = [pipe.rename.get(name, name) for name in pipe.select]
            if len(set(outputs)) != len(outputs):
                self.err("pipeline.rename", "output names must not collide")
        if pipe.format == "csv":
            csv = self.section(d.get("csv", {}), "pipeline.csv", ("columns",), ("json_cells",))
            pipe.columns = self.strings(csv, "columns", "pipeline.csv")
            pipe.json_cells = self.boolean(csv, "json_cells", "pipeline.csv")
            if not pipe.columns:
                self.err("pipeline.csv.columns", "must declare at least one column")
        elif "csv" in d:
            self.err("pipeline.csv", "only valid with CSV format")
        return pipe


def parse(data: Any) -> Connector:
    """Validate schema v1; registered adapter names are checked by the runtime."""
    v = _Validator()
    d = v.section(
        data,
        "",
        ("schema_version", "source", "sink"),
        ("pipeline", "limit", "name", "display_name", "version"),
    )
    schema_version = v.integer(d, "schema_version", "<root>", 1, 1, 1)
    source = v.source(d.get("source", {}))
    pipeline = v.pipeline(d.get("pipeline", {}))
    sink_data = v.section(d.get("sink", {}), "sink", ("type", "path"))
    sink = Sink(
        type=v.string(sink_data, "type", "sink"),
        path=v.string(sink_data, "path", "sink"),
    )
    limit = v.integer(d, "limit", "<root>", 1, 1, 2**63 - 1) if "limit" in d else None
    meta = {
        key: v.string(d, key, "<root>") if key in d else None
        for key in ("name", "display_name", "version")
    }
    if v.errors:
        raise ConfigError(v.errors)
    return Connector(schema_version, source, pipeline, sink, limit, **meta)


def load(path: str | Path) -> Connector:
    """Load a definition without resolving credentials or contacting its source."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ConfigError([f"{path}: cannot read UTF-8 connector file"]) from exc
    loader: _StrictSafeLoader | None = None
    try:
        loader = _StrictSafeLoader(text)
        data = loader.get_single_data()
    except yaml.YAMLError:
        raise ConfigError([f"{path}: invalid YAML"]) from None
    finally:
        if loader is not None:
            loader.dispose()
    return parse(data)
