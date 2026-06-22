"""Motor de posicionamento do array de ventiladores na grelha 2.5D.

Converte um ``FanArray`` (linhas × colunas, passo, unidade-padrão) numa lista de
cargas pontuais posicionadas nos nós da grelha mais próximos de cada ventilador.

A carga de cada unidade é aplicada ao **nó da grelha mais próximo** (critério de
distância euclidiana). Quando a posição cai exactamente entre quatro nós (painel
central), a carga é distribuída pelos quatro nós em proporção inversa à distância
(interpolação bilinear). Isto reproduz fielmente o comportamento de uma carga
pontual na superfície da grelha sem necessitar de elementos de carga finita.

Compatibilidade com o comportamento legado:
  - Quando ``FanArray`` não está presente, usa ``_centre_loaded_nodes`` (carga
    no(s) nó(s) central(is) mais próximo(s) da grelha), que é o comportamento
    original de ``_platform_grillage_geometry``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..models import FanArray
from .grillage import GrillageNode, GrillagePointLoad


@dataclass(frozen=True)
class FanPosition:
    """Posição de uma unidade do array na plataforma [mm relativamente ao canto 0,0]."""

    unit_index: int
    row: int
    column: int
    x_mm: float
    y_mm: float
    operating_weight_kg: float


def array_unit_positions(
    fan_array: FanArray,
    platform_length_mm: float,
    platform_width_mm: float,
) -> list[FanPosition]:
    """Calcula as posições absolutas [mm] de cada unidade do array na plataforma.

    A origem (0,0) é o canto frontal-esquerdo da plataforma.
    O centro do array coincide com o centro da plataforma mais os offsets.
    """
    n_rows = fan_array.rows
    n_cols = fan_array.columns
    pitch_x = fan_array.column_pitch_mm
    pitch_y = fan_array.row_pitch_mm

    # Centro do array na plataforma
    cx = platform_length_mm / 2.0 + fan_array.offset_x_mm
    cy = platform_width_mm / 2.0 + fan_array.offset_y_mm

    # Posição do canto (0,0) do array (unidade [0][0])
    origin_x = cx - (n_cols - 1) * pitch_x / 2.0
    origin_y = cy - (n_rows - 1) * pitch_y / 2.0

    positions: list[FanPosition] = []
    idx = 0
    for row in range(n_rows):
        for col in range(n_cols):
            positions.append(
                FanPosition(
                    unit_index=idx,
                    row=row,
                    column=col,
                    x_mm=origin_x + col * pitch_x,
                    y_mm=origin_y + row * pitch_y,
                    operating_weight_kg=fan_array.unit.operating_weight_kg,
                )
            )
            idx += 1
    return positions


def _nearest_node(
    x_m: float,
    y_m: float,
    nodes: list[GrillageNode],
) -> str:
    """Devolve o id do nó mais próximo de (x_m, y_m)."""
    best_id = nodes[0].id
    best_d2 = math.inf
    for node in nodes:
        d2 = (node.x_m - x_m) ** 2 + (node.y_m - y_m) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_id = node.id
    return best_id


def _bilinear_weights(
    x_m: float,
    y_m: float,
    nodes: list[GrillageNode],
) -> list[tuple[str, float]]:
    """Distribuição bilinear da carga pelos 4 nós do painel que contém (x_m, y_m).

    Devolve lista de (node_id, weight) com soma = 1.0.
    Usa o nó mais próximo se a interpolação falhar (e.g. posição fora da grelha).
    """
    # Encontra os x e y únicos ordenados
    xs = sorted({round(n.x_m, 9) for n in nodes})
    ys = sorted({round(n.y_m, 9) for n in nodes})

    # Clamp à grelha
    x_m = max(xs[0], min(xs[-1], x_m))
    y_m = max(ys[0], min(ys[-1], y_m))

    # Encontra o painel envolvente
    ix = next((i for i in range(len(xs) - 1) if xs[i] <= x_m <= xs[i + 1]), len(xs) - 2)
    iy = next((i for i in range(len(ys) - 1) if ys[i] <= y_m <= ys[i + 1]), len(ys) - 2)

    x0, x1 = xs[ix], xs[ix + 1]
    y0, y1 = ys[iy], ys[iy + 1]
    dx = x1 - x0
    dy = y1 - y0

    if dx < 1e-12 or dy < 1e-12:
        return [(_nearest_node(x_m, y_m, nodes), 1.0)]

    tx = (x_m - x0) / dx
    ty = (y_m - y0) / dy

    # Pesos bilineares para os 4 cantos
    w00 = (1.0 - tx) * (1.0 - ty)
    w10 = tx * (1.0 - ty)
    w01 = (1.0 - tx) * ty
    w11 = tx * ty

    node_map = {(round(n.x_m, 9), round(n.y_m, 9)): n.id for n in nodes}
    result: list[tuple[str, float]] = []
    for (nx, ny), w in (
        ((x0, y0), w00),
        ((x1, y0), w10),
        ((x0, y1), w01),
        ((x1, y1), w11),
    ):
        nid = node_map.get((nx, ny))
        if nid is not None and w > 1e-12:
            result.append((nid, w))

    if not result:
        return [(_nearest_node(x_m, y_m, nodes), 1.0)]
    return result


def build_array_point_loads(
    fan_array: FanArray,
    nodes: list[GrillageNode],
    platform_length_mm: float,
    platform_width_mm: float,
    total_load_kN: float,
) -> tuple[list[GrillagePointLoad], list[str]]:
    """Constrói as cargas pontuais da grelha para um array de ventiladores.

    Args:
        fan_array: Configuração do array.
        nodes: Lista de nós da grelha.
        platform_length_mm: Comprimento da plataforma [mm].
        platform_width_mm: Largura da plataforma [mm].
        total_load_kN: Carga vertical total a aplicar [kN].

    Returns:
        (loads, loaded_node_ids): Cargas pontuais e ids de nós com carga.
    """

    positions = array_unit_positions(fan_array, platform_length_mm, platform_width_mm)
    total_mass = sum(p.operating_weight_kg for p in positions)

    # Acumula carga por nó (proporcional à massa de cada ventilador)
    node_loads: dict[str, float] = {}
    for pos in positions:
        unit_fraction = (
            pos.operating_weight_kg / total_mass if total_mass > 0 else 1.0 / len(positions)
        )
        unit_kN = total_load_kN * unit_fraction
        x_m = pos.x_mm / 1000.0
        y_m = pos.y_mm / 1000.0
        weights = _bilinear_weights(x_m, y_m, nodes)
        for node_id, w in weights:
            node_loads[node_id] = node_loads.get(node_id, 0.0) + unit_kN * w

    loads = [
        GrillagePointLoad(node_id=nid, downward_kN=load_kN)
        for nid, load_kN in node_loads.items()
        if load_kN > 1e-9
    ]
    loaded_node_ids = [nid for nid, _ in node_loads.items() if node_loads.get(nid, 0.0) > 1e-9]
    return loads, loaded_node_ids


def build_centre_point_loads(
    nodes: list[GrillageNode],
    platform_length_mm: float,
    platform_width_mm: float,
    total_load_kN: float,
    eccentricity_moment_kNm: float = 0.0,
) -> tuple[list[GrillagePointLoad], list[str]]:
    """Carga no(s) nó(s) central(is) — comportamento legado (sem array).

    Mantém retrocompatibilidade com o código existente em global_frame.py.
    """
    length_m = platform_length_mm / 1000.0
    width_m = platform_width_mm / 1000.0
    cx, cy = length_m / 2.0, width_m / 2.0

    centre_distance = min((node.x_m - cx) ** 2 + (node.y_m - cy) ** 2 for node in nodes)
    loaded_node_ids = [
        node.id
        for node in nodes
        if abs((node.x_m - cx) ** 2 + (node.y_m - cy) ** 2 - centre_distance) <= 1e-12
    ]
    load_share_kN = total_load_kN / len(loaded_node_ids)
    loads = [
        GrillagePointLoad(
            node_id=nid,
            downward_kN=load_share_kN,
            moment_y_kNm=eccentricity_moment_kNm / len(loaded_node_ids),
        )
        for nid in loaded_node_ids
    ]
    return loads, loaded_node_ids


def array_loaded_node_ids_for_modal(
    fan_array: FanArray,
    nodes: list[GrillageNode],
    platform_length_mm: float,
    platform_width_mm: float,
) -> list[str]:
    """Nós onde a massa do array deve ser aplicada para análise modal.

    Devolve a lista de nós mais próximos de cada ventilador (sem duplicados).
    A massa de cada ventilador é atribuída ao nó mais próximo.
    """
    positions = array_unit_positions(fan_array, platform_length_mm, platform_width_mm)
    seen: set[str] = set()
    result: list[str] = []
    for pos in positions:
        x_m = pos.x_mm / 1000.0
        y_m = pos.y_mm / 1000.0
        nid = _nearest_node(x_m, y_m, nodes)
        if nid not in seen:
            seen.add(nid)
            result.append(nid)
    return result
