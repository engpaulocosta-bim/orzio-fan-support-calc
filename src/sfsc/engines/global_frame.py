"""Phase 03 controlled 2D global-frame solver."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..catalogs.steel_grade_catalog import get_grade_spec
from ..enums import CantileverSubtype, SupportType
from ..models import FanSupportInput, LoadCombination, SteelSection
from ..section_orientation import get_local_section_axis_properties
from ..units import mm_to_m
from .grillage import (
    GrillageMember,
    GrillageNode,
    GrillagePointLoad,
    GrillageSupport,
    build_grillage_stiffness,
    run_grillage_analysis,
)
from .modal_analysis import ModalAnalysisResult, run_modal_analysis

_SINGULAR_TOLERANCE = 1e12


@dataclass(frozen=True)
class _Node2D:
    id: str
    x_m: float
    z_m: float


@dataclass(frozen=True)
class _Support2D:
    node_id: str
    ux: bool
    uz: bool
    ry: bool


@dataclass(frozen=True)
class _Element2D:
    id: str
    node_i: str
    node_j: str
    kind: str
    area_m2: float
    inertia_m4: float
    elastic_modulus_kN_m2: float


@dataclass(frozen=True)
class _FrameModel2D:
    nodes: list[_Node2D]
    elements: list[_Element2D]
    supports: list[_Support2D]
    loaded_node_id: str


@dataclass(frozen=True)
class GlobalFrameAnalysisResult:
    supported: bool
    solved: bool
    failed: bool
    warnings: list[str]
    nodes: list[dict[str, object]]
    members: list[dict[str, object]]
    supports: list[dict[str, object]]
    releases: list[dict[str, object]]
    reactions: list[dict[str, object]]
    displacements: list[dict[str, object]]
    member_end_forces: list[dict[str, object]]


def _section_area_m2(section: SteelSection) -> float:
    return section.A_cm2 * 1e-4


def _section_inertia_m4(section: SteelSection, orientation_deg: float) -> float:
    oriented = get_local_section_axis_properties(section, orientation_deg)
    return oriented.local_iy_mm4 * 1e-12


def _frame_local_stiffness(element: _Element2D, length_m: float) -> np.ndarray:
    ea_l = element.elastic_modulus_kN_m2 * element.area_m2 / length_m
    ei = element.elastic_modulus_kN_m2 * element.inertia_m4
    l2 = length_m**2
    l3 = length_m**3
    return np.array(
        [
            [ea_l, 0.0, 0.0, -ea_l, 0.0, 0.0],
            [0.0, 12.0 * ei / l3, 6.0 * ei / l2, 0.0, -12.0 * ei / l3, 6.0 * ei / l2],
            [0.0, 6.0 * ei / l2, 4.0 * ei / length_m, 0.0, -6.0 * ei / l2, 2.0 * ei / length_m],
            [-ea_l, 0.0, 0.0, ea_l, 0.0, 0.0],
            [0.0, -12.0 * ei / l3, -6.0 * ei / l2, 0.0, 12.0 * ei / l3, -6.0 * ei / l2],
            [0.0, 6.0 * ei / l2, 2.0 * ei / length_m, 0.0, -6.0 * ei / l2, 4.0 * ei / length_m],
        ],
        dtype=float,
    )


def _truss_local_stiffness(element: _Element2D, length_m: float) -> np.ndarray:
    ea_l = element.elastic_modulus_kN_m2 * element.area_m2 / length_m
    return np.array(
        [
            [ea_l, 0.0, 0.0, -ea_l, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [-ea_l, 0.0, 0.0, ea_l, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ],
        dtype=float,
    )


def _transformation_matrix(dx_m: float, dz_m: float, length_m: float) -> np.ndarray:
    c = dx_m / length_m
    s = dz_m / length_m
    return np.array(
        [
            [c, s, 0.0, 0.0, 0.0, 0.0],
            [-s, c, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, c, s, 0.0],
            [0.0, 0.0, 0.0, -s, c, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


def _build_cantilever_1_model(
    inp: FanSupportInput,
    section: SteelSection,
    orientation_deg: float,
) -> _FrameModel2D:
    elastic_modulus_kN_m2 = get_grade_spec(inp.steel_grade).E_mpa * 1_000.0
    area_m2 = _section_area_m2(section)
    inertia_m4 = _section_inertia_m4(section, orientation_deg)
    span_m = mm_to_m(inp.span_mm)
    height_m = mm_to_m(inp.installation_height_mm)
    subtype = inp.cantilever_subtype or CantileverSubtype.PURE

    if subtype == CantileverSubtype.BRACKETED:
        nodes = [
            _Node2D(id="node-base", x_m=0.0, z_m=0.0),
            _Node2D(id="node-top", x_m=0.0, z_m=height_m),
            _Node2D(id="node-tip", x_m=span_m, z_m=height_m),
        ]
        elements = [
            _Element2D(
                id="member-beam",
                node_i="node-top",
                node_j="node-tip",
                kind="frame",
                area_m2=area_m2,
                inertia_m4=inertia_m4,
                elastic_modulus_kN_m2=elastic_modulus_kN_m2,
            ),
            _Element2D(
                id="member-diagonal",
                node_i="node-base",
                node_j="node-tip",
                kind="truss",
                area_m2=area_m2,
                inertia_m4=0.0,
                elastic_modulus_kN_m2=elastic_modulus_kN_m2,
            ),
        ]
        supports = [
            _Support2D(node_id="node-base", ux=True, uz=True, ry=True),
            _Support2D(node_id="node-top", ux=True, uz=True, ry=False),
        ]
        return _FrameModel2D(
            nodes=nodes,
            elements=elements,
            supports=supports,
            loaded_node_id="node-tip",
        )

    nodes = [
        _Node2D(id="node-support", x_m=0.0, z_m=0.0),
        _Node2D(id="node-tip", x_m=span_m, z_m=0.0),
    ]
    elements = [
        _Element2D(
            id="member-beam",
            node_i="node-support",
            node_j="node-tip",
            kind="frame",
            area_m2=area_m2,
            inertia_m4=inertia_m4,
            elastic_modulus_kN_m2=elastic_modulus_kN_m2,
        )
    ]
    supports = [_Support2D(node_id="node-support", ux=True, uz=True, ry=True)]
    return _FrameModel2D(
        nodes=nodes, elements=elements, supports=supports, loaded_node_id="node-tip"
    )


def _build_hanger_model(
    inp: FanSupportInput,
    section: SteelSection,
    orientation_deg: float,
) -> _FrameModel2D:
    """Simply-supported beam with mid-span point load (hanger support beam)."""
    elastic_modulus_kN_m2 = get_grade_spec(inp.steel_grade).E_mpa * 1_000.0
    area_m2 = _section_area_m2(section)
    inertia_m4 = _section_inertia_m4(section, orientation_deg)
    span_m = mm_to_m(inp.span_mm)
    half = span_m / 2.0

    nodes = [
        _Node2D(id="node-left", x_m=0.0, z_m=0.0),
        _Node2D(id="node-mid", x_m=half, z_m=0.0),
        _Node2D(id="node-right", x_m=span_m, z_m=0.0),
    ]
    elements = [
        _Element2D(
            id="member-left",
            node_i="node-left",
            node_j="node-mid",
            kind="frame",
            area_m2=area_m2,
            inertia_m4=inertia_m4,
            elastic_modulus_kN_m2=elastic_modulus_kN_m2,
        ),
        _Element2D(
            id="member-right",
            node_i="node-mid",
            node_j="node-right",
            kind="frame",
            area_m2=area_m2,
            inertia_m4=inertia_m4,
            elastic_modulus_kN_m2=elastic_modulus_kN_m2,
        ),
    ]
    supports = [
        _Support2D(node_id="node-left", ux=True, uz=True, ry=False),
        _Support2D(node_id="node-right", ux=False, uz=True, ry=False),
    ]
    return _FrameModel2D(
        nodes=nodes, elements=elements, supports=supports, loaded_node_id="node-mid"
    )


def _build_cantilever_2_model(
    inp: FanSupportInput,
    section: SteelSection,
    orientation_deg: float,
) -> _FrameModel2D:
    """Symmetric double cantilever: simply-supported beam with mid-span load."""
    return _build_hanger_model(inp, section, orientation_deg)


def _build_cantilever_3_model(
    inp: FanSupportInput,
    section: SteelSection,
    orientation_deg: float,
) -> _FrameModel2D:
    """Inverted-U portal frame: two columns fixed at base, beam across top, load at mid-beam."""
    elastic_modulus_kN_m2 = get_grade_spec(inp.steel_grade).E_mpa * 1_000.0
    area_m2 = _section_area_m2(section)
    inertia_m4 = _section_inertia_m4(section, orientation_deg)
    span_m = mm_to_m(inp.span_mm)
    height_m = mm_to_m(inp.installation_height_mm)
    half = span_m / 2.0

    nodes = [
        _Node2D(id="node-base-left", x_m=0.0, z_m=0.0),
        _Node2D(id="node-top-left", x_m=0.0, z_m=height_m),
        _Node2D(id="node-top-mid", x_m=half, z_m=height_m),
        _Node2D(id="node-top-right", x_m=span_m, z_m=height_m),
        _Node2D(id="node-base-right", x_m=span_m, z_m=0.0),
    ]
    elements = [
        _Element2D(
            id="member-col-left",
            node_i="node-base-left",
            node_j="node-top-left",
            kind="frame",
            area_m2=area_m2,
            inertia_m4=inertia_m4,
            elastic_modulus_kN_m2=elastic_modulus_kN_m2,
        ),
        _Element2D(
            id="member-beam-left",
            node_i="node-top-left",
            node_j="node-top-mid",
            kind="frame",
            area_m2=area_m2,
            inertia_m4=inertia_m4,
            elastic_modulus_kN_m2=elastic_modulus_kN_m2,
        ),
        _Element2D(
            id="member-beam-right",
            node_i="node-top-mid",
            node_j="node-top-right",
            kind="frame",
            area_m2=area_m2,
            inertia_m4=inertia_m4,
            elastic_modulus_kN_m2=elastic_modulus_kN_m2,
        ),
        _Element2D(
            id="member-col-right",
            node_i="node-top-right",
            node_j="node-base-right",
            kind="frame",
            area_m2=area_m2,
            inertia_m4=inertia_m4,
            elastic_modulus_kN_m2=elastic_modulus_kN_m2,
        ),
    ]
    supports = [
        _Support2D(node_id="node-base-left", ux=True, uz=True, ry=True),
        _Support2D(node_id="node-base-right", ux=True, uz=True, ry=True),
    ]
    return _FrameModel2D(
        nodes=nodes, elements=elements, supports=supports, loaded_node_id="node-top-mid"
    )


def _build_pedestal_model(
    inp: FanSupportInput,
    section: SteelSection,
    orientation_deg: float,
) -> _FrameModel2D:
    """Simply-supported beam (one representative skid) with mid-span load."""
    return _build_hanger_model(inp, section, orientation_deg)


def _build_combined_model(
    inp: FanSupportInput,
    section: SteelSection,
    orientation_deg: float,
) -> _FrameModel2D:
    """Same frame geometry as pedestal; load distribution accounted in combinations."""
    return _build_hanger_model(inp, section, orientation_deg)


def _build_platform_model(
    inp: FanSupportInput,
    section: SteelSection,
    orientation_deg: float,
) -> _FrameModel2D:
    """One representative platform beam: cantilevered (bracketed) or simply-supported."""
    elastic_modulus_kN_m2 = get_grade_spec(inp.steel_grade).E_mpa * 1_000.0
    area_m2 = _section_area_m2(section)
    inertia_m4 = _section_inertia_m4(section, orientation_deg)
    length_m = (
        mm_to_m(inp.platform_length_eff_mm)
        if inp.platform_length_eff_mm > 0
        else mm_to_m(inp.span_mm)
    )
    height_m = mm_to_m(inp.installation_height_mm)
    braced = inp.cantilever_subtype is None or inp.cantilever_subtype == CantileverSubtype.BRACKETED

    if braced and height_m > 0:
        nodes = [
            _Node2D(id="node-base", x_m=0.0, z_m=0.0),
            _Node2D(id="node-top", x_m=0.0, z_m=height_m),
            _Node2D(id="node-tip", x_m=length_m, z_m=height_m),
        ]
        elements = [
            _Element2D(
                id="member-beam",
                node_i="node-top",
                node_j="node-tip",
                kind="frame",
                area_m2=area_m2,
                inertia_m4=inertia_m4,
                elastic_modulus_kN_m2=elastic_modulus_kN_m2,
            ),
            _Element2D(
                id="member-diagonal",
                node_i="node-base",
                node_j="node-tip",
                kind="truss",
                area_m2=area_m2,
                inertia_m4=0.0,
                elastic_modulus_kN_m2=elastic_modulus_kN_m2,
            ),
        ]
        supports = [
            _Support2D(node_id="node-base", ux=True, uz=True, ry=True),
            _Support2D(node_id="node-top", ux=True, uz=True, ry=False),
        ]
        return _FrameModel2D(
            nodes=nodes, elements=elements, supports=supports, loaded_node_id="node-tip"
        )

    # Unbraced: simply-supported beam (one beam of platform)
    half = length_m / 2.0
    nodes = [
        _Node2D(id="node-left", x_m=0.0, z_m=0.0),
        _Node2D(id="node-mid", x_m=half, z_m=0.0),
        _Node2D(id="node-right", x_m=length_m, z_m=0.0),
    ]
    elements = [
        _Element2D(
            id="member-left",
            node_i="node-left",
            node_j="node-mid",
            kind="frame",
            area_m2=area_m2,
            inertia_m4=inertia_m4,
            elastic_modulus_kN_m2=elastic_modulus_kN_m2,
        ),
        _Element2D(
            id="member-right",
            node_i="node-mid",
            node_j="node-right",
            kind="frame",
            area_m2=area_m2,
            inertia_m4=inertia_m4,
            elastic_modulus_kN_m2=elastic_modulus_kN_m2,
        ),
    ]
    supports = [
        _Support2D(node_id="node-left", ux=True, uz=True, ry=False),
        _Support2D(node_id="node-right", ux=False, uz=True, ry=False),
    ]
    return _FrameModel2D(
        nodes=nodes, elements=elements, supports=supports, loaded_node_id="node-mid"
    )


def _section_torsion_constant_m4(section: SteelSection) -> float:
    """Estimate Saint-Venant J from the section dimensions available in the catalog."""

    h_mm = section.h_mm
    b_mm = section.b_mm
    tw_mm = section.tw_mm
    tf_mm = section.tf_mm
    if section.family.value == "RHS":
        median_h_mm = max(h_mm - tf_mm, 1e-6)
        median_b_mm = max(b_mm - tw_mm, 1e-6)
        enclosed_area_mm2 = median_h_mm * median_b_mm
        wall_sum = 2.0 * median_h_mm / max(tw_mm, 1e-6) + 2.0 * median_b_mm / max(tf_mm, 1e-6)
        torsion_mm4 = 4.0 * enclosed_area_mm2**2 / wall_sum
    else:
        web_height_mm = max(h_mm - 2.0 * tf_mm, 0.0)
        torsion_mm4 = (2.0 * b_mm * tf_mm**3 + web_height_mm * tw_mm**3) / 3.0
    return max(torsion_mm4 * 1e-12, 1e-16)


def _platform_grillage_geometry(
    inp: FanSupportInput,
    section: SteelSection,
    orientation_deg: float,
) -> tuple[
    list[GrillageNode],
    list[GrillageMember],
    list[GrillageSupport],
    list[str],
]:
    grade = get_grade_spec(inp.steel_grade)
    elastic_modulus_kN_m2 = grade.E_mpa * 1_000.0
    shear_modulus_kN_m2 = grade.G_mpa * 1_000.0
    inertia_m4 = _section_inertia_m4(section, orientation_deg)
    torsion_constant_m4 = _section_torsion_constant_m4(section)
    length_m = mm_to_m(inp.platform_length_eff_mm)
    width_m = mm_to_m(inp.platform_width_eff_mm)
    n_longitudinal = max(2, inp.platform_n_beams)
    n_crossbeams = max(2, inp.platform_n_crossbeams)
    x_positions = np.linspace(0.0, length_m, n_crossbeams)
    y_positions = np.linspace(0.0, width_m, n_longitudinal)

    nodes = [
        GrillageNode(
            id=f"grid-{cross_index}-{long_index}",
            x_m=float(x_m),
            y_m=float(y_m),
        )
        for long_index, y_m in enumerate(y_positions)
        for cross_index, x_m in enumerate(x_positions)
    ]
    members: list[GrillageMember] = []
    for long_index in range(n_longitudinal):
        for cross_index in range(n_crossbeams - 1):
            members.append(
                GrillageMember(
                    id=f"beam-{long_index + 1}-{cross_index + 1}",
                    node_i=f"grid-{cross_index}-{long_index}",
                    node_j=f"grid-{cross_index + 1}-{long_index}",
                    elastic_modulus_kN_m2=elastic_modulus_kN_m2,
                    shear_modulus_kN_m2=shear_modulus_kN_m2,
                    inertia_m4=inertia_m4,
                    torsion_constant_m4=torsion_constant_m4,
                    direction="longitudinal",
                )
            )
    for cross_index in range(n_crossbeams):
        for long_index in range(n_longitudinal - 1):
            members.append(
                GrillageMember(
                    id=f"crossbeam-{cross_index + 1}-{long_index + 1}",
                    node_i=f"grid-{cross_index}-{long_index}",
                    node_j=f"grid-{cross_index}-{long_index + 1}",
                    elastic_modulus_kN_m2=elastic_modulus_kN_m2,
                    shear_modulus_kN_m2=shear_modulus_kN_m2,
                    inertia_m4=inertia_m4,
                    torsion_constant_m4=torsion_constant_m4,
                    direction="transverse",
                )
            )

    braced = inp.cantilever_subtype is None or inp.cantilever_subtype == CantileverSubtype.BRACKETED
    if braced:
        supports = [
            GrillageSupport(
                node_id=f"grid-0-{long_index}",
                w=True,
                rx=True,
                ry=True,
            )
            for long_index in range(n_longitudinal)
        ]
    else:
        supports = [
            GrillageSupport("grid-0-0", w=True),
            GrillageSupport(f"grid-{n_crossbeams - 1}-0", w=True),
            GrillageSupport(f"grid-0-{n_longitudinal - 1}", w=True),
            GrillageSupport(
                f"grid-{n_crossbeams - 1}-{n_longitudinal - 1}",
                w=True,
            ),
        ]

    centre_distance = min(
        (node.x_m - length_m / 2.0) ** 2 + (node.y_m - width_m / 2.0) ** 2 for node in nodes
    )
    loaded_node_ids = [
        node.id
        for node in nodes
        if abs((node.x_m - length_m / 2.0) ** 2 + (node.y_m - width_m / 2.0) ** 2 - centre_distance)
        <= 1e-12
    ]
    return nodes, members, supports, loaded_node_ids


def _run_platform_grillage_analysis(
    inp: FanSupportInput,
    combinations: list[LoadCombination],
    section: SteelSection,
    orientation_deg: float,
) -> GlobalFrameAnalysisResult:
    nodes, members, supports, loaded_node_ids = _platform_grillage_geometry(
        inp,
        section,
        orientation_deg,
    )
    warnings = [
        (
            "Platform vertical response solved with a 2.5D grillage. "
            "Horizontal brace response remains covered by the separate diagonal check."
        )
    ]
    reactions: list[dict[str, object]] = []
    displacements: list[dict[str, object]] = []
    member_end_forces: list[dict[str, object]] = []

    for combination in combinations:
        load_share_kN = abs(combination.V_z_kN) / len(loaded_node_ids)
        eccentricity_m = mm_to_m(inp.eccentricity_mm)
        loads = [
            GrillagePointLoad(
                node_id=node_id,
                downward_kN=load_share_kN,
                moment_y_kNm=-load_share_kN * eccentricity_m,
            )
            for node_id in loaded_node_ids
        ]
        result = run_grillage_analysis(nodes, members, supports, loads)
        if result.failed or not result.solved:
            return GlobalFrameAnalysisResult(
                supported=True,
                solved=False,
                failed=True,
                warnings=warnings + result.warnings,
                nodes=[
                    {
                        "id": node.id,
                        "x_m": node.x_m,
                        "y_m": node.y_m,
                        "z_m": mm_to_m(inp.installation_height_mm),
                    }
                    for node in nodes
                ],
                members=[
                    {
                        "id": member.id,
                        "node_i": member.node_i,
                        "node_j": member.node_j,
                        "kind": "frame",
                        "direction": member.direction,
                    }
                    for member in members
                ],
                supports=[],
                releases=[],
                reactions=[],
                displacements=[],
                member_end_forces=[],
            )
        reactions.extend(
            {
                "combination": combination.name,
                "node_id": row["node_id"],
                "reaction_fx_kN": 0.0,
                "reaction_fz_kN": row["reaction_fz_kN"],
                "reaction_mx_kNm": row["reaction_mx_kNm"],
                "reaction_my_kNm": row["reaction_my_kNm"],
            }
            for row in result.reactions
        )
        displacements.extend(
            {
                "combination": combination.name,
                "node_id": row["node_id"],
                "ux_m": 0.0,
                "uz_m": row["w_m"],
                "rx_rad": row["rx_rad"],
                "ry_rad": row["ry_rad"],
            }
            for row in result.displacements
        )
        member_end_forces.extend(
            {
                "combination": combination.name,
                "member_id": row["member_id"],
                "member_kind": "frame",
                "member_direction": row["member_direction"],
                "node_i": row["node_i"],
                "node_j": row["node_j"],
                "N_i_kN": 0.0,
                "V_i_kN": row["V_i_kN"],
                "M_i_kNm": row["M_i_kNm"],
                "T_i_kNm": row["T_i_kNm"],
                "N_j_kN": 0.0,
                "V_j_kN": row["V_j_kN"],
                "M_j_kNm": row["M_j_kNm"],
                "T_j_kNm": row["T_j_kNm"],
            }
            for row in result.member_end_forces
        )

    return GlobalFrameAnalysisResult(
        supported=True,
        solved=True,
        failed=False,
        warnings=warnings,
        nodes=[
            {
                "id": node.id,
                "x_m": node.x_m,
                "y_m": node.y_m,
                "z_m": mm_to_m(inp.installation_height_mm),
            }
            for node in nodes
        ],
        members=[
            {
                "id": member.id,
                "node_i": member.node_i,
                "node_j": member.node_j,
                "kind": "frame",
                "direction": member.direction,
            }
            for member in members
        ],
        supports=[
            {
                "node_id": support.node_id,
                "w": support.w,
                "rx": support.rx,
                "ry": support.ry,
                "ux": support.rx,
                "uz": support.w,
            }
            for support in supports
        ],
        releases=[],
        reactions=reactions,
        displacements=displacements,
        member_end_forces=member_end_forces,
    )


def run_platform_modal_analysis(
    inp: FanSupportInput,
    section: SteelSection,
    orientation_deg: float,
    excitation_frequencies_hz: list[float],
) -> ModalAnalysisResult:
    """Compute the first natural frequency of the platform grillage and check resonance.

    Only applicable when ``inp.has_platform_grillage`` is True. Falls back to a
    failed result for other support types.
    """

    nodes, members, supports, loaded_node_ids = _platform_grillage_geometry(
        inp, section, orientation_deg
    )

    stiffness_result = build_grillage_stiffness(nodes, members, supports)
    if stiffness_result is None:
        return ModalAnalysisResult(
            solved=False,
            failed=True,
            failure_reason="modal_stiffness_assembly_failed",
            first_frequency_hz=None,
            excitation_frequencies_hz=excitation_frequencies_hz,
            frequency_ratios=[],
            resonance_violated=False,
            violated_excitation_hz=None,
            warnings=["Falha na montagem da matriz de rigidez para análise modal."],
            intermediate={},
        )

    k_ff, free_dofs = stiffness_result
    section_area_m2 = section.A_cm2 * 1e-4
    equipment_mass_kg = sum(unit.operating_weight_kg for unit in inp.fan_units)

    return run_modal_analysis(
        nodes=nodes,
        members=members,
        supports=supports,
        loaded_node_ids=loaded_node_ids,
        stiffness_ff=k_ff,
        free_dofs=free_dofs,
        steel_density_kg_m3=7850.0,
        section_area_m2=section_area_m2,
        equipment_mass_kg=equipment_mass_kg,
        excitation_frequencies_hz=excitation_frequencies_hz,
    )


def _build_model(
    inp: FanSupportInput,
    section: SteelSection,
    orientation_deg: float,
) -> tuple[_FrameModel2D | None, list[str]]:
    if inp.support_type == SupportType.CANTILEVER_1:
        return _build_cantilever_1_model(inp, section, orientation_deg), []
    if inp.support_type == SupportType.HANGER:
        return _build_hanger_model(inp, section, orientation_deg), []
    if inp.support_type == SupportType.CANTILEVER_2:
        return _build_cantilever_2_model(inp, section, orientation_deg), []
    if inp.support_type == SupportType.CANTILEVER_3:
        return _build_cantilever_3_model(inp, section, orientation_deg), []
    if inp.support_type == SupportType.PEDESTAL:
        return _build_pedestal_model(inp, section, orientation_deg), []
    if inp.support_type == SupportType.COMBINED:
        return _build_combined_model(inp, section, orientation_deg), []
    if inp.support_type == SupportType.PLATFORM_FRAME_BRACED:
        return _build_platform_model(inp, section, orientation_deg), []
    return None, [
        f"Global frame solver not yet implemented for support type '{inp.support_type.value}'."
    ]


def run_global_frame_analysis(
    inp: FanSupportInput,
    combinations: list[LoadCombination],
    section: SteelSection | None,
    orientation_deg: float,
) -> GlobalFrameAnalysisResult:
    if section is None:
        return GlobalFrameAnalysisResult(
            supported=False,
            solved=False,
            failed=False,
            warnings=["Global frame solver skipped because no section is available."],
            nodes=[],
            members=[],
            supports=[],
            releases=[],
            reactions=[],
            displacements=[],
            member_end_forces=[],
        )

    if inp.support_type == SupportType.PLATFORM_FRAME_BRACED and inp.has_platform_grillage:
        return _run_platform_grillage_analysis(
            inp,
            combinations,
            section,
            orientation_deg,
        )

    model, warnings = _build_model(inp, section, orientation_deg)
    if model is None:
        return GlobalFrameAnalysisResult(
            supported=False,
            solved=False,
            failed=False,
            warnings=warnings,
            nodes=[],
            members=[],
            supports=[],
            releases=[],
            reactions=[],
            displacements=[],
            member_end_forces=[],
        )

    node_index = {node.id: idx for idx, node in enumerate(model.nodes)}
    dof_count = len(model.nodes) * 3
    stiffness = np.zeros((dof_count, dof_count), dtype=float)
    element_cache: list[tuple[_Element2D, np.ndarray, np.ndarray]] = []

    for element in model.elements:
        node_i = model.nodes[node_index[element.node_i]]
        node_j = model.nodes[node_index[element.node_j]]
        dx_m = node_j.x_m - node_i.x_m
        dz_m = node_j.z_m - node_i.z_m
        length_m = float(np.hypot(dx_m, dz_m))
        if length_m <= 0.0:
            return GlobalFrameAnalysisResult(
                supported=True,
                solved=False,
                failed=True,
                warnings=[f"Member '{element.id}' has zero length."],
                nodes=[],
                members=[],
                supports=[],
                releases=[],
                reactions=[],
                displacements=[],
                member_end_forces=[],
            )
        transform = _transformation_matrix(dx_m, dz_m, length_m)
        local_stiffness = (
            _frame_local_stiffness(element, length_m)
            if element.kind == "frame"
            else _truss_local_stiffness(element, length_m)
        )
        global_stiffness = transform.T @ local_stiffness @ transform
        dofs = [
            node_index[element.node_i] * 3,
            node_index[element.node_i] * 3 + 1,
            node_index[element.node_i] * 3 + 2,
            node_index[element.node_j] * 3,
            node_index[element.node_j] * 3 + 1,
            node_index[element.node_j] * 3 + 2,
        ]
        for row_index in range(6):
            for col_index in range(6):
                stiffness[dofs[row_index], dofs[col_index]] += global_stiffness[
                    row_index, col_index
                ]
        element_cache.append((element, transform, local_stiffness))

    restrained: set[int] = set()
    for support in model.supports:
        base = node_index[support.node_id] * 3
        if support.ux:
            restrained.add(base)
        if support.uz:
            restrained.add(base + 1)
        if support.ry:
            restrained.add(base + 2)

    free = [index for index in range(dof_count) if index not in restrained]
    restrained_sorted = sorted(restrained)
    if not free:
        return GlobalFrameAnalysisResult(
            supported=True,
            solved=False,
            failed=True,
            warnings=["Global frame solver found no free degrees of freedom."],
            nodes=[],
            members=[],
            supports=[],
            releases=[],
            reactions=[],
            displacements=[],
            member_end_forces=[],
        )

    nodal_displacements: list[dict[str, object]] = []
    support_reactions: list[dict[str, object]] = []
    member_end_forces: list[dict[str, object]] = []
    eccentricity_m = mm_to_m(inp.eccentricity_mm)

    for combo in combinations:
        load_vector = np.zeros(dof_count, dtype=float)
        load_base = node_index[model.loaded_node_id] * 3
        load_vector[load_base] += combo.V_y_kN
        load_vector[load_base + 1] += -combo.V_z_kN
        load_vector[load_base + 2] += -combo.V_z_kN * eccentricity_m

        k_ff = stiffness[np.ix_(free, free)]
        if np.linalg.cond(k_ff) > _SINGULAR_TOLERANCE:
            return GlobalFrameAnalysisResult(
                supported=True,
                solved=False,
                failed=True,
                warnings=[
                    f"Global frame solver instability detected for combination '{combo.name}'."
                ],
                nodes=[{"id": node.id, "x_m": node.x_m, "z_m": node.z_m} for node in model.nodes],
                members=[
                    {
                        "id": element.id,
                        "node_i": element.node_i,
                        "node_j": element.node_j,
                        "kind": element.kind,
                    }
                    for element in model.elements
                ],
                supports=[
                    {
                        "node_id": support.node_id,
                        "ux": support.ux,
                        "uz": support.uz,
                        "ry": support.ry,
                    }
                    for support in model.supports
                ],
                releases=[],
                reactions=[],
                displacements=[],
                member_end_forces=[],
            )
        displacement_vector = np.zeros(dof_count, dtype=float)
        displacement_vector[free] = np.linalg.solve(k_ff, load_vector[free])
        reaction_vector = stiffness @ displacement_vector - load_vector

        for node in model.nodes:
            base = node_index[node.id] * 3
            nodal_displacements.append(
                {
                    "combination": combo.name,
                    "node_id": node.id,
                    "ux_m": float(displacement_vector[base]),
                    "uz_m": float(displacement_vector[base + 1]),
                    "ry_rad": float(displacement_vector[base + 2]),
                }
            )
        for dof in restrained_sorted:
            node = model.nodes[dof // 3]
            component = ("ux", "uz", "ry")[dof % 3]
            reaction_value = float(reaction_vector[dof])
            row: dict[str, object] | None = next(
                (
                    item
                    for item in support_reactions
                    if item["combination"] == combo.name and item["node_id"] == node.id
                ),
                None,
            )
            if row is None:
                row = {
                    "combination": combo.name,
                    "node_id": node.id,
                    "reaction_fx_kN": 0.0,
                    "reaction_fz_kN": 0.0,
                    "reaction_my_kNm": 0.0,
                }
                support_reactions.append(row)
            if component == "ux":
                row["reaction_fx_kN"] = reaction_value
            elif component == "uz":
                row["reaction_fz_kN"] = reaction_value
            else:
                row["reaction_my_kNm"] = reaction_value

        for element, transform, local_stiffness in element_cache:
            dofs = [
                node_index[element.node_i] * 3,
                node_index[element.node_i] * 3 + 1,
                node_index[element.node_i] * 3 + 2,
                node_index[element.node_j] * 3,
                node_index[element.node_j] * 3 + 1,
                node_index[element.node_j] * 3 + 2,
            ]
            local_displacements = transform @ displacement_vector[dofs]
            local_forces = local_stiffness @ local_displacements
            member_end_forces.append(
                {
                    "combination": combo.name,
                    "member_id": element.id,
                    "member_kind": element.kind,
                    "node_i": element.node_i,
                    "node_j": element.node_j,
                    "N_i_kN": float(local_forces[0]),
                    "V_i_kN": float(local_forces[1]),
                    "M_i_kNm": float(local_forces[2]),
                    "N_j_kN": float(local_forces[3]),
                    "V_j_kN": float(local_forces[4]),
                    "M_j_kNm": float(local_forces[5]),
                }
            )

    return GlobalFrameAnalysisResult(
        supported=True,
        solved=True,
        failed=False,
        warnings=warnings,
        nodes=[{"id": node.id, "x_m": node.x_m, "z_m": node.z_m} for node in model.nodes],
        members=[
            {
                "id": element.id,
                "node_i": element.node_i,
                "node_j": element.node_j,
                "kind": element.kind,
            }
            for element in model.elements
        ],
        supports=[
            {
                "node_id": support.node_id,
                "ux": support.ux,
                "uz": support.uz,
                "ry": support.ry,
            }
            for support in model.supports
        ],
        releases=[],
        reactions=support_reactions,
        displacements=nodal_displacements,
        member_end_forces=member_end_forces,
    )
