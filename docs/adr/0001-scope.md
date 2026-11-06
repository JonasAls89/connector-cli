# 0001. Scope of the first iteration

- Status: accepted
- Date: 2026-11-02

## Context

The goal is a CLI that standardizes connectors as source, pipeline and sink. The repository only
has [stripe.connector.yml](../../stripe.connector.yml) as a concrete example.

## Decision

- v1 supports only Stripe as a source.
- Source, pipeline and sink are generic abstractions; a simple in-code registry maps the
  connector file's `type` to an implementation. No plugin system or entry points.
- v1 ships only the `local` preview sink. The `sink` section is defined so storage or database
  sinks can be added later without changing the file format.
- Out of scope: scheduling, orchestration, secret stores, a UI, scaffold generation.
- Secrets are read only from environment variables named in the connector file
  (e.g. `STRIPE_SECRET_KEY`).
- Unattended deployment runs are deferred; no design decision is made for them here.

## Consequences

- Third parties cannot add sources without changing this repository.
- The storage/database path is not demonstrated in v1, so sink interface flaws may surface late.
- The `runtime` section of the old connector file is removed.
