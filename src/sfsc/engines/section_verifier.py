"""Steel section verification helpers."""

from __future__ import annotations

import logging
import math

from ..catalogs.steel_grade_catalog import get_grade_spec
from ..catalogs.steel_section_catalog import list_sections
from ..enums import CheckerStatus, SectionFamily, SteelGrade, StructuralCode
from ..models import LoadCombination, SectionVerificationResult, SteelSection
from ..section_orientation import get_local_section_axis_properties

logger = logging.getLogger("sfsc.section_verifier")

MAX_UTILIZATION = 0.90


def _as_float(value: object) -> float:
    if not isinstance(value, int | float):
        raise TypeError(f"Expected numeric value, got {type(value).__name__}")
    return float(value)


def _status_for_ratio(ratio: float) -> CheckerStatus:
    if ratio > 1.0:
        return CheckerStatus.FAIL
    if ratio > MAX_UTILIZATION:
        return CheckerStatus.MARGINAL
    return CheckerStatus.PASS


def verify_section(
    section: SteelSection,
    combination: LoadCombination,
    code: StructuralCode,
    steel_grade: SteelGrade,
    buckling_length_y_mm: float,
    buckling_length_z_mm: float,
    orientation_deg: float = 0.0,
    *,
    include_ltb: bool = True,
    include_biaxial: bool = True,
) -> SectionVerificationResult:
    del code
    spec = get_grade_spec(steel_grade)
    fy_mpa = spec.fy_mpa
    e_mpa = spec.E_mpa
    gamma_m0 = spec.gamma_M0
    gamma_m1 = spec.gamma_M1

    checks: dict[str, float] = {}
    warnings: list[str] = []
    assumptions = ["A-STR-001", "A-STR-002", "A-STR-003", "A-MEMBER-001"]
    clauses: list[str] = []
    details: dict[str, float] = {
        "fy_MPa": fy_mpa,
        "gamma_M0": gamma_m0,
        "gamma_M1": gamma_m1,
    }
    local_props = get_local_section_axis_properties(section, orientation_deg)
    details["section_orientation_deg"] = local_props.orientation_deg

    hw_mm = section.h_mm - 2.0 * section.tf_mm
    av_mm2 = hw_mm * section.tw_mm
    vpl_rd_kN = (av_mm2 * fy_mpa / math.sqrt(3.0)) / (gamma_m0 * 1000.0)
    v_ed_kN = max(abs(combination.V_z_kN), abs(combination.V_y_kN))
    eta_v = v_ed_kN / vpl_rd_kN if vpl_rd_kN > 0 else 0.0
    checks["shear"] = eta_v
    details.update({"Av_mm2": av_mm2, "Vpl_Rd_kN": vpl_rd_kN, "V_Ed_kN": v_ed_kN})
    clauses.append("EN 1993-1-1 cl. 6.2.6")

    rho_shear = 0.0
    if vpl_rd_kN > 0 and v_ed_kN > 0.5 * vpl_rd_kN:
        rho_shear = (2.0 * v_ed_kN / vpl_rd_kN - 1.0) ** 2
        warnings.append(
            "Shear reduction applied to bending resistance because V_Ed exceeds 0.5*Vpl,Rd."
        )

    fy_eff = fy_mpa * (1.0 - rho_shear)
    mc_y_rd_kNm = (local_props.local_wy_pl_mm3 * fy_eff) / (gamma_m0 * 1e6)
    m_y_ed_kNm = abs(combination.M_y_kNm)
    eta_my = m_y_ed_kNm / mc_y_rd_kNm if mc_y_rd_kNm > 0 else 0.0
    checks["bending_y"] = eta_my
    details.update({"fy_eff_MPa": fy_eff, "Mc_y_Rd_kNm": mc_y_rd_kNm, "M_y_Ed_kNm": m_y_ed_kNm})
    clauses.append("EN 1993-1-1 cl. 6.2.5")

    m_z_ed_kNm = abs(combination.M_z_kNm)
    eta_mz = 0.0
    if include_biaxial and m_z_ed_kNm > 0:
        mc_z_rd_kNm = (local_props.local_wz_pl_mm3 * fy_eff) / (gamma_m0 * 1e6)
        eta_mz = m_z_ed_kNm / mc_z_rd_kNm if mc_z_rd_kNm > 0 else 99.0
        checks["bending_z"] = eta_mz
        details.update({"Mc_z_Rd_kNm": mc_z_rd_kNm, "M_z_Ed_kNm": m_z_ed_kNm})
        clauses.append("EN 1993-1-1 cl. 6.2.9")
        if m_y_ed_kNm > 0:
            checks["bending_biaxial"] = eta_my + eta_mz

    if include_ltb and m_y_ed_kNm > 0 and buckling_length_y_mm > 0:
        lcr_mm = buckling_length_y_mm
        i_z_mm4 = local_props.local_iz_mm4
        h_eff_mm = section.h_mm - section.tf_mm
        i_w_mm6 = i_z_mm4 * (h_eff_mm**2) / 4.0
        i_t_mm4 = (
            2.0 * section.b_mm * section.tf_mm**3
            + (section.h_mm - 2.0 * section.tf_mm) * section.tw_mm**3
        ) / 3.0
        g_mpa = spec.G_mpa
        mcr_nmm = (math.pi / lcr_mm) * math.sqrt(
            e_mpa * i_z_mm4 * g_mpa * i_t_mm4
            + (math.pi * e_mpa / lcr_mm) ** 2 * i_z_mm4 * i_w_mm6
        )
        w_pl_y_mm3 = local_props.local_wy_pl_mm3
        lambda_lt = math.sqrt(w_pl_y_mm3 * fy_mpa / mcr_nmm) if mcr_nmm > 0 else 2.0
        alpha_lt = 0.34
        lambda_lt_0 = 0.4
        beta_lt = 0.75
        if lambda_lt <= lambda_lt_0:
            chi_lt = 1.0
        else:
            phi_lt = 0.5 * (
                1.0 + alpha_lt * (lambda_lt - lambda_lt_0) + beta_lt * lambda_lt**2
            )
            chi_lt = min(
                1.0,
                1.0 / (phi_lt + math.sqrt(phi_lt**2 - beta_lt * lambda_lt**2)),
            )
        mb_rd_kNm = chi_lt * w_pl_y_mm3 * fy_mpa / (gamma_m1 * 1e6)
        eta_ltb = m_y_ed_kNm / mb_rd_kNm if mb_rd_kNm > 0 else 0.0
        checks["ltb"] = eta_ltb
        details.update(
            {
                "Lcr_LTB_mm": lcr_mm,
                "Mcr_kNm": mcr_nmm / 1e6,
                "lambda_LT": lambda_lt,
                "chi_LT": chi_lt,
                "Mb_Rd_kNm": mb_rd_kNm,
            }
        )
        clauses.append("EN 1993-1-1 cl. 6.3.2")

    eta_n = 0.0
    if abs(combination.N_kN) > 0.01:
        nc_rd_kN = section.A_mm2 * fy_mpa / (gamma_m0 * 1000.0)
        eta_n = abs(combination.N_kN) / nc_rd_kN if nc_rd_kN > 0 else 0.0
        axial_key = "axial_tension" if combination.N_kN >= 0 else "axial_compression"
        checks[axial_key] = eta_n
        details.update({"Nc_Rd_kN": nc_rd_kN, "N_Ed_kN": abs(combination.N_kN)})
        clauses.append("EN 1993-1-1 cl. 6.2.4")

        if combination.N_kN < 0 and buckling_length_z_mm > 0:
            lambda_z = (buckling_length_z_mm / local_props.local_iz_radius_mm) * math.sqrt(
                fy_mpa / (math.pi**2 * e_mpa)
            )
            alpha_z = 0.49
            phi_z = 0.5 * (1.0 + alpha_z * (lambda_z - 0.2) + lambda_z**2)
            chi_z = min(1.0, 1.0 / (phi_z + math.sqrt(phi_z**2 - lambda_z**2)))
            nb_rd_kN = chi_z * section.A_mm2 * fy_mpa / (gamma_m1 * 1000.0)
            eta_buck = abs(combination.N_kN) / nb_rd_kN if nb_rd_kN > 0 else 0.0
            checks["buckling_z"] = eta_buck
            details.update({"lambda_z": lambda_z, "chi_z": chi_z, "Nb_Rd_kN": nb_rd_kN})
            clauses.append("EN 1993-1-1 cl. 6.3.1")

        interaction = eta_n + eta_my + eta_mz
        if interaction > 0:
            checks["axial_bending_interaction"] = interaction
            clauses.append("EN 1993-1-1 cl. 6.2.9 simplified")

    if not checks:
        checks["no_load"] = 0.0

    max_check = max(checks, key=lambda key: checks[key])
    max_ratio = checks[max_check]
    return SectionVerificationResult(
        section=section,
        utilization_ratio=round(max_ratio, 4),
        utilization_by_check={key: round(value, 4) for key, value in checks.items()},
        governing_check=max_check,
        status=_status_for_ratio(max_ratio),
        code_clause=" | ".join(dict.fromkeys(clauses)),
        warnings=warnings,
        assumptions_used=assumptions,
        calculation_details={key: round(value, 4) for key, value in details.items()},
    )


def _uls_combinations(combinations: list[LoadCombination]) -> list[LoadCombination]:
    uls = [combo for combo in combinations if combo.name.upper().startswith("ULS")]
    return uls or list(combinations)


def verify_section_envelope(
    section: SteelSection,
    combinations: list[LoadCombination],
    code: StructuralCode,
    steel_grade: SteelGrade,
    buckling_length_y_mm: float,
    buckling_length_z_mm: float,
    orientation_deg: float = 0.0,
    *,
    include_ltb: bool = True,
    include_biaxial: bool = True,
) -> SectionVerificationResult:
    results: list[tuple[LoadCombination, SectionVerificationResult]] = [
        (
            combo,
            verify_section(
                section,
                combo,
                code,
                steel_grade,
                buckling_length_y_mm,
                buckling_length_z_mm,
                orientation_deg,
                include_ltb=include_ltb,
                include_biaxial=include_biaxial,
            ),
        )
        for combo in _uls_combinations(combinations)
    ]
    merged_checks: dict[str, float] = {}
    warnings: list[str] = []
    clauses: list[str] = []
    for _, result in results:
        for key, value in result.utilization_by_check.items():
            merged_checks[key] = max(merged_checks.get(key, 0.0), value)
        warnings.extend(item for item in result.warnings if item not in warnings)
        clauses.extend(cl for cl in result.code_clause.split(" | ") if cl and cl not in clauses)

    governing_combo, governing_result = max(results, key=lambda item: item[1].utilization_ratio)
    return SectionVerificationResult(
        section=section,
        utilization_ratio=governing_result.utilization_ratio,
        utilization_by_check={key: round(value, 4) for key, value in merged_checks.items()},
        governing_check=governing_result.governing_check,
        governing_combination=governing_combo.name,
        status=_status_for_ratio(governing_result.utilization_ratio),
        code_clause=" | ".join(clauses),
        warnings=warnings,
        assumptions_used=governing_result.assumptions_used,
        calculation_details=governing_result.calculation_details,
    )


def find_passing_sections(
    combinations: list[LoadCombination],
    code: StructuralCode,
    steel_grade: SteelGrade,
    preferred_families: list[SectionFamily],
    buckling_length_y_mm: float,
    buckling_length_z_mm: float,
    max_utilization: float = 1.0,
    orientation_deg: float = 0.0,
    *,
    include_ltb: bool = True,
    include_biaxial: bool = True,
) -> list[SectionVerificationResult]:
    candidates: list[SectionVerificationResult] = []
    seen: set[tuple[SectionFamily, str]] = set()
    for family in preferred_families:
        for section in list_sections(family):
            key = (section.family, section.designation)
            if key in seen:
                continue
            seen.add(key)
            result = verify_section_envelope(
                section,
                combinations,
                code,
                steel_grade,
                buckling_length_y_mm,
                buckling_length_z_mm,
                orientation_deg,
                include_ltb=include_ltb,
                include_biaxial=include_biaxial,
            )
            if result.utilization_ratio <= max_utilization:
                candidates.append(result)
    return sorted(
        candidates,
        key=lambda result: (
            result.section.weight_kgm,
            result.section.family.value,
            result.section.designation,
        ),
    )


def auto_select_section(
    combinations: list[LoadCombination],
    code: StructuralCode,
    steel_grade: SteelGrade,
    preferred_families: list[SectionFamily],
    buckling_length_y_mm: float,
    buckling_length_z_mm: float,
    max_utilization: float = MAX_UTILIZATION,
    orientation_deg: float = 0.0,
    *,
    include_ltb: bool = True,
    include_biaxial: bool = True,
) -> tuple[SteelSection, SectionVerificationResult]:
    from ..exceptions import OutOfScopeError

    for family in preferred_families:
        for section in list_sections(family):
            result = verify_section_envelope(
                section,
                combinations,
                code,
                steel_grade,
                buckling_length_y_mm,
                buckling_length_z_mm,
                orientation_deg,
                include_ltb=include_ltb,
                include_biaxial=include_biaxial,
            )
            if result.utilization_ratio <= max_utilization:
                logger.info(
                    "Selected: %s eta=%.3f check=%s",
                    section.designation,
                    result.utilization_ratio,
                    result.governing_check,
                )
                return section, result

    raise OutOfScopeError(
        "Nenhum perfil no catálogo satisfaz as verificações EC3. "
        "Considere aço de maior grau ou perfil de catálogo externo.",
        parameter="utilization_ratio",
        limit=max_utilization,
    )


def _member_length_mm_map(
    solver_nodes: list[dict[str, object]],
    solver_members: list[dict[str, object]],
) -> dict[str, float]:
    node_map = {
        str(node["id"]): (_as_float(node["x_m"]), _as_float(node["z_m"]))
        for node in solver_nodes
    }
    lengths: dict[str, float] = {}
    for member in solver_members:
        node_i = node_map[str(member["node_i"])]
        node_j = node_map[str(member["node_j"])]
        lengths[str(member["id"])] = math.hypot(node_j[0] - node_i[0], node_j[1] - node_i[1]) * 1000.0
    return lengths


def _solver_row_to_load_combination(row: dict[str, object]) -> LoadCombination:
    n_i = _as_float(row["N_i_kN"])
    n_j = _as_float(row["N_j_kN"])
    axial_force_kN = 0.5 * (n_j - n_i)
    return LoadCombination(
        name=str(row["combination"]),
        N_kN=axial_force_kN,
        V_z_kN=max(abs(_as_float(row["V_i_kN"])), abs(_as_float(row["V_j_kN"]))),
        M_y_kNm=max(abs(_as_float(row["M_i_kNm"])), abs(_as_float(row["M_j_kNm"]))),
        member_level=True,
        description=f"Solver member force recovery for {row['member_id']}",
    )


def _governing_axis(check_name: str) -> str | None:
    if check_name.endswith("_y") or ".bending_y" in check_name or "ltb" in check_name:
        return "y"
    if check_name.endswith("_z") or ".bending_z" in check_name:
        return "z"
    return None


def _buckling_length_for_check(
    check_name: str,
    buckling_y_mm: float,
    buckling_z_mm: float,
) -> float:
    axis = _governing_axis(check_name)
    if axis == "z":
        return buckling_z_mm
    return buckling_y_mm


def verify_solver_member_envelope(
    section: SteelSection,
    solver_nodes: list[dict[str, object]],
    solver_members: list[dict[str, object]],
    solver_member_end_forces: list[dict[str, object]],
    code: StructuralCode,
    steel_grade: SteelGrade,
    orientation_deg: float = 0.0,
    buckling_length_overrides_mm: dict[str, tuple[float, float]] | None = None,
    *,
    include_ltb: bool = True,
) -> tuple[SectionVerificationResult, list[dict[str, object]]]:
    lengths_mm = _member_length_mm_map(solver_nodes, solver_members)
    member_meta = {str(member["id"]): member for member in solver_members}
    member_rows: list[dict[str, object]] = []
    member_results: list[tuple[str, SectionVerificationResult]] = []

    for member_id, member in member_meta.items():
        force_rows = [
            row
            for row in solver_member_end_forces
            if str(row["member_id"]) == member_id and str(row["combination"]).upper().startswith("ULS")
        ]
        if not force_rows:
            continue
        member_kind = str(member["kind"])
        buckling_y_mm, buckling_z_mm = (
            buckling_length_overrides_mm.get(member_id, (lengths_mm.get(member_id, 0.0), lengths_mm.get(member_id, 0.0)))
            if buckling_length_overrides_mm is not None
            else (lengths_mm.get(member_id, 0.0), lengths_mm.get(member_id, 0.0))
        )
        combos = [_solver_row_to_load_combination(row) for row in force_rows]
        result = verify_section_envelope(
            section,
            combos,
            code,
            steel_grade,
            buckling_y_mm,
            buckling_z_mm,
            orientation_deg,
            include_ltb=include_ltb and member_kind == "frame",
            include_biaxial=False,
        )
        member_results.append((member_id, result))
        governing_combo = next(combo for combo in combos if combo.name == result.governing_combination)
        member_rows.append(
            {
                "member_id": member_id,
                "member_kind": member_kind,
                "status": result.status.value,
                "utilization_ratio": result.utilization_ratio,
                "governing_check": result.governing_check,
                "governing_axis": _governing_axis(result.governing_check),
                "governing_combination": result.governing_combination,
                "axial_force_kN": round(governing_combo.N_kN, 4),
                "shear_force_kN": round(governing_combo.V_z_kN, 4),
                "bending_moment_kNm": round(governing_combo.M_y_kNm, 4),
                "buckling_length_mm": round(
                    _buckling_length_for_check(
                        result.governing_check,
                        buckling_y_mm,
                        buckling_z_mm,
                    ),
                    3,
                ),
                "section_designation": section.designation,
                "steel_grade": steel_grade.value,
                "code_clause": result.code_clause,
                "warnings": list(result.warnings),
            }
        )

    if not member_results:
        raise ValueError("No ULS solver member results available for verification.")

    governing_member_id, governing_result = max(
        member_results,
        key=lambda item: item[1].utilization_ratio,
    )
    merged_checks: dict[str, float] = {}
    warnings: list[str] = []
    clauses: list[str] = []
    single_member = len(member_results) == 1
    for member_id, result in member_results:
        for check_name, ratio in result.utilization_by_check.items():
            merged_key = check_name if single_member else f"{member_id}.{check_name}"
            merged_checks[merged_key] = ratio
        warnings.extend(item for item in result.warnings if item not in warnings)
        clauses.extend(cl for cl in result.code_clause.split(" | ") if cl and cl not in clauses)

    aggregate = SectionVerificationResult(
        section=section,
        utilization_ratio=governing_result.utilization_ratio,
        utilization_by_check={key: round(value, 4) for key, value in merged_checks.items()},
        governing_check=(
            governing_result.governing_check
            if single_member
            else f"{governing_member_id}.{governing_result.governing_check}"
        ),
        governing_combination=governing_result.governing_combination,
        status=_status_for_ratio(governing_result.utilization_ratio),
        code_clause=" | ".join(clauses),
        warnings=warnings,
        assumptions_used=governing_result.assumptions_used,
        calculation_details=dict(governing_result.calculation_details),
    )
    return aggregate, sorted(
        member_rows,
        key=lambda row: _as_float(row["utilization_ratio"]),
        reverse=True,
    )
