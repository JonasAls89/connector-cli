"""Explicit adapter registration and resource-safe run/preview orchestration."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import closing
from dataclasses import dataclass
from itertools import islice
from typing import TextIO

import httpx

from connector_cli.config import ConfigError, Connector, Pipeline, Sink, Source, is_integer
from connector_cli.interfaces import (
    ExecutionError,
    PipelineAdapter,
    Record,
    SinkAdapter,
    SourceAdapter,
)
from connector_cli.pipeline import RecordPipeline
from connector_cli.sink import LocalSink
from connector_cli.source import RestSource


@dataclass
class Registry:
    sources: dict[str, Callable[[Source], SourceAdapter]]
    pipelines: dict[str, Callable[[Pipeline], PipelineAdapter]]
    sinks: dict[str, Callable[[Sink], SinkAdapter]]

    def validate(self, connector: Connector) -> None:
        errors = []
        for name, kind, adapters in (
            ("source", connector.source.type, self.sources),
            ("pipeline", connector.pipeline.type, self.pipelines),
            ("sink", connector.sink.type, self.sinks),
        ):
            if kind not in adapters:
                errors.append(f"{name}.type: no adapter is registered")
        if errors:
            raise ConfigError(errors)


def default_registry(
    *,
    transport: httpx.BaseTransport | None = None,
    environ: Mapping[str, str] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
) -> Registry:
    return Registry(
        sources={
            "rest": lambda config: RestSource(
                config, transport=transport, environ=environ, sleep=sleep, clock=clock
            )
        },
        pipelines={"records": RecordPipeline},
        sinks={"local": LocalSink},
    )


def _redact(text: str, secrets: tuple[str, ...]) -> str:
    variants = {
        variant
        for secret in secrets
        if secret
        for variant in (secret, json.dumps(secret, ensure_ascii=False)[1:-1])
    }
    for secret in sorted(variants, key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return text


def _execute(
    connector: Connector,
    registry: Registry,
    limit: int | None,
    deliver: Callable[[Iterable[str]], None],
    *,
    preview: bool,
) -> int:
    registry.validate(connector)
    source = registry.sources[connector.source.type](connector.source)
    pipeline = registry.pipelines[connector.pipeline.type](connector.pipeline)
    count = 0
    with closing(source.records(limit)) as reader:

        def adapted() -> Iterator[Record]:
            nonlocal count
            for record in islice(reader, limit):
                result = pipeline.transform(record)
                count += 1
                yield result

        def chunks() -> Iterator[str]:
            if preview:
                yield from pipeline.serialize(
                    adapted(), redact=lambda text: _redact(text, source.secrets)
                )
            else:
                yield from pipeline.serialize(adapted())

        try:
            deliver(chunks())
        except ExecutionError as exc:
            raise ExecutionError(_redact(str(exc), source.secrets)) from None
    return count


def run(connector: Connector, *, registry: Registry | None = None, overwrite: bool = False) -> int:
    adapters = default_registry() if registry is None else registry
    adapters.validate(connector)
    sink = adapters.sinks[connector.sink.type](connector.sink)
    return _execute(
        connector,
        adapters,
        connector.limit,
        lambda chunks: sink.write(chunks, overwrite=overwrite),
        preview=False,
    )


def preview(
    connector: Connector,
    *,
    limit: int = 10,
    output: TextIO | None = None,
    registry: Registry | None = None,
) -> int:
    if not is_integer(limit) or limit < 1:
        raise ExecutionError("preview: limit must be a positive integer")
    if connector.limit is not None:
        limit = min(limit, connector.limit)
    stream = sys.stdout if output is None else output

    def deliver(chunks: Iterable[str]) -> None:
        try:
            for chunk in chunks:
                stream.write(chunk)
        except (OSError, UnicodeError):
            raise ExecutionError("preview: cannot write output") from None

    return _execute(
        connector,
        default_registry() if registry is None else registry,
        limit,
        deliver,
        preview=True,
    )
