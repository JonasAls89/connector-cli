"""The execution interfaces shared by built-in and explicitly registered adapters."""

from collections.abc import Callable, Generator, Iterable, Iterator
from typing import Protocol

type Value = bool | int | float | str | list[Value] | dict[str, Value] | None
type Record = dict[str, Value]


class ExecutionError(Exception):
    """An incomplete extraction, transformation, or delivery."""


class SourceAdapter(Protocol):
    secrets: tuple[str, ...]

    def records(self, limit: int | None) -> Generator[Record, None, None]: ...


class PipelineAdapter(Protocol):
    def transform(self, record: Record) -> Record: ...

    def serialize(
        self, records: Iterable[Record], *, redact: Callable[[str], str] | None = None
    ) -> Iterator[str]: ...


class SinkAdapter(Protocol):
    def write(self, chunks: Iterable[str], *, overwrite: bool) -> None: ...


def field_value(value: Value, path: str) -> Value:
    if not path:
        return value
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value
