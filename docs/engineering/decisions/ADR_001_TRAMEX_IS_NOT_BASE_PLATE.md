# ADR 001: Tramex Is Not Base Plate

## Status

Accepted

## Context

During the structural calculator development, platform related terminology was mixed with base plate terminology.

This creates an engineering problem.

A tramex or grating platform is not a base plate.

The two concepts belong to different parts of the structural model.

## Decision

The application must treat tramex as a load surface.

The application must treat base plate as a connection or fixation component.

These concepts must remain separate in:

* data model;
* UI;
* calculation logic;
* PDF;
* i18n labels;
* tests;
* documentation.

## Definitions

### Tramex

Tramex is a grating or platform surface.

In the structural calculator, it may contribute:

* self weight;
* imposed platform load;
* maintenance load;
* equipment support load;
* distributed area load.

Its main calculation role is load generation and load distribution.

### Base Plate

Base plate is a steel plate at a support or column connection.

In the structural calculator, it may contribute to:

* reaction transfer;
* bearing pressure;
* anchor tension;
* anchor shear;
* plate bending;
* weld or bolt connection behavior.

Its main calculation role is connection verification.

## Consequences

The load surface module must not contain base plate checks.

The connection module must not contain tramex load distribution logic.

The PDF must not report tramex as base plate.

The UI must not use base plate labels for platform or grating inputs.

## Correct Modeling

Correct approach:

* tramex area load is defined in kN/m²;
* tramex load is distributed to supporting members;
* global frame solver calculates reactions and member forces;
* support reactions are later used for base plate and anchor checks.

## Incorrect Modeling

Incorrect approach:

* using base plate terminology for tramex;
* treating grating load as connection verification;
* showing base plate as verified because tramex load exists;
* mixing platform area with support fixation dimensions.

## Required Changes

The codebase must be reviewed for terms related to:

* base plate;
* plate;
* platform;
* tramex;
* grating;
* load surface;
* connection;
* fixation.

Any incorrect naming must be corrected.

## Acceptance Criteria

This ADR is respected when:

* tramex appears only as load surface or platform load concept;
* base plate appears only as connection or fixation concept;
* PDF terminology is correct;
* UI terminology is correct;
* tests reflect the separation;
* no calculation function mixes both responsibilities.