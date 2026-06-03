"""CANTILEVER_3 — U invertido (3 lados): dois pilares + viga superior."""
from __future__ import annotations
from ...models import FanSupportInput, LoadCombination
from ...enums import StructuralCode
from ...units import mm_to_m


def calc_cantilever_3(
    inp: FanSupportInput,
    total_weight_kN: float,
    combinations: list[LoadCombination],
    code: StructuralCode,
) -> tuple[LoadCombination, float, float]:
    """
    Pórtico simples: viga superior biapoiada + dois pilares em compressão.
    Viga superior: M = P × L / 4 (carga central)
    Pilares: N = P / 2  (compressão axial)
    Momento nos pilares: M = H × h / 2  (sismo lateral)
    Lcr_pilares = installation_height_mm
    """
    L_mm = inp.span_mm
    h_mm = inp.installation_height_mm
    L_m  = mm_to_m(L_mm)
    h_m  = mm_to_m(h_mm)

    governing = max(combinations, key=lambda c: abs(c.V_z_kN))
    P_kN = governing.V_z_kN
    H_kN = abs(governing.V_y_kN)  # carga horizontal sísmica

    # Viga superior
    M_viga_kNm = P_kN * L_m / 4.0

    # Pilar: compressão + momento de sismo
    N_pilar_kN  = P_kN / 2.0
    M_pilar_kNm = H_kN * h_m / 2.0  # distribuído entre 2 pilares

    # Governa: viga ou pilar?
    # Dimensionamento da viga (normalmente governa)
    M_design_kNm = max(M_viga_kNm, M_pilar_kNm)

    updated = LoadCombination(
        name=governing.name,
        N_kN=N_pilar_kN,
        V_z_kN=P_kN / 2.0,
        V_y_kN=H_kN / 2.0,
        M_y_kNm=M_design_kNm,
        governing=True,
        load_factors_used=governing.load_factors_used,
        description=(
            f"Cantilever 3 lados (pórtico) L={L_m:.2f}m h={h_m:.2f}m "
            f"M_viga={M_viga_kNm:.2f} kNm N_pilar={N_pilar_kN:.2f} kN "
            f"M_pilar_sismo={M_pilar_kNm:.2f} kNm"
        ),
    )
    # Encurvadura: pilares (eixo fraco não travado = h)
    Lcr_y_mm = L_mm          # viga
    Lcr_z_mm = h_mm          # pilares
    return updated, Lcr_y_mm, Lcr_z_mm
