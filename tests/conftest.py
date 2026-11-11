import httpx
import pytest


@pytest.fixture
def definition(tmp_path):
    return {
        "schema_version": 1,
        "source": {
            "type": "rest",
            "url": "https://example.test/items",
            "records_path": "data",
        },
        "sink": {"type": "local", "path": str(tmp_path / "output.jsonl")},
    }


@pytest.fixture(autouse=True)
def forbid_live_http(monkeypatch):
    def fail_request(self, request):
        pytest.fail("Tests must use a controlled HTTP transport")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", fail_request)
