"""Orquestrador principal - run_full_calculation()."""

from __future__ import annotations

import datetime
import logging
import math

from ..catalogs.seismic_catalog import get_seismic_code, get_seismic_factor
from ..catalogs.steel_section_catalog import get_section, list_sections
from ..checks import CheckResult, DiagnosticMessage, aggregate_results, classify_eta
from ..config import get_dataset_provenance
from ..engineering import build_phase01_engineering_model
from ..enums import (
    CalculationMode,
    CheckerStatus,
    CheckStatus,
    Country,
    ExposureClass,
    ModuleId,
    OperationMode,
    StructuralCode,
    SupportFixationMedium,
    SupportType,
)
from ..exceptions import DatasetMissingError, OutOfScopeError
from ..models import (
    CitationItem,
    DiagonalResult,
    FanSupportInput,
    FanSupportResult,
    LoadCombination,
    PlatformResult,
    ReportContext,
    SectionVerificationResult,
    SteelSection,
    WarningItem,
)
from ..policy import WeightBand, weight_band, weight_warning
from ..section_orientation import resolve_section_orientation_deg
from ..units import mm_to_m
from ..validators import validate_fan_support_input
from .anchor import calculate_anchor
from .base_plate import calculate_base_plate
from .checker import classify, run_checker
from .connection_verifier import build_phase05_connection_rows
from .global_frame import (
    GlobalFrameAnalysisResult,
    run_global_frame_analysis,
    run_platform_modal_analysis,
)
from .ifc_import import build_import_review
from .load_surfaces import build_load_path_summary, effective_distribution_method
from .loads import calculate_loads
from .metal_connections import calculate_metal_connection
from .modal_analysis import ModalAnalysisResult
from .quantities import calculate_quantities
from .receiving_member import (
    ReceivingMemberResult,
    resolve_receiving_member_section,
    run_receiving_member_check,
)
from .section_verifier import (
    MAX_UTILIZATION,
    auto_select_section,
    find_passing_sections,
    verify_section,
    verify_section_envelope,
    verify_solver_member_envelope,
)
from .steel_fixation import calculate_steel_fixation
from .support_types.cantilever_1 import calc_cantilever_1
from .support_types.cantilever_2 import calc_cantilever_2
from .support_types.cantilever_3 import calc_cantilever_3
from .support_types.combined import calc_combined
from .support_types.hanger import calc_hanger
from .support_types.pedestal import calc_pedestal
from .support_types.platform_frame_braced import (
    calc_platform_frame_braced,
    compute_platform_breakdown,
)

logger = logging.getLogger("sfsc.selector")

_SERVICEABILITY_COMBINATION = "SLS_characteristic"
_COORD_TOLERANCE_M = 1e-9

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
    SupportType.PLATFORM_FRAME_BRACED: calc_platform_frame_braced,
}


def _numeric(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    raise TypeError(f"Expected numeric solver value, got {type(value).__name__}.")


def _legacy_to_check_status(legacy, eta: float) -> CheckStatus:
    """Mapeia CheckerStatus legado para CheckStatus granular."""
    if legacy == CheckerStatus.FAIL or (eta is not None and eta > 1.0):
        return CheckStatus.FAIL
    if legacy == CheckerStatus.MARGINAL or (eta is not None and eta >= 0.85):
        return CheckStatus.MARGINAL
    return CheckStatus.OK


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


def _platform_support_steel_weight_kg(inp: FanSupportInput, section: SteelSection) -> float:
    n_beams = max(2, inp.platform_n_beams)
    beam_length_m = inp.platform_length_eff_mm / 1_000.0
    steel_kg = section.weight_kgm * n_beams * beam_length_m
    if inp.has_platform_grillage:
        crossbeam_length_m = inp.platform_width_eff_mm / 1_000.0
        steel_kg += section.weight_kgm * inp.platform_n_crossbeams * crossbeam_length_m
    if inp.cantilever_subtype is None or inp.cantilever_subtype.value == "bracketed":
        diagonal_length_m = (
            math.hypot(inp.platform_length_eff_mm, inp.installation_height_mm) / 1_000.0
        )
        steel_kg += section.weight_kgm * n_beams * diagonal_length_m
    return steel_kg


def _serviceability_relevant_span_m(
    inp: FanSupportInput,
    global_frame_result: GlobalFrameAnalysisResult,
    node_id: str,
) -> float:
    if inp.support_type != SupportType.PLATFORM_FRAME_BRACED:
        return mm_to_m(inp.span_mm)

    if not inp.has_platform_grillage:
        return mm_to_m(inp.platform_length_eff_mm)

    node_map = {str(node["id"]): node for node in global_frame_result.nodes}
    node = node_map.get(node_id)
    if node is None:
        return min(mm_to_m(inp.platform_length_eff_mm), mm_to_m(inp.platform_width_eff_mm))

    x_m = _numeric(node["x_m"])
    y_m = _numeric(node.get("y_m", 0.0))
    same_y = [
        _numeric(candidate["x_m"])
        for candidate in global_frame_result.nodes
        if abs(_numeric(candidate.get("y_m", 0.0)) - y_m) <= _COORD_TOLERANCE_M
    ]
    same_x = [
        _numeric(candidate.get("y_m", 0.0))
        for candidate in global_frame_result.nodes
        if abs(_numeric(candidate["x_m"]) - x_m) <= _COORD_TOLERANCE_M
    ]
    spans = [
        max(axis_values) - min(axis_values)
        for axis_values in (same_y, same_x)
        if len(axis_values) >= 2
    ]
    positive_spans = [span for span in spans if span > _COORD_TOLERANCE_M]
    if positive_spans:
        return min(positive_spans)
    return min(mm_to_m(inp.platform_length_eff_mm), mm_to_m(inp.platform_width_eff_mm))


def _serviceability_check_data(
    inp: FanSupportInput,
    global_frame_result: GlobalFrameAnalysisResult | None,
) -> dict[str, object] | None:
    if global_frame_result is None or global_frame_result.failed or not global_frame_result.solved:
        return None

    sls_displacements = [
        row
        for row in global_frame_result.displacements
        if str(row["combination"]) == _SERVICEABILITY_COMBINATION
    ]
    if not sls_displacements:
        return None

    governing_row = max(sls_displacements, key=lambda row: abs(_numeric(row["uz_m"])))
    max_vertical_deflection_m = abs(_numeric(governing_row["uz_m"]))
    governing_node_id = str(governing_row["node_id"])
    relevant_span_m = _serviceability_relevant_span_m(inp, global_frame_result, governing_node_id)
    if relevant_span_m <= 0.0:
        return None

    limit_divisor = inp.calculation_options.serviceability_limit_divisor()
    allowable_deflection_m = relevant_span_m / limit_divisor
    if allowable_deflection_m <= 0.0:
        return None

    node_map = {str(node["id"]): node for node in global_frame_result.nodes}
    governing_node = node_map.get(governing_node_id, {})
    eta_els = max_vertical_deflection_m / allowable_deflection_m

    return {
        "combination_name": _SERVICEABILITY_COMBINATION,
        "governing_node_id": governing_node_id,
        "governing_node_x_m": round(_numeric(governing_node.get("x_m", 0.0)), 6),
        "governing_node_y_m": round(_numeric(governing_node.get("y_m", 0.0)), 6),
        "governing_node_z_m": round(_numeric(governing_node.get("z_m", 0.0)), 6),
        "max_vertical_deflection_m": max_vertical_deflection_m,
        "allowable_deflection_m": allowable_deflection_m,
        "relevant_span_m": relevant_span_m,
        "limit_divisor": limit_divisor,
        "limit_label": inp.calculation_options.serviceability_limit_label(),
        "eta_els": eta_els,
    }


def _resolve_excitation_frequencies(inp: FanSupportInput) -> list[float]:
    """Return excitation frequencies [Hz] for all fan units.

    Priority:
    1. ``calculation_options.excitation_frequency_hz`` (explicit override).
    2. ``fan_unit.speed_rpm`` converted to Hz (rpm / 60).
    Falls back to an empty list (modal analysis will report NOT_VERIFIED).
    """

    explicit = inp.calculation_options.excitation_frequency_hz
    if explicit is not None and explicit > 0.0:
        return [explicit]

    freqs = []
    for unit in inp.fan_units:
        if unit.speed_rpm is not None and unit.speed_rpm > 0.0:
            freqs.append(unit.speed_rpm / 60.0)
    return freqs


def _select_platform_section_from_grillage(
    inp: FanSupportInput,
    combinations: list[LoadCombination],
    struct_code: StructuralCode,
    orientation_deg: float,
    include_ltb: bool,
) -> (
    tuple[
        SteelSection,
        SectionVerificationResult,
        list[SectionVerificationResult],
        GlobalFrameAnalysisResult,
        list[dict[str, object]],
    ]
    | None
):
    """Select the first catalog section that passes using its own grillage forces."""

    passing_options: list[SectionVerificationResult] = []
    for family in inp.preferred_section_families:
        for candidate in list_sections(family):
            analysis = run_global_frame_analysis(
                inp,
                combinations,
                candidate,
                orientation_deg,
            )
            if not analysis.solved or analysis.failed:
                continue
            buckling_overrides_mm = {
                str(member["id"]): (
                    inp.platform_length_eff_mm,
                    inp.platform_length_eff_mm,
                )
                for member in analysis.members
            }
            result, member_rows = verify_solver_member_envelope(
                candidate,
                analysis.nodes,
                analysis.members,
                analysis.member_end_forces,
                struct_code,
                inp.steel_grade,
                orientation_deg,
                buckling_length_overrides_mm=buckling_overrides_mm,
                include_ltb=include_ltb,
            )
            if result.utilization_ratio <= MAX_UTILIZATION:
                passing_options.append(result)
                return candidate, result, passing_options, analysis, member_rows
    return None


def _member_combinations_from_grillage(
    analysis: GlobalFrameAnalysisResult,
    action_combinations: list[LoadCombination],
) -> list[LoadCombination]:
    """Collapse per-member grillage results into a traceable envelope per combination."""

    action_by_name = {combination.name: combination for combination in action_combinations}
    envelopes: list[LoadCombination] = []
    for combination_name in action_by_name:
        rows = [
            row for row in analysis.member_end_forces if str(row["combination"]) == combination_name
        ]
        if not rows:
            continue
        source = action_by_name[combination_name]
        envelopes.append(
            LoadCombination(
                name=combination_name,
                N_kN=0.0,
                V_z_kN=max(
                    max(abs(_numeric(row["V_i_kN"])), abs(_numeric(row["V_j_kN"]))) for row in rows
                ),
                M_y_kNm=max(
                    max(abs(_numeric(row["M_i_kNm"])), abs(_numeric(row["M_j_kNm"])))
                    for row in rows
                ),
                T_kNm=max(
                    max(
                        abs(_numeric(row.get("T_i_kNm", 0.0))),
                        abs(_numeric(row.get("T_j_kNm", 0.0))),
                    )
                    for row in rows
                ),
                member_level=True,
                load_factors_used={
                    **source.load_factors_used,
                    "solver_member_count": float(len(rows)),
                },
                description="Envelope of member forces recovered from the 2.5D grillage solver.",
            )
        )
    return envelopes


def _verify_platform_diagonal(
    inp: FanSupportInput,
    section: SteelSection,
    combinations: list[LoadCombination],
    struct_code: StructuralCode,
    orientation_deg: float,
) -> DiagonalResult | None:
    breakdown = compute_platform_breakdown(inp, combinations)
    if not breakdown.braced or breakdown.diagonal_force_kN <= 0.0:
        return None

    diag_combo = LoadCombination(
        name="platform_diagonal",
        N_kN=breakdown.diagonal_force_kN,
        member_level=True,
        description=f"Compressão na diagonal = {breakdown.diagonal_force_kN:.2f} kN",
    )
    diag_sec = verify_section(
        section,
        diag_combo,
        struct_code,
        inp.steel_grade,
        0.0,
        breakdown.diagonal_length_mm,
        orientation_deg,
        include_ltb=False,
        include_biaxial=False,
    )
    eta_axial = diag_sec.utilization_by_check.get("axial", 0.0)
    eta_buckling = diag_sec.utilization_by_check.get("buckling_z", 0.0)
    eta = max(eta_axial, eta_buckling)
    status = (
        CheckerStatus.FAIL
        if eta > 1.0
        else CheckerStatus.MARGINAL
        if eta > 0.90
        else CheckerStatus.PASS
    )
    return DiagonalResult(
        n_diagonals=breakdown.n_beams,
        angle_deg=breakdown.diagonal_angle_deg,
        length_mm=breakdown.diagonal_length_mm,
        axial_force_kN=round(breakdown.diagonal_force_kN, 3),
        section=section,
        utilization_compression=round(eta_axial, 4),
        utilization_buckling=round(eta_buckling, 4),
        utilization_ratio=round(eta, 4),
        status=status,
        warnings=diag_sec.warnings,
    )


def run_full_calculation(inp: FanSupportInput) -> ReportContext:
    """
    Fluxo completo:
    1. Validação
    2. Código estrutural e factor sísmico
    3. Cargas e combinações de acções totais
    4. Motor do tipo de suporte -> esforços no elemento
    5. Selecção/verificação da secção contra o envelope ULS
    6. Mesa/base plate, ancoragens e ligações
    7. Diagnóstico modular + checker final
    8. ReportContext com citações normativas
    """
    citations: list[CitationItem] = []
    warn_items: list[WarningItem] = []
    assumptions: list[str] = []
    recovered_statuses: list[CheckerStatus] = []

    validate_fan_support_input(inp)
    import_review = (
        build_import_review(
            inp.imported_model,
            confirmed=inp.imported_model_confirmed,
            confirmed_by=inp.prepared_by or None,
            confirmation_notes=inp.imported_model_confirmation_notes,
        )
        if inp.imported_model is not None
        else None
    )

    if import_review is not None:
        for item in import_review.warnings:
            warn_items.append(
                WarningItem(
                    code=item.code,
                    severity=item.severity,
                    message=item.message,
                    module="ifc_import",
                )
            )

    opts = inp.calculation_options
    orientation_deg = resolve_section_orientation_deg(
        inp.section_orientation,
        inp.section_rotation_deg,
    )
    is_benchmark = inp.calculation_mode == CalculationMode.ROBOT_BENCHMARK
    is_steel_fix = inp.support_fixation_medium == SupportFixationMedium.STEEL_STRUCTURE

    eff_base_plate = (opts.include_base_plate or inp.include_base_plate) and not is_benchmark
    eff_anchors = opts.include_anchors and not is_benchmark and not is_steel_fix
    eff_steel_conn = (opts.include_steel_connections and not is_benchmark) or (
        is_steel_fix and not is_benchmark
    )
    eff_seismic = opts.include_seismic_equivalent_static and not is_benchmark
    eff_dynamic = opts.include_dynamic_factor
    eff_ltb = opts.include_lateral_torsional_buckling
    eff_biaxial = opts.include_biaxial_bending and not is_benchmark

    if is_benchmark:
        warn_items.append(
            WarningItem(
                code="W-BENCHMARK",
                severity="WARNING",
                message=(
                    "Modo benchmark de barra (comparável ao Robot): sem base plate, "
                    "ancoragens, ligações nem sísmica. Não é verificação final."
                ),
                module="selector",
            )
        )
    if is_steel_fix and opts.include_anchors and not is_benchmark:
        warn_items.append(
            WarningItem(
                code="W-FIX-STEEL",
                severity="WARNING",
                message=(
                    "Ancoragens em betão desativadas: fixação em estrutura metálica "
                    "(usar ligações aço-aço, EN 1993-1-8)."
                ),
                module="selector",
            )
        )

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
                    "anticorrosiva adequada (galvanização/pintura >= C4; em ambiente "
                    "corrosivo considerar aço inox A4 nas fixações). A protecção não é "
                    "dimensionada por este modelo."
                ),
                module="selector",
            )
        )

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
                    f"Zona sísmica '{inp.seismic_zone}' não encontrada para {inp.country.value} - "
                    f"usada zona default '{zone_used}' (ag/g = {ag_g})."
                ),
                module="selector",
                assumption_id="A-GEN-003",
            )
        )
    assumptions.append("A-GEN-003")
    assumptions.append("A-ORI-001")

    citations.extend(
        [
            CitationItem(
                standard_id=struct_code.value,
                clause="cl. 6.2 + 6.3",
                description="Verificação de secções e elementos estruturais",
            ),
            CitationItem(
                standard_id=seismic_code.value,
                clause="Tabela NA - factores sísmicos por zona",
                description="Factor de aceleração de projecto ag/g",
            ),
            CitationItem(
                standard_id="EN1990",
                clause="cl. 6.4.3.2",
                description="Combinações de acções ULS fundamental e sísmica",
            ),
            CitationItem(
                standard_id="VDI3840",
                clause="Factor dinâmico 1.5",
                description="Factor de amplificação dinâmica para ventiladores industriais",
            ),
        ]
    )

    ag_g_eff = ag_g if eff_seismic else 0.0
    loads_inp = inp if eff_dynamic else inp.model_copy(update={"dynamic_factor": 1.0})
    load_path_summary = build_load_path_summary(loads_inp)
    if load_path_summary.requires_engineer_review:
        warn_items.append(
            WarningItem(
                code="W-SURF-REVIEW",
                severity="WARNING",
                message=(
                    "Load surface or manual load distribution requires engineer review before "
                    "it can be treated as a verified structural input."
                ),
                module="load_surfaces",
            )
        )
    for warning in load_path_summary.warnings:
        warn_items.append(
            WarningItem(
                code="W-SURF",
                severity="INFO",
                message=warning,
                module="load_surfaces",
            )
        )

    def _select_section(
        section_member_combos: list[LoadCombination],
        buckling_y_mm: float,
        buckling_z_mm: float,
    ) -> tuple[
        SteelSection | None,
        SectionVerificationResult | None,
        list[SectionVerificationResult],
        list[CheckerStatus],
        list[WarningItem],
    ]:
        local_recovered: list[CheckerStatus] = []
        local_warnings: list[WarningItem] = []
        section = None
        sec_result = None
        section_options = []

        if inp.operation_mode == OperationMode.VERIFY:
            assert inp.received_section_family is not None
            assert inp.received_section_tag is not None
            try:
                section = get_section(inp.received_section_family, inp.received_section_tag)
            except DatasetMissingError as exc:
                local_recovered.append(CheckerStatus.DATASET_MISSING)
                local_warnings.append(
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
                    section_member_combos,
                    struct_code,
                    inp.steel_grade,
                    buckling_y_mm,
                    buckling_z_mm,
                    orientation_deg,
                    include_ltb=eff_ltb,
                    include_biaxial=eff_biaxial,
                )
                section_options = [sec_result]
        else:
            section_options = find_passing_sections(
                section_member_combos,
                struct_code,
                inp.steel_grade,
                inp.preferred_section_families,
                buckling_y_mm,
                buckling_z_mm,
                max_utilization=1.0,
                orientation_deg=orientation_deg,
                include_ltb=eff_ltb,
                include_biaxial=eff_biaxial,
            )
            if section_options:
                conservative = [opt for opt in section_options if opt.utilization_ratio <= 0.90]
                sec_result = (conservative or section_options)[0]
                section = sec_result.section
            else:
                try:
                    section, sec_result = auto_select_section(
                        section_member_combos,
                        struct_code,
                        inp.steel_grade,
                        inp.preferred_section_families,
                        buckling_y_mm,
                        buckling_z_mm,
                        orientation_deg=orientation_deg,
                        include_ltb=eff_ltb,
                        include_biaxial=eff_biaxial,
                    )
                except OutOfScopeError as exc:
                    local_recovered.append(CheckerStatus.OUT_OF_SCOPE)
                    local_warnings.append(
                        WarningItem(
                            code="W-SCOPE-001",
                            severity="CRITICAL",
                            message=(
                                "Nenhum perfil das famílias seleccionadas verifica o envelope "
                                f"de combinações ({exc.message}). Cálculo marcado OUT_OF_SCOPE - "
                                "rever geometria, aço ou famílias de perfis."
                            ),
                            module="selector",
                        )
                    )

        return section, sec_result, section_options, local_recovered, local_warnings

    total_weight_kN, action_combos = calculate_loads(loads_inp, struct_code, ag_g_eff)
    assumptions.extend(["A-GEN-001", "A-GEN-002", "A-STR-002"])

    uls_actions = _uls_action_combos(action_combos)
    design_load_kN = max(abs(c.V_z_kN) for c in uls_actions)

    engine_fn = _SUPPORT_ENGINES[inp.support_type]
    member_combos, Lcr_y_mm, Lcr_z_mm = engine_fn(
        inp,
        total_weight_kN,
        action_combos,
        struct_code,
    )
    assumptions.extend(["A-STR-001", "A-STR-003"])

    section, sec_result, section_options, section_recovered, section_warn_items = _select_section(
        member_combos,
        Lcr_y_mm,
        Lcr_z_mm,
    )
    recovered_statuses.extend(section_recovered)
    warn_items.extend(section_warn_items)

    if inp.support_type == SupportType.PLATFORM_FRAME_BRACED and section is not None:
        steel_weight_kg = _platform_support_steel_weight_kg(inp, section)
        total_weight_kN, action_combos = calculate_loads(
            loads_inp,
            struct_code,
            ag_g_eff,
            support_steel_weight_kg=steel_weight_kg,
        )
        uls_actions = _uls_action_combos(action_combos)
        design_load_kN = max(abs(c.V_z_kN) for c in uls_actions)
        member_combos, Lcr_y_mm, Lcr_z_mm = engine_fn(
            inp,
            total_weight_kN,
            action_combos,
            struct_code,
        )
        section, sec_result, section_options, section_recovered, section_warn_items = (
            _select_section(
                member_combos,
                Lcr_y_mm,
                Lcr_z_mm,
            )
        )
        recovered_statuses.extend(section_recovered)
        warn_items.extend(section_warn_items)

    platform_result = None
    global_frame_result = None
    member_check_rows: list[dict[str, object]] = []
    connection_check_rows: list[dict[str, object]] = []
    _GLOBAL_FRAME_TYPES = {
        SupportType.CANTILEVER_1,
        SupportType.HANGER,
        SupportType.CANTILEVER_2,
        SupportType.CANTILEVER_3,
        SupportType.PEDESTAL,
        SupportType.COMBINED,
        SupportType.PLATFORM_FRAME_BRACED,
    }
    if section is not None and inp.support_type in _GLOBAL_FRAME_TYPES and not is_benchmark:
        global_frame_result = run_global_frame_analysis(
            inp,
            action_combos,
            section,
            orientation_deg,
        )
        if (
            inp.support_type == SupportType.PLATFORM_FRAME_BRACED
            and inp.has_platform_grillage
            and inp.operation_mode == OperationMode.DIMENSION
        ):
            grillage_selection = None
            previous_signature: tuple[str, str, float] | None = None
            for _ in range(4):
                grillage_selection = _select_platform_section_from_grillage(
                    inp,
                    action_combos,
                    struct_code,
                    orientation_deg,
                    eff_ltb,
                )
                if grillage_selection is None:
                    break
                selected_section = grillage_selection[0]
                selected_steel_weight_kg = _platform_support_steel_weight_kg(
                    inp,
                    selected_section,
                )
                new_total_weight_kN, new_action_combos = calculate_loads(
                    loads_inp,
                    struct_code,
                    ag_g_eff,
                    support_steel_weight_kg=selected_steel_weight_kg,
                )
                new_design_load_kN = max(
                    abs(combination.V_z_kN) for combination in _uls_action_combos(new_action_combos)
                )
                signature = (
                    selected_section.family.value,
                    selected_section.designation,
                    round(new_design_load_kN, 6),
                )
                total_weight_kN = new_total_weight_kN
                action_combos = new_action_combos
                uls_actions = _uls_action_combos(action_combos)
                design_load_kN = new_design_load_kN
                if signature == previous_signature:
                    break
                previous_signature = signature

            if grillage_selection is not None:
                final_selection = _select_platform_section_from_grillage(
                    inp,
                    action_combos,
                    struct_code,
                    orientation_deg,
                    eff_ltb,
                )
                if final_selection is not None:
                    grillage_selection = final_selection
            if grillage_selection is not None:
                (
                    section,
                    sec_result,
                    section_options,
                    global_frame_result,
                    member_check_rows,
                ) = grillage_selection
            else:
                recovered_statuses.append(CheckerStatus.OUT_OF_SCOPE)
                warn_items.append(
                    WarningItem(
                        code="W-GRID-SECTION",
                        severity="CRITICAL",
                        message=(
                            "No catalog section passes the platform grillage force envelope. "
                            "Review geometry, steel grade, or selected section families."
                        ),
                        module="grillage",
                    )
                )
        for warning in global_frame_result.warnings:
            warn_items.append(
                WarningItem(
                    code="W-GFRAME",
                    severity="WARNING" if global_frame_result.failed else "INFO",
                    message=warning,
                    module="global_frame",
                )
            )
        if (
            global_frame_result.supported
            and global_frame_result.solved
            and not global_frame_result.failed
        ):
            try:
                _all_member_ids = {str(m["id"]) for m in global_frame_result.members}
                buckling_overrides_mm = {mid: (Lcr_y_mm, Lcr_z_mm) for mid in _all_member_ids}
                sec_result, member_check_rows = verify_solver_member_envelope(
                    section,
                    global_frame_result.nodes,
                    global_frame_result.members,
                    global_frame_result.member_end_forces,
                    struct_code,
                    inp.steel_grade,
                    orientation_deg,
                    buckling_length_overrides_mm=buckling_overrides_mm,
                    include_ltb=eff_ltb,
                )
                if inp.operation_mode == OperationMode.VERIFY:
                    section_options = [sec_result]
                else:
                    section_options = [
                        sec_result
                        if option.section.designation == section.designation
                        and option.section.family == section.family
                        else option
                        for option in section_options
                    ]
            except ValueError as exc:
                warn_items.append(
                    WarningItem(
                        code="W-MEMBER-CHECKS",
                        severity="WARNING",
                        message=(
                            "Solver member verification could not be completed; "
                            f"falling back to the simplified member envelope ({exc})."
                        ),
                        module="section_verifier",
                    )
                )
            if inp.has_platform_grillage:
                grillage_member_combos = _member_combinations_from_grillage(
                    global_frame_result,
                    action_combos,
                )
                if grillage_member_combos:
                    member_combos = grillage_member_combos
        connection_check_rows = build_phase05_connection_rows(
            inp,
            solver_engine="global_frame",
            solver_failed=global_frame_result.failed,
            solver_reactions=global_frame_result.reactions,
            section=section,
        )
        for row in connection_check_rows:
            status = str(row.get("status", ""))
            missing_value = row.get("missing_inputs", [])
            missing = (
                [str(item) for item in missing_value] if isinstance(missing_value, list) else []
            )
            if status == "not_verified":
                warn_items.append(
                    WarningItem(
                        code="W-CONN-NV",
                        severity="WARNING",
                        message=(
                            "Connection check remains not verified for "
                            f"{row.get('type')} at support {row.get('support_id')} "
                            f"because explicit inputs are missing: {', '.join(missing) or 'n/d'}."
                        ),
                        module="connection_verifier",
                    )
                )
            elif status == "failed":
                warn_items.append(
                    WarningItem(
                        code="W-CONN-FAIL",
                        severity="CRITICAL",
                        message=(
                            "Connection verification failed for "
                            f"{row.get('type')} at support {row.get('support_id')} "
                            f"(η={row.get('utilization_ratio')})."
                        ),
                        module="connection_verifier",
                    )
                )

    if sec_result:
        for w in sec_result.warnings:
            warn_items.append(
                WarningItem(code="W-SEC", severity="WARNING", message=w, module="section_verifier")
            )

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

    if inp.support_type == SupportType.PLATFORM_FRAME_BRACED and section is not None:
        platform_breakdown = compute_platform_breakdown(inp, action_combos)
        platform_load_per_beam_kN = platform_breakdown.load_per_beam_kN
        platform_moment_per_beam_kNm = platform_breakdown.moment_per_beam_kNm
        platform_axial_per_beam_kN = platform_breakdown.axial_per_beam_kN
        if (
            inp.has_platform_grillage
            and global_frame_result is not None
            and global_frame_result.solved
            and not global_frame_result.failed
        ):
            platform_load_per_beam_kN = max(
                max(abs(_numeric(row["V_i_kN"])), abs(_numeric(row["V_j_kN"])))
                for row in global_frame_result.member_end_forces
            )
            platform_moment_per_beam_kNm = max(
                max(abs(_numeric(row["M_i_kNm"])), abs(_numeric(row["M_j_kNm"])))
                for row in global_frame_result.member_end_forces
            )
            platform_axial_per_beam_kN = 0.0
        diagonal_result = _verify_platform_diagonal(
            inp,
            section,
            action_combos,
            struct_code,
            orientation_deg,
        )
        steel_weight_kg = _platform_support_steel_weight_kg(inp, section)
        platform_result = PlatformResult(
            n_beams=platform_breakdown.n_beams,
            n_crossbeams=inp.platform_n_crossbeams,
            analysis_model=(
                "grillage_2_5d" if inp.has_platform_grillage else "legacy_parallel_beams"
            ),
            braced=platform_breakdown.braced,
            width_mm=round(inp.platform_width_eff_mm, 1),
            length_mm=round(inp.platform_length_eff_mm, 1),
            area_m2=round(inp.platform_area_m2, 3),
            surface_weight_kn_m2=inp.walking_surface.self_weight_kn_m2,
            surface_weight_kg=round(inp.platform_surface_weight_kg, 1),
            steel_weight_kg=round(steel_weight_kg, 1),
            load_per_beam_kN=round(platform_load_per_beam_kN, 4),
            moment_per_beam_kNm=round(platform_moment_per_beam_kNm, 4),
            axial_per_beam_kN=round(platform_axial_per_beam_kN, 4),
            load_distribution_method=effective_distribution_method(inp).value,
            load_surface_components=load_path_summary.surface_components,
            distributed_line_loads=load_path_summary.distributed_line_loads,
            manual_loads_applied=load_path_summary.manual_loads_applied,
            diagonal=diagonal_result,
            warnings=load_path_summary.warnings,
        )
        citations.append(
            CitationItem(
                standard_id="EN1991-1-1",
                clause="cl. 6.3 + Anexo A",
                description="Peso próprio da superfície e da estrutura da plataforma",
            )
        )
        if inp.has_platform_grillage:
            citations.append(
                CitationItem(
                    standard_id="EN1993-1-1",
                    clause="cl. 5.2",
                    description=(
                        "Análise elástica global da grelha 2.5D com rigidez "
                        "de flexão e torção das barras."
                    ),
                )
            )
        if diagonal_result:
            for w in diagonal_result.warnings:
                warn_items.append(
                    WarningItem(
                        code="W-DIAG",
                        severity="WARNING",
                        message=w,
                        module="platform_diagonal",
                    )
                )
            if diagonal_result.status == CheckerStatus.FAIL:
                warn_items.append(
                    WarningItem(
                        code="W-DIAG-FAIL",
                        severity="CRITICAL",
                        message=(
                            "A diagonal / mão-francesa não verifica à compressão ou "
                            f"encurvadura (η={diagonal_result.utilization_ratio:.2f})."
                        ),
                        module="platform_diagonal",
                    )
                )

    bp_result = None
    if eff_base_plate and section:
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
        assumptions.extend(["A-BP-001", "A-BP-002"])
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

    anc_result = None
    steel_fix_result = None
    if eff_anchors:
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
                    description="Varões roscados de suspensão - tracção, corte e interacção",
                )
            )
        else:
            citations.append(
                CitationItem(
                    standard_id="EN1992-4",
                    clause="cl. 7.2.1 + 7.2.2",
                    description="Dimensionamento de ancoragens - tracção, corte e interacção",
                )
            )
        for w in anc_result.warnings:
            warn_items.append(
                WarningItem(code="W-ANC", severity="WARNING", message=w, module="anchor")
            )
    recv_result: ReceivingMemberResult | None = None
    if is_steel_fix and not is_benchmark:
        steel_fix_result = calculate_steel_fixation(inp, governing_member, section=section)
        citations.append(
            CitationItem(
                standard_id="EN1993-1-8",
                clause="cl. 3 + 4",
                description="Fixação aço-aço: parafusos, esmagamento, soldaduras e chapa",
            )
        )

        recv_section_id = (
            inp.steel_fixation.receiving_member_section_id if inp.steel_fixation else None
        )
        recv_material_str = (
            inp.steel_fixation.receiving_member_material if inp.steel_fixation else None
        )
        include_recv = opts.include_receiving_member and recv_section_id is not None

        if include_recv and recv_section_id is not None:
            recv_section = resolve_receiving_member_section(recv_section_id)
            if recv_section is not None:
                try:
                    from ..enums import SteelGrade as _SteelGrade

                    recv_grade = (
                        _SteelGrade(recv_material_str) if recv_material_str else inp.steel_grade
                    )
                except ValueError:
                    recv_grade = inp.steel_grade
                recv_result = run_receiving_member_check(
                    section=recv_section,
                    steel_grade=recv_grade,
                    combination=governing_member,
                    support_section_width_mm=float(section.b_mm) if section else None,
                )
                citations.append(
                    CitationItem(
                        standard_id="EN1993-1-1",
                        clause="cl. 6.2.4 + 6.2.5 + 6.2.6 + 6.2.7 + 6.2.8",
                        description="Verificação do perfil receptor: axial, flexão, corte, torção e interacções",
                    )
                )
                if recv_result.eta_overall > 1.0:
                    warn_items.append(
                        WarningItem(
                            code="W-RECV-001",
                            severity="CRITICAL",
                            message=(
                                f"Perfil receptor {recv_section_id} insuficiente: "
                                f"η={recv_result.eta_overall:.3f} ({recv_result.governing_check})."
                            ),
                            module="receiving_member",
                        )
                    )
                # Registo na fixação de que o receptor foi verificado.
                steel_fix_result = steel_fix_result.model_copy(
                    update={"receiving_member_checked": True}
                )
            else:
                warn_items.append(
                    WarningItem(
                        code="W-RECV-SECTION-NF",
                        severity="WARNING",
                        message=(
                            f"Perfil receptor '{recv_section_id}' não encontrado no catálogo. "
                            "Verificar separadamente."
                        ),
                        module="receiving_member",
                    )
                )
                warn_items.append(
                    WarningItem(
                        code="W-STEELFIX-RECEIVER",
                        severity="WARNING",
                        message=(
                            "Elemento receptor (perfil existente) não verificado por este "
                            "modelo - verificar separadamente."
                        ),
                        module="steel_fixation",
                    )
                )
        else:
            warn_items.append(
                WarningItem(
                    code="W-STEELFIX-RECEIVER",
                    severity="WARNING",
                    message=(
                        "Elemento receptor (perfil existente) não verificado por este "
                        "modelo - verificar separadamente."
                    ),
                    module="steel_fixation",
                )
            )

    metal_conn_result = None
    if section and eff_steel_conn:
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

    serviceability_data = _serviceability_check_data(inp, global_frame_result)
    if inp.calculation_options.include_serviceability:
        citations.append(
            CitationItem(
                standard_id="EN1990",
                clause="A1.4",
                description="Verificação de flecha vertical em combinação característica de serviceability.",
            )
        )

    modal_result: ModalAnalysisResult | None = None
    opts = inp.calculation_options
    if opts.include_modal_frequency and inp.has_platform_grillage and section is not None:
        excitation_hz = _resolve_excitation_frequencies(inp)
        modal_result = run_platform_modal_analysis(
            inp,
            section,
            orientation_deg,
            excitation_hz,
        )
        citations.append(
            CitationItem(
                standard_id="VDI 3840",
                clause="Blatt 1",
                description="Verificação de afastamento à ressonância: faixa proibida [0.7, 1.3]×f_exc.",
            )
        )
        if modal_result.resonance_violated:
            warn_items.append(
                WarningItem(
                    code="W-MODAL-001",
                    severity="CRITICAL",
                    message=(
                        f"RESSONÂNCIA: f1={modal_result.first_frequency_hz} Hz está dentro da "
                        f"faixa proibida [0.7, 1.3]×f_excitação. Consultar especialista em vibrações."
                    ),
                    module="modal_analysis",
                )
            )

    breakdown: list[CheckResult] = []

    def _msg(severity: str, key: str) -> DiagnosticMessage:
        return DiagnosticMessage(severity=severity, key=key)

    if sec_result:
        non_ltb = {k: v for k, v in sec_result.utilization_by_check.items() if k != "ltb"}
        eta_section = max(non_ltb.values(), default=0.0)
        breakdown.append(
            CheckResult(
                id=ModuleId.STEEL_SECTION,
                label_key="calculation.modules.steelSection",
                eta=round(eta_section, 4),
                status=classify_eta(eta_section),
                clause_refs=[sec_result.code_clause],
                inputs={"section": section.designation if section else None},
                intermediate_values=dict(sec_result.calculation_details),
            )
        )
        eta_ltb = sec_result.utilization_by_check.get("ltb")
        breakdown.append(
            CheckResult(
                id=ModuleId.LATERAL_TORSIONAL_BUCKLING,
                label_key="calculation.modules.lateralTorsionalBuckling",
                eta=round(eta_ltb, 4) if (eff_ltb and eta_ltb is not None) else None,
                status=classify_eta(eta_ltb)
                if (eff_ltb and eta_ltb is not None)
                else CheckStatus.NOT_CHECKED,
                clause_refs=["EN 1993-1-1 cl. 6.3.2"],
                messages=[] if eff_ltb else [_msg("warning", "warning.module.disabled")],
            )
        )

    if eff_base_plate and bp_result:
        breakdown.append(
            CheckResult(
                id=ModuleId.BASE_PLATE,
                label_key="calculation.modules.basePlate",
                eta=round(bp_result.utilization_ratio, 4),
                status=_legacy_to_check_status(bp_result.status, bp_result.utilization_ratio),
                clause_refs=[bp_result.code_clause],
            )
        )
    else:
        breakdown.append(
            CheckResult(
                id=ModuleId.BASE_PLATE,
                label_key="calculation.modules.basePlate",
                status=CheckStatus.NOT_CHECKED,
                messages=[_msg("warning", "warning.module.disabled")],
            )
        )

    if eff_anchors and anc_result:
        eta_anc = anc_result.utilization_combined
        breakdown.append(
            CheckResult(
                id=ModuleId.CONCRETE_ANCHORS,
                label_key="calculation.modules.anchors",
                eta=round(eta_anc, 4),
                status=_legacy_to_check_status(anc_result.status, eta_anc),
                clause_refs=[anc_result.code_clause],
            )
        )
    else:
        msgs = []
        if is_steel_fix:
            msgs.append(_msg("warning", "warning.anchors.steelMediumDisablesConcrete"))
        else:
            msgs.append(_msg("warning", "warning.module.disabled"))
        breakdown.append(
            CheckResult(
                id=ModuleId.CONCRETE_ANCHORS,
                label_key="calculation.modules.anchors",
                status=CheckStatus.NOT_CHECKED,
                messages=msgs,
            )
        )

    steel_etas = []
    steel_clauses = []
    if metal_conn_result:
        steel_etas.append(metal_conn_result.utilization_ratio)
        steel_clauses.append(metal_conn_result.code_clause)
    if steel_fix_result:
        steel_etas.append(steel_fix_result.utilization_ratio)
        steel_clauses.append(steel_fix_result.code_clause)
    if steel_etas:
        eta_steel = max(steel_etas)
        msgs = []
        if steel_fix_result and not steel_fix_result.receiving_member_checked:
            msgs.append(_msg("warning", "warning.steel.receivingMemberNotChecked"))
        breakdown.append(
            CheckResult(
                id=ModuleId.STEEL_CONNECTIONS,
                label_key="calculation.modules.steelConnections",
                eta=round(eta_steel, 4),
                status=classify_eta(eta_steel),
                clause_refs=steel_clauses,
                messages=msgs,
            )
        )
    else:
        breakdown.append(
            CheckResult(
                id=ModuleId.STEEL_CONNECTIONS,
                label_key="calculation.modules.steelConnections",
                status=CheckStatus.NOT_CHECKED,
                messages=[_msg("warning", "warning.module.disabled")],
            )
        )

    if is_steel_fix and opts.include_receiving_member:
        if recv_result is not None and recv_result.solved:
            breakdown.append(
                CheckResult(
                    id=ModuleId.RECEIVING_MEMBER,
                    label_key="calculation.modules.receivingMember",
                    eta=round(recv_result.eta_overall, 4),
                    status=(classify_eta(recv_result.eta_overall)),
                    clause_refs=["EN 1993-1-1 cl. 6.2.4–6.2.8"],
                    messages=[
                        _msg(
                            "critical" if recv_result.eta_overall > 1.0 else "info",
                            "warning.receivingMember.failed"
                            if recv_result.eta_overall > 1.0
                            else "warning.receivingMember.verified",
                        )
                    ],
                    inputs={
                        "section_id": recv_result.section_id,
                        "material": recv_result.material,
                        "governing_check": recv_result.governing_check,
                    },
                    intermediate_values={
                        k: float(v)
                        for k, v in recv_result.intermediate.items()
                        if isinstance(v, (int, float))
                    },
                )
            )
        else:
            reason_key = (
                "warning.receivingMember.sectionNotFound"
                if recv_result is None
                else "warning.receivingMember.solverFailed"
            )
            breakdown.append(
                CheckResult(
                    id=ModuleId.RECEIVING_MEMBER,
                    label_key="calculation.modules.receivingMember",
                    status=CheckStatus.NOT_CHECKED,
                    messages=[_msg("warning", reason_key)],
                )
            )
    elif is_steel_fix and not opts.include_receiving_member:
        breakdown.append(
            CheckResult(
                id=ModuleId.RECEIVING_MEMBER,
                label_key="calculation.modules.receivingMember",
                status=CheckStatus.NOT_CHECKED,
                messages=[_msg("warning", "warning.receivingMember.disabled")],
            )
        )
    else:
        breakdown.append(
            CheckResult(
                id=ModuleId.RECEIVING_MEMBER,
                label_key="calculation.modules.receivingMember",
                status=CheckStatus.NOT_CHECKED,
                messages=[_msg("warning", "warning.receivingMember.notSteelFixation")],
            )
        )

    breakdown.append(
        CheckResult(
            id=ModuleId.SEISMIC_EQUIVALENT_STATIC,
            label_key="calculation.modules.seismicEquivalentStatic",
            status=CheckStatus.INFORMATIVE if eff_seismic else CheckStatus.NOT_CHECKED,
            clause_refs=[seismic_code.value],
            messages=[] if eff_seismic else [_msg("warning", "warning.module.disabled")],
        )
    )

    breakdown.append(
        CheckResult(
            id=ModuleId.SERVICEABILITY,
            label_key="calculation.modules.serviceability",
            eta=(
                round(_numeric(serviceability_data["eta_els"]), 4)
                if serviceability_data is not None
                else None
            ),
            status=(
                classify_eta(_numeric(serviceability_data["eta_els"]))
                if serviceability_data is not None
                else CheckStatus.NOT_CHECKED
            ),
            clause_refs=["EN 1990 A1.4"] if opts.include_serviceability else [],
            messages=(
                [_msg("warning", "warning.module.disabled")]
                if not opts.include_serviceability
                else [_msg("warning", "warning.serviceability.notVerified")]
                if serviceability_data is None
                else [_msg("critical", "warning.serviceability.exceeded")]
                if classify_eta(_numeric(serviceability_data["eta_els"])) == CheckStatus.FAIL
                else [_msg("warning", "warning.serviceability.atLimit")]
                if classify_eta(_numeric(serviceability_data["eta_els"])) == CheckStatus.MARGINAL
                else [_msg("info", "warning.serviceability.checked")]
            ),
            inputs=(
                {
                    "combination": str(serviceability_data["combination_name"]),
                    "limit_label": str(serviceability_data["limit_label"]),
                    "governing_node_id": str(serviceability_data["governing_node_id"]),
                }
                if serviceability_data is not None
                else {}
            ),
            intermediate_values=(
                {
                    "max_vertical_deflection_m": _numeric(
                        serviceability_data["max_vertical_deflection_m"]
                    ),
                    "allowable_deflection_m": _numeric(
                        serviceability_data["allowable_deflection_m"]
                    ),
                    "relevant_span_m": _numeric(serviceability_data["relevant_span_m"]),
                    "limit_divisor": _numeric(serviceability_data["limit_divisor"]),
                    "eta_els": _numeric(serviceability_data["eta_els"]),
                    "governing_node_x_m": _numeric(serviceability_data["governing_node_x_m"]),
                    "governing_node_y_m": _numeric(serviceability_data["governing_node_y_m"]),
                    "governing_node_z_m": _numeric(serviceability_data["governing_node_z_m"]),
                }
                if serviceability_data is not None
                else {}
            ),
        )
    )

    if inp.walking_surface.surface_type.value != "none" or inp.manual_loads:
        effective_surface_method = effective_distribution_method(inp)
        surface_distribution_verified = (
            inp.has_platform_grillage
            and effective_surface_method.value == "two_way"
            and not load_path_summary.requires_engineer_review
        )
        breakdown.append(
            CheckResult(
                id=ModuleId.LOAD_DISTRIBUTION_SURFACE,
                label_key="calculation.modules.loadDistributionSurface",
                status=(
                    CheckStatus.MARGINAL
                    if load_path_summary.requires_engineer_review
                    else CheckStatus.OK
                    if surface_distribution_verified
                    else CheckStatus.INFORMATIVE
                ),
                inputs={
                    "surface_type": inp.walking_surface.surface_type.value,
                    "distribution_method": effective_surface_method.value,
                    "manual_load_count": float(len(inp.manual_loads)),
                },
                messages=[
                    _msg("info", "warning.surface.notBasePlate"),
                    _msg(
                        "warning" if load_path_summary.requires_engineer_review else "info",
                        "warning.surface.requiresEngineerReview"
                        if load_path_summary.requires_engineer_review
                        else "warning.surface.twoWayDistribution"
                        if surface_distribution_verified
                        else "warning.surface.simplifiedDistribution",
                    ),
                ],
            )
        )

    if opts.include_modal_frequency:
        if modal_result is not None and modal_result.solved:
            modal_eta = (
                max(modal_result.frequency_ratios) / 1.3
                if modal_result.resonance_violated
                else min(abs(r - 1.0) / 0.3 for r in modal_result.frequency_ratios)
                if modal_result.frequency_ratios
                else None
            )
            modal_status = CheckStatus.FAIL if modal_result.resonance_violated else CheckStatus.OK
            breakdown.append(
                CheckResult(
                    id=ModuleId.MODAL_FREQUENCY,
                    label_key="calculation.modules.modalFrequency",
                    eta=round(float(modal_eta), 4) if modal_eta is not None else None,
                    status=modal_status,
                    clause_refs=["VDI 3840 Blatt 1"],
                    messages=[
                        _msg(
                            "critical" if modal_result.resonance_violated else "info",
                            "warning.modal.resonanceViolated"
                            if modal_result.resonance_violated
                            else "warning.modal.verified",
                        ),
                        _msg("info", "warning.modal.limitationStaticFactor"),
                    ],
                    inputs={
                        "first_frequency_hz": float(modal_result.first_frequency_hz or 0.0),
                        "excitation_frequencies_hz": modal_result.excitation_frequencies_hz,
                        "frequency_ratios": modal_result.frequency_ratios,
                        "resonance_band_low": 0.7,
                        "resonance_band_high": 1.3,
                    },
                    intermediate_values=dict(modal_result.intermediate),
                )
            )
        else:
            failure_key = (
                "warning.modal.noExcitationFrequency"
                if modal_result is not None
                and modal_result.failure_reason == "modal_no_excitation_frequency"
                else "warning.modal.solverFailed"
            )
            breakdown.append(
                CheckResult(
                    id=ModuleId.MODAL_FREQUENCY,
                    label_key="calculation.modules.modalFrequency",
                    status=CheckStatus.NOT_CHECKED,
                    clause_refs=["VDI 3840 Blatt 1"],
                    messages=[_msg("warning", failure_key)],
                )
            )
    else:
        breakdown.append(
            CheckResult(
                id=ModuleId.MODAL_FREQUENCY,
                label_key="calculation.modules.modalFrequency",
                status=CheckStatus.NOT_CHECKED,
                messages=[_msg("warning", "warning.modal.disabled")],
            )
        )

    aggregate = aggregate_results(breakdown)

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
        solver_engine=(
            "global_frame"
            if global_frame_result is not None and global_frame_result.supported
            else "simplified"
        ),
        solver_failed=global_frame_result.failed if global_frame_result is not None else False,
        solver_nodes=global_frame_result.nodes if global_frame_result is not None else [],
        solver_members=global_frame_result.members if global_frame_result is not None else [],
        solver_supports=global_frame_result.supports if global_frame_result is not None else [],
        solver_releases=global_frame_result.releases if global_frame_result is not None else [],
        solver_reactions=global_frame_result.reactions if global_frame_result is not None else [],
        solver_displacements=(
            global_frame_result.displacements if global_frame_result is not None else []
        ),
        solver_member_end_forces=(
            global_frame_result.member_end_forces if global_frame_result is not None else []
        ),
        solver_warnings=global_frame_result.warnings if global_frame_result is not None else [],
        member_check_rows=member_check_rows,
        connection_check_rows=connection_check_rows,
        recommended_section=section,
        section_verification=sec_result,
        section_options=section_options,
        base_plate=bp_result,
        anchor=anc_result,
        steel_fixation=steel_fix_result,
        metal_connection=metal_conn_result,
        platform=platform_result,
        warnings=[w.message for w in warn_items],
        assumptions_used=list(dict.fromkeys(assumptions)),
        module_breakdown=aggregate.checks,
        global_status=aggregate.global_status,
        governing_module=aggregate.governing_module,
        governing_eta=aggregate.governing_eta,
    )
    fan_result.status = run_checker(inp, fan_result, extra_statuses=recovered_statuses)
    fan_result.classification_level = classify(inp, fan_result)
    fan_result.quantities = calculate_quantities(inp, fan_result)
    engineering_model, engineering_report_state = build_phase01_engineering_model(
        inp,
        fan_result,
        import_review=import_review,
    )

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
                message=(
                    "Anti-vibração: dimensionamento dinâmico das molas/silentblocks "
                    "fora do âmbito (A-VIB-001)."
                ),
                module="selector",
            )
        )

    assumptions.append("A-FAT-001")
    fan_result.warnings = [w.message for w in warn_items]
    fan_result.assumptions_used = list(dict.fromkeys(assumptions))

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
        dataset_provenance={
            **get_dataset_provenance(),
            "options_fingerprint": inp.calculation_options.fingerprint(),
            "calculation_mode": inp.calculation_mode.value,
            "calculation_model_type": engineering_model.structure.calculation_model.value,
            "solver_module": (
                "grillage_2_5d"
                if inp.has_platform_grillage
                and global_frame_result is not None
                and global_frame_result.solved
                else fan_result.solver_engine
            ),
            "platform_grid": {
                "longitudinal_beams": inp.platform_n_beams,
                "crossbeams": inp.platform_n_crossbeams,
            },
            "import_source_type": (
                import_review.source.source_type if import_review is not None else None
            ),
            "import_file_name": (
                import_review.source.file_name if import_review is not None else None
            ),
            "import_confirmed": import_review.confirmed if import_review is not None else False,
        },
        limitations=[
            "Análise dinâmica de vibrações fora do âmbito (A-VIB-001).",
            "Verificação de fadiga (EN 1993-1-9) fora do âmbito (A-FAT-001).",
            (
                "A plataforma foi analisada como grelha elástica linear 2.5D; "
                "efeitos não lineares e ligações semirrígidas não foram modelados."
                if inp.has_platform_grillage
                else "O modelo estrutural depende da idealização global indicada no memorial."
            ),
            (
                "A verificação de serviceability usa a flecha vertical máxima da combinação SLS característica e o limite configurado pelo utilizador."
                if serviceability_data is not None
                else "Os resultados de serviceability permanecem não verificados quando não existirem deslocamentos do solver para a combinação SLS."
            ),
            "As verificações de ligação só podem ser tratadas como verificadas quando existirem reações do solver e inputs explícitos de ligação; caso contrário permanecem não verificadas.",
            "Dimensionamento de fundações / maciços de betão fora do âmbito.",
            "Ligações soldadas verificadas por tensão nominal - sem análise de raiz.",
            "Execução assume Classe EXC2 conforme EN 1090.",
            "Acção sísmica por força estática equivalente (sem espectro de resposta) - preliminar.",
            "Campos informativos sem efeito no cálculo: peso vazio, potência, rotação, tipo de fixação do ventilador.",
            "Geometria BIM/IFC importada permanece assistida e revista pelo utilizador; não substitui automaticamente o modelo activo de cálculo.",
        ],
        engineering_model=engineering_model,
        engineering_report_state=engineering_report_state,
        import_review=import_review,
    )

    logger.info(
        "Cálculo completo: %s | %s | status=%s | classification=%s",
        inp.support_tag,
        inp.support_type.value,
        fan_result.status.value,
        fan_result.classification_level.value,
    )
    return ctx
