# 0002. CLI framework and package layout

- Status: accepted
- Date: 2026-11-02

## Context

The CLI needs subcommands. [pyproject.toml](../../pyproject.toml) has `pyyaml` as its only
dependency.

## Decision

- The CLI lives in `src/connector_cli` ([cli.py](../../src/connector_cli/cli.py)) and is exposed as
  the `connector-cli` console script.
- It uses stdlib `argparse`; click and typer are not used, so no dependency is added.
- The placeholder root `main.py` (scaffold generator) is removed; it was out of v1 scope.

## Consequences

- argparse is more verbose for subcommands.
- Scaffold generation is dropped until someone re-adds it.
