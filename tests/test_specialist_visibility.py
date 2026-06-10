"""Visibilidade de REQUIRES_SPECIALIST em todos os outputs — auditoria C-03.

Caso: 540 kg (>500) → classificação REQUIRES_SPECIALIST. A headline tem de
ser "REQUER ESPECIALISTA" (nunca verde) na avaliação, no CSV, no Excel e no PDF.
"""
import base64
import re
import zlib

import pytest
from sfsc.enums import SupportType, Country, FanType, CheckerStatus
from sfsc.models import FanSupportInput, FanUnit
from sfsc.engines.selector import run_full_calculation
from sfsc.assessment import assess_result
from sfsc.reports.exports import generate_csv, generate_excel
from sfsc.reports.memorial_pdf import generate_pdf

HEADLINE = "REQUER ESPECIALISTA"


@pytest.fixture(scope="module")
def specialist_ctx():
    inp = FanSupportInput(
        project_name="Spec", support_tag="FSU-540",
        fan_units=[FanUnit(fan_type=FanType.CENTRIFUGAL, weight_kg=520.0,
                           operating_weight_kg=540.0,
                           footprint_length_mm=1200.0, footprint_width_mm=900.0)],
        support_type=SupportType.HANGER,
        country=Country.PORTUGAL, seismic_zone="1.3",
        installation_height_mm=500.0, span_mm=1200.0,
    )
    return run_full_calculation(inp)


def test_assessment_headline_never_green(specialist_ctx):
    res = specialist_ctx.fan_support_result
    assert res.status == CheckerStatus.PASS  # numericamente passa…
    a = assess_result(res)
    assert a.is_specialist
    assert a.headline == HEADLINE            # …mas a headline nunca é "PASSA - CONSERVADOR"
    assert not a.is_conservative
    assert "engenheiro estrutural" in a.summary


def test_csv_contains_specialist_headline(specialist_ctx):
    csv_str = generate_csv(specialist_ctx)
    assert HEADLINE in csv_str
    assert "REQUIRES_SPECIALIST" in csv_str


def test_excel_summary_contains_specialist_headline(specialist_ctx):
    import io
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(generate_excel(specialist_ctx)))
    values = [
        str(cell.value)
        for row in wb["Resumo"].iter_rows()
        for cell in row if cell.value is not None
    ]
    assert any(HEADLINE in v for v in values)
    assert any("REQUIRES_SPECIALIST" in v for v in values)


def _pdf_text(pdf_bytes: bytes) -> bytes:
    """Extrai texto dos content streams (ASCII85 + Flate do ReportLab)."""
    text = b""
    for m in re.finditer(rb"(?<!end)stream\r?\n(.*?)endstream", pdf_bytes, re.DOTALL):
        data = m.group(1).strip()
        try:
            text += zlib.decompress(base64.a85decode(data, adobe=True))
        except Exception:
            try:
                text += zlib.decompress(data)
            except Exception:
                pass
    return text


def test_pdf_contains_specialist_headline(specialist_ctx):
    text = _pdf_text(generate_pdf(specialist_ctx))
    assert HEADLINE.encode() in text
    assert b"REQUER REVIS" in text  # faixa "REQUER REVISÃO POR ENGENHEIRO ESTRUTURAL…"


def test_ui_banner_shows_specialist():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file("app.py", default_timeout=60)
    app.run()
    op_weight = [f for f in app.number_input if "Peso operação" in f.label][0]
    op_weight.set_value(540.0)
    calc = [b for b in app.button if "Calcular" in b.label][0]
    calc.click()
    app.run()
    assert not app.exception
    errors = " ".join(e.value for e in app.error)
    warnings = " ".join(w.value for w in app.warning)
    assert HEADLINE in errors
    # aviso de política de peso na sidebar (banda SPECIALIST)
    assert "REQUIRES_SPECIALIST" in warnings or "500" in warnings
    # nunca banner verde de sucesso para especialista
    successes = " ".join(s.value for s in app.success)
    assert "PASSA - CONSERVADOR" not in successes
