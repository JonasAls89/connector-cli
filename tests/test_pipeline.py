import csv
import io
import json

import pytest

from connector_cli.config import Pipeline
from connector_cli.interfaces import ExecutionError
from connector_cli.pipeline import RecordPipeline


def test_select_nested_paths_missing_fields_and_rename():
    pipeline = RecordPipeline(
        Pipeline(select=["profile.name", "missing", "array.0"], rename={"profile.name": "name"})
    )
    record = {"profile": {"name": "Ada"}, "array": [1]}
    assert pipeline.transform(record) == {"name": "Ada", "missing": None, "array.0": None}
    assert record == {"profile": {"name": "Ada"}, "array": [1]}


def test_flatten_preserves_arrays_and_empty_objects():
    record = {"profile": {"name": "Ada", "empty": {}}, "items": [{"id": 1}]}
    pipeline = RecordPipeline(Pipeline(flatten=True, rename={"profile": "person"}))
    assert pipeline.transform(record) == {
        "person.name": "Ada",
        "person.empty": {},
        "items": [{"id": 1}],
    }


@pytest.mark.parametrize(
    ("config", "record", "message"),
    [
        (Pipeline(rename={"a": "b"}), {"a": 1, "b": 2}, "collide"),
        (Pipeline(rename={"missing": "x"}), {"a": 1}, "absent"),
        (Pipeline(flatten=True), {"a": {"b": 1}, "a.b": 2}, "collide"),
    ],
)
def test_collisions_fail(config, record, message):
    with pytest.raises(ExecutionError, match=message):
        RecordPipeline(config).transform(record)


def test_empty_selection_and_jsonl():
    pipeline = RecordPipeline(Pipeline(select=[]))
    assert list(pipeline.serialize([pipeline.transform({"id": 1})])) == ["{}\n"]
    original = {"nested": {"name": "\u00e6"}, "array": [True, None]}
    serialized = list(RecordPipeline(Pipeline()).serialize([original]))
    assert len(serialized) == 1
    assert serialized[0].endswith("\n")
    assert json.loads(serialized[0]) == original


def test_csv_declared_columns_scalar_encoding_and_missing_values():
    pipeline = RecordPipeline(Pipeline(format="csv", columns=["id", "active", "ratio", "missing"]))
    data = "".join(pipeline.serialize([{"ignored": "x", "id": 1, "active": True, "ratio": 1.5}]))
    assert list(csv.reader(io.StringIO(data))) == [
        ["id", "active", "ratio", "missing"],
        ["1", "true", "1.5", ""],
    ]


def test_csv_json_cells_and_quoting():
    pipeline = RecordPipeline(Pipeline(format="csv", columns=["name", "nested"], json_cells=True))
    original = {"name": 'a,"quoted"\nname', "nested": [{"id": 1}]}
    data = "".join(pipeline.serialize([original]))
    rows = list(csv.reader(io.StringIO(data)))
    assert rows[0] == ["name", "nested"]
    assert rows[1][0] == original["name"]
    assert json.loads(rows[1][1]) == original["nested"]


@pytest.mark.parametrize("value", [{"id": 1}, [1, 2]])
def test_csv_nested_values_require_explicit_encoding(value):
    pipeline = RecordPipeline(Pipeline(format="csv", columns=["value"]))
    with pytest.raises(ExecutionError, match="require json_cells"):
        list(pipeline.serialize([{"value": value}]))


@pytest.mark.parametrize("format_name", ["jsonl", "csv"])
def test_nonfinite_numbers_fail(format_name):
    pipeline = RecordPipeline(Pipeline(format=format_name, columns=["value"]))
    with pytest.raises(ExecutionError, match="represented as JSON"):
        list(pipeline.serialize([{"value": float("inf")}]))


def test_recursive_records_fail_explicitly():
    record = {}
    record["self"] = record
    with pytest.raises(ExecutionError, match="nesting is too deep"):
        RecordPipeline(Pipeline(flatten=True)).transform(record)
    with pytest.raises(ExecutionError, match="represented as JSON"):
        list(RecordPipeline(Pipeline()).serialize([record]))


def test_preview_redacts_nested_values_before_serialization():
    record = {"private": ["example-value", {"private": "example-value"}, 1, None]}
    pipeline = RecordPipeline(Pipeline())
    output = "".join(
        pipeline.serialize(
            [record], redact=lambda text: text.replace("example-value", "[REDACTED]")
        )
    )
    assert json.loads(output) == {"private": ["[REDACTED]", {"private": "[REDACTED]"}, 1, None]}


@pytest.mark.parametrize("format_name", ["jsonl", "csv"])
def test_preview_redaction_collisions_are_explicit(format_name):
    pipeline = RecordPipeline(Pipeline(format=format_name, columns=["a", "b"]))
    with pytest.raises(ExecutionError, match="collide"):
        list(pipeline.serialize([{"a": 1, "b": 2}], redact=lambda _: "[REDACTED]"))


@pytest.mark.parametrize("format_name", ["jsonl", "csv"])
def test_preview_recursive_values_fail_explicitly(format_name):
    nested = {}
    nested["self"] = nested
    pipeline = RecordPipeline(Pipeline(format=format_name, columns=["nested"], json_cells=True))
    with pytest.raises(ExecutionError, match="nesting is too deep"):
        list(pipeline.serialize([{"nested": nested}], redact=lambda text: text))
