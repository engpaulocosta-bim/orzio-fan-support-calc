# Phase 01: Concepts and Data Model

## Goal

Create a stable engineering data model before adding more calculations.

The current application already contains some structural inputs, but the calculation model needs clearer separation between geometry, loads, sections, supports, analysis results and verification results.

## Problem

The existing implementation mixes early concept logic with future engineering features.

Examples:

* section orientation fields exist but do not affect calculation;
* serviceability is shown in the UI but deflection is not calculated;
* structural type selection exists but visual cards are missing;
* old sidebar labels are still hardcoded in Portuguese;
* the simplified model does not yet represent a true global frame.

## Required Concepts

The data model must explicitly represent:

* project;
* structure;
* node;
* member;
* support;
* release;
* material;
* section;
* section orientation;
* load case;
* load combination;
* load surface;
* point load;
* line load;
* distributed load;
* solver result;
* member check result;
* connection check result;
* report state.

## Units

All units must be explicit.

Recommended internal units:

* length: m;
* force: kN;
* moment: kNm;
* stress: MPa;
* area: cm² or m², but converted consistently before calculation;
* inertia: cm⁴ or m⁴, but converted consistently before calculation;
* mass: kg;
* distributed area load: kN/m²;
* distributed line load: kN/m.

The UI can display user friendly units, but calculation functions must receive normalized units.

## Coordinate System

The model must distinguish:

* global X;
* global Y;
* global Z;
* member local x;
* member local y;
* member local z.

The local member x axis follows the member direction.

The local y and z axes must be derived from the selected section orientation.

## Section Orientation

Section orientation must affect section properties.

For steel profiles, the calculation must use the correct bending axis.

Required behavior:

* orientation 0 degrees uses the default section axes;
* orientation 90 degrees swaps strong and weak bending axes where applicable;
* W_y and W_z must be selected according to actual local bending direction;
* I_y and I_z must follow the same logic;
* the UI must show which axis is being checked.

This is a required correction because fields currently exist but do not affect calculation.

## Calculation State

Every result must expose its state.

Allowed states:

* verified;
* simplified;
* not_verified;
* not_applicable;
* requires_engineer_review.

Examples:

* serviceability toggle enabled but no deflection solver available: not_verified;
* member axial check implemented: verified;
* connection not implemented: not_verified;
* simplified beam approximation: simplified.

## Deliverables

This phase must deliver:

* updated TypeScript interfaces or equivalent model definitions;
* normalized unit helpers;
* section orientation helpers;
* calculation state enum;
* tests for section orientation behavior;
* i18n keys for engineering states;
* documentation for all assumptions.

## Implementation Status

Phase 01 is partially implemented in the current codebase.

Implemented in this phase:

* explicit Phase 01 engineering data model for project, structure, materials, sections, nodes, members, supports, releases, load cases, load combinations, load surfaces, manual loads, solver placeholders, member-check placeholders, connection-check placeholders and report state;
* explicit engineering result states: verified, simplified, not_verified, not_applicable, requires_engineer_review and failed;
* section orientation helpers for 0 degrees and 90 degrees;
* active orientation-based selection of local I_y, I_z, W_y and W_z in the current member verification path;
* explicit serviceability not_verified state when deflection results are unavailable;
* explicit connection-check not_verified state for the Phase 01 engineering layer;
* UI/PDF/JSON exposure of the new engineering state summary;
* tests for orientation, serviceability state, connection placeholder state and tramex terminology separation.

Remaining after Phase 01:

* explicit frame nodes, members, supports and releases are still placeholders for the future global frame solver;
* arbitrary custom section rotation beyond 0 degrees and 90 degrees is not supported yet;
* load surface distribution remains outside this phase;
* connection verification remains outside this phase even if legacy simplified outputs exist.

## Acceptance Criteria

Phase 01 is complete when:

* no calculation uses ambiguous units;
* section orientation is represented in the model;
* section orientation helper tests exist;
* serviceability can no longer be visually confused with verified status;
* calculation states are visible to UI and PDF layers;
* old terminology that confuses tramex and base plate is removed from the data model.
