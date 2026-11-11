# Runtime and extension contracts

The [CLI](../src/connector_cli/cli.py) and
[runtime](../src/connector_cli/runtime.py) implement the initial scope of
[ADR 0003](adr/0003-configuration-driven-runtime.md). That immutable ADR records
the decision-time implementation status; this document describes current code.
See the [definition reference](CONFIGURATION.md) for exact schema fields.

## Commands

```sh
uv run connector-cli validate stripe.connector.yml
uv run connector-cli preview enhetsregisteret.connector.yml --limit 5
uv run connector-cli run enhetsregisteret.connector.yml --overwrite
```

- `validate FILE`: offline structure, value, and registered-name checks. Does
  not instantiate adapters, resolve environment secrets, or contact the source.
- `run FILE [--overwrite]`: acquire, adapt, serialize, and deliver, then print
  a delivered-record count. An intentional root record limit counts as success.
- `preview FILE [--limit N]`: a live source read through the configured pipeline,
  defaulting to at most 10 records. A smaller definition limit still applies.
  Emits the configured JSONL/CSV representation to stdout, with no count mixed
  into the data. It validates but never constructs or writes the configured sink.

Success is exit 0. Definition and execution errors print safe diagnostics to
stderr and return 1; argparse usage errors return 2.
Source authentication values, including Basic's encoded credential, are redacted
from diagnostics and previews. The pipeline applies preview redaction before
JSON/CSV encoding, including nested values and field/header names, so quoting
cannot bypass it. Redaction-induced name collisions fail explicitly.
Normal delivered data is not redacted or silently altered.

Preview is not a dry run: it makes real GET requests. A failed preview can have
already printed sample records, but returns nonzero. Neither preview nor run
promises a consistent snapshot while a remote dataset changes.

## Publication and cleanup

The [local sink](../src/connector_cli/sink.py) consumes serialized text chunks
into an owner-only temporary file in the destination directory. It flushes and
syncs that file before publication. With overwrite permission it uses atomic
replacement; otherwise it atomically links the completed file into place,
refusing even a destination created concurrently. The filesystem must support
the selected operation; unsupported publication fails explicitly.

Failures in acquisition, transformation, serialization, or publication stop the
run; bad records are never skipped. Before publication, an existing destination
remains unchanged and a new destination remains absent. Temporary files are
removed on failure and success; cleanup failures are reported, even if output
was already published. There are no resumable checkpoints or partial-success
destinations. Parent directories are not implicitly created.

The runtime closes the source generator on success, exceptions, and early
sampling termination; the REST source owns and closes its HTTP client.
Records are processed incrementally, buffering a response page and serialized
record/row rather than the whole extraction. Pagination loop detection retains
request identities and page fingerprints, not all acquired records.

## Python adapters

The [interfaces](../src/connector_cli/interfaces.py) define:

- `SourceAdapter.secrets`: authentication values that must not appear in
  diagnostics or previews. `records(limit)` yields object records through a
  generator and releases acquisition resources when closed.
- `PipelineAdapter.transform(record)`: returns one adapted record without
  mutating the input. `serialize(records, *, redact=None)` yields text chunks,
  applying any supplied text redactor before encoding values and labels.
- `SinkAdapter.write(chunks, *, overwrite)`: exhausts the chunks or raises;
  success means delivery is complete, not merely started.
- `ExecutionError`: explicit acquisition/transformation/delivery failures.
  Adapters must not include response bodies or credentials in error messages.

`default_registry()` explicitly registers `rest`, `records`, and `local`
factories. The registry exposes `sources`, `pipelines`, and `sinks` mappings
from definition type names to factories accepting their respective parsed
configuration dataclasses. Add in-package adapters to those mappings; pass a
custom registry to `run`, `preview`, or CLI `main` for embedded use or tests.
There is no arbitrary import-path loading or third-party plugin discovery.

New adapters must obey the same failure, cleanup, limit, redaction, and delivery
contracts. Adding a different configuration shape also requires explicit
parser validation; registration does not introduce arbitrary YAML options.
Custom transformation pipelines can inherit the built-in
[RecordPipeline](../src/connector_cli/pipeline.py) serializer to preserve
representation and redaction behavior.

## Verification

[Runtime tests](../tests/test_runtime.py) execute both reference definitions
through one REST adapter, exercise registered replacements, and cover CLI output
and failed-run preservation.
[REST tests](../tests/test_source.py) cover pagination, limits, retries, safe
navigation, authentication, and malformed responses.
[Pipeline tests](../tests/test_pipeline.py) cover projections, collisions,
JSONL/CSV, and preview redaction.
[Sink tests](../tests/test_sink.py) cover publication races and cleanup failures.

The [test fixtures](../tests/conftest.py) block accidental live HTTP requests.
Normal tests require no credentials or external services. Live smoke checks
are optional, explicit operator actions, not part of the test suite.
The [installation test](../tests/test_installation.py) invokes the installed
entry point from outside the repository without `PYTHONPATH`, so source-path
overrides cannot mask packaging or import failures.
