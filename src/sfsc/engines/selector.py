"""Orquestrador principal — run_full_calculation()."""
from __future__ import annotations
import datetime
import logging
from ..models import (
    FanSupportInput, FanSupportResult, ReportContext,
    CitationItem, WarningItem, SteelSection,
    PlatformResult, DiagonalResult,
)
from ..enums import (
    SupportType, StructuralCode, Country, OperationMode, AnchorageSubstrate,
    CheckerStatus,
)
from ..validators import validate_fan_support_input
from ..catalogs.seismic_catalog import get_seismic_factor, get_seismic_code
from ..catalogs.steel_section_catalog import get_section, is_overdimensioned_choice
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
from .support_types.platform import calc_platform, compute_platform_breakdown
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
    SupportType.PLATFORM:     calc_platform,
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
        passing_sections = [opt.section for opt in res.section_options]
        if is_overdimensioned_choice(chosen.section, passing_sections):
            message = (
                "Perfil aprovado, porem possivelmente sobredimensionado para esta carga. "
                "Existe perfil mais leve aprovado na lista de candidatos."
            )
            selected_ctx.warnings.append(WarningItem(
                code="W-SEC-HEAVY",
                severity="WARNING",
                message=message,
                module="section_selector",
            ))
            selected_ctx.fan_support_result.warnings.append(message)
    selected_ctx.fan_support_input = inp
    return selected_ctx


def _platform_steel_weight_kg(inp: FanSupportInput, section: SteelSection) -> float:
    """Peso real do aço da grelha: N vigas no vão + (se escorada) N diagonais."""
    from ..units import mm_to_m
    n = max(2, inp.platform_n_beams)
    L_m = mm_to_m(inp.platform_length_eff_mm)
    beams_kg = section.weight_kgm * n * L_m
    diag_kg = 0.0
    if inp.cantilever_subtype is not None and inp.cantilever_subtype.value == "bracketed":
        import math
        diag_len_m = mm_to_m(math.hypot(inp.span_mm, inp.installation_height_mm))
        # Diagonais com a mesma secção (conservativo); uma por viga.
        diag_kg = section.weight_kgm * n * diag_len_m
    return beams_kg + diag_kg


def _verify_diagonal(
    inp: FanSupportInput,
    section: SteelSection,
    combinations: list,
    struct_code: StructuralCode,
) -> DiagonalResult | None:
    """Verifica a mão-francesa à compressão + encurvadura (mesma secção da viga)."""
    bd = compute_platform_breakdown(inp, combinations)
    if not bd.braced or bd.diagonal_force_kN <= 0.0:
        return None

    from .section_verifier import verify_section
    from ..models import LoadCombination

    # Diagonal: barra comprimida, sem flexão. Lcr = comprimento da diagonal.
    diag_combo = LoadCombination(
        name="diagonal",
        N_kN=bd.diagonal_force_kN,
        description=f"Compressão na mão-francesa = {bd.diagonal_force_kN:.2f} kN",
    )
    sv = verify_section(
        section, diag_combo, struct_code, inp.steel_grade,
        buckling_length_y_mm=0.0,
        buckling_length_z_mm=bd.diagonal_length_mm,
    )
    eta_axial = sv.utilization_by_check.get("axial", 0.0)
    eta_buck = sv.utilization_by_check.get("buckling_z", 0.0)
    eta = max(eta_axial, eta_buck)
    status = (
        CheckerStatus.FAIL if eta > 1.0
        else CheckerStatus.MARGINAL if eta > 0.90
        else CheckerStatus.PASS
    )
    return DiagonalResult(
        n_diagonals=bd.n_beams,
        angle_deg=bd.diagonal_angle_deg,
        length_mm=bd.diagonal_length_mm,
        axial_force_kN=round(bd.diagonal_force_kN, 3),
        section=section,
        utilization_compression=round(eta_axial, 4),
        utilization_buckling=round(eta_buck, 4),
        utilization_ratio=round(eta, 4),
        status=status,
        warnings=sv.warnings,
    )


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

    engine_fn = _SUPPORT_ENGINES[inp.support_type]

    def _loads_engine_section(steel_self_weight_kg: float | None):
        """Corre cargas → motor → selecção de secção. Reutilizável para a 2ª
        passagem de convergência do peso próprio da plataforma."""
        total_weight_kN, combinations = calculate_loads(
            inp, struct_code, ag_g, steel_self_weight_kg=steel_self_weight_kg,
        )
        governing_combo, Lcr_y_mm, Lcr_z_mm = engine_fn(
            inp, total_weight_kN, combinations, struct_code,
        )
        all_combos = [
            governing_combo if c.name == governing_combo.name else c
            for c in combinations
        ]

        section = None
        sec_result = None
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
        return (total_weight_kN, all_combos, governing_combo,
                Lcr_y_mm, Lcr_z_mm, section, sec_result, section_options)

    # ── 3-5. Cargas + motor + secção ──────────────────────────────────────────
    (total_weight_kN, all_combos, governing_combo,
     Lcr_y_mm, Lcr_z_mm, section, sec_result, section_options) = _loads_engine_section(None)

    # PLATFORM: 2ª passagem com o peso real do aço da secção escolhida
    # (substitui a estimativa pré-selecção e re-equilibra a carga própria).
    if inp.support_type == SupportType.PLATFORM and section is not None:
        steel_kg = _platform_steel_weight_kg(inp, section)
        (total_weight_kN, all_combos, governing_combo,
         Lcr_y_mm, Lcr_z_mm, section, sec_result, section_options) = \
            _loads_engine_section(steel_kg)

    assumptions.append("A-GEN-001")
    assumptions.append("A-GEN-002")
    assumptions.append("A-STR-001")
    assumptions.append("A-STR-002")
    assumptions.append("A-STR-003")

    if sec_result:
        for w in sec_result.warnings:
            warn_items.append(WarningItem(code="W-SEC", severity="WARNING",
                                          message=w, module="section_verifier"))
        if section and section.catalog_status in ("heavy", "hidden"):
            warn_items.append(WarningItem(
                code="W-SEC-HEAVY",
                severity="WARNING",
                message=(
                    "Perfil aprovado, porem possivelmente sobredimensionado para esta carga. "
                    "Validar se a escolha e intencional."
                ),
                module="section_selector",
            ))

    # ── 5b. Plataforma: síntese da grelha + verificação das diagonais ─────────
    platform_result = None
    if inp.support_type == SupportType.PLATFORM and section is not None:
        bd = compute_platform_breakdown(inp, all_combos)
        diag_result = _verify_diagonal(inp, section, all_combos, struct_code)
        steel_kg = _platform_steel_weight_kg(inp, section)
        platform_result = PlatformResult(
            n_beams=bd.n_beams,
            braced=bd.braced,
            width_mm=round(inp.platform_width_eff_mm, 1),
            length_mm=round(inp.platform_length_eff_mm, 1),
            area_m2=round(inp.platform_area_m2, 3),
            grating_kg_m2=inp.platform_grating_kg_m2,
            grating_weight_kg=round(inp.grating_weight_kg, 1),
            steel_weight_kg=round(steel_kg, 1),
            load_per_beam_kN=bd.load_per_beam_kN,
            moment_per_beam_kNm=bd.moment_per_beam_kNm,
            axial_per_beam_kN=bd.axial_per_beam_kN,
            diagonal=diag_result,
        )
        citations.append(CitationItem(
            standard_id="EN1991-1-1",
            clause="cl. 6.3 + Anexo A",
            description="Cargas permanentes — peso próprio do piso (tramex) e da estrutura",
        ))
        if diag_result is not None:
            for w in diag_result.warnings:
                warn_items.append(WarningItem(code="W-DIAG", severity="WARNING",
                                              message=w, module="platform_diagonal"))
            if diag_result.status == CheckerStatus.FAIL:
                warn_items.append(WarningItem(
                    code="W-DIAG-FAIL", severity="CRITICAL",
                    message=(
                        f"Mão-francesa não verifica à compressão/encurvadura "
                        f"(η={diag_result.utilization_ratio:.2f}). Rever secção da diagonal."
                    ),
                    module="platform_diagonal",
                ))

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
    if inp.anchorage_substrate == AnchorageSubstrate.STEEL_STRUCTURE:
        citations.append(CitationItem(
            standard_id="EN1993-1-8",
            clause="cl. 3.6 + 3.7",
            description="Ligação aparafusada a estrutura metálica",
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
        platform=platform_result,
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
