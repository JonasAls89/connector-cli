# connector-cli

Execute versioned YAML connector definitions through a reusable REST source,
record pipeline, and local-file sink. The [runtime](src/connector_cli/runtime.py)
implements the [accepted design](docs/adr/0003-configuration-driven-runtime.md);
the ADR's implementation status describes the decision-time scaffold.

## Usage

Install the project's dependencies:

```sh
uv sync --locked
```

Validate either reference definition without credentials or network access:

```sh
uv run --no-editable connector-cli validate stripe.connector.yml
uv run --no-editable connector-cli validate enhetsregisteret.connector.yml
```

Read a live sample from the public entity register:

```sh
uv run --no-editable connector-cli preview enhetsregisteret.connector.yml --limit 5
```

Deliver the configured extraction to a local file:

```sh
uv run --no-editable connector-cli run enhetsregisteret.connector.yml
uv run --no-editable connector-cli run enhetsregisteret.connector.yml --overwrite
```

The [Stripe example](stripe.connector.yml) requires `STRIPE_SECRET_KEY` in the
environment for `run` and `preview`. Do not put credentials in the YAML file.
Both examples intentionally limit acquisition to 10 records.

Preview makes real HTTP requests but never writes to the configured sink.
Runs publish local output only after success, refuse existing destinations
unless `--overwrite` is given, and exit nonzero on incomplete extraction.
Output paths are relative to the current working directory; their parent
directories must already exist. See the [CLI and adapter contracts](docs/RUNTIME.md)
and [configuration reference](docs/CONFIGURATION.md).

## Development

```sh
uv run ruff check .
uv run ruff format --check .
uv run bandit -c pyproject.toml -r .
uv run pytest
```

After documentation changes, invoke `/wayfinder-context` in Copilot to refresh
the [context index](docs/CONTEXT.md) and validate the
[guardrails](docs/GUARDRAILS.md). This is a skill invocation, not a shell command.

[Tests](tests/) use controlled HTTP transports and temporary files, never live
APIs or real credentials. The [coverage gate](pyproject.toml) requires 90%.
To verify a non-editable installation independently of the project environment:

```sh
uv run --isolated --no-editable --reinstall-package connector-cli pytest
```

Run `uv run prek run --all-files` before committing. The
[hook configuration](.pre-commit-config.yaml) includes pytest for Python and
project-configuration changes.

[main.py](main.py) remains a separate client-generator prototype with its own
manifest. It is not the installed CLI and its format is not accepted by the
runtime.
