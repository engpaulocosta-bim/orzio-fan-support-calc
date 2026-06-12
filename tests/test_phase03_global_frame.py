import pytest

from sfsc.catalogs.steel_section_catalog import get_section
from sfsc.engineering import CalculationModelType, CalculationResultState
from sfsc.engines.global_frame import run_global_frame_analysis
from sfsc.engines.selector import run_full_calculation
from sfsc.enums import (
    CantileverSubtype,
    Country,
    FanType,
    SectionFamily,
    SteelGrade,
    SupportType,
)
from sfsc.models import FanSupportInput, FanUnit, LoadCombination
from sfsc.section_orientation import get_local_section_axis_properties


def _cantilever_input(**updates) -> FanSupportInput:
    data = {
        "project_name": "Phase 03",
        "support_tag": "FSU-PH03",
        "prepared_by": "Eng. Phase 03",
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


def test_global_frame_solver_matches_simple_cantilever_reaction_and_deflection():
    inp = _cantilever_input()
    section = get_section(SectionFamily.HEB, "HEB200")
    combo = LoadCombination(name="ULS_fundamental", V_z_kN=10.0)

    analysis = run_global_frame_analysis(inp, [combo], section, orientation_deg=0.0)

    assert analysis.supported is True
    assert analysis.solved is True
    reaction = next(item for item in analysis.reactions if item["combination"] == combo.name)
    member = next(item for item in analysis.member_end_forces if item["combination"] == combo.name)
    tip = next(
        item
        for item in analysis.displacements
        if item["combination"] == combo.name and item["node_id"] == "node-tip"
    )

    oriented = get_local_section_axis_properties(section, 0.0)
    e_kN_m2 = 210000.0 * 1000.0
    inertia_m4 = oriented.local_iy_mm4 * 1e-12
    expected_deflection_m = 10.0 * 2.0**3 / (3.0 * e_kN_m2 * inertia_m4)

    assert reaction["reaction_fz_kN"] == pytest.approx(10.0, rel=1e-6)
    assert abs(reaction["reaction_my_kNm"]) == pytest.approx(20.0, rel=1e-4)
    assert abs(member["M_i_kNm"]) == pytest.approx(20.0, rel=1e-4)
    assert abs(tip["uz_m"]) == pytest.approx(expected_deflection_m, rel=1e-4)


def test_phase03_engineering_model_uses_global_frame_for_supported_case():
    ctx = run_full_calculation(_cantilever_input())

    assert ctx.engineering_model.structure.calculation_model == CalculationModelType.GLOBAL_FRAME
    assert ctx.engineering_report_state.state_for("solver_results").state == (
        CalculationResultState.VERIFIED
    )
    assert ctx.engineering_model.solver_results.reactions
    assert ctx.engineering_model.solver_results.displacements
    assert ctx.engineering_report_state.state_for("member_checks").state == (
        CalculationResultState.VERIFIED
    )


def test_serviceability_remains_not_verified_even_with_solver_results():
    from sfsc.models import CalculationOptions

    ctx = run_full_calculation(
        _cantilever_input(calculation_options=CalculationOptions(include_serviceability=True))
    )

    assert ctx.engineering_report_state.state_for("solver_results").state == (
        CalculationResultState.VERIFIED
    )
    assert ctx.engineering_report_state.state_for("serviceability").state == (
        CalculationResultState.NOT_VERIFIED
    )


def test_bracketed_cantilever_solver_reports_beam_and_diagonal_forces():
    ctx = run_full_calculation(_cantilever_input(cantilever_subtype=CantileverSubtype.BRACKETED))

    assert ctx.engineering_model.structure.calculation_model == CalculationModelType.GLOBAL_FRAME
    member_ids = {row["member_id"] for row in ctx.fan_support_result.solver_member_end_forces}
    assert "member-beam" in member_ids
    assert "member-diagonal" in member_ids


def _make_fan_units():
    return [
        FanUnit(
            tag="FAN-1",
            fan_type=FanType.CENTRIFUGAL,
            weight_kg=280.0,
            operating_weight_kg=300.0,
            footprint_length_mm=1000.0,
            footprint_width_mm=800.0,
            centre_of_gravity_height_mm=350.0,
        )
    ]


def test_pedestal_uses_global_frame():
    ctx = run_full_calculation(
        FanSupportInput(
            project_name="Phase 03 Pedestal",
            support_tag="FSU-PH03-PED",
            prepared_by="Eng. Phase 03",
            fan_units=_make_fan_units(),
            support_type=SupportType.PEDESTAL,
            country=Country.PORTUGAL,
            seismic_zone="1.2",
            installation_height_mm=700.0,
            span_mm=1100.0,
        )
    )

    assert ctx.engineering_model.structure.calculation_model == CalculationModelType.GLOBAL_FRAME
    assert ctx.engineering_report_state.state_for("solver_results").state == (
        CalculationResultState.VERIFIED
    )
    assert ctx.engineering_model.solver_results.reactions
    assert ctx.engineering_model.solver_results.displacements


def test_hanger_uses_global_frame():
    ctx = run_full_calculation(
        FanSupportInput(
            project_name="Phase 03 Hanger",
            support_tag="FSU-PH03-HNG",
            prepared_by="Eng. Phase 03",
            fan_units=_make_fan_units(),
            support_type=SupportType.HANGER,
            country=Country.PORTUGAL,
            seismic_zone="1.2",
            installation_height_mm=1200.0,
            span_mm=1500.0,
        )
    )

    assert ctx.engineering_model.structure.calculation_model == CalculationModelType.GLOBAL_FRAME
    assert ctx.engineering_model.solver_results.reactions
    assert ctx.engineering_model.solver_results.displacements


def test_cantilever_2_uses_global_frame():
    ctx = run_full_calculation(
        FanSupportInput(
            project_name="Phase 03 Cantilever 2",
            support_tag="FSU-PH03-C2",
            prepared_by="Eng. Phase 03",
            fan_units=_make_fan_units(),
            support_type=SupportType.CANTILEVER_2,
            country=Country.PORTUGAL,
            seismic_zone="1.2",
            installation_height_mm=1000.0,
            span_mm=2000.0,
        )
    )

    assert ctx.engineering_model.structure.calculation_model == CalculationModelType.GLOBAL_FRAME
    assert ctx.engineering_model.solver_results.reactions
    assert ctx.engineering_model.solver_results.displacements


def test_cantilever_3_uses_global_frame():
    ctx = run_full_calculation(
        FanSupportInput(
            project_name="Phase 03 Cantilever 3",
            support_tag="FSU-PH03-C3",
            prepared_by="Eng. Phase 03",
            fan_units=_make_fan_units(),
            support_type=SupportType.CANTILEVER_3,
            country=Country.PORTUGAL,
            seismic_zone="1.2",
            installation_height_mm=2000.0,
            span_mm=3000.0,
        )
    )

    assert ctx.engineering_model.structure.calculation_model == CalculationModelType.GLOBAL_FRAME
    assert ctx.engineering_model.solver_results.reactions
    assert ctx.engineering_model.solver_results.displacements


def test_hanger_midspan_deflection_matches_closed_form():
    """Simply-supported beam with central point load: δ = PL³/48EI."""
    section = get_section(SectionFamily.HEB, "HEB200")
    combo = LoadCombination(name="ULS_fundamental", V_z_kN=10.0)
    inp = FanSupportInput(
        project_name="Phase 03 Hanger CF",
        support_tag="FSU-PH03-HNG-CF",
        prepared_by="Eng.",
        fan_units=_make_fan_units(),
        support_type=SupportType.HANGER,
        country=Country.PORTUGAL,
        seismic_zone="1.2",
        installation_height_mm=1200.0,
        span_mm=2000.0,
    )

    analysis = run_global_frame_analysis(inp, [combo], section, orientation_deg=0.0)

    assert analysis.supported is True
    assert analysis.solved is True

    from sfsc.section_orientation import get_local_section_axis_properties

    oriented = get_local_section_axis_properties(section, 0.0)
    e_kN_m2 = 210_000.0 * 1_000.0
    inertia_m4 = oriented.local_iy_mm4 * 1e-12
    span_m = 2.0
    expected_deflection_m = 10.0 * span_m**3 / (48.0 * e_kN_m2 * inertia_m4)

    mid = next(
        item
        for item in analysis.displacements
        if item["combination"] == combo.name and item["node_id"] == "node-mid"
    )
    assert abs(mid["uz_m"]) == pytest.approx(expected_deflection_m, rel=1e-4)

    left_reaction = next(
        item
        for item in analysis.reactions
        if item["combination"] == combo.name and item["node_id"] == "node-left"
    )
    assert left_reaction["reaction_fz_kN"] == pytest.approx(5.0, rel=1e-6)
