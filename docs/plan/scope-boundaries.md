<!-- automagic:node scope-boundaries 6d91e069c41a3eff5c6cedfbffd23277944510d9ba4e08413914814644920444 -->
# Scope boundaries for first iteration

Planning topic `scope-boundaries`, hash `6d91e069c41a3eff5c6cedfbffd23277944510d9ba4e08413914814644920444`. Goal: I want to build a connector cli that standardizes how to connect to a source in components: source, pipeline, sink. Source should connect to data sources, the pipeline should adapt the schema and file format to the target, and the sink should dump/stream data to a storage container/database or allow for previewing locally if developing on a local machine.
Work item: `wi-01`

## Agreed scope

Settled. (1) v1 uses only Stripe as its source (based on the existing stripe.connector.yml). (2) The design is generalized so the source/pipeline/sink abstractions and the connector config format can be reused for other data sources later, rather than being Stripe-specific. (3) v1 ships only the local preview sink. The sink interface and the config 'sink' section are defined so that a storage or database sink can be added later without changing the connector file format. Tradeoff accepted: the goal's 'dump/stream to a storage container or database' is not demonstrated in v1, so interface flaws may surface late. (4) Out of scope for v1: scheduling, orchestration, secret stores, and a UI. (5) Secrets are read only from environment variables named in the connector file (for example STRIPE_SECRET_KEY, which stripe.connector.yml already uses); no secret store is built. (6) 'Generalized' means a simple in-code registry that maps the connector file's 'type' to a source implementation. There is no plugin system or installable entry-point mechanism in v1. Tradeoff accepted: unattended deployment needs the deferred features added later, and third parties cannot add sources without changing this repository. Decision to be recorded in docs/adr/0001-scope.md.

## Boundaries

- Estimated change: about 40 lines (budget 400 per work item).
- Expected files: `docs/adr/0001-scope.md`
- `automagic review` flags changes outside these files; guardrail, CI and config files need to be listed here to be changed.

## Depends on

- [Intended outcome and users](outcome-and-users.md)

## Required by

- [Inspect existing stripe.connector.yml and main.py and define the connector config format](existing-connector-config.md)

## Hash chain

```
scope-boundaries 6d91e069c41a3eff5c6cedfbffd23277944510d9ba4e08413914814644920444 (valid)
  outcome-and-users b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da (valid)
```

## Decisions from the interview

- Q: For v1, should we limit scope to: one reference source (Stripe, from stripe.connector.yml), a local preview sink only (no real storage container or database sink), and no scheduling, orchestration, secret stores or UI? Or should anything on that list move in or out, for example a real storage or database sink?
  A: I think I want a more generalized approach. It's fine that v1 only use Stripe, but I wmething that I can generalize on and reuse for other data sources
- Q: For v1, should the "Scope boundaries for first iteration" include only the local preview sink (terminal plus optional local file), or must v1 also ship one real storage-container or database sink to prove that the sink abstraction works beyond local development?
  A: Ship only the local preview sink in v1, but define the sink interface and the config 'sink' section so that a storage or database sink can be added later without changing the connector file format.
- Q: Should scheduling, orchestration, secret stores (beyond reading the token from an environment variable such as STRIPE_SECRET_KEY, which stripe.connector.yml already uses) and a UI all be explicitly out of scope for v1 under "Scope boundaries for first iteration"? And, in the same decision, what should 'generalized' mean for adding a new source later: (a) an in-code registry mapping the connector file's 'type' to an implementation, (b) installable entry-point plugins, or (c) only a clean interface with no registry?
  A: Yes, all four are out of scope for v1; secrets are read only from environment variables named in the connector file; and generalization is (a) a simple in-code registry keyed by 'type', with no plugin system.
