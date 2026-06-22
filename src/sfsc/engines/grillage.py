"""Linear 2.5D grillage solver with vertical displacement and two rotations per node."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_SINGULAR_TOLERANCE = 1e14


@dataclass(frozen=True)
class GrillageNode:
    id: str
    x_m: float
    y_m: float


@dataclass(frozen=True)
class GrillageMember:
    id: str
    node_i: str
    node_j: str
    elastic_modulus_kN_m2: float
    shear_modulus_kN_m2: float
    inertia_m4: float
    torsion_constant_m4: float
    direction: str = "longitudinal"


@dataclass(frozen=True)
class GrillageSupport:
    node_id: str
    w: bool = True
    rx: bool = False
    ry: bool = False


@dataclass(frozen=True)
class GrillagePointLoad:
    node_id: str
    downward_kN: float
    moment_x_kNm: float = 0.0
    moment_y_kNm: float = 0.0


@dataclass(frozen=True)
class GrillageAnalysisResult:
    solved: bool
    failed: bool
    warnings: list[str]
    nodes: list[dict[str, object]]
    members: list[dict[str, object]]
    supports: list[dict[str, object]]
    reactions: list[dict[str, object]]
    displacements: list[dict[str, object]]
    member_end_forces: list[dict[str, object]]


def _local_stiffness(member: GrillageMember, length_m: float) -> np.ndarray:
    """Return the local grid-member matrix for [w, rx, ry] at each end.

    Local ``rx`` is torsion about the member axis. Local ``ry`` is bending
    rotation about the in-plane transverse axis.
    """

    ei = member.elastic_modulus_kN_m2 * member.inertia_m4
    gj_l = member.shear_modulus_kN_m2 * member.torsion_constant_m4 / length_m
    l2 = length_m**2
    l3 = length_m**3
    matrix = np.zeros((6, 6), dtype=float)

    bending_dofs = (0, 2, 3, 5)
    bending = np.array(
        [
            [12.0 * ei / l3, 6.0 * ei / l2, -12.0 * ei / l3, 6.0 * ei / l2],
            [6.0 * ei / l2, 4.0 * ei / length_m, -6.0 * ei / l2, 2.0 * ei / length_m],
            [-12.0 * ei / l3, -6.0 * ei / l2, 12.0 * ei / l3, -6.0 * ei / l2],
            [6.0 * ei / l2, 2.0 * ei / length_m, -6.0 * ei / l2, 4.0 * ei / length_m],
        ],
        dtype=float,
    )
    matrix[np.ix_(bending_dofs, bending_dofs)] = bending
    matrix[1, 1] = gj_l
    matrix[1, 4] = -gj_l
    matrix[4, 1] = -gj_l
    matrix[4, 4] = gj_l
    return matrix


def _transformation(dx_m: float, dy_m: float, length_m: float) -> np.ndarray:
    """Transform global [w, rx, ry] rotations into member-local axes."""

    c = dx_m / length_m
    s = dy_m / length_m
    node_transform = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, c, s],
            [0.0, -s, c],
        ],
        dtype=float,
    )
    transform = np.zeros((6, 6), dtype=float)
    transform[:3, :3] = node_transform
    transform[3:, 3:] = node_transform
    return transform


def _failure(
    message: str,
    nodes: list[GrillageNode],
    members: list[GrillageMember],
    supports: list[GrillageSupport],
) -> GrillageAnalysisResult:
    return GrillageAnalysisResult(
        solved=False,
        failed=True,
        warnings=[message],
        nodes=[{"id": node.id, "x_m": node.x_m, "y_m": node.y_m} for node in nodes],
        members=[
            {
                "id": member.id,
                "node_i": member.node_i,
                "node_j": member.node_j,
                "direction": member.direction,
            }
            for member in members
        ],
        supports=[
            {
                "node_id": support.node_id,
                "w": support.w,
                "rx": support.rx,
                "ry": support.ry,
            }
            for support in supports
        ],
        reactions=[],
        displacements=[],
        member_end_forces=[],
    )


def run_grillage_analysis(
    nodes: list[GrillageNode],
    members: list[GrillageMember],
    supports: list[GrillageSupport],
    loads: list[GrillagePointLoad],
) -> GrillageAnalysisResult:
    """Solve a linear elastic grillage under nodal vertical loads and moments."""

    if not nodes or not members:
        return _failure("Grillage requires nodes and members.", nodes, members, supports)

    node_index = {node.id: index for index, node in enumerate(nodes)}
    if len(node_index) != len(nodes):
        return _failure("Grillage node identifiers must be unique.", nodes, members, supports)

    dof_count = len(nodes) * 3
    stiffness = np.zeros((dof_count, dof_count), dtype=float)
    element_cache: list[tuple[GrillageMember, np.ndarray, np.ndarray, list[int]]] = []

    for member in members:
        if member.node_i not in node_index or member.node_j not in node_index:
            return _failure(
                f"Member '{member.id}' references an unknown node.",
                nodes,
                members,
                supports,
            )
        node_i = nodes[node_index[member.node_i]]
        node_j = nodes[node_index[member.node_j]]
        dx_m = node_j.x_m - node_i.x_m
        dy_m = node_j.y_m - node_i.y_m
        length_m = float(np.hypot(dx_m, dy_m))
        if length_m <= 0.0:
            return _failure(
                f"Member '{member.id}' has zero length.",
                nodes,
                members,
                supports,
            )

        transform = _transformation(dx_m, dy_m, length_m)
        local_stiffness = _local_stiffness(member, length_m)
        global_stiffness = transform.T @ local_stiffness @ transform
        dofs = [
            node_index[member.node_i] * 3,
            node_index[member.node_i] * 3 + 1,
            node_index[member.node_i] * 3 + 2,
            node_index[member.node_j] * 3,
            node_index[member.node_j] * 3 + 1,
            node_index[member.node_j] * 3 + 2,
        ]
        stiffness[np.ix_(dofs, dofs)] += global_stiffness
        element_cache.append((member, transform, local_stiffness, dofs))

    restrained: set[int] = set()
    for support in supports:
        if support.node_id not in node_index:
            return _failure(
                f"Support references unknown node '{support.node_id}'.",
                nodes,
                members,
                supports,
            )
        base = node_index[support.node_id] * 3
        if support.w:
            restrained.add(base)
        if support.rx:
            restrained.add(base + 1)
        if support.ry:
            restrained.add(base + 2)

    free = [dof for dof in range(dof_count) if dof not in restrained]
    if not free:
        return _failure(
            "Grillage has no free degrees of freedom.",
            nodes,
            members,
            supports,
        )

    load_vector = np.zeros(dof_count, dtype=float)
    for load in loads:
        if load.node_id not in node_index:
            return _failure(
                f"Load references unknown node '{load.node_id}'.",
                nodes,
                members,
                supports,
            )
        base = node_index[load.node_id] * 3
        load_vector[base] -= load.downward_kN
        load_vector[base + 1] += load.moment_x_kNm
        load_vector[base + 2] += load.moment_y_kNm

    k_ff = stiffness[np.ix_(free, free)]
    if np.linalg.cond(k_ff) > _SINGULAR_TOLERANCE:
        return _failure(
            "Grillage instability detected.",
            nodes,
            members,
            supports,
        )

    displacement = np.zeros(dof_count, dtype=float)
    displacement[free] = np.linalg.solve(k_ff, load_vector[free])
    reaction = stiffness @ displacement - load_vector

    displacement_rows = []
    for node in nodes:
        base = node_index[node.id] * 3
        displacement_rows.append(
            {
                "node_id": node.id,
                "w_m": float(displacement[base]),
                "rx_rad": float(displacement[base + 1]),
                "ry_rad": float(displacement[base + 2]),
            }
        )

    reaction_rows = []
    for support in supports:
        base = node_index[support.node_id] * 3
        reaction_rows.append(
            {
                "node_id": support.node_id,
                "reaction_fz_kN": float(reaction[base]) if support.w else 0.0,
                "reaction_mx_kNm": float(reaction[base + 1]) if support.rx else 0.0,
                "reaction_my_kNm": float(reaction[base + 2]) if support.ry else 0.0,
            }
        )

    force_rows = []
    for member, transform, local_stiffness, dofs in element_cache:
        local_displacement = transform @ displacement[dofs]
        local_force = local_stiffness @ local_displacement
        force_rows.append(
            {
                "member_id": member.id,
                "member_direction": member.direction,
                "node_i": member.node_i,
                "node_j": member.node_j,
                "V_i_kN": float(local_force[0]),
                "T_i_kNm": float(local_force[1]),
                "M_i_kNm": float(local_force[2]),
                "V_j_kN": float(local_force[3]),
                "T_j_kNm": float(local_force[4]),
                "M_j_kNm": float(local_force[5]),
            }
        )

    return GrillageAnalysisResult(
        solved=True,
        failed=False,
        warnings=[],
        nodes=[{"id": node.id, "x_m": node.x_m, "y_m": node.y_m} for node in nodes],
        members=[
            {
                "id": member.id,
                "node_i": member.node_i,
                "node_j": member.node_j,
                "direction": member.direction,
            }
            for member in members
        ],
        supports=[
            {
                "node_id": support.node_id,
                "w": support.w,
                "rx": support.rx,
                "ry": support.ry,
            }
            for support in supports
        ],
        reactions=reaction_rows,
        displacements=displacement_rows,
        member_end_forces=force_rows,
    )
