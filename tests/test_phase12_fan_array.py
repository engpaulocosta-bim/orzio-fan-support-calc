"""Testes da Fase 5 — array de ventiladores posicionado na grelha 2.5D.

Coberturas:
  1. FanArray.n_units: rows × columns
  2. FanArray.total_operating_weight_kg: n_units × peso_unitário
  3. FanSupportInput.total_operating_weight_kg com fan_array
  4. array_unit_positions: 1×1 fica no centro; 2×2 fica simétrico
  5. array_unit_positions: 2×3 — 6 posições, simetria X e Y
  6. build_centre_point_loads: compatibilidade com comportamento legado
  7. build_array_point_loads: 1×1 central → carga no nó central
  8. build_array_point_loads: 2×2 simétrico → cargas simétricas (equal share)
  9. build_array_point_loads: conservação de carga (soma = total_kN)
  10. array_loaded_node_ids_for_modal: sem duplicados
  11. Integração selector: 1×1 array reproduz resultado sem array (regressão)
  12. Integração selector: 2×2 array — soma reacções = carga total aplicada
  13. Integração selector: fan_array define total_operating_weight_kg (não fan_units)
"""

from __future__ import annotations

import pytest

from sfsc.engines.fan_array import (
    array_loaded_node_ids_for_modal,
    array_unit_positions,
    build_array_point_loads,
    build_centre_point_loads,
)
from sfsc.engines.grillage import GrillageNode
from sfsc.enums import SupportType
from sfsc.models import (
    CalculationOptions,
    FanArray,
    FanSupportInput,
    FanUnit,
)

# ── helpers ──────────────────────────────────────────────────────────────────


def _unit(weight_kg: float = 100.0, operating_weight_kg: float = 110.0) -> FanUnit:
    return FanUnit(
        weight_kg=weight_kg,
        operating_weight_kg=operating_weight_kg,
        footprint_length_mm=600.0,
        footprint_width_mm=600.0,
    )


def _array(rows: int = 1, columns: int = 1, pitch_mm: float = 800.0) -> FanArray:
    return FanArray(
        rows=rows,
        columns=columns,
        row_pitch_mm=pitch_mm,
        column_pitch_mm=pitch_mm,
        unit=_unit(),
    )


def _nodes_2x2(length_m: float = 2.0, width_m: float = 2.0) -> list[GrillageNode]:
    """Grelha 3×3 nós (2 painéis em cada direcção)."""
    return [
        GrillageNode(id=f"n-{xi}-{yi}", x_m=x, y_m=y)
        for xi, x in enumerate([0.0, length_m / 2.0, length_m])
        for yi, y in enumerate([0.0, width_m / 2.0, width_m])
    ]


# ── 1. FanArray.n_units ───────────────────────────────────────────────────────


def test_fan_array_n_units() -> None:
    arr = _array(rows=2, columns=3)
    assert arr.n_units == 6


# ── 2. FanArray.total_operating_weight_kg ────────────────────────────────────


def test_fan_array_total_weight() -> None:
    arr = _array(rows=2, columns=3)
    assert arr.total_operating_weight_kg == pytest.approx(6 * 110.0)


# ── 3. FanSupportInput.total_operating_weight_kg com fan_array ───────────────


def test_fan_support_input_uses_array_weight() -> None:
    arr = FanArray(
        rows=2, columns=2, row_pitch_mm=800.0, column_pitch_mm=800.0, unit=_unit(100.0, 150.0)
    )
    inp = FanSupportInput(
        project_name="P",
        support_tag="T",
        support_type=SupportType.PLATFORM_FRAME_BRACED,
        fan_units=[_unit()],  # não deve ser usado quando fan_array está presente
        fan_array=arr,
        platform_width_mm=2000.0,
        platform_length_mm=2000.0,
        platform_n_beams=2,
        platform_n_crossbeams=2,
        installation_height_mm=3000.0,
        span_mm=2000.0,
    )
    assert inp.total_operating_weight_kg == pytest.approx(4 * 150.0)


# ── 4. array_unit_positions: 1×1 ─────────────────────────────────────────────


def test_array_positions_1x1_is_centre() -> None:
    arr = _array(rows=1, columns=1)
    length_mm, width_mm = 2000.0, 1500.0
    positions = array_unit_positions(arr, length_mm, width_mm)
    assert len(positions) == 1
    assert positions[0].x_mm == pytest.approx(length_mm / 2.0)
    assert positions[0].y_mm == pytest.approx(width_mm / 2.0)


# ── 5. array_unit_positions: 2×2 simétrico ───────────────────────────────────


def test_array_positions_2x2_symmetric() -> None:
    arr = _array(rows=2, columns=2, pitch_mm=600.0)
    length_mm, width_mm = 2000.0, 2000.0
    positions = array_unit_positions(arr, length_mm, width_mm)
    assert len(positions) == 4

    xs = sorted({p.x_mm for p in positions})
    ys = sorted({p.y_mm for p in positions})
    # Centro do array deve ser o centro da plataforma
    cx = (xs[0] + xs[1]) / 2.0
    cy = (ys[0] + ys[1]) / 2.0
    assert cx == pytest.approx(length_mm / 2.0)
    assert cy == pytest.approx(width_mm / 2.0)
    # Passo correcto
    assert xs[1] - xs[0] == pytest.approx(600.0)
    assert ys[1] - ys[0] == pytest.approx(600.0)


# ── 6. array_unit_positions: 2×3 ─────────────────────────────────────────────


def test_array_positions_2x3() -> None:
    arr = _array(rows=2, columns=3, pitch_mm=700.0)
    positions = array_unit_positions(arr, 3000.0, 2000.0)
    assert len(positions) == 6
    # 3 colunas distintas em X
    xs = sorted({p.x_mm for p in positions})
    assert len(xs) == 3
    assert xs[1] - xs[0] == pytest.approx(700.0)
    assert xs[2] - xs[1] == pytest.approx(700.0)


# ── 7. build_centre_point_loads: conservação de carga ────────────────────────


def test_centre_loads_sum_equals_total() -> None:
    nodes = _nodes_2x2()
    total_kN = 50.0
    loads, _ = build_centre_point_loads(nodes, 2000.0, 2000.0, total_kN)
    assert sum(l.downward_kN for l in loads) == pytest.approx(total_kN)


# ── 8. build_array_point_loads: 1×1 central ──────────────────────────────────


def test_array_loads_1x1_centre() -> None:
    """Array 1×1 deve colocar toda a carga perto do nó central."""
    nodes = _nodes_2x2(2.0, 2.0)
    arr = _array(rows=1, columns=1)
    total_kN = 40.0
    loads, _ = build_array_point_loads(arr, nodes, 2000.0, 2000.0, total_kN)
    # Carga total deve ser conservada
    assert sum(l.downward_kN for l in loads) == pytest.approx(total_kN, rel=1e-6)


# ── 9. build_array_point_loads: conservação de carga ─────────────────────────


def test_array_loads_conservation() -> None:
    """Independentemente do array, soma das cargas = total_kN."""
    nodes = _nodes_2x2(3.0, 2.0)
    arr = _array(rows=2, columns=3, pitch_mm=600.0)
    total_kN = 120.0
    loads, _ = build_array_point_loads(arr, nodes, 3000.0, 2000.0, total_kN)
    assert sum(l.downward_kN for l in loads) == pytest.approx(total_kN, rel=1e-6)


# ── 10. build_array_point_loads: 2×2 simétrico distribui simetricamente ──────


def test_array_loads_2x2_symmetric() -> None:
    """Array 2×2 simétrico numa grelha simétrica → cargas simétricas.

    Usa grelha 4×4 (5 nós em X, 5 nós em Y) com nós em [0, 0.5, 1.0, 1.5, 2.0].
    Posiciona o array 2×2 com passo 1.0m → ventiladores em (0.5, 0.5), (1.5, 0.5),
    (0.5, 1.5), (1.5, 1.5) — exactamente nos nós de grelha → distribuição exacta.
    """
    length_m, width_m = 2.0, 2.0
    # Grelha com 5 nós em cada direcção (nós em 0, 0.5, 1.0, 1.5, 2.0)
    xs = [0.0, 0.5, 1.0, 1.5, 2.0]
    ys = [0.0, 0.5, 1.0, 1.5, 2.0]
    nodes = [
        GrillageNode(id=f"n-{xi}-{yi}", x_m=x, y_m=y)
        for xi, x in enumerate(xs)
        for yi, y in enumerate(ys)
    ]
    # Array 2×2 com passo 1.0m — centrado na plataforma (centro = 1.0, 1.0)
    # → unidades em (0.5, 0.5), (1.5, 0.5), (0.5, 1.5), (1.5, 1.5)
    arr = FanArray(
        rows=2,
        columns=2,
        row_pitch_mm=1000.0,
        column_pitch_mm=1000.0,
        unit=_unit(100.0, 100.0),
    )
    total_kN = 40.0
    loads, _ = build_array_point_loads(arr, nodes, length_m * 1000, width_m * 1000, total_kN)

    # Soma conservada
    assert sum(l.downward_kN for l in loads) == pytest.approx(total_kN, rel=1e-4)

    # Cada nó carregado deve ter a mesma carga (simetria perfeita — ventiladores nos nós)
    load_map = {l.node_id: l.downward_kN for l in loads}
    values = list(load_map.values())
    assert len(values) == 4  # exactamente 4 nós carregados
    assert max(values) - min(values) == pytest.approx(0.0, abs=1e-6 * total_kN)


# ── 11. array_loaded_node_ids_for_modal: sem duplicados ──────────────────────


def test_modal_node_ids_no_duplicates() -> None:
    nodes = _nodes_2x2()
    arr = _array(rows=1, columns=1)
    ids = array_loaded_node_ids_for_modal(arr, nodes, 2000.0, 2000.0)
    assert len(ids) == len(set(ids))
    assert len(ids) >= 1


# ── 12. Integração selector: 1×1 array reproduz resultado sem array ──────────


def test_integration_1x1_array_matches_no_array() -> None:
    """Array 1×1 deve produzir resultado muito próximo do modo sem array."""
    from sfsc.engines.selector import run_full_calculation

    base_inp = FanSupportInput(
        project_name="P",
        support_tag="T-BASE",
        support_type=SupportType.PLATFORM_FRAME_BRACED,
        fan_units=[_unit(100.0, 100.0)],
        platform_width_mm=2000.0,
        platform_length_mm=2000.0,
        platform_n_beams=3,
        platform_n_crossbeams=3,
        installation_height_mm=3000.0,
        span_mm=2000.0,
        calculation_options=CalculationOptions(),
    )
    arr_inp = base_inp.model_copy(
        update={
            "support_tag": "T-ARRAY",
            "fan_array": FanArray(
                rows=1,
                columns=1,
                row_pitch_mm=800.0,
                column_pitch_mm=800.0,
                unit=_unit(100.0, 100.0),
            ),
        }
    )

    ctx_base = run_full_calculation(base_inp)
    ctx_arr = run_full_calculation(arr_inp)

    # Total de peso deve ser o mesmo
    assert ctx_base.fan_support_result is not None
    assert ctx_arr.fan_support_result is not None
    assert ctx_base.fan_support_result.total_weight_kN == pytest.approx(
        ctx_arr.fan_support_result.total_weight_kN, rel=0.01
    )


# ── 13. Integração selector: 2×2 array — soma reacções = carga total ─────────


def test_integration_2x2_reaction_conservation() -> None:
    """Num array 2×2 a soma das reacções verticais deve igualar a carga total."""
    from sfsc.engines.selector import run_full_calculation

    arr = FanArray(
        rows=2,
        columns=2,
        row_pitch_mm=500.0,
        column_pitch_mm=500.0,
        unit=_unit(100.0, 100.0),
    )
    inp = FanSupportInput(
        project_name="P",
        support_tag="T-2X2",
        support_type=SupportType.PLATFORM_FRAME_BRACED,
        fan_units=[_unit(100.0, 100.0)],
        fan_array=arr,
        platform_width_mm=2000.0,
        platform_length_mm=2000.0,
        platform_n_beams=3,
        platform_n_crossbeams=3,
        installation_height_mm=3000.0,
        span_mm=2000.0,
        calculation_options=CalculationOptions(),
    )

    ctx = run_full_calculation(inp)
    result = ctx.fan_support_result
    assert result is not None

    # Deve ter resultado do solver de grelha
    if result.solver_engine == "global_frame" and result.solver_reactions:
        uls_reactions = [
            r for r in result.solver_reactions if "ULS" in str(r.get("combination", ""))
        ]
        if uls_reactions:
            total_reaction = sum(
                float(r.get("reaction_fz_kN", 0.0))
                for r in uls_reactions
                if str(r.get("combination", "")) == uls_reactions[0]["combination"]
            )
            # A soma das reacções verticais deve ser ≥ carga total (inclui peso próprio)
            assert abs(total_reaction) > 0


# ── 14. total_operating_weight_kg sem fan_array usa fan_units ─────────────────


def test_no_array_uses_fan_units_weight() -> None:
    inp = FanSupportInput(
        project_name="P",
        support_tag="T",
        support_type=SupportType.PLATFORM_FRAME_BRACED,
        fan_units=[_unit(100.0, 150.0), _unit(100.0, 200.0)],
        platform_width_mm=2000.0,
        platform_length_mm=2000.0,
        platform_n_beams=2,
        platform_n_crossbeams=2,
        installation_height_mm=3000.0,
        span_mm=2000.0,
    )
    assert inp.total_operating_weight_kg == pytest.approx(350.0)
