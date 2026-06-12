from sfsc.engines.loads import calculate_loads
from sfsc.engines.selector import run_full_calculation
from sfsc.engines.support_types.platform_frame_braced import compute_platform_breakdown
from sfsc.enums import (
    CantileverSubtype,
    Country,
    FanType,
    SteelGrade,
    StructuralCode,
    SupportType,
    WalkingSurfaceType,
)
from sfsc.models import FanSupportInput, FanUnit, WalkingSurface


def _france_air_units(n=4, kg=83.0):
    return [
        FanUnit(
            tag=f"V{i + 1}",
            fan_type=FanType.CENTRIFUGAL,
            weight_kg=kg,
            operating_weight_kg=kg,
            footprint_length_mm=760.0,
            footprint_width_mm=760.0,
            centre_of_gravity_height_mm=300.0,
        )
        for i in range(n)
    ]


def _platform_inp(subtype=CantileverSubtype.BRACKETED, n_beams=3):
    return FanSupportInput(
        project_name="Caso real France Air",
        support_tag="FSU-REAL",
        prepared_by="Eng",
        fan_units=_france_air_units(),
        support_type=SupportType.PLATFORM_FRAME_BRACED,
        cantilever_subtype=subtype,
        country=Country.EU_GENERIC,
        steel_grade=SteelGrade.S235,
        installation_height_mm=1000.0,
        span_mm=2000.0,
        platform_n_beams=n_beams,
        platform_width_mm=2425.0,
        platform_length_mm=2000.0,
        walking_surface=WalkingSurface(
            surface_type=WalkingSurfaceType.STEEL_GRATING_TRAMEX,
            self_weight_kn_m2=0.30,
        ),
    )


def test_platform_self_weight_counts_surface_and_steel():
    inp = _platform_inp()
    total_g_kN, _ = calculate_loads(inp, StructuralCode.EC3_EN1993, 0.10)
    equipment_kN = 4 * 83 * 9.80665 / 1000.0
    assert total_g_kN > equipment_kN * 1.5


def test_platform_load_shared_across_beams():
    inp_2 = _platform_inp(n_beams=2)
    inp_4 = _platform_inp(n_beams=4)
    combos_2 = calculate_loads(inp_2, StructuralCode.EC3_EN1993, 0.10)[1]
    combos_4 = calculate_loads(inp_4, StructuralCode.EC3_EN1993, 0.10)[1]
    bd_2 = compute_platform_breakdown(inp_2, combos_2)
    bd_4 = compute_platform_breakdown(inp_4, combos_4)
    assert bd_4.load_per_beam_kN < bd_2.load_per_beam_kN
    assert bd_4.moment_per_beam_kNm < bd_2.moment_per_beam_kNm


def test_platform_braced_has_diagonal_and_pure_does_not():
    braced = run_full_calculation(_platform_inp(CantileverSubtype.BRACKETED)).fan_support_result
    pure = run_full_calculation(_platform_inp(CantileverSubtype.PURE)).fan_support_result

    assert braced.platform is not None
    assert braced.platform.braced is True
    assert braced.platform.diagonal is not None
    assert braced.platform.diagonal.axial_force_kN > 0

    assert pure.platform is not None
    assert pure.platform.braced is False
    assert pure.platform.diagonal is None
    assert pure.platform.axial_per_beam_kN == 0.0


def test_platform_result_exposes_summary():
    res = run_full_calculation(_platform_inp()).fan_support_result
    assert res.platform is not None
    assert res.platform.n_beams == 3
    assert res.platform.area_m2 > 0
    assert res.platform.surface_weight_kg > 0
    assert res.platform.steel_weight_kg > 0
