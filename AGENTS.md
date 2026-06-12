# AGENTS.md

## Project Context

This repository contains the structural calculation module for the SFSC application.

The current structural model is intentionally simplified. It approximates the system as simply supported beams with axial struts. This is acceptable only for early concept validation, but it is not sufficient for a reliable engineering workflow.

The next development target is to evolve the application into a global frame based structural calculator, with transparent assumptions, traceable results, Robot benchmark validation, Eurocode based member checks and clear PDF reporting.

## Engineering Priorities

Work must follow this order:

1. Preserve the current working application.
2. Clarify concepts and data model before adding calculations.
3. Separate load surface, member model, solver, code checks, connections and reporting.
4. Do not treat tramex or grating load surfaces as base plates.
5. Do not claim serviceability verification until deformation checks are actually implemented.
6. Do not claim connection verification until base plates, anchors, welds or bolts are actually checked.
7. Keep engineering assumptions explicit in UI and PDF.
8. Keep Robot benchmark cases as the reference for numerical validation.

## Current Known Limitations

The following limitations are known and must not be hidden:

* The current model is simplified.
* Beam behavior is currently approximated.
* Struts are mostly axial.
* Section orientation fields exist but do not yet affect calculations.
* W_y and W_z swapping by orientation is not yet implemented.
* The serviceability toggle exists but deflection verification is not yet implemented.
* Some legacy sidebar labels are still hardcoded in Portuguese.
* Visual cards for structural type selection were not implemented yet.
* The PDF should clearly distinguish verified, simplified and not verified items.

## Coding Rules

* Do not rewrite large areas without need.
* Prefer small, reviewable commits.
* Each phase must be implemented independently.
* Add tests before or together with calculation changes.
* Avoid hidden defaults in engineering calculations.
* Every default must be documented.
* Every calculated result must expose input assumptions.
* Keep i18n keys organized.
* Do not hardcode UI labels in Portuguese, English or Spanish.
* Do not mix UI state with engineering calculation logic.
* Do not use graphical labels as calculation identifiers.

## Engineering Rules

* All units must be explicit.
* Internal calculation units must be consistent.
* Loads must keep their origin: self weight, imposed load, equipment, tramex, manual load, wind, accidental or other.
* Load combinations must be traceable.
* Support conditions must be explicit.
* Member releases must be explicit.
* Section orientation must affect local axes and section properties.
* Global frame results must include reactions, displacements and internal forces.
* Member checks must show utilization ratios.
* Failed, passed and not checked states must be clearly separated.

## Definition of Done

A task is done only when:

* The calculation logic is implemented.
* Existing tests pass.
* New tests cover the added behavior.
* UI labels use i18n where applicable.
* PDF output reflects the calculation state honestly.
* The result can be compared against a Robot benchmark when applicable.
* Any limitation is documented in the relevant phase file or ADR.