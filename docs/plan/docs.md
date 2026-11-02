<!-- automagic:node docs f4794c7c4deaf7cc8789bde9400a84a1f05075f9e39d4b056c6962dfa0b8f035 -->
# Documentation and ADRs

Planning topic `docs`, hash `f4794c7c4deaf7cc8789bde9400a84a1f05075f9e39d4b056c6962dfa0b8f035`. Goal: I want to build a connector cli that standardizes how to connect to a source in components: source, pipeline, sink. Source should connect to data sources, the pipeline should adapt the schema and file format to the target, and the sink should dump/stream data to a storage container/database or allow for previewing locally if developing on a local machine.
Work item: `wi-03`

## Agreed scope

Update README with usage and the connector file format; add ADRs for scope, CLI framework, component interfaces; update docs/CONTEXT.md index. Add GLOSSARY.md (absent) defining source, pipeline, sink, connector only if terms need pinning.

## Boundaries

- Estimated change: about 90 lines (budget 400 per work item).
- Expected files: `README.md`, `docs/CONTEXT.md`, `docs/adr/0001-scope.md`, `docs/adr/0002-cli-framework.md`, `docs/adr/0003-component-interfaces.md`
- `automagic review` flags changes outside these files; guardrail, CI and config files need to be listed here to be changed.

## Depends on

- [CLI commands: validate, run](cli-commands.md)

## Hash chain

```
docs f4794c7c4deaf7cc8789bde9400a84a1f05075f9e39d4b056c6962dfa0b8f035 (valid)
  cli-commands b6779d66b73e818c89933a01634840ececdcddb11e1705adce87ae439669b4db (valid)
    config-schema e11fac9942cce86bbe5855791ce86c866227e747443e873576cdbbb47a0817bb (valid)
      existing-connector-config 97b37fe67fe6578639e2e992deb979a522c3ee449c0d3645802dbeb75fc601a6 (valid)
        scope-boundaries 6d91e069c41a3eff5c6cedfbffd23277944510d9ba4e08413914814644920444 (valid)
          outcome-and-users b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da (valid)
      package-layout 0f5c8506d115b8ed85196f213c74ec3781cc94430fe0c0a837f07baf01e190d9 (valid)
        constraints 81cd3e73565e288b0162867cfb9ad6caeff385f7f8240e42a8f686c2721fc3f9 (valid)
        existing-connector-config 97b37fe67fe6578639e2e992deb979a522c3ee449c0d3645802dbeb75fc601a6 (valid)
          scope-boundaries 6d91e069c41a3eff5c6cedfbffd23277944510d9ba4e08413914814644920444 (valid)
            outcome-and-users b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da (valid)
    local-preview-sink 40af0ae757a5d063e6579bbe9447cc7c6cb39fb9f749a7c0451a548f47ff6fe3 (valid)
      component-interfaces 6286149a30e87f4f0d1454fc839522ee754904531c825c5962cf5a5bd94cfb11 (valid)
        package-layout 0f5c8506d115b8ed85196f213c74ec3781cc94430fe0c0a837f07baf01e190d9 (valid)
          constraints 81cd3e73565e288b0162867cfb9ad6caeff385f7f8240e42a8f686c2721fc3f9 (valid)
          existing-connector-config 97b37fe67fe6578639e2e992deb979a522c3ee449c0d3645802dbeb75fc601a6 (valid)
            scope-boundaries 6d91e069c41a3eff5c6cedfbffd23277944510d9ba4e08413914814644920444 (valid)
              outcome-and-users b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da (valid)
    pipeline-adaptation a788868efb0985365a80146aed657e6825006011b039bc2d1bbee8d6af640ea9 (valid)
      component-interfaces 6286149a30e87f4f0d1454fc839522ee754904531c825c5962cf5a5bd94cfb11 (valid)
        package-layout 0f5c8506d115b8ed85196f213c74ec3781cc94430fe0c0a837f07baf01e190d9 (valid)
          constraints 81cd3e73565e288b0162867cfb9ad6caeff385f7f8240e42a8f686c2721fc3f9 (valid)
          existing-connector-config 97b37fe67fe6578639e2e992deb979a522c3ee449c0d3645802dbeb75fc601a6 (valid)
            scope-boundaries 6d91e069c41a3eff5c6cedfbffd23277944510d9ba4e08413914814644920444 (valid)
              outcome-and-users b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da (valid)
      config-schema e11fac9942cce86bbe5855791ce86c866227e747443e873576cdbbb47a0817bb (valid)
        existing-connector-config 97b37fe67fe6578639e2e992deb979a522c3ee449c0d3645802dbeb75fc601a6 (valid)
          scope-boundaries 6d91e069c41a3eff5c6cedfbffd23277944510d9ba4e08413914814644920444 (valid)
            outcome-and-users b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da (valid)
        package-layout 0f5c8506d115b8ed85196f213c74ec3781cc94430fe0c0a837f07baf01e190d9 (valid)
          constraints 81cd3e73565e288b0162867cfb9ad6caeff385f7f8240e42a8f686c2721fc3f9 (valid)
          existing-connector-config 97b37fe67fe6578639e2e992deb979a522c3ee449c0d3645802dbeb75fc601a6 (valid)
            scope-boundaries 6d91e069c41a3eff5c6cedfbffd23277944510d9ba4e08413914814644920444 (valid)
              outcome-and-users b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da (valid)
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
