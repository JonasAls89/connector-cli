import os
import subprocess
import sys
from pathlib import Path

import yaml


def test_installed_entrypoint_works_outside_repository(definition, tmp_path):
    path = tmp_path / "connector.yml"
    path.write_text(yaml.safe_dump(definition), encoding="utf-8")
    executable = Path(sys.executable).with_name(
        "connector-cli.exe" if os.name == "nt" else "connector-cli"
    )
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run(  # noqa: S603 - fixed installed command and test-owned file, no shell.
        [str(executable), "validate", str(path)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"{path}: valid"
