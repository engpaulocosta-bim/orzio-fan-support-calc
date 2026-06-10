"""CANTILEVER_1 — consola simples engastada num lado (mão-francesa)."""
from __future__ import annotations
import math
from ...models import FanSupportInput, LoadCombination
from ...enums import StructuralCode, CantileverSubtype
from ...units import mm_to_m


def _member_forces(inp: FanSupportInput, c: LoadCombination) -> LoadCombination:
    """Esforços no elemento para UMA combinação de acções.

    PURE:     Consola horizontal pura engastada numa face.
              M_y = V_z × (L + e)   (e = excentricidade do CG)
              M_z = |V_y| × L       (acção horizontal no eixo fraco)

    BRACKETED: Mão-francesa com diagonal (triângulo).
              Força na diagonal: F_diag = V_z / sin(θ)
              Compressão na viga horizontal: N = V_z / tan(θ)
              M_y ≈ 5% do momento puro (imperfeições) + V_z × e
              θ = atan(h / L) com h = installation_height_mm
    """
    L_mm = inp.span_mm
    L_m = mm_to_m(L_mm)
    e_m = mm_to_m(inp.eccentricity_mm)
    subtype = inp.cantilever_subtype or CantileverSubtype.PURE
    P_kN = c.V_z_kN
    H_kN = abs(c.V_y_kN)

    if subtype == CantileverSubtype.BRACKETED:
        h_m = mm_to_m(inp.installation_height_mm)
        theta = math.atan2(h_m, L_m) if L_m > 0 else math.pi / 4.0
        F_diag_kN = P_kN / math.sin(theta)
        N_comp_kN = P_kN / math.tan(theta) if math.tan(theta) > 1e-6 else P_kN * 10
        M_y_kNm = 0.05 * P_kN * L_m + abs(P_kN) * e_m
        N_design_kN = N_comp_kN
        desc = (
            f"Cantilever BRACKETED L={L_m:.2f}m h={h_m:.2f}m θ={math.degrees(theta):.1f}° "
            f"F_diag={F_diag_kN:.2f} kN N_comp={N_comp_kN:.2f} kN"
        )
    else:  # PURE
        M_y_kNm = P_kN * (L_m + e_m)
        N_design_kN = 0.0
        desc = f"Cantilever PURE L={L_m:.2f}m M={M_y_kNm:.2f} kNm"

    M_z_kNm = H_kN * L_m

    return LoadCombination(
        name=c.name,
        N_kN=N_design_kN,
        V_z_kN=P_kN,
        V_y_kN=c.V_y_kN,
        M_y_kNm=M_y_kNm,
        M_z_kNm=M_z_kNm,
        member_level=True,
        load_factors_used=c.load_factors_used,
        description=desc,
    )


def calc_cantilever_1(
    inp: FanSupportInput,
    total_weight_kN: float,
    combinations: list[LoadCombination],
    code: StructuralCode,
) -> tuple[list[LoadCombination], float, float]:
    """
    Transforma TODAS as combinações de acções em esforços no elemento
    (auditoria C-01/C-02 — a combinação sísmica também é verificada).

    Comprimentos de encurvadura:
        PURE:      Lcr_y = 2×L (consola livre), Lcr_z = L
        BRACKETED: Lcr_y = L (apoio no nó),     Lcr_z = L
    """
    member_combos = [_member_forces(inp, c) for c in combinations]

    L_mm = inp.span_mm
    subtype = inp.cantilever_subtype or CantileverSubtype.PURE
    if subtype == CantileverSubtype.BRACKETED:
        Lcr_y_mm = L_mm
        Lcr_z_mm = L_mm
    else:
        Lcr_y_mm = 2.0 * L_mm
        Lcr_z_mm = L_mm
    return member_combos, Lcr_y_mm, Lcr_z_mm
