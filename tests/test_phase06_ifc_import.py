from pydantic import ValidationError as PydanticValidationError

from conftest import pdf_text
from sfsc.engineering import CalculationResultState
from sfsc.engines.ifc_import import build_import_review
from sfsc.engines.selector import run_full_calculation
from sfsc.enums import Country, FanType, SupportType
from sfsc.models import FanSupportInput, FanUnit, ImportedModelPayload
from sfsc.reports.export_json import export_report_dict
from sfsc.reports.memorial_pdf import generate_pdf


def _fan_input(**updates) -> FanSupportInput:
    data = {
        "project_name": "Phase 06",
        "support_tag": "FSU-PH06",
        "prepared_by": "Eng. Phase 06",
        "fan_units": [
            FanUnit(
                tag="FAN-1",
                fan_type=FanType.CENTRIFUGAL,
                weight_kg=120.0,
                operating_weight_kg=130.0,
                footprint_length_mm=800.0,
                footprint_width_mm=700.0,
                centre_of_gravity_height_mm=250.0,
            )
        ],
        "support_type": SupportType.HANGER,
        "country": Country.PORTUGAL,
        "seismic_zone": "1.3",
        "installation_height_mm": 600.0,
        "span_mm": 1400.0,
    }
    data.update(updates)
    return FanSupportInput(**data)


def _clean_payload() -> ImportedModelPayload:
    return ImportedModelPayload.model_validate(
        {
            "source": {
                "source_type": "ifc_extracted",
                "file_name": "fan_support.ifc",
                "source_application": "Revit",
            },
            "elements": [
                {
                    "id": "B1",
                    "classification": "beam",
                    "is_structural": True,
                    "start": {"x_m": 0.0, "y_m": 0.0, "z_m": 0.0},
                    "end": {"x_m": 1.4, "y_m": 0.0, "z_m": 0.0},
                    "section_name": "HEB200",
                    "material_name": "S355",
                    "orientation_deg": 0.0,
                    "start_support_condition": "fixed",
                }
            ],
        }
    )


def _invalid_payload() -> ImportedModelPayload:
    return ImportedModelPayload.model_validate(
        {
            "source": {
                "source_type": "ifc_extracted",
                "file_name": "bad_support.ifc",
            },
            "elements": [
                {
                    "id": "B0",
                    "classification": "beam",
                    "is_structural": True,
                    "start": {"x_m": 0.0, "y_m": 0.0, "z_m": 0.0},
                    "end": {"x_m": 0.0, "y_m": 0.0, "z_m": 0.0},
                    "section_name": "X999",
                    "material_name": "UNKNOWN",
                    "orientation_deg": 17.0,
                },
                {
                    "id": "G1",
                    "classification": "tramex",
                    "is_structural": False,
                },
            ],
        }
    )


def test_phase06_import_requires_explicit_confirmation():
    payload = _clean_payload()

    try:
        _fan_input(imported_model=payload)
    except PydanticValidationError:
        pass
    else:
        raise AssertionError("Imported geometry must not be accepted without confirmation.")


def test_phase06_import_review_rejects_invalid_geometry_and_non_structural_items():
    review = build_import_review(
        _invalid_payload(),
        confirmed=True,
        confirmed_by="Eng. Phase 06",
        confirmation_notes="Reviewed.",
    )

    assert review.accepted_members_count == 0
    assert review.rejected_elements_count == 2
    assert any(item.code == "W-IFC-002" for item in review.warnings)
    assert any(member.rejection_reason == "non_structural_element" for member in review.members)
    assert review.requires_engineer_review is True


def test_phase06_confirmed_import_is_visible_in_engineering_state_json_and_pdf():
    ctx = run_full_calculation(
        _fan_input(
            imported_model=_clean_payload(),
            imported_model_confirmed=True,
            imported_model_confirmation_notes="Imported beam and support reviewed by engineer.",
        )
    )

    assert ctx.import_review is not None
    assert ctx.import_review.confirmed is True
    assert ctx.engineering_report_state.state_for("import_review").state == (
        CalculationResultState.VERIFIED
    )

    payload = export_report_dict(ctx)
    assert payload["import_review"] is not None
    assert payload["import_review"]["source"]["file_name"] == "fan_support.ifc"

    pdf_bytes = generate_pdf(ctx)
    text = pdf_text(pdf_bytes).decode("latin1", errors="ignore")
    assert "fan_support.ifc" in text
    assert "BIM/IFC" in text


def test_phase06_confirmed_but_invalid_import_stays_requires_engineer_review():
    ctx = run_full_calculation(
        _fan_input(
            imported_model=_invalid_payload(),
            imported_model_confirmed=True,
            imported_model_confirmation_notes="Reviewed with unresolved BIM issues.",
        )
    )

    assert ctx.import_review is not None
    assert ctx.engineering_report_state.state_for("import_review").state == (
        CalculationResultState.REQUIRES_ENGINEER_REVIEW
    )
    assert any(item.code == "W-IFC-002" for item in ctx.import_review.warnings)
