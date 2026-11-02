<!-- automagic:node local-preview-sink 40af0ae757a5d063e6579bbe9447cc7c6cb39fb9f749a7c0451a548f47ff6fe3 -->
# Local preview sink

Planning topic `local-preview-sink`, hash `40af0ae757a5d063e6579bbe9447cc7c6cb39fb9f749a7c0451a548f47ff6fe3`. Goal: I want to build a connector cli that standardizes how to connect to a source in components: source, pipeline, sink. Source should connect to data sources, the pipeline should adapt the schema and file format to the target, and the sink should dump/stream data to a storage container/database or allow for previewing locally if developing on a local machine.
Work item: `wi-02`

## Agreed scope

Sink that previews the first N records in the terminal and optionally writes them to a local file, for local development. Requires no credentials. This is the only sink guaranteed in v1; storage/database sinks are deferred.

Configuration lives in the connector file's `sink` section: `sink: {type: local, limit: 10, path: <optional>}`.
- `limit` sets how many records are previewed (default 10 in the example).
- The CLI `--limit` flag overrides the file's `limit`.
- `path` is optional. The local file is written only when `path` is set.

Terminal preview prints records as JSON lines (one JSON object per line). This keeps the sink dependency-free and consistent with the pipeline's first format. A table view is not part of this node.

## Boundaries

- Estimated change: about 80 lines (budget 400 per work item).
- Expected files: `src/connector_cli/sinks/local.py`, `tests/test_local_sink.py`
- `automagic review` flags changes outside these files; guardrail, CI and config files need to be listed here to be changed.

## Depends on

- [Source, Pipeline, Sink interfaces](component-interfaces.md)

## Required by

- [CLI commands: validate, run](cli-commands.md)

## Hash chain

```
local-preview-sink 40af0ae757a5d063e6579bbe9447cc7c6cb39fb9f749a7c0451a548f47ff6fe3 (valid)
  component-interfaces 6286149a30e87f4f0d1454fc839522ee754904531c825c5962cf5a5bd94cfb11 (valid)
    package-layout 0f5c8506d115b8ed85196f213c74ec3781cc94430fe0c0a837f07baf01e190d9 (valid)
      constraints 81cd3e73565e288b0162867cfb9ad6caeff385f7f8240e42a8f686c2721fc3f9 (valid)
      existing-connector-config 97b37fe67fe6578639e2e992deb979a522c3ee449c0d3645802dbeb75fc601a6 (valid)
        scope-boundaries 6d91e069c41a3eff5c6cedfbffd23277944510d9ba4e08413914814644920444 (valid)
          outcome-and-users b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da (valid)
```

## Decisions from the interview

- Q: For "Local preview sink": should the preview limit and the optional output file be configured in the connector file's 'sink' section (type: local, with optional 'limit' and 'path'), with a CLI '--limit' flag overriding it? What should the terminal preview print: JSON lines, or a table?
  A: Use 'sink: {type: local, limit: 10, path: optional}', with the CLI --limit overriding it, and print records as JSON lines to the terminal. The file is written only when 'path' is set.
