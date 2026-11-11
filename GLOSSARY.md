# Connector Data Transfer

The language used to describe acquiring data, adapting its representation,
and delivering it to a destination.

## Language

**Connector definition**:
A configuration describing a source, any transformations, and a destination.
_Avoid_: Connector instance, run

**Run**:
One execution of a connector definition.
_Avoid_: Connector definition

**Preview**:
An inspection of a bounded sample of adapted records without delivering them
to the connector definition's destination.
_Avoid_: Dry run

**Record**:
One data item acquired from a source.
_Avoid_: File, batch

**Record limit**:
The maximum number of records to acquire during an execution.
_Avoid_: Page limit

**Source**:
The component responsible for acquiring records from a data source.
_Avoid_: Connector

**Pipeline**:
The component responsible for adapting records and their output representation.
_Avoid_: Source, sink

**Sink**:
The component responsible for receiving a pipeline's output at a destination.
_Avoid_: Source
