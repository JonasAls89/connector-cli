# Connector definitions: schema v1

The [parser](../src/connector_cli/config.py) validates YAML structure and values.
The [registry](../src/connector_cli/runtime.py) checks adapter names. Unknown
keys, duplicate YAML mapping keys, and unsafe YAML tags are rejected.
`validate` performs both checks offline without resolving secrets.

Use the working [Stripe](../stripe.connector.yml) and
[Enhetsregisteret](../enhetsregisteret.connector.yml) definitions as references.
Both select `source.type: rest` and `sink.type: local`.

## Root

- `schema_version`: required integer, exactly `1`.
- `source`, `sink`: required mappings. `pipeline` is optional.
- `limit`: optional positive integer counting acquired records, not pages.
  Without it, extract until pagination ends. A limit is a maximum, not a
  guarantee that the source contains that many records.
- `name`, `display_name`, `version`: optional non-empty metadata strings.
  Metadata `version` is not `schema_version`.

## REST source

The [REST adapter](../src/connector_cli/source.py) supports GET requests.

| Field | Contract |
| --- | --- |
| `type` | Required registered name; built-in is `rest`. |
| `url` | Required absolute HTTP(S) URL; no userinfo, query, or fragment. |
| `records_path` | Dot-separated path to an array of object records. Default `""` selects a root array. |
| `query` | Mapping of names to strings, finite numbers, or booleans. |
| `headers` | Non-sensitive, printable ASCII HTTP headers. Authorization, proxy authorization, Cookie, and Host are reserved. |
| `timeout_seconds` | Connect/read/write/pool timeout, default 15, integer 1-3600. |
| `retries` | Additional attempts for transient failures, default 3, integer 0-10. |
| `max_retry_delay_seconds` | Maximum wait per retry, default 60, integer 1-3600. |
| `auth` | Authentication mapping below; defaults to `type: none`. |
| `pagination` | Pagination mapping below; defaults to `type: none`. |

Field paths traverse object keys only: no array indexing, expressions, or
escaping of dots in key names. Missing selected pipeline fields become null;
a missing source record array is an error. Each record must be an object;
arrays and nested objects inside a record are allowed.

### Authentication

- `type: none`: no other auth fields.
- `type: bearer`: require `token_env`.
- `type: basic`: require `username_env` and `password_env`.

These fields name environment variables, never literal credentials.
Missing or empty referenced variables fail before requests or output creation.
Bearer tokens must be printable ASCII without spaces; Basic usernames cannot
contain a colon. Authenticated sources require HTTPS. OAuth acquisition and
refresh, custom header credentials, and inline query credentials are not
supported; `query` and `headers` must contain only non-sensitive configuration.

### Pagination

| `type` | Configuration and termination |
| --- | --- |
| `none` | One response, no continuation fields. |
| `page` | Require `param`; `start` defaults to 0 and may be 0 or 1. Increment the parameter after each page. Optional `total_pages_path` identifies a nonnegative page count; otherwise continue until an empty array. |
| `cursor` | Require `param`, `cursor_path`, and `has_more_path`. Read the next cursor from the last record; `has_more_path` must identify a boolean in the response. Stop when false. |
| `next_link` | Require `next_path` in the response. Missing or null means completion; otherwise resolve the link against the current request URL. |

For `page` and `cursor`, the engine owns `param`; do not also set it in `query`.
A next link supplies its own query: initial filters are not added again.
Only same-origin links (scheme, host, port) without userinfo or fragments are
accepted. HTTP redirects are never followed, even on the same origin.
The HTTP client does not inherit proxy configuration from environment variables.

All paginated strategies accept optional positive `max_records` for an endpoint
result cap. If more results are needed beyond the cap, extraction fails rather
than publishing truncated output. Reaching an intentional record limit succeeds.
Enhetsregisteret's definition declares its 10,000-result cap and page-count path.
That example does not implement full-register bulk downloads.

Repeated request identities and repeated non-empty record pages fail explicitly.
This conservative protection also rejects APIs that return identical whole pages.
An empty page claiming further pages, malformed continuation metadata, and
invalid JSON fail rather than being treated as normal completion.

### Retries

Retry GET timeouts, network errors, remote protocol failures, and HTTP
408/429/500/502/503/504. Other request failures and other HTTP statuses fail
immediately, including invalid credentials and redirects.
Successful record responses must have status 200.

Without `Retry-After`, waits are 1, 2, 4, ... seconds, capped by
`max_retry_delay_seconds`. Integer seconds and HTTP-date `Retry-After` values
are honored. Invalid headers or waits exceeding the configured maximum fail
explicitly rather than sleeping indefinitely or retrying too soon.

## Record pipeline

The [pipeline](../src/connector_cli/pipeline.py) defaults to `type: records`
and `format: jsonl`. Each acquired record produces exactly one adapted record.

```yaml
pipeline:
  select: [id, profile.name, tags]
  rename:
    profile.name: name
  flatten: false
  format: csv
  csv:
    columns: [id, name, tags]
    json_cells: true
```

- Omit `select` to keep all top-level fields. Otherwise each selected path
  becomes a literal output field name; missing paths produce null.
  `select: []` deliberately produces empty objects.
- `rename` maps selected field labels (or top-level names without `select`)
  to literal output names, not nested object paths. A missing rename source
  without selection fails; with selection, rename keys must be selected paths.
- `flatten: true` runs after select/rename, joining nested object keys with
  dots. Arrays and empty objects remain intact.
- Duplicate selections and colliding output names fail rather than overwrite.
  No filtering, joins, casts, aggregation, scripts, or array expansion.

JSONL preserves nesting, emits one JSON object per line, and rejects non-finite
numbers. CSV requires non-empty, unique, explicitly ordered `csv.columns`.
Column names refer to literal adapted output fields. Extra fields are excluded;
missing/null columns become empty cells. Booleans are `true`/`false`.
Objects and arrays require `csv.json_cells: true` (default false) and become JSON
text with ordinary CSV quoting. No columns are inferred from the first record.

## Local sink

Require `type: local` and non-empty `path`. Paths are relative to the process
working directory, not the definition file. Parent directories must exist.
Overwrite permission comes only from `run --overwrite`.
See [publication and failure semantics](RUNTIME.md).

## Migration from the scaffold

Add `schema_version: 1`. Replace `source.type: stripe`, `resource`, and `api`
with `type: rest`, a complete `url`, and explicit extraction/pagination fields.
Move timeout/retry settings directly under `source`.
Move the old `sink.limit` to root `limit` and specify `sink.path`.
The scaffold's unimplemented `pipeline.cast` field is not supported.
The separate [generator prototype](../main.py) manifest is not a runtime schema
and has no compatibility alias.
