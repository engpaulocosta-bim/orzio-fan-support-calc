"""Geração do memorial de cálculo em PDF — ReportLab."""

from __future__ import annotations

import io
from pathlib import Path

from .. import __version__
from ..assessment import assess_result
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


def generate_pdf(ctx: ReportContext, output_path: str | Path | None = None) -> bytes:
    """Gera memorial PDF e retorna bytes. Escreve ficheiro se output_path fornecido."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            HRFlowable,
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
        topMargin=25 * mm,
        bottomMargin=25 * mm,
    )

    W = A4[0] - 40 * mm

    def _color(rgb):
        return colors.Color(*rgb)

    S_title = ParagraphStyle(
        "title", fontName="Helvetica-Bold", fontSize=16, textColor=_color(BLUE), spaceAfter=4
    )
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
    S_right = ParagraphStyle(
        "right", fontName="Helvetica", fontSize=8, alignment=TA_RIGHT, textColor=_color(GREY)
    )

    def hr():
        return HRFlowable(
            width="100%",
            thickness=0.5,
            color=_color((0.8, 0.85, 0.92)),
            spaceAfter=4,
            spaceBefore=4,
        )

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

    story = []

    inp = ctx.fan_support_input
    res = ctx.fan_support_result
    assessment = assess_result(res) if res else None

    def fmt_pct(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.1f}%"

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
        fontSize=24,
        textColor=_color(BLUE),
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    S_cover_sub = ParagraphStyle(
        "cover_sub",
        fontName="Helvetica",
        fontSize=12,
        textColor=_color(GREY),
        alignment=TA_CENTER,
    )
    story.append(Spacer(1, 45 * mm))
    story.append(Paragraph("MEMORIAL DE CÁLCULO", S_cover_title))
    story.append(Paragraph("Suporte metálico para ventilador industrial", S_cover_sub))
    story.append(Paragraph(f"SFSC — Steel Fan Support Calc v{__version__}", S_cover_sub))
    story.append(Spacer(1, 18 * mm))
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
                "DOCUMENTO PRELIMINAR — NÃO APROVADO PARA CONSTRUÇÃO",
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
            "Este memorial apoia, mas não substitui, o julgamento do engenheiro "
            "responsável. Resultados de modelo simplificado — ver secções de "
            "limitações, pressupostos e rastreabilidade.",
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
    header_data = [
        [
            Paragraph("<b>SFSC</b> — Steel Fan Support Calc", S_title),
            Paragraph(f"Rev. {ctx.revision} &nbsp;|&nbsp; {ctx.date}", S_right),
        ]
    ]
    ht = Table(header_data, colWidths=[W * 0.70, W * 0.30])
    ht.setStyle(
        TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("TOPPADDING", (0, 0), (-1, -1), 0)])
    )
    story.append(ht)
    story.append(hr())

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

    # ══════════════════════════════════════════════════════════════════════════
    # 1. IDENTIFICAÇÃO
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("1. IDENTIFICAÇÃO", S_h1))
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
    ]
    if inp and inp.design_notes:
        rows_id.append(("Notas", inp.design_notes))
    story.append(kv_table(rows_id))
    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 2. VENTILADOR
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("2. DADOS DO VENTILADOR", S_h1))
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
    story.append(Paragraph("3. GEOMETRIA E CONFIGURAÇÃO", S_h1))
    if inp:
        rows_geo = [
            ("Tipo de suporte", inp.support_type.value.replace("_", " ").title()),
            ("Vão / comprimento (L)", f"{inp.span_mm:.0f} mm  ({inp.span_mm / 1000:.3f} m)"),
            ("Altura de instalação (h)", f"{inp.installation_height_mm:.0f} mm"),
            ("Excentricidade CG", f"{inp.eccentricity_mm:.0f} mm"),
            ("Factor dinâmico", f"{inp.dynamic_factor}  (VDI 3840)"),
            ("Anti-vibração", inp.anti_vibration.value),
            ("Mesa / base plate", "Sim" if inp.include_base_plate else "Não"),
            ("Classe de exposição", inp.exposure_class.value),
            ("Betão de suporte", inp.concrete_grade),
        ]
        if inp.cantilever_subtype:
            rows_geo.insert(1, ("Subtipo consola", inp.cantilever_subtype.value))
        story.append(kv_table(rows_geo))
    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════════════════════════
    # 4. CARGAS E COMBINAÇÕES
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("4. CARGAS E COMBINAÇÕES DE ACÇÕES", S_h1))
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
    story.append(Paragraph("5. SECÇÃO METÁLICA", S_h1))
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
        if sv.calculation_details:
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
        story.append(Paragraph("6. MESA / CHAPA DE ASSENTO", S_h1))
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
        story.append(Paragraph("7. VARÕES ROSCADOS DE SUSPENSÃO", S_h1))
    else:
        story.append(Paragraph("7. ANCORAGENS", S_h1))
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
        story.append(Paragraph("8. LIGAÇÕES METÁLICAS", S_h1))
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
    story.append(Paragraph("9. VERIFICAÇÃO FINAL", S_h1))
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
    story.append(Paragraph("10. CITAÇÕES NORMATIVAS", S_h1))
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
    story.append(Paragraph("11. LIMITAÇÕES E PRESSUPOSTOS", S_h1))
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
    if ctx.warnings:
        story.append(Paragraph("12. AVISOS", S_h1))
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
    story.append(Paragraph("13. RASTREABILIDADE DE DADOS E VERSÃO", S_h1))
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
    story.append(Paragraph("14. ASSINATURAS", S_h1))
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
    story.append(sig)
    story.append(
        Paragraph(
            "A verificação por engenheiro estrutural qualificado é obrigatória antes "
            "de qualquer uso em projecto ou construção.",
            S_note,
        )
    )

    # ══════════════════════════════════════════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 8 * mm))
    story.append(hr())
    story.append(
        Paragraph(
            "RESTRICTED TO QUALIFIED STRUCTURAL ENGINEERS — "
            "ENGINEERING ESTIMATE ONLY — NOT FOR CONSTRUCTION WITHOUT SPECIALIST REVIEW",
            ParagraphStyle(
                "footer",
                fontName="Helvetica-Bold",
                fontSize=7,
                textColor=_color(CORAL),
                alignment=TA_CENTER,
            ),
        )
    )
    story.append(
        Paragraph(
            f"SFSC v{__version__}  |  {ctx.prepared_by}  |  {ctx.date}  |  dados {combined_hash}",
            ParagraphStyle(
                "footer2",
                fontName="Helvetica",
                fontSize=7,
                textColor=_color(GREY),
                alignment=TA_CENTER,
            ),
        )
    )

    def _decorate_page(canvas, _doc) -> None:
        if not is_preliminary:
            return
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 52)
        canvas.setFillColor(colors.Color(0.95, 0.55, 0.50, alpha=0.18))
        canvas.translate(A4[0] / 2, A4[1] / 2)
        canvas.rotate(45)
        canvas.drawCentredString(0, 60, "PRELIMINAR")
        canvas.drawCentredString(0, -10, "NÃO APROVADO")
        canvas.restoreState()

    doc.build(story, onFirstPage=_decorate_page, onLaterPages=_decorate_page)
    pdf_bytes = buf.getvalue()

    if output_path:
        Path(output_path).write_bytes(pdf_bytes)

    return pdf_bytes
