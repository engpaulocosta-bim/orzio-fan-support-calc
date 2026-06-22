"""Phase 05 explicit connection and fixation checks based on solver reactions."""

from __future__ import annotations

import math

from ..catalogs.steel_grade_catalog import get_grade_spec
from ..enums import BoltClass, CheckerStatus, SupportFixationMedium
from ..models import FanSupportInput, LoadCombination, SteelSection
from .steel_fixation import calculate_steel_fixation

_FCK: dict[str, float] = {
    "C20/25": 20.0,
    "C25/30": 25.0,
    "C30/37": 30.0,
    "C35/45": 35.0,
    "C40/50": 40.0,
}
_FUB: dict[str, float] = {
    BoltClass.C4_6.value: 400.0,
    BoltClass.C5_6.value: 500.0,
    BoltClass.C8_8.value: 800.0,
    BoltClass.C10_9.value: 1000.0,
}
_GAMMA_M2 = 1.25


def _as_float(value: object) -> float:
    assert isinstance(value, int | float)
    return float(value)


def _status_for_ratio(ratio: float) -> str:
    if ratio > 1.0:
        return "failed"
    return "verified"


def _solver_reaction_rows(solver_reactions: list[dict[str, object]]) -> list[dict[str, object]]:
    return [row for row in solver_reactions if str(row["combination"]).upper().startswith("ULS")]


def _governing_reaction_key(row: dict[str, object]) -> float:
    return (
        abs(_as_float(row["reaction_fz_kN"]))
        + abs(_as_float(row["reaction_fx_kN"]))
        + abs(_as_float(row["reaction_my_kNm"])) * 10.0
    )


def _bolt_area_mm2(diameter_mm: float) -> float:
    return 0.78 * math.pi * (diameter_mm / 2.0) ** 2


def _bolt_capacities_kN(diameter_mm: float, bolt_class: str) -> tuple[float, float]:
    fub = _FUB.get(bolt_class, 800.0)
    area_mm2 = _bolt_area_mm2(diameter_mm)
    tensile_kN = 0.9 * fub * area_mm2 / (_GAMMA_M2 * 1000.0)
    shear_kN = 0.6 * fub * area_mm2 / (_GAMMA_M2 * 1000.0)
    return tensile_kN, shear_kN


def _base_row(
    *,
    support_id: str,
    check_type: str,
    status: str,
    governing_combination: str,
    reaction_row: dict[str, object],
    utilization: float | None,
    warnings: list[str],
    missing_inputs: list[str],
    assumptions: list[str],
    code_clause: str,
) -> dict[str, object]:
    return {
        "support_id": support_id,
        "type": check_type,
        "status": status,
        "utilization_ratio": round(utilization, 4) if utilization is not None else None,
        "governing_combination": governing_combination,
        "reaction_fx_kN": round(_as_float(reaction_row["reaction_fx_kN"]), 4),
        "reaction_fz_kN": round(_as_float(reaction_row["reaction_fz_kN"]), 4),
        "reaction_my_kNm": round(_as_float(reaction_row["reaction_my_kNm"]), 4),
        "warnings": warnings,
        "missing_inputs": missing_inputs,
        "assumptions": assumptions,
        "code_clause": code_clause,
    }


def _not_verified_row(
    *,
    support_id: str,
    check_type: str,
    governing_combination: str,
    reaction_row: dict[str, object],
    missing_inputs: list[str],
    warnings: list[str],
) -> dict[str, object]:
    return _base_row(
        support_id=support_id,
        check_type=check_type,
        status="not_verified",
        governing_combination=governing_combination,
        reaction_row=reaction_row,
        utilization=None,
        warnings=warnings,
        missing_inputs=missing_inputs,
        assumptions=[],
        code_clause="",
    )


def _check_base_plate(
    inp: FanSupportInput,
    support_id: str,
    reaction_row: dict[str, object],
    section: SteelSection | None,
) -> dict[str, object]:
    plate = inp.base_plate_input
    missing_inputs: list[str] = []
    if plate is None or plate.length_mm is None:
        missing_inputs.append("base_plate_input.length_mm")
    if plate is None or plate.width_mm is None:
        missing_inputs.append("base_plate_input.width_mm")
    if plate is None or plate.thickness_mm is None:
        missing_inputs.append("base_plate_input.thickness_mm")
    if section is None:
        missing_inputs.append("recommended_section")
    if missing_inputs:
        return _not_verified_row(
            support_id=support_id,
            check_type="base_plate",
            governing_combination=str(reaction_row["combination"]),
            reaction_row=reaction_row,
            missing_inputs=missing_inputs,
            warnings=[
                "Base plate verification needs explicit plate geometry and a selected section."
            ],
        )

    assert plate is not None
    assert plate.length_mm is not None
    assert plate.width_mm is not None
    assert plate.thickness_mm is not None
    assert section is not None

    spec = get_grade_spec(inp.steel_grade)
    fck = _FCK.get(inp.concrete_grade, 0.0)
    if fck <= 0.0:
        return _not_verified_row(
            support_id=support_id,
            check_type="base_plate",
            governing_combination=str(reaction_row["combination"]),
            reaction_row=reaction_row,
            missing_inputs=["concrete_grade"],
            warnings=["Concrete grade is required for base plate bearing verification."],
        )

    axial_kN = abs(_as_float(reaction_row["reaction_fz_kN"]))
    area_mm2 = plate.length_mm * plate.width_mm
    bearing_mpa = (axial_kN * 1000.0) / area_mm2 if area_mm2 > 0 else 0.0
    fcd = fck / 1.5
    bearing_rd_mpa = 0.67 * fcd
    eta_bearing = bearing_mpa / bearing_rd_mpa if bearing_rd_mpa > 0 else 99.0

    projection_mm = max((plate.length_mm - section.h_mm) / 2.0, 10.0)
    m_plate_nmm_mm = bearing_mpa * projection_mm**2 / 2.0
    bending_rd = spec.fy_mpa * plate.thickness_mm**2 / 6.0
    eta_bending = m_plate_nmm_mm / bending_rd if bending_rd > 0 else 99.0
    utilization = max(eta_bearing, eta_bending)

    return _base_row(
        support_id=support_id,
        check_type="base_plate",
        status=_status_for_ratio(utilization),
        governing_combination=str(reaction_row["combination"]),
        reaction_row=reaction_row,
        utilization=utilization,
        warnings=[],
        missing_inputs=[],
        assumptions=[
            "Explicit plate dimensions provided by user.",
            "Compression-dominant base plate check.",
        ],
        code_clause="EN 1993-1-8 cl. 6.2.5 simplified",
    )


def _check_base_plate_transfer(
    inp: FanSupportInput,
    support_id: str,
    reaction_row: dict[str, object],
) -> dict[str, object]:
    plate = inp.base_plate_input
    missing_inputs: list[str] = []
    if plate is None:
        missing_inputs.extend(
            [
                "base_plate_input.weld_throat_mm or base_plate_input.bolt_diameter_mm",
                "base_plate_input.n_bolts",
            ]
        )
        return _not_verified_row(
            support_id=support_id,
            check_type="base_plate_transfer",
            governing_combination=str(reaction_row["combination"]),
            reaction_row=reaction_row,
            missing_inputs=missing_inputs,
            warnings=["Reaction transfer must be defined by explicit weld size or bolt data."],
        )

    shear_kN = abs(_as_float(reaction_row["reaction_fx_kN"]))
    axial_kN = abs(_as_float(reaction_row["reaction_fz_kN"]))
    transfer_kN = shear_kN + 0.3 * axial_kN
    if transfer_kN <= 0.0:
        return _base_row(
            support_id=support_id,
            check_type="base_plate_transfer",
            status="verified",
            governing_combination=str(reaction_row["combination"]),
            reaction_row=reaction_row,
            utilization=0.0,
            warnings=[],
            missing_inputs=[],
            assumptions=["No shear transfer demand in governing reaction."],
            code_clause="EN 1993-1-8 simplified",
        )

    if plate.weld_throat_mm is not None:
        length_mm = 2.0 * ((plate.length_mm or 0.0) + (plate.width_mm or 0.0))
        if length_mm <= 0.0:
            return _not_verified_row(
                support_id=support_id,
                check_type="base_plate_transfer",
                governing_combination=str(reaction_row["combination"]),
                reaction_row=reaction_row,
                missing_inputs=["base_plate_input.length_mm", "base_plate_input.width_mm"],
                warnings=["Plate plan dimensions are required to check weld transfer."],
            )
        fu = get_grade_spec(inp.steel_grade).fu_mpa
        f_vwd = fu / (math.sqrt(3.0) * 0.90 * 1.25)
        capacity_kN = plate.weld_throat_mm * length_mm * f_vwd / 1000.0
        utilization = transfer_kN / capacity_kN if capacity_kN > 0 else 99.0
        return _base_row(
            support_id=support_id,
            check_type="base_plate_transfer",
            status=_status_for_ratio(utilization),
            governing_combination=str(reaction_row["combination"]),
            reaction_row=reaction_row,
            utilization=utilization,
            warnings=[],
            missing_inputs=[],
            assumptions=["Reaction transfer checked by explicit weld throat."],
            code_clause="EN 1993-1-8 cl. 4 simplified",
        )

    if plate.bolt_diameter_mm is None:
        missing_inputs.append("base_plate_input.bolt_diameter_mm")
    if plate.n_bolts is None:
        missing_inputs.append("base_plate_input.n_bolts")
    if missing_inputs:
        return _not_verified_row(
            support_id=support_id,
            check_type="base_plate_transfer",
            governing_combination=str(reaction_row["combination"]),
            reaction_row=reaction_row,
            missing_inputs=missing_inputs,
            warnings=["Bolt transfer check needs explicit bolt diameter and count."],
        )

    assert plate.bolt_diameter_mm is not None
    assert plate.n_bolts is not None
    _, shear_capacity_per_bolt = _bolt_capacities_kN(
        plate.bolt_diameter_mm,
        plate.bolt_class.value,
    )
    total_capacity = plate.n_bolts * shear_capacity_per_bolt
    utilization = transfer_kN / total_capacity if total_capacity > 0 else 99.0
    return _base_row(
        support_id=support_id,
        check_type="base_plate_transfer",
        status=_status_for_ratio(utilization),
        governing_combination=str(reaction_row["combination"]),
        reaction_row=reaction_row,
        utilization=utilization,
        warnings=[],
        missing_inputs=[],
        assumptions=["Reaction transfer checked by explicit bolt group."],
        code_clause="EN 1993-1-8 cl. 3 simplified",
    )


def _check_anchor_group(
    inp: FanSupportInput,
    support_id: str,
    reaction_row: dict[str, object],
) -> dict[str, object]:
    layout = inp.anchor_layout
    missing_inputs: list[str] = []
    if layout is None or layout.n_anchors is None:
        missing_inputs.append("anchor_layout.n_anchors")
    if layout is None or layout.anchor_diameter_mm is None:
        missing_inputs.append("anchor_layout.anchor_diameter_mm")
    if not inp.concrete_grade:
        missing_inputs.append("concrete_grade")
    if abs(_as_float(reaction_row["reaction_my_kNm"])) > 0.0:
        if layout is None or layout.spacing_x_mm is None:
            missing_inputs.append("anchor_layout.spacing_x_mm")
    if missing_inputs:
        return _not_verified_row(
            support_id=support_id,
            check_type="anchor_group",
            governing_combination=str(reaction_row["combination"]),
            reaction_row=reaction_row,
            missing_inputs=missing_inputs,
            warnings=["Anchor verification needs explicit anchor layout and concrete grade."],
        )

    assert layout is not None
    assert layout.n_anchors is not None
    assert layout.anchor_diameter_mm is not None

    tension_capacity_per_anchor, shear_capacity_per_anchor = _bolt_capacities_kN(
        layout.anchor_diameter_mm,
        BoltClass.C8_8.value,
    )
    n_tension = max(1, layout.n_anchors // 2)
    lever_m = (layout.spacing_x_mm or 0.0) / 1000.0
    axial_tension_kN = (
        abs(_as_float(reaction_row["reaction_my_kNm"])) / (lever_m * n_tension)
        if lever_m > 0
        else 0.0
    )
    shear_per_anchor_kN = abs(_as_float(reaction_row["reaction_fx_kN"])) / layout.n_anchors
    eta_tension = (
        axial_tension_kN / tension_capacity_per_anchor if tension_capacity_per_anchor > 0 else 99.0
    )
    eta_shear = (
        shear_per_anchor_kN / shear_capacity_per_anchor if shear_capacity_per_anchor > 0 else 99.0
    )
    eta_interaction = eta_tension**1.5 + eta_shear**1.5

    fck = _FCK.get(inp.concrete_grade, 0.0)
    hef_mm = max(8.0 * layout.anchor_diameter_mm, 100.0)
    fbd_mpa = 0.7 * 2.25 * (fck / 25.0) ** 0.5 if fck > 0 else 0.0
    pullout_capacity_kN = (
        math.pi * layout.anchor_diameter_mm * hef_mm * fbd_mpa / 1000.0 if fbd_mpa > 0 else 0.0
    )
    eta_pullout = axial_tension_kN / pullout_capacity_kN if pullout_capacity_kN > 0 else 99.0

    edge_factor = 1.0
    if layout.edge_distance_x_mm is not None:
        edge_factor = min(edge_factor, layout.edge_distance_x_mm / max(1.5 * hef_mm, 1.0))
    if layout.edge_distance_y_mm is not None:
        edge_factor = min(edge_factor, layout.edge_distance_y_mm / max(1.5 * hef_mm, 1.0))
    spacing_factor = 1.0
    if layout.spacing_y_mm is not None:
        spacing_factor = min(
            spacing_factor,
            layout.spacing_y_mm / max(3.0 * hef_mm, 1.0),
        )
    reduced_pullout_capacity_kN = (
        pullout_capacity_kN * min(1.0, edge_factor) * min(1.0, spacing_factor)
    )
    eta_pullout = (
        axial_tension_kN / reduced_pullout_capacity_kN
        if reduced_pullout_capacity_kN > 0
        else eta_pullout
    )

    utilization = max(eta_tension, eta_shear, eta_interaction, eta_pullout)
    return _base_row(
        support_id=support_id,
        check_type="anchor_group",
        status=_status_for_ratio(utilization),
        governing_combination=str(reaction_row["combination"]),
        reaction_row=reaction_row,
        utilization=utilization,
        warnings=[],
        missing_inputs=[],
        assumptions=[
            "Simple anchor tension from overturning moment.",
            "hef = max(8d, 100 mm) simplified pull-out assumption.",
        ],
        code_clause="EN 1992-4 cl. 7.2 simplified",
    )


def build_phase05_connection_rows(
    inp: FanSupportInput,
    *,
    solver_engine: str,
    solver_failed: bool,
    solver_reactions: list[dict[str, object]],
    section: SteelSection | None,
) -> list[dict[str, object]]:
    if solver_engine != "global_frame" or solver_failed:
        return []

    reaction_rows = _solver_reaction_rows(solver_reactions)
    if not reaction_rows:
        return []

    governing_by_support: dict[str, dict[str, object]] = {}
    for row in reaction_rows:
        support_id = str(row["node_id"])
        current = governing_by_support.get(support_id)
        if current is None or _governing_reaction_key(row) > _governing_reaction_key(current):
            governing_by_support[support_id] = row

    checks: list[dict[str, object]] = []
    for support_id, reaction_row in governing_by_support.items():
        if inp.support_fixation_medium == SupportFixationMedium.CONCRETE:
            if inp.calculation_options.include_base_plate or inp.include_base_plate:
                checks.append(_check_base_plate(inp, support_id, reaction_row, section))
                checks.append(_check_base_plate_transfer(inp, support_id, reaction_row))
            if inp.calculation_options.include_anchors:
                checks.append(_check_anchor_group(inp, support_id, reaction_row))
        elif inp.support_fixation_medium == SupportFixationMedium.STEEL_STRUCTURE:
            steel_fix = inp.steel_fixation
            missing_inputs: list[str] = []
            if steel_fix is None:
                missing_inputs.append("steel_fixation")
            else:
                if steel_fix.bolt_diameter_mm is None and steel_fix.weld_size_mm is None:
                    missing_inputs.append(
                        "steel_fixation.bolt_diameter_mm or steel_fixation.weld_size_mm"
                    )
                if steel_fix.number_of_bolts is None and steel_fix.weld_size_mm is None:
                    missing_inputs.append("steel_fixation.number_of_bolts")
                if steel_fix.plate_thickness_mm is None:
                    missing_inputs.append("steel_fixation.plate_thickness_mm")
            if missing_inputs:
                checks.append(
                    _not_verified_row(
                        support_id=support_id,
                        check_type="steel_fixation",
                        governing_combination=str(reaction_row["combination"]),
                        reaction_row=reaction_row,
                        missing_inputs=missing_inputs,
                        warnings=["Steel fixation verification needs explicit fixation input."],
                    )
                )
            else:
                combination = LoadCombination(
                    name=str(reaction_row["combination"]),
                    V_y_kN=abs(_as_float(reaction_row["reaction_fx_kN"])),
                    V_z_kN=abs(_as_float(reaction_row["reaction_fz_kN"])),
                    M_y_kNm=abs(_as_float(reaction_row["reaction_my_kNm"])),
                    member_level=True,
                    description=f"Solver support reaction at {support_id}",
                )
                steel_result = calculate_steel_fixation(inp, combination, section=section)
                checks.append(
                    _base_row(
                        support_id=support_id,
                        check_type="steel_fixation",
                        status="failed"
                        if steel_result.status == CheckerStatus.FAIL
                        else "verified",
                        governing_combination=str(reaction_row["combination"]),
                        reaction_row=reaction_row,
                        utilization=steel_result.utilization_ratio,
                        warnings=list(steel_result.warnings),
                        missing_inputs=[],
                        assumptions=["Steel fixation check uses solver support reactions."],
                        code_clause=steel_result.code_clause,
                    )
                )

    return checks
