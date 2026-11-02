import copy

import pytest
import yaml

from connector_cli.cli import main
from connector_cli.config import ConfigError, load, parse

VALID = {
    "name": "stripe",
    "source": {
        "type": "stripe",
        "resource": "customers",
        "api": {"base_url": "https://api.stripe.com", "timeout_seconds": 15, "retries": 3},
        "auth": {"type": "bearer", "token_env": "STRIPE_SECRET_KEY"},
        "headers": {"Accept": "application/json"},
    },
    "pipeline": {"select": ["id"], "rename": {"id": "x"}, "cast": {"x": "int"}, "format": "csv"},
    "sink": {"type": "local", "limit": 5, "path": "out"},
}


def errors_for(mutate) -> list[str]:
    data = copy.deepcopy(VALID)
    mutate(data)
    with pytest.raises(ConfigError) as exc:
        parse(data)
    return exc.value.errors


def test_valid_full():
    c = parse(VALID)
    assert c.source.resource == "customers"
    assert c.pipeline.format == "csv"
    assert c.sink.limit == 5


def test_defaults():
    c = parse({"source": {"type": "stripe", "resource": "r"}, "sink": {"type": "local"}})
    assert c.source.timeout_seconds == 15
    assert c.source.retries == 3
    assert c.sink.limit == 10
    assert c.pipeline.format == "jsonl"


def test_repo_connector_file_is_valid():
    assert load("stripe.connector.yml").source.type == "stripe"


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda d: d["source"].pop("resource"), "source.resource: required"),
        (lambda d: d.pop("sink"), "sink: required section"),
        (lambda d: d.pop("source"), "source: required section"),
        (lambda d: d["source"].update(extra=1), "source.extra: unknown key"),
        (lambda d: d["sink"].update(extra=1), "sink.extra: unknown key"),
        (lambda d: d["pipeline"].update(extra=1), "pipeline.extra: unknown key"),
        (lambda d: d.update(runtime={}), "runtime: unknown key"),
        (lambda d: d["source"].update(type="x"), "source.type: must be one of"),
        (lambda d: d["sink"].update(type="s3"), "sink.type: must be one of"),
        (lambda d: d["pipeline"].update(cast={"a": "date"}), "pipeline.cast.a: must be one of"),
        (lambda d: d["pipeline"].update(cast=[1]), "pipeline.cast: must be a mapping"),
        (lambda d: d["pipeline"].update(format="parquet"), "pipeline.format: must be one of"),
        (lambda d: d["pipeline"].update(select="id"), "pipeline.select: must be a list"),
        (lambda d: d["pipeline"].update(rename={"a": 1}), "pipeline.rename: must be a mapping"),
        (lambda d: d["sink"].update(limit=0), "sink.limit: must be an integer"),
        (lambda d: d["sink"].update(limit=True), "sink.limit: must be an integer"),
        (lambda d: d["sink"].update(path=""), "sink.path: must be a non-empty"),
        (lambda d: d["source"]["api"].update(retries=-1), "source.api.retries"),
        (lambda d: d["source"]["api"].update(base_url=3), "source.api.base_url"),
        (lambda d: d["source"]["auth"].pop("type"), "source.auth.type: required"),
        (lambda d: d["source"].update(auth=[]), "source.auth: must be a mapping"),
        (lambda d: d["source"].update(headers={"a": 1}), "source.headers: must be a mapping"),
        (lambda d: d["source"].update(api=[]), "source.api: must be a mapping"),
        (lambda d: d["source"].update(resource=3), "source.resource: must be a non-empty"),
        (lambda d: d.update(source=[]), "source: must be a mapping"),
        (lambda d: d.update(pipeline=[]), "pipeline: must be a mapping"),
        (lambda d: d.update(name=3), "name: must be a non-empty"),
    ],
)
def test_invalid(mutate, expected):
    assert any(expected in e for e in errors_for(mutate))


def test_root_not_mapping():
    with pytest.raises(ConfigError, match="<root>"):
        parse([1])


def test_load_errors(tmp_path):
    with pytest.raises(ConfigError, match="cannot read"):
        load(tmp_path / "missing.yml")
    bad = tmp_path / "bad.yml"
    bad.write_text("a: [", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load(bad)


def test_cli(tmp_path, capsys):
    good = tmp_path / "g.yml"
    good.write_text(yaml.safe_dump(VALID), encoding="utf-8")
    assert main(["validate", str(good)]) == 0
    assert "valid" in capsys.readouterr().out
    bad = tmp_path / "b.yml"
    bad.write_text("source: {}\n", encoding="utf-8")
    assert main(["validate", str(bad)]) == 1
    assert "source.type: required" in capsys.readouterr().err
