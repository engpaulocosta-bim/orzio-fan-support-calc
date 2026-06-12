# SFSC Global Frame Roadmap

## Objective

Evolve the SFSC application from a simplified support calculator into a reliable structural frame calculation workflow.

The final target is not to replace professional software such as Autodesk Robot Structural Analysis, but to create a pragmatic engineering assistant capable of:

* modeling small steel support frames;
* distributing platform and equipment loads;
* solving global frame behavior;
* checking members according to simplified Eurocode based rules;
* documenting assumptions and limitations;
* benchmarking results against Robot;
* generating clear PDF reports.

## Current State

The current model is useful for early sizing and comparison, but it is simplified.

Known current state:

* Structural type selection exists in the form.
* A new type was added to the select with i18n label and description.
* Visual cards for structural type selection are not implemented yet.
* The current mechanical model is simplified as beams plus axial struts.
* Section orientation fields exist in the data model.
* Section orientation does not yet affect the calculation.
* W_y and W_z swapping by orientation is not implemented yet.
* The serviceability toggle exists and is tracked.
* Deflection calculation is not implemented yet.
* PDF output contains new i18n driven sections.
* Some old sidebar labels are still hardcoded in Portuguese.
* Tramex was previously confused with base plate terminology and must be corrected.

## Target Engineering Model

The target model is a global frame model.

Main entities:

* nodes;
* members;
* supports;
* releases;
* sections;
* materials;
* load cases;
* load surfaces;
* load combinations;
* solver results;
* member checks;
* connection checks;
* report results.

The calculation should progress from a controlled manual model to an assisted import model.

## Phase Overview

### Phase 01: Concepts and Data Model

Create the stable engineering vocabulary and data structures.

Main outcome:

* clear structural entities;
* clear units;
* clear local and global axes;
* explicit section orientation;
* explicit calculation states.

### Phase 02: Load Surface and Manual Model

Implement platform and tramex load surfaces correctly.

Main outcome:

* tramex treated as load surface;
* manual load definition;
* load distribution to beams;
* load origin traceability.

### Phase 03: Global Frame Solver

Replace simplified beam plus axial strut approximation with a global frame solver.

Main outcome:

* stiffness based model;
* nodal displacements;
* reactions;
* member internal forces;
* testable numerical cases.

### Phase 04: Member Code Checks

Implement member utilization checks.

Main outcome:

* axial checks;
* bending checks;
* shear checks;
* combined checks;
* buckling checks;
* transparent utilization ratios.

### Phase 05: Connections and Fixations

Add base plate, anchors, bolts and welds as separate checks.

Main outcome:

* base plate no longer confused with tramex;
* connection checks clearly separated from member checks;
* not verified states exposed when checks are missing.

### Phase 06: IFC Assisted Import

Add assisted import from IFC or BIM model data.

Main outcome:

* model extraction support;
* user confirmation before calculation;
* no blind trust in imported geometry.

### Phase 07: Robot Benchmark

Create reference benchmark cases against Autodesk Robot Structural Analysis.

Main outcome:

* consistent validation models;
* documented differences;
* acceptable tolerances;
* benchmark driven confidence.

### Phase 08: PDF and i18n

Finalize reporting and internationalization.

Main outcome:

* clear PDF report;
* multilingual UI and report;
* assumptions visible;
* verified and not verified states clearly separated.

## Important Engineering Decisions

The following decisions are documented separately:

* ADR 001: Tramex is not base plate.
* ADR 002: Global frame model.

## Implementation Strategy

The implementation must be incremental.

Do not attempt to implement all phases at once.

Recommended order:

1. Complete documentation.
2. Stabilize data model.
3. Correct terminology.
4. Implement load surface.
5. Implement global solver.
6. Add member checks.
7. Add connection checks.
8. Validate against Robot.
9. Improve PDF and i18n.

## Non Goals

The first release does not need to include:

* full advanced finite element modeling;
* nonlinear analysis;
* dynamic analysis;
* seismic analysis;
* automatic design optimization;
* full Eurocode national annex coverage;
* full connection design for every connection type;
* automatic Robot file import.

## Engineering Honesty Rule

The application must never present an unchecked item as verified.

Allowed states:

* verified;
* simplified;
* not verified;
* outside scope;
* requires engineer review.

This rule applies to UI, PDF, logs and exported results.