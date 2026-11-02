"""Connector file schema and strict validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SOURCE_TYPES = ("stripe",)
SINK_TYPES = ("local",)
CAST_TYPES = ("string", "int", "float", "bool")
FORMATS = ("jsonl", "csv")


class ConfigError(Exception):
    """Raised with all validation errors, each naming a field path."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass
class Source:
    type: str
    resource: str
    base_url: str | None = None
    timeout_seconds: int = 15
    retries: int = 3
    auth_type: str | None = None
    token_env: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class Pipeline:
    select: list[str] | None = None
    rename: dict[str, str] = field(default_factory=dict)
    cast: dict[str, str] = field(default_factory=dict)
    format: str = "jsonl"


@dataclass
class Sink:
    type: str
    limit: int = 10
    path: str | None = None


@dataclass
class Connector:
    name: str | None
    display_name: str | None
    version: str | None
    source: Source
    pipeline: Pipeline
    sink: Sink


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_str_map(value: Any) -> bool:
    return isinstance(value, dict) and all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    )


class _Validator:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def err(self, path: str, msg: str) -> None:
        self.errors.append(f"{path}: {msg}")

    def section(
        self, data: Any, path: str, required: tuple[str, ...], optional: tuple[str, ...]
    ) -> dict[str, Any] | None:
        if not isinstance(data, dict):
            self.err(path, "must be a mapping")
            return None
        for key in data:
            if key not in required and key not in optional:
                self.err(f"{path}.{key}", "unknown key")
        for key in required:
            if key not in data:
                self.err(f"{path}.{key}", "required key is missing")
        return data

    def string(self, data: dict[str, Any], key: str, path: str) -> str | None:
        if key not in data:
            return None
        value = data[key]
        if not isinstance(value, str) or not value:
            self.err(f"{path}.{key}", "must be a non-empty string")
            return None
        return value

    def choice(self, data: dict[str, Any], key: str, path: str, allowed: tuple[str, ...]) -> Any:
        value = self.string(data, key, path)
        if value is not None and value not in allowed:
            self.err(f"{path}.{key}", f"must be one of {', '.join(allowed)}")
            return None
        return value

    def integer(self, data: dict[str, Any], key: str, path: str, default: int, minimum: int) -> int:
        if key not in data:
            return default
        value = data[key]
        if not _is_int(value) or value < minimum:
            self.err(f"{path}.{key}", f"must be an integer >= {minimum}")
            return default
        return value

    def str_map(self, data: dict[str, Any], key: str, path: str) -> dict[str, str]:
        value = data.get(key, {})
        if not _is_str_map(value):
            self.err(f"{path}.{key}", "must be a mapping of strings to strings")
            return {}
        return value

    def source(self, data: Any) -> Source | None:
        d = self.section(data, "source", ("type", "resource"), ("api", "auth", "headers"))
        if d is None:
            return None
        src = Source(
            type=self.choice(d, "type", "source", SOURCE_TYPES) or "",
            resource=self.string(d, "resource", "source") or "",
        )
        api = d.get("api", {})
        a = self.section(api, "source.api", (), ("base_url", "timeout_seconds", "retries"))
        if a is not None:
            src.base_url = self.string(a, "base_url", "source.api")
            src.timeout_seconds = self.integer(a, "timeout_seconds", "source.api", 15, 1)
            src.retries = self.integer(a, "retries", "source.api", 3, 0)
        if "auth" in d:
            au = self.section(d["auth"], "source.auth", ("type", "token_env"), ())
            if au is not None:
                src.auth_type = self.string(au, "type", "source.auth")
                src.token_env = self.string(au, "token_env", "source.auth")
        if "headers" in d:
            src.headers = self.str_map(d, "headers", "source")
        return src

    def pipeline(self, data: Any) -> Pipeline:
        pipe = Pipeline()
        d = self.section(data, "pipeline", (), ("select", "rename", "cast", "format"))
        if d is None:
            return pipe
        if "select" in d:
            sel = d["select"]
            if not isinstance(sel, list) or not all(isinstance(s, str) and s for s in sel):
                self.err("pipeline.select", "must be a list of field names")
            else:
                pipe.select = sel
        if "rename" in d:
            pipe.rename = self.str_map(d, "rename", "pipeline")
        if "cast" in d:
            cast = self.str_map(d, "cast", "pipeline")
            for name, typ in cast.items():
                if typ not in CAST_TYPES:
                    self.err(f"pipeline.cast.{name}", f"must be one of {', '.join(CAST_TYPES)}")
            pipe.cast = cast
        pipe.format = self.choice(d, "format", "pipeline", FORMATS) or "jsonl"
        return pipe

    def sink(self, data: Any) -> Sink | None:
        d = self.section(data, "sink", ("type",), ("limit", "path"))
        if d is None:
            return None
        return Sink(
            type=self.choice(d, "type", "sink", SINK_TYPES) or "",
            limit=self.integer(d, "limit", "sink", 10, 1),
            path=self.string(d, "path", "sink"),
        )


def parse(data: Any) -> Connector:
    """Validate a loaded connector mapping; raise ConfigError listing every problem."""
    v = _Validator()
    if not isinstance(data, dict):
        raise ConfigError(["<root>: must be a mapping"])
    allowed = {"name", "display_name", "version", "source", "pipeline", "sink"}
    for key in data:
        if key not in allowed:
            v.err(str(key), "unknown key")
    meta = {k: v.string(data, k, "") for k in ("name", "display_name", "version")}
    for key in ("source", "sink"):
        if key not in data:
            v.err(key, "required section is missing")
    source = v.source(data["source"]) if "source" in data else None
    pipeline = v.pipeline(data["pipeline"]) if "pipeline" in data else Pipeline()
    sink = v.sink(data["sink"]) if "sink" in data else None
    if v.errors or source is None or sink is None:
        raise ConfigError(v.errors)
    return Connector(
        name=meta["name"],
        display_name=meta["display_name"],
        version=meta["version"],
        source=source,
        pipeline=pipeline,
        sink=sink,
    )


def load(path: str | Path) -> Connector:
    """Load and validate a connector file."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError([f"{path}: cannot read file ({exc.strerror})"]) from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError([f"{path}: invalid YAML ({exc})"]) from exc
    return parse(data)
