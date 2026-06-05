"""Dimensionamento da chapa de assento (base plate) e parafusos."""
from __future__ import annotations
import math
from ..models import FanSupportInput, SteelSection, LoadCombination, BasePlateResult
from ..enums import SteelGrade, StructuralCode, CheckerStatus, FanConnectionType, AnchorageSubstrate
from ..catalogs.steel_grade_catalog import get_grade_spec

# Resistência do betão [MPa] — fck por designação
_FCK: dict[str, float] = {
    "C20/25": 20.0, "C25/30": 25.0, "C30/37": 30.0,
    "C35/45": 35.0, "C40/50": 40.0,
}


def calculate_base_plate(
    inp: FanSupportInput,
    section: SteelSection,
    combination: LoadCombination,
    code: StructuralCode,
    concrete_grade: str = "C25/30",
) -> BasePlateResult:
    """
    Dimensiona a chapa de assento (base plate).

    Método: EN 1993-1-8 cl. 6.2.5 (bearing pressure) +
            EN 1993-1-1 cl. 6.2.5 (bending plate)

    Outputs:
        - Dimensões L×B da chapa
        - Espessura t
        - Parafusos ventilador → chapa
        - Parafusos chapa → estrutura
        - Verificação da soldadura chapa → perfil
    """
    warnings: list[str] = []
    spec     = get_grade_spec(inp.steel_grade)
    fy_mpa   = spec.fy_mpa
    gamma_M0 = spec.gamma_M0

    is_concrete_anchor = inp.anchorage_substrate == AnchorageSubstrate.CONCRETE
    fck = _FCK.get(concrete_grade, 25.0)
    fcd = fck / 1.5   # resistência de cálculo betão [MPa]

    # Tensão de contacto admissível (bearing): f_jd = beta_j × kj × fcd
    beta_j = 0.67
    kj     = 1.0      # conservativo
    f_jd   = beta_j * kj * fcd if is_concrete_anchor else fy_mpa / gamma_M0   # MPa

    P_kN = abs(combination.V_z_kN)
    P_N  = P_kN * 1000.0

    # ── Dimensões mínimas da chapa ────────────────────────────────────────────
    # Área mínima necessária para distribuir carga no betão
    fan = inp.fan_units[0]
    A_min_mm2 = P_N / f_jd if f_jd > 0 else 1.0
    L_base = fan.footprint_length_mm + 2 * 50  # folga 50mm cada lado
    B_base = fan.footprint_width_mm  + 2 * 50

    # Aumentar se necessário para garantir f_jd
    while L_base * B_base < A_min_mm2:
        L_base += 25.0
        B_base += 25.0

    A_actual_mm2 = L_base * B_base
    sigma_bearing_mpa = P_N / A_actual_mm2  # tensão real de contacto

    # ── Espessura da chapa ────────────────────────────────────────────────────
    # Projecção da chapa fora do banzo do perfil: c = (L_base - h_section) / 2
    c_mm = (L_base - section.h_mm) / 2.0
    if c_mm < 10.0:
        c_mm = 10.0
        L_base = section.h_mm + 2 * c_mm

    # Momento na projecção: M = sigma_bearing × c² / 2
    M_plate_Nmm_mm = sigma_bearing_mpa * c_mm**2 / 2.0   # Nmm/mm de largura

    # Espessura necessária: t = sqrt(6 × M / fy)
    t_min_mm = math.sqrt(6.0 * M_plate_Nmm_mm / (fy_mpa / gamma_M0))
    t_min_mm = max(t_min_mm, 10.0)  # mínimo 10 mm
    # Arredondar para espessura comercial
    t_plate_mm = _round_plate_thickness(t_min_mm)

    # ── Parafusos ventilador → chapa ──────────────────────────────────────────
    # Carga por parafuso; assume 4 parafusos de montagem
    n_bolts_fan = 4
    # Capacidade de um parafuso M16 8.8 em corte: ~48 kN
    d_bolt_fan_mm = 16.0
    Fv_Rd_kN = _bolt_shear_capacity(d_bolt_fan_mm, grade="8.8")
    eta_fan   = (P_kN / n_bolts_fan) / Fv_Rd_kN

    # Mais parafusos se necessário
    while eta_fan > 0.90 and n_bolts_fan < 12:
        n_bolts_fan += 2
        eta_fan = (P_kN / n_bolts_fan) / Fv_Rd_kN

    # ── Parafusos chapa → estrutura metálica ──────────────────────────────────
    # (estrutura metálica = perfis do suporte)
    n_bolts_str = 4
    d_bolt_str_mm = 20.0
    hole_diameter_mm = d_bolt_str_mm + 2.0
    Fv_Rd_str_kN = _bolt_shear_capacity(d_bolt_str_mm, grade="8.8")
    eta_str = (P_kN / n_bolts_str) / Fv_Rd_str_kN

    while eta_str > 0.90 and n_bolts_str < 16:
        n_bolts_str += 2
        eta_str = (P_kN / n_bolts_str) / Fv_Rd_str_kN

    # ── Furação, espaçamentos mínimos e bordo livre ───────────────────────────
    # Regras geométricas simplificadas EN 1993-1-8: p_min = 2.2*d0, e_min = 1.2*d0.
    # Para ancoragens em betão usa-se ainda hef para reduzir a capacidade do cone.
    min_spacing_mm = 2.2 * hole_diameter_mm
    min_edge_distance_mm = 1.2 * hole_diameter_mm
    preferred_edge_mm = max(60.0, 3.0 * d_bolt_str_mm)
    edge_x_mm = min(preferred_edge_mm, max(min_edge_distance_mm, L_base / 3.0))
    edge_y_mm = min(preferred_edge_mm, max(min_edge_distance_mm, B_base / 3.0))
    spacing_x_mm = max(0.0, L_base - 2.0 * edge_x_mm)
    spacing_y_mm = max(0.0, B_base - 2.0 * edge_y_mm)
    spacing_ok = spacing_x_mm >= min_spacing_mm and spacing_y_mm >= min_spacing_mm
    edge_ok = edge_x_mm >= min_edge_distance_mm and edge_y_mm >= min_edge_distance_mm

    if not spacing_ok:
        warnings.append(
            "Furação da base plate com espaçamento inferior ao mínimo simplificado. "
            "Aumentar dimensões da chapa ou rever layout de ancoragens."
        )
    if not edge_ok:
        warnings.append(
            "Bordo livre da furação inferior ao mínimo simplificado. "
            "Aumentar chapa ou afastar ancoragens do bordo."
        )

    # ── Verificações adicionais de betão para o grupo de ancoragens ───────────
    hef_mm = max(8.0 * d_bolt_str_mm, 100.0)
    gamma_concrete = 1.5
    n_eff = max(1, n_bolts_str)
    N_Ed_kN = P_kN
    V_Ed_kN = abs(combination.V_y_kN)

    # Cone de betão: fórmula simplificada proporcional a sqrt(fck)*hef^1.5,
    # penalizada por bordo e espaçamento curtos.
    edge_factor = min(1.0, min(edge_x_mm, edge_y_mm) / (1.5 * hef_mm))
    spacing_factor = min(1.0, min(spacing_x_mm, spacing_y_mm) / (3.0 * hef_mm)) if n_eff > 1 else 1.0
    cone_single_kN = 7.2 * math.sqrt(fck) * (hef_mm ** 1.5) / 1000.0 / gamma_concrete
    concrete_cone_capacity_kN = n_eff * cone_single_kN * edge_factor * spacing_factor

    # Pull-out por aderência: perímetro * hef * fbd.
    fbd_mpa = 0.7 * 2.25 * (fck / 25.0) ** 0.5
    pullout_capacity_kN = n_eff * math.pi * d_bolt_str_mm * hef_mm * fbd_mpa / 1000.0 / gamma_concrete

    # Pry-out em corte, conservativamente relacionado com capacidade de cone.
    pryout_capacity_kN = 2.0 * concrete_cone_capacity_kN

    eta_cone = N_Ed_kN / concrete_cone_capacity_kN if concrete_cone_capacity_kN > 0 else 99.0
    eta_pullout = N_Ed_kN / pullout_capacity_kN if pullout_capacity_kN > 0 else 99.0
    eta_pryout = V_Ed_kN / pryout_capacity_kN if pryout_capacity_kN > 0 else 0.0

    if is_concrete_anchor and eta_cone > 1.0:
        warnings.append(
            f"Cone de betão insuficiente no modelo simplificado (η={eta_cone:.2f}). "
            "Rever embebimento, distância ao bordo e classe do betão."
        )
    if is_concrete_anchor and eta_pullout > 1.0:
        warnings.append(
            f"Arrancamento/pull-out insuficiente no modelo simplificado (η={eta_pullout:.2f}). "
            "Aumentar embebimento ou diâmetro das ancoragens."
        )
    if is_concrete_anchor and eta_pryout > 1.0:
        warnings.append(
            f"Pry-out por corte insuficiente no modelo simplificado (η={eta_pryout:.2f}). "
            "Rever grupo de ancoragens."
        )

    # ── Soldadura chapa → perfil ──────────────────────────────────────────────
    # Cordão filete em torno do banzo do perfil
    # Comprimento efectivo: 2 × (b_section + h_section)
    if not is_concrete_anchor:
        concrete_cone_capacity_kN = 0.0
        pullout_capacity_kN = 0.0
        pryout_capacity_kN = 0.0
        eta_cone = 0.0
        eta_pullout = 0.0
        eta_pryout = 0.0
        warnings.append(
            "Fixação em estrutura metálica: cone de betão, pull-out e pry-out "
            "não se aplicam. Confirmar espessura, bordo livre e rigidez do "
            "elemento metálico receptor."
        )

    L_weld_mm = 2.0 * (section.b_mm + section.h_mm)
    # Resistência do cordão: f_vw,d = fu / (sqrt(3) × beta_w × gamma_M2)
    fu_mpa    = spec.fu_mpa
    beta_w    = 0.90   # EC3 Tab. 4.1 para S355
    gamma_M2  = spec.gamma_M2
    f_vwd     = fu_mpa / (math.sqrt(3) * beta_w * gamma_M2)

    # Tensão no cordão: tau = P / (a × L_weld)
    # Garganta mínima: a = 3 mm
    a_min_mm = 3.0
    tau_weld  = P_N / (a_min_mm * L_weld_mm)  # N/mm²
    a_req_mm  = tau_weld / f_vwd
    a_plate_mm = max(a_req_mm, a_min_mm)
    a_plate_mm = min(a_plate_mm, 8.0)   # máximo prático 8mm

    # Recalcular com a escolhida
    tau_actual = P_N / (a_plate_mm * L_weld_mm)
    eta_weld   = tau_actual / f_vwd

    if eta_weld > 1.0:
        warnings.append(
            f"Soldadura insuficiente (η={eta_weld:.2f}). "
            "Aumentar garganta ou comprimento de cordão."
        )

    # ── Verificação geral ─────────────────────────────────────────────────────
    eta_bearing = sigma_bearing_mpa / f_jd
    eta_bending = (M_plate_Nmm_mm * gamma_M0) / (fy_mpa * t_plate_mm**2 / 6.0)
    eta_overall = max(
        eta_bearing,
        eta_bending,
        eta_fan,
        eta_str,
        eta_weld,
        eta_cone,
        eta_pullout,
        eta_pryout,
        1.01 if not (spacing_ok and edge_ok) else 0.0,
    )

    if eta_overall > 1.0:
        status = CheckerStatus.FAIL
    elif eta_overall > 0.90:
        status = CheckerStatus.MARGINAL
    else:
        status = CheckerStatus.PASS

    warnings.append(
        "AVISO: Dimensionamento de parafusos por cálculo simplificado. "
        "Verificar classe de parafusos e condições de instalação."
    )

    return BasePlateResult(
        anchorage_substrate=inp.anchorage_substrate,
        concrete_grade=concrete_grade if is_concrete_anchor else "",
        length_mm=round(L_base, 0),
        width_mm=round(B_base, 0),
        thickness_mm=t_plate_mm,
        steel_grade=inp.steel_grade,
        bearing_stress_mpa=round(sigma_bearing_mpa, 2),
        utilization_bearing=round(eta_bearing, 4),
        utilization_bending=round(eta_bending, 4),
        utilization_ratio=round(eta_overall, 4),
        bolt_diameter_mm=d_bolt_fan_mm,
        n_bolts_fan=n_bolts_fan,
        bolt_utilization_fan=round(eta_fan, 4),
        n_bolts_structure=n_bolts_str,
        bolt_utilization_structure=round(eta_str, 4),
        hole_diameter_mm=round(hole_diameter_mm, 1),
        anchor_spacing_x_mm=round(spacing_x_mm, 0),
        anchor_spacing_y_mm=round(spacing_y_mm, 0),
        edge_distance_x_mm=round(edge_x_mm, 0),
        edge_distance_y_mm=round(edge_y_mm, 0),
        min_spacing_mm=round(min_spacing_mm, 1),
        min_edge_distance_mm=round(min_edge_distance_mm, 1),
        spacing_ok=spacing_ok,
        edge_distance_ok=edge_ok,
        concrete_cone_capacity_kN=round(concrete_cone_capacity_kN, 2),
        pullout_capacity_kN=round(pullout_capacity_kN, 2),
        pryout_capacity_kN=round(pryout_capacity_kN, 2),
        utilization_concrete_cone=round(eta_cone, 4),
        utilization_pullout=round(eta_pullout, 4),
        utilization_pryout=round(eta_pryout, 4),
        weld_throat_mm=round(a_plate_mm, 1),
        weld_utilization=round(eta_weld, 4),
        status=status,
        code_clause="EN 1993-1-8 cl. 6.2.5 | EN 1993-1-1 cl. 6.2.5",
        warnings=warnings,
    )


def _round_plate_thickness(t_min: float) -> float:
    """Arredonda para espessura comercial de chapa."""
    thicknesses = [10, 12, 15, 16, 20, 25, 30, 35, 40, 50]
    for t in thicknesses:
        if t >= t_min:
            return float(t)
    return math.ceil(t_min / 5.0) * 5.0


def _bolt_shear_capacity(d_mm: float, grade: str = "8.8") -> float:
    """Resistência ao corte de um parafuso [kN] — aproximação EN 1993-1-8."""
    fub = {"8.8": 800.0, "10.9": 1000.0}.get(grade, 800.0)
    As_mm2 = 0.78 * math.pi * (d_mm / 2.0)**2  # área resistente aproximada
    Fv_Rd_N = 0.6 * fub * As_mm2 / 1.25
    return Fv_Rd_N / 1000.0
