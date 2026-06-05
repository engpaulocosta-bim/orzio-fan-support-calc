"""Engineering-drawing style SVG preview of the fan support.

Rendered to scale from the real span/height, with technical dimension lines,
load arrows, a utilisation gauge and a detailed fixing node. Returned as a
self-contained HTML document meant to be embedded with
``streamlit.components.v1.html`` (an isolated iframe), NOT ``st.markdown``:
the Streamlit markdown sanitiser mangles complex SVG and leaks the markup as
raw text.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape

from sfsc.enums import AnchorageSubstrate, CheckerStatus, SupportType
from sfsc.models import FanSupportInput, FanSupportResult

# ── Canvas / drawing constants ──────────────────────────────────────────────────
# The drawing area is the central band between the margins. The top margin is
# large so the legend card and the utilisation gauge (pinned to the top corners)
# never collide with the structure, which is drawn only inside the band.
_W = 960
_H = 560
_MARGIN_L = 150        # leave room so the structure clears the legend card
_MARGIN_R = 150        # …and the utilisation gauge on the right
_MARGIN_T = 150        # legend / gauge live above this line
_MARGIN_B = 120        # span dimension + anchor labels live below this line
_DRAW_W = _W - _MARGIN_L - _MARGIN_R
_DRAW_H = _H - _MARGIN_T - _MARGIN_B

_STATUS_COLOR = {
    "PASS": "#16a34a",
    "MARGINAL": "#ca8a04",
    "FAIL": "#dc2626",
    "REQUIRES_SPECIALIST": "#7c3aed",
}
_STEEL = "#1f6feb"
_INK = "#0f172a"
_DIM = "#475569"
_GRID = "#e8eef5"


@dataclass
class _Scene:
    """Resolved drawing scene in canvas coordinates."""

    scale: float          # mm -> px
    base_y: float         # ground / fixing line (canvas y)
    top_y: float          # top of the steel frame
    left_x: float         # left support line
    right_x: float        # right support / span end
    fan_cx: float         # fan centre x
    fan_y: float          # baseline the fan rests on (its bottom edge)
    fan_w: float          # fan footprint width in px
    fan_h: float          # fan body height in px


def support_preview_html(inp: FanSupportInput, res: FanSupportResult) -> str:
    """Return a full HTML document with the to-scale support drawing."""
    support_label = inp.support_type.value.replace("_", " ").title()
    section = res.recommended_section.designation if res.recommended_section else "n/a"
    substrate = (
        "Betão"
        if inp.anchorage_substrate == AnchorageSubstrate.CONCRETE
        else "Estrutura metálica"
    )
    status = res.status.value if isinstance(res.status, CheckerStatus) else str(res.status)
    status_color = _STATUS_COLOR.get(status, "#64748b")

    eta = _utilisation(res)
    fan_mass = sum(u.operating_weight_kg for u in inp.fan_units) if inp.fan_units else 0.0
    footprint_mm = (
        max(u.footprint_width_mm for u in inp.fan_units) if inp.fan_units else 600.0
    )

    scene = _build_scene(inp)

    frame = _frame(inp.support_type, scene)
    extras = _extras(inp.support_type, scene)
    fan = _fan(scene, fan_mass)
    load_arrow = _load_arrow(scene)
    anchors = _anchors(inp.anchorage_substrate, inp.support_type, scene)
    dims = _dimensions(inp, scene)
    grid = _grid()
    gauge = _gauge(eta, status, status_color)
    legend = _legend(support_label, section, substrate, status, status_color)

    svg = f"""
      <svg viewBox="0 0 {_W} {_H}" role="img"
           aria-label="Modelo esquematico do suporte a escala">
        <defs>
          <!-- userSpaceOnUse so vertical (zero-width-bbox) members still get a
               visible stroke; an objectBoundingBox gradient collapses on them. -->
          <linearGradient id="steel" gradientUnits="userSpaceOnUse"
                          x1="0" y1="{_MARGIN_T}" x2="0" y2="{_MARGIN_T + _DRAW_H}">
            <stop offset="0" stop-color="#3b82f6"/>
            <stop offset="1" stop-color="#1d4ed8"/>
          </linearGradient>
          <linearGradient id="fanBody" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#f1f5f9"/>
            <stop offset="1" stop-color="#cbd5e1"/>
          </linearGradient>
          <filter id="softShadow" x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="0" dy="5" stdDeviation="5"
                          flood-color="#0b1220" flood-opacity="0.20"/>
          </filter>
          <marker id="dimArrow" markerWidth="9" markerHeight="9"
                  refX="7" refY="4.5" orient="auto">
            <path d="M0 0 L8 4.5 L0 9 z" fill="{_DIM}"/>
          </marker>
          <marker id="loadArrow" markerWidth="12" markerHeight="12"
                  refX="5" refY="10" orient="auto">
            <path d="M5 11 L0 2 L10 2 z" fill="#dc2626"/>
          </marker>
        </defs>

        <rect x="0" y="0" width="{_W}" height="{_H}" fill="#f8fafc"/>
        <rect x="40" y="44" width="{_W - 80}" height="{_H - 92}" rx="10"
              fill="#ffffff" stroke="#dbe4ee"/>
        {grid}
        {frame}
        {extras}
        {fan}
        {load_arrow}
        {anchors}
        {dims}
        {gauge}
        {legend}
      </svg>
    """

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  html, body {{ margin: 0; padding: 0; height: 100%; background: transparent; }}
  /* Centre the drawing and bound it by BOTH width and height so it keeps its
     aspect ratio and is never clipped when the iframe gets wide on maximise. */
  .sfsc-preview {{
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    box-sizing: border-box;
  }}
  .sfsc-preview svg {{
    max-width: 100%;
    max-height: 100%;
    width: auto;
    height: auto;
    display: block;
    border: 1px solid #dbe4ee;
    border-radius: 10px;
    background: #f8fafc;
    font-family: 'Segoe UI', system-ui, sans-serif;
  }}
</style></head>
<body><div class="sfsc-preview">{svg}</div></body></html>"""


# ── Scene resolution (real geometry -> canvas) ──────────────────────────────────

def _build_scene(inp: FanSupportInput) -> _Scene:
    span = max(inp.span_mm, 1.0)
    height = max(inp.installation_height_mm, 1.0)

    # The fan is an equipment symbol with a modest size — it is NOT drawn to
    # footprint scale. We only reserve vertical room for it so it never overflows
    # the top margin; its width is adapted below to never exceed the span.
    fan_h = 60.0
    fan_clearance = fan_h + 34.0   # body + load arrow above the frame

    # The structure must fit the draw band horizontally (span) and in the
    # vertical room that is left after reserving the fan clearance.
    avail_h = max(_DRAW_H - fan_clearance, 40.0)
    scale = min(_DRAW_W / span, avail_h / height)
    scale = max(scale, 1e-3)

    base_y = _MARGIN_T + _DRAW_H
    top_y = base_y - height * scale

    span_px = span * scale
    left_x = _MARGIN_L + (_DRAW_W - span_px) / 2.0
    right_x = left_x + span_px

    # Keep the fan inside the structure: cap its width to the span (small inset)
    # but keep it readable. For small spans it shrinks; for large ones it stays
    # modest rather than growing without bound.
    fan_w = max(min(span_px * 0.82, 168.0), 84.0)

    fan_cx = (left_x + right_x) / 2.0
    if inp.support_type == SupportType.HANGER:
        # Suspended: the fan hangs near the base, just above the cross member.
        fan_y = base_y - 14.0
    else:
        fan_y = top_y  # fan rests on top of the frame

    return _Scene(
        scale=scale, base_y=base_y, top_y=top_y, left_x=left_x, right_x=right_x,
        fan_cx=fan_cx, fan_y=fan_y, fan_w=fan_w, fan_h=fan_h,
    )


# ── Steel frame per support type ────────────────────────────────────────────────

def _frame(support_type: SupportType, s: _Scene) -> str:
    lx, rx, by, ty, cx = s.left_x, s.right_x, s.base_y, s.top_y, s.fan_cx
    g_open = ('<g stroke="url(#steel)" stroke-width="10" stroke-linecap="round" '
              'stroke-linejoin="round" fill="none" filter="url(#softShadow)">')

    if support_type == SupportType.HANGER:
        # Ceiling beam at the top, two threaded rods hanging down to a bottom
        # cross member from which the fan is suspended.
        cross_y = by - 14.0
        body = (
            f'<path d="M{lx - 24:.0f} {ty:.0f} L{rx + 24:.0f} {ty:.0f}"/>'
            f'<path d="M{lx:.0f} {ty:.0f} L{lx:.0f} {cross_y:.0f}"/>'
            f'<path d="M{rx:.0f} {ty:.0f} L{rx:.0f} {cross_y:.0f}"/>'
            f'<path d="M{lx:.0f} {cross_y:.0f} L{rx:.0f} {cross_y:.0f}"/>'
        )
    elif support_type == SupportType.CANTILEVER_1:
        body = (
            f'<path d="M{lx:.0f} {ty:.0f} L{lx:.0f} {by:.0f}"/>'
            f'<path d="M{lx:.0f} {ty:.0f} L{rx:.0f} {ty:.0f}"/>'
        )
    elif support_type == SupportType.CANTILEVER_2:
        body = (
            f'<path d="M{cx:.0f} {ty:.0f} L{cx:.0f} {by:.0f}"/>'
            f'<path d="M{lx:.0f} {ty:.0f} L{rx:.0f} {ty:.0f}"/>'
        )
    elif support_type == SupportType.CANTILEVER_3:
        body = (
            f'<path d="M{lx:.0f} {by:.0f} L{lx:.0f} {ty:.0f} '
            f'L{rx:.0f} {ty:.0f} L{rx:.0f} {by:.0f}"/>'
        )
    elif support_type == SupportType.PEDESTAL:
        inset = (rx - lx) * 0.18
        body = (
            f'<path d="M{lx + inset:.0f} {by:.0f} L{lx + inset:.0f} {ty:.0f} '
            f'L{rx - inset:.0f} {ty:.0f} L{rx - inset:.0f} {by:.0f}"/>'
            f'<path d="M{lx:.0f} {by:.0f} L{rx:.0f} {by:.0f}"/>'
        )
    else:  # COMBINED — portal frame
        body = (
            f'<path d="M{lx:.0f} {by:.0f} L{lx:.0f} {ty:.0f} '
            f'L{rx:.0f} {ty:.0f} L{rx:.0f} {by:.0f}"/>'
            f'<path d="M{lx:.0f} {ty:.0f} L{rx:.0f} {ty:.0f}"/>'
        )
    return g_open + body + "</g>"


def _extras(support_type: SupportType, s: _Scene) -> str:
    """Diagonal braces and anti-vibration springs."""
    parts: list[str] = []
    lx, rx, by, ty, cx = s.left_x, s.right_x, s.base_y, s.top_y, s.fan_cx

    if support_type in (SupportType.CANTILEVER_1, SupportType.COMBINED):
        bx = lx + (rx - lx) * 0.45
        parts.append(
            '<g stroke="url(#steel)" stroke-width="9" stroke-linecap="round" '
            f'fill="none" opacity="0.85"><path d="M{lx:.0f} {by:.0f} '
            f'L{bx:.0f} {ty:.0f}"/></g>'
        )

    if support_type == SupportType.COMBINED:
        sp = []
        for px in (cx - s.fan_w * 0.35, cx + s.fan_w * 0.35):
            y0 = ty - 26
            sp.append(
                f'<path d="M{px:.0f} {y0:.0f} q14 8 0 16 q-14 8 0 16 '
                f'q14 8 0 16 q-14 8 0 16"/>'
            )
        parts.append(
            '<g stroke="#f97316" stroke-width="4" fill="none">'
            + "".join(sp) + "</g>"
        )
    return "".join(parts)


# ── Equipment ───────────────────────────────────────────────────────────────────

def _fan(s: _Scene, fan_mass: float) -> str:
    bx = s.fan_cx - s.fan_w / 2.0
    by = s.fan_y - s.fan_h
    label = "VENTILADOR"
    mass = f"{fan_mass:.0f} kg" if fan_mass else ""
    # Mounting flange: a thin strip at the base, same colour family as the body
    # (subtle), so the fan reads as "equipment on a flange" without a jarring
    # dark slab. A small intake circle hints at the impeller.
    flange_h = 7.0
    flange_y = s.fan_y - flange_h
    return f"""
      <g filter="url(#softShadow)">
        <rect x="{bx:.0f}" y="{by:.0f}" width="{s.fan_w:.0f}" height="{s.fan_h:.0f}"
              rx="10" fill="url(#fanBody)" stroke="#64748b" stroke-width="1.5"/>
        <rect x="{bx + 6:.0f}" y="{flange_y:.0f}" width="{s.fan_w - 12:.0f}"
              height="{flange_h:.0f}" rx="3" fill="#cbd5e1" stroke="#64748b"
              stroke-width="1"/>
        <circle cx="{s.fan_cx:.0f}" cy="{by + s.fan_h * 0.34:.0f}" r="9"
                fill="none" stroke="#94a3b8" stroke-width="2"/>
        <text x="{s.fan_cx:.0f}" y="{by + s.fan_h * 0.62:.0f}" text-anchor="middle"
              font-size="14" font-weight="700" fill="{_INK}">{label}</text>
        <text x="{s.fan_cx:.0f}" y="{by + s.fan_h * 0.84:.0f}" text-anchor="middle"
              font-size="11" fill="{_DIM}">{mass}</text>
      </g>
    """


def _load_arrow(s: _Scene) -> str:
    """Downward design-load arrow just off the fan's right edge (clears cap)."""
    ax = s.fan_cx + s.fan_w * 0.5 + 14   # outside the body, to the right
    body_top = s.fan_y - s.fan_h
    y0 = body_top - 6
    y1 = body_top + s.fan_h * 0.45
    return (
        f'<line x1="{ax:.0f}" y1="{y0:.0f}" x2="{ax:.0f}" y2="{y1:.0f}" '
        f'stroke="#dc2626" stroke-width="3" marker-end="url(#loadArrow)"/>'
        f'<text x="{ax + 7:.0f}" y="{y0 + 14:.0f}" font-size="12" '
        f'font-weight="700" fill="#dc2626">F_Ed</text>'
    )


def _anchors(substrate: AnchorageSubstrate, support_type: SupportType, s: _Scene) -> str:
    concrete = substrate == AnchorageSubstrate.CONCRETE
    color = "#64748b" if concrete else "#2563eb"
    label = "chumbadores (betão)" if concrete else "parafusos aço-aço"

    # A hanger fixes to the ceiling (top); everything else fixes to the floor.
    if support_type == SupportType.HANGER:
        fix_y = s.top_y
        node_dir = -1          # hardware sits above the fixing line
        hatch_y = fix_y - 10
        label_y = fix_y - 22
    else:
        fix_y = s.base_y
        node_dir = 1           # hardware sits below the fixing line
        hatch_y = fix_y + 10
        label_y = fix_y + 34

    plate_y = fix_y - 2 if node_dir > 0 else fix_y - 10
    bolt_cy = fix_y + node_dir * 4
    nodes = []
    for fx in (s.left_x, s.right_x):
        nodes.append(
            f'<rect x="{fx - 22:.0f}" y="{plate_y:.0f}" width="44" height="12" '
            f'rx="2" fill="{color}" opacity="0.9"/>'
            f'<circle cx="{fx - 11:.0f}" cy="{bolt_cy:.0f}" r="4" fill="#1e293b"/>'
            f'<circle cx="{fx + 11:.0f}" cy="{bolt_cy:.0f}" r="4" fill="#1e293b"/>'
        )

    return f"""
      <g>{''.join(nodes)}</g>
      <line x1="{_MARGIN_L - 30:.0f}" y1="{fix_y:.0f}"
            x2="{_W - _MARGIN_R + 30:.0f}" y2="{fix_y:.0f}"
            stroke="#334155" stroke-width="3"/>
      <line x1="{_MARGIN_L - 30:.0f}" y1="{hatch_y:.0f}"
            x2="{_W - _MARGIN_R + 30:.0f}" y2="{hatch_y:.0f}"
            stroke="#94a3b8" stroke-width="1" stroke-dasharray="6 5"/>
      <text x="{s.fan_cx:.0f}" y="{label_y:.0f}" text-anchor="middle"
            font-size="12" fill="{_DIM}">{label}</text>
    """


# ── Technical dimensions ────────────────────────────────────────────────────────

def _dimensions(inp: FanSupportInput, s: _Scene) -> str:
    parts: list[str] = []

    # Span L — horizontal dimension below the structure.
    dim_y = s.base_y + 56
    parts.append(_hdim(s.left_x, s.right_x, dim_y, f"L = {inp.span_mm:.0f} mm"))

    # Height h — vertical dimension on the right.
    dim_x = _W - _MARGIN_R + 34
    parts.append(_vdim(dim_x, s.top_y, s.base_y, f"h = {inp.installation_height_mm:.0f} mm"))

    return "".join(parts)


def _hdim(x0: float, x1: float, y: float, label: str) -> str:
    return (
        f'<line x1="{x0:.0f}" y1="{y - 8:.0f}" x2="{x0:.0f}" y2="{y + 8:.0f}" '
        f'stroke="{_DIM}" stroke-width="1"/>'
        f'<line x1="{x1:.0f}" y1="{y - 8:.0f}" x2="{x1:.0f}" y2="{y + 8:.0f}" '
        f'stroke="{_DIM}" stroke-width="1"/>'
        f'<line x1="{x0:.0f}" y1="{y:.0f}" x2="{x1:.0f}" y2="{y:.0f}" '
        f'stroke="{_DIM}" stroke-width="1.4" '
        f'marker-start="url(#dimArrow)" marker-end="url(#dimArrow)"/>'
        f'<rect x="{(x0 + x1) / 2 - 62:.0f}" y="{y - 12:.0f}" width="124" height="22" '
        f'rx="4" fill="#f8fafc"/>'
        f'<text x="{(x0 + x1) / 2:.0f}" y="{y + 4:.0f}" text-anchor="middle" '
        f'font-size="13" font-weight="600" fill="{_INK}">{escape(label)}</text>'
    )


def _vdim(x: float, y0: float, y1: float, label: str) -> str:
    cy = (y0 + y1) / 2
    return (
        f'<line x1="{x - 8:.0f}" y1="{y0:.0f}" x2="{x + 8:.0f}" y2="{y0:.0f}" '
        f'stroke="{_DIM}" stroke-width="1"/>'
        f'<line x1="{x - 8:.0f}" y1="{y1:.0f}" x2="{x + 8:.0f}" y2="{y1:.0f}" '
        f'stroke="{_DIM}" stroke-width="1"/>'
        f'<line x1="{x:.0f}" y1="{y0:.0f}" x2="{x:.0f}" y2="{y1:.0f}" '
        f'stroke="{_DIM}" stroke-width="1.4" '
        f'marker-start="url(#dimArrow)" marker-end="url(#dimArrow)"/>'
        f'<text x="{x + 6:.0f}" y="{cy:.0f}" text-anchor="middle" '
        f'font-size="13" font-weight="600" fill="{_INK}" '
        f'transform="rotate(90 {x + 6:.0f} {cy:.0f})">{escape(label)}</text>'
    )


# ── Background grid ─────────────────────────────────────────────────────────────

def _grid() -> str:
    lines = []
    step = 40
    for gx in range(_MARGIN_L, _W - _MARGIN_R + 1, step):
        lines.append(
            f'<line x1="{gx}" y1="{_MARGIN_T}" x2="{gx}" y2="{_MARGIN_T + _DRAW_H}" '
            f'stroke="{_GRID}" stroke-width="1"/>'
        )
    for gy in range(_MARGIN_T, _MARGIN_T + _DRAW_H + 1, step):
        lines.append(
            f'<line x1="{_MARGIN_L}" y1="{gy}" x2="{_W - _MARGIN_R}" y2="{gy}" '
            f'stroke="{_GRID}" stroke-width="1"/>'
        )
    return f'<g opacity="0.8">{"".join(lines)}</g>'


# ── Utilisation gauge ───────────────────────────────────────────────────────────

def _gauge(eta: float, status: str, color: str) -> str:
    # Pinned to the top-right band, above _MARGIN_T so it clears the structure.
    bar_x, bar_y, bar_w, bar_h = _W - 260, 56, 168, 14
    pct = max(0.0, min(eta, 1.0))
    fill_w = bar_w * pct
    return f"""
      <g>
        <text x="{bar_x:.0f}" y="{bar_y - 6:.0f}" font-size="12" font-weight="700"
              fill="{_INK}">Utilização  &#951; = {eta * 100:.1f}%</text>
        <rect x="{bar_x:.0f}" y="{bar_y:.0f}" width="{bar_w}" height="{bar_h}"
              rx="7" fill="#e2e8f0"/>
        <rect x="{bar_x:.0f}" y="{bar_y:.0f}" width="{fill_w:.0f}" height="{bar_h}"
              rx="7" fill="{color}"/>
        <rect x="{bar_x + bar_w + 8:.0f}" y="{bar_y - 2:.0f}" width="92" height="20"
              rx="10" fill="{color}"/>
        <text x="{bar_x + bar_w + 54:.0f}" y="{bar_y + 12:.0f}" text-anchor="middle"
              font-size="11" font-weight="700" fill="white">{escape(status)}</text>
      </g>
    """


# ── Legend card ─────────────────────────────────────────────────────────────────

def _legend(label: str, section: str, substrate: str,
            status: str, color: str) -> str:
    # Pinned to the top-left band, above _MARGIN_T so it clears the structure.
    x, y, w, h = 50, 40, 250, 92
    return f"""
      <g>
        <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10"
              fill="#f1f5f9" stroke="#dbe4ee"/>
        <rect x="{x}" y="{y}" width="6" height="{h}" rx="3" fill="{color}"/>
        <text x="{x + 18}" y="{y + 26}" font-size="15" font-weight="700"
              fill="{_INK}">{escape(label)}</text>
        <text x="{x + 18}" y="{y + 50}" font-size="13" fill="#334155">Perfil: {escape(section)}</text>
        <text x="{x + 18}" y="{y + 74}" font-size="13" fill="#334155">Fixação: {escape(substrate)}</text>
      </g>
    """


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _utilisation(res: FanSupportResult) -> float:
    """Best-available governing utilisation ratio, clamped to a sane range."""
    sv = getattr(res, "section_verification", None)
    eta = getattr(sv, "utilization_ratio", None) if sv else None
    if eta is None:
        anchor = getattr(res, "anchor", None)
        eta = getattr(anchor, "utilization_ratio", None) if anchor else None
    try:
        return max(0.0, float(eta))
    except (TypeError, ValueError):
        return 0.0
