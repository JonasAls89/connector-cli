import py_compile
import runpy

import yaml


def test_prototype_stays_separate_and_generates_valid_python(tmp_path):
    prototype = runpy.run_path("main.py", run_name="connector_generator_prototype")
    manifest = {
        "name": "example",
        "display_name": "Example",
        "version": "1.0",
        "api": {"base_url": "https://example.test"},
        "auth": {"type": "bearer", "token_env": "EXAMPLE_TOKEN"},
    }
    prototype["validate_manifest"](manifest)
    prototype["generate_connector"](manifest, tmp_path)
    generated = yaml.safe_load((tmp_path / "connector.yml").read_text(encoding="utf-8"))
    assert generated["api"]["base_url"] == "https://example.test"
    assert "source" not in generated
    py_compile.compile(str(tmp_path / "client.py"), doraise=True)
    assert "PyYAML" in (tmp_path / "requirements.txt").read_text(encoding="utf-8")
