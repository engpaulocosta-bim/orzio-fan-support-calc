"""Fase 3 — análise modal 2.5D e verificação de ressonância.

Resolve o problema de valores próprios generalizado K·φ = ω²·M·φ para obter a
primeira frequência própria f1 da grelha, e verifica se f1 está fora da faixa
proibida [0.7, 1.3]×f_excitação (VDI 3840 / boas práticas de equipamento rotativo).

Abordagem de massa: lumped diagonal restrita aos DOFs verticais (w).
  - Cada nó tem 3 GL: [w, rx, ry]. Apenas o DOF w (índice 0) transporta massa.
  - As rotações têm inércia desprezável no modelo de grelha plana.
  - A análise modal usa condensação estática de Guyan para eliminar os DOFs
    rotacionais (sem massa) e resolver K_ww·u_w = ω²·M_w·u_w.

Condensação de Guyan (static condensation):
    Particionar K_ff em blocos [K_ww, K_wr; K_rw, K_rr] (w = vertical, r = rotacional).
    K_red = K_ww - K_wr·K_rr⁻¹·K_rw  (rigidez reduzida para DOFs verticais)
    M_red = M_ww                        (massa diagonal — só vertical)
    Resolver K_red·u_w = ω²·M_red·u_w.

Esta condensação é exacta (sem aproximação) para a primeira frequência própria
quando a massa rotacional é zero, que é o caso deste modelo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .grillage import GrillageMember, GrillageNode, GrillageSupport

# Faixa proibida definida na especificação: ±30 % em torno da frequência de excitação.
RESONANCE_BAND_LOW = 0.7
RESONANCE_BAND_HIGH = 1.3


@dataclass(frozen=True)
class ModalAnalysisResult:
    solved: bool
    failed: bool
    failure_reason: str
    first_frequency_hz: float | None
    excitation_frequencies_hz: list[float]
    frequency_ratios: list[float]
    resonance_violated: bool
    violated_excitation_hz: float | None
    warnings: list[str]
    intermediate: dict[str, object]


def _build_vertical_mass_vector(
    nodes: list[GrillageNode],
    members: list[GrillageMember],
    *,
    steel_density_kg_m3: float,
    section_area_m2: float,
    equipment_mass_kg: float,
    loaded_node_ids: list[str],
    node_index: dict[str, int],
) -> np.ndarray:
    """Return the lumped mass for the vertical DOF of each node [kg].

    Output has shape (n_nodes,): one mass per node (only the w DOF).
    """

    mass = np.zeros(len(nodes), dtype=float)

    for member in members:
        ni = node_index.get(member.node_i)
        nj = node_index.get(member.node_j)
        if ni is None or nj is None:
            continue
        node_i = nodes[ni]
        node_j = nodes[nj]
        length_m = math.hypot(node_j.x_m - node_i.x_m, node_j.y_m - node_i.y_m)
        member_mass_kg = steel_density_kg_m3 * section_area_m2 * length_m
        mass[ni] += member_mass_kg / 2.0
        mass[nj] += member_mass_kg / 2.0

    equipment_share_kg = equipment_mass_kg / max(1, len(loaded_node_ids))
    for nid in loaded_node_ids:
        idx = node_index.get(nid)
        if idx is not None:
            mass[idx] += equipment_share_kg

    return mass


def run_modal_analysis(
    *,
    nodes: list[GrillageNode],
    members: list[GrillageMember],
    supports: list[GrillageSupport],
    loaded_node_ids: list[str],
    stiffness_ff: np.ndarray,
    free_dofs: list[int],
    steel_density_kg_m3: float,
    section_area_m2: float,
    equipment_mass_kg: float,
    excitation_frequencies_hz: list[float],
) -> ModalAnalysisResult:
    """Compute the first natural frequency and check against the prohibited resonance band.

    Parameters
    ----------
    stiffness_ff:
        Condensed free-DOF stiffness sub-matrix [kN/m] from the grillage solver.
    free_dofs:
        List of free global DOF indices (3 per node: 3*i, 3*i+1, 3*i+2).
    steel_density_kg_m3:
        Material density for self-weight mass contribution.
    section_area_m2:
        Cross-section area for linear mass of each member.
    equipment_mass_kg:
        Total equipment mass (all fan units) applied at loaded_node_ids.
    excitation_frequencies_hz:
        One or more excitation frequencies. Must not be empty.
    """

    if not excitation_frequencies_hz:
        return ModalAnalysisResult(
            solved=False,
            failed=True,
            failure_reason="modal_no_excitation_frequency",
            first_frequency_hz=None,
            excitation_frequencies_hz=[],
            frequency_ratios=[],
            resonance_violated=False,
            violated_excitation_hz=None,
            warnings=["Nenhuma frequência de excitação fornecida — análise modal não executada."],
            intermediate={},
        )

    node_index = {node.id: i for i, node in enumerate(nodes)}

    restrained_global: set[int] = set()
    for support in supports:
        if support.node_id not in node_index:
            continue
        base = node_index[support.node_id] * 3
        if support.w:
            restrained_global.add(base)
        if support.rx:
            restrained_global.add(base + 1)
        if support.ry:
            restrained_global.add(base + 2)

    # Identify vertical free DOFs (global DOF index = node_index * 3 + 0).
    # We need their local position within free_dofs for sub-matrix extraction.
    free_set = set(free_dofs)
    free_local_of_global = {gdof: lidx for lidx, gdof in enumerate(free_dofs)}

    vertical_free_global = [
        node_index[node.id] * 3 for node in nodes if node_index[node.id] * 3 in free_set
    ]
    rotational_free_global = [dof for dof in free_dofs if dof not in set(vertical_free_global)]

    if not vertical_free_global:
        return ModalAnalysisResult(
            solved=False,
            failed=True,
            failure_reason="modal_zero_mass",
            first_frequency_hz=None,
            excitation_frequencies_hz=excitation_frequencies_hz,
            frequency_ratios=[],
            resonance_violated=False,
            violated_excitation_hz=None,
            warnings=["Nenhum DOF vertical livre — análise modal não executada."],
            intermediate={},
        )

    # Local indices within stiffness_ff.
    w_local = [free_local_of_global[g] for g in vertical_free_global]
    r_local = [free_local_of_global[g] for g in rotational_free_global]

    # Guyan condensation: K_red = K_ww - K_wr @ inv(K_rr) @ K_rw
    k_ww = stiffness_ff[np.ix_(w_local, w_local)]
    if r_local:
        k_wr = stiffness_ff[np.ix_(w_local, r_local)]
        k_rr = stiffness_ff[np.ix_(r_local, r_local)]
        try:
            k_rr_inv = np.linalg.inv(k_rr)
        except np.linalg.LinAlgError:
            # Fallback: use pseudo-inverse if K_rr is singular
            k_rr_inv = np.linalg.pinv(k_rr)
        k_red = k_ww - k_wr @ k_rr_inv @ k_wr.T
    else:
        k_red = k_ww

    # Force symmetry.
    k_red = (k_red + k_red.T) / 2.0

    # Lumped mass for vertical DOFs only.
    node_vertical_mass = _build_vertical_mass_vector(
        nodes,
        members,
        steel_density_kg_m3=steel_density_kg_m3,
        section_area_m2=section_area_m2,
        equipment_mass_kg=equipment_mass_kg,
        loaded_node_ids=loaded_node_ids,
        node_index=node_index,
    )

    # Map node mass to the vertical free DOFs (some nodes are restrained).
    m_diag = np.array(
        [
            node_vertical_mass[node_index[nodes[node_index[nid]].id]]
            for nid in [
                nodes[node_index_reverse].id
                for node_index_reverse, gdof in enumerate(node_index[node.id] * 3 for node in nodes)
                if gdof in set(vertical_free_global)
            ]
        ],
        dtype=float,
    )

    # Simpler: build mass directly from free vertical dofs
    free_vertical_node_indices = [
        node_index[node.id] for node in nodes if node_index[node.id] * 3 in free_set
    ]
    m_diag = node_vertical_mass[free_vertical_node_indices]

    positive_mass = m_diag[m_diag > 0.0]
    if len(positive_mass) == 0:
        return ModalAnalysisResult(
            solved=False,
            failed=True,
            failure_reason="modal_zero_mass",
            first_frequency_hz=None,
            excitation_frequencies_hz=excitation_frequencies_hz,
            frequency_ratios=[],
            resonance_violated=False,
            violated_excitation_hz=None,
            warnings=["Massa efetiva nula — análise modal não executada."],
            intermediate={},
        )

    # Convert K from kN/m to N/m for SI-consistent eigenvalue (ω² in rad²/s²).
    k_red_si = k_red * 1_000.0

    # Regularise zero-mass entries (should not occur for loaded grillages, but defensive).
    min_mass = float(np.min(positive_mass))
    m_reg = np.where(m_diag > 0.0, m_diag, min_mass * 1e-6)

    # Scale to standard symmetric eigenvalue problem.
    m_inv_sqrt = 1.0 / np.sqrt(m_reg)
    k_scaled = (m_inv_sqrt[:, None] * k_red_si) * m_inv_sqrt[None, :]
    k_scaled = (k_scaled + k_scaled.T) / 2.0

    try:
        eigenvalues = np.linalg.eigvalsh(k_scaled)
    except np.linalg.LinAlgError as exc:
        return ModalAnalysisResult(
            solved=False,
            failed=True,
            failure_reason="modal_eigensolver_failed",
            first_frequency_hz=None,
            excitation_frequencies_hz=excitation_frequencies_hz,
            frequency_ratios=[],
            resonance_violated=False,
            violated_excitation_hz=None,
            warnings=[f"Solver de valores próprios falhou: {exc}"],
            intermediate={},
        )

    positive_eigenvalues = eigenvalues[eigenvalues > 0.0]
    if len(positive_eigenvalues) == 0:
        return ModalAnalysisResult(
            solved=False,
            failed=True,
            failure_reason="modal_no_positive_eigenvalue",
            first_frequency_hz=None,
            excitation_frequencies_hz=excitation_frequencies_hz,
            frequency_ratios=[],
            resonance_violated=False,
            violated_excitation_hz=None,
            warnings=["Nenhum valor próprio positivo — modelo modal singular."],
            intermediate={},
        )

    omega1_sq = float(positive_eigenvalues[0])
    omega1 = math.sqrt(omega1_sq)
    f1_hz = omega1 / (2.0 * math.pi)

    ratios = [f1_hz / f_exc for f_exc in excitation_frequencies_hz]
    violated_hz: float | None = None
    for f_exc, ratio in zip(excitation_frequencies_hz, ratios, strict=True):
        if RESONANCE_BAND_LOW <= ratio <= RESONANCE_BAND_HIGH:
            violated_hz = f_exc
            break

    total_structural_mass_kg = float(np.sum(node_vertical_mass))
    total_equipment_mass_kg = equipment_mass_kg

    return ModalAnalysisResult(
        solved=True,
        failed=False,
        failure_reason="",
        first_frequency_hz=round(f1_hz, 4),
        excitation_frequencies_hz=excitation_frequencies_hz,
        frequency_ratios=[round(r, 4) for r in ratios],
        resonance_violated=violated_hz is not None,
        violated_excitation_hz=violated_hz,
        warnings=[],
        intermediate={
            "omega1_rad_s": round(omega1, 4),
            "total_structural_mass_kg": round(total_structural_mass_kg, 2),
            "total_equipment_mass_kg": round(total_equipment_mass_kg, 2),
            "total_effective_mass_kg": round(total_structural_mass_kg + total_equipment_mass_kg, 2),
            "n_free_vertical_dofs": len(vertical_free_global),
            "n_positive_eigenvalues": int(len(positive_eigenvalues)),
            "resonance_band_low": RESONANCE_BAND_LOW,
            "resonance_band_high": RESONANCE_BAND_HIGH,
        },
    )
