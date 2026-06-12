# Phase 02: Load Surface and Manual Model

## Goal

Implement a correct manual structural model for small support frames, including tramex or grating surfaces as load surfaces.

This phase must make load definition clear before the global frame solver is implemented.

## Problem

The application previously mixed platform related concepts with base plate terminology.

This is technically incorrect.

A tramex or grating platform is a load surface. It distributes vertical loads to supporting members.

A base plate is a connection element at a column or support fixation point.

These two concepts must remain separate.

## Load Surface Definition

A load surface must represent:

* geometry;
* supported area;
* load direction;
* load magnitude;
* load source;
* distribution method;
* target members;
* load case.

Examples of load sources:

* tramex self weight;
* equipment load;
* maintenance load;
* imposed load;
* manual engineering load;
* piping load;
* duct load.

## Default Load Case Strategy

At minimum, support:

* G: permanent loads;
* Q: imposed or variable loads;
* EQ: equipment loads, if treated separately;
* MANUAL: user defined loads.

The application must not hide which load case was used.

## Tramex Load

Tramex must be modeled as an area load.

Required behavior:

* user defines platform area or dimensions;
* user defines or confirms area load in kN/m²;
* application distributes load to supporting beams;
* resulting line loads are shown to the user;
* PDF reports original area load and resulting distributed line loads.

## Manual Load Model

Manual model must allow:

* point loads;
* line loads;
* area loads;
* self weight toggle;
* equipment load input;
* load case assignment.

The user must be able to understand where every load came from.

## Load Distribution

Initial acceptable methods:

* one way distribution to selected beams;
* tributary width distribution;
* manual member assignment.

Avoid pretending to perform advanced slab or grillage behavior at this phase.

## UI Requirements

The UI should include:

* structural type select;
* future visual cards for structural type selection;
* clear load source labels;
* tramex load surface section;
* manual load entry section;
* warning when load distribution is simplified.

Visual cards were not implemented yet, but the data model should allow them later.

## PDF Requirements

PDF must show:

* input area loads;
* equivalent line loads;
* load cases;
* combination assumptions;
* simplifications;
* items not verified.

## Deliverables

This phase must deliver:

* LoadSurface model;
* ManualLoad model;
* load distribution helpers;
* tramex load surface UI;
* tests for area to line load conversion;
* PDF section for load surfaces;
* i18n keys for all new labels.

## Acceptance Criteria

Phase 02 is complete when:

* tramex is no longer referenced as base plate;
* load surfaces generate traceable line loads;
* manual loads can be assigned to members;
* PDF exposes the load path;
* tests confirm area load distribution;
* unsupported distribution methods show requires_engineer_review or simplified state.

## Progress 2026-06-12

Implemented in the current codebase:

* explicit Phase 02 load surface and manual load models in the engineering data layer;
* explicit load cases `G`, `Q`, `EQ` and `MANUAL` in the simplified load path;
* simplified one-way / tributary-width distribution helpers with traceable resulting line loads;
* `requires_engineer_review` state when manual or surface distribution lacks explicit targets;
* UI inputs for tramex/load surface properties and manual loads;
* JSON/PDF engineering output carrying load surface, line-load and manual-load trace data;
* tests for area-to-line conversion, manual-load review state and terminology separation.

Still intentionally out of scope for this phase:

* no global frame solver;
* no advanced slab/grillage distribution;
* no serviceability deflection verification;
* no connection verification module;
* no Robot benchmark implementation.
