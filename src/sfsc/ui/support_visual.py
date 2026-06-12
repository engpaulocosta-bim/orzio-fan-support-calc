"""Engineering SVG preview of the fan support."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from sfsc.enums import (
    AntiVibrationType,
    CantileverSubtype,
    CheckerStatus,
    SupportFixationMedium,
    SupportType,
)
from sfsc.models import FanSupportInput, FanSupportResult

_W = 1180
_H = 600
_PANEL_W = 560
_PANEL_GAP = 20
_PANEL_PLAN_X = 20
_PANEL_ELEV_X = _PANEL_PLAN_X + _PANEL_W + _PANEL_GAP

_M_L = 70
_M_R = 70
_M_T = 96
_M_B = 92
_BAND_W = _PANEL_W - _M_L - _M_R
_BAND_H = _H - _M_T - _M_B

_STATUS_COLOR = {
    "PASS": "#16a34a",
    "MARGINAL": "#ca8a04",
    "FAIL": "#dc2626",
    "REQUIRES_SPECIALIST": "#7c3aed",
}
_STEEL = "#1d4ed8"
_INK = "#0f172a"
_DIM = "#475569"
_GRID = "#e8eef5"
_BASE = "#1e40af"
_PLATE = "#f59e0b"


def support_preview_html(inp: FanSupportInput, res: FanSupportResult) -> str:
    """Return a self-contained HTML document with plan and elevation views."""
    support_label = _support_label(inp)
    section = res.recommended_section.designation if res.recommended_section else "n/a"
    fixation = (
        "Estrutura metálica"
        if inp.support_fixation_medium == SupportFixationMedium.STEEL_STRUCTURE
        else "Betão"
    )
    status = res.status.value if isinstance(res.status, CheckerStatus) else str(res.status)
    status_color = _STATUS_COLOR.get(status, "#64748b")
    eta = _utilisation(res)

    svg = f"""
      <svg viewBox="0 0 {_W} {_H}" role="img" aria-label="Modelo do suporte: planta e alçado">
        {_defs()}
        <rect x="0" y="0" width="{_W}" height="{_H}" fill="#f8fafc"/>
        {_header(support_label, section, fixation, status, status_color, eta)}
        {_panel(_PANEL_PLAN_X, "PLANTA", _draw_plan(inp))}
        {_panel(_PANEL_ELEV_X, "ALÇADO", _draw_elevation(inp))}
      </svg>
    """
    return _document(svg)


def _panel(x0: float, title: str, body: str) -> str:
    return f"""
      <g transform="translate({x0} 0)">
        <rect x="6" y="64" width="{_PANEL_W - 12}" height="{_H - 86}" rx="10"
              fill="#ffffff" stroke="#dbe4ee"/>
        <text x="{_PANEL_W / 2:.0f}" y="86" text-anchor="middle"
              font-size="15" font-weight="800" fill="{_INK}"
              letter-spacing="1">{title}</text>
        {body}
      </g>
    """


def _header(label: str, section: str, fixation: str, status: str, color: str, eta: float) -> str:
    bar_x, bar_y, bar_w, bar_h = _W - 270, 30, 168, 14
    pct = max(0.0, min(eta, 1.0))
    return f"""
      <g>
        <rect x="20" y="14" width="360" height="40" rx="10" fill="#f1f5f9" stroke="#dbe4ee"/>
        <rect x="20" y="14" width="6" height="40" rx="3" fill="{color}"/>
        <text x="38" y="32" font-size="14" font-weight="700" fill="{_INK}">{escape(label)}</text>
        <text x="38" y="48" font-size="12" fill="#334155">Perfil: {escape(section)}  •  Fixação: {escape(fixation)}</text>
        <text x="{bar_x:.0f}" y="{bar_y - 4:.0f}" font-size="12" font-weight="700"
              fill="{_INK}">Utilização  η = {eta * 100:.1f}%</text>
        <rect x="{bar_x:.0f}" y="{bar_y:.0f}" width="{bar_w}" height="{bar_h}" rx="7" fill="#e2e8f0"/>
        <rect x="{bar_x:.0f}" y="{bar_y:.0f}" width="{bar_w * pct:.0f}" height="{bar_h}" rx="7" fill="{color}"/>
        <rect x="{bar_x + bar_w + 8:.0f}" y="{bar_y - 2:.0f}" width="86" height="20" rx="10" fill="{color}"/>
        <text x="{bar_x + bar_w + 51:.0f}" y="{bar_y + 12:.0f}" text-anchor="middle"
              font-size="11" font-weight="700" fill="white">{escape(status)}</text>
      </g>
    """


def _defs() -> str:
    return f"""
        <defs>
          <linearGradient id="steel" gradientUnits="userSpaceOnUse"
                          x1="0" y1="{_M_T}" x2="0" y2="{_M_T + _BAND_H}">
            <stop offset="0" stop-color="#3b82f6"/>
            <stop offset="1" stop-color="#1d4ed8"/>
          </linearGradient>
          <linearGradient id="fanBody" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#f1f5f9"/>
            <stop offset="1" stop-color="#cbd5e1"/>
          </linearGradient>
          <filter id="softShadow" x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="0" dy="4" stdDeviation="4"
                          flood-color="#0b1220" flood-opacity="0.18"/>
          </filter>
          <marker id="dimArrow" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
            <path d="M0 0 L8 4.5 L0 9 z" fill="{_DIM}"/>
          </marker>
          <marker id="loadArrow" markerWidth="12" markerHeight="12" refX="5" refY="10" orient="auto">
            <path d="M5 11 L0 2 L10 2 z" fill="#dc2626"/>
          </marker>
          <pattern id="concreteHatch" width="8" height="8" patternTransform="rotate(45)"
                   patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="0" y2="8" stroke="#94a3b8" stroke-width="1"/>
          </pattern>
          <pattern id="tramex" width="9" height="9" patternUnits="userSpaceOnUse">
            <rect width="9" height="9" fill="#eef2f7"/>
            <path d="M0 0 H9 M0 0 V9" stroke="#9aa7b8" stroke-width="0.8"/>
          </pattern>
        </defs>
    """


def _document(svg: str) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  html, body {{ margin: 0; padding: 0; height: 100%; background: transparent; }}
  .sfsc-preview {{
    width: 100%; height: 100%;
    display: flex; align-items: center; justify-content: center;
    box-sizing: border-box;
  }}
  .sfsc-preview svg {{
    max-width: 100%; max-height: 100%; width: auto; height: auto;
    display: block;
    border: 1px solid #dbe4ee; border-radius: 10px; background: #f8fafc;
    font-family: 'Segoe UI', system-ui, sans-serif;
  }}
</style></head>
<body><div class="sfsc-preview">{svg}</div></body></html>"""


def _is_engaste(inp: FanSupportInput) -> bool:
    return inp.support_type in (SupportType.CANTILEVER_1, SupportType.CANTILEVER_2)


def _is_platform(inp: FanSupportInput) -> bool:
    return inp.support_type == SupportType.PLATFORM_FRAME_BRACED


def _two_sided(inp: FanSupportInput) -> bool:
    return inp.support_type == SupportType.CANTILEVER_2


def _braced(inp: FanSupportInput) -> bool:
    if _is_platform(inp) and inp.cantilever_subtype is None:
        return True
    return inp.cantilever_subtype == CantileverSubtype.BRACKETED


def _support_label(inp: FanSupportInput) -> str:
    if inp.support_type == SupportType.HANGER:
        return "Pendurado (tirantes)"
    if inp.support_type == SupportType.CANTILEVER_2:
        return "Engastado (2 lados)"
    if inp.support_type == SupportType.CANTILEVER_1:
        return "Engastado (1 lado)"
    if inp.support_type == SupportType.PLATFORM_FRAME_BRACED:
        brace = "com mão-francesa" if _braced(inp) else "sem mão-francesa"
        return f"Plataforma · {max(2, inp.platform_n_beams)} vigas · {brace}"
    return inp.support_type.value.replace("_", " ").title()


def _fan_dims_mm(inp: FanSupportInput) -> tuple[float, float, float, float]:
    unit = inp.fan_units[0] if inp.fan_units else None
    width = max((u.footprint_width_mm for u in inp.fan_units), default=600.0)
    length = max((u.footprint_length_mm for u in inp.fan_units), default=600.0)
    cg = unit.centre_of_gravity_height_mm if unit else 0.0
    box_h = max(2.0 * cg, 250.0)
    mass = sum(u.operating_weight_kg for u in inp.fan_units) if inp.fan_units else 0.0
    return width, length, box_h, mass


@dataclass
class _Elev:
    scale: float
    base_y: float
    top_y: float
    left_x: float
    right_x: float
    axis_x: float
    fan_cx: float
    fan_y: float
    fan_w: float
    fan_h: float
    cg_x: float
    cg_y: float
    ecc_mm: float


def _elev_scene(inp: FanSupportInput) -> _Elev:
    span = max(inp.span_mm, 1.0)
    height = max(inp.installation_height_mm, 1.0)
    fan_w_mm, _fan_len_mm, fan_h_mm, _mass = _fan_dims_mm(inp)
    ecc_mm = inp.eccentricity_mm

    head_px = 48.0
    avail_h = max(_BAND_H - head_px, 40.0)
    total_h_mm = height + fan_h_mm
    horiz_mm = (
        span + fan_w_mm * 0.5
        if inp.support_type == SupportType.CANTILEVER_1
        else max(span, fan_w_mm)
    )
    scale = max(min(_BAND_W / horiz_mm, avail_h / total_h_mm), 1e-3)

    fan_w = fan_w_mm * scale
    fan_h = fan_h_mm * scale
    span_px = span * scale
    base_y = _M_T + _BAND_H
    top_y = base_y - height * scale

    if inp.support_type == SupportType.HANGER:
        left_x = _M_L + (_BAND_W - span_px) / 2.0
        right_x = left_x + span_px
        axis_x = (left_x + right_x) / 2.0
        fan_cx = axis_x + ecc_mm * scale
        fan_y = base_y - 14.0
    elif inp.support_type == SupportType.CANTILEVER_1:
        left_x = _M_L + 8
        right_x = left_x + span_px
        axis_x = right_x
        fan_cx = min(right_x + ecc_mm * scale, _PANEL_W - _M_R - fan_w / 2)
        fan_y = top_y
    else:
        left_x = _M_L + (_BAND_W - span_px) / 2.0
        right_x = left_x + span_px
        axis_x = (left_x + right_x) / 2.0
        fan_cx = axis_x + ecc_mm * scale
        fan_y = top_y

    cg_x = fan_cx
    cg_y = fan_y - fan_h / 2.0
    return _Elev(
        scale,
        base_y,
        top_y,
        left_x,
        right_x,
        axis_x,
        fan_cx,
        fan_y,
        fan_w,
        fan_h,
        cg_x,
        cg_y,
        ecc_mm,
    )


def _draw_elevation(inp: FanSupportInput) -> str:
    if _is_platform(inp):
        return _draw_elevation_platform(inp)
    s = _elev_scene(inp)
    _, _fan_len, _box_h, mass = _fan_dims_mm(inp)
    concrete = inp.support_fixation_medium != SupportFixationMedium.STEEL_STRUCTURE

    parts = [_grid()]
    if inp.support_type == SupportType.HANGER:
        parts.append(_elev_hanger(s))
    else:
        parts.append(_elev_engaste(inp, s, concrete))
    parts.append(_fan_box(s.fan_cx, s.fan_y, s.fan_w, s.fan_h, s.cg_x, s.cg_y, mass))
    parts.append(_elev_optional_mounts(inp, s))
    parts.append(_load_arrow(s))
    parts.append(_elev_dims(inp, s))
    return "".join(parts)


def _draw_elevation_platform(inp: FanSupportInput) -> str:
    span = max(inp.platform_length_eff_mm, 1.0)
    height = max(inp.installation_height_mm, 1.0)
    fan_w_mm, _fan_len_mm, fan_h_mm, mass = _fan_dims_mm(inp)
    braced = _braced(inp)
    concrete = inp.support_fixation_medium != SupportFixationMedium.STEEL_STRUCTURE

    head_px = 48.0
    avail_h = max(_BAND_H - head_px, 40.0)
    total_h_mm = height + fan_h_mm
    horiz_mm = max(span, fan_w_mm) * 1.1
    scale = max(min(_BAND_W / horiz_mm, avail_h / total_h_mm), 1e-3)

    span_px = span * scale
    base_y = _M_T + _BAND_H
    deck_y = base_y - height * scale
    left_x = _M_L + 16
    right_x = left_x + span_px

    parts = [_grid()]
    bw = 22.0
    fill = "url(#concreteHatch)" if concrete else "#94a3b8"
    tag = "viga betão" if concrete else "viga metálica"
    parts.append(
        f'<rect x="{left_x - bw:.0f}" y="{deck_y - 24:.0f}" width="{bw:.0f}" '
        f'height="{base_y - deck_y + 44:.0f}" rx="2" fill="{fill}" '
        f'stroke="#64748b" stroke-width="1.5"/>'
        f'<text x="{left_x - bw / 2:.0f}" y="{deck_y - 30:.0f}" text-anchor="middle" '
        f'font-size="10" fill="{_DIM}">{tag}</text>'
        f'<text x="{left_x:.0f}" y="{deck_y - 30:.0f}" font-size="10" '
        f'font-weight="700" fill="#b45309">ENGASTE</text>'
    )

    if braced:
        parts.append(
            '<g stroke="url(#steel)" stroke-width="7" stroke-linecap="round" '
            'fill="none" opacity="0.9">'
            f'<path d="M{left_x:.0f} {base_y:.0f} L{right_x:.0f} {deck_y:.0f}"/></g>'
        )

    deck_h = 12.0
    parts.append(
        f'<rect x="{left_x:.0f}" y="{deck_y - deck_h / 2:.0f}" width="{span_px:.0f}" '
        f'height="{deck_h:.0f}" rx="2" fill="url(#tramex)" stroke="#1e293b" '
        f'stroke-width="1.2"/>'
        f'<text x="{(left_x + right_x) / 2:.0f}" y="{deck_y + deck_h + 10:.0f}" '
        f'text-anchor="middle" font-size="9" fill="{_DIM}">plataforma + tramex</text>'
    )

    fan_w = fan_w_mm * scale
    fan_h = fan_h_mm * scale
    fan_cx = (left_x + right_x) / 2
    fan_y = deck_y - deck_h / 2
    cg_x = fan_cx
    cg_y = fan_y - fan_h / 2
    parts.append(_fan_box(fan_cx, fan_y, fan_w, fan_h, cg_x, cg_y, mass))
    parts.append(
        f'<line x1="{cg_x:.1f}" y1="{fan_y - fan_h - 44:.1f}" x2="{cg_x:.1f}" '
        f'y2="{fan_y - fan_h - 4:.1f}" stroke="#dc2626" stroke-width="3" '
        f'marker-end="url(#loadArrow)"/>'
        f'<text x="{cg_x + 8:.1f}" y="{fan_y - fan_h - 30:.1f}" font-size="12" '
        f'font-weight="700" fill="#dc2626">F_Ed</text>'
    )
    parts.append(_hdim(left_x, right_x, base_y + 50, f"L = {inp.platform_length_eff_mm:.0f} mm"))
    parts.append(
        _vdim(_PANEL_W - _M_R + 30, deck_y, base_y, f"h = {inp.installation_height_mm:.0f} mm")
    )
    return "".join(parts)


def _elev_hanger(s: _Elev) -> str:
    cross_y = s.base_y - 14.0
    g = '<g stroke="url(#steel)" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" fill="none" filter="url(#softShadow)">'
    rods = (
        f'<path d="M{s.left_x:.0f} {s.top_y:.0f} L{s.left_x:.0f} {cross_y:.0f}"/>'
        f'<path d="M{s.right_x:.0f} {s.top_y:.0f} L{s.right_x:.0f} {cross_y:.0f}"/>'
        f'<path d="M{s.left_x:.0f} {cross_y:.0f} L{s.right_x:.0f} {cross_y:.0f}"/>'
    )
    ceil = (
        f'<line x1="{_M_L - 24:.0f}" y1="{s.top_y:.0f}" x2="{_PANEL_W - _M_R + 24:.0f}" '
        f'y2="{s.top_y:.0f}" stroke="#334155" stroke-width="3"/>'
        f'<rect x="{_M_L - 24:.0f}" y="{s.top_y - 12:.0f}" width="{_BAND_W + 48:.0f}" '
        f'height="12" fill="url(#concreteHatch)"/>'
    )
    return ceil + g + rods + "</g>"


def _elev_engaste(inp: FanSupportInput, s: _Elev, concrete: bool) -> str:
    arm_y = s.top_y
    fan_left = s.fan_cx - s.fan_w / 2
    fan_right = s.fan_cx + s.fan_w / 2
    beams: list[str] = []
    braces: list[str] = []
    bases: list[str] = []

    def beam(cx: float) -> str:
        bw, bh = 24.0, (s.base_y - s.top_y) + 44
        bx = cx - bw / 2
        by = s.top_y - 24
        fill = "url(#concreteHatch)" if concrete else "#94a3b8"
        tag = "viga betão" if concrete else "viga metálica"
        return (
            f'<rect x="{bx:.0f}" y="{by:.0f}" width="{bw:.0f}" height="{bh:.0f}" '
            f'rx="2" fill="{fill}" stroke="#64748b" stroke-width="1.5"/>'
            f'<text x="{cx:.0f}" y="{by - 6:.0f}" text-anchor="middle" '
            f'font-size="10" fill="{_DIM}">{tag}</text>'
        )

    if _two_sided(inp):
        beams.extend([beam(s.left_x), beam(s.right_x)])
        bases.append(_elev_base_rect(inp, s.left_x, s.right_x, arm_y))
        if _braced(inp):
            braces.append(_knee(s.left_x, arm_y, fan_left, s.base_y))
            braces.append(_knee(s.right_x, arm_y, fan_right, s.base_y))
        beams.append(_engaste_bolts(s.left_x, arm_y, concrete))
        beams.append(_engaste_bolts(s.right_x, arm_y, concrete))
    else:
        beams.append(beam(s.left_x))
        bases.append(_elev_base_rect(inp, s.left_x, max(s.fan_cx, fan_right), arm_y))
        if _braced(inp):
            braces.append(_knee(s.left_x, arm_y, fan_left, s.base_y))
        beams.append(_engaste_bolts(s.left_x, arm_y, concrete))

    return "".join(beams) + "".join(braces) + "".join(bases)


def _base_fixing_label(inp: FanSupportInput) -> str:
    if inp.support_fixation_medium == SupportFixationMedium.STEEL_STRUCTURE:
        return "base reta aparafusada"
    return "base reta engastada"


def _elev_base_rect(inp: FanSupportInput, x0: float, x1: float, y: float) -> str:
    if x0 > x1:
        x0, x1 = x1, x0
    h = 14.0
    return (
        f'<g filter="url(#softShadow)">'
        f'<rect x="{x0:.0f}" y="{y - h / 2:.0f}" width="{max(10.0, x1 - x0):.0f}" '
        f'height="{h:.0f}" rx="2" fill="{_BASE}" stroke="#1e293b" stroke-width="1"/>'
        f'<text x="{(x0 + x1) / 2:.0f}" y="{y - 12:.0f}" text-anchor="middle" '
        f'font-size="10" font-weight="700" fill="{_INK}">{escape(_base_fixing_label(inp))}</text>'
        f"</g>"
    )


def _elev_optional_mounts(inp: FanSupportInput, s: _Elev) -> str:
    parts: list[str] = []
    fan_left = s.fan_cx - s.fan_w / 2
    fan_right = s.fan_cx + s.fan_w / 2
    if inp.include_base_plate:
        parts.append(
            f'<rect x="{fan_left - 10:.0f}" y="{s.fan_y - 10:.0f}" width="{s.fan_w + 20:.0f}" '
            f'height="10" rx="2" fill="{_PLATE}" stroke="#92400e" stroke-width="1.2"/>'
            f'<text x="{s.fan_cx:.0f}" y="{s.fan_y - 15:.0f}" text-anchor="middle" '
            f'font-size="10" fill="#92400e">base plate</text>'
        )
    if inp.anti_vibration == AntiVibrationType.SPRINGS:
        spring_y = s.fan_y - (14.0 if inp.include_base_plate else 4.0)
        for x in (fan_left + s.fan_w * 0.22, fan_right - s.fan_w * 0.22):
            parts.append(_spring_symbol(x, spring_y))
    return "".join(parts)


def _spring_symbol(cx: float, y: float) -> str:
    return (
        f'<path d="M{cx - 10:.0f} {y:.0f} c4 -8 8 8 12 0 c4 -8 8 8 12 0" '
        f'fill="none" stroke="#0f766e" stroke-width="2"/>'
    )


def _knee(beam_x: float, arm_y: float, tip_x: float, base_y: float) -> str:
    low_y = arm_y + (base_y - arm_y) * 0.5
    return (
        '<g stroke="url(#steel)" stroke-width="7" stroke-linecap="round" fill="none" opacity="0.85">'
        f'<path d="M{beam_x:.0f} {low_y:.0f} L{tip_x:.0f} {arm_y:.0f}"/></g>'
    )


def _engaste_bolts(beam_x: float, arm_y: float, concrete: bool) -> str:
    color = "#64748b" if concrete else "#2563eb"
    bx = beam_x + 14
    return "".join(
        f'<circle cx="{bx:.0f}" cy="{arm_y + dy:.0f}" r="3.5" fill="{color}"/>' for dy in (-10, 10)
    )


def _fan_box(
    cx: float, base_y: float, w: float, h: float, cg_x: float, cg_y: float, mass: float
) -> str:
    bx = cx - w / 2
    by = base_y - h
    label = "VENTILADOR"
    mass_s = f"{mass:.0f} kg" if mass else ""
    if h >= 60 and w >= 120:
        texts = (
            f'<text x="{cx:.0f}" y="{by + h * 0.26:.0f}" text-anchor="middle" '
            f'font-size="13" font-weight="700" fill="{_INK}">{label}</text>'
            f'<text x="{cx:.0f}" y="{by + h * 0.82:.0f}" text-anchor="middle" '
            f'font-size="11" fill="{_DIM}">{mass_s}</text>'
        )
    else:
        texts = (
            f'<text x="{cx:.0f}" y="{by - 10:.0f}" text-anchor="middle" '
            f'font-size="12" font-weight="700" fill="{_INK}">{label} — {mass_s}</text>'
        )
    return f"""
      <g filter="url(#softShadow)">
        <rect x="{bx:.1f}" y="{by:.1f}" width="{w:.1f}" height="{h:.1f}"
              rx="8" fill="url(#fanBody)" stroke="#64748b" stroke-width="1.5"/>
        {texts}
      </g>
      {_cg_marker(cg_x, cg_y)}
    """


def _cg_marker(cx: float, cy: float) -> str:
    r = 8.0
    return (
        f'<g><circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="white" stroke="#0f172a" stroke-width="1.5"/>'
        f'<path d="M{cx:.1f} {cy:.1f} L{cx:.1f} {cy - r:.1f} A{r} {r} 0 0 1 {cx + r:.1f} {cy:.1f} Z" fill="#0f172a"/>'
        f'<path d="M{cx:.1f} {cy:.1f} L{cx:.1f} {cy + r:.1f} A{r} {r} 0 0 1 {cx - r:.1f} {cy:.1f} Z" fill="#0f172a"/>'
        f'<text x="{cx + r + 4:.1f}" y="{cy - r - 2:.1f}" font-size="10" font-weight="700" fill="#0f172a">CG</text></g>'
    )


def _load_arrow(s: _Elev) -> str:
    box_top = s.fan_y - s.fan_h
    tight = not (s.fan_h >= 60 and s.fan_w >= 120)
    head_gap = 30 if tight else 2
    y0 = box_top - head_gap - 40
    y1 = box_top - head_gap
    return (
        f'<line x1="{s.cg_x:.1f}" y1="{y0:.1f}" x2="{s.cg_x:.1f}" y2="{y1:.1f}" '
        f'stroke="#dc2626" stroke-width="3" marker-end="url(#loadArrow)"/>'
        f'<line x1="{s.cg_x:.1f}" y1="{box_top:.1f}" x2="{s.cg_x:.1f}" y2="{s.cg_y - 9:.1f}" '
        f'stroke="#dc2626" stroke-width="1.2" stroke-dasharray="3 3" opacity="0.7"/>'
        f'<text x="{s.cg_x + 8:.1f}" y="{y0 + 13:.1f}" font-size="12" font-weight="700" fill="#dc2626">F_Ed</text>'
    )


def _elev_dims(inp: FanSupportInput, s: _Elev) -> str:
    parts = [
        _hdim(s.left_x, s.right_x, s.base_y + 50, f"L = {inp.span_mm:.0f} mm"),
        _vdim(_PANEL_W - _M_R + 30, s.top_y, s.base_y, f"h = {inp.installation_height_mm:.0f} mm"),
        f'<line x1="{s.axis_x:.1f}" y1="{s.top_y - 4:.1f}" x2="{s.axis_x:.1f}" y2="{s.base_y:.1f}" stroke="#94a3b8" stroke-width="1" stroke-dasharray="4 4"/>',
    ]
    if abs(s.ecc_mm) >= 0.5:
        parts.append(_hdim(s.axis_x, s.cg_x, s.fan_y - s.fan_h - 30, f"e = {s.ecc_mm:.0f} mm"))
    return "".join(parts)


def _draw_plan(inp: FanSupportInput) -> str:
    if _is_platform(inp):
        return _draw_plan_platform(inp)
    span = max(inp.span_mm, 1.0)
    fan_w_mm, fan_len_mm, _box_h, _mass = _fan_dims_mm(inp)
    ecc_mm = inp.eccentricity_mm
    concrete = inp.support_fixation_medium != SupportFixationMedium.STEEL_STRUCTURE
    color = "#64748b" if concrete else "#2563eb"
    hole_label = "chumbadores" if concrete else "parafusos"

    horiz_mm = max(span, fan_len_mm * 1.2)
    if inp.support_type == SupportType.CANTILEVER_1:
        horiz_mm = max(span + fan_w_mm * 0.70 + ecc_mm, fan_len_mm * 1.2)
    scale = max(min(_BAND_W / horiz_mm, _BAND_H / max(fan_len_mm * 1.6, 1.0)), 1e-3)

    cx0 = _PANEL_W / 2.0
    cy0 = _M_T + _BAND_H / 2.0
    span_px = span * scale
    left_x = cx0 - span_px / 2
    right_x = cx0 + span_px / 2
    fw = fan_w_mm * scale
    fl = fan_len_mm * scale
    fan_cx = (
        right_x + ecc_mm * scale
        if inp.support_type == SupportType.CANTILEVER_1
        else (cx0 + ecc_mm * scale)
    )
    fan_cy = cy0

    parts = [_grid()]
    fill = "url(#concreteHatch)" if concrete else "#cbd5e1"

    def plan_beam(bx: float) -> str:
        return (
            f'<rect x="{bx - 13:.0f}" y="{_M_T:.0f}" width="26" height="{_BAND_H:.0f}" '
            f'fill="{fill}" stroke="#64748b" stroke-width="1.5"/>'
        )

    if inp.support_type == SupportType.HANGER:
        beam_note = "tirantes (4 pontos)"
    elif _two_sided(inp):
        parts.append(plan_beam(left_x))
        parts.append(plan_beam(right_x))
        beam_note = "vigas de apoio (2 lados)"
    else:
        parts.append(plan_beam(left_x))
        beam_note = "viga de apoio (esquerda)"

    if _is_engaste(inp):
        parts.append(_plan_base_rect(inp, left_x, right_x, fan_cx, fan_cy, fw, fl))

    parts.append(
        f'<rect x="{fan_cx - fw / 2:.1f}" y="{fan_cy - fl / 2:.1f}" width="{fw:.1f}" height="{fl:.1f}" '
        f'rx="6" fill="url(#fanBody)" stroke="#64748b" stroke-width="1.5"/>'
        f'<text x="{fan_cx:.0f}" y="{fan_cy - fl * 0.28:.0f}" text-anchor="middle" '
        f'font-size="12" font-weight="700" fill="{_INK}">VENTILADOR</text>'
    )
    parts.append(_plan_holes(inp, left_x, right_x, fan_cx, fan_cy, fw, fl, color))
    parts.append(_plan_optional_mounts(inp, fan_cx, fan_cy, fw, fl))
    parts.append(_cg_marker(fan_cx, fan_cy))

    axis_x = right_x if inp.support_type == SupportType.CANTILEVER_1 else cx0
    parts.append(
        f'<line x1="{axis_x:.1f}" y1="{_M_T:.1f}" x2="{axis_x:.1f}" y2="{_M_T + _BAND_H:.1f}" '
        f'stroke="#94a3b8" stroke-width="1" stroke-dasharray="4 4"/>'
    )
    if abs(ecc_mm) >= 0.5:
        parts.append(_hdim(axis_x, fan_cx, fan_cy - fl / 2 - 22, f"e = {ecc_mm:.0f} mm"))
    parts.append(
        _hdim(fan_cx - fw / 2, fan_cx + fw / 2, fan_cy + fl / 2 + 28, f"b = {fan_w_mm:.0f} mm")
    )
    if _is_engaste(inp):
        parts.append(
            f'<text x="{left_x:.0f}" y="{_M_T - 8:.0f}" text-anchor="middle" '
            f'font-size="10" font-weight="700" fill="#b45309">ENGASTE</text>'
        )
    parts.append(
        f'<text x="{_PANEL_W / 2:.0f}" y="{_M_T + _BAND_H + 56:.0f}" text-anchor="middle" '
        f'font-size="11" fill="{_DIM}">{beam_note} — {hole_label}</text>'
    )
    return "".join(parts)


def _draw_plan_platform(inp: FanSupportInput) -> str:
    length_mm = max(inp.platform_length_eff_mm, 1.0)
    width_mm = max(inp.platform_width_eff_mm, 1.0)
    n_beams = max(2, inp.platform_n_beams)
    braced = _braced(inp)
    fan_w_mm, fan_len_mm, _box_h, _mass = _fan_dims_mm(inp)

    scale = max(min(_BAND_W / (length_mm * 1.05), _BAND_H / (width_mm * 1.05)), 1e-3)
    pl = length_mm * scale
    pw = width_mm * scale
    x0 = _PANEL_W / 2 - pl / 2
    y0 = _M_T + _BAND_H / 2 - pw / 2
    x1 = x0 + pl
    y1 = y0 + pw

    parts = [_grid()]
    parts.append(
        f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{pl:.1f}" height="{pw:.1f}" rx="3" '
        f'fill="url(#tramex)" stroke="#64748b" stroke-width="1.5"/>'
    )

    surface_label = f"{inp.walking_surface.self_weight_kn_m2:.2f} kN/m²"
    parts.append(
        f'<text x="{(x0 + x1) / 2:.0f}" y="{y0 - 8:.0f}" text-anchor="middle" '
        f'font-size="10" fill="{_DIM}">tramex {surface_label}</text>'
    )

    ys = [y0 + pw * (i / (n_beams - 1)) for i in range(n_beams)] if n_beams > 1 else [(y0 + y1) / 2]
    for by in ys:
        parts.append(
            f'<line x1="{x0:.1f}" y1="{by:.1f}" x2="{x1:.1f}" y2="{by:.1f}" stroke="url(#steel)" stroke-width="6" stroke-linecap="round"/>'
        )
    parts.append(
        f'<text x="{x0 + 6:.0f}" y="{ys[0] - 6:.0f}" font-size="9" fill="{_STEEL}">{n_beams} vigas</text>'
    )
    parts.append(
        f'<line x1="{x0:.1f}" y1="{y0 - 6:.1f}" x2="{x0:.1f}" y2="{y1 + 6:.1f}" stroke="#b45309" stroke-width="4"/>'
        f'<text x="{x0:.0f}" y="{y0 - 18:.0f}" text-anchor="middle" font-size="10" font-weight="700" fill="#b45309">ENGASTE</text>'
    )
    if braced:
        for by in (ys[0], ys[-1]):
            parts.append(
                f'<circle cx="{x1:.1f}" cy="{by:.1f}" r="4" fill="none" stroke="{_STEEL}" stroke-width="2"/>'
            )
        parts.append(
            f'<text x="{x1:.0f}" y="{y1 + 18:.0f}" text-anchor="middle" font-size="9" fill="{_STEEL}">apoio mão-francesa</text>'
        )

    fw = fan_w_mm * scale
    fl = fan_len_mm * scale
    fcx = (x0 + x1) / 2
    fcy = (y0 + y1) / 2
    parts.append(
        f'<rect x="{fcx - fl / 2:.1f}" y="{fcy - fw / 2:.1f}" width="{fl:.1f}" height="{fw:.1f}" '
        f'rx="6" fill="url(#fanBody)" stroke="#64748b" stroke-width="1.5" opacity="0.92"/>'
        f'<text x="{fcx:.0f}" y="{fcy:.0f}" text-anchor="middle" font-size="11" font-weight="700" fill="{_INK}">VENTILADOR(ES)</text>'
    )
    parts.append(_hdim(x0, x1, y1 + 40, f"L = {length_mm:.0f} mm"))
    parts.append(_vdim(x1 + 28, y0, y1, f"b = {width_mm:.0f} mm"))
    return "".join(parts)


def _plan_base_rect(
    inp: FanSupportInput,
    left_x: float,
    right_x: float,
    fan_cx: float,
    fan_cy: float,
    fw: float,
    fl: float,
) -> str:
    h = max(18.0, min(34.0, fl * 0.16))
    x0 = left_x
    x1 = right_x if _two_sided(inp) else fan_cx + fw / 2
    if x0 > x1:
        x0, x1 = x1, x0
    label = _base_fixing_label(inp)
    return (
        f'<rect x="{x0:.1f}" y="{fan_cy - h / 2:.1f}" width="{max(10.0, x1 - x0):.1f}" '
        f'height="{h:.1f}" rx="3" fill="#dbeafe" stroke="{_BASE}" stroke-width="2"/>'
        f'<text x="{(x0 + x1) / 2:.0f}" y="{fan_cy - h / 2 - 8:.0f}" text-anchor="middle" '
        f'font-size="10" font-weight="700" fill="{_BASE}">{escape(label)}</text>'
    )


def _plan_optional_mounts(
    inp: FanSupportInput, fan_cx: float, fan_cy: float, fw: float, fl: float
) -> str:
    parts: list[str] = []
    if inp.include_base_plate:
        parts.append(
            f'<rect x="{fan_cx - fw / 2 - 8:.1f}" y="{fan_cy - fl / 2 - 8:.1f}" width="{fw + 16:.1f}" height="{fl + 16:.1f}" '
            f'rx="4" fill="none" stroke="{_PLATE}" stroke-width="2.2" stroke-dasharray="6 4"/>'
        )
    if inp.anti_vibration == AntiVibrationType.SPRINGS:
        for sx in (-1, 1):
            for sy in (-1, 1):
                parts.append(
                    f'<circle cx="{fan_cx + sx * fw * 0.34:.1f}" cy="{fan_cy + sy * fl * 0.34:.1f}" '
                    f'r="5" fill="#ccfbf1" stroke="#0f766e" stroke-width="1.5"/>'
                )
    return "".join(parts)


def _plan_holes(
    inp: FanSupportInput,
    left_x: float,
    right_x: float,
    fan_cx: float,
    fan_cy: float,
    fw: float,
    fl: float,
    color: str,
) -> str:
    r = 3.5
    pts: list[tuple[float, float]] = []
    dy = fl * 0.32
    if inp.support_type == SupportType.HANGER:
        for sx in (-1, 1):
            for sy in (-1, 1):
                pts.append((fan_cx + sx * fw * 0.4, fan_cy + sy * dy))
    elif _two_sided(inp):
        for bx in (left_x, right_x):
            for sy in (-1, 1):
                pts.append((bx, fan_cy + sy * dy))
    else:
        for sy in (-1, 1):
            pts.append((left_x, fan_cy + sy * dy))
            pts.append((left_x + 18, fan_cy + sy * dy))
    return "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="none" stroke="{color}" stroke-width="2"/>'
        for x, y in pts
    )


def _grid() -> str:
    lines = []
    for gx in range(_M_L, _PANEL_W - _M_R + 1, 40):
        lines.append(
            f'<line x1="{gx}" y1="{_M_T}" x2="{gx}" y2="{_M_T + _BAND_H}" stroke="{_GRID}" stroke-width="1"/>'
        )
    for gy in range(_M_T, _M_T + _BAND_H + 1, 40):
        lines.append(
            f'<line x1="{_M_L}" y1="{gy}" x2="{_PANEL_W - _M_R}" y2="{gy}" stroke="{_GRID}" stroke-width="1"/>'
        )
    return f'<g opacity="0.7">{"".join(lines)}</g>'


def _hdim(x0: float, x1: float, y: float, label: str) -> str:
    if x0 > x1:
        x0, x1 = x1, x0
    mid = (x0 + x1) / 2
    return (
        f'<line x1="{x0:.0f}" y1="{y - 7:.0f}" x2="{x0:.0f}" y2="{y + 7:.0f}" stroke="{_DIM}" stroke-width="1"/>'
        f'<line x1="{x1:.0f}" y1="{y - 7:.0f}" x2="{x1:.0f}" y2="{y + 7:.0f}" stroke="{_DIM}" stroke-width="1"/>'
        f'<line x1="{x0:.0f}" y1="{y:.0f}" x2="{x1:.0f}" y2="{y:.0f}" stroke="{_DIM}" stroke-width="1.4" '
        f'marker-start="url(#dimArrow)" marker-end="url(#dimArrow)"/>'
        f'<rect x="{mid - 58:.0f}" y="{y - 11:.0f}" width="116" height="20" rx="4" fill="#f8fafc"/>'
        f'<text x="{mid:.0f}" y="{y + 4:.0f}" text-anchor="middle" font-size="12" font-weight="600" fill="{_INK}">{escape(label)}</text>'
    )


def _vdim(x: float, y0: float, y1: float, label: str) -> str:
    cy = (y0 + y1) / 2
    return (
        f'<line x1="{x - 7:.0f}" y1="{y0:.0f}" x2="{x + 7:.0f}" y2="{y0:.0f}" stroke="{_DIM}" stroke-width="1"/>'
        f'<line x1="{x - 7:.0f}" y1="{y1:.0f}" x2="{x + 7:.0f}" y2="{y1:.0f}" stroke="{_DIM}" stroke-width="1"/>'
        f'<line x1="{x:.0f}" y1="{y0:.0f}" x2="{x:.0f}" y2="{y1:.0f}" stroke="{_DIM}" stroke-width="1.4" marker-start="url(#dimArrow)" marker-end="url(#dimArrow)"/>'
        f'<text x="{x + 5:.0f}" y="{cy:.0f}" text-anchor="middle" font-size="12" font-weight="600" fill="{_INK}" transform="rotate(90 {x + 5:.0f} {cy:.0f})">{escape(label)}</text>'
    )


def _utilisation(res: FanSupportResult) -> float:
    sv = getattr(res, "section_verification", None)
    eta = getattr(sv, "utilization_ratio", None) if sv else None
    if eta is None:
        anchor = getattr(res, "anchor", None)
        eta = getattr(anchor, "utilization_combined", None) if anchor else None
    platform = getattr(res, "platform", None)
    diagonal = platform.diagonal if platform is not None else None
    if eta is None and diagonal is not None:
        eta = diagonal.utilization_ratio
    try:
        return max(0.0, float(eta if eta is not None else 0.0))
    except (TypeError, ValueError):
        return 0.0
