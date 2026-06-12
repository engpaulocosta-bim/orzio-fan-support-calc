# Technical Audit 2026-06

## Status

Draft

## Purpose

This document records the current technical and engineering state of the SFSC structural calculation module as of June 2026.

It must be used as a reference before implementing new structural calculation features.

## Current Engineering State

The current structural model is simplified.

The application currently approximates the system as:

1. Simply supported beam behavior.
2. Axial strut behavior.
3. Simplified load distribution.
4. Limited member verification.
5. No complete global frame stiffness analysis.

This is acceptable for early concept sizing, but not enough for a reliable engineering workflow.

## Known Limitations

### Global structural model

Current limitation:

The application does not yet solve the full frame behavior using nodes, members, supports, releases and global stiffness assembly.

Current status after Phase 03 (extended 2026-06-12):

A controlled 2D linear elastic global frame solver now covers all 7 support types.

Supported cases currently implemented:

1. cantilever_1 pure
2. cantilever_1 bracketed
3. hanger (3-node simply-supported beam with mid-span load)
4. cantilever_2 (3-node simply-supported beam — symmetric double cantilever)
5. cantilever_3 (5-node inverted-U portal frame, two fixed columns)
6. pedestal (3-node simply-supported beam per representative skid)
7. combined (same frame topology as pedestal; load factors in combinations)
8. platform_frame_braced (bracketed: 3-node cantilever+diagonal; unbraced: 3-node simply-supported)

Remaining limitation:

Solver-based member forces are used for member verification. The governing check label
now includes the member ID (e.g., member-left.ltb). Horizontal forces on horizontal beam
members produce axial force rather than bending moment — this is structurally correct and
differs from the simplified model's M_sismo approximation.

Required future correction:

Implement the global frame solver described in Phase 03.

### Section orientation

Current limitation:

Phase 01 now activates the explicit 0 degree and 90 degree orientation cases in the member verification path.

Remaining limitation:

Arbitrary custom rotation is still not supported and must not be treated as globally verified behavior.

Required future correction:

Extend the orientation handling to the future global frame member local-axis model and to any later custom rotation support.

### Serviceability

Current limitation:

The serviceability toggle exists and is tracked, but deflection calculation is not implemented.

Required future correction:

Serviceability must remain not verified until displacement results are calculated by the solver.

### Connections and fixations

Current limitation:

Phase 01 now exposes connection checks as not_verified in the engineering state layer.

Remaining limitation:

Legacy base plate, anchor and steel connection outputs still exist for preliminary workflows, but they must not be interpreted as complete connection verification.

Required future correction:

Connection checks must be implemented as a separate module and must use support reactions from the global frame solver.

Current status after Phase 05:

Supported global-frame cases now expose explicit Phase 05 connection checks based on solver support reactions when the user provides explicit base plate, anchor or steel-fixation input.

Remaining limitation:

If solver reactions are unavailable or explicit connection input is missing, the result must remain not_verified. Unsupported support types still do not produce solver-based connection verification.

### Tramex terminology

Current limitation:

Tramex or grating platform concepts were previously confused with base plate terminology.

Current status after Phase 02:

The engineering model now stores tramex/grating as load surface data and keeps base plate terminology for connection-related items only.

Remaining limitation:

The structural response is still based on simplified tributary-width / one-way distribution, so load surfaces must not be interpreted as a solved global frame slab or grillage model.

Required future correction:

Tramex must be modeled as a load surface. Base plate must be modeled as a connection component.

### Load surface and manual load traceability

Current status after Phase 02:

Load surfaces and manual loads are now explicit in the data model, JSON export and PDF reporting, including resulting simplified line loads.

Remaining limitation:

If a manual or surface load is entered without explicit target members, the result must remain in requires_engineer_review state and must not be promoted to verified.

Required future correction:

Tie manual and surface load targets to the future global frame entities and solver reactions/displacements.

### PDF reporting

Current status after Phase 07:

PDF output now includes dedicated sections for:
- Calculation model type (simplified vs global frame)
- Serviceability status (not_verified when deflection is unavailable)
- Connection verification status (not_verified sub-items when not implemented)
- Engineering warnings section (always visible, listing simplified model, not-verified checks, engineer review required and tramex/grating clarification)

All PDF section headings are now driven by i18n keys.

Remaining limitation:

Some legacy UI sidebar labels outside the Phase 07 engineering flow are still hardcoded in Portuguese. These are classified as low risk.

Required future correction:

Extend PDF to support multilingual generation (currently defaults to PT). Implement deflection and connection calculations before serviceability and connection sections can show verified states.

### Member checks

Current status after Phase 04:

Supported Phase 03 global-frame cases now use solver member end forces for member verification and expose member-level governing utilization, governing combination and governing axis in the UI and PDF.

Remaining limitation:

Automatic section preselection still starts from the simplified envelope before the final supported solver-based verification pass, and unsupported support types still remain on the simplified member-check path.

Required future correction:

Move section sizing and verification fully onto the future broader global-frame solver coverage so all supported typologies use the same force model end-to-end.

### i18n

Current status after Phase 07:

All Phase 07 required i18n keys have been added to EN, PT and ES:
- Engineering result states (verified, simplified, not_verified, not_applicable, requires_engineer_review, failed)
- PDF section headings and cover text
- Serviceability status and warning labels
- Connection status and warning labels
- Simplified model warning labels
- Tramex/grating/platform and base plate terminology labels

Remaining limitation:

Some legacy sidebar labels outside the Phase 07 engineering flow are still hardcoded in Portuguese. These are classified as low risk and can be migrated incrementally.

Required future correction:

Complete migration of all hardcoded visible labels to i18n. Implement multilingual PDF generation.

### IFC assisted import

Current status after Phase 06:

An assisted BIM/IFC review path now exists for extracted JSON payloads, including candidate member/node mapping, warning generation, explicit confirmation, and PDF/JSON traceability.

Remaining limitation:

The current Phase 06 path is not a full IFC parser and does not yet replace the active structural solver model automatically. Imported geometry remains assisted input and must still be reviewed as a separate engineering step.

## Engineering Risk Classification

### High risk

1. Presenting unchecked items as verified.
2. Using wrong section axis due to orientation not affecting calculation.
3. Mixing tramex load surface with base plate connection logic.
4. Reporting serviceability without displacement calculation.
5. Using simplified model results as if they came from a global frame analysis.

### Medium risk

1. Hardcoded labels in legacy UI.
2. Incomplete PDF assumptions.
3. Missing visual cards for structural type selection.
4. Lack of Robot benchmark validation.

### Low risk

1. Cosmetic UI improvements.
2. Layout refinements.
3. Non critical translation cleanup.

## Required Development Order

1. Stabilize concepts and data model.
2. Correct terminology.
3. Implement load surface and manual load model.
4. Implement global frame solver.
5. Implement member checks.
6. Implement connection checks.
7. Create Robot benchmark cases.
8. Finalize PDF and i18n.

## Engineering Rule

The application must use the following states honestly:

1. verified
2. simplified
3. not_verified
4. not_applicable
5. requires_engineer_review
6. failed

No calculation, UI component or PDF section may present a missing check as verified.

## Audit Conclusion

The project is viable, but the next implementation must focus on engineering correctness before adding more UI or advanced features.

The highest priority is to prevent misleading results and to evolve the calculator toward a global frame based model validated against Robot.
