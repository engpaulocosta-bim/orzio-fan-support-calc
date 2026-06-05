from sfsc.enums import AnchorageSubstrate, CheckerStatus
from sfsc.engines.selector import run_full_calculation
from sfsc.ui.support_visual import support_preview_html


def test_support_preview_contains_model_status_and_substrate(base_inp):
    inp = base_inp.model_copy(update={
        "anchorage_substrate": AnchorageSubstrate.STEEL_STRUCTURE,
    })
    ctx = run_full_calculation(inp)
    res = ctx.fan_support_result
    res.status = CheckerStatus.PASS

    html = support_preview_html(inp, res)

    assert "<svg" in html
    assert "Hanger" in html
    assert "Estrutura metálica" in html
    assert "PASS" in html


def test_support_preview_is_self_contained_document(base_inp):
    ctx = run_full_calculation(base_inp)
    res = ctx.fan_support_result

    html = support_preview_html(base_inp, res)

    # Full HTML doc so it can be embedded with components.html (iframe).
    assert html.lstrip().startswith("<!doctype html>")
    assert "</html>" in html


def test_support_preview_renders_real_dimensions(base_inp):
    ctx = run_full_calculation(base_inp)
    res = ctx.fan_support_result

    html = support_preview_html(base_inp, res)

    assert f"L = {base_inp.span_mm:.0f} mm" in html
    assert f"h = {base_inp.installation_height_mm:.0f} mm" in html
    # Utilisation gauge present.
    assert "Utilização" in html


def test_support_preview_handles_concrete_substrate(base_inp):
    inp = base_inp.model_copy(update={
        "anchorage_substrate": AnchorageSubstrate.CONCRETE,
    })
    ctx = run_full_calculation(inp)
    res = ctx.fan_support_result

    html = support_preview_html(inp, res)

    assert "betão" in html.lower()
