# Release Checklist

## Status

Draft

## Purpose

This checklist defines the minimum requirements before releasing structural calculation changes in SFSC.

No engineering calculation release should be shipped without passing this checklist.

## Release Identification

Release name:

Release date:

Commit or branch:

Responsible developer:

Engineering reviewer:

## 1. General Safety

Required before release:

1. The application builds successfully.
2. Existing tests pass.
3. New calculation logic has tests.
4. No known critical engineering limitation is hidden.
5. UI does not show unchecked items as verified.
6. PDF does not show unchecked items as verified.
7. Errors and warnings are visible to the user.

Status:

Pending

## 2. Data Model

Required before release:

1. Units are explicit.
2. Materials are explicit.
3. Sections are explicit.
4. Member orientation is explicit.
5. Supports are explicit.
6. Load cases are explicit.
7. Load combinations are explicit.
8. Result states are explicit.

Status:

Pending

## 3. Load Model

Required before release:

1. Permanent loads are identified.
2. Variable loads are identified.
3. Equipment loads are identified where applicable.
4. Manual loads are identified.
5. Tramex is modeled as load surface.
6. Base plate is not used as load surface terminology.
7. Area to line load conversion is traceable.
8. Load distribution assumptions are visible.

Status:

Pending

## 4. Solver

Required before release:

1. Solver type is visible.
2. Simplified model is labeled as simplified.
3. Global frame model is labeled as global frame when implemented.
4. Reactions are calculated or marked as not verified.
5. Displacements are calculated or marked as not verified.
6. Member forces are calculated or marked as not verified.
7. Instability warnings are handled.

Status:

Pending

## 5. Member Checks

Required before release:

1. Axial checks are implemented or marked as not verified.
2. Bending checks are implemented or marked as not verified.
3. Shear checks are implemented or marked as not verified.
4. Combined checks are implemented or marked as not verified.
5. Buckling checks are implemented or marked as not verified.
6. Section orientation affects check axes where implemented.
7. Governing utilization is visible.
8. Failed members are clearly shown.

Status:

Pending

## 6. Serviceability

Required before release:

1. Deflection is calculated before serviceability is marked as verified.
2. Deflection limit is explicit.
3. Governing displacement is visible.
4. If deflection is not calculated, serviceability is shown as not verified.

Status:

Pending

## 7. Connections and Fixations

Required before release:

1. Base plate checks are separate from tramex load surface.
2. Anchor checks are separate from member checks.
3. Weld checks are separate from member checks.
4. Bolt checks are separate from member checks.
5. Missing connection data produces not verified status.
6. Connection safety is not implied without calculation.

Status:

Pending

## 8. PDF Report

Required before release:

1. PDF includes input assumptions.
2. PDF includes load summary.
3. PDF includes calculation model type.
4. PDF includes reactions where available.
5. PDF includes displacements where available.
6. PDF includes member checks where available.
7. PDF includes connection checks where available.
8. PDF includes warnings.
9. PDF clearly identifies simplified and not verified items.

Status:

Pending

## 9. i18n

Required before release:

1. No new hardcoded visible labels.
2. Engineering states are translated.
3. PDF labels are translated.
4. UI labels are translated.
5. Legacy hardcoded labels are documented if not yet migrated.

Status:

Pending

## 10. Robot Benchmark

Required before major release:

1. At least one simple benchmark case is compared.
2. Assumptions match Robot as closely as possible.
3. Differences are documented.
4. Tolerance is defined.
5. Benchmark result is stored.

Status:

Pending

## Phase 07 Requirements (PDF and i18n)

The following additional requirements must be met before releasing any version that uses the PDF report for engineering decisions:

1. PDF must not overstate verification — serviceability, connections and advanced checks must never show as verified without actual calculation.
2. Serviceability requires real displacement calculation — not_verified must remain until Phase 03 solver provides nodal displacement outputs.
3. Connection checks require actual connection calculations — not_verified must remain until Phase 05 connection module is extended.
4. Not verified states must remain visible — the PDF must always include the Engineering Warnings section.
5. PDF section headings must use i18n keys — no hardcoded visible labels.
6. Tramex/grating must not appear as base plate in PDF or UI.
7. Base plate must appear only as a connection/fixation term.

Status after Phase 07: Requirements 1–7 are implemented. See PHASE_07_PDF_AND_I18N.md for details.

## Final Release Decision

Release status:

Not ready

Reason:

The structural calculation module is still under staged development. Phase 07 has improved engineering transparency in PDF and i18n, but global frame solver, connection checks and serviceability remain not_verified. Release can proceed only for clearly marked simplified or experimental features unless all required checks above are completed.

## Sign Off

Developer:

Engineering reviewer:

Date:
