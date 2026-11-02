<!-- automagic:node reference-source 6b2fb43eca172e89b54269b557679bd60c3f3289333a17afd14c1a3661fe23cf -->
# Reference source implementation (Stripe, live HTTP via urllib)

Planning topic `reference-source`, hash `6b2fb43eca172e89b54269b557679bd60c3f3289333a17afd14c1a3661fe23cf`. Goal: I want to build a connector cli that standardizes how to connect to a source in components: source, pipeline, sink. Source should connect to data sources, the pipeline should adapt the schema and file format to the target, and the sink should dump/stream data to a storage container/database or allow for previewing locally if developing on a local machine.
Work item: `wi-03`

## Agreed scope

Implement one reference source, Stripe (suggested by stripe.connector.yml), to prove the source abstraction. The Stripe source makes real HTTP calls to the live Stripe API in v1 using only the stdlib urllib, so no new dependency is added. Timeout and retries are taken from the source config. The token is read from the environment variable named by the 'token_env' field in the config; secrets are never committed. The HTTP call sits behind a small transport function so it can be replaced. Tests replace that transport with a stub and never touch the network. Live behavior is verified manually by a developer using their own key. Pagination is hand-written on top of urllib.

## Boundaries

- Estimated change: about 120 lines (budget 400 per work item).
- Expected files: `src/connector_cli/sources/stripe.py`, `tests/test_stripe_source.py`
- `automagic review` flags changes outside these files; guardrail, CI and config files need to be listed here to be changed.

## Depends on

- [Source, Pipeline, Sink interfaces](component-interfaces.md)
- [Inspect existing stripe.connector.yml and main.py and define the connector config format](existing-connector-config.md)

## Required by

- [CLI commands: validate, run](cli-commands.md)

## Hash chain

```
reference-source 6b2fb43eca172e89b54269b557679bd60c3f3289333a17afd14c1a3661fe23cf (valid)
  component-interfaces 6286149a30e87f4f0d1454fc839522ee754904531c825c5962cf5a5bd94cfb11 (valid)
    package-layout 0f5c8506d115b8ed85196f213c74ec3781cc94430fe0c0a837f07baf01e190d9 (valid)
      constraints 81cd3e73565e288b0162867cfb9ad6caeff385f7f8240e42a8f686c2721fc3f9 (valid)
      existing-connector-config 97b37fe67fe6578639e2e992deb979a522c3ee449c0d3645802dbeb75fc601a6 (valid)
        scope-boundaries 6d91e069c41a3eff5c6cedfbffd23277944510d9ba4e08413914814644920444 (valid)
          outcome-and-users b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da (valid)
  existing-connector-config 97b37fe67fe6578639e2e992deb979a522c3ee449c0d3645802dbeb75fc601a6 (valid)
    scope-boundaries 6d91e069c41a3eff5c6cedfbffd23277944510d9ba4e08413914814644920444 (valid)
      outcome-and-users b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da (valid)
```

## Decisions from the interview

- Q: For "Reference source implementation": should the Stripe source make real HTTP calls to the live Stripe API in v1, using the stdlib urllib so no new dependency is added, with the token read from the env var named in the file? And should tests use only a stubbed transport and never touch the network?
  A: Yes. Use stdlib urllib with timeout and retries taken from the source config, read the token from the 'token_env' variable, and keep the HTTP call behind a small transport function that tests replace with a stub.
