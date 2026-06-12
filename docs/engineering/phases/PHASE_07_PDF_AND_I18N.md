# Phase 07: PDF and i18n

## Status

Implemented — 2026-06-12

## Goal

Improve PDF reporting, i18n coverage and engineering transparency so that:

1. The UI and PDF clearly distinguish verified, simplified, not_verified, not_applicable, requires_engineer_review, and failed states.
2. The system never presents a missing or unchecked structural verification as verified.
3. All engineering result states are translated through i18n keys.
4. Tramex, grating and platform terminology is not mixed with base plate terminology.

## What Was Implemented

### i18n (EN / PT / ES)

Added Phase 07 required keys to all three language files:

- `report.section.calculationModel` — PDF section label for calculation model
- `report.section.serviceability` — PDF section label for serviceability status
- `report.section.connectionStatus` — PDF section label for connection verification status
- `report.section.engineeringWarnings` — PDF section label for engineering warnings
- `report.label.serviceabilityStatus` — Label for the serviceability status row
- `report.label.serviceabilityNotVerified` — Warning label when serviceability is not verified
- `report.label.deflectionNotAvailable` — Explanation that deflection is not available
- `report.label.basePlateStatus` — Connection-level base plate status label
- `report.label.anchorStatus` — Anchor check status label
- `report.label.weldStatus` — Weld/bolt check status label
- `report.label.connectionNotVerified` — Warning when connection checks are missing
- `report.label.connectionWarning` — Explanation that connection checks need actual calculation
- `report.label.simplifiedModelWarning` — Warning that simplified model is in use
- `report.label.engineerReviewRequired` — Engineer review required notice
- `report.label.tramexNotBasePlate` — Clarification that tramex is a load surface term
- `warning.serviceability.notVerified` — Serviceability not verified warning
- `warning.connection.notVerified` — Connection checks not verified warning
- `warning.connection.basePlateNotVerified` — Base plate not verified warning
- `warning.connection.anchorNotVerified` — Anchor not verified warning
- `warning.connection.weldNotVerified` — Weld/bolt not verified warning
- `warning.model.simplified` — Simplified model in use warning
- `warning.engineer.reviewRequired` — Engineer review required warning
- `warning.tramex.notBasePlate` — Tramex is not base plate warning
- `sidebar.results.serviceabilityNotVerified` — UI serviceability not verified notice
- `sidebar.results.connectionNotVerified` — UI connection not verified notice
- `sidebar.results.simplifiedModel` — UI simplified model notice
- `pdf.cover.title` — PDF cover title (migrated from hardcoded PT)
- `pdf.cover.subtitle` — PDF cover subtitle (migrated from hardcoded PT)
- `pdf.preliminary.label` — Preliminary document label (migrated from hardcoded PT)
- `pdf.disclaimer` — PDF disclaimer text (migrated from hardcoded PT)
- `pdf.section.*` — All PDF section headings (migrated from hardcoded PT)
- `pdf.footer.warning` — PDF footer warning (migrated from hardcoded EN)

### PDF Generation (memorial_pdf.py)

Added three new Phase 07 sections before section 1 (Identification):

1. **Calculation Model section** — shows model type (simplified or global frame) and solver engine. Warns if simplified model is in use.
2. **Serviceability section** — shows serviceability status (not_verified, not_applicable or verified). When serviceability is enabled but no displacement results exist, shows a visible red warning and the reason.
3. **Connection verification status section** — shows per-component states (base plate, anchors, welds/bolts). When no connection check rows exist, shows a visible red warning.
4. **Engineering warnings section** — always-present section listing: simplified model warning, serviceability not verified warning (if applicable), base plate/anchor/weld not verified warnings (if applicable), engineer review required notice, and tramex is not base plate clarification.

Migrated all hardcoded PDF section headings and cover text from Portuguese/English strings to i18n keys.

Fixed terminology in geometry section: the "Mesa / base plate" row now uses the i18n key `report.label.basePlateStatus` which correctly identifies it as a connection component, not a tramex/grating load surface.

### results_view UI (results_view.py)

- Added `_render_serviceability_warning()` function: shows a UI warning when serviceability is enabled but no displacement results are available.
- `_render_banner()`: now always shows a simplified model warning and connection not verified warning when the engine is simplified or has no connection rows.
- `_render_tabs()`: renamed "Mesa" tab to "Mesa / Chapa" to clarify it refers to connection/fixation (bearing plate), not tramex.

### Engineering State Guards (engineering.py)

Confirmed correct implementation:

- `determine_serviceability_state()`: hardcoded `displacement_results_available=False` in `build_phase01_engineering_model()` ensures serviceability is always `NOT_VERIFIED` or `NOT_APPLICABLE` until deflection is implemented.
- `determine_connection_state()`: returns `NOT_VERIFIED` when checks are requested but no rows exist, and `NOT_APPLICABLE` when checks are not requested.
- No path exists where a missing or uncalculated check is presented as `VERIFIED`.

## What Was Intentionally Not Implemented

- Deflection calculation (Phase 03 future work)
- Global frame solver for all support types (Phase 03 future work)
- Connection checks calculation (Phase 05 future work)
- IFC import integration (Phase 06 future work)
- Visual cards for structural type selection (deferred)
- Full migration of all legacy UI sidebar labels (only Phase 07 relevant labels were migrated)

## Tests Added

File: `tests/test_phase07_pdf_and_i18n.py` — 139 tests

Categories:

1. **i18n key presence** — 114 parametrized tests verifying all Phase 07 i18n keys exist in EN, PT and ES files
2. **Engineering state translation** — all 6 `CalculationResultState` values resolve correctly via `t()` in all 3 languages
3. **Serviceability not_verified** — 5 tests covering all state transitions
4. **Connection not_verified** — 5 tests covering state determination logic and engineering model integration
5. **Tramex is not base plate** — 4 tests verifying terminology separation in i18n
6. **Report state integrity** — 3 tests verifying report never marks missing checks as verified
7. **Warning keys presence** — 4 grouped tests
8. **PDF section labels** — 4 tests
9. **PDF generation smoke tests** — 2 tests verifying PDF generation succeeds and does not overstate serviceability

## Engineering Warnings Visible in PDF

The PDF now always includes an Engineering Warnings section containing:

- Simplified model warning (when not using global frame solver)
- Serviceability not verified warning (when enabled but not calculated)
- Base plate not verified warning (when no connection rows)
- Anchor not verified warning (when no connection rows)
- Weld/bolt not verified warning (when no connection rows)
- Engineer review required notice
- Tramex is not base plate clarification

## i18n Areas Updated

- PDF cover and section headings — fully migrated
- PDF footer warning — migrated from hardcoded English
- Engineering result state labels — confirmed present (pre-existing + confirmed)
- Serviceability status labels — added
- Connection status labels — added
- Warning messages — added
- Tramex/grating/platform/base plate terminology — confirmed correct in all languages

## Known Limitations Remaining

- Serviceability deflection calculation is not implemented. Serviceability remains `not_verified` until Phase 03 global frame solver includes nodal displacement outputs.
- Connection checks are not fully implemented for all support types. Connection remains `not_verified` until Phase 05 implementation is extended.
- Some legacy sidebar labels in PT are still hardcoded (outside the Phase 07 engineering flow). These are documented as low risk in the audit.
- Visual cards for structural type selection are still not implemented.
- The PDF is still generated in Portuguese as the default language. Full multilingual PDF generation is future work.

## Recommended Next Phase

Phase 03 Global Frame Solver — extend solver coverage to all support types so that:

- Serviceability can be computed from nodal displacements
- Connection checks can be based on solver support reactions
- Member checks can use global frame internal forces
- Simplified model state transitions to verified for supported typologies
