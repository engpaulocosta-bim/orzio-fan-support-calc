"""PEDESTAL — mesa com 2 patins longitudinais (perfis tipo patim)."""
from __future__ import annotations

from ...enums import StructuralCode
from ...models import FanSupportInput, LoadCombination
from ...units import mm_to_m


def _member_forces(inp: FanSupportInput, c: LoadCombination) -> LoadCombination:
    """Esforços no patim para UMA combinação de acções.

    2 perfis longitudinais (patins) sob o ventilador; cada patim recebe
    V_z/2 como carga distribuída uniforme:
        M_patim = (V_z/2) × L / 8 + (V_z/2) × e   (viga biapoiada, carga distribuída)
        M_sismo = V_y × h / 2                      (força horizontal × altura da mesa)
        M_y = M_patim + M_sismo
        V por patim = V_z / 4
    """
    L_m = mm_to_m(inp.span_mm)                 # comprimento dos patins
    h_m = mm_to_m(inp.installation_height_mm)  # altura dos pés
    e_m = mm_to_m(inp.eccentricity_mm)
    P_kN = c.V_z_kN
    H_kN = abs(c.V_y_kN)

    q_kNm = (P_kN / 2.0) / L_m if L_m > 0 else 0.0
    M_patim_kNm = q_kNm * L_m**2 / 8.0 + abs(P_kN / 2.0) * e_m
    M_sismo_kNm = H_kN * h_m / 2.0
    M_y_kNm = M_patim_kNm + M_sismo_kNm

    return LoadCombination(
        name=c.name,
        N_kN=0.0,
        V_z_kN=P_kN / 4.0,
        V_y_kN=H_kN / 2.0,
        M_y_kNm=M_y_kNm,
        member_level=True,
        load_factors_used=c.load_factors_used,
        description=(
            f"Pedestal (2 patins) L={L_m:.2f}m h={h_m:.2f}m "
            f"M_patim={M_patim_kNm:.2f} kNm M_sismo={M_sismo_kNm:.2f} kNm"
        ),
    )


def calc_pedestal(
    inp: FanSupportInput,
    total_weight_kN: float,
    combinations: list[LoadCombination],
    code: StructuralCode,
) -> tuple[list[LoadCombination], float, float]:
    """
    Transforma TODAS as combinações de acções em esforços no patim
    (auditoria C-01/C-02 — a combinação sísmica também é verificada).

    Lcr_y = L (patins), Lcr_z = h (pés, se houver).
    """
    member_combos = [_member_forces(inp, c) for c in combinations]

    L_mm = inp.span_mm
    h_mm = inp.installation_height_mm
    Lcr_y_mm = L_mm
    Lcr_z_mm = h_mm if h_mm > 0 else L_mm
    return member_combos, Lcr_y_mm, Lcr_z_mm
