# SFSC JSON Export Schema

Schema version: `1.0`

The JSON export is a canonical, integration-oriented envelope around a complete
`ReportContext`. It is generated locally only; Fase 5 does not upload data or
call external services.

## Top-Level Envelope

Required keys:

- `schema_version`: string. Current value: `1.0`.
- `calc_id`: UUID string generated per export/API call.
- `created_at`: ISO 8601 UTC timestamp.
- `project_id`: project identifier, currently `ReportContext.project_name`.
- `support_id`: support identifier, currently `ReportContext.support_tag`.
- `software_version`: SFSC package version.
- `dataset_provenance`: software/data hashes and modification dates.
- `input`: serialized `FanSupportInput`.
- `result`: serialized `FanSupportResult`.
- `assessment`: serialized user-facing assessment summary.
- `warnings`: list of structured warnings.
- `citations`: list of normative citations.
- `assumptions`: list of expanded assumption records from `assumptions.yaml`.
- `limitations`: list of calculation limitations.

## Quantities

Budget quantities are exposed at:

```text
result.quantities
```

Fields:

- `estimate_note`: states that quantities are for budgeting and not a cut list.
- `structural_steel_length_m`: estimated primary member length.
- `structural_steel_mass_kg`: primary section mass from catalog kg/m.
- `plate_mass_kg`: base plate mass, when applicable.
- `total_steel_mass_kg`: structural steel plus plate mass.
- `anchor_count`: number of anchors or rods.
- `anchor_diameter_mm`: anchor or rod diameter.
- `anchor_embedment_or_length_mm`: embedment depth for concrete anchors, rod length for hangers.
- `anchor_type`: `concrete` or `rod`.
- `weld_length_mm`: estimated weld bead length.
- `weld_throat_mm`: governing throat used in the estimate.
- `line_items`: machine-readable detail lines.

Quantities are preliminary budgeting quantities. They are not fabrication cut
lists and must not be used as procurement quantities without engineering and
fabrication review.

## API Response

`sfsc.api.run_calculation(payload)` returns a dictionary.

Success:

```json
{
  "ok": true,
  "report": {
    "schema_version": "1.0",
    "calc_id": "uuid",
    "created_at": "timestamp",
    "project_id": "Project",
    "support_id": "FSU-001"
  }
}
```

Validation or domain error:

```json
{
  "ok": false,
  "errors": [
    {
      "field": "fan_units.0.weight_kg",
      "code": "greater_than",
      "message": "Input should be greater than 0"
    }
  ]
}
```
