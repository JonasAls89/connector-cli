# 0003. Configuration-driven connector runtime

- Status: accepted
- Date: 2026-11-07
- Implementation: not yet implemented

## Context

The [glossary](../../GLOSSARY.md) defines source/pipeline/sink composition.
The packaged [CLI](../../src/connector_cli/cli.py) validates definitions;
its [model](../../src/connector_cli/config.py) and
[sample](../../stripe.connector.yml) describe Stripe, local output, and
JSONL/CSV. Separately, [main.py](../../main.py) generates HTTP clients from
a different manifest. These are not one supported execution model today.

Standardize REST connector creation through reusable modules, rather than
generalizing one API client afterward. Prioritize manual technical operators.
This ADR records a future contract, not existing runtime behavior.

Two contrasting sources will demonstrate generality:
[Stripe customers](https://docs.stripe.com/api/customers/list), with API-key
authentication and cursor pagination, and the public
[Bronnoysund Enhetsregisteret API](https://data.brreg.no/enhetsregisteret/api/dokumentasjon/en/index.html),
with unauthenticated access and numbered pagination.
The latter's paged queries have a 10,000-result cap and separate bulk-download
routes; paginated extraction must not imply a complete register snapshot.
Public API access, data licensing, and software licensing are distinct.

## Decision

### Product and authoring

Build a common execution engine for connector definitions, not a generator of
standalone clients. Retain YAML and the source/pipeline/sink structure, with an
explicitly versioned definition schema and a generic REST source type rather
than API-name-specific branches.

Configure ordinary REST behavior without Python. Developers may explicitly
register adapters in the Python package. Keep interfaces replaceable, but
exclude arbitrary import paths in definitions, external plugin discovery,
and configuration that becomes a programming language.

The future schema migration must update the validator and sample together.
Do not promise compatibility with the generator's manifest. Treat `main.py`
as a separate prototype; this documentation decision does not remove it.

### Module interfaces

- **Source:** acquire and yield decoded object records. Own HTTP requests,
  authentication, response-envelope extraction, and pagination.
- **Pipeline:** adapt each record and serialize output into chunks. Own field
  operations and output representation.
- **Sink:** consume serialized chunks and deliver them. Do not interpret
  record fields or choose the format.
- **Runtime:** coordinate execution and resource cleanup. Exceptions
  terminate execution rather than becoming successful results.

Process records incrementally rather than buffering a full extraction.
Initially, each input record produces one output record. Reject scalar or
array-valued records; arrays inside object records are allowed.

### REST source and extraction

Initially support GET requests with configured URLs and query parameters,
a nested path to the response's record array, and explicit pagination
strategies: none, page-number, cursor, or next-link. Stripe and Enhetsregisteret
must use the same REST adapter with different definitions.

Acquire records matching the configured endpoint/query until pagination ends
or an explicit record limit is reached. A limit counts acquired records, not
pages; the initial pipeline preserves that count. Do not promise snapshot
consistency, unrestricted full-dataset access, or incremental synchronization.
Detect non-advancing pagination. If an endpoint cap prevents the requested
extraction, fail explicitly rather than reporting truncated output as complete.

Support no authentication, bearer tokens, and HTTP Basic. Reference credentials
through environment variables rather than storing them in definitions.
Missing referenced credentials must fail before requests begin. Do not expose
authentication credentials in diagnostics or previews. Refuse unsafe next-link
targets rather than forwarding credentials to another origin.

### Pipeline and representation

Apply field selection and renaming, followed by optional object flattening.
Nested field paths address object fields. Missing selected fields become null.
Flattened keys use dots; output-name collisions fail rather than overwrite.
Keep arrays intact: do not explode them into additional records.
Do not support joins, cross-record aggregation, or embedded scripts initially.

Default to JSONL, which preserves nested values. CSV requires explicitly
declared columns and a stable output schema, not columns inferred from the
first record. Object or array values in CSV require explicit JSON-cell encoding;
otherwise fail. Apply normal CSV quoting to encoded text, never implicit Python
string representations.

### Delivery and failures

The initial sink writes local files. Stream into a temporary file and publish
the destination only after the run succeeds. An existing destination requires
explicit overwrite permission. Failed runs must leave existing destinations
unchanged and must not publish partial files as successful output.

Stop with a nonzero exit on acquisition, transformation, or delivery failure;
do not skip bad records. Retry only transient read failures with bounded
retries, honoring `Retry-After`. Do not retry invalid credentials or invalid
configuration. A successful exit means the requested extraction, including
any intentional record limit, was delivered.

### CLI behavior

- `validate`: check definitions offline, without contacting APIs or requiring
  referenced secrets to be present.
- `run`: acquire, adapt, and deliver according to the definition.
- `preview`: perform a live read of a bounded sample, apply the pipeline, and
  display adapted records without writing to the configured sink.

Preview defaults to 10 acquired records and fetches only the pages needed for
that sample. It is not a dry run and must not imply that no API requests occur.
Authentication credentials must never appear in preview output.

### Acceptance and implementation scope

Test through the module interfaces with controlled HTTP responses and temporary
files. Prove both reference definitions use one REST adapter. Cover both
pagination styles, nested response extraction,
record limits, transformation and CSV edge cases, bounded retries, credential
handling, pagination safety, and failed-run publication.
Normal tests require neither credentials nor live APIs; live smoke checks
are optional and explicit.

Exclude schedulers, a service or UI, database or remote sinks, REST-serving
endpoints, POST-based searches, GraphQL, bulk-download ingestion, incremental
state, OAuth acquisition/refresh, and external plugin discovery initially.

Exact schema keys, Python signatures, and numeric retry/timeout settings will
be decided in implementation work items, not inferred from this ADR.
Implement in dependency-ordered, reviewable changes within the
[guardrails](../GUARDRAILS.md), not one oversized PR.

## Consequences

A shared REST implementation avoids duplicating transport and pagination per
API. Configuration-first authoring trades adapter simplicity for explicit
extraction and pagination settings; Python handles exceptional behavior.

We reject standalone client generation as the product foundation, a dedicated
Python adapter for every ordinary API, and an unrestricted configuration
language. Those alternatives respectively fragment execution, burden
connector authors, or turn definitions into programs.

Stable interfaces and versioned definitions cost more upfront but enable
interchangeable, testable connectors. Atomic publication prevents misleading
partial success; failed work must be repeated without resumable extraction.
JSONL is flexible; CSV requires explicit representation choices.
Enhetsregisteret proves paginated queries, not full-register ingestion.
