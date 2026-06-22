import pytest

from sfsc.catalogs.steel_section_catalog import get_section
from sfsc.engineering import CalculationResultState
from sfsc.engines.section_verifier import verify_section
from sfsc.engines.selector import run_full_calculation
from sfsc.enums import (
    Country,
    FanType,
    SectionFamily,
    SectionOrientation,
    SteelGrade,
    StructuralCode,
    SupportType,
    WalkingSurfaceType,
)
from sfsc.models import (
    CalculationOptions,
    FanSupportInput,
    FanUnit,
    LoadCombination,
    WalkingSurface,
)
from sfsc.reports.export_json import export_report_dict
from sfsc.section_orientation import get_local_section_axis_properties


def _inp(**updates) -> FanSupportInput:
    data = {
        "project_name": "Phase 01",
        "support_tag": "FSU-PH01",
        "prepared_by": "Eng. Phase 01",
        "fan_units": [
            FanUnit(
                tag="FAN-1",
                fan_type=FanType.CENTRIFUGAL,
                weight_kg=280.0,
                operating_weight_kg=300.0,
                footprint_length_mm=1000.0,
                footprint_width_mm=800.0,
                centre_of_gravity_height_mm=350.0,
            )
        ],
        "support_type": SupportType.PEDESTAL,
        "country": Country.PORTUGAL,
        "seismic_zone": "1.2",
        "installation_height_mm": 700.0,
        "span_mm": 1100.0,
    }
    data.update(updates)
    return FanSupportInput(**data)


def test_section_orientation_zero_keeps_default_axes():
    section = get_section(SectionFamily.HEB, "HEB200")
    props = get_local_section_axis_properties(section, 0.0)

    assert props.local_iy_mm4 == pytest.approx(section.I_y_mm4)
    assert props.local_iz_mm4 == pytest.approx(section.I_z_mm4)
    assert props.local_wy_el_mm3 == pytest.approx(section.W_el_y_mm3)
    assert props.local_wz_el_mm3 == pytest.approx(section.W_el_z_mm3)


def test_section_orientation_ninety_swaps_axes():
    section = get_section(SectionFamily.HEB, "HEB200")
    props = get_local_section_axis_properties(section, 90.0)

    assert props.local_iy_mm4 == pytest.approx(section.I_z_mm4)
    assert props.local_iz_mm4 == pytest.approx(section.I_y_mm4)
    assert props.local_wy_el_mm3 == pytest.approx(section.W_el_z_mm3)
    assert props.local_wz_el_mm3 == pytest.approx(section.W_el_y_mm3)


def test_section_verification_uses_orientation_in_bending_checks():
    section = get_section(SectionFamily.HEB, "HEB200")
    combo = LoadCombination(name="ULS_fundamental", V_z_kN=20.0, M_y_kNm=30.0)

    strong = verify_section(
        section,
        combo,
        StructuralCode.EC3_EN1993,
        SteelGrade.S355,
        1200.0,
        600.0,
        orientation_deg=0.0,
    )
    weak = verify_section(
        section,
        combo,
        StructuralCode.EC3_EN1993,
        SteelGrade.S355,
        1200.0,
        600.0,
        orientation_deg=90.0,
    )

    assert strong.calculation_details["section_orientation_deg"] == pytest.approx(0.0)
    assert weak.calculation_details["section_orientation_deg"] == pytest.approx(90.0)
    assert weak.utilization_by_check["bending_y"] > strong.utilization_by_check["bending_y"]


def test_serviceability_is_not_verified_when_deflection_is_unavailable():
    ctx = run_full_calculation(
        _inp(calculation_options=CalculationOptions(include_serviceability=True))
    )

    serviceability = ctx.engineering_report_state.state_for("serviceability")
    assert serviceability.state == CalculationResultState.NOT_VERIFIED


def test_connection_checks_placeholder_is_not_verified():
    ctx = run_full_calculation(_inp())

    connection_state = ctx.engineering_report_state.state_for("connection_checks")
    assert connection_state.state == CalculationResultState.NOT_VERIFIED
    assert ctx.engineering_model.connection_checks[0].status == CalculationResultState.NOT_VERIFIED


def test_tramex_is_treated_as_load_surface_not_base_plate():
    ctx = run_full_calculation(
        _inp(
            support_type=SupportType.PLATFORM_FRAME_BRACED,
            walking_surface=WalkingSurface(
                surface_type=WalkingSurfaceType.STEEL_GRATING_TRAMEX,
                self_weight_kn_m2=0.45,
            ),
        )
    )

    assert ctx.engineering_model.load_surfaces
    assert ctx.engineering_model.load_surfaces[0].type == "tramex"
    assert ctx.engineering_report_state.state_for("load_surfaces").state == (
        CalculationResultState.SIMPLIFIED
    )
    assert ctx.engineering_report_state.state_for("connection_checks").state == (
        CalculationResultState.NOT_VERIFIED
    )


def test_json_export_includes_phase01_engineering_state():
    ctx = run_full_calculation(_inp(section_orientation=SectionOrientation.WEAK_AXIS_VERTICAL))
    payload = export_report_dict(ctx, calc_id="00000000-0000-4000-8000-000000000003")

    assert payload["engineering_model"]["sections"][0]["orientation_deg"] == pytest.approx(90.0)
    assert payload["engineering_report_state"]["states"]
    states = {item["id"]: item["state"] for item in payload["engineering_report_state"]["states"]}
    assert states["connection_checks"] == CalculationResultState.NOT_VERIFIED.value
