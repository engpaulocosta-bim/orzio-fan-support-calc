# Phase 05: Connections and Fixations

## Status

Implemented in part.

Current status after this phase increment:

* explicit base plate and anchor layout inputs now exist for the Phase 05 path;
* supported global-frame cases now build connection checks from solver support reactions;
* connection checks now distinguish verified, failed and not_verified states based on explicit input availability;
* UI and PDF now expose Phase 05 connection check rows with governing support reaction and missing-input reporting;
* tramex remains separated from base plate terminology and does not activate connection verification.

Current limitation:

* Phase 05 connection verification currently runs only for supported solver cases;
* unsupported support types still remain not_verified at the engineering connection state layer;
* the legacy preliminary base plate, anchor and internal metal-connection outputs still exist alongside the explicit Phase 05 verification path and must not be confused with solver-based verified connection checks.

## Goal

Add connection and fixation checks as a separate engineering module.

This phase must not be mixed with load surface behavior.

## Critical Terminology

Tramex is not base plate.

A tramex or grating platform is a load surface.

A base plate is a steel plate used to transfer column or support reactions to concrete, anchors or another supporting element.

This distinction is mandatory.

## Scope

Connection checks may include:

* base plate bearing;
* anchor tension;
* anchor shear;
* weld checks;
* bolt checks;
* local plate bending;
* support reaction transfer;
* connection status reporting.

## Current State

Connection verification is not implemented.

Any UI or PDF section related to connections must show not_verified until actual checks exist.

## Inputs

Connection module requires:

* support reaction;
* axial force;
* shear force;
* bending moment;
* base plate dimensions;
* plate thickness;
* anchor layout;
* anchor diameter;
* concrete strength;
* steel grade;
* weld size;
* bolt grade;
* edge distances.

## Base Plate Model

Base plate checks should be introduced gradually.

First version may support:

* axial compression dominant base;
* simple shear transfer;
* simple anchor tension from overturning moment;
* simplified bearing pressure check.

Complex cases must be marked as requires_engineer_review.

## Anchors

Anchor checks must not be invented without input data.

Required behavior:

* if anchor data is missing, status is not_verified;
* if concrete data is missing, status is not_verified;
* if moment exists and anchor layout is missing, status is not_verified;
* PDF must expose missing input.

## Welds and Bolts

Weld and bolt checks should be separate from base plate checks.

Do not assume welded or bolted connection without user input.

## UI Requirements

UI should show:

* connection type;
* required inputs;
* current verification state;
* missing inputs;
* governing reaction;
* connection utilization where available.

## PDF Requirements

PDF must show:

* support reactions;
* connection assumptions;
* base plate inputs;
* anchor inputs;
* weld or bolt inputs;
* verified checks;
* not verified checks;
* engineer review warnings.

## Deliverables

This phase must deliver:

* connection data model;
* base plate input form;
* anchor layout input form;
* simplified base plate check;
* connection result model;
* PDF connection section;
* tests for missing data state;
* tests for simple base plate check.

## Acceptance Criteria

Phase 05 is complete when:

* tramex and base plate are fully separated in UI, data model and PDF;
* connection checks use solver support reactions;
* missing inputs produce not_verified state;
* simple base plate checks have tests;
* PDF does not imply connection safety without verification.
