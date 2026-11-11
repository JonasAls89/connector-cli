"""One-record-in/one-record-out adaptation and streaming serialization."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, Iterable, Iterator

from connector_cli.config import Pipeline
from connector_cli.interfaces import ExecutionError, Record, Value, field_value


def _json(value: Value) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (ValueError, TypeError, RecursionError):
        raise ExecutionError("pipeline: value cannot be represented as JSON") from None


def _redacted(value: Value, redact: Callable[[str], str]) -> Value:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [_redacted(child, redact) for child in value]
    if isinstance(value, dict):
        result: Record = {}
        for key, child in value.items():
            name = redact(key)
            if name in result:
                raise ExecutionError("preview: redacted field names collide")
            result[name] = _redacted(child, redact)
        return result
    return value


class RecordPipeline:
    def __init__(self, config: Pipeline) -> None:
        self.config = config

    def transform(self, record: Record) -> Record:
        config = self.config
        selected = (
            {name: field_value(record, name) for name in config.select}
            if config.select is not None
            else record
        )
        if set(config.rename) - set(selected):
            raise ExecutionError("pipeline.rename: source field is absent")
        renamed: Record = {}
        for name, value in selected.items():
            target = config.rename.get(name, name)
            if target in renamed:
                raise ExecutionError("pipeline.rename: output names collide")
            renamed[target] = value
        if not config.flatten:
            return renamed
        flattened: Record = {}

        def add(name: str, value: Value) -> None:
            if isinstance(value, dict) and value:
                for key, child in value.items():
                    add(f"{name}.{key}", child)
            else:
                if name in flattened:
                    raise ExecutionError("pipeline.flatten: output names collide")
                flattened[name] = value

        try:
            for name, value in renamed.items():
                add(name, value)
        except RecursionError:
            raise ExecutionError("pipeline.flatten: object nesting is too deep") from None
        return flattened

    def serialize(
        self, records: Iterable[Record], *, redact: Callable[[str], str] | None = None
    ) -> Iterator[str]:
        if self.config.format == "jsonl":
            for record in records:
                try:
                    value = _redacted(record, redact) if redact is not None else record
                except RecursionError:
                    raise ExecutionError("preview: object nesting is too deep") from None
                yield _json(value) + "\n"
            return
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")

        def row(values: Iterable[Value]) -> str:
            buffer.seek(0)
            buffer.truncate()
            writer.writerow(values)
            return buffer.getvalue()

        columns = [redact(name) for name in self.config.columns] if redact else self.config.columns
        if len(set(columns)) != len(columns):
            raise ExecutionError("preview: redacted column names collide")
        yield row(columns)
        for record in records:
            cells: list[Value] = []
            for name in self.config.columns:
                value = record.get(name)
                if redact is not None:
                    try:
                        value = _redacted(value, redact)
                    except RecursionError:
                        raise ExecutionError("preview: object nesting is too deep") from None
                if isinstance(value, (dict, list)):
                    if not self.config.json_cells:
                        raise ExecutionError("pipeline.csv: object/array cells require json_cells")
                    value = _json(value)
                elif isinstance(value, (float, bool)):
                    value = _json(value)
                cells.append(value)
            yield row(cells)
