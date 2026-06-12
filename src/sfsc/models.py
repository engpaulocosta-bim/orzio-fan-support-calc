"""Modelos Pydantic v2 — SFSC."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from .checks import CheckResult
from .enums import (
    AntiVibrationType,
    BasePlateRole,
    BoltClass,
    CalculationMode,
    CantileverSubtype,
    CheckerStatus,
    CheckStatus,
    ClassificationLevel,
    Country,
    ExposureClass,
    FanConnectionType,
    FanType,
    ModuleId,
    OperationMode,
    SectionFamily,
    SectionOrientation,
    SeismicCode,
    SteelConnectionType,
    SteelGrade,
    StructuralCode,
    SupportFixationMedium,
    SupportType,
    WalkingSurfaceType,
)

# ── Opções de cálculo (módulos opcionais — tarefa 1.3) ──────────────────────


class CalculationOptions(BaseModel):
    """Toggles que decidem que módulos entram no cálculo.

    Cada toggle afeta realmente o cálculo, aparece no relatório e entra no
    hash de rastreabilidade (``options_fingerprint``).
    """

    include_dynamic_factor: bool = True
    include_biaxial_bending: bool = True
    include_lateral_torsional_buckling: bool = True
    include_base_plate: bool = False
    include_anchors: bool = True
    include_steel_connections: bool = True
    include_seismic_equivalent_static: bool = True
    include_serviceability: bool = False

    def fingerprint(self) -> str:
        """Assinatura curta e estável das opções (entra no hash de rastreabilidade)."""
        import hashlib

        payload = "|".join(f"{k}={int(v)}" for k, v in sorted(self.model_dump().items()))
        return hashlib.sha256(payload.encode()).hexdigest()[:12]


# ── Superfície de distribuição de carga (tramex/chapa — NÃO é base plate) ────


class WalkingSurface(BaseModel):
    """Superfície superior (tramex, grelha, chapa) que distribui carga às vigas.

    Tarefa 1.4 / secção 10: NUNCA calcula cone de betão, pull-out, pry-out ou
    ancoragens — apenas converte peso em carga de área e/ou peso próprio.
    """

    surface_type: WalkingSurfaceType = WalkingSurfaceType.NONE
    self_weight_kn_m2: float = Field(
        default=0.0, ge=0, description="Peso próprio da superfície [kN/m²]"
    )
    equipment_load_distributed: bool = Field(
        default=False,
        description="True = carga do equipamento distribuída na superfície; False = pontual",
    )


# ── Fixação em estrutura metálica (alternativa ao betão — tarefa 1.5) ────────


class SteelFixationInput(BaseModel):
    """Dados da ligação aço-aço quando a fixação é em estrutura metálica."""

    connection_type: SteelConnectionType = SteelConnectionType.BOLTED
    receiving_member_section_id: str | None = None
    receiving_member_material: str | None = None
    plate_thickness_mm: float | None = Field(default=None, gt=0)
    bolt_diameter_mm: float | None = Field(default=None, gt=0)
    bolt_class: BoltClass = BoltClass.C8_8
    number_of_bolts: int | None = Field(default=None, gt=0)
    hole_diameter_mm: float | None = Field(default=None, gt=0)
    edge_distance_mm: float | None = Field(default=None, gt=0)
    spacing_mm: float | None = Field(default=None, gt=0)
    weld_size_mm: float | None = Field(default=None, gt=0)
    weld_length_mm: float | None = Field(default=None, gt=0)
    has_stiffeners: bool = False


# ── Dados do ventilador ────────────────────────────────────────────────────────


class FanUnit(BaseModel):
    """Uma unidade de ventilador industrial."""

    tag: str = ""
    fan_type: FanType = FanType.CENTRIFUGAL
    weight_kg: float = Field(gt=0, description="Peso vazio [kg]")
    operating_weight_kg: float = Field(gt=0, description="Peso em operação [kg]")
    footprint_length_mm: float = Field(gt=0, description="Comprimento da base [mm]")
    footprint_width_mm: float = Field(gt=0, description="Largura da base [mm]")
    centre_of_gravity_height_mm: float = Field(
        default=0.0, ge=0, description="Altura do CG acima da base [mm]"
    )
    rated_power_kw: float | None = Field(
        default=None, ge=0, description="Potência nominal [kW] — para memorial"
    )
    speed_rpm: float | None = Field(default=None, ge=0, description="Velocidade de rotação [rpm]")

    @model_validator(mode="after")
    def _check_operating_weight(self) -> FanUnit:
        if self.operating_weight_kg < self.weight_kg:
            raise ValueError(
                "operating_weight_kg deve ser ≥ weight_kg "
                f"({self.operating_weight_kg} < {self.weight_kg})"
            )
        return self


# ── Input principal ────────────────────────────────────────────────────────────


class FanSupportInput(BaseModel):
    """Entrada completa para cálculo de suporte de ventilador industrial."""

    # Identificação
    project_name: str = Field(min_length=1)
    support_tag: str = Field(min_length=1, description="Ex: FSU-001")
    design_notes: str = ""
    prepared_by: str = "SFSC v1.0"

    # Equipamento
    fan_units: list[FanUnit] = Field(min_length=1)

    # Tipo de suporte e modo
    support_type: SupportType
    cantilever_subtype: CantileverSubtype | None = None
    operation_mode: OperationMode = OperationMode.DIMENSION

    # País e norma
    country: Country = Country.EU_GENERIC
    seismic_zone: str | None = Field(
        default=None, description="Zona sísmica local. None = automático por país (conservativo)"
    )

    # Material
    steel_grade: SteelGrade = SteelGrade.S355
    preferred_section_families: list[SectionFamily] = Field(
        default_factory=lambda: [SectionFamily.HEB, SectionFamily.IPE]
    )
    allow_auto_select: bool = True

    # Factor dinâmico (arranque / vibração)
    dynamic_factor: float = Field(
        default=1.5,
        ge=1.0,
        le=3.0,
        description="Factor de amplificação dinâmica. Default 1.5 (VDI 3840)",
    )

    # Geometria
    installation_height_mm: float = Field(
        gt=0, description="Altura de instalação — chão/tecto à base do ventilador [mm]"
    )
    span_mm: float = Field(gt=0, description="Vão / comprimento do braço do suporte [mm]")
    eccentricity_mm: float = Field(
        default=0.0, ge=0, description="Excentricidade do CG em relação ao apoio [mm]"
    )

    # Hanger — comprimento dos varões roscados
    hanger_rod_length_mm: float | None = Field(
        default=None, gt=0, description="Comprimento dos varões roscados (HANGER) [mm]"
    )

    # Anti-vibração
    anti_vibration: AntiVibrationType = AntiVibrationType.NONE
    anti_vibration_static_deflection_mm: float | None = Field(
        default=None, gt=0, description="Deflexão estática das molas [mm] — obrigatório se SPRINGS"
    )

    # Mesa / base plate
    include_base_plate: bool = False
    fan_connection_type: FanConnectionType | None = None
    base_plate_thickness_mm: float | None = Field(
        default=None, gt=0, description="Espessura da chapa. None = dimensionar automaticamente"
    )

    # Modo verificar
    received_section_tag: str | None = None
    received_section_family: SectionFamily | None = None

    # Condições ambientais
    exposure_class: ExposureClass = ExposureClass.INTERIOR_DRY

    # Betão de suporte (para ancoragens)
    concrete_grade: str = Field(
        default="C25/30", description="Classe do betão de fixação. Ex: C25/30, C30/37, fck=25MPa"
    )

    # Política de peso (sfsc.policy): faixa EXTENDED (600–1000 kg) exige
    # confirmação explícita do utilizador.
    confirm_extended_range: bool = Field(
        default=False,
        description="Confirmação de utilização na faixa 600–1000 kg, fora da faixa do produto",
    )

    # ── Conceitos separados (tarefa 1.4/1.5/secção 6) ────────────────────────
    calculation_mode: CalculationMode = CalculationMode.FULL_PRELIMINARY_DESIGN
    calculation_options: CalculationOptions = Field(default_factory=CalculationOptions)
    walking_surface: WalkingSurface = Field(default_factory=WalkingSurface)
    support_fixation_medium: SupportFixationMedium = SupportFixationMedium.CONCRETE
    base_plate_role: BasePlateRole = BasePlateRole.NONE
    steel_fixation: SteelFixationInput | None = None
    section_orientation: SectionOrientation = SectionOrientation.STRONG_AXIS_VERTICAL
    section_rotation_deg: float | None = None

    @model_validator(mode="after")
    def _sync_options_with_legacy_flags(self) -> FanSupportInput:
        """Mantém include_base_plate (legado) coerente com as opções de módulos."""
        # Se o utilizador ativou a mesa pelo flag legado, refletir nas opções.
        if self.include_base_plate and not self.calculation_options.include_base_plate:
            self.calculation_options = self.calculation_options.model_copy(
                update={"include_base_plate": True}
            )
        return self

    @model_validator(mode="after")
    def _check_verify_mode(self) -> FanSupportInput:
        if self.operation_mode == OperationMode.VERIFY:
            if not self.received_section_tag:
                raise ValueError("received_section_tag obrigatório em modo VERIFY")
            if self.received_section_family is None:
                raise ValueError("received_section_family obrigatório em modo VERIFY")
        return self

    @model_validator(mode="after")
    def _check_base_plate(self) -> FanSupportInput:
        if self.include_base_plate and self.fan_connection_type is None:
            raise ValueError("fan_connection_type obrigatório quando include_base_plate=True")
        return self

    @property
    def total_operating_weight_kg(self) -> float:
        return sum(u.operating_weight_kg for u in self.fan_units)

    @property
    def total_weight_kn(self) -> float:
        from .units import kg_to_kn

        return kg_to_kn(self.total_operating_weight_kg)


# ── Secção metálica ────────────────────────────────────────────────────────────


class SteelSection(BaseModel):
    """Secção metálica do catálogo."""

    family: SectionFamily
    designation: str
    h_mm: float
    b_mm: float
    tw_mm: float
    tf_mm: float
    A_cm2: float
    I_y_cm4: float
    I_z_cm4: float
    W_el_y_cm3: float
    W_el_z_cm3: float
    W_pl_y_cm3: float
    W_pl_z_cm3: float
    i_y_mm: float
    i_z_mm: float
    weight_kgm: float

    @property
    def A_mm2(self) -> float:
        from .units import cm2_to_mm2

        return cm2_to_mm2(self.A_cm2)

    @property
    def I_y_mm4(self) -> float:
        from .units import cm4_to_mm4

        return cm4_to_mm4(self.I_y_cm4)

    @property
    def I_z_mm4(self) -> float:
        from .units import cm4_to_mm4

        return cm4_to_mm4(self.I_z_cm4)

    @property
    def W_el_y_mm3(self) -> float:
        from .units import cm3_to_mm3

        return cm3_to_mm3(self.W_el_y_cm3)

    @property
    def W_pl_y_mm3(self) -> float:
        from .units import cm3_to_mm3

        return cm3_to_mm3(self.W_pl_y_cm3)

    @property
    def W_pl_z_mm3(self) -> float:
        from .units import cm3_to_mm3

        return cm3_to_mm3(self.W_pl_z_cm3)


# ── Cargas ─────────────────────────────────────────────────────────────────────


class LoadCombination(BaseModel):
    """Combinação de acções calculada.

    member_level distingue acções totais (False — output de loads.py) de
    esforços de cálculo no elemento (True — output dos motores de suporte).
    Os dois níveis nunca devem ser misturados na mesma tabela (auditoria C-02).
    """

    name: str
    N_kN: float = 0.0
    V_y_kN: float = 0.0
    V_z_kN: float = 0.0
    M_y_kNm: float = 0.0
    M_z_kNm: float = 0.0
    T_kNm: float = 0.0
    governing: bool = False
    member_level: bool = False
    load_factors_used: dict[str, float] = Field(default_factory=dict)
    description: str = ""


# ── Resultados de verificação ──────────────────────────────────────────────────


class SectionVerificationResult(BaseModel):
    """Resultado da verificação de uma secção metálica."""

    section: SteelSection
    utilization_ratio: float
    utilization_by_check: dict[str, float] = Field(default_factory=dict)
    governing_check: str = ""
    governing_combination: str = ""
    status: CheckerStatus
    code_clause: str = ""
    warnings: list[str] = Field(default_factory=list)
    assumptions_used: list[str] = Field(default_factory=list)
    # Valores intermédios da combinação governante (Av, Vpl_Rd, Mcr, χ_LT, …)
    # — alimentam a memória de fórmulas do memorial PDF (auditoria 4.8).
    calculation_details: dict[str, float] = Field(default_factory=dict)


class BasePlateResult(BaseModel):
    """Resultado do dimensionamento da mesa / chapa de assento."""

    length_mm: float
    width_mm: float
    thickness_mm: float
    steel_grade: SteelGrade
    bearing_stress_mpa: float
    utilization_bearing: float
    utilization_bending: float
    utilization_ratio: float
    bolt_diameter_mm: float = 0.0
    n_bolts_fan: int = 0
    bolt_utilization_fan: float = 0.0
    n_bolts_structure: int = 0
    bolt_utilization_structure: float = 0.0
    hole_diameter_mm: float = 0.0
    anchor_spacing_x_mm: float = 0.0
    anchor_spacing_y_mm: float = 0.0
    edge_distance_x_mm: float = 0.0
    edge_distance_y_mm: float = 0.0
    min_spacing_mm: float = 0.0
    min_edge_distance_mm: float = 0.0
    spacing_ok: bool = True
    edge_distance_ok: bool = True
    concrete_cone_capacity_kN: float = 0.0
    pullout_capacity_kN: float = 0.0
    pryout_capacity_kN: float = 0.0
    utilization_concrete_cone: float = 0.0
    utilization_pullout: float = 0.0
    utilization_pryout: float = 0.0
    weld_throat_mm: float = 0.0
    weld_utilization: float = 0.0
    status: CheckerStatus
    code_clause: str = ""
    warnings: list[str] = Field(default_factory=list)


class AnchorResult(BaseModel):
    """Resultado do dimensionamento de ancoragens / varões de suspensão.

    anchor_type: "concrete" = ancoragem embebida em betão (hef aplicável);
                 "rod"      = varão roscado de suspensão (HANGER — sem betão).
    """

    n_anchors: int
    anchor_diameter_mm: float
    embedment_depth_mm: float
    anchor_type: str = "concrete"
    tensile_capacity_kN: float
    shear_capacity_kN: float
    utilization_tension: float
    utilization_shear: float
    utilization_combined: float
    status: CheckerStatus
    code_clause: str = ""
    warnings: list[str] = Field(default_factory=list)


class SteelFixationResult(BaseModel):
    """Resultado da fixação aço-aço (EN 1993-1-8) — alternativa ao betão (tarefa 1.5)."""

    connection_type: SteelConnectionType
    n_bolts: int
    bolt_diameter_mm: float
    bolt_class: str
    plate_thickness_mm: float
    utilization_bolt_shear: float
    utilization_bolt_tension: float
    utilization_bolt_interaction: float
    utilization_bearing: float
    utilization_weld: float
    utilization_plate: float
    utilization_ratio: float
    receiving_member_checked: bool = False
    status: CheckerStatus
    code_clause: str = "EN 1993-1-8"
    warnings: list[str] = Field(default_factory=list)
    intermediate_values: dict[str, float] = Field(default_factory=dict)


class MetalConnectionResult(BaseModel):
    """Resultado simplificado das ligações metálicas do suporte."""

    connection_type: str
    plate_thickness_mm: float
    bolt_diameter_mm: float
    bolt_hole_diameter_mm: float
    n_bolts: int
    bolt_grade: str = "8.8"
    min_spacing_mm: float
    provided_spacing_mm: float
    min_edge_distance_mm: float
    provided_edge_distance_mm: float
    spacing_ok: bool
    edge_distance_ok: bool
    bolt_shear_capacity_kN: float
    bolt_tension_capacity_kN: float
    utilization_bolt_shear: float
    utilization_bolt_tension: float
    weld_throat_mm: float
    weld_length_mm: float
    weld_utilization: float
    stiffener_required: bool = False
    stiffener_thickness_mm: float = 0.0
    cleat_angle: str = ""
    diagonal_member: str = ""
    utilization_ratio: float
    status: CheckerStatus
    code_clause: str = ""
    warnings: list[str] = Field(default_factory=list)


class FanSupportResult(BaseModel):
    """Resultado completo para um suporte de ventilador."""

    support_tag: str
    support_type: SupportType
    structural_code: StructuralCode
    seismic_code: SeismicCode
    seismic_factor_g: float
    total_weight_kN: float
    # Carga vertical ULS total (nível de acções) — auditoria C-02.
    design_load_kN: float
    # Combinação governante ao nível do ELEMENTO (esforços de cálculo).
    governing_load_combination: LoadCombination | None = None
    # Combinações de acções totais (output de loads.py, sem transformação).
    all_combinations: list[LoadCombination] = Field(default_factory=list)
    # Esforços de cálculo no elemento, por combinação (output do motor de suporte).
    member_forces: list[LoadCombination] = Field(default_factory=list)
    recommended_section: SteelSection | None = None
    section_verification: SectionVerificationResult | None = None
    section_options: list[SectionVerificationResult] = Field(default_factory=list)
    base_plate: BasePlateResult | None = None
    anchor: AnchorResult | None = None
    steel_fixation: SteelFixationResult | None = None
    metal_connection: MetalConnectionResult | None = None
    classification_level: ClassificationLevel = ClassificationLevel.ENGINEERING_ESTIMATE
    status: CheckerStatus = CheckerStatus.PASS
    warnings: list[str] = Field(default_factory=list)
    assumptions_used: list[str] = Field(default_factory=list)
    # Breakdown modular granular (tarefa 1.1) + diagnóstico global agregado.
    module_breakdown: list[CheckResult] = Field(default_factory=list)
    global_status: CheckStatus = CheckStatus.OK
    governing_module: ModuleId | None = None
    governing_eta: float | None = None


# ── Contexto do memorial ───────────────────────────────────────────────────────


class CitationItem(BaseModel):
    standard_id: str
    edition: str = ""
    clause: str = ""
    description: str = ""
    equation_used: str | None = None


class WarningItem(BaseModel):
    code: str
    severity: str = "WARNING"  # INFO, WARNING, CRITICAL
    message: str
    module: str = ""
    assumption_id: str | None = None


class ReportContext(BaseModel):
    """Contexto completo para geração do memorial de cálculo."""

    project_name: str
    support_tag: str
    prepared_by: str = "SFSC v1.0"
    date: str = ""
    revision: str = "A"

    fan_support_input: FanSupportInput | None = None
    fan_support_result: FanSupportResult | None = None

    citations: list[CitationItem] = Field(default_factory=list)
    warnings: list[WarningItem] = Field(default_factory=list)
    assumptions_declared: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    dataset_provenance: dict[str, Any] = Field(default_factory=dict)


class BatchRowResult(BaseModel):
    row_index: int
    support_tag: str
    status: str
    governing_issue: str | None = None
    dataset_missing: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    warnings_count: int = 0
    error_message: str | None = None
    report_context: ReportContext | None = None
