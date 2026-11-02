<!-- automagic:node constraints 81cd3e73565e288b0162867cfb9ad6caeff385f7f8240e42a8f686c2721fc3f9 -->
# Technical constraints from repo

Planning topic `constraints`, hash `81cd3e73565e288b0162867cfb9ad6caeff385f7f8240e42a8f686c2721fc3f9`. Goal: I want to build a connector cli that standardizes how to connect to a source in components: source, pipeline, sink. Source should connect to data sources, the pipeline should adapt the schema and file format to the target, and the sink should dump/stream data to a storage container/database or allow for previewing locally if developing on a local machine.
Work item: `wi-01`

## Agreed scope

Facts from pyproject.toml: Python >=3.13, uv, pyyaml dependency, pytest with coverage fail_under=90, ruff (line-length 100, rules E,F,I,B,UP,S,SIM,RUF), bandit, prek, zizmor. Note: pytest addopts has an unrendered '--cov={{ package_name }}' template placeholder and testpaths=tests with pythonpath=src, but no src/ or tests/ exist yet; the placeholder must be fixed before tests can run. Changes must be ~400 lines per PR; decisions go in docs/adr/.

## Boundaries

- Estimated change: about 10 lines (budget 400 per work item).
- Expected files: `pyproject.toml`, `.pre-commit-config.yaml`
- `automagic review` flags changes outside these files; guardrail, CI and config files need to be listed here to be changed.

## Depends on

- Nothing.

## Required by

- [Package layout and CLI entrypoint](package-layout.md)
- [Quality gates and CI](quality-gates.md)

## Hash chain

```
constraints 81cd3e73565e288b0162867cfb9ad6caeff385f7f8240e42a8f686c2721fc3f9 (valid)
```
