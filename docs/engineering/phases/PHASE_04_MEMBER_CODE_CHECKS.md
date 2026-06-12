# Phase 04: Member Code Checks

## Status

Implemented in part.

Current status after this phase increment:

* supported global-frame cases now derive member checks from solver member end forces;
* implemented checks include axial tension, axial compression, shear, bending about local y, simple axial plus bending interaction, compression buckling and lateral torsional buckling for frame members;
* section orientation now propagates into the solver-based member-check path;
* UI and PDF now expose member-level governing check, governing combination, governing axis and utilization;
* serviceability remains not_verified;
* connection checks remain not_verified.

Current limitation:

* solver-based member checks currently apply only to supported Phase 03 global-frame cases;
* other support types still fall back to the simplified legacy member model;
* automatic section preselection still starts from the simplified envelope before the final supported solver-based verification pass.

## Goal

Implement transparent member verification checks for steel members.

The first target is a pragmatic Eurocode based workflow for small steel support frames.

## Scope

This phase checks members, not connections.

Member checks may include:

* axial tension;
* axial compression;
* shear;
* bending about local y;
* bending about local z;
* combined axial force and bending;
* buckling;
* lateral torsional buckling where applicable.

## Inputs

Member checks require:

* material grade;
* yield strength;
* partial safety factors;
* section properties;
* member length;
* effective buckling length;
* member forces from solver;
* section class or simplified assumption;
* local axis orientation;
* load combination.

## Section Orientation

The check must use the correct local axis.

Required behavior:

* bending around local y uses corresponding section modulus;
* bending around local z uses corresponding section modulus;
* rotated sections must swap or transform relevant section properties;
* UI must show which axis governs;
* PDF must show governing axis.

This corrects the current limitation where orientation fields exist but do not yet affect calculation.

## Utilization Ratio

Each check must return a utilization ratio.

Example states:

* utilization <= 1.00: pass;
* utilization > 1.00: fail;
* missing data: not_verified;
* unsupported case: requires_engineer_review.

The application must not hide failed checks.

## Simplified Eurocode Strategy

The first implementation may use simplified Eurocode based checks, provided that:

* assumptions are visible;
* limitations are documented;
* advanced cases are marked as requires_engineer_review;
* Robot benchmark remains the reference for validation.

## Required Checks

Minimum first implementation:

* axial resistance;
* bending resistance about y;
* bending resistance about z;
* shear resistance;
* simple combined axial plus bending interaction;
* compression buckling check with user defined or default effective length factor.

## Later Checks

Later additions:

* section classification;
* lateral torsional buckling;
* interaction formulas by member type;
* national annex parameters;
* stainless steel or aluminum;
* advanced connection interaction.

## UI Requirements

UI must show:

* governing check;
* utilization percentage;
* member status;
* governing load combination;
* governing axis;
* warnings;
* missing assumptions.

## PDF Requirements

PDF must show:

* member list;
* section;
* material;
* axial force;
* shear force;
* bending moment;
* governing check;
* utilization ratio;
* pass or fail state;
* assumptions.

## Deliverables

This phase must deliver:

* member check engine;
* Eurocode parameter model;
* utilization ratio model;
* tests for axial, bending, shear and combined checks;
* UI result table;
* PDF member check table;
* i18n labels.

## Acceptance Criteria

Phase 04 is complete when:

* member checks use solver forces;
* section orientation affects bending checks;
* governing utilization is visible;
* not implemented checks are not shown as passed;
* tests cover pass and fail cases;
* PDF reports verified, failed and not verified states honestly.
