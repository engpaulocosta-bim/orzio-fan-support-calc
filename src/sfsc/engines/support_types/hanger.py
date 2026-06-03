"""HANGER — suporte pendurado em viga (varões roscados + viga de apoio)."""
from __future__ import annotations
from ...models import FanSupportInput, LoadCombination
from ...enums import StructuralCode
from ...units import mm_to_m


def calc_hanger(
    inp: FanSupportInput,
    total_weight_kN: float,
    combinations: list[LoadCombination],
    code: StructuralCode,
) -> tuple[LoadCombination, float, float]:
    """
    Modelo: viga biapoiada com carga central. Varões roscados em tracção pura.

    Geometria:
        span_mm     = comprimento da viga de apoio (entre os dois pontos de fixação)
        rod_length  = comprimento dos varões (altura tecto → base ventilador)

    Momento máximo: M = P × L / 4  (carga central)
    Comprimentos de encurvadura: Lcr_y = span, Lcr_z = 0.5×span (travamento lateral pelos varões)
    """
    L_mm  = inp.span_mm
    L_m   = mm_to_m(L_mm)

    # Actualizar M_y_kNm na combinação governante
    governing = max(combinations, key=lambda c: abs(c.V_z_kN))
    M_max_kNm = governing.V_z_kN * L_m / 4.0

    updated = LoadCombination(
        name=governing.name,
        N_kN=governing.N_kN,
        V_z_kN=governing.V_z_kN,
        V_y_kN=governing.V_y_kN,
        M_y_kNm=M_max_kNm,
        M_z_kNm=governing.M_z_kNm,
        T_kNm=governing.T_kNm,
        governing=True,
        load_factors_used=governing.load_factors_used,
        description=f"Hanger — viga biapoiada L={L_m:.2f}m, M={M_max_kNm:.2f} kNm",
    )

    # Comprimentos de encurvadura
    Lcr_y_mm = L_mm            # eixo forte — comprimento total
    Lcr_z_mm = 0.5 * L_mm     # eixo fraco — travamento a meio vão pelos varões

    return updated, Lcr_y_mm, Lcr_z_mm
