import pytest

from sfsc.catalogs.steel_section_catalog import get_section
from sfsc.engineering import CalculationResultState
from sfsc.engines.global_frame import run_global_frame_analysis
from sfsc.engines.grillage import (
    GrillageMember,
    GrillageNode,
    GrillagePointLoad,
    GrillageSupport,
    run_grillage_analysis,
)
from sfsc.engines.load_surfaces import build_load_path_summary
from sfsc.engines.selector import run_full_calculation
from sfsc.enums import (
    Country,
    FanType,
    LoadDistributionMethod,
    ModuleId,
    SectionFamily,
    SupportType,
    WalkingSurfaceType,
)
from sfsc.models import FanSupportInput, FanUnit, LoadCombination, WalkingSurface

E_KN_M2 = 210_000_000.0
G_KN_M2 = 81_000_000.0
I_M4 = 8.0e-6
J_M4 = 1.0e-6


def _member(member_id: str, node_i: str, node_j: str, direction: str) -> GrillageMember:
    return GrillageMember(
        id=member_id,
        node_i=node_i,
        node_j=node_j,
        elastic_modulus_kN_m2=E_KN_M2,
        shear_modulus_kN_m2=G_KN_M2,
        inertia_m4=I_M4,
        torsion_constant_m4=J_M4,
        direction=direction,
    )


def test_single_span_grillage_member_matches_simply_supported_beam_closed_form():
    length_m = 4.0
    load_kN = 12.0
    nodes = [
        GrillageNode("left", 0.0, 0.0),
        GrillageNode("mid", length_m / 2.0, 0.0),
        GrillageNode("right", length_m, 0.0),
    ]
    members = [
        _member("beam-left", "left", "mid", "longitudinal"),
        _member("beam-right", "mid", "right", "longitudinal"),
    ]
    supports = [
        GrillageSupport("left", w=True, rx=True),
        GrillageSupport("right", w=True, rx=True),
    ]

    result = run_grillage_analysis(
        nodes,
        members,
        supports,
        [GrillagePointLoad("mid", downward_kN=load_kN)],
    )

    assert result.solved is True
    mid = next(row for row in result.displacements if row["node_id"] == "mid")
    expected_deflection_m = load_kN * length_m**3 / (48.0 * E_KN_M2 * I_M4)
    expected_moment_kNm = load_kN * length_m / 4.0
    member_moments = [
        abs(float(row[key])) for row in result.member_end_forces for key in ("M_i_kNm", "M_j_kNm")
    ]

    assert abs(float(mid["w_m"])) == pytest.approx(expected_deflection_m, rel=1e-8)
    assert max(member_moments) == pytest.approx(expected_moment_kNm, rel=1e-8)


def test_two_by_two_panel_grid_is_symmetric_under_central_load():
    coordinates = (0.0, 1.0, 2.0)
    nodes = [
        GrillageNode(f"n-{ix}-{iy}", x_m, y_m)
        for iy, y_m in enumerate(coordinates)
        for ix, x_m in enumerate(coordinates)
    ]
    members = []
    for iy in range(3):
        for ix in range(2):
            members.append(
                _member(
                    f"long-{ix}-{iy}",
                    f"n-{ix}-{iy}",
                    f"n-{ix + 1}-{iy}",
                    "longitudinal",
                )
            )
    for ix in range(3):
        for iy in range(2):
            members.append(
                _member(
                    f"cross-{ix}-{iy}",
                    f"n-{ix}-{iy}",
                    f"n-{ix}-{iy + 1}",
                    "transverse",
                )
            )
    supports = [
        GrillageSupport("n-0-0"),
        GrillageSupport("n-2-0"),
        GrillageSupport("n-0-2"),
        GrillageSupport("n-2-2"),
    ]

    result = run_grillage_analysis(
        nodes,
        members,
        supports,
        [GrillagePointLoad("n-1-1", downward_kN=10.0)],
    )

    assert result.solved is True
    reactions = {row["node_id"]: float(row["reaction_fz_kN"]) for row in result.reactions}
    assert len(set(round(value, 8) for value in reactions.values())) == 1

    force_by_member = {row["member_id"]: row for row in result.member_end_forces}
    assert abs(float(force_by_member["long-0-1"]["M_j_kNm"])) == pytest.approx(
        abs(float(force_by_member["long-1-1"]["M_i_kNm"])),
        rel=1e-8,
    )
    assert abs(float(force_by_member["cross-1-0"]["M_j_kNm"])) == pytest.approx(
        abs(float(force_by_member["cross-1-1"]["M_i_kNm"])),
        rel=1e-8,
    )


def test_grillage_vertical_reactions_conserve_applied_load():
    nodes = [
        GrillageNode("a", 0.0, 0.0),
        GrillageNode("b", 1.0, 0.0),
        GrillageNode("c", 2.0, 0.0),
    ]
    result = run_grillage_analysis(
        nodes,
        [
            _member("ab", "a", "b", "longitudinal"),
            _member("bc", "b", "c", "longitudinal"),
        ],
        [
            GrillageSupport("a", w=True, rx=True),
            GrillageSupport("c", w=True, rx=True),
        ],
        [GrillagePointLoad("b", downward_kN=7.5)],
    )

    total_reaction_kN = sum(float(row["reaction_fz_kN"]) for row in result.reactions)
    assert total_reaction_kN == pytest.approx(7.5, rel=1e-10)


def _platform_input(**updates) -> FanSupportInput:
    data = {
        "project_name": "Phase 08",
        "support_tag": "GRID-01",
        "prepared_by": "Eng.",
        "fan_units": [
            FanUnit(
                tag="FAN-1",
                fan_type=FanType.CENTRIFUGAL,
                weight_kg=100.0,
                operating_weight_kg=110.0,
                footprint_length_mm=800.0,
                footprint_width_mm=600.0,
                centre_of_gravity_height_mm=300.0,
            )
        ],
        "support_type": SupportType.PLATFORM_FRAME_BRACED,
        "country": Country.PORTUGAL,
        "installation_height_mm": 800.0,
        "span_mm": 2000.0,
        "platform_n_beams": 3,
        "platform_width_mm": 2000.0,
        "platform_length_mm": 2000.0,
    }
    data.update(updates)
    return FanSupportInput(**data)


def test_two_way_surface_distribution_conserves_load_and_uses_both_directions():
    inp = _platform_input(
        platform_n_crossbeams=3,
        walking_surface=WalkingSurface(
            surface_type=WalkingSurfaceType.STEEL_GRATING_TRAMEX,
            self_weight_kn_m2=1.0,
            distribution_method=LoadDistributionMethod.TWO_WAY,
        ),
    )

    summary = build_load_path_summary(inp)
    lines = [
        row for row in summary.distributed_line_loads if row["source"] == "surface_self_weight"
    ]

    assert {str(row["target_member"]).split("_")[0] for row in lines} == {
        "beam",
        "crossbeam",
    }
    assert sum(float(row["total_load_kN"]) for row in lines) == pytest.approx(4.0)
    assert {float(row["direction_share"]) for row in lines} == {0.5}


def test_crossbeam_default_zero_preserves_legacy_platform_input():
    inp = _platform_input()

    assert inp.platform_n_crossbeams == 0
    assert inp.has_platform_grillage is False


def test_platform_with_crossbeams_uses_real_grillage_and_conserves_load():
    inp = _platform_input(platform_n_crossbeams=3)
    section = get_section(SectionFamily.HEB, "HEB200")
    combination = LoadCombination(name="ULS_fundamental", V_z_kN=18.0)

    result = run_global_frame_analysis(
        inp,
        [combination],
        section,
        orientation_deg=0.0,
    )

    assert result.solved is True
    assert len(result.nodes) == 9
    assert len(result.members) == 12
    assert {row["direction"] for row in result.members} == {
        "longitudinal",
        "transverse",
    }
    assert sum(float(row["reaction_fz_kN"]) for row in result.reactions) == pytest.approx(
        18.0,
        rel=1e-8,
    )
    assert any(str(row["member_id"]).startswith("crossbeam-") for row in result.member_end_forces)


def test_full_platform_calculation_selects_section_from_grillage_envelope():
    inp = _platform_input(
        platform_n_crossbeams=3,
        walking_surface=WalkingSurface(
            surface_type=WalkingSurfaceType.STEEL_GRATING_TRAMEX,
            self_weight_kn_m2=0.3,
            distribution_method=LoadDistributionMethod.TWO_WAY,
        ),
    )

    ctx = run_full_calculation(inp)
    result = ctx.fan_support_result

    assert result is not None
    assert result.solver_engine == "global_frame"
    assert result.solver_failed is False
    assert result.recommended_section is not None
    assert result.section_verification is not None
    assert result.section_verification.utilization_ratio <= 0.9
    assert any(str(member["id"]).startswith("crossbeam-") for member in result.solver_members)
    assert result.member_check_rows
    assert result.platform is not None
    assert result.platform.analysis_model == "grillage_2_5d"
    assert result.platform.n_crossbeams == 3
    assert all("grillage solver" in combo.description for combo in result.member_forces)
    surface_check = next(
        check for check in result.module_breakdown if check.id == ModuleId.LOAD_DISTRIBUTION_SURFACE
    )
    assert surface_check.status.value == "ok"
    assert ctx.engineering_report_state.state_for("load_surfaces").state == (
        CalculationResultState.VERIFIED
    )
    assert ctx.dataset_provenance["solver_module"] == "grillage_2_5d"
    assert ctx.dataset_provenance["platform_grid"] == {
        "longitudinal_beams": 3,
        "crossbeams": 3,
    }
    assert result.quantities is not None
    assert any(item["item"] == "platform_crossbeams" for item in result.quantities.line_items)
