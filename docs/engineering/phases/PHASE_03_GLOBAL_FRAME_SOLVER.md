# Phase 03: Global Frame Solver

## Goal

Introduce the first controlled global frame solver into SFSC.

This phase replaces the placeholder solver layer with a real linear elastic structural analysis engine for supported cases.

## Engineering Scope

Phase 03 must stay controlled.

Initial acceptable scope:

* linear elastic analysis;
* small displacement behavior;
* 2D frame model;
* explicit nodes and members;
* explicit support conditions;
* nodal displacement output;
* support reaction output;
* member end-force output;
* instability detection;
* explicit warnings for unsupported support types.

This phase does not yet complete member code checks, connection checks or Robot benchmarking.

## Required Behavior

The solver must:

* assemble stiffness from explicit frame entities;
* solve nodal displacements;
* recover support reactions;
* recover member end forces;
* preserve load-combination traceability;
* expose solver warnings;
* never hide instability or unsupported behavior.

## Initial Support Policy

The first implementation may support only controlled structural types.

For unsupported support types:

* the legacy simplified model may remain active;
* the result must remain clearly marked as simplified;
* the application must not imply that a global frame result exists.

## Output Requirements

Phase 03 outputs must include:

* calculation model type;
* solver status;
* nodes;
* members;
* supports;
* releases;
* nodal displacements;
* support reactions;
* member end forces;
* solver warnings.

## Interaction With Other Phases

Phase 03 must not overclaim later work.

Therefore:

* serviceability remains not_verified until an explicit deflection check exists;
* member checks may remain simplified until Phase 04 uses solver forces directly;
* connection checks remain not_verified until Phase 05;
* Robot comparison remains out of scope until Phase 07.

## Deliverables

This phase must deliver:

* a dedicated global frame solver module;
* controlled structural-model builders for supported support types;
* solver integration into the engineering result layer;
* tests for reactions, displacements and member-force recovery;
* explicit unsupported-scope warnings;
* updated documentation of supported and unsupported cases.

## Progress 2026-06-12 (Phase 03 extension)

Implemented in the current codebase:

* a first 2D linear elastic global frame solver module;
* stiffness-based displacement, reaction and member end-force recovery;
* controlled Phase 03 integration extended to all 7 support types:
  - `cantilever_1` pure and bracketed (2-node cantilever / 3-node bracketed frame)
  - `hanger` (3-node simply-supported beam with mid-span load)
  - `cantilever_2` (3-node symmetric simply-supported beam — same topology as hanger)
  - `cantilever_3` (5-node inverted-U portal frame with two fixed-base columns)
  - `pedestal` (3-node simply-supported beam per skid, mid-span load)
  - `combined` (same topology as pedestal; load factors accounted in combinations)
  - `platform_frame_braced` (bracketed: 3-node cantilever+diagonal; unbraced: 3-node simply-supported)
* engineering-model export of real solver nodes, supports, displacements, reactions and member forces;
* member-check governing combination driven by solver member end forces for all support types;
* instability/unsupported-scope handling through explicit solver warnings;
* buckling length overrides applied to all solver members via their member IDs.

Known limitations remaining:

* governing check label is now member-prefixed (e.g., `member-left.ltb`) — reflects member-level check;
* horizontal seismic force creates axial in horizontal beam members, not bending — this is the correct global-frame result, differing from the simplified model's M_sismo approximation;
* serviceability deflection verification is still not implemented;
* connection checks remain outside Phase 03 scope;
* no Robot benchmark validation yet;
* validation case expected values updated to match global-frame results (see memoria.md files).

## Acceptance Criteria

Phase 03 is complete when:

* at least one controlled structural type is solved by a real stiffness-based model;
* nodal displacements, reactions and member end forces are exported;
* unsupported cases remain clearly simplified;
* solver failures are not presented as verified;
* tests confirm at least one closed-form reaction/displacement case.
