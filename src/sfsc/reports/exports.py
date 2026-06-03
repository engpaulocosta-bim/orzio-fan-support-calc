"""Exportação para Excel e CSV."""
from __future__ import annotations
import csv
import io
from pathlib import Path
from typing import Optional
from ..models import ReportContext


def generate_excel(ctx: ReportContext, output_path: Optional[str | Path] = None) -> bytes:
    """Gera workbook Excel com folhas: Resumo, Secção, Mesa, Ancoragens, Combinações."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise ImportError("openpyxl não instalado. Execute: pip install openpyxl")

    wb = openpyxl.Workbook()
    inp = ctx.fan_support_input
    res = ctx.fan_support_result

    BLUE_HEX   = "1447E6"
    LIGHT_HEX  = "EFF4FE"
    CORAL_HEX  = "FF6B5B"
    GREY_HEX   = "64748B"
    GREEN_HEX  = "22C55E"

    def _header_style(cell, bg=BLUE_HEX):
        cell.font = Font(bold=True, color="FFFFFF", size=10)
        cell.fill = PatternFill("solid", fgColor=bg)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    def _set_col_widths(ws, widths: list[int]):
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

    def _kv_row(ws, row, key, value, row_n):
        ws.cell(row=row_n, column=1, value=key).font = Font(bold=True, size=9)
        ws.cell(row=row_n, column=1).fill = PatternFill("solid", fgColor=LIGHT_HEX)
        ws.cell(row=row_n, column=2, value=value).font = Font(size=9)
        ws.cell(row=row_n, column=2).alignment = Alignment(wrap_text=True)

    # ── Folha 1: Resumo ───────────────────────────────────────────────────────
    ws = wb.active
    ws.title = "Resumo"
    ws.cell(1, 1, "SFSC — Steel Fan Support Calc").font = Font(bold=True, size=14, color=BLUE_HEX)
    ws.cell(2, 1, f"Projecto: {ctx.project_name}  |  Tag: {ctx.support_tag}  |  {ctx.date}")
    ws.cell(2, 1).font = Font(size=9, color=GREY_HEX)
    n = 4
    kv_data = []
    if inp:
        kv_data += [
            ("Tipo de suporte", inp.support_type.value),
            ("País / norma", f"{inp.country.value}"),
            ("Aço", inp.steel_grade.value),
            ("Peso total operação [kg]", inp.total_operating_weight_kg),
            ("Carga de projecto [kN]", res.design_load_kN if res else "—"),
            ("Factor sísmico ag/g", res.seismic_factor_g if res else "—"),
        ]
    if res:
        kv_data += [
            ("Perfil seleccionado", res.recommended_section.designation if res.recommended_section else "—"),
            ("Utilização máx. secção", res.section_verification.utilization_ratio if res.section_verification else "—"),
            ("Estado global", res.status.value),
            ("Classificação", res.classification_level.value),
        ]
    for k, v in kv_data:
        _kv_row(ws, None, k, v, n)
        n += 1
    _set_col_widths(ws, [35, 30])

    # ── Folha 2: Combinações ──────────────────────────────────────────────────
    ws2 = wb.create_sheet("Combinações")
    headers_c = ["Combinação", "V_z (kN)", "V_y (kN)", "M_y (kNm)", "N (kN)", "Governante"]
    for j, h in enumerate(headers_c, 1):
        _header_style(ws2.cell(1, j, h))
    if res and res.all_combinations:
        for i, c in enumerate(res.all_combinations, 2):
            ws2.cell(i, 1, c.name)
            ws2.cell(i, 2, round(c.V_z_kN, 3))
            ws2.cell(i, 3, round(c.V_y_kN, 3))
            ws2.cell(i, 4, round(c.M_y_kNm, 3))
            ws2.cell(i, 5, round(c.N_kN, 3))
            ws2.cell(i, 6, "Sim" if c.governing else "")
    _set_col_widths(ws2, [28, 16, 16, 16, 16, 14])

    # ── Folha 3: Secção ───────────────────────────────────────────────────────
    ws3 = wb.create_sheet("Secção")
    if res and res.recommended_section:
        sec = res.recommended_section
        n3 = 1
        for k, v in [
            ("Designação", sec.designation), ("Família", sec.family.value),
            ("h [mm]", sec.h_mm), ("b [mm]", sec.b_mm),
            ("tw [mm]", sec.tw_mm), ("tf [mm]", sec.tf_mm),
            ("A [cm²]", sec.A_cm2), ("I_y [cm⁴]", sec.I_y_cm4),
            ("W_el,y [cm³]", sec.W_el_y_cm3), ("Peso [kg/m]", sec.weight_kgm),
        ]:
            _kv_row(ws3, None, k, v, n3); n3 += 1

        if res.section_verification:
            sv = res.section_verification
            n3 += 1
            ws3.cell(n3, 1, "Verificações").font = Font(bold=True, color=BLUE_HEX)
            n3 += 1
            headers_v = ["Check", "η (utilização)", "Estado"]
            for j, h in enumerate(headers_v, 1):
                _header_style(ws3.cell(n3, j))
            n3 += 1
            for check, eta in sv.utilization_by_check.items():
                ws3.cell(n3, 1, check)
                ws3.cell(n3, 2, round(eta, 4))
                ws3.cell(n3, 3, "OK" if eta <= 1.0 else "FALHA")
                if eta > 1.0:
                    ws3.cell(n3, 3).fill = PatternFill("solid", fgColor="FECACA")
                n3 += 1
    _set_col_widths(ws3, [28, 20, 16])

    # ── Folha 4: Mesa ─────────────────────────────────────────────────────────
    if res and res.base_plate:
        ws4 = wb.create_sheet("Mesa (Base Plate)")
        bp = res.base_plate
        n4 = 1
        for k, v in [
            ("L [mm]", bp.length_mm), ("B [mm]", bp.width_mm),
            ("Espessura [mm]", bp.thickness_mm), ("Aço", bp.steel_grade.value),
            ("σ_bearing [MPa]", bp.bearing_stress_mpa),
            ("η_bearing", bp.utilization_bearing), ("η_bending", bp.utilization_bending),
            ("Parafusos ventilador", f"M{bp.bolt_diameter_mm:.0f} × {bp.n_bolts_fan}"),
            ("η_bolt_fan", bp.bolt_utilization_fan),
            ("Parafusos estrutura", f"M20 × {bp.n_bolts_structure}"),
            ("η_bolt_str", bp.bolt_utilization_structure),
            ("Garganta soldadura [mm]", bp.weld_throat_mm),
            ("η_weld", bp.weld_utilization), ("Estado", bp.status.value),
        ]:
            _kv_row(ws4, None, k, v, n4); n4 += 1
        _set_col_widths(ws4, [35, 25])

    # ── Folha 5: Ancoragens ───────────────────────────────────────────────────
    if res and res.anchor:
        ws5 = wb.create_sheet("Ancoragens")
        anc = res.anchor
        n5 = 1
        for k, v in [
            ("Nº ancoragens", anc.n_anchors),
            ("Diâmetro [mm]", anc.anchor_diameter_mm),
            ("Profundidade hef [mm]", anc.embedment_depth_mm),
            ("N_Rd total [kN]", anc.tensile_capacity_kN),
            ("V_Rd total [kN]", anc.shear_capacity_kN),
            ("η_tracção", anc.utilization_tension),
            ("η_corte", anc.utilization_shear),
            ("η_interacção", anc.utilization_combined),
            ("Estado", anc.status.value), ("Cláusula", anc.code_clause),
        ]:
            _kv_row(ws5, None, k, v, n5); n5 += 1
        _set_col_widths(ws5, [35, 25])

    buf = io.BytesIO()
    wb.save(buf)
    xlsx_bytes = buf.getvalue()
    if output_path:
        Path(output_path).write_bytes(xlsx_bytes)
    return xlsx_bytes


def generate_csv(ctx: ReportContext, output_path: Optional[str | Path] = None) -> str:
    """Gera CSV resumo de uma linha (útil para batch)."""
    inp = ctx.fan_support_input
    res = ctx.fan_support_result

    fields = {
        "support_tag": ctx.support_tag,
        "project": ctx.project_name,
        "support_type": inp.support_type.value if inp else "",
        "country": inp.country.value if inp else "",
        "total_weight_kg": inp.total_operating_weight_kg if inp else "",
        "design_load_kN": res.design_load_kN if res else "",
        "seismic_factor_g": res.seismic_factor_g if res else "",
        "section": res.recommended_section.designation if (res and res.recommended_section) else "",
        "section_utilization": res.section_verification.utilization_ratio if (res and res.section_verification) else "",
        "base_plate_t_mm": res.base_plate.thickness_mm if (res and res.base_plate) else "",
        "anchor_d_mm": res.anchor.anchor_diameter_mm if (res and res.anchor) else "",
        "n_anchors": res.anchor.n_anchors if (res and res.anchor) else "",
        "status": res.status.value if res else "",
        "classification": res.classification_level.value if res else "",
    }
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(fields.keys()))
    writer.writeheader()
    writer.writerow(fields)
    csv_str = buf.getvalue()
    if output_path:
        Path(output_path).write_text(csv_str, encoding="utf-8")
    return csv_str
