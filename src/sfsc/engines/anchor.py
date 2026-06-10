"""Dimensionamento de ancoragens / varões de suspensão — por tipo de suporte.

Correcção da auditoria C-05/C-06: o modelo anterior tratava a carga
gravítica (V_z) como tracção nas ancoragens e assumia embebimento em betão
para qualquer tipo de suporte, incluindo HANGER pendurado em viga metálica.

Modelo actual, a partir das combinações de ACÇÕES totais (não transformadas):

HANGER (anchor_type="rod") — varões roscados de suspensão:
    N_Ed,rod = V_uls / n      (tracção directa: o peso pendura nos varões)
    V_Ed,rod = E_h / n        (corte: acção horizontal sísmica)
    Resistências EN 1993-1-8 Tab. 3.4:
        F_t,Rd = 0.9·fub·As / γM2     F_v,Rd = 0.6·fub·As / γM2
    Interacção: F_v/F_v,Rd + F_t/(1.4·F_t,Rd) ≤ 1.0
    Sem verificações de betão (hef = 0). hanger_rod_length_mm → esbelteza
    λ = L/i (i = d/4, varão circular): se λ > 200, o varão não tem
    capacidade de compressão — aviso de travamento.

Suportes no chão (PEDESTAL, COMBINED, CANTILEVER_3) — chumbadores em betão:
    Tracção por derrube sísmico (auditoria C-06):
        h_cg   = installation_height + max(CG das unidades)
        M_ot   = E_h × h_cg
        braço  = 0.8 × footprint_length      (dispersão do grupo de ancoragens)
        n_t    = n/2                          (ancoragens do lado traccionado)
        T_anc  = max(0, M_ot/(braço·n_t) − G/n)    [G = 1.0·G_total, favorável]
        V_anc  = E_h / n
    Exemplo (verificado em teste): 320 kg, ag/g=0.40, h=800 mm, CG=300 mm,
    footprint 1000 mm → G_tot=3.609 kN, E_h=1.444 kN, M_ot=1.588 kNm,
    braço=0.8 m, T_anc = max(0, 1.588/(0.8·2) − 3.609/4) = 0.090 kN > 0.

Consolas em parede (CANTILEVER_1, CANTILEVER_2) — chumbadores em betão:
    Tracção pelo momento de encastramento:
        CANTILEVER_1: M_fix = V_uls × (L + e)
        CANTILEVER_2: M_fix = (V_uls/2) × (L/2 + e)  por apoio
        braço = max(0.9 × h_secção, 150 mm)
        T_anc = M_fix/(braço·n_t)
        V_anc = sqrt(V_apoio² + E_h²) / n      (peso pendura em corte na parede)

Verificações de betão (apenas anchor_type="concrete"): pull-out por
aderência com hef = max(8d, 100 mm) — modelo simplificado, ver A-ANC-001.
"""
from __future__ import annotations
import math
from typing import Optional
from ..models import FanSupportInput, LoadCombination, AnchorResult, SteelSection
from ..enums import StructuralCode, CheckerStatus, SupportType
from ..units import mm_to_m

_FCK: dict[str, float] = {
    "C20/25": 20.0, "C25/30": 25.0, "C30/37": 30.0,
    "C35/45": 35.0, "C40/50": 40.0,
}

# Tensão de cedência e rotura de varões roscados [MPa]
_ROD_GRADES: dict[str, tuple[float, float]] = {
    "5.8": (400.0, 500.0),
    "8.8": (640.0, 800.0),
    "10.9":(900.0, 1000.0),
    "A4-70": (450.0, 700.0),  # inox AISI 316
}

_FLOOR_TYPES = (SupportType.PEDESTAL, SupportType.COMBINED, SupportType.CANTILEVER_3)
_WALL_TYPES  = (SupportType.CANTILEVER_1, SupportType.CANTILEVER_2)

_GAMMA_M2 = 1.25
_DIAMETERS = [12.0, 16.0, 20.0, 24.0, 30.0]
_N_OPTIONS = [4, 6, 8]


def _rod_area_mm2(d_mm: float) -> float:
    return 0.78 * math.pi * (d_mm / 2.0) ** 2


def _capacities_kN(d_mm: float, fu_rod: float) -> tuple[float, float]:
    """(F_t,Rd, F_v,Rd) por varão — EN 1993-1-8 Tab. 3.4."""
    As = _rod_area_mm2(d_mm)
    Ft_Rd = 0.9 * fu_rod * As / (_GAMMA_M2 * 1000.0)
    Fv_Rd = 0.6 * fu_rod * As / (_GAMMA_M2 * 1000.0)
    return Ft_Rd, Fv_Rd


def _action_demands(combinations: list[LoadCombination]) -> tuple[float, float, float]:
    """Extrai (V_uls_total, E_h, G_unfactored) das combinações de acções totais."""
    uls = [c for c in combinations if c.name.upper().startswith("ULS")] or list(combinations)
    V_uls_kN = max(abs(c.V_z_kN) for c in uls)
    E_h_kN = max((abs(c.V_y_kN) for c in uls), default=0.0)
    seis = next((c for c in uls if "SEISMIC" in c.name.upper()), None)
    G_kN = abs(seis.V_z_kN) if seis else V_uls_kN / 1.35
    return V_uls_kN, E_h_kN, G_kN


def calculate_anchor(
    inp: FanSupportInput,
    combinations: list[LoadCombination],
    code: StructuralCode,
    concrete_grade: str = "C25/30",
    rod_grade: str = "8.8",
    section: Optional[SteelSection] = None,
) -> AnchorResult:
    """Dimensiona ancoragens/varões a partir das combinações de acções totais."""
    warnings: list[str] = []
    fy_rod, fu_rod = _ROD_GRADES.get(rod_grade, (640.0, 800.0))
    V_uls_kN, E_h_kN, G_kN = _action_demands(combinations)

    is_rod = inp.support_type == SupportType.HANGER

    # ── Esforços por ancoragem, em função do tipo de suporte ─────────────────
    def demands(n: int) -> tuple[float, float]:
        """(N_Ed por ancoragem, V_Ed por ancoragem) para n ancoragens."""
        n_t = max(1, n // 2)
        if is_rod:
            return V_uls_kN / n, E_h_kN / n
        if inp.support_type in _FLOOR_TYPES:
            h_cg_mm = inp.installation_height_mm + max(
                u.centre_of_gravity_height_mm for u in inp.fan_units
            )
            M_ot_kNm = E_h_kN * mm_to_m(h_cg_mm)
            lever_m = 0.8 * mm_to_m(inp.fan_units[0].footprint_length_mm)
            T_kN = max(0.0, M_ot_kNm / (lever_m * n_t) - G_kN / n) if lever_m > 0 else 0.0
            return T_kN, E_h_kN / n
        # _WALL_TYPES — consolas fixadas em parede
        e_m = mm_to_m(inp.eccentricity_mm)
        if inp.support_type == SupportType.CANTILEVER_2:
            P_support_kN = V_uls_kN / 2.0
            M_fix_kNm = P_support_kN * (mm_to_m(inp.span_mm) / 2.0 + e_m)
        else:
            P_support_kN = V_uls_kN
            M_fix_kNm = P_support_kN * (mm_to_m(inp.span_mm) + e_m)
        lever_m = mm_to_m(max(0.9 * section.h_mm, 150.0)) if section else 0.150
        T_kN = M_fix_kNm / (lever_m * n_t)
        V_kN = math.sqrt(P_support_kN**2 + E_h_kN**2) / n
        return T_kN, V_kN

    def interaction(eta_N: float, eta_V: float) -> float:
        if is_rod:
            # EN 1993-1-8 Tab. 3.4: Fv/FvRd + Ft/(1.4·FtRd) ≤ 1.0
            return eta_V + eta_N / 1.4
        # EN 1992-4 cl. 7.2.2: interacção exponencial 1.5
        return eta_N**1.5 + eta_V**1.5

    # ── Escolher diâmetro/quantidade ──────────────────────────────────────────
    best = None
    for d_mm in _DIAMETERS:
        Ft_Rd_kN, Fv_Rd_kN = _capacities_kN(d_mm, fu_rod)
        for n in _N_OPTIONS:
            N_Ed_kN, V_Ed_kN = demands(n)
            eta_N = N_Ed_kN / Ft_Rd_kN
            eta_V = V_Ed_kN / Fv_Rd_kN
            eta_comb = interaction(eta_N, eta_V)
            if eta_comb <= 1.0 and eta_N <= 0.90 and eta_V <= 0.90:
                best = (d_mm, n, Ft_Rd_kN, Fv_Rd_kN, N_Ed_kN, eta_N, eta_V, eta_comb)
                break
        if best:
            break

    if best is None:
        d_mm, n = _DIAMETERS[-1], _N_OPTIONS[-1]
        Ft_Rd_kN, Fv_Rd_kN = _capacities_kN(d_mm, fu_rod)
        N_Ed_kN, V_Ed_kN = demands(n)
        eta_N = N_Ed_kN / Ft_Rd_kN
        eta_V = V_Ed_kN / Fv_Rd_kN
        eta_comb = interaction(eta_N, eta_V)
        best = (d_mm, n, Ft_Rd_kN, Fv_Rd_kN, N_Ed_kN, eta_N, eta_V, eta_comb)
        warnings.append(
            "CRÍTICO: Ancoragem máxima (Ø30mm × 8) ainda insuficiente. "
            "Verificar com engenheiro de estruturas."
        )

    d_mm, n_anchors, Ft_Rd_kN, Fv_Rd_kN, N_Ed_anchor_kN, eta_N, eta_V, eta_comb = best

    # ── Verificações específicas por tipo ─────────────────────────────────────
    if is_rod:
        hef_mm = 0.0
        clause = "EN 1993-1-8 Tab. 3.4 (varões roscados — sem betão)"
        if inp.hanger_rod_length_mm:
            # Esbelteza do varão circular: i = d/4
            i_mm = d_mm / 4.0
            lam = inp.hanger_rod_length_mm / i_mm
            if lam > 200.0:
                warnings.append(
                    f"Varões roscados esbeltos (λ = {lam:.0f} > 200, "
                    f"L = {inp.hanger_rod_length_mm:.0f} mm): sem capacidade de "
                    "compressão — a acção horizontal sísmica exige travamento "
                    "lateral dedicado (verificar por especialista)."
                )
        if E_h_kN > 0.01:
            warnings.append(
                "Acção horizontal em suporte pendurado: assumido que os varões "
                "absorvem o corte. Confirmar travamento/contraventamento real."
            )
    else:
        fck = _FCK.get(concrete_grade, 25.0)
        hef_mm = max(8.0 * d_mm, 100.0)
        # Pull-out por aderência: Nbd = π·d·hef·fbd (modelo simplificado A-ANC-001)
        fbd_mpa = 0.7 * 2.25 * (fck / 25.0) ** 0.5
        N_bd_kN = math.pi * d_mm * hef_mm * fbd_mpa / 1000.0
        if N_Ed_anchor_kN > 0 and N_bd_kN < N_Ed_anchor_kN:
            hef_mm = (N_Ed_anchor_kN * 1000.0) / (math.pi * d_mm * fbd_mpa)
            hef_mm = math.ceil(hef_mm / 10.0) * 10.0
            warnings.append(
                f"Profundidade aumentada para {hef_mm:.0f} mm "
                "para garantir resistência ao arranque."
            )
        if code.value.startswith("EN"):
            clause = "EN 1992-4 cl. 7.2.1 + 7.2.2"
        elif code == StructuralCode.NBR_8800:
            clause = "NBR 6122 (simplificado)"
        else:
            clause = "EN 1992-4 cl. 7.2.1 (referência)"
        if inp.support_type in _FLOOR_TYPES and N_Ed_anchor_kN <= 0.0:
            warnings.append(
                "Sem tracção de derrube nas ancoragens (peso próprio governa). "
                "Ancoragens dimensionadas ao corte sísmico — confirmar fixação mínima construtiva."
            )

    if eta_comb > 1.0 or eta_N > 1.0 or eta_V > 1.0:
        status = CheckerStatus.FAIL
    elif eta_comb > 0.90:
        status = CheckerStatus.MARGINAL
    else:
        status = CheckerStatus.PASS

    return AnchorResult(
        n_anchors=n_anchors,
        anchor_diameter_mm=d_mm,
        embedment_depth_mm=round(hef_mm, 0),
        anchor_type="rod" if is_rod else "concrete",
        tensile_capacity_kN=round(n_anchors * Ft_Rd_kN, 2),
        shear_capacity_kN=round(n_anchors * Fv_Rd_kN, 2),
        utilization_tension=round(eta_N, 4),
        utilization_shear=round(eta_V, 4),
        utilization_combined=round(eta_comb, 4),
        status=status,
        code_clause=clause,
        warnings=warnings,
    )
