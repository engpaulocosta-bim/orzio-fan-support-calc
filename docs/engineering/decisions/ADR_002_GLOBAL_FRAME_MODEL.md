# ADR 002: Global Frame Model

## Status

Accepted

## Context

The current SFSC calculation model is simplified.

It approximates the structure using beam behavior and axial struts. This is useful for early sizing, but it does not represent the complete behavior of a structural frame.

The application needs to evolve toward a global frame model to improve engineering reliability and allow comparison with Robot.

## Decision

SFSC will evolve toward a global frame based structural model.

The global frame model will use:

* nodes;
* members;
* supports;
* releases;
* materials;
* sections;
* member orientation;
* load cases;
* load combinations;
* global stiffness analysis;
* member force recovery;
* displacement calculation.

## Reasoning

A global frame model is required because small steel support structures are affected by:

* member stiffness interaction;
* support conditions;
* frame action;
* member orientation;
* axial and bending interaction;
* displacement behavior;
* load path;
* connection reactions.

These effects cannot be reliably captured by isolated simply supported beam assumptions.

## Initial Scope

The first implementation should remain controlled.

Recommended initial scope:

* linear elastic analysis;
* small displacement behavior;
* 2D frame model for controlled cases;
* explicit warning when behavior is outside supported scope;
* future extension to 3D frame model.

## Solver Outputs

The solver must provide:

* nodal displacements;
* support reactions;
* member end forces;
* axial force;
* shear force;
* bending moment;
* solver warnings;
* instability detection.

## Serviceability

Serviceability verification depends on displacement results.

Before global displacement calculation exists, serviceability must be reported as not verified.

After displacement calculation exists, serviceability may be checked against explicit limits.

## Member Checks

Member checks must use global frame results.

This includes:

* axial force;
* shear force;
* bending moment about local axes;
* governing load combination;
* section orientation.

## Robot Benchmark

Robot will be used as external benchmark.

SFSC does not need to match Robot for unsupported advanced cases.

For supported cases, differences must be documented and kept within agreed tolerances.

## Consequences

The old simplified model may remain temporarily as legacy, but it must be labeled as simplified.

The UI must clearly identify which calculation engine produced the result.

The PDF must not mix simplified and global frame results without explanation.

## Non Goals

The first global frame implementation will not include:

* nonlinear analysis;
* dynamic analysis;
* seismic analysis;
* shell finite elements;
* advanced connection stiffness;
* automatic design optimization;
* full Robot feature parity.

## Acceptance Criteria

This ADR is respected when:

* new calculations are based on nodes and members;
* support reactions come from the global model;
* member checks use global internal forces;
* serviceability uses actual displacement;
* unsupported behavior is marked clearly;
* Robot benchmark cases are used for validation.