<!-- automagic:node component-interfaces 6286149a30e87f4f0d1454fc839522ee754904531c825c5962cf5a5bd94cfb11 -->
# Source, Pipeline, Sink interfaces

Planning topic `component-interfaces`, hash `6286149a30e87f4f0d1454fc839522ee754904531c825c5962cf5a5bd94cfb11`. Goal: I want to build a connector cli that standardizes how to connect to a source in components: source, pipeline, sink. Source should connect to data sources, the pipeline should adapt the schema and file format to the target, and the sink should dump/stream data to a storage container/database or allow for previewing locally if developing on a local machine.
Work item: `wi-02`

## Agreed scope

Decision: Define minimal Python interfaces (Protocols/ABCs) for the three components, iterator-based so both streaming and batch work.

- Source: connects to a data source and lazily yields records as dicts (an iterator).
- Pipeline: transforms records (record by record), adapts schema, and handles file format adaptation/serialization for the target.
- Sink: consumes records one at a time (write/stream) into a storage container/database, or previews locally.
- A simple in-code registry maps the connector file's 'type' to an implementation.
- The decision is recorded in docs/adr/0003-component-interfaces.md.

Tradeoff accepted: lazy iteration supports streaming and batch sinks and keeps memory low, but sinks needing whole-dataset operations (e.g. Parquet files) must buffer internally, and the interface may need revision when a real storage or database sink is added.

## Boundaries

- Estimated change: about 120 lines (budget 400 per work item).
- Expected files: `src/connector_cli/components.py`, `src/connector_cli/registry.py`, `tests/test_components.py`, `docs/adr/0003-component-interfaces.md`
- `automagic review` flags changes outside these files; guardrail, CI and config files need to be listed here to be changed.

## Depends on

- [Package layout and CLI entrypoint](package-layout.md)

## Required by

- [Local preview sink](local-preview-sink.md)
- [Pipeline schema and file format adaptation](pipeline-adaptation.md)
- [Reference source implementation (Stripe, live HTTP via urllib)](reference-source.md)

## Hash chain

```
component-interfaces 6286149a30e87f4f0d1454fc839522ee754904531c825c5962cf5a5bd94cfb11 (valid)
  package-layout 0f5c8506d115b8ed85196f213c74ec3781cc94430fe0c0a837f07baf01e190d9 (valid)
    constraints 81cd3e73565e288b0162867cfb9ad6caeff385f7f8240e42a8f686c2721fc3f9 (valid)
    existing-connector-config 97b37fe67fe6578639e2e992deb979a522c3ee449c0d3645802dbeb75fc601a6 (valid)
      scope-boundaries 6d91e069c41a3eff5c6cedfbffd23277944510d9ba4e08413914814644920444 (valid)
        outcome-and-users b7ef96cd3aa934e64d65fce0e900349396aa9821a2c49b14cc4eab92e07262da (valid)
```

## Decisions from the interview

- Q: For "Source, Pipeline, Sink interfaces": should the three components be minimal Python interfaces where the source yields records as dicts lazily (an iterator), the pipeline transforms record by record and handles schema and file format adaptation, and the sink consumes records one at a time, with a simple in-code registry mapping the connector file's 'type' to an implementation, and should this decision be recorded in docs/adr/0003-component-interfaces.md?
  A: Yes: iterator-based Source (yields dict records), Pipeline (record transform plus format serialization) and Sink (consumes records), looked up via a simple registry by 'type', recorded in docs/adr/0003-component-interfaces.md.
