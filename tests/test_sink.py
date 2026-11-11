import os
from pathlib import Path

import pytest

from connector_cli.config import Sink
from connector_cli.interfaces import ExecutionError
from connector_cli.sink import LocalSink


def test_streaming_output_is_not_published_until_complete(tmp_path):
    destination = tmp_path / "output.jsonl"

    def chunks():
        yield '{"id":1}\n'
        assert not destination.exists()
        yield '{"id":2}\n'

    LocalSink(Sink("local", str(destination))).write(chunks())
    assert destination.read_text(encoding="utf-8") == '{"id":1}\n{"id":2}\n'
    assert list(tmp_path.iterdir()) == [destination]


def test_existing_destination_requires_explicit_overwrite(tmp_path):
    destination = tmp_path / "output"
    destination.write_text("original", encoding="utf-8")
    sink = LocalSink(Sink("local", str(destination)))

    def chunks():
        assert destination.read_text(encoding="utf-8") == "original"
        yield "replacement"
        assert destination.read_text(encoding="utf-8") == "original"

    with pytest.raises(ExecutionError, match="use --overwrite"):
        sink.write(chunks())
    assert destination.read_text(encoding="utf-8") == "original"
    sink.write(chunks(), overwrite=True)
    assert destination.read_text(encoding="utf-8") == "replacement"


@pytest.mark.parametrize("existing", [False, True])
def test_failed_extraction_never_publishes_partial_output(tmp_path, existing):
    destination = tmp_path / "output"
    if existing:
        destination.write_text("original", encoding="utf-8")

    def broken_chunks():
        yield "partial"
        raise ExecutionError("source failed")

    with pytest.raises(ExecutionError, match="source failed"):
        LocalSink(Sink("local", str(destination))).write(broken_chunks(), overwrite=existing)
    assert destination.exists() == existing
    if existing:
        assert destination.read_text(encoding="utf-8") == "original"
    assert sorted(tmp_path.iterdir()) == ([destination] if existing else [])


def test_no_overwrite_handles_creation_race(tmp_path, monkeypatch):
    destination = tmp_path / "output"
    real_link = os.link

    def racing_link(source, target):
        destination.write_text("other writer", encoding="utf-8")
        real_link(source, target)

    monkeypatch.setattr("connector_cli.sink.os.link", racing_link)
    with pytest.raises(ExecutionError, match="destination exists"):
        LocalSink(Sink("local", str(destination))).write(["new"])
    assert destination.read_text(encoding="utf-8") == "other writer"
    assert list(tmp_path.iterdir()) == [destination]


@pytest.mark.parametrize("operation", ["fsync", "replace"])
def test_publication_failures_preserve_existing_output(tmp_path, monkeypatch, operation):
    destination = tmp_path / "output"
    destination.write_text("original", encoding="utf-8")

    def fail(*args):
        raise OSError("simulated filesystem failure")

    monkeypatch.setattr(f"connector_cli.sink.os.{operation}", fail)
    with pytest.raises(ExecutionError, match="cannot write or publish"):
        LocalSink(Sink("local", str(destination))).write(["new"], overwrite=True)
    assert destination.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.iterdir()) == [destination]


def test_missing_parent_and_invalid_encoding_are_explicit(tmp_path):
    with pytest.raises(ExecutionError, match="cannot write or publish"):
        LocalSink(Sink("local", str(tmp_path / "missing" / "output"))).write(["new"])
    with pytest.raises(ExecutionError, match="cannot write or publish"):
        LocalSink(Sink("local", str(tmp_path / "output"))).write(["\ud800"])
    assert list(tmp_path.iterdir()) == []


def test_cleanup_failure_is_reported(tmp_path, monkeypatch):
    destination = tmp_path / "output"

    def fail_unlink(self, **kwargs):
        raise OSError("simulated cleanup failure")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail_unlink)
        with pytest.raises(ExecutionError, match="could not remove temporary"):
            LocalSink(Sink("local", str(destination))).write(["complete"])
    assert destination.read_text(encoding="utf-8") == "complete"
    for path in tmp_path.glob(".*.tmp"):
        path.unlink()


def test_overwrite_does_not_unlink_a_consumed_temporary_path(tmp_path, monkeypatch):
    destination = tmp_path / "output"
    destination.write_text("original", encoding="utf-8")

    def forbidden_unlink(self, **kwargs):
        pytest.fail("the temporary path is no longer owned after atomic replacement")

    monkeypatch.setattr(Path, "unlink", forbidden_unlink)
    LocalSink(Sink("local", str(destination))).write(["replacement"], overwrite=True)
    assert destination.read_text(encoding="utf-8") == "replacement"


def test_broken_symlink_is_still_an_existing_destination(tmp_path):
    destination = tmp_path / "output"
    destination.symlink_to(tmp_path / "missing")
    with pytest.raises(ExecutionError, match="destination exists"):
        LocalSink(Sink("local", str(destination))).write(["new"])
    assert destination.is_symlink()
