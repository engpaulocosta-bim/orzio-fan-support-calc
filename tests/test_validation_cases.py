"""Runner da biblioteca de casos de validação (validation_cases/).

Cada caso tem input.json (FanSupportInput), expected.json (valores + tolerâncias)
e memoria.md (cálculo manual independente que justifica os valores esperados).

Divergência fora da tolerância = regressão numérica: investigar a causa e,
se a mudança for intencional, recalcular a memória manual antes de atualizar
o expected.json.
"""

import json
from pathlib import Path

import pytest

from sfsc.engines.selector import run_full_calculation
from sfsc.models import FanSupportInput

CASES_DIR = Path(__file__).parent.parent / "validation_cases"
CASE_DIRS = sorted(p for p in CASES_DIR.iterdir() if p.is_dir())


def _load(case_dir: Path):
    inp = FanSupportInput.model_validate_json((case_dir / "input.json").read_text(encoding="utf-8"))
    doc = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
    return inp, doc["expected"], doc["tolerances"]


@pytest.mark.parametrize("case_dir", CASE_DIRS, ids=lambda p: p.name)
def test_validation_case(case_dir: Path):
    assert (case_dir / "memoria.md").exists(), (
        f"{case_dir.name}: falta memoria.md — valores esperados sem justificação manual"
    )

    inp, expected, tol = _load(case_dir)
    res = run_full_calculation(inp).fan_support_result
    assert res is not None

    assert res.design_load_kN == pytest.approx(
        expected["design_load_kN"], rel=tol["design_load_kN_rel"]
    )

    assert res.governing_load_combination is not None
    assert res.governing_load_combination.name == expected["governing_combination"]

    assert res.recommended_section is not None
    assert res.recommended_section.designation == expected["section"]

    assert res.section_verification is not None
    assert res.section_verification.utilization_ratio == pytest.approx(
        expected["utilization_ratio"], rel=tol["utilization_ratio_rel"]
    )
    assert res.section_verification.governing_check == expected["governing_check"]

    assert res.status.value == expected["status"]
    assert res.classification_level.value == expected["classification"]

    assert res.anchor is not None
    assert res.anchor.anchor_type == expected["anchor_type"]
    if "anchor_utilization_tension" in expected:
        assert res.anchor.utilization_tension == pytest.approx(
            expected["anchor_utilization_tension"], abs=tol["anchor_utilization_tension_abs"]
        )


def test_inputs_round_trip():
    """Os input.json têm de continuar a desserializar para o modelo actual —
    protege compatibilidade do schema de input."""
    for case_dir in CASE_DIRS:
        inp, _, _ = _load(case_dir)
        # round-trip estável
        again = FanSupportInput.model_validate_json(inp.model_dump_json())
        assert again == inp, f"{case_dir.name}: round-trip JSON instável"
