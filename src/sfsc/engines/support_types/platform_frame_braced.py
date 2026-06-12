"""PLATFORM_FRAME_BRACED — plataforma metálica com quadro superior e escoras.

Modelo recomendado para casos tipo Robot: quadro metálico superior (vigas +
travessas) com tramex/grelha, contraventado por escoras/diagonais inferiores
ligadas a estrutura existente.

Modelo simplificado:
  - Viga superior dimensionante: biapoiada, carga vertical central → M = P·L/4;
    soma o peso próprio da superfície (tramex) como carga distribuída.
  - Diagonais/escoras absorvem a acção horizontal (axial nas escoras), pelo que
    o momento de eixo fraco na viga é pequeno (quadro contraventado).
  - Encurvadura: Lcr_y = L (viga), Lcr_z = 0.5·L (travado pelas travessas).
"""

from __future__ import annotations

from ...enums import StructuralCode
from ...models import FanSupportInput, LoadCombination
from ...units import mm_to_m


def _surface_line_load_kN_m(inp: FanSupportInput) -> float:
    """Peso próprio da superfície (tramex/chapa) como carga linear na viga [kN/m]."""
    surf = inp.walking_surface
    if surf.self_weight_kn_m2 <= 0:
        return 0.0
    # Largura tributária ≈ footprint da 1ª unidade (m).
    trib_w_m = mm_to_m(inp.fan_units[0].footprint_width_mm) if inp.fan_units else 0.6
    return surf.self_weight_kn_m2 * trib_w_m


def _member_forces(inp: FanSupportInput, c: LoadCombination) -> LoadCombination:
    L_m = mm_to_m(inp.span_mm)
    e_m = mm_to_m(inp.eccentricity_mm)
    P_kN = c.V_z_kN
    H_kN = abs(c.V_y_kN)

    # Momento da viga superior: carga central + peso próprio da superfície + excentricidade.
    M_central = P_kN * L_m / 4.0
    q_surface = _surface_line_load_kN_m(inp)
    M_surface = q_surface * L_m**2 / 8.0
    M_y_kNm = M_central + M_surface + abs(P_kN) * e_m

    # Acção horizontal nas escoras (axial) → momento de eixo fraco residual pequeno.
    M_z_kNm = H_kN * L_m / 8.0
    # Compressão indicativa nas escoras diagonais (45°): N ≈ H/cos45.
    N_brace_kN = H_kN * 1.414

    return LoadCombination(
        name=c.name,
        N_kN=N_brace_kN,
        V_z_kN=P_kN / 2.0,  # a viga partilha com a travessa
        V_y_kN=c.V_y_kN,
        M_y_kNm=M_y_kNm,
        M_z_kNm=M_z_kNm,
        member_level=True,
        load_factors_used=c.load_factors_used,
        description=(
            f"Plataforma contraventada L={L_m:.2f}m M_viga={M_y_kNm:.2f} kNm "
            f"N_escora={N_brace_kN:.2f} kN q_tramex={q_surface:.2f} kN/m"
        ),
    )


def calc_platform_frame_braced(
    inp: FanSupportInput,
    total_weight_kN: float,
    combinations: list[LoadCombination],
    code: StructuralCode,
) -> tuple[list[LoadCombination], float, float]:
    """Transforma todas as combinações em esforços na viga superior dimensionante."""
    member_combos = [_member_forces(inp, c) for c in combinations]
    L_mm = inp.span_mm
    Lcr_y_mm = L_mm
    Lcr_z_mm = 0.5 * L_mm
    return member_combos, Lcr_y_mm, Lcr_z_mm
