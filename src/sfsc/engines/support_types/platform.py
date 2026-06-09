"""PLATFORM — plataforma / mesa de grelha com N vigas paralelas.

A mesa é uma grelha de ``N`` vigas paralelas (mínimo 2 — as duas bordas) que
correm na direcção do vão, com piso de tramex. A carga vertical total reparte-se
igualmente pelas ``N`` vigas. O apoio pode ser:

* **PURE** (sem mão-francesa): a mesa apoia-se em duas extremidades — cada viga
  comporta-se como biapoiada de vão ``L`` sob carga distribuída → ``M = qL²/8``.
* **BRACKETED** (com mão-francesa): bordo engastado na estrutura + diagonais a
  ``θ = atan(h/L)``. A diagonal escora a ponta livre; modelo de viga em consola
  com apoio elástico na ponta — adopta-se o modelo de propped cantilever, cujo
  momento máximo é ``qL²/8`` (no engaste), com a diagonal a equilibrar a reacção
  da ponta. As diagonais introduzem compressão na viga e ficam elas próprias
  comprimidas — verificadas à parte.

O número de diagonais iguala o número de vigas (uma mão-francesa por viga, nas
duas bordas e nas intermédias), pelo que a carga axial reparte-se igualmente.
"""
from __future__ import annotations
import math
from dataclasses import dataclass

from ...models import FanSupportInput, LoadCombination
from ...enums import StructuralCode, CantileverSubtype
from ...units import mm_to_m


@dataclass(frozen=True)
class PlatformBreakdown:
    """Esforços derivados do modelo de plataforma (para o selector / relatório)."""
    n_beams: int
    braced: bool
    load_per_beam_kN: float        # carga vertical por viga (já majorada)
    moment_per_beam_kNm: float
    axial_per_beam_kN: float       # compressão induzida pelas diagonais na viga
    diagonal_force_kN: float       # esforço axial por diagonal (compressão +)
    diagonal_angle_deg: float
    diagonal_length_mm: float
    Lcr_y_mm: float
    Lcr_z_mm: float


def compute_platform_breakdown(
    inp: FanSupportInput,
    combinations: list[LoadCombination],
) -> PlatformBreakdown:
    """Reparte a carga pelas N vigas e calcula os esforços do modelo de grelha."""
    L_mm = inp.span_mm
    L_m  = mm_to_m(L_mm)
    h_mm = inp.installation_height_mm
    h_m  = mm_to_m(h_mm)
    n_beams = max(2, inp.platform_n_beams)
    braced = inp.cantilever_subtype == CantileverSubtype.BRACKETED

    governing = max(combinations, key=lambda c: abs(c.V_z_kN))
    P_kN = abs(governing.V_z_kN)          # carga vertical total da mesa
    H_kN = abs(governing.V_y_kN)          # carga horizontal (sismo)

    # ── Reparte a carga vertical pelas N vigas ────────────────────────────────
    P_beam_kN = P_kN / n_beams
    # Carga distribuída ao longo do vão de cada viga.
    q_kNm = P_beam_kN / L_m if L_m > 0 else 0.0

    if braced:
        # Propped cantilever (engaste no bordo + apoio na ponta via diagonal):
        # M_max no engaste = q L² / 8.
        M_beam_kNm = q_kNm * L_m**2 / 8.0
        theta = math.atan2(h_m, L_m) if L_m > 0 else math.pi / 4.0
        # Reacção da ponta (apoio simples do propped cantilever) = 3qL/8.
        R_tip_kN = 3.0 * q_kNm * L_m / 8.0 if L_m > 0 else 0.0
        # Esforço na diagonal que materializa esse apoio (uma por viga).
        F_diag_kN = R_tip_kN / math.sin(theta) if math.sin(theta) > 1e-6 else R_tip_kN
        # Componente horizontal da diagonal → compressão na viga.
        N_beam_kN = R_tip_kN / math.tan(theta) if math.tan(theta) > 1e-6 else 0.0
        diag_len_mm = math.hypot(L_mm, h_mm)
        Lcr_y_mm = L_mm
        Lcr_z_mm = L_mm
    else:
        # Mesa biapoiada nas duas extremidades: viga simplesmente apoiada.
        M_beam_kNm = q_kNm * L_m**2 / 8.0
        theta = 0.0
        F_diag_kN = 0.0
        N_beam_kN = 0.0
        diag_len_mm = 0.0
        Lcr_y_mm = L_mm
        Lcr_z_mm = 0.5 * L_mm

    # Acréscimo de momento por sismo horizontal sobre a altura da mesa,
    # distribuído pelas vigas.
    M_seismic_kNm = (H_kN * h_m) / n_beams if h_m > 0 else 0.0
    M_beam_kNm += M_seismic_kNm

    return PlatformBreakdown(
        n_beams=n_beams,
        braced=braced,
        load_per_beam_kN=round(P_beam_kN, 4),
        moment_per_beam_kNm=round(M_beam_kNm, 4),
        axial_per_beam_kN=round(N_beam_kN, 4),
        diagonal_force_kN=round(F_diag_kN, 4),
        diagonal_angle_deg=round(math.degrees(theta), 2),
        diagonal_length_mm=round(diag_len_mm, 1),
        Lcr_y_mm=Lcr_y_mm,
        Lcr_z_mm=Lcr_z_mm,
    )


def calc_platform(
    inp: FanSupportInput,
    total_weight_kN: float,
    combinations: list[LoadCombination],
    code: StructuralCode,
) -> tuple[LoadCombination, float, float]:
    """Esforços de dimensionamento de UMA viga da grelha (a mais carregada)."""
    bd = compute_platform_breakdown(inp, combinations)
    governing = max(combinations, key=lambda c: abs(c.V_z_kN))

    # Corte de cada viga biapoiada/propped: V ≈ carga da viga / 2.
    V_beam_kN = bd.load_per_beam_kN / 2.0

    desc = (
        f"Plataforma (grelha) {bd.n_beams} vigas — "
        f"{'com mão-francesa' if bd.braced else 'sem mão-francesa'} — "
        f"P/viga={bd.load_per_beam_kN:.2f} kN M/viga={bd.moment_per_beam_kNm:.2f} kNm"
    )
    if bd.braced:
        desc += (
            f" | diagonal θ={bd.diagonal_angle_deg:.1f}° "
            f"F_diag={bd.diagonal_force_kN:.2f} kN N_viga={bd.axial_per_beam_kN:.2f} kN"
        )

    updated = LoadCombination(
        name=governing.name,
        N_kN=bd.axial_per_beam_kN,
        V_z_kN=V_beam_kN,
        V_y_kN=governing.V_y_kN / bd.n_beams,
        M_y_kNm=bd.moment_per_beam_kNm,
        governing=True,
        load_factors_used={
            **governing.load_factors_used,
            "n_beams": bd.n_beams,
            "load_per_beam_kN": bd.load_per_beam_kN,
            "diagonal_force_kN": bd.diagonal_force_kN,
        },
        description=desc,
    )
    return updated, bd.Lcr_y_mm, bd.Lcr_z_mm
