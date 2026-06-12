# JSON Schema

## Status

Draft

## Purpose

This document defines the expected JSON structure for the SFSC structural calculation module.

The schema must support the transition from a simplified structural model to a global frame model.

This document is not yet the final machine validated JSON Schema. It is the engineering contract that will guide implementation.

## Schema Principles

1. Every engineering input must have explicit units.
2. Every calculated result must expose its assumptions.
3. Every check must expose its verification state.
4. Geometry, loads, solver results, member checks and connection checks must remain separated.
5. Tramex load surfaces must not be mixed with base plate connection data.
6. Section orientation must affect local axes and section properties.
7. Missing data must produce not_verified or requires_engineer_review, never a false pass.

## Top Level Structure

```json
{
  "schemaVersion": "0.1.0",
  "project": {},
  "structure": {},
  "materials": [],
  "sections": [],
  "nodes": [],
  "members": [],
  "supports": [],
  "releases": [],
  "loadCases": [],
  "loadCombinations": [],
  "loadSurfaces": [],
  "manualLoads": [],
  "analysisSettings": {},
  "solverResults": {},
  "memberChecks": [],
  "connectionChecks": [],
  "importReview": {},
  "reportState": {}
}
```

## Project

```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "createdAt": "ISO_DATE",
  "updatedAt": "ISO_DATE",
  "engineer": "string",
  "location": "string"
}
```

## Structure

```json
{
  "id": "string",
  "type": "small_steel_support_frame",
  "calculationModel": "simplified | global_frame",
  "designCode": "eurocode",
  "status": "draft | benchmark | released"
}
```

## Material

```json
{
  "id": "string",
  "name": "S235 | S275 | S355 | custom",
  "elasticModulus_MPa": 210000,
  "yieldStrength_MPa": 275,
  "density_kg_m3": 7850,
  "poissonRatio": 0.3
}
```

## Section

```json
{
  "id": "string",
  "name": "IPE 200",
  "type": "ipe | hea | heb | rhs | chs | custom",
  "area_m2": 0,
  "iy_m4": 0,
  "iz_m4": 0,
  "wy_m3": 0,
  "wz_m3": 0,
  "torsionConstant_m4": 0,
  "source": "database | user"
}
```

## Node

```json
{
  "id": "string",
  "x_m": 0,
  "y_m": 0,
  "z_m": 0
}
```

## Member

```json
{
  "id": "string",
  "startNodeId": "string",
  "endNodeId": "string",
  "sectionId": "string",
  "materialId": "string",
  "orientation_deg": 0,
  "memberType": "beam | column | brace | strut",
  "calculationRole": "primary | secondary"
}
```

## Support

```json
{
  "id": "string",
  "nodeId": "string",
  "restraints": {
    "ux": true,
    "uy": true,
    "uz": true,
    "rx": false,
    "ry": false,
    "rz": false
  }
}
```

## Load Case

```json
{
  "id": "string",
  "name": "G | Q | EQUIPMENT | MANUAL",
  "type": "permanent | variable | equipment | manual"
}
```

## Load Combination

```json
{
  "id": "string",
  "name": "ULS 1",
  "type": "uls | sls",
  "factors": [
    {
      "loadCaseId": "string",
      "factor": 1.35
    }
  ]
}
```

## Load Surface

```json
{
  "id": "string",
  "name": "Tramex platform",
  "type": "tramex | grating | platform | custom",
  "loadCaseId": "string",
  "area_m2": 0,
  "load_kN_m2": 0,
  "distributionMethod": "one_way | tributary_width | manual",
  "targetMemberIds": [],
  "resultingLineLoads": []
}
```

## Manual Load

```json
{
  "id": "string",
  "type": "point | line | area",
  "loadCaseId": "string",
  "targetId": "string",
  "direction": "global_x | global_y | global_z | local_y | local_z",
  "value": 0,
  "unit": "kN | kN_m | kN_m2"
}
```

## Analysis Settings

```json
{
  "includeSelfWeight": true,
  "solverType": "simplified | global_frame_2d | global_frame_3d",
  "serviceabilityLimit": "L/200 | L/250 | L/300 | custom",
  "serviceabilityCustomLimit": null
}
```

## Solver Results

```json
{
  "status": "verified | simplified | not_verified | failed",
  "reactions": [],
  "displacements": [],
  "memberForces": [],
  "warnings": []
}
```

## Member Check

```json
{
  "memberId": "string",
  "status": "verified | simplified | not_verified | failed | requires_engineer_review",
  "governingCheck": "axial | bending_y | bending_z | shear | combined | buckling",
  "utilization": 0,
  "loadCombinationId": "string",
  "warnings": []
}
```

## Connection Check

```json
{
  "supportId": "string",
  "type": "base_plate | anchor_group | weld | bolt_group",
  "status": "verified | not_verified | failed | requires_engineer_review",
  "utilization": null,
  "warnings": []
}
```

## Import Review

```json
{
  "source": {
    "sourceType": "ifc_extracted | bim_json | other",
    "fileName": "string",
    "sourceApplication": "string"
  },
  "importedElementsCount": 0,
  "acceptedMembersCount": 0,
  "rejectedElementsCount": 0,
  "warnings": [],
  "confirmed": false,
  "confirmationNotes": "string"
}
```

## Report State

```json
{
  "pdfReady": false,
  "engineeringReviewRequired": true,
  "containsSimplifiedResults": true,
  "containsUnverifiedChecks": true,
  "warnings": []
}
```

## Next Step

This document must later be converted into a formal JSON Schema file when the Phase 01 data model is implemented.
