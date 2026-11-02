<!-- automagic:node existing-connector-config 97b37fe67fe6578639e2e992deb979a522c3ee449c0d3645802dbeb75fc601a6 -->
# Inspect existing stripe.connector.yml and main.py and define the connector config format

Planning topic `existing-connector-config`, hash `97b37fe67fe6578639e2e992deb979a522c3ee449c0d3645802dbeb75fc601a6`. Goal: I want to build a connector cli that standardizes how to connect to a source in components: source, pipeline, sink. Source should connect to data sources, the pipeline should adapt the schema and file format to the target, and the sink should dump/stream data to a storage container/database or allow for previewing locally if developing on a local machine.
Work item: `wi-01`

## Agreed scope

Verified by reading both files: stripe.connector.yml has name, display_name, version, api (base_url, timeout_seconds, retries), auth (type, token_env), headers and runtime (language, package_name). main.py is a placeholder that only generates connector.yml, client.py, .env.example, requirements.txt and README from templates, with no run logic.

Decision: the new connector format is a three-section layout.
- Top-level metadata: name, display_name, version (kept as is).
- source: holds the existing api (base_url, timeout_seconds, retries), auth (type, token_env) and headers, plus a 'type: stripe' field and the resource to read.
- pipeline: new section, to be defined in later nodes.
- sink: new section, to be defined in later nodes.
- runtime (language, package_name) is removed from the connector file, because it only served scaffold generation.

Outcome of this node: the documented list of fields the config format must support is name, display_name, version, source (type, resource, api, auth, headers), pipeline and sink. The inner fields of pipeline and sink, and the exact name and shape of the resource field, are not decided here and are left to later nodes.

Tradeoff accepted: this changes the existing file's layout, so anything relying on the old scaffold format or 'runtime' would need to migrate.

## Boundaries

- Estimated change: about 10 lines (budget 400 per work item).
- Expected files: `stripe.connector.yml`, `main.py`
- `automagic review` flags changes outside these files; guardrail, CI and config files need to be listed here to be changed.

## Depends on

- [Scope boundaries for first iteration](scope-boundaries.md)

## Required by

- [Connector config schema and validation](config-schema.md)
- [Package layout and CLI entrypoint](package-layout.md)
- [Reference source implementation (Stripe, live HTTP via urllib)](reference-source.md)

## Hash chain

```
existing-connector-config 97b37fe67fe6578639e2e992deb979a522c3ee449c0d3645802dbeb75fc601a6 (valid)
  scope-boundaries 6d91e069c41a3eff5c6cedfbffd23277944510d9ba4e08413914814644920444 (valid)
    outcome-and-users b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da (valid)
```

## Decisions from the interview

- Q: In "Inspect existing stripe.connector.yml and main.py": I read stripe.connector.yml and main.py. The file has name, display_name, version, api (base_url, timeout_seconds, retries), auth (type, token_env), headers and runtime (language, package_name). main.py only generates connector.yml, client.py, .env.example, requirements.txt and README from templates, with no run logic. Should the new connector format treat name, display_name and version as top-level connector metadata, move api/auth/headers under a 'source' section, and drop the 'runtime' section (it only serves scaffold generation, which is out of v1)? Or should 'runtime' be kept as is?
  A: Keep name, display_name and version top-level; move api/auth/headers under 'source' alongside a 'type: stripe' field plus the resource to read; add 'pipeline' and 'sink' sections; remove 'runtime' from the connector file because it only served scaffold generation.
