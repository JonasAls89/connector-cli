#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from string import Template
from typing import Any

try:
    import yaml
except ImportError:
    print("Install the dependency first: pip install pyyaml", file=sys.stderr)
    raise SystemExit(1) from None


CONNECTOR_YAML_TEMPLATE = """\
name: ${name}
display_name: ${display_name}
version: "${version}"

api:
  base_url: ${base_url}
  timeout_seconds: ${timeout_seconds}
  retries: ${retries}

auth:
  type: ${auth_type}
  token_env: ${token_env}

headers:
${headers}
"""

ENV_TEMPLATE = """\
# API credentials
${secret_env}=replace-me

# Optional override
${base_url_env}=

"""

REQUIREMENTS_TEMPLATE = """\
requests>=2.31.0,<3
python-dotenv>=1.0.0,<2
PyYAML>=6,<7
"""

README_TEMPLATE = """\
# ${display_name}

Generated standardized API connector.

## Configuration

Copy the environment template:

```bash
cp .env.example .env
```

Set the required secret:

```bash
${secret_env}=your-secret-value
```

## Usage

```python
from client import ApiClient

client = ApiClient.from_environment()

response = client.request(
    method="GET",
    path="${example_path}",
)

print(response.status_code)
print(response.json())
```

## Generated files

- `connector.yml`: standard connector metadata and API configuration.
- `client.py`: HTTP client with authentication, timeout, and retry handling.
- `.env.example`: environment variable template.
- `requirements.txt`: runtime dependencies.
"""

CLIENT_TEMPLATE = r"""\
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


CONFIG_PATH = Path(__file__).with_name("connector.yml")


@dataclass
class ApiClient:
    base_url: str
    timeout_seconds: int
    retries: int
    auth_type: str
    token: str | None
    token_env: str | None
    headers: dict[str, str]

    @classmethod
    def from_environment(cls) -> "ApiClient":
        load_dotenv()

        config = _load_yaml(CONFIG_PATH)
        api_config = config["api"]
        auth_config = config.get("auth", {})

        base_url = os.getenv(
            "API_BASE_URL",
            api_config["base_url"],
        ).rstrip("/")

        auth_type = auth_config.get("type", "none")
        token_env = auth_config.get("token_env")
        token = os.getenv(token_env) if token_env else None

        if auth_type != "none" and not token:
            raise RuntimeError(
                f"Missing authentication value. "
                f"Set the {token_env} environment variable."
            )

        return cls(
            base_url=base_url,
            timeout_seconds=int(api_config.get("timeout_seconds", 15)),
            retries=int(api_config.get("retries", 3)),
            auth_type=auth_type,
            token=token,
            token_env=token_env,
            headers=config.get("headers", {}),
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"

        request_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            **self.headers,
            **(headers or {}),
        }

        if self.auth_type == "bearer":
            request_headers["Authorization"] = f"Bearer {self.token}"

        elif self.auth_type == "api_key":
            request_headers["X-API-Key"] = str(self.token)

        last_error: Exception | None = None

        for attempt in range(self.retries + 1):
            try:
                response = requests.request(
                    method=method.upper(),
                    url=url,
                    params=query,
                    json=body,
                    headers=request_headers,
                    timeout=self.timeout_seconds,
                )

                if response.status_code >= 500 and attempt < self.retries:
                    time.sleep(2**attempt)
                    continue

                response.raise_for_status()
                return response

            except requests.RequestException as error:
                last_error = error

                if attempt >= self.retries:
                    raise

                time.sleep(2**attempt)

        raise RuntimeError("Request failed") from last_error


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)
"""


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        manifest = yaml.safe_load(file)

    if not isinstance(manifest, dict):
        raise ValueError("The manifest must contain a YAML object.")

    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: dict[str, Any]) -> None:
    required_fields = ["name", "display_name", "version", "api", "auth"]

    for field in required_fields:
        if field not in manifest:
            raise ValueError(f"Missing required manifest field: {field}")

    if not re.fullmatch(r"[a-z][a-z0-9_-]*", manifest["name"]):
        raise ValueError(
            "name must contain lowercase letters, numbers, underscores, or hyphens "
            "and must start with a letter."
        )

    api = manifest["api"]

    if "base_url" not in api:
        raise ValueError("api.base_url is required.")

    if not re.match(r"^https?://", api["base_url"]):
        raise ValueError("api.base_url must start with http:// or https://")

    auth = manifest["auth"]
    auth_type = auth.get("type", "none")

    if auth_type not in {"none", "bearer", "api_key"}:
        raise ValueError("auth.type must be one of: none, bearer, api_key")

    if auth_type != "none" and not auth.get("token_env"):
        raise ValueError("auth.token_env is required when authentication is enabled.")


def yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"

    if value is None:
        return "null"

    if isinstance(value, (int, float)):
        return str(value)

    text = str(value)

    if re.fullmatch(r"[A-Za-z0-9_./:-]+", text):
        return text

    return json.dumps(text)


def render_headers(headers: dict[str, Any]) -> str:
    if not headers:
        return "  {}"

    lines = []

    for key, value in headers.items():
        lines.append(f"  {key}: {yaml_scalar(value)}")

    return "\n".join(lines)


def render_connector_yaml(manifest: dict[str, Any]) -> str:
    api = manifest["api"]
    auth = manifest["auth"]

    values = {
        "name": manifest["name"],
        "display_name": manifest["display_name"],
        "version": manifest["version"],
        "base_url": yaml_scalar(api["base_url"]),
        "timeout_seconds": api.get("timeout_seconds", 15),
        "retries": api.get("retries", 3),
        "auth_type": auth.get("type", "none"),
        "token_env": auth.get("token_env", ""),
        "headers": render_headers(manifest.get("headers", {})),
    }

    return Template(CONNECTOR_YAML_TEMPLATE).safe_substitute(values)


def render_env_file(manifest: dict[str, Any]) -> str:
    auth = manifest["auth"]
    token_env = auth.get("token_env", "API_TOKEN")

    return Template(ENV_TEMPLATE).safe_substitute(
        secret_env=token_env,
        base_url_env="API_BASE_URL",
    )


def render_readme(manifest: dict[str, Any]) -> str:
    auth = manifest["auth"]

    return Template(README_TEMPLATE).safe_substitute(
        display_name=manifest["display_name"],
        secret_env=auth.get("token_env", "No secret required"),
        example_path=manifest.get("example_path", "/"),
    )


def generate_connector(manifest: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "connector.yml": render_connector_yaml(manifest),
        ".env.example": render_env_file(manifest),
        "requirements.txt": REQUIREMENTS_TEMPLATE,
        "README.md": render_readme(manifest),
        "client.py": CLIENT_TEMPLATE,
    }

    for filename, content in files.items():
        target = output_dir / filename
        target.write_text(content, encoding="utf-8")

    print(f"Generated connector: {output_dir}")
    for filename in files:
        print(f"  - {filename}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a standardized API connector.")

    parser.add_argument(
        "manifest",
        type=Path,
        help="Path to the connector YAML manifest.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory where the connector will be generated.",
    )

    args = parser.parse_args()

    try:
        manifest = load_manifest(args.manifest)
        generate_connector(manifest, args.output)
    except FileNotFoundError as error:
        print(f"File not found: {error.filename}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"Invalid manifest: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
