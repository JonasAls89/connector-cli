import base64
import csv
import io
import json

import httpx
import pytest
import yaml

from connector_cli.cli import main
from connector_cli.config import ConfigError, load, parse
from connector_cli.interfaces import ExecutionError
from connector_cli.pipeline import RecordPipeline
from connector_cli.runtime import default_registry, preview, run


@pytest.mark.parametrize("filename", ["stripe.connector.yml", "enhetsregisteret.connector.yml"])
def test_reference_definitions_execute_through_same_rest_adapter(filename, tmp_path):
    connector = load(filename)
    connector.sink.path = str(tmp_path / "records.jsonl")
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.host == "api.stripe.com":
            assert request.headers["Authorization"] == "Bearer example-test-token"
            if "starting_after" not in request.url.params:
                return httpx.Response(200, json={"data": [{"id": "a"}], "has_more": True})
            assert request.url.params["starting_after"] == "a"
            return httpx.Response(200, json={"data": [{"id": "b"}], "has_more": False})
        assert "Authorization" not in request.headers
        page = int(request.url.params["page"])
        return httpx.Response(
            200,
            json={
                "_embedded": {"enheter": [{"organisasjonsnummer": str(page)}]},
                "page": {"totalPages": 2},
            },
        )

    registry = default_registry(
        transport=httpx.MockTransport(handler), environ={"STRIPE_SECRET_KEY": "example-test-token"}
    )
    assert run(connector, registry=registry) == 2
    assert len(requests) == 2
    records = [json.loads(line) for line in (tmp_path / "records.jsonl").read_text().splitlines()]
    assert len(records) == 2
    assert records[0] != records[1]


def test_preview_is_live_bounded_and_never_constructs_sink(definition):
    definition["source"]["pagination"] = {"type": "page", "param": "page"}
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"data": [{"id": i} for i in range(20)]})

    def forbidden_sink(config):
        pytest.fail("preview must not construct the configured sink")

    registry = default_registry(transport=httpx.MockTransport(handler))
    registry.sinks["local"] = forbidden_sink
    output = io.StringIO()
    connector = parse(definition)
    assert preview(connector, registry=registry, output=output) == 10
    assert len(output.getvalue().splitlines()) == 10
    assert len(requests) == 1
    connector.limit = 3
    output = io.StringIO()
    assert preview(connector, registry=registry, output=output) == 3
    assert len(output.getvalue().splitlines()) == 3


@pytest.mark.parametrize("format_name", ["jsonl", "csv"])
@pytest.mark.parametrize("echoed_value", ['example"secret', "\\"])
def test_preview_redacts_credentials_even_when_echoed_and_encoded(
    definition, format_name, echoed_value
):
    definition["source"]["auth"] = {
        "type": "basic",
        "username_env": "API_USER",
        "password_env": "API_PASSWORD",
    }
    definition["pipeline"] = {"format": format_name}
    if format_name == "csv":
        definition["pipeline"]["csv"] = {"columns": ["value"]}
    encoded = base64.b64encode(f"operator:{echoed_value}".encode()).decode()

    def handler(request):
        assert request.headers["Authorization"] == f"Basic {encoded}"
        return httpx.Response(200, json={"data": [{"value": echoed_value}]})

    registry = default_registry(
        transport=httpx.MockTransport(handler),
        environ={"API_USER": "operator", "API_PASSWORD": echoed_value},
    )
    output = io.StringIO()
    assert preview(parse(definition), registry=registry, output=output) == 1
    if format_name == "jsonl":
        assert json.loads(output.getvalue()) == {"value": "[REDACTED]"}
    else:
        assert list(csv.reader(io.StringIO(output.getvalue())))[1] == ["[REDACTED]"]


def test_custom_source_registration_closes_on_early_limit_and_failure(definition):
    closed = []

    class MemorySource:
        secrets = ("example-secret-value",)

        def records(self, limit):
            try:
                for i in range(20):
                    yield {"id": i}
            finally:
                closed.append(True)

    connector = parse(definition)
    connector.source.type = "memory"
    registry = default_registry()
    registry.sources["memory"] = lambda _: MemorySource()
    assert preview(connector, registry=registry, output=io.StringIO(), limit=2) == 2
    assert closed == [True]

    class BrokenOutput(io.StringIO):
        def write(self, text):
            raise OSError("simulated stdout failure")

    with pytest.raises(ExecutionError, match="cannot write output"):
        preview(connector, registry=registry, output=BrokenOutput())
    assert closed == [True, True]


def test_registered_pipeline_and_sink_use_public_interfaces(definition):
    received = []

    class UppercasePipeline(RecordPipeline):
        def transform(self, record):
            return {"name": record["name"].upper()}

    class MemorySink:
        def write(self, chunks, *, overwrite):
            received.extend(chunks)

    connector = parse(definition)
    connector.pipeline.type = "uppercase"
    connector.sink.type = "memory"
    registry = default_registry(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"data": [{"name": "ada"}]})
        )
    )
    registry.pipelines["uppercase"] = UppercasePipeline
    registry.sinks["memory"] = lambda _: MemorySink()
    assert run(connector, registry=registry) == 1
    assert json.loads(received[0]) == {"name": "ADA"}


def test_unknown_adapters_report_all_sections(definition):
    connector = parse(definition)
    connector.source.type = connector.pipeline.type = connector.sink.type = "unknown"
    with pytest.raises(ConfigError) as error:
        default_registry().validate(connector)
    assert len(error.value.errors) == 3


@pytest.mark.parametrize("limit", [0, -1, True])
def test_preview_rejects_invalid_limit(definition, limit):
    with pytest.raises(ExecutionError, match="positive integer"):
        preview(parse(definition), limit=limit)


def test_cli_commands_and_explicit_overwrite(definition, tmp_path, capsys):
    path = tmp_path / "connector.yml"
    path.write_text(yaml.safe_dump(definition), encoding="utf-8")
    registry = default_registry(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"data": [{"id": 1}]}))
    )
    assert main(["run", str(path)], registry=registry) == 0
    assert "delivered 1 records" in capsys.readouterr().out
    assert main(["run", str(path)], registry=registry) == 1
    assert "destination exists" in capsys.readouterr().err
    assert main(["run", str(path), "--overwrite"], registry=registry) == 0
    capsys.readouterr()
    assert main(["preview", str(path), "--limit", "1"], registry=registry) == 0
    assert json.loads(capsys.readouterr().out) == {"id": 1}


@pytest.mark.parametrize("value", ["0", "-1", "not-an-integer"])
def test_cli_preview_limit_errors(value):
    with pytest.raises(SystemExit) as error:
        main(["preview", "unused.yml", "--limit", value])
    assert error.value.code == 2


def test_cli_failure_after_first_page_preserves_destination(definition, tmp_path, capsys):
    destination = tmp_path / "output.jsonl"
    destination.write_text("original", encoding="utf-8")
    definition["source"].update(
        auth={"type": "bearer", "token_env": "TOKEN"},
        pagination={"type": "page", "param": "page"},
    )
    path = tmp_path / "connector.yml"
    path.write_text(yaml.safe_dump(definition), encoding="utf-8")
    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, json={"data": [{"id": 1}]})
        return httpx.Response(401, text="example-secret-value")

    registry = default_registry(
        transport=httpx.MockTransport(handler), environ={"TOKEN": "example-secret-value"}
    )
    assert main(["run", str(path), "--overwrite"], registry=registry) == 1
    captured = capsys.readouterr()
    assert "HTTP 401" in captured.err
    assert "example-secret-value" not in captured.err + captured.out
    assert destination.read_text(encoding="utf-8") == "original"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["connector.yml", "output.jsonl"]


def test_missing_credentials_fail_before_requests_or_output(definition, tmp_path):
    definition["source"]["auth"] = {"type": "bearer", "token_env": "TOKEN"}
    connector = parse(definition)
    with pytest.raises(ExecutionError, match="missing or empty"):
        run(connector, registry=default_registry(environ={}))
    assert list(tmp_path.iterdir()) == []
