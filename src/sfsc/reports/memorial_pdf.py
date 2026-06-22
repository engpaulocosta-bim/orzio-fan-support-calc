"""Geração do memorial de cálculo em PDF — ReportLab."""

from __future__ import annotations

import io
from pathlib import Path

from .. import __version__
from ..assessment import assess_result
from ..engineering import CalculationResultState
from ..enums import CheckStatus
from ..i18n import Lang, t
from ..models import ReportContext

# Cores Orzio
BLUE = (0.08, 0.28, 0.90)  # #1447E6
CYAN = (0.13, 0.83, 0.93)  # #22D3EE
CORAL = (1.00, 0.42, 0.36)  # #FF6B5B
GREY = (0.28, 0.33, 0.40)
LIGHT = (0.95, 0.97, 0.99)
WHITE = (1.0, 1.0, 1.0)
RED_BG = (0.99, 0.95, 0.95)
WARN_BG = (1.00, 0.99, 0.88)
GREEN_BG = (0.92, 0.99, 0.93)

_STATUS_COLORS = {
    "PASS": GREEN_BG,
    "FAIL": RED_BG,
    "MARGINAL": WARN_BG,
    "DATASET_MISSING": (0.95, 0.90, 0.99),
    "OUT_OF_SCOPE": (0.94, 0.94, 0.94),
    "REQUIRES_SPECIALIST": RED_BG,
    "WARNING": WARN_BG,
}

_ENGINEERING_STATE_KEY = {
    CalculationResultState.VERIFIED: "engineering.state.verified",
    CalculationResultState.SIMPLIFIED: "engineering.state.simplified",
    CalculationResultState.NOT_VERIFIED: "engineering.state.notVerified",
    CalculationResultState.NOT_APPLICABLE: "engineering.state.notApplicable",
    CalculationResultState.REQUIRES_ENGINEER_REVIEW: "engineering.state.requiresEngineerReview",
    CalculationResultState.FAILED: "engineering.state.failed",
}


def generate_pdf(ctx: ReportContext, output_path: str | Path | None = None) -> bytes:
    """Gera memorial PDF e retorna bytes. Escreve ficheiro se output_path fornecido."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            CondPageBreak,
            KeepTogether,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise ImportError("reportlab não instalado. Execute: pip install reportlab") from exc

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=24 * mm,
        bottomMargin=24 * mm,
    )

    W = A4[0] - 40 * mm

    def _color(rgb):
        return colors.Color(*rgb)

    S_h1 = ParagraphStyle(
        "h1",
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=_color(BLUE),
        spaceBefore=10,
        spaceAfter=3,
    )
    S_h2 = ParagraphStyle(
        "h2",
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=_color(GREY),
        spaceBefore=6,
        spaceAfter=2,
    )
    S_body = ParagraphStyle("body", fontName="Helvetica", fontSize=9, leading=13)
    S_note = ParagraphStyle(
        "note", fontName="Helvetica-Oblique", fontSize=8, textColor=_color(GREY), leading=11
    )
    S_center = ParagraphStyle("center", fontName="Helvetica", fontSize=9, alignment=TA_CENTER)

    def kv_table(rows: list[tuple[str, str]], col_w=(70 * mm, None)) -> Table:
        cw = [col_w[0], W - col_w[0]]
        data = [[Paragraph(f"<b>{k}</b>", S_body), Paragraph(str(v), S_body)] for k, v in rows]
        t = Table(data, colWidths=cw)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), _color(LIGHT)),
                    ("GRID", (0, 0), (-1, -1), 0.3, _color((0.85, 0.88, 0.92))),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return t

    def data_table(headers: list[str], rows: list[list], col_widths=None) -> Table:
        head_row = [Paragraph(f"<b>{h}</b>", S_center) for h in headers]
        body_rows = [[Paragraph(str(c), S_center) for c in r] for r in rows]
        t = Table([head_row] + body_rows, colWidths=col_widths)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), _color(BLUE)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), _color(WHITE)),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("GRID", (0, 0), (-1, -1), 0.3, _color((0.85, 0.88, 0.92))),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_color(WHITE), _color(LIGHT)]),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        return t

    def section_heading(text: str, min_height=34 * mm) -> list:
        return [CondPageBreak(min_height), Paragraph(text, S_h1)]

    story = []

    inp = ctx.fan_support_input
    res = ctx.fan_support_result
    assessment = assess_result(res) if res else None

    # Phase 07: default to PT for legacy sections; use i18n for new sections.
    _lang = Lang.PT

    def fmt_pct(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.1f}%"

    def member_status_label(status: str, lang: Lang) -> str:
        key = {
            "PASS": "status.ok",
            "MARGINAL": "status.marginal",
            "FAIL": "status.fail",
        }.get(status)
        return t(key, lang) if key else status

    def member_axis_label(axis: object, lang: Lang) -> str:
        if axis in ("y", "z"):
            return str(axis)
        return t("report.label.none", lang)

    def connection_status_label(status: str, lang: Lang) -> str:
        return {
            "verified": t("engineering.state.verified", lang),
            "failed": t("engineering.state.failed", lang),
            "not_verified": t("engineering.state.notVerified", lang),
            "requires_engineer_review": t("engineering.state.requiresEngineerReview", lang),
        }.get(status, status)

    # O memorial é preliminar se não passa, requer especialista ou é PRELIMINARY:
    # nesse caso todas as páginas recebem marca de água diagonal.
    is_preliminary = (
        res is None
        or res.status.value != "PASS"
        or (assessment is not None and assessment.is_specialist)
        or (res.classification_level.value == "PRELIMINARY")
    )

    provenance = ctx.dataset_provenance or {}
    combined_hash = str(provenance.get("datasets_combined_sha256", ""))[:12] or "n/d"

    # ══════════════════════════════════════════════════════════════════════════
    # CAPA
    # ══════════════════════════════════════════════════════════════════════════
    S_cover_title = ParagraphStyle(
        "cover_title",
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=_color(BLUE),
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    S_cover_sub = ParagraphStyle(
        "cover_sub",
        fontName="Helvetica",
        fontSize=12,
        leading=15,
        textColor=_color(GREY),
        alignment=TA_CENTER,
    )
    story.append(Spacer(1, 50 * mm))
    story.append(Paragraph(t("pdf.cover.title", _lang), S_cover_title))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(t("pdf.cover.subtitle", _lang), S_cover_sub))
    story.append(Paragraph(f"SFSC — Steel Fan Support Calc v{__version__}", S_cover_sub))
    story.append(Spacer(1, 16 * mm))
    cover_rows = [
        ("Projecto", ctx.project_name),
        ("Tag do suporte", ctx.support_tag),
        ("Tipo de suporte", inp.support_type.value.replace("_", " ").title() if inp else "—"),
        (
            "País / norma",
            f"{inp.country.value if inp else '—'} — {res.structural_code.value if res else '—'}",
        ),
        ("Revisão", ctx.revision),
        ("Data", ctx.date),
        ("Engenheiro responsável", ctx.prepared_by),
        ("Diagnóstico", assessment.headline if assessment else "—"),
        ("Classificação", res.classification_level.value if res else "—"),
        ("Hash dos dados", combined_hash),
    ]
    story.append(kv_table(cover_rows, col_w=(60 * mm, None)))
    story.append(Spacer(1, 14 * mm))
    if is_preliminary:
        story.append(
            Paragraph(
                t("pdf.preliminary.label", _lang),
                ParagraphStyle(
                    "cover_warn",
                    fontName="Helvetica-Bold",
                    fontSize=12,
                    textColor=_color(CORAL),
                    alignment=TA_CENTER,
                ),
            )
        )
        story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            t("pdf.disclaimer", _lang),
            ParagraphStyle(
                "cover_note",
                fontName="Helvetica-Oblique",
                fontSize=9,
                textColor=_color(GREY),
                alignment=TA_CENTER,
            ),
        )
    )
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # CABEÇALHO
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 2 * mm))

    SPECIALIST_BG = (0.95, 0.90, 0.99)  # violeta — REQUER ESPECIALISTA

    if assessment:
        if assessment.is_failure:
            assessment_bg = RED_BG
        elif assessment.is_specialist:
            assessment_bg = SPECIALIST_BG
        elif assessment.is_borderline:
            assessment_bg = WARN_BG
        else:
            assessment_bg = GREEN_BG

        story.append(Paragraph("RESUMO EXECUTIVO", S_h1))
        summary_data = [
            [
                Paragraph("<b>Diagnóstico</b>", S_center),
                Paragraph("<b>Utilização governante</b>", S_center),
                Paragraph("<b>Conservadorismo</b>", S_center),
                Paragraph("<b>Uso do limite</b>", S_center),
            ],
            [
                Paragraph(f"<b>{assessment.headline}</b>", S_center),
                Paragraph(fmt_pct(assessment.utilization_percent), S_center),
                Paragraph(fmt_pct(assessment.conservatism_percent), S_center),
                Paragraph(fmt_pct(assessment.limit_percent), S_center),
            ],
        ]
        summary_table = Table(summary_data, colWidths=[W * 0.34, W * 0.22, W * 0.22, W * 0.22])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), _color(BLUE)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), _color(WHITE)),
                    ("BACKGROUND", (0, 1), (-1, 1), _color(assessment_bg)),
                    ("GRID", (0, 0), (-1, -1), 0.4, _color((0.80, 0.85, 0.92))),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(summary_table)
        story.append(Spacer(1, 2 * mm))
        story.append(
            Paragraph(
                f"{assessment.summary} Verificação governante: <b>{assessment.governing_item}</b>.",
                S_body,
            )
        )
        if assessment.is_specialist:
            story.append(Spacer(1, 2 * mm))
            story.append(
                Paragraph(
                    "REQUER REVISÃO POR ENGENHEIRO ESTRUTURAL QUALIFICADO — "
                    "este memorial não constitui aprovação do suporte.",
                    ParagraphStyle(
                        "specialist", fontName="Helvetica-Bold", fontSize=9, textColor=_color(CORAL)
                    ),
                )
            )
        story.append(Spacer(1, 4 * mm))

    # ── Verificação final por módulo (tarefa 1.1) ────────────────────────────
    if res and res.module_breakdown:
        lang = Lang.PT
        story.append(Paragraph(t("report.section.moduleSummary", lang), S_h1))
        _STATUS_KEY = {
            CheckStatus.OK: "status.ok",
            CheckStatus.MARGINAL: "status.marginal",
            CheckStatus.FAIL: "status.fail",
            CheckStatus.NOT_CHECKED: "status.not_checked",
            CheckStatus.INFORMATIVE: "status.informative",
        }
        mod_rows = []
        for c in res.module_breakdown:
            eta_txt = "N/A" if c.eta is None else f"{c.eta:.3f}"
            gov_txt = "Sim" if c.governing else ""
            mod_rows.append(
                [
                    t(c.label_key, lang),
                    t(_STATUS_KEY.get(c.status, "status.informative"), lang),
                    eta_txt,
                    gov_txt,
                ]
            )
        story.append(
            data_table(
                [
                    t("report.column.module", lang),
                    t("report.column.status", lang),
                    t("report.column.eta", lang),
                    t("report.column.governing", lang),
                ],
                mod_rows,
                col_widths=[W - 110 * mm, 38 * mm, 30 * mm, 22 * mm],
            )
        )
        story.append(Spacer(1, 4 * mm))

    if ctx.engineering_report_state and ctx.engineering_report_state.states:
        lang = Lang.PT
        story.append(Paragraph(t("engineering.summary.title", lang), S_h1))
        engineering_rows = [
            [
                t(item.label_key, lang),
                t(_ENGINEERING_STATE_KEY[item.state], lang),
            ]
            for item in ctx.engineering_report_state.states
        ]
        story.append(
            data_table(
                [
                    t("engineering.column.item", lang),
                    t("report.column.status", lang),
                ],
                engineering_rows,
                col_widths=[W * 0.62, W * 0.38],
            )
        )
        story.append(Spacer(1, 4 * mm))

    if ctx.import_review is not None:
        lang = Lang.PT
        import_review = ctx.import_review
        story.append(Paragraph(t("report.section.importReview", lang), S_h1))
        story.append(
            kv_table(
                [
                    (
                        t("report.column.source", lang),
                        import_review.source.source_type,
                    ),
                    (
                        t("report.column.fileName", lang),
                        import_review.source.file_name or "—",
                    ),
                    (
                        t("report.column.confirmed", lang),
                        t("common.yes", lang) if import_review.confirmed else t("common.no", lang),
                    ),
                    (
                        t("report.column.importedElements", lang),
                        str(import_review.imported_elements_count),
                    ),
                    (
                        t("report.column.acceptedMembers", lang),
                        str(import_review.accepted_members_count),
                    ),
                    (
                        t("report.column.rejectedElements", lang),
                        str(import_review.rejected_elements_count),
                    ),
                ],
                col_w=(62 * mm, None),
            )
        )
        if import_review.confirmation_notes:
            story.append(
                Paragraph(
                    f"<b>{t('report.label.assumptions', lang)}:</b> "
                    f"{import_review.confirmation_notes}",
                    S_body,
                )
            )
        if import_review.warnings:
            warning_rows = [
                [
                    str(item.code),
                    str(item.severity),
                    str(item.element_id or "—"),
                    str(item.message),
                ]
                for item in import_review.warnings
            ]
            story.append(
                data_table(
                    [
                        t("report.column.warningCode", lang),
                        t("report.column.warningSeverity", lang),
                        t("report.column.element", lang),
                        t("report.column.warnings", lang),
                    ],
                    warning_rows,
                    col_widths=[22 * mm, 24 * mm, 22 * mm, W - 68 * mm],
                )
            )
        story.append(Spacer(1, 4 * mm))

    if res and res.connection_check_rows:
        lang = Lang.PT
        story.append(Paragraph(t("report.section.connectionChecks", lang), S_h1))
        connection_rows = [
            [
                str(row.get("support_id", "")),
                str(row.get("type", "")),
                connection_status_label(str(row.get("status", "")), lang),
                "N/A"
                if row.get("utilization_ratio") is None
                else f"{float(row.get('utilization_ratio', 0.0)):.3f}",
                str(row.get("governing_combination", "")),
                f"{float(row.get('reaction_fx_kN', 0.0)):.3f}",
                f"{float(row.get('reaction_fz_kN', 0.0)):.3f}",
                f"{float(row.get('reaction_my_kNm', 0.0)):.3f}",
                ", ".join(str(item) for item in row.get("missing_inputs", [])) or "—",
            ]
            for row in res.connection_check_rows
        ]
        story.append(
            data_table(
                [
                    t("report.column.support", lang),
                    t("report.column.type", lang),
                    t("report.column.status", lang),
                    t("report.column.eta", lang),
                    t("report.column.combination", lang),
                    t("report.column.reactionFx", lang),
                    t("report.column.reactionFz", lang),
                    t("report.column.reactionMy", lang),
                    t("report.column.missingInputs", lang),
                ],
                connection_rows,
                col_widths=[
                    17 * mm,
                    20 * mm,
                    21 * mm,
                    12 * mm,
                    21 * mm,
                    14 * mm,
                    14 * mm,
                    16 * mm,
                    W - 135 * mm,
                ],
            )
        )
        story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 07: CALCULATION MODEL TRANSPARENCY
    # ══════════════════════════════════════════════════════════════════════════
    lang = _lang
    story.append(Paragraph(t("report.section.calculationModel", lang), S_h1))
    _solver_engine = res.solver_engine if res else "simplified"
    _is_global_frame = _solver_engine == "global_frame" and res and not res.solver_failed
    _model_type_label = (
        t("report.label.globalFrame", lang)
        if _is_global_frame
        else t("report.label.simplified", lang)
    )
    story.append(
        kv_table(
            [
                (t("report.label.calculationModelType", lang), _model_type_label),
                (t("report.label.solverEngine", lang), _solver_engine),
            ]
        )
    )
    if not _is_global_frame:
        story.append(
            Paragraph(
                f"⚠ {t('report.label.simplifiedModelWarning', lang)}",
                S_note,
            )
        )
    story.append(Spacer(1, 4 * mm))

    # ── Phase 07: Serviceability status ─────────────────────────────────────
    story.append(Paragraph(t("report.section.serviceability", lang), S_h1))
    _include_sls = inp.calculation_options.include_serviceability if inp else False
    _displacement_available = bool(res and res.solver_displacements)
    if not _include_sls:
        _sls_state = t("engineering.state.notApplicable", lang)
        _sls_reason = "Serviceability module not enabled in calculation options."
    elif _displacement_available:
        _sls_state = t("engineering.state.verified", lang)
        _sls_reason = "Displacement results available from solver."
    else:
        _sls_state = t("engineering.state.notVerified", lang)
        _sls_reason = t("report.label.deflectionNotAvailable", lang)
    story.append(
        kv_table(
            [
                (t("report.label.serviceabilityStatus", lang), _sls_state),
                (t("report.label.serviceabilityReason", lang), _sls_reason),
            ]
        )
    )
    if _include_sls and not _displacement_available:
        story.append(
            Paragraph(
                f"⚠ {t('report.label.serviceabilityNotVerified', lang)}",
                ParagraphStyle(
                    "sls_warn",
                    fontName="Helvetica-Bold",
                    fontSize=9,
                    textColor=_color(CORAL),
                    leading=13,
                ),
            )
        )
    story.append(Spacer(1, 4 * mm))

    # ── Phase 07: Connection verification status ──────────────────────────────
    story.append(Paragraph(t("report.section.connectionStatus", lang), S_h1))
    _has_connection_rows = bool(res and res.connection_check_rows)
    _connection_checks_requested = inp is not None and (
        inp.calculation_options.include_base_plate
        or inp.calculation_options.include_anchors
        or inp.calculation_options.include_steel_connections
    )

    def _connection_item_state(check_type: str) -> str:
        if not _has_connection_rows:
            return t("engineering.state.notVerified", lang)
        matching = [
            r for r in (res.connection_check_rows if res else []) if r.get("type") == check_type
        ]
        if not matching:
            return t("engineering.state.notVerified", lang)
        statuses = {str(r.get("status", "")) for r in matching}
        if "failed" in statuses:
            return t("engineering.state.failed", lang)
        if "not_verified" in statuses:
            return t("engineering.state.notVerified", lang)
        if "requires_engineer_review" in statuses:
            return t("engineering.state.requiresEngineerReview", lang)
        return t("engineering.state.verified", lang)

    story.append(
        kv_table(
            [
                (t("report.label.basePlateStatus", lang), _connection_item_state("base_plate")),
                (t("report.label.anchorStatus", lang), _connection_item_state("anchor_group")),
                (t("report.label.weldStatus", lang), _connection_item_state("steel_fixation")),
            ]
        )
    )
    if not _has_connection_rows:
        story.append(
            Paragraph(
                f"⚠ {t('report.label.connectionNotVerified', lang)}",
                ParagraphStyle(
                    "conn_warn",
                    fontName="Helvetica-Bold",
                    fontSize=9,
                    textColor=_color(CORAL),
                    leading=13,
                ),
            )
        )
        story.append(
            Paragraph(
                t("report.label.connectionWarning", lang),
                S_note,
            )
        )
    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 1. IDENTIFICAÇÃO
    # ══════════════════════════════════════════════════════════════════════════
    story.extend(section_heading(t("pdf.section.identification", _lang), 42 * mm))
    rows_id = [
        ("Projecto", inp.project_name if inp else "—"),
        ("Tag do suporte", inp.support_tag if inp else "—"),
        ("Tipo de suporte", inp.support_type.value.upper().replace("_", " ") if inp else "—"),
        (
            "País / norma",
            f"{inp.country.value if inp else '—'} — {res.structural_code.value if res else '—'}",
        ),
        ("Preparado por", ctx.prepared_by),
        ("Data", ctx.date),
        ("Revisão", ctx.revision),
        (t("report.label.calculationModelType", _lang), _model_type_label),
    ]
    if inp and inp.design_notes:
        rows_id.append(("Notas", inp.design_notes))
    story.append(kv_table(rows_id))
    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 2. VENTILADOR
    # ══════════════════════════════════════════════════════════════════════════
    story.extend(section_heading(t("pdf.section.fan", _lang), 34 * mm))
    if inp and inp.fan_units:
        total_w = inp.total_operating_weight_kg
        fan_rows = []
        for i, u in enumerate(inp.fan_units, 1):
            fan_rows.append(
                [
                    f"Und. {i}" + (f" ({u.tag})" if u.tag else ""),
                    u.fan_type.value,
                    f"{u.weight_kg:.0f} kg",
                    f"{u.operating_weight_kg:.0f} kg",
                    f"{u.footprint_length_mm:.0f} × {u.footprint_width_mm:.0f} mm",
                    f"{u.centre_of_gravity_height_mm:.0f} mm",
                ]
            )
        story.append(
            data_table(
                ["Unidade", "Tipo", "Peso vazio", "Peso operação", "Footprint L×W", "Altura CG"],
                fan_rows,
                col_widths=[30 * mm, 28 * mm, 25 * mm, 28 * mm, 35 * mm, 24 * mm],
            )
        )
        story.append(
            Paragraph(
                f"<b>Peso total em operação: {total_w:.1f} kg ({inp.total_weight_kn:.2f} kN)</b>",
                S_body,
            )
        )
    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 3. GEOMETRIA E CONFIGURAÇÃO
    # ══════════════════════════════════════════════════════════════════════════
    story.extend(section_heading(t("pdf.section.geometry", _lang), 48 * mm))
    if inp:
        rows_geo = [
            ("Tipo de suporte", inp.support_type.value.replace("_", " ").title()),
            ("Vão / comprimento (L)", f"{inp.span_mm:.0f} mm  ({inp.span_mm / 1000:.3f} m)"),
            ("Altura de instalação (h)", f"{inp.installation_height_mm:.0f} mm"),
            ("Excentricidade CG", f"{inp.eccentricity_mm:.0f} mm"),
            ("Factor dinâmico", f"{inp.dynamic_factor}  (VDI 3840)"),
            ("Anti-vibração", inp.anti_vibration.value),
            (
                t("report.label.basePlateStatus", _lang),
                t("common.yes", _lang) if inp.include_base_plate else t("common.no", _lang),
            ),
            ("Classe de exposição", inp.exposure_class.value),
            ("Betão de suporte", inp.concrete_grade),
        ]
        if inp.cantilever_subtype:
            rows_geo.insert(1, ("Subtipo consola", inp.cantilever_subtype.value))
        if inp.support_type.value == "platform_frame_braced":
            rows_geo.extend(
                [
                    (
                        t("report.label.platformModel", _lang),
                        (
                            t("report.label.grillage25d", _lang)
                            if inp.has_platform_grillage
                            else t("report.label.legacyParallelBeams", _lang)
                        ),
                    ),
                    (
                        t("report.label.platformGrid", _lang),
                        f"{inp.platform_n_beams} / {inp.platform_n_crossbeams}",
                    ),
                ]
            )
        story.append(kv_table(rows_geo))
    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 4. CARGAS E COMBINAÇÕES
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph(t("pdf.section.loads", _lang), S_h1))
    if res:
        kv_loads = [
            ("Factor sísmico ag/g", f"{res.seismic_factor_g:.3f}  ({res.seismic_code.value})"),
            ("Peso total G", f"{res.total_weight_kN:.3f} kN"),
            ("Carga de cálculo ULS (total)", f"{res.design_load_kN:.3f} kN"),
        ]
        if res.governing_load_combination:
            g = res.governing_load_combination
            kv_loads.append(
                (
                    "Esforço de cálculo no elemento",
                    f"V = {g.V_z_kN:.3f} kN | M = {g.M_y_kNm:.3f} kNm  ({g.name})",
                )
            )
        story.append(kv_table(kv_loads))
        if res.platform and (
            res.platform.load_surface_components
            or res.platform.distributed_line_loads
            or res.platform.manual_loads_applied
        ):
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph("4.A Superficies de carga e modelo manual", S_h2))
            if res.platform.load_surface_components:
                story.append(
                    data_table(
                        [
                            "Origem",
                            "Caso",
                            "q [kN/m2]",
                            "Area [m2]",
                            "Total [kN]",
                            "Metodo",
                        ],
                        [
                            [
                                str(item["source"]),
                                str(item["load_case"]),
                                f"{float(item['area_load_kn_m2']):.3f}",
                                f"{float(item['area_m2']):.3f}",
                                f"{float(item['total_load_kN']):.3f}",
                                str(item["distribution_method"]),
                            ]
                            for item in res.platform.load_surface_components
                        ],
                        col_widths=[34 * mm, 18 * mm, 22 * mm, 22 * mm, 22 * mm, 32 * mm],
                    )
                )
            if res.platform.distributed_line_loads:
                story.append(Spacer(1, 2 * mm))
                story.append(
                    data_table(
                        [
                            "Origem",
                            "Caso",
                            "Membro",
                            "q [kN/m]",
                            "L [m]",
                            "Total [kN]",
                        ],
                        [
                            [
                                str(item["source"]),
                                str(item["load_case"]),
                                str(item["target_member"]),
                                f"{float(item['line_load_kN_m']):.3f}",
                                f"{float(item['loaded_length_m']):.3f}",
                                f"{float(item['total_load_kN']):.3f}",
                            ]
                            for item in res.platform.distributed_line_loads
                        ],
                        col_widths=[30 * mm, 16 * mm, 26 * mm, 22 * mm, 18 * mm, 22 * mm],
                    )
                )
            if res.platform.manual_loads_applied:
                story.append(Spacer(1, 2 * mm))
                story.append(
                    data_table(
                        [
                            "Carga manual",
                            "Caso",
                            "Direcao",
                            "Membro",
                            "Valor",
                            "Eq. [kN]",
                        ],
                        [
                            [
                                str(item["name"]),
                                str(item["load_case"]),
                                str(item["direction"]),
                                str(item["target_member"]),
                                f"{float(item['value']):.3f} {item['unit']}",
                                f"{float(item['equivalent_total_kN']):.3f}",
                            ]
                            for item in res.platform.manual_loads_applied
                        ],
                        col_widths=[34 * mm, 16 * mm, 20 * mm, 24 * mm, 28 * mm, 20 * mm],
                    )
                )
            if res.platform.warnings:
                story.append(Spacer(1, 1 * mm))
                for warning in res.platform.warnings:
                    story.append(Paragraph(warning, S_note))

        def _combo_rows(combos):
            return [
                [
                    c.name,
                    f"{c.V_z_kN:.2f}",
                    f"{c.V_y_kN:.2f}",
                    f"{c.M_y_kNm:.2f}",
                    f"{c.N_kN:.2f}",
                    "★" if c.governing else "",
                ]
                for c in combos
            ]

        combo_headers = ["Combinação", "V_z (kN)", "V_y (kN)", "M_y (kNm)", "N (kN)", "Gov."]
        combo_widths = [48 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm, 14 * mm]

        if res.all_combinations:
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph("4.1 Combinações de acções (totais)", S_h2))
            story.append(
                data_table(
                    combo_headers, _combo_rows(res.all_combinations), col_widths=combo_widths
                )
            )
        if res.member_forces:
            story.append(Spacer(1, 2 * mm))
            story.append(
                Paragraph("4.2 Esforços de cálculo no elemento (modelo do tipo de suporte)", S_h2)
            )
            story.append(
                data_table(combo_headers, _combo_rows(res.member_forces), col_widths=combo_widths)
            )
            story.append(
                Paragraph(
                    "Nota: a tabela 4.1 apresenta acções totais; a tabela 4.2 apresenta os "
                    "esforços no elemento dimensionante após o modelo estrutural do suporte. "
                    "Os dois níveis não são directamente comparáveis.",
                    S_note,
                )
            )
    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 5. PERFIL DIMENSIONADO
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph(t("pdf.section.section", _lang), S_h1))
    if res and res.recommended_section:
        sec = res.recommended_section
        story.append(
            kv_table(
                [
                    ("Perfil seleccionado", f"<b>{sec.designation}</b>  ({sec.family.value})"),
                    ("Aço", inp.steel_grade.value if inp else "—"),
                    ("h × b × tw × tf", f"{sec.h_mm} × {sec.b_mm} × {sec.tw_mm} × {sec.tf_mm} mm"),
                    ("A", f"{sec.A_cm2:.1f} cm²"),
                    ("I_y", f"{sec.I_y_cm4:.1f} cm⁴"),
                    ("W_el,y", f"{sec.W_el_y_cm3:.1f} cm³"),
                    ("Peso linear", f"{sec.weight_kgm:.1f} kg/m"),
                ]
            )
        )
    if res and res.section_verification:
        sv = res.section_verification
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph("Verificações:", S_h2))
        bg = _STATUS_COLORS.get(sv.status.value, WHITE)
        check_rows = [
            [k, f"{v:.3f}", "OK" if v <= 1.0 else "FALHA"]
            for k, v in sv.utilization_by_check.items()
        ]
        story.append(
            data_table(
                ["Verificação", "η (utilização)", "Estado"],
                check_rows,
                col_widths=[80 * mm, 40 * mm, 30 * mm],
            )
        )
        story.append(
            Paragraph(
                f"Ratio máximo: <b>η = {sv.utilization_ratio:.3f}</b>  "
                f"(governa: {sv.governing_check})  |  Cláusula: {sv.code_clause}",
                S_body,
            )
        )
        if res.member_check_rows:
            lang = Lang.PT
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(t("report.section.memberChecks", lang), S_h2))
            member_rows = [
                [
                    str(row.get("member_id", "")),
                    str(row.get("member_kind", "")),
                    member_status_label(str(row.get("status", "")), lang),
                    f"{float(row.get('utilization_ratio', 0.0)):.3f}",
                    str(row.get("governing_check", "")),
                    str(row.get("governing_combination", "")),
                    member_axis_label(row.get("governing_axis"), lang),
                    f"{float(row.get('axial_force_kN', 0.0)):.3f}",
                    f"{float(row.get('shear_force_kN', 0.0)):.3f}",
                    f"{float(row.get('bending_moment_kNm', 0.0)):.3f}",
                ]
                for row in res.member_check_rows
            ]
            story.append(
                data_table(
                    [
                        t("report.column.member", lang),
                        t("report.column.type", lang),
                        t("report.column.status", lang),
                        t("report.column.eta", lang),
                        t("report.column.governingCheck", lang),
                        t("report.column.combination", lang),
                        t("report.column.axis", lang),
                        t("report.column.axialForce", lang),
                        t("report.column.shearForce", lang),
                        t("report.column.bendingMoment", lang),
                    ],
                    member_rows,
                    col_widths=[
                        16 * mm,
                        12 * mm,
                        16 * mm,
                        10 * mm,
                        26 * mm,
                        18 * mm,
                        8 * mm,
                        13 * mm,
                        13 * mm,
                        14 * mm,
                    ],
                )
            )
            if sv.assumptions_used:
                story.append(
                    Paragraph(
                        f"{t('report.label.assumptions', lang)}: " + ", ".join(sv.assumptions_used),
                        S_note,
                    )
                )
        if sv.calculation_details:
            story.append(CondPageBreak(72 * mm))
            story.append(Spacer(1, 2 * mm))
            story.append(
                Paragraph(
                    f"Memória de fórmulas (combinação governante: "
                    f"{sv.governing_combination or 'n/d'}):",
                    S_h2,
                )
            )
            d = sv.calculation_details
            formula_rows: list[list[str]] = []

            def _frow(label: str, formula: str, *keys: str) -> None:
                if all(k in d for k in keys):
                    values = " | ".join(f"{k} = {d[k]:g}" for k in keys)
                    formula_rows.append([label, formula, values])

            _frow(
                "Corte (cl. 6.2.6)",
                "Vpl,Rd = Av·fy/(√3·γM0)",
                "Av_mm2",
                "Vpl_Rd_kN",
                "V_Ed_kN",
            )
            _frow(
                "Flexão M_y (cl. 6.2.5)",
                "Mc,Rd = W_pl,y·fy,eff/γM0",
                "Mc_Rd_kNm",
                "M_Ed_kNm",
            )
            _frow(
                "Flexão M_z (cl. 6.2.9)",
                "Mc,z,Rd = W_pl,z·fy,eff/γM0",
                "Mc_z_Rd_kNm",
                "M_z_Ed_kNm",
            )
            _frow(
                "Encurvadura lateral (cl. 6.3.2)",
                "Mb,Rd = χ_LT·W_pl,y·fy/γM1; λ_LT = √(W_pl·fy/Mcr)",
                "Mcr_kNm",
                "lambda_LT",
                "chi_LT",
                "Mb_Rd_kNm",
            )
            _frow(
                "Compressão (cl. 6.2.4)",
                "Nc,Rd = A·fy/γM0",
                "Nc_Rd_kN",
                "N_Ed_kN",
            )
            _frow(
                "Encurvadura compressão (cl. 6.3.1)",
                "Nb,Rd = χ_z·A·fy/γM1",
                "lambda_z",
                "chi_z",
                "Nb_Rd_kN",
            )
            if formula_rows:
                story.append(
                    data_table(
                        ["Verificação", "Fórmula", "Valores intermédios"],
                        formula_rows,
                        col_widths=[42 * mm, 52 * mm, W - 94 * mm],
                    )
                )
            story.append(
                Paragraph(
                    f"Coeficientes parciais: γM0 = {d.get('gamma_M0', 1.0):g}, "
                    f"γM1 = {d.get('gamma_M1', 1.0):g} | fy = {d.get('fy_MPa', 0):g} MPa",
                    S_note,
                )
            )
    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 6. MESA / BASE PLATE (se activada)
    # ══════════════════════════════════════════════════════════════════════════
    if res and res.base_plate:
        story.extend(section_heading(t("pdf.section.basePlate", _lang), 76 * mm))
        bp = res.base_plate
        story.append(
            kv_table(
                [
                    ("Dimensões L × B", f"{bp.length_mm:.0f} × {bp.width_mm:.0f} mm"),
                    ("Espessura", f"{bp.thickness_mm:.0f} mm"),
                    ("Aço da chapa", bp.steel_grade.value),
                    (
                        "Tensão de contacto",
                        f"{bp.bearing_stress_mpa:.2f} MPa  (η = {bp.utilization_bearing:.3f})",
                    ),
                    ("Flexão da chapa", f"η = {bp.utilization_bending:.3f}"),
                    (
                        "Parafusos ventilador → chapa",
                        f"M{bp.bolt_diameter_mm:.0f} × {bp.n_bolts_fan}  (η = {bp.bolt_utilization_fan:.3f})",
                    ),
                    (
                        "Parafusos chapa → estrutura",
                        f"M20 × {bp.n_bolts_structure}  (η = {bp.bolt_utilization_structure:.3f})",
                    ),
                    (
                        "Furação",
                        f"d0={bp.hole_diameter_mm:.1f} mm | p={bp.anchor_spacing_x_mm:.0f}×{bp.anchor_spacing_y_mm:.0f} mm | e={bp.edge_distance_x_mm:.0f}/{bp.edge_distance_y_mm:.0f} mm",
                    ),
                    (
                        "Mínimos geométricos",
                        f"p_min={bp.min_spacing_mm:.1f} mm | e_min={bp.min_edge_distance_mm:.1f} mm",
                    ),
                    (
                        "Cone de betão",
                        f"N_Rd={bp.concrete_cone_capacity_kN:.2f} kN  (η = {bp.utilization_concrete_cone:.3f})",
                    ),
                    (
                        "Arrancamento / pull-out",
                        f"N_Rd={bp.pullout_capacity_kN:.2f} kN  (η = {bp.utilization_pullout:.3f})",
                    ),
                    (
                        "Pry-out",
                        f"V_Rd={bp.pryout_capacity_kN:.2f} kN  (η = {bp.utilization_pryout:.3f})",
                    ),
                    (
                        "Soldadura chapa → perfil (a)",
                        f"{bp.weld_throat_mm:.1f} mm  (η = {bp.weld_utilization:.3f})",
                    ),
                    ("Cláusula", bp.code_clause),
                ]
            )
        )
        story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 7. ANCORAGENS
    # ══════════════════════════════════════════════════════════════════════════
    if res and res.anchor and res.anchor.anchor_type == "rod":
        story.append(Paragraph(t("pdf.section.anchors", _lang), S_h1))
    else:
        story.extend(section_heading(t("pdf.section.anchors", _lang), 56 * mm))
    if res and res.anchor:
        anc = res.anchor
        anc_rows = [
            (
                "Tipo de verificação",
                "Varão roscado de suspensão (sem betão)"
                if anc.anchor_type == "rod"
                else "Ancoragem embebida em betão",
            ),
            ("Número", str(anc.n_anchors)),
            ("Diâmetro", f"Ø{anc.anchor_diameter_mm:.0f} mm"),
        ]
        if anc.anchor_type != "rod":
            anc_rows.append(("Profundidade de embebimento", f"{anc.embedment_depth_mm:.0f} mm"))
        anc_rows += [
            (
                "Capacidade de tracção total",
                f"{anc.tensile_capacity_kN:.2f} kN  (η = {anc.utilization_tension:.3f})",
            ),
            (
                "Capacidade de corte total",
                f"{anc.shear_capacity_kN:.2f} kN  (η = {anc.utilization_shear:.3f})",
            ),
            ("Interacção tracção + corte", f"η_comb = {anc.utilization_combined:.3f}"),
            ("Cláusula", anc.code_clause),
        ]
        story.append(kv_table(anc_rows))
        story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 8. LIGAÇÕES METÁLICAS
    # ══════════════════════════════════════════════════════════════════════════
    if res and res.metal_connection:
        story.extend(section_heading(t("pdf.section.metalConnection", _lang), 62 * mm))
        mc = res.metal_connection
        story.append(
            kv_table(
                [
                    ("Tipo de ligação", mc.connection_type),
                    ("Chapa de ligação", f"{mc.plate_thickness_mm:.1f} mm"),
                    (
                        "Parafusos perfil-perfil",
                        f"M{mc.bolt_diameter_mm:.0f} × {mc.n_bolts} ({mc.bolt_grade}) | d0={mc.bolt_hole_diameter_mm:.1f} mm",
                    ),
                    (
                        "Espaçamentos",
                        f"p={mc.provided_spacing_mm:.1f} mm ≥ {mc.min_spacing_mm:.1f} mm | e={mc.provided_edge_distance_mm:.1f} mm ≥ {mc.min_edge_distance_mm:.1f} mm",
                    ),
                    (
                        "Capacidade parafusos",
                        f"Corte={mc.bolt_shear_capacity_kN:.2f} kN (η={mc.utilization_bolt_shear:.3f}) | Tração={mc.bolt_tension_capacity_kN:.2f} kN (η={mc.utilization_bolt_tension:.3f})",
                    ),
                    (
                        "Soldadura real",
                        f"a={mc.weld_throat_mm:.1f} mm | L={mc.weld_length_mm:.0f} mm | η={mc.weld_utilization:.3f}",
                    ),
                    (
                        "Stiffeners",
                        f"{mc.stiffener_thickness_mm:.1f} mm"
                        if mc.stiffener_required
                        else "Não requeridos pelo modelo",
                    ),
                    ("Cantoneiras", mc.cleat_angle or "—"),
                    ("Diagonais", mc.diagonal_member or "—"),
                    ("η global", f"{mc.utilization_ratio:.3f}"),
                    ("Cláusula", mc.code_clause),
                ]
            )
        )
        story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 9. VERIFICAÇÃO FINAL
    # ══════════════════════════════════════════════════════════════════════════
    story.extend(section_heading(t("pdf.section.finalCheck", _lang), 52 * mm))
    if res and assessment:
        status_val = res.status.value
        bg = RED_BG if assessment.is_failure else WARN_BG if assessment.is_borderline else GREEN_BG
        status_data = [
            [
                Paragraph("<b>Conclusão</b>", S_body),
                Paragraph(f"<b>{assessment.headline}</b>", S_body),
            ],
            [
                Paragraph("<b>Estado técnico</b>", S_body),
                Paragraph(status_val, S_body),
            ],
            [
                Paragraph("<b>Classificação</b>", S_body),
                Paragraph(res.classification_level.value, S_body),
            ],
            [
                Paragraph("<b>Verificação governante</b>", S_body),
                Paragraph(assessment.governing_item, S_body),
            ],
            [
                Paragraph("<b>Utilização governante</b>", S_body),
                Paragraph(fmt_pct(assessment.utilization_percent), S_body),
            ],
            [
                Paragraph("<b>Conservadorismo informativo</b>", S_body),
                Paragraph(fmt_pct(assessment.conservatism_percent), S_body),
            ],
            [
                Paragraph("<b>Nota</b>", S_body),
                Paragraph(assessment.summary, S_body),
            ],
        ]
        st = Table(status_data, colWidths=[W * 0.34, W * 0.66])
        st.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), _color(bg)),
                    ("BACKGROUND", (0, 1), (0, -1), _color(LIGHT)),
                    ("GRID", (0, 0), (-1, -1), 0.4, _color((0.80, 0.85, 0.92))),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(st)
    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 10. CITAÇÕES NORMATIVAS
    # ══════════════════════════════════════════════════════════════════════════
    story.extend(section_heading(t("pdf.section.normativeRefs", _lang), 60 * mm))
    if ctx.citations:
        cit_rows = [
            [c.standard_id, c.edition or "—", c.clause or "—", c.description or "—"]
            for c in ctx.citations
        ]
        story.append(
            data_table(
                ["Norma", "Edição", "Cláusula", "Descrição"],
                cit_rows,
                col_widths=[30 * mm, 18 * mm, 35 * mm, W - 83 * mm],
            )
        )
    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 11. LIMITAÇÕES E PRESSUPOSTOS
    # ══════════════════════════════════════════════════════════════════════════
    story.extend(section_heading(t("pdf.section.limitations", _lang), 54 * mm))
    if ctx.assumptions_declared:
        from ..config import get_assumptions

        assumption_index = {
            a.get("id"): a.get("description", "") for a in get_assumptions().get("assumptions", [])
        }
        story.append(Paragraph("<b>Pressupostos declarados:</b>", S_h2))
        for a_id in ctx.assumptions_declared:
            desc = assumption_index.get(a_id, "")
            text = f"• <b>{a_id}</b>" + (f" — {desc}" if desc else "")
            story.append(Paragraph(text, S_note))
    if ctx.limitations:
        story.append(Paragraph("<b>Limitações:</b>", S_h2))
        for lim in ctx.limitations:
            story.append(Paragraph(f"• {lim}", S_note))
    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 12. AVISOS
    # ══════════════════════════════════════════════════════════════════════════
    # ── Phase 07: Engineering warnings section (always present) ───────────────
    _phase07_warnings: list[str] = []
    if not _is_global_frame:
        _phase07_warnings.append(t("warning.model.simplified", _lang))
    if _include_sls and not _displacement_available:
        _phase07_warnings.append(t("warning.serviceability.notVerified", _lang))
    if not _has_connection_rows:
        _phase07_warnings.append(t("warning.connection.basePlateNotVerified", _lang))
        _phase07_warnings.append(t("warning.connection.anchorNotVerified", _lang))
        _phase07_warnings.append(t("warning.connection.weldNotVerified", _lang))
    _phase07_warnings.append(t("warning.engineer.reviewRequired", _lang))
    _phase07_warnings.append(t("warning.tramex.notBasePlate", _lang))

    story.extend(section_heading(t("report.section.engineeringWarnings", _lang), 40 * mm))
    for _w_txt in _phase07_warnings:
        story.append(
            Paragraph(
                f"⚠ {_w_txt}",
                ParagraphStyle(
                    "eng_warn",
                    fontName="Helvetica-Oblique",
                    fontSize=8.5,
                    textColor=_color((0.7, 0.35, 0.0)),
                    leading=12,
                    spaceAfter=2,
                ),
            )
        )
    story.append(Spacer(1, 4 * mm))

    if ctx.warnings:
        story.extend(section_heading(t("pdf.section.warnings", _lang), 40 * mm))
        for w in ctx.warnings:
            sev = w.severity.upper()
            color_map = {"CRITICAL": CORAL, "WARNING": (0.8, 0.5, 0.0), "INFO": GREY}
            col = color_map.get(sev, GREY)
            story.append(
                Paragraph(
                    f"<font color='#{int(col[0] * 255):02x}{int(col[1] * 255):02x}{int(col[2] * 255):02x}'>"
                    f"[{sev}]</font> {w.message}",
                    S_note,
                )
            )

    # ══════════════════════════════════════════════════════════════════════════
    # 13. RASTREABILIDADE DE DADOS E VERSÃO
    # ══════════════════════════════════════════════════════════════════════════
    story.extend(section_heading(t("pdf.section.traceability", _lang), 70 * mm))
    story.append(
        kv_table(
            [
                ("Versão do software", f"SFSC v{__version__}"),
                ("Hash combinado dos datasets", combined_hash),
            ]
        )
    )
    datasets = provenance.get("datasets", {})
    if datasets:
        story.append(Spacer(1, 2 * mm))
        ds_rows = [
            [name, str(meta.get("sha256", ""))[:12], str(meta.get("modified", "—"))]
            for name, meta in datasets.items()
        ]
        story.append(
            data_table(
                ["Dataset", "SHA-256 (12)", "Modificado"],
                ds_rows,
                col_widths=[90 * mm, 40 * mm, W - 130 * mm],
            )
        )
        story.append(
            Paragraph(
                "Um relatório só é reproduzível com a mesma versão de software e os "
                "mesmos hashes de dataset.",
                S_note,
            )
        )
    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 14. ASSINATURAS
    # ══════════════════════════════════════════════════════════════════════════
    story.append(CondPageBreak(72 * mm))
    signature_block = [Paragraph(t("pdf.section.signatures", _lang), S_h1)]
    sig_rows = [
        [
            Paragraph("<b>Função</b>", S_center),
            Paragraph("<b>Nome</b>", S_center),
            Paragraph("<b>Assinatura</b>", S_center),
            Paragraph("<b>Data</b>", S_center),
        ],
        [Paragraph("Elaborado por", S_body), Paragraph(ctx.prepared_by, S_body), "", ""],
        [Paragraph("Verificado por (Eng. estrutural)", S_body), "", "", ""],
        [Paragraph("Aprovado por", S_body), "", "", ""],
    ]
    sig = Table(
        sig_rows,
        colWidths=[W * 0.30, W * 0.28, W * 0.26, W * 0.16],
        rowHeights=[8 * mm, 12 * mm, 12 * mm, 12 * mm],
    )
    sig.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _color(BLUE)),
                ("TEXTCOLOR", (0, 0), (-1, 0), _color(WHITE)),
                ("GRID", (0, 0), (-1, -1), 0.4, _color((0.80, 0.85, 0.92))),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    signature_block.append(sig)
    signature_block.append(
        Paragraph(
            "A verificação por engenheiro estrutural qualificado é obrigatória antes "
            "de qualquer uso em projecto ou construção.",
            S_note,
        )
    )
    story.append(KeepTogether(signature_block))

    # ══════════════════════════════════════════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════════════════════════════════════════
    def _decorate_page(canvas, _doc) -> None:
        canvas.saveState()
        page_num = canvas.getPageNumber()
        left = doc.leftMargin
        right = A4[0] - doc.rightMargin
        top_y = A4[1] - 13 * mm
        bottom_y = 13 * mm

        if page_num > 1:
            canvas.setStrokeColor(colors.Color(0.80, 0.85, 0.92))
            canvas.setLineWidth(0.45)
            canvas.line(left, top_y - 4 * mm, right, top_y - 4 * mm)
            canvas.setFont("Helvetica-Bold", 8.5)
            canvas.setFillColor(_color(BLUE))
            canvas.drawString(left, top_y, "SFSC - Steel Fan Support Calc")
            canvas.setFont("Helvetica", 7.5)
            canvas.setFillColor(_color(GREY))
            canvas.drawRightString(
                right,
                top_y,
                f"{ctx.project_name} | {ctx.support_tag} | Rev. {ctx.revision} | {ctx.date}",
            )

        canvas.setStrokeColor(colors.Color(0.80, 0.85, 0.92))
        canvas.setLineWidth(0.35)
        canvas.line(left, bottom_y + 4 * mm, right, bottom_y + 4 * mm)
        canvas.setFont("Helvetica-Bold", 6.7)
        canvas.setFillColor(_color(CORAL))
        canvas.drawCentredString(
            A4[0] / 2,
            bottom_y + 1.5 * mm,
            t("pdf.footer.warning", _lang),
        )
        canvas.setFont("Helvetica", 6.7)
        canvas.setFillColor(_color(GREY))
        canvas.drawString(left, bottom_y - 2.2 * mm, f"SFSC v{__version__} | dados {combined_hash}")
        canvas.drawRightString(right, bottom_y - 2.2 * mm, f"Pag. {page_num}")

        if is_preliminary:
            canvas.setFont("Helvetica-Bold", 42)
            canvas.setFillColor(colors.Color(0.95, 0.55, 0.50, alpha=0.075))
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(45)
            canvas.drawCentredString(0, 24, "PRELIMINAR")
            canvas.drawCentredString(0, -32, "NAO APROVADO")
        canvas.restoreState()

    doc.build(story, onFirstPage=_decorate_page, onLaterPages=_decorate_page)
    pdf_bytes = buf.getvalue()

    if output_path:
        Path(output_path).write_bytes(pdf_bytes)

    return pdf_bytes
