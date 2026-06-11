"""CANTILEVER_3 — U invertido (3 lados): dois pilares + viga superior."""
from __future__ import annotations

from ...enums import StructuralCode
from ...models import FanSupportInput, LoadCombination
from ...units import mm_to_m


def _member_forces(inp: FanSupportInput, c: LoadCombination) -> LoadCombination:
    """Esforços no elemento para UMA combinação de acções.

    Pórtico simples: viga superior biapoiada + dois pilares em compressão.
        Viga:   M_viga = V_z × L / 4 + V_z × e   (carga central)
        Pilar:  N = V_z / 2; M_pilar = V_y × h / 2 (acção horizontal)
        M_y = max(M_viga, M_pilar)
    """
    L_m = mm_to_m(inp.span_mm)
    h_m = mm_to_m(inp.installation_height_mm)
    e_m = mm_to_m(inp.eccentricity_mm)
    P_kN = c.V_z_kN
    H_kN = abs(c.V_y_kN)

    M_viga_kNm = P_kN * L_m / 4.0 + abs(P_kN) * e_m
    N_pilar_kN = P_kN / 2.0
    M_pilar_kNm = H_kN * h_m / 2.0   # distribuído entre 2 pilares
    M_y_kNm = max(M_viga_kNm, M_pilar_kNm)

    return LoadCombination(
        name=c.name,
        N_kN=N_pilar_kN,
        V_z_kN=P_kN / 2.0,
        V_y_kN=H_kN / 2.0,
        M_y_kNm=M_y_kNm,
        member_level=True,
        load_factors_used=c.load_factors_used,
        description=(
            f"Cantilever 3 lados (pórtico) L={L_m:.2f}m h={h_m:.2f}m "
            f"M_viga={M_viga_kNm:.2f} kNm N_pilar={N_pilar_kN:.2f} kN "
            f"M_pilar_sismo={M_pilar_kNm:.2f} kNm"
        ),
    )


def calc_cantilever_3(
    inp: FanSupportInput,
    total_weight_kN: float,
    combinations: list[LoadCombination],
    code: StructuralCode,
) -> tuple[list[LoadCombination], float, float]:
    """
    Transforma TODAS as combinações de acções em esforços no elemento
    (auditoria C-01/C-02 — a combinação sísmica também é verificada).

    Encurvadura: Lcr_y = L (viga), Lcr_z = h (pilares — eixo fraco não travado).
    """
    member_combos = [_member_forces(inp, c) for c in combinations]

    Lcr_y_mm = inp.span_mm
    Lcr_z_mm = inp.installation_height_mm
    return member_combos, Lcr_y_mm, Lcr_z_mm
