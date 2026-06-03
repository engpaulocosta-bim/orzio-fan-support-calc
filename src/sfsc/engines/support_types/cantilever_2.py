"""CANTILEVER_2 — consolas simétricas dos dois lados."""
from __future__ import annotations
from ...models import FanSupportInput, LoadCombination
from ...enums import StructuralCode
from ...units import mm_to_m


def calc_cantilever_2(
    inp: FanSupportInput,
    total_weight_kN: float,
    combinations: list[LoadCombination],
    code: StructuralCode,
) -> tuple[LoadCombination, float, float]:
    """
    Dois braços simétricos. Cada braço suporta P/2.
    Viga central (entre apoios) recebe carga total — biapoiada.
    Momento na viga: M = P/2 × (L_arm)  por braço.
    Momento na viga central: depende da geometria — assume biapoiada simétrica.
    Lcr_y = L_total (vão entre apoios externos)
    Lcr_z = 0.5 × L_total
    """
    L_mm  = inp.span_mm       # vão total entre apoios externos
    L_m   = mm_to_m(L_mm)
    L_arm = L_m / 2.0         # braço de cada lado

    governing = max(combinations, key=lambda c: abs(c.V_z_kN))
    P_kN = governing.V_z_kN

    # Momento máximo em cada braço
    M_arm_kNm = (P_kN / 2.0) * L_arm

    # Momento máximo na viga central (carga distribuída simétrica)
    M_central_kNm = P_kN * L_m / 8.0  # wL²/8 equivalente

    M_governing = max(M_arm_kNm, M_central_kNm)

    updated = LoadCombination(
        name=governing.name,
        N_kN=0.0,
        V_z_kN=P_kN / 2.0,   # cada braço recebe metade
        V_y_kN=governing.V_y_kN,
        M_y_kNm=M_governing,
        governing=True,
        load_factors_used=governing.load_factors_used,
        description=(
            f"Cantilever 2 lados L={L_m:.2f}m braço={L_arm:.2f}m "
            f"M_braço={M_arm_kNm:.2f} kNm M_central={M_central_kNm:.2f} kNm"
        ),
    )
    Lcr_y_mm = L_mm
    Lcr_z_mm = 0.5 * L_mm
    return updated, Lcr_y_mm, Lcr_z_mm
