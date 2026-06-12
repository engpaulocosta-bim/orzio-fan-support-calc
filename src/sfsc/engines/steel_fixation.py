"""Fixação em estrutura metálica — ligação aço-aço (EN 1993-1-8, tarefa 1.5).

Alternativa às ancoragens em betão: quando ``support_fixation_medium`` é
``steel_structure``, o suporte é fixado a um perfil existente por parafusos,
soldadura ou ambos. O elemento receptor (perfil existente) NÃO é verificado
por este modelo — emite-se aviso explícito.
"""

from __future__ import annotations

import math

from ..enums import BoltClass, CheckerStatus, SteelConnectionType
from ..models import FanSupportInput, LoadCombination, SteelFixationResult, SteelSection

# fub por classe de parafuso [MPa] (EN 1993-1-8 Tab. 3.1).
_FUB: dict[str, float] = {"4.6": 400.0, "5.6": 500.0, "8.8": 800.0, "10.9": 1000.0}
_FYB: dict[str, float] = {"4.6": 240.0, "5.6": 300.0, "8.8": 640.0, "10.9": 900.0}
_GAMMA_M2 = 1.25
_BETA_W = 0.90  # S355 (conservativo)
_FU_PLATE = 510.0  # S355 chapa [MPa]
_FY_PLATE = 355.0


def _bolt_area_mm2(d_mm: float) -> float:
    return 0.78 * math.pi * (d_mm / 2.0) ** 2


def calculate_steel_fixation(
    inp: FanSupportInput,
    combination: LoadCombination,
    section: SteelSection | None = None,
) -> SteelFixationResult:
    """Verificação simplificada da ligação aço-aço a partir do esforço governante."""
    fix = inp.steel_fixation
    conn_type = fix.connection_type if fix else SteelConnectionType.BOLTED
    bolt_class = fix.bolt_class.value if fix else BoltClass.C8_8.value
    fub = _FUB.get(bolt_class, 800.0)

    warnings: list[str] = []

    # Defaults sensatos quando o utilizador não fornece tudo.
    d_bolt = fix.bolt_diameter_mm if fix and fix.bolt_diameter_mm else 16.0
    n_bolts = int(fix.number_of_bolts) if fix and fix.number_of_bolts else 4
    t_plate = fix.plate_thickness_mm if fix and fix.plate_thickness_mm else 10.0
    hole_d = fix.hole_diameter_mm if fix and fix.hole_diameter_mm else d_bolt + 2.0

    V_Ed_kN = max(abs(combination.V_z_kN), abs(combination.V_y_kN))
    # Tração por momento de encastramento (braço ~ altura da secção ou 150 mm).
    lever_m = max((section.h_mm if section else 150.0) * 0.9, 150.0) / 1000.0
    N_from_moment = abs(combination.M_y_kNm) / lever_m if lever_m > 0 else 0.0
    N_Ed_kN = max(0.0, abs(combination.N_kN)) + N_from_moment

    As = _bolt_area_mm2(d_bolt)

    has_bolts = conn_type in (SteelConnectionType.BOLTED, SteelConnectionType.BOLTED_WELDED)
    has_weld = conn_type in (SteelConnectionType.WELDED, SteelConnectionType.BOLTED_WELDED)

    # ── Parafusos ─────────────────────────────────────────────────────────────
    eta_shear = eta_tension = eta_inter = eta_bearing = 0.0
    if has_bolts:
        Fv_Rd = 0.6 * fub * As / (_GAMMA_M2 * 1000.0)  # corte por parafuso [kN]
        Ft_Rd = 0.9 * fub * As / (_GAMMA_M2 * 1000.0)  # tração por parafuso [kN]
        eta_shear = (V_Ed_kN / n_bolts) / Fv_Rd if Fv_Rd > 0 else 99.0
        eta_tension = (N_Ed_kN / n_bolts) / Ft_Rd if Ft_Rd > 0 else 0.0
        # Interacção EN 1993-1-8 Tab. 3.4: Fv/FvRd + Ft/(1.4·FtRd) ≤ 1.0
        eta_inter = eta_shear + eta_tension / 1.4
        # Esmagamento/furação simplificado: F_b,Rd = 2.5·fu·d·t/γM2 (k1·αb ≈ 2.5).
        Fb_Rd = 2.5 * _FU_PLATE * d_bolt * t_plate / (_GAMMA_M2 * 1000.0)
        eta_bearing = (V_Ed_kN / n_bolts) / Fb_Rd if Fb_Rd > 0 else 99.0

    # ── Soldadura (filete por tensão nominal) ─────────────────────────────────
    eta_weld = 0.0
    if has_weld:
        a_weld = fix.weld_size_mm if fix and fix.weld_size_mm else 4.0
        L_weld = (
            fix.weld_length_mm
            if fix and fix.weld_length_mm
            else 2.0 * (section.b_mm if section else 100.0)
        )
        f_vwd = _FU_PLATE / (math.sqrt(3.0) * _BETA_W * _GAMMA_M2)
        weld_cap_kN = a_weld * L_weld * f_vwd / 1000.0
        eta_weld = (V_Ed_kN + 0.3 * N_Ed_kN) / weld_cap_kN if weld_cap_kN > 0 else 99.0

    # ── Chapa de ligação à flexão/corte (simplificado) ───────────────────────
    Vpl_plate_kN = (hole_d * 4) * t_plate * _FY_PLATE / math.sqrt(3) / 1000.0
    eta_plate = V_Ed_kN / Vpl_plate_kN if Vpl_plate_kN > 0 else 0.0

    eta_overall = max(eta_shear, eta_tension, eta_inter, eta_bearing, eta_weld, eta_plate)

    if eta_overall > 1.0:
        status = CheckerStatus.FAIL
    elif eta_overall > 0.90:
        status = CheckerStatus.MARGINAL
    else:
        status = CheckerStatus.PASS

    # Elemento receptor não verificado — aviso obrigatório (tarefa 1.5).
    receiving_checked = False
    warnings.append("W-STEELFIX-RECEIVER")  # mapeado para i18n no relatório

    return SteelFixationResult(
        connection_type=conn_type,
        n_bolts=n_bolts if has_bolts else 0,
        bolt_diameter_mm=d_bolt if has_bolts else 0.0,
        bolt_class=bolt_class,
        plate_thickness_mm=t_plate,
        utilization_bolt_shear=round(eta_shear, 4),
        utilization_bolt_tension=round(eta_tension, 4),
        utilization_bolt_interaction=round(eta_inter, 4),
        utilization_bearing=round(eta_bearing, 4),
        utilization_weld=round(eta_weld, 4),
        utilization_plate=round(eta_plate, 4),
        utilization_ratio=round(eta_overall, 4),
        receiving_member_checked=receiving_checked,
        status=status,
        code_clause="EN 1993-1-8 cl. 3 (parafusos) + cl. 4 (soldaduras)",
        warnings=warnings,
        intermediate_values={
            "V_Ed_kN": round(V_Ed_kN, 3),
            "N_Ed_kN": round(N_Ed_kN, 3),
            "bolt_As_mm2": round(As, 1),
            "fub_MPa": fub,
        },
    )
