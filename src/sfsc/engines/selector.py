"""Orquestrador principal — run_full_calculation()."""

from __future__ import annotations

import datetime
import logging

from ..catalogs.seismic_catalog import get_seismic_code, get_seismic_factor
from ..catalogs.steel_section_catalog import get_section
from ..config import get_dataset_provenance
from ..enums import (
    CheckerStatus,
    Country,
    ExposureClass,
    OperationMode,
    StructuralCode,
    SupportType,
)
from ..exceptions import DatasetMissingError, OutOfScopeError
from ..models import (
    CitationItem,
    FanSupportInput,
    FanSupportResult,
    LoadCombination,
    ReportContext,
    WarningItem,
)
from ..policy import WeightBand, weight_band, weight_warning
from ..validators import validate_fan_support_input
from .anchor import calculate_anchor
from .base_plate import calculate_base_plate
from .checker import classify, run_checker
from .loads import calculate_loads
from .metal_connections import calculate_metal_connection
from .section_verifier import (
    auto_select_section,
    find_passing_sections,
    verify_section_envelope,
)
from .support_types.cantilever_1 import calc_cantilever_1
from .support_types.cantilever_2 import calc_cantilever_2
from .support_types.cantilever_3 import calc_cantilever_3
from .support_types.combined import calc_combined
from .support_types.hanger import calc_hanger
from .support_types.pedestal import calc_pedestal

logger = logging.getLogger("sfsc.selector")

_STRUCTURAL_CODE_MAP: dict[Country, StructuralCode] = {
    Country.PORTUGAL: StructuralCode.EC3_EN1993,
    Country.SPAIN: StructuralCode.EC3_EN1993,
    Country.IRELAND: StructuralCode.EC3_EN1993,
    Country.EU_GENERIC: StructuralCode.EC3_EN1993,
    Country.UK: StructuralCode.EC3_UK_NA,
    Country.FRANCE: StructuralCode.EC3_NF_NA,
    Country.BRAZIL: StructuralCode.NBR_8800,
    Country.CHILE: StructuralCode.NCH_427,
}

_SUPPORT_ENGINES = {
    SupportType.HANGER: calc_hanger,
    SupportType.CANTILEVER_1: calc_cantilever_1,
    SupportType.CANTILEVER_2: calc_cantilever_2,
    SupportType.CANTILEVER_3: calc_cantilever_3,
    SupportType.PEDESTAL: calc_pedestal,
    SupportType.COMBINED: calc_combined,
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

    verify_inp = inp.model_copy(
        update={
            "operation_mode": OperationMode.VERIFY,
            "received_section_family": chosen.section.family,
            "received_section_tag": chosen.section.designation,
        }
    )
    selected_ctx = run_full_calculation(verify_inp)
    if selected_ctx.fan_support_result:
        selected_ctx.fan_support_result.section_options = res.section_options
    selected_ctx.fan_support_input = inp
    # Registar no contexto que o perfil foi escolhido pelo utilizador (M-04):
    # o memorial deixa de sugerir que esta foi a recomendação automática.
    selected_ctx.warnings.append(
        WarningItem(
            code="W-SEC-CHOICE",
            severity="INFO",
            message=(
                f"Perfil {designation} seleccionado manualmente pelo utilizador "
                "entre as opções aprovadas (recomendação automática: "
                f"{current or 'n/d'})."
            ),
            module="selector",
        )
    )
    return selected_ctx


def _uls_action_combos(combinations: list[LoadCombination]) -> list[LoadCombination]:
    uls = [c for c in combinations if c.name.upper().startswith("ULS")]
    return uls or list(combinations)


def run_full_calculation(inp: FanSupportInput) -> ReportContext:
    """
    Fluxo completo:
    1. Validação (política de peso sfsc.policy)
    2. Código estrutural e factor sísmico
    3. Cargas e combinações de ACÇÕES totais
    4. Motor do tipo de suporte → esforços no ELEMENTO para TODAS as combinações
    5. Selecção/verificação da secção contra o envelope ULS (inclui sísmica)
    6. Mesa (se activada) — envelope de acções totais
    7. Ancoragens/varões — por tipo de suporte
    8. Ligações metálicas — esforços do elemento governantes
    9. Checker final + classificação
    10. ReportContext com citações normativas
    """
    citations: list[CitationItem] = []
    warn_items: list[WarningItem] = []
    assumptions: list[str] = []
    recovered_statuses: list[CheckerStatus] = []

    # ── 1. Validação ──────────────────────────────────────────────────────────
    validate_fan_support_input(inp)

    w_msg = weight_warning(inp.total_operating_weight_kg)
    if w_msg:
        band = weight_band(inp.total_operating_weight_kg)
        warn_items.append(
            WarningItem(
                code=f"W-WEIGHT-{band.value}",
                severity="CRITICAL"
                if band in (WeightBand.SPECIALIST, WeightBand.EXTENDED)
                else "WARNING",
                message=w_msg,
                module="policy",
            )
        )

    if inp.exposure_class in (ExposureClass.EXTERIOR, ExposureClass.CORROSIVE):
        warn_items.append(
            WarningItem(
                code="W-EXP-001",
                severity="WARNING",
                message=(
                    f"Classe de exposição '{inp.exposure_class.value}': prever protecção "
                    "anticorrosiva adequada (galvanização/pintura ≥ C4; em ambiente "
                    "corrosivo considerar aço inox A4 nas fixações). A protecção não é "
                    "dimensionada por este modelo."
                ),
                module="selector",
            )
        )

    # ── 2. Código e sismo ─────────────────────────────────────────────────────
    struct_code = resolve_structural_code(inp.country)
    seismic_code = get_seismic_code(inp.country)
    ag_g, zone_used = get_seismic_factor(inp.country, inp.seismic_zone)

    if inp.seismic_zone is None:
        warn_items.append(
            WarningItem(
                code="W-SEISMIC-001",
                severity="WARNING",
                message=(
                    f"Factor sísmico de tabela interna: ag/g = {ag_g} (zona '{zone_used}'). "
                    "Verificar com zonamento sísmico local do projecto."
                ),
                module="selector",
                assumption_id="A-GEN-003",
            )
        )
    elif zone_used != inp.seismic_zone:
        warn_items.append(
            WarningItem(
                code="W-SEISMIC-002",
                severity="WARNING",
                message=(
                    f"Zona sísmica '{inp.seismic_zone}' não encontrada para {inp.country.value} — "
                    f"usada zona default '{zone_used}' (ag/g = {ag_g})."
                ),
                module="selector",
                assumption_id="A-GEN-003",
            )
        )
    assumptions.append("A-GEN-003")

    citations.append(
        CitationItem(
            standard_id=struct_code.value,
            clause="cl. 6.2 + 6.3",
            description="Verificação de secções e elementos estruturais",
        )
    )
    citations.append(
        CitationItem(
            standard_id=seismic_code.value,
            clause="Tabela NA — factores sísmicos por zona",
            description="Factor de aceleração de projecto ag/g",
        )
    )
    citations.append(
        CitationItem(
            standard_id="EN1990",
            clause="cl. 6.4.3.2",
            description="Combinações de acções ULS fundamental e sísmica",
        )
    )
    citations.append(
        CitationItem(
            standard_id="VDI3840",
            clause="Factor dinâmico 1.5",
            description="Factor de amplificação dinâmica para ventiladores industriais",
        )
    )

    # ── 3. Cargas (combinações de ACÇÕES totais) ──────────────────────────────
    total_weight_kN, action_combos = calculate_loads(inp, struct_code, ag_g)
    assumptions.append("A-GEN-001")
    assumptions.append("A-GEN-002")
    assumptions.append("A-STR-002")

    uls_actions = _uls_action_combos(action_combos)
    design_load_kN = max(abs(c.V_z_kN) for c in uls_actions)

    # ── 4. Motor do tipo de suporte (TODAS as combinações → elemento) ─────────
    engine_fn = _SUPPORT_ENGINES[inp.support_type]
    member_combos, Lcr_y_mm, Lcr_z_mm = engine_fn(
        inp,
        total_weight_kN,
        action_combos,
        struct_code,
    )
    assumptions.append("A-STR-001")
    assumptions.append("A-STR-003")

    # ── 5. Secção (envelope ULS — inclui combinação sísmica) ─────────────────
    section = None
    sec_result = None
    section_options = []

    if inp.operation_mode == OperationMode.VERIFY:
        # O model_validator de FanSupportInput garante estes campos em modo VERIFY.
        assert inp.received_section_family is not None
        assert inp.received_section_tag is not None
        try:
            section = get_section(inp.received_section_family, inp.received_section_tag)
        except DatasetMissingError as exc:
            recovered_statuses.append(CheckerStatus.DATASET_MISSING)
            warn_items.append(
                WarningItem(
                    code="W-DATASET-001",
                    severity="CRITICAL",
                    message=(
                        f"Perfil '{inp.received_section_tag}' não encontrado no catálogo "
                        f"({exc.message}). Verificação de secção não realizada."
                    ),
                    module="selector",
                )
            )
        if section is not None:
            sec_result = verify_section_envelope(
                section,
                member_combos,
                struct_code,
                inp.steel_grade,
                Lcr_y_mm,
                Lcr_z_mm,
            )
            section_options = [sec_result]
    else:
        section_options = find_passing_sections(
            member_combos,
            struct_code,
            inp.steel_grade,
            inp.preferred_section_families,
            Lcr_y_mm,
            Lcr_z_mm,
            max_utilization=1.0,
        )
        if section_options:
            conservative = [opt for opt in section_options if opt.utilization_ratio <= 0.90]
            sec_result = (conservative or section_options)[0]
            section = sec_result.section
        else:
            try:
                section, sec_result = auto_select_section(
                    member_combos,
                    struct_code,
                    inp.steel_grade,
                    inp.preferred_section_families,
                    Lcr_y_mm,
                    Lcr_z_mm,
                )
            except OutOfScopeError as exc:
                recovered_statuses.append(CheckerStatus.OUT_OF_SCOPE)
                warn_items.append(
                    WarningItem(
                        code="W-SCOPE-001",
                        severity="CRITICAL",
                        message=(
                            "Nenhum perfil das famílias seleccionadas verifica o envelope "
                            f"de combinações ({exc.message}). Cálculo marcado OUT_OF_SCOPE — "
                            "rever geometria, aço ou famílias de perfis."
                        ),
                        module="selector",
                    )
                )

    if sec_result:
        for w in sec_result.warnings:
            warn_items.append(
                WarningItem(code="W-SEC", severity="WARNING", message=w, module="section_verifier")
            )

    # Combinação governante ao nível do elemento (a que produz o η máximo)
    if sec_result and sec_result.governing_combination:
        governing_member = next(
            (c for c in member_combos if c.name == sec_result.governing_combination),
            member_combos[0],
        )
    else:
        governing_member = max(
            (c for c in member_combos if c.name.upper().startswith("ULS")),
            key=lambda c: abs(c.V_z_kN),
            default=member_combos[0],
        )
    member_combos = [
        c.model_copy(update={"governing": c.name == governing_member.name}) for c in member_combos
    ]
    governing_member = next(c for c in member_combos if c.governing)
    action_combos = [
        c.model_copy(update={"governing": c.name == governing_member.name}) for c in action_combos
    ]

    # ── 6. Mesa — envelope de acções totais (V_z e V_y máximos ULS) ──────────
    bp_result = None
    if inp.include_base_plate and section:
        action_envelope = LoadCombination(
            name="ULS_envelope",
            V_z_kN=max(abs(c.V_z_kN) for c in uls_actions),
            V_y_kN=max(abs(c.V_y_kN) for c in uls_actions),
            description="Envelope das combinações ULS totais (mesa/ancoragens)",
        )
        bp_result = calculate_base_plate(
            inp,
            section,
            action_envelope,
            struct_code,
            inp.concrete_grade,
        )
        assumptions.append("A-BP-001")
        assumptions.append("A-BP-002")
        citations.append(
            CitationItem(
                standard_id="EN1993-1-8",
                clause="cl. 6.2.5",
                description="Dimensionamento da chapa de assento (base plate)",
            )
        )
        for w in bp_result.warnings:
            warn_items.append(
                WarningItem(code="W-BP", severity="INFO", message=w, module="base_plate")
            )

    # ── 7. Ancoragens / varões — por tipo de suporte ──────────────────────────
    anc_result = calculate_anchor(
        inp,
        action_combos,
        struct_code,
        inp.concrete_grade,
        section=section,
    )
    assumptions.append("A-ANC-001")
    if anc_result.anchor_type == "rod":
        citations.append(
            CitationItem(
                standard_id="EN1993-1-8",
                clause="Tab. 3.4",
                description="Varões roscados de suspensão — tracção, corte e interacção",
            )
        )
    else:
        citations.append(
            CitationItem(
                standard_id="EN1992-4",
                clause="cl. 7.2.1 + 7.2.2",
                description="Dimensionamento de ancoragens — tracção, corte e interacção",
            )
        )
    for w in anc_result.warnings:
        warn_items.append(WarningItem(code="W-ANC", severity="WARNING", message=w, module="anchor"))

    # ── 8. Ligações metálicas ─────────────────────────────────────────────────
    metal_conn_result = None
    if section:
        metal_conn_result = calculate_metal_connection(
            inp,
            section,
            governing_member,
            struct_code,
        )
        assumptions.append("A-CONN-001")
        citations.append(
            CitationItem(
                standard_id="EN1993-1-8",
                clause="cl. 3 + 4 + 6",
                description="Ligações metálicas: parafusos, soldaduras, chapas, stiffeners e diagonais",
            )
        )
        for w in metal_conn_result.warnings:
            warn_items.append(
                WarningItem(
                    code="W-CONN", severity="WARNING", message=w, module="metal_connections"
                )
            )

    # ── 9. Checker + classificação ────────────────────────────────────────────
    fan_result = FanSupportResult(
        support_tag=inp.support_tag,
        support_type=inp.support_type,
        structural_code=struct_code,
        seismic_code=seismic_code,
        seismic_factor_g=ag_g,
        total_weight_kN=round(total_weight_kN, 3),
        design_load_kN=round(design_load_kN, 3),
        governing_load_combination=governing_member,
        all_combinations=action_combos,
        member_forces=member_combos,
        recommended_section=section,
        section_verification=sec_result,
        section_options=section_options,
        base_plate=bp_result,
        anchor=anc_result,
        metal_connection=metal_conn_result,
        warnings=[w.message for w in warn_items],
        assumptions_used=list(dict.fromkeys(assumptions)),
    )
    fan_result.status = run_checker(inp, fan_result, extra_statuses=recovered_statuses)
    fan_result.classification_level = classify(inp, fan_result)

    if fan_result.classification_level.value == "REQUIRES_SPECIALIST":
        warn_items.append(
            WarningItem(
                code="W-CLASS-001",
                severity="CRITICAL",
                message=(
                    "Classificação REQUIRES_SPECIALIST: "
                    "este cálculo requer revisão por engenheiro estrutural qualificado."
                ),
                module="checker",
            )
        )

    if inp.anti_vibration.value in ("springs", "silentblocks"):
        assumptions.append("A-VIB-001")
        warn_items.append(
            WarningItem(
                code="W-VIB-001",
                severity="WARNING",
                message="Anti-vibração: dimensionamento dinâmico das molas/silentblocks fora do âmbito (A-VIB-001).",
                module="selector",
            )
        )

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
        citations=list({(c.standard_id, c.clause): c for c in citations}.values()),
        warnings=warn_items,
        assumptions_declared=list(dict.fromkeys(assumptions)),
        dataset_provenance=get_dataset_provenance(),
        limitations=[
            "Análise dinâmica de vibrações fora do âmbito (A-VIB-001).",
            "Verificação de fadiga (EN 1993-1-9) fora do âmbito (A-FAT-001).",
            "Dimensionamento de fundações / maciços de betão fora do âmbito.",
            "Ligações soldadas verificadas por tensão nominal — sem análise de raiz.",
            "Execução assume Classe EXC2 conforme EN 1090.",
            "Acção sísmica por força estática equivalente (sem espectro de resposta) — preliminar.",
            "Campos informativos sem efeito no cálculo: peso vazio, potência, rotação, tipo de fixação do ventilador.",
        ],
    )

    logger.info(
        "Cálculo completo: %s | %s | status=%s | classification=%s",
        inp.support_tag,
        inp.support_type.value,
        fan_result.status.value,
        fan_result.classification_level.value,
    )
    return ctx
