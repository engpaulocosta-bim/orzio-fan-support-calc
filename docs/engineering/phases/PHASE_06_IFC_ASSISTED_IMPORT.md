# Phase 06: IFC Assisted Import

## Status

Implemented in part.

Current status after this phase increment:

* assisted BIM/IFC import now accepts an extracted JSON payload for review;
* imported elements are mapped into candidate nodes, members and explicit support-condition records only when that information exists in the source;
* invalid geometry, unsupported section/material names, unknown orientation and non structural items now produce visible warnings or rejection markers;
* imported geometry now requires explicit user confirmation before it can proceed into a calculation input;
* UI, JSON export and PDF now expose import source, counts, warnings and confirmation state.

Current limitation:

* the current Phase 06 path is an assisted review adapter, not a full IFC parser;
* imported geometry is documented and reviewed, but it does not yet replace the active solver model automatically;
* editable review currently happens at the extracted JSON payload level rather than through a full graphical/member table editor.

## Goal

Add assisted import from BIM or IFC data while keeping engineering control in the hands of the user.

The application must not blindly trust imported geometry.

## Purpose

IFC assisted import should reduce manual typing, not replace engineering review.

Useful imported data may include:

* member geometry;
* section names;
* material names;
* levels;
* member connectivity;
* approximate coordinates;
* object classifications;
* model source metadata.

## Risks

Imported BIM data may contain:

* disconnected elements;
* wrong analytical alignment;
* wrong section names;
* wrong material names;
* duplicated objects;
* non structural objects;
* local coordinate inconsistencies;
* missing support conditions;
* missing releases;
* missing load data.

Therefore, imported data must always pass through a review step.

## Import Workflow

Recommended workflow:

1. User imports IFC or extracted BIM data.
2. Application reads candidate structural elements.
3. Application maps elements to nodes and members.
4. Application detects sections and materials.
5. Application shows warnings.
6. User confirms or corrects model.
7. Only confirmed model is used for calculation.

## Required Mapping

Importer should attempt to map:

* beams to members;
* columns to members;
* braces to members;
* supports to boundary conditions only when explicitly available;
* sections to known steel profiles;
* materials to known grades.

No automatic assumption should be hidden.

## Validation Rules

Importer must detect:

* zero length members;
* duplicate nodes;
* disconnected members;
* unsupported section names;
* missing materials;
* unknown profile orientation;
* non structural elements;
* missing support conditions.

## UI Requirements

UI should show:

* imported elements count;
* accepted members;
* rejected members;
* warnings;
* editable model table;
* confirmation step.

## PDF Requirements

PDF should show:

* model source;
* import date;
* imported file name when available;
* number of imported elements;
* number of accepted structural members;
* warnings;
* user confirmed assumptions.

## Deliverables

This phase must deliver:

* IFC import adapter or input format adapter;
* mapping model;
* validation warnings;
* review UI;
* confirmation workflow;
* tests for invalid imported geometry;
* PDF import summary.

## Acceptance Criteria

Phase 06 is complete when:

* imported geometry is never calculated without confirmation;
* warnings are visible;
* invalid members are rejected or marked;
* support conditions are not guessed silently;
* sections and materials require mapping confirmation;
* PDF exposes import source and assumptions.
