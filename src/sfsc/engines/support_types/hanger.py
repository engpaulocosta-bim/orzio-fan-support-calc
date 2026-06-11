"""HANGER — suporte pendurado em viga (varões roscados + viga de apoio)."""

from __future__ import annotations

from ...enums import StructuralCode
from ...models import FanSupportInput, LoadCombination
from ...units import mm_to_m


def _member_forces(inp: FanSupportInput, c: LoadCombination) -> LoadCombination:
    """Esforços na viga de apoio para UMA combinação de acções.

    Modelo: viga biapoiada com carga central.
        M_y = V_z × L / 4  +  |V_z| × e   (e = excentricidade do CG)
        M_z = |V_y| × L / 4               (acção horizontal, mesmo modelo lateral)
    """
    L_m = mm_to_m(inp.span_mm)
    e_m = mm_to_m(inp.eccentricity_mm)
    M_y_kNm = c.V_z_kN * L_m / 4.0 + abs(c.V_z_kN) * e_m
    M_z_kNm = abs(c.V_y_kN) * L_m / 4.0
    return LoadCombination(
        name=c.name,
        N_kN=c.N_kN,
        V_z_kN=c.V_z_kN,
        V_y_kN=c.V_y_kN,
        M_y_kNm=M_y_kNm,
        M_z_kNm=M_z_kNm,
        T_kNm=c.T_kNm,
        member_level=True,
        load_factors_used=c.load_factors_used,
        description=f"Hanger — viga biapoiada L={L_m:.2f}m, M={M_y_kNm:.2f} kNm",
    )


def calc_hanger(
    inp: FanSupportInput,
    total_weight_kN: float,
    combinations: list[LoadCombination],
    code: StructuralCode,
) -> tuple[list[LoadCombination], float, float]:
    """
    Transforma TODAS as combinações de acções em esforços na viga de apoio
    (auditoria C-01/C-02 — a combinação sísmica também é verificada).

    Geometria:
        span_mm     = comprimento da viga de apoio (entre os dois pontos de fixação)
        rod_length  = comprimento dos varões (altura tecto → base ventilador)

    Comprimentos de encurvadura: Lcr_y = span, Lcr_z = 0.5×span
    (travamento lateral a meio vão pelos varões).
    """
    member_combos = [_member_forces(inp, c) for c in combinations]

    L_mm = inp.span_mm
    Lcr_y_mm = L_mm
    Lcr_z_mm = 0.5 * L_mm
    return member_combos, Lcr_y_mm, Lcr_z_mm
