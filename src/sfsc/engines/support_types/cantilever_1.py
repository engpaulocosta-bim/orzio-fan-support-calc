"""CANTILEVER_1 — consola simples engastada num lado (mão-francesa)."""
from __future__ import annotations
import math
from ...models import FanSupportInput, LoadCombination
from ...enums import StructuralCode, CantileverSubtype
from ...units import mm_to_m


def calc_cantilever_1(
    inp: FanSupportInput,
    total_weight_kN: float,
    combinations: list[LoadCombination],
    code: StructuralCode,
) -> tuple[LoadCombination, float, float]:
    """
    PURE:     Consola horizontal pura engastada numa face.
              M_encastramento = P × L  (máximo)
              Lcr_y = 2×L  (consola livre)
              Lcr_z = L    (sem travamento lateral)

    BRACKETED: Mão-francesa com diagonal (triângulo).
              Diagonal alivia o momento; a viga horizontal recebe compressão/tracção.
              Força na diagonal: F_diag = P / sin(θ)
              Compressão na viga horizontal: N = P / tan(θ)
              Momento na viga: M ≈ 0 (apoio no nó)  [modelo articulado nos nós]
              θ = atan(h_bracket / L)  com h_bracket = installation_height_mm
    """
    L_mm  = inp.span_mm
    L_m   = mm_to_m(L_mm)
    subtype = inp.cantilever_subtype or CantileverSubtype.PURE

    governing = max(combinations, key=lambda c: abs(c.V_z_kN))
    P_kN = governing.V_z_kN

    if subtype == CantileverSubtype.BRACKETED:
        h_mm  = inp.installation_height_mm
        h_m   = mm_to_m(h_mm)
        theta = math.atan2(h_m, L_m) if L_m > 0 else math.pi / 4.0

        # Força na diagonal (tracção) e compressão na viga horizontal
        F_diag_kN = P_kN / math.sin(theta)
        N_comp_kN = P_kN / math.tan(theta) if math.tan(theta) > 1e-6 else P_kN * 10

        # Momento desprezável no modelo articulado; V ≈ P na viga
        M_y_kNm = 0.05 * P_kN * L_m   # 5% do momento puro — imperfeições geométricas
        Lcr_y_mm = L_mm
        Lcr_z_mm = L_mm

        desc = (
            f"Cantilever BRACKETED L={L_m:.2f}m h={h_m:.2f}m θ={math.degrees(theta):.1f}° "
            f"F_diag={F_diag_kN:.2f} kN N_comp={N_comp_kN:.2f} kN"
        )
        N_design_kN = N_comp_kN  # compressão governa a diagonal

    else:  # PURE
        M_y_kNm   = P_kN * L_m
        Lcr_y_mm  = 2.0 * L_mm   # consola = 2×L
        Lcr_z_mm  = L_mm
        N_design_kN = 0.0
        desc = f"Cantilever PURE L={L_m:.2f}m M={M_y_kNm:.2f} kNm"

    updated = LoadCombination(
        name=governing.name,
        N_kN=N_design_kN,
        V_z_kN=P_kN,
        V_y_kN=governing.V_y_kN,
        M_y_kNm=M_y_kNm,
        governing=True,
        load_factors_used=governing.load_factors_used,
        description=desc,
    )
    return updated, Lcr_y_mm, Lcr_z_mm
