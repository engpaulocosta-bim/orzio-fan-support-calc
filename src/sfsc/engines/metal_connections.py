"""Simplified steel connection checks for support assemblies."""
from __future__ import annotations

import math

from ..catalogs.steel_grade_catalog import get_grade_spec
from ..enums import CantileverSubtype, CheckerStatus, StructuralCode, SupportType
from ..models import (
    FanSupportInput,
    LoadCombination,
    MetalConnectionResult,
    SteelSection,
)


def calculate_metal_connection(
    inp: FanSupportInput,
    section: SteelSection,
    combination: LoadCombination,
    code: StructuralCode,
) -> MetalConnectionResult:
    """Return a governing simplified steel-to-steel connection for the support."""
    warnings: list[str] = []
    spec = get_grade_spec(inp.steel_grade)

    connection_type = _connection_type(inp)
    plate_thickness_mm = _plate_thickness(inp, section)
    bolt_diameter_mm = _bolt_diameter(inp, combination)
    hole_diameter_mm = bolt_diameter_mm + 2.0
    n_bolts = _bolt_count(inp, combination)

    min_spacing_mm = 2.2 * hole_diameter_mm
    min_edge_mm = 1.2 * hole_diameter_mm
    provided_spacing_mm = max(min_spacing_mm, min(section.h_mm * 0.55, 140.0))
    provided_edge_mm = max(min_edge_mm, min(section.b_mm * 0.35, 70.0))
    spacing_ok = provided_spacing_mm >= min_spacing_mm
    edge_ok = provided_edge_mm >= min_edge_mm

    bolt_shear_capacity_kN = _bolt_shear_capacity(bolt_diameter_mm)
    bolt_tension_capacity_kN = _bolt_tension_capacity(bolt_diameter_mm)

    V_Ed_kN = max(abs(combination.V_z_kN), abs(combination.V_y_kN))
    lever_arm_m = max(section.h_mm, inp.installation_height_mm, 100.0) / 1000.0
    moment_tension_kN = abs(combination.M_y_kNm) / lever_arm_m if lever_arm_m > 0 else 0.0
    N_Ed_kN = max(0.0, abs(combination.N_kN)) + moment_tension_kN

    eta_shear = V_Ed_kN / (n_bolts * bolt_shear_capacity_kN)
    eta_tension = N_Ed_kN / (n_bolts * bolt_tension_capacity_kN)

    weld_length_mm = _weld_length(inp, section)
    weld_throat_mm = _weld_throat(inp, plate_thickness_mm, V_Ed_kN, weld_length_mm, spec.fu_mpa)
    weld_capacity_kN = _weld_capacity(weld_throat_mm, weld_length_mm, spec.fu_mpa, spec.gamma_M2)
    weld_utilization = (V_Ed_kN + 0.3 * N_Ed_kN) / weld_capacity_kN if weld_capacity_kN > 0 else 99.0

    stiffener_required = _needs_stiffener(inp, combination, section)
    stiffener_thickness_mm = max(8.0, plate_thickness_mm) if stiffener_required else 0.0
    cleat_angle = _cleat_angle(inp, section)
    diagonal_member = _diagonal_member(inp, section)

    if not spacing_ok:
        warnings.append("Espacamento dos parafusos perfil-perfil inferior ao minimo simplificado.")
    if not edge_ok:
        warnings.append("Bordo livre dos parafusos perfil-perfil inferior ao minimo simplificado.")
    if stiffener_required:
        warnings.append("Stiffeners recomendados no no principal devido a momento/concentracao de carga.")
    if weld_utilization > 1.0:
        warnings.append("Soldadura principal insuficiente no modelo simplificado.")

    utilization_ratio = max(
        eta_shear,
        eta_tension,
        weld_utilization,
        1.01 if not (spacing_ok and edge_ok) else 0.0,
    )
    if utilization_ratio > 1.0:
        status = CheckerStatus.FAIL
    elif utilization_ratio > 0.90:
        status = CheckerStatus.MARGINAL
    else:
        status = CheckerStatus.PASS

    return MetalConnectionResult(
        connection_type=connection_type,
        plate_thickness_mm=round(plate_thickness_mm, 1),
        bolt_diameter_mm=bolt_diameter_mm,
        bolt_hole_diameter_mm=round(hole_diameter_mm, 1),
        n_bolts=n_bolts,
        min_spacing_mm=round(min_spacing_mm, 1),
        provided_spacing_mm=round(provided_spacing_mm, 1),
        min_edge_distance_mm=round(min_edge_mm, 1),
        provided_edge_distance_mm=round(provided_edge_mm, 1),
        spacing_ok=spacing_ok,
        edge_distance_ok=edge_ok,
        bolt_shear_capacity_kN=round(bolt_shear_capacity_kN * n_bolts, 2),
        bolt_tension_capacity_kN=round(bolt_tension_capacity_kN * n_bolts, 2),
        utilization_bolt_shear=round(eta_shear, 4),
        utilization_bolt_tension=round(eta_tension, 4),
        weld_throat_mm=round(weld_throat_mm, 1),
        weld_length_mm=round(weld_length_mm, 0),
        weld_utilization=round(weld_utilization, 4),
        stiffener_required=stiffener_required,
        stiffener_thickness_mm=round(stiffener_thickness_mm, 1),
        cleat_angle=cleat_angle,
        diagonal_member=diagonal_member,
        utilization_ratio=round(utilization_ratio, 4),
        status=status,
        code_clause=_code_clause(code),
        warnings=warnings,
    )


def _connection_type(inp: FanSupportInput) -> str:
    if inp.support_type == SupportType.HANGER:
        return "Cleat aparafusado perfil-viga + olhais/varoes"
    if inp.support_type == SupportType.CANTILEVER_1:
        if inp.cantilever_subtype == CantileverSubtype.BRACKETED:
            return "Chapa de no + diagonal + soldadura de contorno"
        return "End plate de consola aparafusada/soldada"
    if inp.support_type == SupportType.CANTILEVER_2:
        return "Dupla consola com chapas laterais e parafusos perfil-perfil"
    if inp.support_type == SupportType.CANTILEVER_3:
        return "Ligacao de joelho de portico com stiffeners"
    if inp.support_type == SupportType.PEDESTAL:
        return "Chapas de ligacao patim-pe e cantoneiras de apoio"
    return "Mesa combinada com pendurais, cleats e diagonais locais"


def _plate_thickness(inp: FanSupportInput, section: SteelSection) -> float:
    base = max(8.0, section.tf_mm, 0.08 * section.h_mm)
    if inp.support_type in (SupportType.CANTILEVER_1, SupportType.CANTILEVER_3):
        base += 2.0
    return _round_plate(base)


def _bolt_diameter(inp: FanSupportInput, combination: LoadCombination) -> float:
    demand = max(abs(combination.V_z_kN), abs(combination.V_y_kN), abs(combination.N_kN))
    if inp.support_type in (SupportType.CANTILEVER_1, SupportType.CANTILEVER_3) or demand > 25.0:
        return 20.0
    return 16.0


def _bolt_count(inp: FanSupportInput, combination: LoadCombination) -> int:
    if inp.support_type in (SupportType.CANTILEVER_1, SupportType.CANTILEVER_3):
        return 6 if abs(combination.M_y_kNm) > 4.0 else 4
    if inp.support_type in (SupportType.PEDESTAL, SupportType.COMBINED):
        return 8
    return 4


def _weld_length(inp: FanSupportInput, section: SteelSection) -> float:
    if inp.support_type == SupportType.HANGER:
        return 2.0 * section.b_mm
    if inp.support_type == SupportType.PEDESTAL:
        return 4.0 * section.b_mm
    return 2.0 * (section.h_mm + section.b_mm)


def _weld_throat(
    inp: FanSupportInput,
    plate_thickness_mm: float,
    V_Ed_kN: float,
    weld_length_mm: float,
    fu_mpa: float,
) -> float:
    min_throat = 3.0
    beta_w = 0.90
    gamma_M2 = 1.25
    f_vwd = fu_mpa / (math.sqrt(3.0) * beta_w * gamma_M2)
    required = (V_Ed_kN * 1000.0) / (max(weld_length_mm, 1.0) * f_vwd)
    throat = max(min_throat, required * 1.25)
    if inp.support_type in (SupportType.CANTILEVER_1, SupportType.CANTILEVER_3):
        throat = max(throat, 4.0)
    return min(throat, 0.7 * plate_thickness_mm)


def _weld_capacity(a_mm: float, length_mm: float, fu_mpa: float, gamma_M2: float) -> float:
    beta_w = 0.90
    f_vwd = fu_mpa / (math.sqrt(3.0) * beta_w * gamma_M2)
    return a_mm * length_mm * f_vwd / 1000.0


def _needs_stiffener(inp: FanSupportInput, combination: LoadCombination, section: SteelSection) -> bool:
    if inp.support_type in (SupportType.CANTILEVER_1, SupportType.CANTILEVER_3):
        return abs(combination.M_y_kNm) > 0.5
    if inp.support_type in (SupportType.PEDESTAL, SupportType.COMBINED):
        return section.h_mm < inp.installation_height_mm / 4.0
    return False


def _cleat_angle(inp: FanSupportInput, section: SteelSection) -> str:
    leg = max(50, int(round(section.b_mm / 10.0) * 10))
    thickness = 6 if section.h_mm <= 160 else 8
    if inp.support_type in (SupportType.PEDESTAL, SupportType.HANGER, SupportType.COMBINED):
        return f"L{leg}x{leg}x{thickness}"
    return ""


def _diagonal_member(inp: FanSupportInput, section: SteelSection) -> str:
    if inp.support_type == SupportType.CANTILEVER_1 and inp.cantilever_subtype == CantileverSubtype.BRACKETED:
        return f"RHS{max(40, int(section.b_mm / 2))}x{max(40, int(section.b_mm / 2))}x4"
    if inp.support_type == SupportType.COMBINED:
        return f"RHS{max(40, int(section.b_mm / 2))}x{max(30, int(section.b_mm / 3))}x4"
    return ""


def _bolt_shear_capacity(d_mm: float, grade: str = "8.8") -> float:
    fub = {"8.8": 800.0, "10.9": 1000.0}.get(grade, 800.0)
    As_mm2 = 0.78 * math.pi * (d_mm / 2.0) ** 2
    return 0.6 * fub * As_mm2 / (1.25 * 1000.0)


def _bolt_tension_capacity(d_mm: float, grade: str = "8.8") -> float:
    fub = {"8.8": 800.0, "10.9": 1000.0}.get(grade, 800.0)
    As_mm2 = 0.78 * math.pi * (d_mm / 2.0) ** 2
    return 0.9 * fub * As_mm2 / (1.25 * 1000.0)


def _round_plate(value: float) -> float:
    for thickness in (8, 10, 12, 15, 16, 20, 25, 30):
        if thickness >= value:
            return float(thickness)
    return math.ceil(value / 5.0) * 5.0


def _code_clause(code: StructuralCode) -> str:
    if code.value.startswith("EN"):
        return "EN 1993-1-8 cl. 3, 4, 6 (simplificado)"
    if code == StructuralCode.NBR_8800:
        return "NBR 8800 ligacoes parafusadas/soldadas (simplificado)"
    return "NCh427 ligacoes metalicas (referencia simplificada)"
