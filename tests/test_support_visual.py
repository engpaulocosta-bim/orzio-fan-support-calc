from sfsc.engines.selector import run_full_calculation
from sfsc.enums import (
    AntiVibrationType,
    CantileverSubtype,
    CheckerStatus,
    FanConnectionType,
    SupportFixationMedium,
    SupportType,
)
from sfsc.ui.support_visual import support_preview_html


def test_support_preview_has_both_views_and_status(base_inp):
    inp = base_inp.model_copy(
        update={"support_fixation_medium": SupportFixationMedium.STEEL_STRUCTURE}
    )
    ctx = run_full_calculation(inp)
    res = ctx.fan_support_result
    res.status = CheckerStatus.PASS

    html = support_preview_html(inp, res)

    assert "<svg" in html
    assert "PLANTA" in html
    assert "ALÇADO" in html
    assert "Estrutura metálica" in html
    assert "PASS" in html


def test_support_preview_real_dimensions(base_inp):
    ctx = run_full_calculation(base_inp)
    html = support_preview_html(base_inp, ctx.fan_support_result)

    assert f"L = {base_inp.span_mm:.0f} mm" in html
    assert f"h = {base_inp.installation_height_mm:.0f} mm" in html
    assert "Utilização" in html


def test_support_preview_shows_eccentricity_dimension(base_inp):
    inp = base_inp.model_copy(update={"eccentricity_mm": 120.0})
    ctx = run_full_calculation(inp)
    html = support_preview_html(inp, ctx.fan_support_result)

    assert "e = 120 mm" in html
    assert "CG" in html


def test_support_preview_optional_mounts_follow_inputs(base_inp):
    inp = base_inp.model_copy(
        update={
            "support_type": SupportType.CANTILEVER_1,
            "cantilever_subtype": CantileverSubtype.BRACKETED,
            "include_base_plate": True,
            "fan_connection_type": FanConnectionType.DIRECT_FLANGE,
            "anti_vibration": AntiVibrationType.SPRINGS,
            "anti_vibration_static_deflection_mm": 25.0,
        }
    )
    ctx = run_full_calculation(inp)
    html = support_preview_html(inp, ctx.fan_support_result)

    assert "base plate" in html
    assert "#0f766e" in html
    assert "base reta" in html.lower()


def test_support_preview_platform_mentions_beams(base_inp):
    inp = base_inp.model_copy(
        update={
            "support_type": SupportType.PLATFORM_FRAME_BRACED,
            "platform_n_beams": 4,
            "platform_width_mm": 2200.0,
            "platform_length_mm": 1800.0,
        }
    )
    ctx = run_full_calculation(inp)
    html = support_preview_html(inp, ctx.fan_support_result)

    assert "4 vigas" in html
    assert "tramex" in html
