<!-- automagic:node outcome-and-users b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da -->
# Intended outcome and users

Planning topic `outcome-and-users`, hash `b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da`. Goal: I want to build a connector cli that standardizes how to connect to a source in components: source, pipeline, sink. Source should connect to data sources, the pipeline should adapt the schema and file format to the target, and the sink should dump/stream data to a storage container/database or allow for previewing locally if developing on a local machine.
Work item: `wi-01`

## Agreed scope

Outcome (agreed): a Python CLI whose core is to validate, run and preview a connector definition end-to-end through three components: source -> pipeline -> sink. The source connects to data sources, the pipeline adapts schema and file format to the target, and the sink writes or streams data to a storage container or database, or previews it locally when developing on a local machine.

Primary users (agreed): developers defining connectors.

v1 execution context (agreed): developers run the CLI locally to validate and preview. Running unattended in deployment (e.g. scheduled, CI or containers) moving real data into a storage container or database is not a v1 goal, but the same connector file must be designed so it can later be run unattended in deployment. Users beyond developers are not agreed.

Connector definition: the existing stripe.connector.yml is extended with pipeline and sink sections. Its current api/auth/headers sections become the source config (runtime section is not addressed and is left unchanged for now).

Scope: scaffold generation (the current main.py behavior) is left out of v1. Deployment-run behavior is deferred; the answer does not specify how the sink or run design will support it, so no design decision is made here.

Observable success: a connector definition file (e.g. stripe.connector.yml at repo root) can be validated and run end-to-end locally, with output previewable locally.

## Boundaries

- Estimated change: about 30 lines (budget 400 per work item).
- Expected files: `README.md`
- `automagic review` flags changes outside these files; guardrail, CI and config files need to be listed here to be changed.

## Depends on

- Nothing.

## Required by

- [Scope boundaries for first iteration](scope-boundaries.md)

## Hash chain

```
outcome-and-users b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da (valid)
```

## Decisions from the interview

- Q: Should the CLI primarily (a) run a connector definition end-to-end (source -> pipeline -> sink), (b) generate connector scaffolds as the current main.py does, or (c) both? The existing stripe.connector.yml has only api/auth/headers/runtime sections, so how should it relate to the new format: replaced, extended, or kept as the source's config?
  A: (a) run/validate/preview as the core, with stripe.connector.yml extended by pipeline and sink sections and its api/auth/headers becoming the source config; scaffold generation is left out of v1.
- Q: Who will use this CLI, and where will it run? Is it for developers running connectors only on their local machines (validate/preview), or will it also be used to run connectors in deployment (e.g. scheduled or in CI/containers) moving real data into a storage container or database?
  A: Developers defining connectors, running locally for validate/preview in v1, with the same connector file designed so it can later be run unattended in deployment.
