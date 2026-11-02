<!-- automagic:node config-schema e11fac9942cce86bbe5855791ce86c866227e747443e873576cdbbb47a0817bb -->
# Connector config schema and validation

Planning topic `config-schema`, hash `e11fac9942cce86bbe5855791ce86c866227e747443e873576cdbbb47a0817bb`. Goal: I want to build a connector cli that standardizes how to connect to a source in components: source, pipeline, sink. Source should connect to data sources, the pipeline should adapt the schema and file format to the target, and the sink should dump/stream data to a storage container/database or allow for previewing locally if developing on a local machine.
Work item: `wi-01`

## Agreed scope

Define a YAML schema with three sections: source, pipeline, sink, derived from the existing stripe.connector.yml. Load with pyyaml (safe_load only, for bandit).

Decisions:
- Top level: `source` (required), `sink` (required), `pipeline` (optional as a whole).
- `source` has exactly these keys:
  - `type` (required): 'stripe'.
  - `resource` (required): a single string naming one Stripe collection (for example 'customers'). One resource per connector file; reading several resources requires several connector files until the format is extended.
  - `api` (optional, keeps the existing fields): `base_url`, `timeout_seconds` (default 15), `retries` (default 3). Defaults follow the current stripe.connector.yml values.
  - `auth` (keeps the existing fields): `type`, `token_env`.
  - `headers`: keeps the existing field from stripe.connector.yml.
  - There is no page-size field in v1; Stripe pagination uses a fixed page size.
- `sink` has exactly these keys:
  - `type` (required): 'local'.
  - `limit` (optional): default 10.
  - `path` (optional).
- `pipeline` section in v1 has four keys, all optional:
  - `select`: list of field names to keep.
  - `rename`: mapping of old field name to new field name.
  - `cast`: mapping of field name to type; allowed types are string, int, float, bool.
  - `format`: `jsonl` or `csv` (stdlib only), defaulting to `jsonl`. Parquet is deferred to a later iteration.
- Pipeline transforms are applied in the order select, rename, cast.
- v1 pipeline has no nested-field paths and no computed fields.
- Validation is strict: unknown keys (including under `source`, `sink` and `pipeline`) and missing required keys are rejected. Each error is clear and names the field path (for example 'source.resource' or 'pipeline.cast'). The CLI exits non-zero on any validation error.
- Because validation is strict, adding fields later (such as page size or new sink types) is a deliberate schema change.

Note: whether `api`, `auth` and `headers` are individually required or optional, and the exact sub-key requirements, follow the existing stripe.connector.yml as read in the existing-connector-config node; the answer did not specify them further.

## Boundaries

- Estimated change: about 140 lines (budget 400 per work item).
- Expected files: `src/connector_cli/config.py`, `tests/test_config.py`
- `automagic review` flags changes outside these files; guardrail, CI and config files need to be listed here to be changed.

## Depends on

- [Inspect existing stripe.connector.yml and main.py and define the connector config format](existing-connector-config.md)
- [Package layout and CLI entrypoint](package-layout.md)

## Required by

- [CLI commands: validate, run](cli-commands.md)
- [Pipeline schema and file format adaptation](pipeline-adaptation.md)

## Hash chain

```
config-schema e11fac9942cce86bbe5855791ce86c866227e747443e873576cdbbb47a0817bb (valid)
  existing-connector-config 97b37fe67fe6578639e2e992deb979a522c3ee449c0d3645802dbeb75fc601a6 (valid)
    scope-boundaries 6d91e069c41a3eff5c6cedfbffd23277944510d9ba4e08413914814644920444 (valid)
      outcome-and-users b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da (valid)
  package-layout 0f5c8506d115b8ed85196f213c74ec3781cc94430fe0c0a837f07baf01e190d9 (valid)
    constraints 81cd3e73565e288b0162867cfb9ad6caeff385f7f8240e42a8f686c2721fc3f9 (valid)
    existing-connector-config 97b37fe67fe6578639e2e992deb979a522c3ee449c0d3645802dbeb75fc601a6 (valid)
      scope-boundaries 6d91e069c41a3eff5c6cedfbffd23277944510d9ba4e08413914814644920444 (valid)
        outcome-and-users b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da (valid)
```

## Decisions from the interview

- Q: For "Connector config schema and validation": how should the Stripe 'resource' be expressed in the source section, and how strict should validation be? Should 'source.resource' be a single string naming one Stripe collection (for example 'customers'), with one resource per connector file, and should unknown keys be rejected with a clear error and non-zero exit?
  A: se 'source.resource' as one string naming a single collection, with one resource per connector file. Reject unknown or missing required keys with a clear error naming the field path, and exit non-zero.
- Q: For "Connector config schema and validation": what should the 'pipeline' section contain in v1? Should it support (a) 'select' (a list of fields to keep), (b) 'rename' (a mapping of old name to new name), (c) 'cast' (a mapping of field to type: string, int, float, bool), and (d) 'format' (jsonl or csv, stdlib only, with Parquet deferred)? Should all of these be optional, with 'format' defaulting to jsonl?
  A: Yes. Support optional 'select', 'rename' and 'cast', plus 'format' of jsonl or csv defaulting to jsonl. Apply them in the order select, rename, cast. Reject unknown keys under strict validation, and defer Parquet.
- Q: For "Connector config schema and validation": the pipeline keys and 'source.resource' are agreed. To finish the schema, should the 'source' section have exactly these keys: type (required, 'stripe'), resource (required), api (base_url, timeout_seconds, retries), auth (type, token_env) and headers? And should the 'sink' section have exactly type (required, 'local'), limit (optional, default 10) and path (optional), with 'pipeline' optional as a whole and 'sink' required?
  A: Yes. 'source' keeps exactly the existing api/auth/headers fields plus type and resource. 'sink' has type, optional limit and optional path. 'pipeline' is optional. 'sink' is required. Defaults for api timeout_seconds (15) and retries (3) follow the current stripe.connector.yml values. There is no page-size field in v1.
