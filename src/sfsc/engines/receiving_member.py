"""Verificação do perfil receptor (elemento hospedeiro) — EC3 EN 1993-1-1 + 1-8.

O perfil receptor é o elemento existente (viga, pilar) ao qual o suporte de
ventilador está fixado. Quando a fixação é em estrutura metálica e o utilizador
fornece ``receiving_member_section_id`` em ``SteelFixationInput``, este módulo
verifica esse perfil sob as reacções do suporte.

Verificações realizadas (EC3 EN 1993-1-1):
  - Corte: VEd / Vpl,Rd  (cl. 6.2.6)
  - Flexão (momento forte/fraco): MEd / Mpl,Rd  (cl. 6.2.5)
  - Axial: NEd / Npl,Rd  (cl. 6.2.4)
  - Torção: TEd / Tpl,Rd  (cl. 6.2.7 — método de St. Venant para secções abertas)
  - Interacção M+V: redução Mpl quando VEd > 0.5·Vpl  (cl. 6.2.8)
  - Interacção N+M: equação linear (cl. 6.2.1 eq. 6.2)

A excentricidade da reacção (braço da torção = distância do eixo do suporte
ao eixo do receptor) é fornecida via ``torsion_lever_mm`` ou estimada como
metade da largura do perfil suporte.

Modelo simplificado: secções de Classe 1/2, sem flambagem local, sem LTB
(a flexão lateral está coberta no módulo do suporte). Produz um relatório de
utilização η por verificação e η_global = max(η_i).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..catalogs.steel_grade_catalog import get_grade_spec
from ..catalogs.steel_section_catalog import get_section
from ..enums import SectionFamily, SteelGrade
from ..models import LoadCombination, SteelSection

# Coeficientes parciais EC3 EN 1993-1-1.
_GAMMA_M0 = 1.00
_GAMMA_M1 = 1.00


def _section_plastic_torsion_m3(section: SteelSection) -> float:
    """Módulo plástico de torção de St. Venant aproximado [mm³] para secções abertas.

    Para perfis I/H: Wt ≈ sum(b·t²) para os rectangulos constituintes.
    """
    # flanges (2×): b × tf²
    # alma: (h - 2·tf) × tw²
    tf = section.tf_mm
    tw = section.tw_mm
    b = section.b_mm
    h = section.h_mm
    hw = h - 2.0 * tf
    return 2.0 * b * tf**2 + hw * tw**2


def _torsion_capacity_kNm(section: SteelSection, fy_mpa: float) -> float:
    """Resistência plástica à torção de St. Venant simplificada [kNm].

    Tt,pl,Rd = fy·Wt / (sqrt(3)·γM0)   (derivado de τ_t,Rd = fy/(sqrt(3)·γM0))
    """
    wt_mm3 = _section_plastic_torsion_m3(section)
    tau_rd_mpa = fy_mpa / (math.sqrt(3.0) * _GAMMA_M0)
    return tau_rd_mpa * wt_mm3 / 1e6  # kNm


@dataclass(frozen=True)
class ReceivingMemberResult:
    """Resultado da verificação do perfil receptor."""

    solved: bool
    failed: bool
    failure_reason: str
    section_id: str
    material: str
    eta_shear: float
    eta_bending_y: float
    eta_bending_z: float
    eta_axial: float
    eta_torsion: float
    eta_interaction_mv: float
    eta_interaction_nm: float
    eta_overall: float
    governing_check: str
    warnings: list[str] = field(default_factory=list)
    intermediate: dict[str, object] = field(default_factory=dict)


def run_receiving_member_check(
    *,
    section: SteelSection,
    steel_grade: SteelGrade,
    combination: LoadCombination,
    torsion_lever_mm: float | None = None,
    support_section_width_mm: float | None = None,
) -> ReceivingMemberResult:
    """Verifica o perfil receptor sob as reacções do suporte.

    Args:
        section: Secção de aço do perfil receptor (obtida do catálogo).
        steel_grade: Aço do perfil receptor (S235/S275/S355…).
        combination: Combinação de acções governante (esforços no pé do suporte).
        torsion_lever_mm: Braço de torção explícito [mm]. Se None, usa b_suporte/2.
        support_section_width_mm: Largura da secção do suporte [mm] (para estimar
            o braço de torção quando ``torsion_lever_mm`` não é fornecido).
    """
    try:
        grade = get_grade_spec(steel_grade)
    except Exception:
        return ReceivingMemberResult(
            solved=False,
            failed=True,
            failure_reason="material_not_found",
            section_id=section.designation,
            material=steel_grade.value,
            eta_shear=0.0,
            eta_bending_y=0.0,
            eta_bending_z=0.0,
            eta_axial=0.0,
            eta_torsion=0.0,
            eta_interaction_mv=0.0,
            eta_interaction_nm=0.0,
            eta_overall=0.0,
            governing_check="",
        )

    fy_mpa = grade.fy_mpa
    warnings: list[str] = []

    # ── Capacidades resistentes ───────────────────────────────────────────────
    A_mm2 = section.A_cm2 * 100.0  # cm² → mm²
    Wpl_y_mm3 = section.W_pl_y_cm3 * 1000.0  # cm³ → mm³
    Wpl_z_mm3 = getattr(section, "W_pl_z_cm3", section.W_pl_y_cm3 * 0.25) * 1000.0

    # Av (alma em corte) ≈ h·tw para perfis I/H (EC3 cl. 6.2.6(3))
    Av_mm2 = section.h_mm * section.tw_mm

    Npl_Rd = fy_mpa * A_mm2 / (_GAMMA_M0 * 1000.0)  # kN
    Vpl_Rd = fy_mpa * Av_mm2 / (math.sqrt(3.0) * _GAMMA_M0 * 1000.0)  # kN
    Mpl_y_Rd = fy_mpa * Wpl_y_mm3 / (_GAMMA_M0 * 1e6)  # kNm
    Mpl_z_Rd = fy_mpa * Wpl_z_mm3 / (_GAMMA_M0 * 1e6)  # kNm
    Tt_pl_Rd = _torsion_capacity_kNm(section, fy_mpa)  # kNm

    # ── Esforços solicitantes ─────────────────────────────────────────────────
    # A reacção vertical do suporte é o corte aplicado ao receptor.
    V_Ed = abs(combination.V_z_kN)
    # A força axial do suporte gera axial no receptor.
    N_Ed = abs(combination.N_kN)
    # O momento do suporte (arrancamento/encastramento) gera flexão no receptor.
    M_y_Ed = abs(combination.M_y_kNm)
    M_z_Ed = abs(combination.M_z_kNm)

    # Torção: braço = distância lateral entre eixo do suporte e eixo do receptor.
    if torsion_lever_mm is not None and torsion_lever_mm > 0.0:
        e_mm = torsion_lever_mm
    elif support_section_width_mm is not None and support_section_width_mm > 0.0:
        # Conservador: braço = metade da largura do suporte.
        e_mm = support_section_width_mm / 2.0
    else:
        # Estimativa mínima (perfil de 100 mm de largura como referência).
        e_mm = 50.0
        warnings.append(
            "W-RECV-TORSION-LEVER: braço de torção estimado (50 mm); fornecer torsion_lever_mm para maior precisão."
        )

    # Torção de St. Venant provocada pela reacção vertical excêntrica.
    T_Ed = V_Ed * e_mm / 1000.0  # kNm

    # ── Verificações individuais ──────────────────────────────────────────────
    eta_v = V_Ed / Vpl_Rd if Vpl_Rd > 0 else 99.0
    eta_my = M_y_Ed / Mpl_y_Rd if Mpl_y_Rd > 0 else 99.0
    eta_mz = M_z_Ed / Mpl_z_Rd if Mpl_z_Rd > 0 else 0.0
    eta_n = N_Ed / Npl_Rd if Npl_Rd > 0 else 0.0
    eta_t = T_Ed / Tt_pl_Rd if Tt_pl_Rd > 0 else 99.0

    # ── Interacção M+V (EC3 cl. 6.2.8) ──────────────────────────────────────
    # Quando VEd > 0.5·Vpl,Rd reduz-se Mpl,Rd pelo factor ρ.
    rho = 0.0
    if V_Ed > 0.5 * Vpl_Rd and Vpl_Rd > 0:
        rho = (2.0 * V_Ed / Vpl_Rd - 1.0) ** 2
    # Mpl,Rd reduzido pelo efeito do corte.
    Mpl_y_Rd_red = Mpl_y_Rd * (1.0 - rho * (Av_mm2**2) / (4.0 * Wpl_y_mm3 * section.tw_mm))
    Mpl_y_Rd_red = max(Mpl_y_Rd_red, Mpl_y_Rd * (1.0 - rho))
    eta_mv = M_y_Ed / Mpl_y_Rd_red if Mpl_y_Rd_red > 0 else 99.0

    # ── Interacção N+M (EC3 cl. 6.2.1 eq. 6.2 — linear conservativo) ─────────
    eta_nm = eta_n + eta_my + eta_mz

    # ── Resultado global ─────────────────────────────────────────────────────
    checks: dict[str, float] = {
        "shear_z": eta_v,
        "bending_y": eta_my,
        "bending_z": eta_mz,
        "axial": eta_n,
        "torsion": eta_t,
        "interaction_mv": eta_mv,
        "interaction_nm": eta_nm,
    }
    eta_overall = max(checks.values())
    governing = max(checks, key=lambda k: checks[k])

    if eta_overall > 1.0:
        warnings.append(
            f"W-RECV-FAIL: η={eta_overall:.3f} — perfil receptor insuficiente ({governing})."
        )

    return ReceivingMemberResult(
        solved=True,
        failed=False,
        failure_reason="",
        section_id=section.designation,
        material=steel_grade.value,
        eta_shear=round(eta_v, 4),
        eta_bending_y=round(eta_my, 4),
        eta_bending_z=round(eta_mz, 4),
        eta_axial=round(eta_n, 4),
        eta_torsion=round(eta_t, 4),
        eta_interaction_mv=round(eta_mv, 4),
        eta_interaction_nm=round(eta_nm, 4),
        eta_overall=round(eta_overall, 4),
        governing_check=governing,
        warnings=warnings,
        intermediate={
            "Npl_Rd_kN": round(Npl_Rd, 3),
            "Vpl_Rd_kN": round(Vpl_Rd, 3),
            "Mpl_y_Rd_kNm": round(Mpl_y_Rd, 3),
            "Mpl_z_Rd_kNm": round(Mpl_z_Rd, 3),
            "Tt_pl_Rd_kNm": round(Tt_pl_Rd, 3),
            "Mpl_y_Rd_red_kNm": round(Mpl_y_Rd_red, 3),
            "V_Ed_kN": round(V_Ed, 3),
            "M_y_Ed_kNm": round(M_y_Ed, 3),
            "N_Ed_kN": round(N_Ed, 3),
            "T_Ed_kNm": round(T_Ed, 3),
            "torsion_lever_mm": round(e_mm, 1),
            "rho_shear_moment": round(rho, 4),
        },
    )


def resolve_receiving_member_section(
    section_id: str,
) -> SteelSection | None:
    """Tenta encontrar a secção pelo id no catálogo (formato 'HEB200', 'IPE300', etc.)."""
    section_id = section_id.strip().upper()
    for family in (
        SectionFamily.HEB,
        SectionFamily.HEA,
        SectionFamily.IPE,
        SectionFamily.UPN,
        SectionFamily.RHS,
    ):
        try:
            return get_section(family, section_id)
        except Exception:
            continue
    return None
