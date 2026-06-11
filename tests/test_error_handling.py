"""Excepções recuperáveis → status; traceback oculto na UI — auditoria H-05/H-08."""

import pytest

from sfsc.engines.selector import run_full_calculation
from sfsc.enums import (
    CantileverSubtype,
    CheckerStatus,
    Country,
    FanType,
    OperationMode,
    SectionFamily,
    SupportType,
)
from sfsc.exceptions import OutOfScopeError
from sfsc.models import FanSupportInput, FanUnit


def _inp(**kwargs):
    defaults = dict(
        project_name="Err",
        support_tag="FSU-X",
        fan_units=[
            FanUnit(
                fan_type=FanType.CENTRIFUGAL,
                weight_kg=120.0,
                operating_weight_kg=130.0,
                footprint_length_mm=800.0,
                footprint_width_mm=600.0,
            )
        ],
        support_type=SupportType.HANGER,
        country=Country.PORTUGAL,
        seismic_zone="1.3",
        installation_height_mm=500.0,
        span_mm=1200.0,
    )
    defaults.update(kwargs)
    return FanSupportInput(**defaults)


def test_no_passing_section_becomes_out_of_scope_status():
    """Nenhum perfil UPN aguenta 950 kg em consola de 6 m → em vez de explodir,
    o cálculo termina com status OUT_OF_SCOPE e warning W-SCOPE-001."""
    inp = _inp(
        support_type=SupportType.CANTILEVER_1,
        cantilever_subtype=CantileverSubtype.PURE,
        span_mm=6000.0,
        preferred_section_families=[SectionFamily.UPN],
        confirm_extended_range=True,
        fan_units=[
            FanUnit(
                fan_type=FanType.CENTRIFUGAL,
                weight_kg=900.0,
                operating_weight_kg=950.0,
                footprint_length_mm=1500.0,
                footprint_width_mm=1200.0,
            )
        ],
    )
    ctx = run_full_calculation(inp)
    res = ctx.fan_support_result
    assert res.status == CheckerStatus.OUT_OF_SCOPE
    assert res.recommended_section is None
    assert any(w.code == "W-SCOPE-001" for w in ctx.warnings)


def test_unknown_section_in_verify_becomes_dataset_missing():
    """VERIFY com perfil inexistente → status DATASET_MISSING (não excepção)."""
    inp = _inp(
        operation_mode=OperationMode.VERIFY,
        received_section_family=SectionFamily.HEB,
        received_section_tag="HEB999",
    )
    ctx = run_full_calculation(inp)
    res = ctx.fan_support_result
    assert res.status == CheckerStatus.DATASET_MISSING
    assert res.recommended_section is None
    assert any(w.code == "W-DATASET-001" for w in ctx.warnings)


def test_blocked_weight_raises_out_of_scope():
    """>1000 kg não é recuperável: OutOfScopeError clara antes de calcular."""
    inp = _inp(
        fan_units=[
            FanUnit(
                fan_type=FanType.CENTRIFUGAL,
                weight_kg=1400.0,
                operating_weight_kg=1500.0,
                footprint_length_mm=2000.0,
                footprint_width_mm=1500.0,
            )
        ],
        confirm_extended_range=True,
    )
    with pytest.raises(OutOfScopeError):
        run_full_calculation(inp)


def test_invalid_seismic_zone_falls_back_with_warning():
    """Zona inválida → zona default com warning W-SEISMIC-002 (não silencioso)."""
    ctx = run_full_calculation(_inp(seismic_zone="ZONA_INEXISTENTE"))
    assert any(w.code == "W-SEISMIC-002" for w in ctx.warnings)


def test_ui_domain_error_shown_without_traceback():
    """UI: peso bloqueado → mensagem de erro de domínio, sem traceback."""
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file("app.py", default_timeout=60)
    app.run()
    op_weight = [f for f in app.number_input if "Peso operação" in f.label][0]
    op_weight.set_value(1500.0)
    calc = [b for b in app.button if "Calcular" in b.label][0]
    calc.click()
    app.run()
    assert not app.exception  # a app não rebenta
    errors = " ".join(e.value for e in app.error)
    assert "OUT_OF_SCOPE" in errors  # código de domínio visível
    assert "Traceback" not in errors


def test_ui_invalid_operating_weight_message():
    """UI: peso operação < peso vazio → mensagem de input inválido amigável."""
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file("app.py", default_timeout=60)
    app.run()
    op_weight = [f for f in app.number_input if "Peso operação" in f.label][0]
    op_weight.set_value(50.0)  # peso vazio default = 120 → inválido
    calc = [b for b in app.button if "Calcular" in b.label][0]
    calc.click()
    app.run()
    assert not app.exception
    errors = " ".join(e.value for e in app.error)
    assert "Input inválido" in errors or "weight_kg" in errors
