"""Orquestrador principal — run_full_calculation()."""
from __future__ import annotations
import datetime
import logging
from ..models import (
    FanSupportInput, FanSupportResult, ReportContext,
    CitationItem, WarningItem,
)
from ..enums import (
    SupportType, StructuralCode, Country, OperationMode,
)
from ..validators import validate_fan_support_input
from ..catalogs.seismic_catalog import get_seismic_factor, get_seismic_code
from ..catalogs.steel_section_catalog import get_section
from .loads import calculate_loads
from .section_verifier import verify_section, auto_select_section, find_passing_sections
from .base_plate import calculate_base_plate
from .anchor import calculate_anchor
from .metal_connections import calculate_metal_connection
from .checker import run_checker, classify
from .support_types.hanger import calc_hanger
from .support_types.cantilever_1 import calc_cantilever_1
from .support_types.cantilever_2 import calc_cantilever_2
from .support_types.cantilever_3 import calc_cantilever_3
from .support_types.pedestal import calc_pedestal
from .support_types.combined import calc_combined

logger = logging.getLogger("sfsc.selector")

_STRUCTURAL_CODE_MAP: dict[Country, StructuralCode] = {
    Country.PORTUGAL:   StructuralCode.EC3_EN1993,
    Country.SPAIN:      StructuralCode.EC3_EN1993,
    Country.IRELAND:    StructuralCode.EC3_EN1993,
    Country.EU_GENERIC: StructuralCode.EC3_EN1993,
    Country.UK:         StructuralCode.EC3_UK_NA,
    Country.FRANCE:     StructuralCode.EC3_NF_NA,
    Country.BRAZIL:     StructuralCode.NBR_8800,
    Country.CHILE:      StructuralCode.NCH_427,
}

_SUPPORT_ENGINES = {
    SupportType.HANGER:       calc_hanger,
    SupportType.CANTILEVER_1: calc_cantilever_1,
    SupportType.CANTILEVER_2: calc_cantilever_2,
    SupportType.CANTILEVER_3: calc_cantilever_3,
    SupportType.PEDESTAL:     calc_pedestal,
    SupportType.COMBINED:     calc_combined,
}


def resolve_structural_code(country: Country) -> StructuralCode:
    return _STRUCTURAL_CODE_MAP.get(country, StructuralCode.EC3_EN1993)


def context_for_section_choice(ctx: ReportContext, designation: str) -> ReportContext:
    """Recalcula o contexto activo para um perfil aprovado escolhido na UI."""
    inp = ctx.fan_support_input
    res = ctx.fan_support_result
    if inp is None or res is None or not res.section_options:
        return ctx

    chosen = next(
        (opt for opt in res.section_options if opt.section.designation == designation),
        None,
    )
    if chosen is None:
        return ctx

    current = res.recommended_section.designation if res.recommended_section else None
    if current == chosen.section.designation:
        return ctx

    verify_inp = inp.model_copy(update={
        "operation_mode": OperationMode.VERIFY,
        "received_section_family": chosen.section.family,
        "received_section_tag": chosen.section.designation,
    })
    selected_ctx = run_full_calculation(verify_inp)
    if selected_ctx.fan_support_result:
        selected_ctx.fan_support_result.section_options = res.section_options
    selected_ctx.fan_support_input = inp
    return selected_ctx


def run_full_calculation(inp: FanSupportInput) -> ReportContext:
    """
    Fluxo completo:
    1. Validação
    2. Código estrutural e factor sísmico
    3. Cargas e combinações
    4. Motor do tipo de suporte → esforços + comprimentos de encurvadura
    5. Selecção/verificação da secção
    6. Mesa (se activada)
    7. Ancoragens
    8. Checker final + classificação
    9. ReportContext com citações normativas
    """
    citations:   list[CitationItem] = []
    warn_items:  list[WarningItem]  = []
    assumptions: list[str]          = []

    # ── 1. Validação ──────────────────────────────────────────────────────────
    validate_fan_support_input(inp)

    # ── 2. Código e sismo ─────────────────────────────────────────────────────
    struct_code  = resolve_structural_code(inp.country)
    seismic_code = get_seismic_code(inp.country)
    ag_g, zone_used = get_seismic_factor(inp.country, inp.seismic_zone)

    if inp.seismic_zone is None:
        warn_items.append(WarningItem(
            code="W-SEISMIC-001",
            severity="WARNING",
            message=(
                f"Factor sísmico de tabela interna: ag/g = {ag_g} (zona '{zone_used}'). "
                "Verificar com zonamento sísmico local do projecto."
            ),
            module="selector",
            assumption_id="A-GEN-003",
        ))
    assumptions.append("A-GEN-003")

    citations.append(CitationItem(
        standard_id=struct_code.value,
        clause="cl. 6.2 + 6.3",
        description="Verificação de secções e elementos estruturais",
    ))
    citations.append(CitationItem(
        standard_id=seismic_code.value,
        clause="Tabela NA — factores sísmicos por zona",
        description="Factor de aceleração de projecto ag/g",
    ))
    citations.append(CitationItem(
        standard_id="EN1990",
        clause="cl. 6.4.3.2",
        description="Combinações de acções ULS fundamental e sísmica",
    ))
    citations.append(CitationItem(
        standard_id="VDI3840",
        clause="Factor dinâmico 1.5",
        description="Factor de amplificação dinâmica para ventiladores industriais",
    ))

    # ── 3. Cargas ─────────────────────────────────────────────────────────────
    total_weight_kN, combinations = calculate_loads(inp, struct_code, ag_g)
    assumptions.append("A-GEN-001")
    assumptions.append("A-GEN-002")
    assumptions.append("A-STR-002")

    # ── 4. Motor do tipo de suporte ───────────────────────────────────────────
    engine_fn = _SUPPORT_ENGINES[inp.support_type]
    governing_combo, Lcr_y_mm, Lcr_z_mm = engine_fn(
        inp, total_weight_kN, combinations, struct_code,
    )
    assumptions.append("A-STR-001")
    assumptions.append("A-STR-003")

    # Marcar combinação governante
    all_combos = []
    for c in combinations:
        if c.name == governing_combo.name:
            all_combos.append(governing_combo)
        else:
            all_combos.append(c)

    # ── 5. Secção ─────────────────────────────────────────────────────────────
    section = None
    sec_result = None
    section_options = []

    if inp.operation_mode == OperationMode.VERIFY:
        section = get_section(inp.received_section_family, inp.received_section_tag)
        sec_result = verify_section(
            section, governing_combo, struct_code, inp.steel_grade,
            Lcr_y_mm, Lcr_z_mm,
        )
        section_options = [sec_result]
    else:
        section_options = find_passing_sections(
            all_combos, struct_code, inp.steel_grade,
            inp.preferred_section_families,
            Lcr_y_mm, Lcr_z_mm,
            max_utilization=1.0,
        )
        if section_options:
            conservative = [opt for opt in section_options if opt.utilization_ratio <= 0.90]
            sec_result = (conservative or section_options)[0]
            section = sec_result.section
        else:
            section, sec_result = auto_select_section(
                all_combos, struct_code, inp.steel_grade,
                inp.preferred_section_families,
                Lcr_y_mm, Lcr_z_mm,
            )

    if sec_result:
        for w in sec_result.warnings:
            warn_items.append(WarningItem(code="W-SEC", severity="WARNING",
                                          message=w, module="section_verifier"))

    # ── 6. Mesa ───────────────────────────────────────────────────────────────
    bp_result = None
    if inp.include_base_plate and section:
        bp_result = calculate_base_plate(
            inp, section, governing_combo, struct_code, inp.concrete_grade,
        )
        assumptions.append("A-BP-001")
        assumptions.append("A-BP-002")
        citations.append(CitationItem(
            standard_id="EN1993-1-8",
            clause="cl. 6.2.5",
            description="Dimensionamento da chapa de assento (base plate)",
        ))
        for w in bp_result.warnings:
            warn_items.append(WarningItem(code="W-BP", severity="INFO",
                                          message=w, module="base_plate"))

    # ── 7. Ancoragens ─────────────────────────────────────────────────────────
    anc_result = calculate_anchor(
        inp, governing_combo, struct_code, inp.concrete_grade,
    )
    assumptions.append("A-ANC-001")
    citations.append(CitationItem(
        standard_id="EN1992-4",
        clause="cl. 7.2.1 + 7.2.2",
        description="Dimensionamento de ancoragens — tracção, corte e interacção",
    ))
    for w in anc_result.warnings:
        warn_items.append(WarningItem(code="W-ANC", severity="WARNING",
                                      message=w, module="anchor"))

    # ── 8. Ligações metálicas ─────────────────────────────────────────────────
    metal_conn_result = None
    if section:
        metal_conn_result = calculate_metal_connection(
            inp, section, governing_combo, struct_code,
        )
        assumptions.append("A-CONN-001")
        citations.append(CitationItem(
            standard_id="EN1993-1-8",
            clause="cl. 3 + 4 + 6",
            description="Ligações metálicas: parafusos, soldaduras, chapas, stiffeners e diagonais",
        ))
        for w in metal_conn_result.warnings:
            warn_items.append(WarningItem(code="W-CONN", severity="WARNING",
                                          message=w, module="metal_connections"))

    # ── 9. Checker + classificação ────────────────────────────────────────────
    fan_result = FanSupportResult(
        support_tag=inp.support_tag,
        support_type=inp.support_type,
        structural_code=struct_code,
        seismic_code=seismic_code,
        seismic_factor_g=ag_g,
        total_weight_kN=round(total_weight_kN, 3),
        design_load_kN=round(governing_combo.V_z_kN, 3),
        governing_load_combination=governing_combo,
        all_combinations=all_combos,
        recommended_section=section,
        section_verification=sec_result,
        section_options=section_options,
        base_plate=bp_result,
        anchor=anc_result,
        metal_connection=metal_conn_result,
        warnings=[w.message for w in warn_items],
        assumptions_used=list(dict.fromkeys(assumptions)),
    )
    fan_result.status = run_checker(inp, fan_result)
    fan_result.classification_level = classify(inp, fan_result)

    if fan_result.classification_level.value == "REQUIRES_SPECIALIST":
        warn_items.append(WarningItem(
            code="W-CLASS-001",
            severity="CRITICAL",
            message=(
                "Classificação REQUIRES_SPECIALIST: "
                "este cálculo requer revisão por engenheiro estrutural qualificado."
            ),
            module="checker",
        ))

    if inp.anti_vibration.value in ("springs", "silentblocks"):
        assumptions.append("A-VIB-001")
        warn_items.append(WarningItem(
            code="W-VIB-001",
            severity="WARNING",
            message="Anti-vibração: dimensionamento dinâmico das molas/silentblocks fora do âmbito (A-VIB-001).",
            module="selector",
        ))

    assumptions.append("A-FAT-001")

    # ── 10. ReportContext ─────────────────────────────────────────────────────
    ctx = ReportContext(
        project_name=inp.project_name,
        support_tag=inp.support_tag,
        prepared_by=inp.prepared_by,
        date=datetime.date.today().isoformat(),
        revision="A",
        fan_support_input=inp,
        fan_support_result=fan_result,
        citations=list({c.standard_id: c for c in citations}.values()),
        warnings=warn_items,
        assumptions_declared=list(dict.fromkeys(assumptions)),
        limitations=[
            "Análise dinâmica de vibrações fora do âmbito (A-VIB-001).",
            "Verificação de fadiga (EN 1993-1-9) fora do âmbito (A-FAT-001).",
            "Dimensionamento de fundações / maciços de betão fora do âmbito.",
            "Ligações soldadas verificadas por tensão nominal — sem análise de raiz.",
            "Execução assume Classe EXC2 conforme EN 1090.",
        ],
    )

    logger.info(
        "Cálculo completo: %s | %s | status=%s | classification=%s",
        inp.support_tag, inp.support_type.value,
        fan_result.status.value, fan_result.classification_level.value,
    )
    return ctx
