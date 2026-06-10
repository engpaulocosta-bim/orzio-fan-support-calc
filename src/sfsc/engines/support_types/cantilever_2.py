"""CANTILEVER_2 — consolas simétricas dos dois lados."""
from __future__ import annotations
from ...models import FanSupportInput, LoadCombination
from ...enums import StructuralCode
from ...units import mm_to_m


def _member_forces(inp: FanSupportInput, c: LoadCombination) -> LoadCombination:
    """Esforços no elemento para UMA combinação de acções.

    Dois braços simétricos. Cada braço suporta V_z/2.
        M_braço   = (V_z/2) × L_braço + (V_z/2) × e
        M_central = V_z × L / 8   (viga central biapoiada)
        M_y = max(M_braço, M_central)
        M_z = max((V_y/2) × L_braço, V_y × L / 8)   (acção horizontal)
    """
    L_m = mm_to_m(inp.span_mm)   # vão total entre apoios externos
    L_arm = L_m / 2.0
    e_m = mm_to_m(inp.eccentricity_mm)
    P_kN = c.V_z_kN
    H_kN = abs(c.V_y_kN)

    M_arm_kNm = (P_kN / 2.0) * L_arm + abs(P_kN / 2.0) * e_m
    M_central_kNm = P_kN * L_m / 8.0
    M_y_kNm = max(M_arm_kNm, M_central_kNm)
    M_z_kNm = max((H_kN / 2.0) * L_arm, H_kN * L_m / 8.0)

    return LoadCombination(
        name=c.name,
        N_kN=0.0,
        V_z_kN=P_kN / 2.0,   # cada braço recebe metade
        V_y_kN=c.V_y_kN / 2.0,
        M_y_kNm=M_y_kNm,
        M_z_kNm=M_z_kNm,
        member_level=True,
        load_factors_used=c.load_factors_used,
        description=(
            f"Cantilever 2 lados L={L_m:.2f}m braço={L_arm:.2f}m "
            f"M_braço={M_arm_kNm:.2f} kNm M_central={M_central_kNm:.2f} kNm"
        ),
    )


def calc_cantilever_2(
    inp: FanSupportInput,
    total_weight_kN: float,
    combinations: list[LoadCombination],
    code: StructuralCode,
) -> tuple[list[LoadCombination], float, float]:
    """
    Transforma TODAS as combinações de acções em esforços no elemento
    (auditoria C-01/C-02 — a combinação sísmica também é verificada).

    Lcr_y = L_total (vão entre apoios externos), Lcr_z = 0.5×L_total.
    """
    member_combos = [_member_forces(inp, c) for c in combinations]

    L_mm = inp.span_mm
    Lcr_y_mm = L_mm
    Lcr_z_mm = 0.5 * L_mm
    return member_combos, Lcr_y_mm, Lcr_z_mm
