"""PEDESTAL — mesa com 2 patins longitudinais (perfis tipo patim)."""
from __future__ import annotations
from ...models import FanSupportInput, LoadCombination
from ...enums import StructuralCode
from ...units import mm_to_m


def calc_pedestal(
    inp: FanSupportInput,
    total_weight_kN: float,
    combinations: list[LoadCombination],
    code: StructuralCode,
) -> tuple[LoadCombination, float, float]:
    """
    2 perfis longitudinais (patins) sob o ventilador.
    Cada patim recebe P/2 como carga distribuída uniforme.
    Momento: M = P/2 × L² / 8  (viga biapoiada, carga distribuída)
    Corte máximo: V = P/4
    Altura dos patins: installation_height_mm
    Lcr = installation_height_mm (comprimento dos pés se houver)
    """
    L_mm = inp.span_mm                # comprimento dos patins
    h_mm = inp.installation_height_mm # altura dos pés
    L_m  = mm_to_m(L_mm)
    h_m  = mm_to_m(h_mm)

    governing = max(combinations, key=lambda c: abs(c.V_z_kN))
    P_kN = governing.V_z_kN
    H_kN = abs(governing.V_y_kN)

    # Cada patim: P/2 distribuído em L
    q_kNm     = (P_kN / 2.0) / L_m if L_m > 0 else 0.0
    M_patim_kNm = q_kNm * L_m**2 / 8.0
    V_patim_kN  = P_kN / 4.0

    # Momento adicional por sismo (força horizontal sobre altura da mesa)
    M_sismo_kNm = H_kN * h_m / 2.0

    M_design_kNm = M_patim_kNm + M_sismo_kNm

    updated = LoadCombination(
        name=governing.name,
        N_kN=0.0,
        V_z_kN=V_patim_kN,
        V_y_kN=H_kN / 2.0,
        M_y_kNm=M_design_kNm,
        governing=True,
        load_factors_used=governing.load_factors_used,
        description=(
            f"Pedestal (2 patins) L={L_m:.2f}m h={h_m:.2f}m "
            f"M_patim={M_patim_kNm:.2f} kNm M_sismo={M_sismo_kNm:.2f} kNm"
        ),
    )
    Lcr_y_mm = L_mm
    Lcr_z_mm = h_mm if h_mm > 0 else L_mm
    return updated, Lcr_y_mm, Lcr_z_mm
