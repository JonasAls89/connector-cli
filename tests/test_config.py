import pytest
import yaml

from connector_cli.cli import main
from connector_cli.config import ConfigError, load, parse
from connector_cli.runtime import default_registry


def test_defaults(definition):
    connector = parse(definition)
    assert connector.schema_version == 1
    assert connector.limit is None
    assert connector.source.timeout_seconds == 15
    assert connector.source.retries == 3
    assert connector.source.max_retry_delay_seconds == 60
    assert connector.source.auth.type == "none"
    assert connector.source.pagination.type == "none"
    assert connector.pipeline.type == "records"
    assert connector.pipeline.format == "jsonl"


@pytest.mark.parametrize("filename", ["stripe.connector.yml", "enhetsregisteret.connector.yml"])
def test_reference_definitions(filename):
    connector = load(filename)
    default_registry().validate(connector)
    assert connector.source.type == "rest"
    assert connector.limit == 10


def test_full_definition(definition):
    definition.update(name="example", display_name="Example", version="1.0", limit=20)
    definition["source"].update(
        query={"size": 20, "active": True, "ratio": 1.5, "name": "example"},
        headers={"Accept": "application/json"},
        auth={"type": "basic", "username_env": "API_USER", "password_env": "API_PASSWORD"},
        pagination={"type": "page", "param": "page", "start": 1, "total_pages_path": "pages"},
    )
    definition["pipeline"] = {
        "select": ["nested.id", "missing"],
        "rename": {"nested.id": "id"},
        "flatten": True,
        "format": "csv",
        "csv": {"columns": ["id", "missing"], "json_cells": True},
    }
    connector = parse(definition)
    assert connector.name == "example"
    assert connector.source.auth.username_env == "API_USER"
    assert connector.source.pagination.start == 1
    assert connector.pipeline.columns == ["id", "missing"]
    assert connector.pipeline.json_cells


@pytest.mark.parametrize(
    ("section", "changes", "expected"),
    [
        ("", {"schema_version": 2}, "schema_version"),
        ("", {"schema_version": True}, "schema_version"),
        ("", {"schema_version": "1"}, "schema_version"),
        ("", {"limit": 0}, "limit"),
        ("", {"limit": True}, "limit"),
        ("", {"name": 1}, "name"),
        ("", {"extra": 1}, "unknown key"),
        ("source", {"type": ""}, "source.type"),
        ("source", {"url": 3}, "source.url"),
        ("source", {"url": "file:///tmp/records"}, "source.url"),
        ("source", {"url": "https://user:example@example.test/items"}, "source.url"),
        ("source", {"url": "https://example.test/items?key=example"}, "source.url"),
        ("source", {"url": "https://example.test/items#fragment"}, "source.url"),
        ("source", {"url": "https://example.test:bad/items"}, "source.url"),
        ("source", {"extra": 1}, "source.extra"),
        ("source", {"records_path": "a..b"}, "records_path"),
        ("source", {"timeout_seconds": 0}, "timeout_seconds"),
        ("source", {"retries": 11}, "retries"),
        ("source", {"max_retry_delay_seconds": 0}, "max_retry_delay_seconds"),
        ("source", {"query": []}, "source.query"),
        ("source", {"query": {"x": None}}, "source.query"),
        ("source", {"query": {"x": float("inf")}}, "source.query"),
        ("source", {"headers": {"x": 1}}, "source.headers"),
        ("source", {"headers": {"Authorization": "example"}}, "source.headers"),
        ("source", {"headers": {"Cookie": "example"}}, "source.headers"),
        ("source", {"headers": {"Host": "example.test"}}, "source.headers"),
        ("source", {"headers": {"bad key": "x"}}, "source.headers"),
        ("source", {"headers": {"X-Header": "a\nb"}}, "source.headers"),
        ("source", {"headers": {"X-Header": "\u00e6"}}, "source.headers"),
        ("source", {"auth": []}, "source.auth"),
        ("source", {"auth": {"type": "oauth"}}, "source.auth.type"),
        ("source", {"auth": {"type": "bearer"}}, "token_env"),
        ("source", {"auth": {"type": "bearer", "token_env": "not-an-env"}}, "token_env"),
        ("source", {"auth": {"type": "none", "token_env": "TOKEN"}}, "token_env"),
        ("source", {"auth": {"type": "basic", "username_env": "USER"}}, "password_env"),
        ("source", {"pagination": []}, "source.pagination"),
        ("source", {"pagination": {"type": "offset"}}, "source.pagination.type"),
        ("source", {"pagination": {"type": "page"}}, "source.pagination.param"),
        ("source", {"pagination": {"type": "page", "param": "page", "start": 2}}, "start"),
        ("source", {"pagination": {"type": "cursor", "param": "after"}}, "cursor_path"),
        ("source", {"pagination": {"type": "next_link"}}, "next_path"),
        ("source", {"pagination": {"type": "none", "next_path": "next"}}, "unknown key"),
        ("pipeline", {"type": 3}, "pipeline.type"),
        ("pipeline", {"select": "id"}, "pipeline.select"),
        ("pipeline", {"select": ["id", "id"]}, "duplicates"),
        ("pipeline", {"select": ["a..b"]}, "field path"),
        ("pipeline", {"rename": {"id": 3}}, "pipeline.rename"),
        ("pipeline", {"select": ["id"], "rename": {"other": "x"}}, "selected fields"),
        ("pipeline", {"select": ["id", "x"], "rename": {"id": "x"}}, "collide"),
        ("pipeline", {"flatten": "yes"}, "pipeline.flatten"),
        ("pipeline", {"format": "parquet"}, "pipeline.format"),
        ("pipeline", {"format": "csv"}, "pipeline.csv.columns"),
        ("pipeline", {"format": "csv", "csv": {"columns": []}}, "at least one"),
        ("pipeline", {"format": "csv", "csv": {"columns": ["a", "a"]}}, "duplicates"),
        ("pipeline", {"format": "csv", "csv": {"columns": ["a"], "json_cells": 1}}, "boolean"),
        ("pipeline", {"csv": {"columns": ["id"]}}, "only valid"),
        ("pipeline", {"cast": {"id": "int"}}, "unknown key"),
        ("sink", {"path": ""}, "sink.path"),
        ("sink", {"path": "\x00"}, "sink.path"),
        ("sink", {"limit": 10}, "unknown key"),
    ],
)
def test_invalid_fields(definition, section, changes, expected):
    target = definition.setdefault(section, {}) if section else definition
    target.update(changes)
    with pytest.raises(ConfigError, match=expected):
        parse(definition)


@pytest.mark.parametrize("key", ["schema_version", "source", "sink"])
def test_required_sections(definition, key):
    del definition[key]
    with pytest.raises(ConfigError, match="required key"):
        parse(definition)


@pytest.mark.parametrize("section", ["source", "pipeline", "sink"])
def test_sections_must_be_mappings(definition, section):
    definition[section] = []
    with pytest.raises(ConfigError, match="must be a mapping"):
        parse(definition)


def test_root_and_mapping_keys(definition):
    with pytest.raises(ConfigError, match="<root>"):
        parse([1])
    definition[False] = "not a string key"
    with pytest.raises(ConfigError, match="keys must be strings"):
        parse(definition)


def test_https_auth_and_pagination_owned_query(definition):
    definition["source"].update(
        url="http://example.test/items",
        auth={"type": "bearer", "token_env": "TOKEN"},
        query={"page": 2},
        pagination={"type": "page", "param": "page"},
    )
    with pytest.raises(ConfigError) as error:
        parse(definition)
    assert "authentication requires HTTPS" in str(error.value)
    assert "pagination-owned" in str(error.value)


def test_load_failures_do_not_echo_contents(tmp_path):
    with pytest.raises(ConfigError, match="cannot read"):
        load(tmp_path / "missing.yml")
    path = tmp_path / "bad.yml"
    path.write_text("example-secret-value: [", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML") as error:
        load(path)
    assert "example-secret-value" not in str(error.value)
    path.write_bytes(b"\xff")
    with pytest.raises(ConfigError, match="UTF-8"):
        load(path)


def test_duplicate_yaml_keys_and_unsafe_tags_are_rejected(tmp_path):
    path = tmp_path / "duplicate.yml"
    path.write_text("schema_version: 1\nschema_version: 1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load(path)
    path.write_text("\x00", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load(path)
    path.write_text("!!python/object:builtins.object {}", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load(path)


def test_offline_cli_validation(definition, tmp_path, capsys):
    definition["source"]["auth"] = {"type": "bearer", "token_env": "UNSET_TEST_TOKEN"}
    path = tmp_path / "connector.yml"
    path.write_text(yaml.safe_dump(definition), encoding="utf-8")
    assert main(["validate", str(path)], registry=default_registry(environ={})) == 0
    assert "valid" in capsys.readouterr().out
    definition["source"]["type"] = "unregistered"
    path.write_text(yaml.safe_dump(definition), encoding="utf-8")
    assert main(["validate", str(path)]) == 1
    assert "source.type: no adapter is registered" in capsys.readouterr().err
