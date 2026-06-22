"""Engineering data model and result-state helpers for Phases 01-02."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .catalogs.steel_grade_catalog import get_grade_spec
from .checks import CheckResult
from .engines.load_surfaces import build_load_path_summary
from .enums import (
    CheckStatus,
    LoadCaseName,
    ModuleId,
    SupportFixationMedium,
    SupportType,
    WalkingSurfaceType,
)
from .models import (
    FanSupportInput,
    FanSupportResult,
    ImportedModelReview,
    LoadCombination,
    SteelSection,
)
from .section_orientation import (
    LocalSectionAxisProperties,
    get_local_section_axis_properties,
    resolve_section_orientation_deg,
)
from .units import mm_to_m


class CalculationModelType(str, Enum):
    SIMPLIFIED = "simplified"
    GLOBAL_FRAME = "global_frame"


class CalculationResultState(str, Enum):
    VERIFIED = "verified"
    SIMPLIFIED = "simplified"
    NOT_VERIFIED = "not_verified"
    NOT_APPLICABLE = "not_applicable"
    REQUIRES_ENGINEER_REVIEW = "requires_engineer_review"
    FAILED = "failed"


class ExplicitUnits(BaseModel):
    length: str = "m"
    force: str = "kN"
    moment: str = "kNm"
    stress: str = "MPa"
    mass: str = "kg"
    area: str = "m2"
    section_area: str = "cm2"
    inertia: str = "cm4"
    section_modulus: str = "cm3"
    line_load: str = "kN/m"
    area_load: str = "kN/m2"
    angle: str = "deg"


class EngineeringProject(BaseModel):
    id: str
    name: str
    description: str = ""
    engineer: str = ""


class EngineeringStructure(BaseModel):
    id: str
    type: str = "small_steel_support_frame"
    support_type: str
    calculation_model: CalculationModelType
    design_code: str = "eurocode"
    status: str = "draft"


class EngineeringMaterial(BaseModel):
    id: str
    name: str
    elastic_modulus_MPa: float
    yield_strength_MPa: float
    density_kg_m3: float = 7850.0
    poisson_ratio: float = 0.3


class EngineeringSection(BaseModel):
    id: str
    name: str
    family: str
    area_cm2: float
    iy_cm4: float
    iz_cm4: float
    wy_cm3: float
    wz_cm3: float
    orientation_deg: float
    source: str = "database"


class EngineeringNode(BaseModel):
    id: str
    x_m: float
    y_m: float
    z_m: float


class EngineeringRelease(BaseModel):
    id: str
    member_id: str
    node_end: str
    releases: dict[str, bool] = Field(default_factory=dict)


class EngineeringMember(BaseModel):
    id: str
    start_node_id: str
    end_node_id: str
    section_id: str
    material_id: str
    orientation_deg: float
    member_type: str
    calculation_role: str = "primary"


class EngineeringSupport(BaseModel):
    id: str
    node_id: str
    restraints: dict[str, bool]


class EngineeringLoadCase(BaseModel):
    id: str
    name: str
    type: str
    origin: str


class EngineeringLoadCombinationFactor(BaseModel):
    load_case_id: str
    factor: float


class EngineeringLoadCombination(BaseModel):
    id: str
    name: str
    type: str
    factors: list[EngineeringLoadCombinationFactor] = Field(default_factory=list)
    description: str = ""


class EngineeringLoadSurface(BaseModel):
    id: str
    name: str
    type: str
    load_case_id: str
    area_m2: float
    load_kN_m2: float
    distribution_method: str
    target_member_ids: list[str] = Field(default_factory=list)
    resulting_line_loads: list[dict[str, float | str]] = Field(default_factory=list)


class EngineeringManualLoad(BaseModel):
    id: str
    type: str
    load_case_id: str
    target_id: str
    direction: str
    value: float
    unit: str
    origin: str = "manual"


class EngineeringAnalysisSettings(BaseModel):
    include_self_weight: bool = True
    solver_type: str = "simplified"
    serviceability_limit: str | None = None
    serviceability_custom_limit: str | None = None


class EngineeringSolverResults(BaseModel):
    status: CalculationResultState
    reactions: list[dict[str, object]] = Field(default_factory=list)
    displacements: list[dict[str, object]] = Field(default_factory=list)
    member_forces: list[dict[str, object]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EngineeringMemberCheck(BaseModel):
    member_id: str
    status: CalculationResultState
    governing_check: str
    utilization: float | None = None
    load_combination_id: str | None = None
    warnings: list[str] = Field(default_factory=list)


class EngineeringConnectionCheck(BaseModel):
    support_id: str
    type: str
    status: CalculationResultState
    utilization: float | None = None
    load_combination_id: str | None = None
    reaction_fx_kN: float | None = None
    reaction_fz_kN: float | None = None
    reaction_my_kNm: float | None = None
    missing_inputs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EngineeringStateItem(BaseModel):
    id: str
    label_key: str
    state: CalculationResultState
    notes: list[str] = Field(default_factory=list)


class EngineeringReportState(BaseModel):
    pdf_ready: bool = False
    engineering_review_required: bool = True
    contains_simplified_results: bool = False
    contains_unverified_checks: bool = False
    warnings: list[str] = Field(default_factory=list)
    states: list[EngineeringStateItem] = Field(default_factory=list)

    def state_for(self, item_id: str) -> EngineeringStateItem:
        return next(item for item in self.states if item.id == item_id)


class EngineeringModel(BaseModel):
    schema_version: str = "0.3.0"
    project: EngineeringProject
    structure: EngineeringStructure
    units: ExplicitUnits = Field(default_factory=ExplicitUnits)
    materials: list[EngineeringMaterial] = Field(default_factory=list)
    sections: list[EngineeringSection] = Field(default_factory=list)
    nodes: list[EngineeringNode] = Field(default_factory=list)
    members: list[EngineeringMember] = Field(default_factory=list)
    supports: list[EngineeringSupport] = Field(default_factory=list)
    releases: list[EngineeringRelease] = Field(default_factory=list)
    load_cases: list[EngineeringLoadCase] = Field(default_factory=list)
    load_combinations: list[EngineeringLoadCombination] = Field(default_factory=list)
    load_surfaces: list[EngineeringLoadSurface] = Field(default_factory=list)
    manual_loads: list[EngineeringManualLoad] = Field(default_factory=list)
    analysis_settings: EngineeringAnalysisSettings = Field(
        default_factory=EngineeringAnalysisSettings
    )
    solver_results: EngineeringSolverResults
    member_checks: list[EngineeringMemberCheck] = Field(default_factory=list)
    connection_checks: list[EngineeringConnectionCheck] = Field(default_factory=list)
    import_review: ImportedModelReview | None = None
    report_state: EngineeringReportState


def determine_serviceability_state(
    *,
    include_serviceability: bool,
    displacement_results_available: bool,
    serviceability_check_status: CheckStatus | None = None,
) -> CalculationResultState:
    if not include_serviceability:
        return CalculationResultState.NOT_APPLICABLE
    if not displacement_results_available:
        return CalculationResultState.NOT_VERIFIED
    if serviceability_check_status == CheckStatus.FAIL:
        return CalculationResultState.FAILED
    if serviceability_check_status == CheckStatus.MARGINAL:
        return CalculationResultState.REQUIRES_ENGINEER_REVIEW
    if serviceability_check_status == CheckStatus.NOT_CHECKED:
        return CalculationResultState.NOT_VERIFIED
    return CalculationResultState.VERIFIED


def determine_connection_state(
    *,
    checks_requested: bool,
    rows: list[dict[str, object]],
) -> CalculationResultState:
    if not checks_requested:
        return CalculationResultState.NOT_APPLICABLE
    if not rows:
        return CalculationResultState.NOT_VERIFIED
    statuses = {str(row.get("status", "")) for row in rows}
    if "failed" in statuses:
        return CalculationResultState.FAILED
    if "not_verified" in statuses:
        return CalculationResultState.NOT_VERIFIED
    if "requires_engineer_review" in statuses:
        return CalculationResultState.REQUIRES_ENGINEER_REVIEW
    return CalculationResultState.VERIFIED


def determine_member_check_state(
    *,
    has_checks: bool,
    calculation_model: CalculationModelType,
    uses_solver_results: bool,
    has_failed_checks: bool,
) -> CalculationResultState:
    if not has_checks:
        return CalculationResultState.NOT_VERIFIED
    if has_failed_checks:
        return CalculationResultState.FAILED
    if uses_solver_results:
        return CalculationResultState.VERIFIED
    if calculation_model == CalculationModelType.SIMPLIFIED:
        return CalculationResultState.SIMPLIFIED
    return CalculationResultState.NOT_VERIFIED


def determine_solver_state(
    *,
    calculation_model: CalculationModelType,
    has_nodes: bool,
    has_members: bool,
    has_supports: bool,
    displacement_results_available: bool,
    reaction_results_available: bool,
    failed: bool,
) -> CalculationResultState:
    if calculation_model == CalculationModelType.SIMPLIFIED:
        return CalculationResultState.SIMPLIFIED
    if failed:
        return CalculationResultState.FAILED
    if not (has_nodes and has_members and has_supports):
        return CalculationResultState.NOT_VERIFIED
    if not (displacement_results_available and reaction_results_available):
        return CalculationResultState.NOT_VERIFIED
    return CalculationResultState.VERIFIED


def determine_load_surface_state(
    *,
    has_load_surface: bool,
    has_manual_loads: bool,
    load_distribution_available: bool,
    requires_engineer_review: bool,
) -> CalculationResultState:
    if not has_load_surface and not has_manual_loads:
        return CalculationResultState.NOT_APPLICABLE
    if requires_engineer_review:
        return CalculationResultState.REQUIRES_ENGINEER_REVIEW
    if load_distribution_available:
        return CalculationResultState.VERIFIED
    return CalculationResultState.SIMPLIFIED


def determine_import_review_state(
    import_review: ImportedModelReview | None,
) -> CalculationResultState:
    if import_review is None:
        return CalculationResultState.NOT_APPLICABLE
    if not import_review.confirmed:
        return CalculationResultState.NOT_VERIFIED
    if import_review.requires_engineer_review:
        return CalculationResultState.REQUIRES_ENGINEER_REVIEW
    return CalculationResultState.VERIFIED


def _calculation_model_for_result(result: FanSupportResult) -> CalculationModelType:
    if result.solver_engine == "global_frame" and not result.solver_failed:
        return CalculationModelType.GLOBAL_FRAME
    return CalculationModelType.SIMPLIFIED


def _surface_type_name(surface_type: WalkingSurfaceType) -> str:
    if surface_type == WalkingSurfaceType.STEEL_GRATING_TRAMEX:
        return "tramex"
    if surface_type == WalkingSurfaceType.CHECKER_PLATE:
        return "checker_plate"
    if surface_type == WalkingSurfaceType.SOLID_PLATE:
        return "solid_plate"
    if surface_type == WalkingSurfaceType.OTHER:
        return "custom"
    return "none"


def _load_case_id(case_name: str) -> str:
    return {
        LoadCaseName.G.value: "case_g",
        LoadCaseName.Q.value: "case_q",
        LoadCaseName.EQ.value: "case_eq",
        LoadCaseName.MANUAL.value: "case_manual",
        "E_SEISMIC": "case_seismic",
    }.get(case_name, f"case_{case_name.lower()}")


def _as_float(value: object) -> float:
    assert isinstance(value, int | float)
    return float(value)


def _serviceability_module_check(result: FanSupportResult) -> CheckResult | None:
    return next(
        (check for check in result.module_breakdown if check.id == ModuleId.SERVICEABILITY),
        None,
    )


def _build_material(inp: FanSupportInput) -> EngineeringMaterial:
    grade = get_grade_spec(inp.steel_grade)
    return EngineeringMaterial(
        id=f"material-{inp.steel_grade.value.lower()}",
        name=inp.steel_grade.value,
        elastic_modulus_MPa=grade.E_mpa,
        yield_strength_MPa=grade.fy_mpa,
        density_kg_m3=7850.0,
        poisson_ratio=0.3,
    )


def _build_section(
    section: SteelSection | None,
    oriented_props: LocalSectionAxisProperties | None,
) -> list[EngineeringSection]:
    if section is None or oriented_props is None:
        return []
    return [
        EngineeringSection(
            id=f"section-{section.family.value.lower()}-{section.designation.lower()}",
            name=section.designation,
            family=section.family.value.lower(),
            area_cm2=section.A_cm2,
            iy_cm4=round(oriented_props.local_iy_mm4 / 1e4, 6),
            iz_cm4=round(oriented_props.local_iz_mm4 / 1e4, 6),
            wy_cm3=round(oriented_props.local_wy_el_mm3 / 1e3, 6),
            wz_cm3=round(oriented_props.local_wz_el_mm3 / 1e3, 6),
            orientation_deg=oriented_props.orientation_deg,
        )
    ]


def _build_frame_entities(
    inp: FanSupportInput,
    result: FanSupportResult,
    section_id: str | None,
    material_id: str,
    orientation_deg: float,
) -> tuple[
    list[EngineeringNode],
    list[EngineeringMember],
    list[EngineeringSupport],
    list[EngineeringRelease],
]:
    if section_id is None:
        return [], [], [], []
    if result.solver_engine == "global_frame" and result.solver_nodes and result.solver_members:
        solver_nodes = [
            EngineeringNode(
                id=str(node["id"]),
                x_m=_as_float(node["x_m"]),
                y_m=_as_float(node.get("y_m", 0.0)),
                z_m=_as_float(node["z_m"]),
            )
            for node in result.solver_nodes
        ]
        solver_members = [
            EngineeringMember(
                id=str(member["id"]),
                start_node_id=str(member["node_i"]),
                end_node_id=str(member["node_j"]),
                section_id=section_id,
                material_id=material_id,
                orientation_deg=orientation_deg,
                member_type=str(member["kind"]),
                calculation_role="global_frame_member",
            )
            for member in result.solver_members
        ]
        solver_supports = [
            EngineeringSupport(
                id=f"support-{support['node_id']}",
                node_id=str(support["node_id"]),
                restraints={
                    "ux": bool(support["ux"]),
                    "uy": False,
                    "uz": bool(support["uz"]),
                    "rx": False,
                    "ry": bool(support["ry"]),
                    "rz": False,
                },
            )
            for support in result.solver_supports
        ]
        solver_releases = [
            EngineeringRelease(
                id=f"release-{release['member_id']}-{release['node_end']}",
                member_id=str(release["member_id"]),
                node_end=str(release["node_end"]),
                releases={
                    str(key): bool(value) for key, value in dict(release["releases"]).items()
                },
            )
            for release in result.solver_releases
        ]
        return solver_nodes, solver_members, solver_supports, solver_releases

    if inp.support_type == SupportType.PLATFORM_FRAME_BRACED:
        width_m = mm_to_m(inp.platform_width_eff_mm)
        length_m = mm_to_m(inp.platform_length_eff_mm)
        z_m = mm_to_m(inp.installation_height_mm)
        n_beams = max(2, inp.platform_n_beams)
        nodes: list[EngineeringNode] = []
        members: list[EngineeringMember] = []
        supports: list[EngineeringSupport] = []
        releases: list[EngineeringRelease] = []

        for index in range(n_beams):
            y_m = 0.0 if n_beams == 1 else width_m * index / max(1, n_beams - 1)
            start_id = f"node-beam-{index + 1}-start"
            end_id = f"node-beam-{index + 1}-end"
            member_id = f"member-beam-{index + 1}"
            nodes.extend(
                [
                    EngineeringNode(id=start_id, x_m=0.0, y_m=round(y_m, 6), z_m=round(z_m, 6)),
                    EngineeringNode(
                        id=end_id,
                        x_m=round(length_m, 6),
                        y_m=round(y_m, 6),
                        z_m=round(z_m, 6),
                    ),
                ]
            )
            members.append(
                EngineeringMember(
                    id=member_id,
                    start_node_id=start_id,
                    end_node_id=end_id,
                    section_id=section_id,
                    material_id=material_id,
                    orientation_deg=orientation_deg,
                    member_type="beam",
                    calculation_role="platform_beam",
                )
            )
            supports.extend(
                [
                    EngineeringSupport(
                        id=f"support-{member_id}-start",
                        node_id=start_id,
                        restraints={
                            "ux": True,
                            "uy": True,
                            "uz": True,
                            "rx": False,
                            "ry": False,
                            "rz": False,
                        },
                    ),
                    EngineeringSupport(
                        id=f"support-{member_id}-end",
                        node_id=end_id,
                        restraints={
                            "ux": True,
                            "uy": True,
                            "uz": True,
                            "rx": False,
                            "ry": False,
                            "rz": False,
                        },
                    ),
                ]
            )
            releases.extend(
                [
                    EngineeringRelease(
                        id=f"release-{member_id}-start",
                        member_id=member_id,
                        node_end="start",
                        releases={"ry": True, "rz": True},
                    ),
                    EngineeringRelease(
                        id=f"release-{member_id}-end",
                        member_id=member_id,
                        node_end="end",
                        releases={"ry": True, "rz": True},
                    ),
                ]
            )
        return nodes, members, supports, releases

    start_id = "node-support"
    end_id = "node-loaded"
    member_id = "member-primary"
    span_m = mm_to_m(inp.span_mm)
    z_m = mm_to_m(inp.installation_height_mm)
    nodes = [
        EngineeringNode(id=start_id, x_m=0.0, y_m=0.0, z_m=0.0),
        EngineeringNode(id=end_id, x_m=round(span_m, 6), y_m=0.0, z_m=round(z_m, 6)),
    ]
    members = [
        EngineeringMember(
            id=member_id,
            start_node_id=start_id,
            end_node_id=end_id,
            section_id=section_id,
            material_id=material_id,
            orientation_deg=orientation_deg,
            member_type="frame_member",
            calculation_role="primary",
        )
    ]
    supports = [
        EngineeringSupport(
            id="support-primary",
            node_id=start_id,
            restraints={"ux": True, "uy": True, "uz": True, "rx": True, "ry": True, "rz": True},
        )
    ]
    return nodes, members, supports, []


def _build_load_cases(inp: FanSupportInput) -> list[EngineeringLoadCase]:
    surface_origin = _surface_type_name(inp.walking_surface.surface_type)
    return [
        EngineeringLoadCase(
            id="case_g", name="G", type="permanent", origin="support_self_weight_and_surface"
        ),
        EngineeringLoadCase(
            id="case_q", name="Q", type="variable", origin="dynamic_and_imposed_loads"
        ),
        EngineeringLoadCase(
            id="case_eq",
            name="EQ",
            type="permanent",
            origin="equipment_weight_or_surface_equipment",
        ),
        EngineeringLoadCase(
            id="case_manual", name="MANUAL", type="manual", origin="manual_engineering_load"
        ),
        EngineeringLoadCase(
            id="case_seismic",
            name="E_SEISMIC",
            type="accidental",
            origin=f"seismic_equivalent_static:{surface_origin}",
        ),
    ]


def _build_load_combinations(
    combinations: list[LoadCombination],
) -> list[EngineeringLoadCombination]:
    mapping: dict[str, list[EngineeringLoadCombinationFactor]] = {
        "ULS_fundamental": [
            EngineeringLoadCombinationFactor(load_case_id="case_g", factor=1.35),
            EngineeringLoadCombinationFactor(load_case_id="case_eq", factor=1.35),
            EngineeringLoadCombinationFactor(load_case_id="case_q", factor=1.50),
            EngineeringLoadCombinationFactor(load_case_id="case_manual", factor=1.50),
        ],
        "ULS_seismic": [
            EngineeringLoadCombinationFactor(load_case_id="case_g", factor=1.0),
            EngineeringLoadCombinationFactor(load_case_id="case_eq", factor=1.0),
            EngineeringLoadCombinationFactor(load_case_id="case_manual", factor=1.0),
            EngineeringLoadCombinationFactor(load_case_id="case_seismic", factor=1.0),
        ],
        "SLS_characteristic": [
            EngineeringLoadCombinationFactor(load_case_id="case_g", factor=1.0),
            EngineeringLoadCombinationFactor(load_case_id="case_eq", factor=1.0),
            EngineeringLoadCombinationFactor(load_case_id="case_q", factor=1.0),
            EngineeringLoadCombinationFactor(load_case_id="case_manual", factor=1.0),
        ],
    }
    result: list[EngineeringLoadCombination] = []
    for combo in combinations:
        combo_type = "sls" if combo.name.upper().startswith("SLS") else "uls"
        result.append(
            EngineeringLoadCombination(
                id=combo.name.lower(),
                name=combo.name,
                type=combo_type,
                factors=mapping.get(combo.name, []),
                description=combo.description,
            )
        )
    return result


def _build_load_surfaces(inp: FanSupportInput) -> list[EngineeringLoadSurface]:
    load_path = build_load_path_summary(inp)
    if not load_path.surface_components:
        return []

    surfaces: list[EngineeringLoadSurface] = []
    for index, component in enumerate(load_path.surface_components, start=1):
        source = str(component["source"])
        surfaces.append(
            EngineeringLoadSurface(
                id=f"load-surface-{index}",
                name=source,
                type=_surface_type_name(inp.walking_surface.surface_type),
                load_case_id=_load_case_id(str(component["load_case"])),
                area_m2=_as_float(component["area_m2"]),
                load_kN_m2=_as_float(component["area_load_kn_m2"]),
                distribution_method=str(component["distribution_method"]),
                target_member_ids=[
                    str(item["target_member"])
                    for item in load_path.distributed_line_loads
                    if item["source"] == source
                ],
                resulting_line_loads=[
                    {
                        "target_member": str(item["target_member"]),
                        "line_load_kN_m": _as_float(item["line_load_kN_m"]),
                        "loaded_length_m": _as_float(item["loaded_length_m"]),
                        "total_load_kN": _as_float(item["total_load_kN"]),
                    }
                    for item in load_path.distributed_line_loads
                    if item["source"] == source
                ],
            )
        )
    return surfaces


def _build_manual_loads(inp: FanSupportInput) -> list[EngineeringManualLoad]:
    load_path = build_load_path_summary(inp)
    return [
        EngineeringManualLoad(
            id=f"manual-load-{index}",
            type=str(item["load_type"]),
            load_case_id=_load_case_id(str(item["load_case"])),
            target_id=str(item["target_member"]),
            direction=str(item["direction"]),
            value=_as_float(item["value"]),
            unit=str(item["unit"]),
            origin=str(item["name"]),
        )
        for index, item in enumerate(load_path.manual_loads_applied, start=1)
    ]


def _build_solver_results(
    result: FanSupportResult,
    solver_state: CalculationResultState,
) -> EngineeringSolverResults:
    if result.solver_engine == "global_frame" and (
        result.solver_reactions or result.solver_displacements or result.solver_member_end_forces
    ):
        return EngineeringSolverResults(
            status=solver_state,
            reactions=[
                {
                    "combination": str(item["combination"]),
                    "node_id": str(item["node_id"]),
                    "reaction_fx_kN": _as_float(item["reaction_fx_kN"]),
                    "reaction_fz_kN": _as_float(item["reaction_fz_kN"]),
                    "reaction_my_kNm": _as_float(item["reaction_my_kNm"]),
                }
                for item in result.solver_reactions
            ],
            displacements=[
                {
                    "combination": str(item["combination"]),
                    "node_id": str(item["node_id"]),
                    "ux_m": _as_float(item["ux_m"]),
                    "uz_m": _as_float(item["uz_m"]),
                    "ry_rad": _as_float(item["ry_rad"]),
                }
                for item in result.solver_displacements
            ],
            member_forces=list(result.solver_member_end_forces),
            warnings=list(result.solver_warnings),
        )
    member_force_rows = [
        {
            "combination": combo.name,
            "N_kN": combo.N_kN,
            "V_y_kN": combo.V_y_kN,
            "V_z_kN": combo.V_z_kN,
            "M_y_kNm": combo.M_y_kNm,
            "M_z_kNm": combo.M_z_kNm,
            "T_kNm": combo.T_kNm,
        }
        for combo in result.member_forces
    ]
    warnings = [
        "Simplified member-force recovery is available.",
        "Global frame reactions and nodal displacements are not available in the simplified engine.",
    ]
    return EngineeringSolverResults(
        status=solver_state,
        reactions=[],
        displacements=[],
        member_forces=member_force_rows
        if solver_state == CalculationResultState.SIMPLIFIED
        else [],
        warnings=warnings,
    )


def _build_member_checks(
    result: FanSupportResult,
    state: CalculationResultState,
) -> list[EngineeringMemberCheck]:
    if result.member_check_rows:
        checks: list[EngineeringMemberCheck] = []
        for row in result.member_check_rows:
            row_status = str(row.get("status", ""))
            checks.append(
                EngineeringMemberCheck(
                    member_id=str(row.get("member_id", "unknown_member")),
                    status=(
                        CalculationResultState.FAILED
                        if row_status == "FAIL"
                        else CalculationResultState.VERIFIED
                    ),
                    governing_check=str(row.get("governing_check", "not_available")),
                    utilization=float(row["utilization_ratio"])
                    if row.get("utilization_ratio") is not None
                    else None,
                    load_combination_id=str(row.get("governing_combination"))
                    if row.get("governing_combination")
                    else None,
                    warnings=["Member checks use solver-recovered internal forces."]
                    + [str(item) for item in row.get("warnings", [])],
                )
            )
        return checks

    if result.section_verification is None:
        return [
            EngineeringMemberCheck(
                member_id="primary_member",
                status=CalculationResultState.NOT_VERIFIED,
                governing_check="not_available",
                utilization=None,
                load_combination_id=None,
                warnings=["Member verification is not available for the current input."],
            )
        ]
    return [
        EngineeringMemberCheck(
            member_id="primary_member",
            status=state,
            governing_check=result.section_verification.governing_check or "not_available",
            utilization=result.section_verification.utilization_ratio,
            load_combination_id=result.section_verification.governing_combination or None,
            warnings=["Member checks are based on the current simplified structural model."],
        )
    ]


def _build_connection_checks(
    result: FanSupportResult,
    state: CalculationResultState,
) -> list[EngineeringConnectionCheck]:
    if result.connection_check_rows:
        checks: list[EngineeringConnectionCheck] = []
        for row in result.connection_check_rows:
            row_status = str(row.get("status", ""))
            checks.append(
                EngineeringConnectionCheck(
                    support_id=str(row.get("support_id", "support-1")),
                    type=str(row.get("type", "connection")),
                    status={
                        "verified": CalculationResultState.VERIFIED,
                        "failed": CalculationResultState.FAILED,
                        "not_verified": CalculationResultState.NOT_VERIFIED,
                        "requires_engineer_review": CalculationResultState.REQUIRES_ENGINEER_REVIEW,
                    }.get(row_status, CalculationResultState.NOT_VERIFIED),
                    utilization=float(row["utilization_ratio"])
                    if row.get("utilization_ratio") is not None
                    else None,
                    load_combination_id=str(row.get("governing_combination"))
                    if row.get("governing_combination")
                    else None,
                    reaction_fx_kN=_as_float(row["reaction_fx_kN"])
                    if row.get("reaction_fx_kN") is not None
                    else None,
                    reaction_fz_kN=_as_float(row["reaction_fz_kN"])
                    if row.get("reaction_fz_kN") is not None
                    else None,
                    reaction_my_kNm=_as_float(row["reaction_my_kNm"])
                    if row.get("reaction_my_kNm") is not None
                    else None,
                    missing_inputs=[str(item) for item in row.get("missing_inputs", [])],
                    warnings=[str(item) for item in row.get("warnings", [])],
                )
            )
        return checks

    return [
        EngineeringConnectionCheck(
            support_id="support-1",
            type="connection_placeholder",
            status=state,
            utilization=None,
            load_combination_id=None,
            reaction_fx_kN=None,
            reaction_fz_kN=None,
            reaction_my_kNm=None,
            missing_inputs=[],
            warnings=[
                "Explicit Phase 05 connection verification is not available for the current input.",
                "Load surfaces, tramex, and grating inputs must not be treated as base plate verification.",
            ],
        )
    ]


def build_phase01_engineering_model(
    inp: FanSupportInput,
    result: FanSupportResult,
    import_review: ImportedModelReview | None = None,
) -> tuple[EngineeringModel, EngineeringReportState]:
    calculation_model = _calculation_model_for_result(result)
    orientation_deg = resolve_section_orientation_deg(
        inp.section_orientation,
        inp.section_rotation_deg,
    )
    oriented_props = (
        get_local_section_axis_properties(result.recommended_section, orientation_deg)
        if result.recommended_section is not None
        else None
    )
    load_path = build_load_path_summary(inp)

    sections = _build_section(result.recommended_section, oriented_props)
    materials = [_build_material(inp)]
    section_id = sections[0].id if sections else None
    material_id = materials[0].id
    nodes, members, supports, releases = _build_frame_entities(
        inp,
        result,
        section_id,
        material_id,
        orientation_deg,
    )

    solver_state = determine_solver_state(
        calculation_model=calculation_model,
        has_nodes=bool(nodes),
        has_members=bool(members),
        has_supports=bool(supports),
        displacement_results_available=bool(result.solver_displacements),
        reaction_results_available=bool(result.solver_reactions),
        failed=result.solver_failed,
    )
    member_check_state = determine_member_check_state(
        has_checks=bool(result.member_check_rows) or result.section_verification is not None,
        calculation_model=calculation_model,
        uses_solver_results=bool(result.member_check_rows),
        has_failed_checks=any(str(row.get("status")) == "FAIL" for row in result.member_check_rows)
        or (
            result.section_verification is not None
            and result.section_verification.status.value == "FAIL"
        ),
    )
    serviceability_check = _serviceability_module_check(result)
    serviceability_state = determine_serviceability_state(
        include_serviceability=inp.calculation_options.include_serviceability,
        displacement_results_available=bool(result.solver_displacements),
        serviceability_check_status=(
            serviceability_check.status if serviceability_check is not None else None
        ),
    )
    connection_checks_requested = (
        inp.calculation_options.include_base_plate
        or inp.calculation_options.include_anchors
        or inp.support_fixation_medium == SupportFixationMedium.STEEL_STRUCTURE
        or inp.calculation_options.include_steel_connections
    )
    connection_state = determine_connection_state(
        checks_requested=connection_checks_requested,
        rows=result.connection_check_rows,
    )
    load_surface_state = determine_load_surface_state(
        has_load_surface=inp.walking_surface.surface_type != WalkingSurfaceType.NONE,
        has_manual_loads=bool(inp.manual_loads),
        load_distribution_available=(
            inp.has_platform_grillage and bool(load_path.distributed_line_loads)
        ),
        requires_engineer_review=load_path.requires_engineer_review,
    )
    import_review_state = determine_import_review_state(import_review)
    if calculation_model == CalculationModelType.GLOBAL_FRAME:
        calculation_model_state = (
            CalculationResultState.VERIFIED
            if solver_state == CalculationResultState.VERIFIED
            else CalculationResultState.FAILED
            if solver_state == CalculationResultState.FAILED
            else CalculationResultState.NOT_VERIFIED
        )
    else:
        calculation_model_state = CalculationResultState.SIMPLIFIED

    state_items = [
        EngineeringStateItem(
            id="calculation_model",
            label_key="engineering.item.calculationModel",
            state=calculation_model_state,
            notes=[f"Current engine uses the {calculation_model.value} structural model."],
        ),
        EngineeringStateItem(
            id="import_review",
            label_key="engineering.item.importReview",
            state=import_review_state,
            notes=(
                ["No BIM/IFC assisted import was used for the current calculation."]
                if import_review is None
                else (
                    [
                        "Imported BIM/IFC geometry was reviewed and explicitly confirmed by the user before calculation.",
                        "Imported geometry remains assisted input and does not silently replace the active solver model.",
                    ]
                    if import_review.confirmed and not import_review.requires_engineer_review
                    else [
                        "Imported BIM/IFC geometry requires explicit engineering review and warning resolution.",
                        "Support conditions are only accepted when explicitly present in the imported data.",
                    ]
                )
            )
            + [
                item.message
                for item in (import_review.warnings if import_review is not None else [])
            ],
        ),
        EngineeringStateItem(
            id="solver_results",
            label_key="engineering.item.solverResults",
            state=solver_state,
            notes=(
                [
                    "Global frame nodal displacements and support reactions are available from the Phase 03 solver."
                ]
                if solver_state == CalculationResultState.VERIFIED
                else ["Global frame nodal displacements and support reactions are not available."]
            )
            + list(result.solver_warnings),
        ),
        EngineeringStateItem(
            id="member_checks",
            label_key="engineering.item.memberChecks",
            state=member_check_state,
            notes=(
                [
                    "Member verification uses solver-recovered internal forces from the Phase 04 path."
                ]
                if result.member_check_rows
                else (
                    [
                        "At least one member verification failed and must not be presented as verified."
                    ]
                    if member_check_state == CalculationResultState.FAILED
                    else [
                        "Section/member utilization is still derived from the simplified member model."
                    ]
                )
            ),
        ),
        EngineeringStateItem(
            id="serviceability",
            label_key="engineering.item.serviceability",
            state=serviceability_state,
            notes=(
                []
                if serviceability_state == CalculationResultState.NOT_APPLICABLE
                else [
                    "Vertical deflection was checked against the configured serviceability limit."
                ]
                if serviceability_state == CalculationResultState.VERIFIED
                else ["Vertical deflection is close to the configured serviceability limit."]
                if serviceability_state == CalculationResultState.REQUIRES_ENGINEER_REVIEW
                else ["Vertical deflection exceeds the configured serviceability limit."]
                if serviceability_state == CalculationResultState.FAILED
                else [
                    "Deflection verification could not be completed because no SLS displacement result is available."
                ]
            ),
        ),
        EngineeringStateItem(
            id="connection_checks",
            label_key="engineering.item.connectionChecks",
            state=connection_state,
            notes=(
                ["Connection checks use explicit Phase 05 input data and solver support reactions."]
                if result.connection_check_rows
                else [
                    "Connection checks remain unavailable for the current input and must not be reported as verified."
                ]
            ),
        ),
        EngineeringStateItem(
            id="load_surfaces",
            label_key="engineering.item.loadSurfaces",
            state=load_surface_state,
            notes=(
                ["Tramex/grating/platform inputs are stored as load surfaces, not base plates."]
                + load_path.warnings
            ),
        ),
    ]

    contains_simplified = any(
        item.state == CalculationResultState.SIMPLIFIED for item in state_items
    )
    contains_unverified = any(
        item.state
        in (
            CalculationResultState.NOT_VERIFIED,
            CalculationResultState.REQUIRES_ENGINEER_REVIEW,
            CalculationResultState.FAILED,
        )
        for item in state_items
    )
    report_warnings = (
        ["Never interpret simplified or missing checks as verified."]
        + load_path.warnings
        + [item.message for item in (import_review.warnings if import_review is not None else [])]
    )
    report_state = EngineeringReportState(
        pdf_ready=True,
        engineering_review_required=True,
        contains_simplified_results=contains_simplified,
        contains_unverified_checks=contains_unverified,
        warnings=report_warnings,
        states=state_items,
    )

    model = EngineeringModel(
        project=EngineeringProject(
            id=inp.support_tag,
            name=inp.project_name,
            description=inp.design_notes,
            engineer=inp.prepared_by,
        ),
        structure=EngineeringStructure(
            id=inp.support_tag,
            support_type=inp.support_type.value,
            calculation_model=calculation_model,
        ),
        materials=materials,
        sections=sections,
        nodes=nodes,
        members=members,
        supports=supports,
        releases=releases,
        load_cases=_build_load_cases(inp),
        load_combinations=_build_load_combinations(result.all_combinations),
        load_surfaces=_build_load_surfaces(inp),
        manual_loads=_build_manual_loads(inp),
        analysis_settings=EngineeringAnalysisSettings(
            include_self_weight=True,
            solver_type=calculation_model.value,
            serviceability_limit=inp.calculation_options.serviceability_limit_label(),
            serviceability_custom_limit=(
                str(inp.calculation_options.serviceability_custom_limit_divisor)
                if inp.calculation_options.serviceability_custom_limit_divisor is not None
                else None
            ),
        ),
        solver_results=_build_solver_results(result, solver_state),
        member_checks=_build_member_checks(result, member_check_state),
        connection_checks=_build_connection_checks(result, connection_state),
        import_review=import_review,
        report_state=report_state,
    )
    return model, report_state
