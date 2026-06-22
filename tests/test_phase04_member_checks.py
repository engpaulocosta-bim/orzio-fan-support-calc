from sfsc.catalogs.steel_section_catalog import get_section
from sfsc.engineering import CalculationResultState
from sfsc.engines.section_verifier import verify_section
from sfsc.engines.selector import run_full_calculation
from sfsc.enums import (
    CantileverSubtype,
    Country,
    FanType,
    OperationMode,
    SectionFamily,
    SteelGrade,
    StructuralCode,
    SupportType,
)
from sfsc.models import CalculationOptions, FanSupportInput, FanUnit, LoadCombination


def _cantilever_input(**updates) -> FanSupportInput:
    data = {
        "project_name": "Phase 04",
        "support_tag": "FSU-PH04",
        "prepared_by": "Eng. Phase 04",
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
        "support_type": SupportType.CANTILEVER_1,
        "cantilever_subtype": CantileverSubtype.PURE,
        "country": Country.PORTUGAL,
        "seismic_zone": "1.2",
        "steel_grade": SteelGrade.S355,
        "installation_height_mm": 1000.0,
        "span_mm": 2000.0,
        "eccentricity_mm": 0.0,
    }
    data.update(updates)
    return FanSupportInput(**data)


def test_phase04_supported_global_frame_member_checks_use_solver_forces():
    ctx = run_full_calculation(_cantilever_input())

    assert ctx.fan_support_result.member_check_rows
    assert ctx.engineering_report_state.state_for("member_checks").state == (
        CalculationResultState.VERIFIED
    )
    row = ctx.fan_support_result.member_check_rows[0]
    assert row["member_id"] == "member-beam"
    assert row["governing_combination"] == "ULS_fundamental"
    assert ctx.engineering_model.member_checks[0].load_combination_id == "ULS_fundamental"


def test_phase04_compression_buckling_is_only_checked_for_compression():
    section = get_section(SectionFamily.HEB, "HEB200")
    tension = verify_section(
        section,
        LoadCombination(name="ULS_tension", N_kN=50.0),
        StructuralCode.EC3_EN1993,
        SteelGrade.S355,
        2500.0,
        2500.0,
    )
    compression = verify_section(
        section,
        LoadCombination(name="ULS_compression", N_kN=-50.0),
        StructuralCode.EC3_EN1993,
        SteelGrade.S355,
        2500.0,
        2500.0,
    )

    assert "axial_tension" in tension.utilization_by_check
    assert "buckling_z" not in tension.utilization_by_check
    assert "axial_compression" in compression.utilization_by_check
    assert "buckling_z" in compression.utilization_by_check


def test_phase04_bracketed_member_checks_keep_member_specific_results():
    ctx = run_full_calculation(_cantilever_input(cantilever_subtype=CantileverSubtype.BRACKETED))

    row_ids = {row["member_id"] for row in ctx.fan_support_result.member_check_rows}
    assert row_ids == {"member-beam", "member-diagonal"}
    assert (
        "member-diagonal.buckling_z"
        in ctx.fan_support_result.section_verification.utilization_by_check
    )


def test_phase04_serviceability_and_connections_remain_not_verified():
    ctx = run_full_calculation(
        _cantilever_input(calculation_options=CalculationOptions(include_serviceability=True))
    )

    assert ctx.engineering_report_state.state_for("serviceability").state == (
        CalculationResultState.NOT_VERIFIED
    )
    assert ctx.engineering_report_state.state_for("connection_checks").state == (
        CalculationResultState.NOT_VERIFIED
    )


def test_phase04_failed_member_checks_are_not_reported_as_verified():
    ctx = run_full_calculation(
        _cantilever_input(
            operation_mode=OperationMode.VERIFY,
            received_section_family=SectionFamily.IPE,
            received_section_tag="IPE80",
            span_mm=6000.0,
            installation_height_mm=1500.0,
        )
    )

    assert ctx.engineering_report_state.state_for("member_checks").state == (
        CalculationResultState.FAILED
    )
    assert any(
        check.status == CalculationResultState.FAILED
        for check in ctx.engineering_model.member_checks
    )
