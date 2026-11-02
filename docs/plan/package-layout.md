<!-- automagic:node package-layout 0f5c8506d115b8ed85196f213c74ec3781cc94430fe0c0a837f07baf01e190d9 -->
# Package layout and CLI entrypoint

Planning topic `package-layout`, hash `0f5c8506d115b8ed85196f213c74ec3781cc94430fe0c0a837f07baf01e190d9`. Goal: I want to build a connector cli that standardizes how to connect to a source in components: source, pipeline, sink. Source should connect to data sources, the pipeline should adapt the schema and file format to the target, and the sink should dump/stream data to a storage container/database or allow for previewing locally if developing on a local machine.
Work item: `wi-01`

## Agreed scope

Decision: The CLI lives in a new src/connector_cli package with a cli module. It is exposed as a console script named 'connector-cli', registered in pyproject.toml. It is built with stdlib argparse, so no new dependency is added (click and typer are not used). The root main.py is removed, because its scaffold-generation behavior is out of v1 scope. The framework choice is recorded in docs/adr/0002-cli-framework.md.

Tradeoff accepted: argparse is more verbose than click or typer for subcommands. Removing main.py drops the scaffold generator until someone re-adds it.

## Boundaries

- Estimated change: about 80 lines (budget 400 per work item).
- Expected files: `pyproject.toml`, `src/connector_cli/__init__.py`, `src/connector_cli/cli.py`, `main.py`, `docs/adr/0002-cli-framework.md`
- `automagic review` flags changes outside these files; guardrail, CI and config files need to be listed here to be changed.

## Depends on

- [Technical constraints from repo](constraints.md)
- [Inspect existing stripe.connector.yml and main.py and define the connector config format](existing-connector-config.md)

## Required by

- [Source, Pipeline, Sink interfaces](component-interfaces.md)
- [Connector config schema and validation](config-schema.md)

## Hash chain

```
package-layout 0f5c8506d115b8ed85196f213c74ec3781cc94430fe0c0a837f07baf01e190d9 (valid)
  constraints 81cd3e73565e288b0162867cfb9ad6caeff385f7f8240e42a8f686c2721fc3f9 (valid)
  existing-connector-config 97b37fe67fe6578639e2e992deb979a522c3ee449c0d3645802dbeb75fc601a6 (valid)
    scope-boundaries 6d91e069c41a3eff5c6cedfbffd23277944510d9ba4e08413914814644920444 (valid)
      outcome-and-users b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da (valid)
```

## Decisions from the interview

- Q: For "Package layout and CLI entrypoint": should the CLI live in a new src/connector_cli package, exposed as a console script named 'connector-cli' registered in pyproject.toml, and built with stdlib argparse (no new dependency) rather than click or typer? Since scaffold generation is out of v1, should the old root main.py be removed or left untouched for now?
  A: Use src/connector_cli with a cli module and a 'connector-cli' console script, using argparse. Remove main.py, since its scaffold behavior is out of v1 scope. Record the framework choice in docs/adr/0002-cli-framework.md.
