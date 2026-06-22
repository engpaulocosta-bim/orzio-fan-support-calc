"""Enumerações do sistema SFSC."""

from __future__ import annotations

from enum import Enum


class SupportType(str, Enum):
    HANGER = "hanger"
    CANTILEVER_1 = "cantilever_1"
    CANTILEVER_2 = "cantilever_2"
    CANTILEVER_3 = "cantilever_3"
    PEDESTAL = "pedestal"
    COMBINED = "combined"
    # Plataforma metálica com quadro e escoras (recomendada p/ modelos tipo Robot).
    PLATFORM_FRAME_BRACED = "platform_frame_braced"


class CantileverSubtype(str, Enum):
    PURE = "pure"  # consola horizontal pura
    BRACKETED = "bracketed"  # com diagonal (mão-francesa triangulada)


class Country(str, Enum):
    PORTUGAL = "PT"
    SPAIN = "ES"
    IRELAND = "IE"
    EU_GENERIC = "EU"
    UK = "UK"
    FRANCE = "FR"
    BRAZIL = "BR"
    CHILE = "CL"


class StructuralCode(str, Enum):
    EC3_EN1993 = "EN1993-1-1"
    EC3_UK_NA = "EN1993-1-1+UK_NA"
    EC3_NF_NA = "EN1993-1-1+NF_NA"
    NBR_8800 = "NBR_8800:2008"
    NCH_427 = "NCh427:2020"


class SeismicCode(str, Enum):
    EC8 = "EN1998-1"
    EC8_UK = "EN1998-1+UK_NA"
    NBR_15421 = "NBR_15421:2006"
    NCH_433 = "NCh433:2009"


class SteelGrade(str, Enum):
    S235 = "S235"
    S275 = "S275"
    S355 = "S355"
    A36 = "A36"
    A572_GR50 = "A572Gr50"
    AT500 = "AT-500"


class SectionFamily(str, Enum):
    HEA = "HEA"
    HEB = "HEB"
    IPE = "IPE"
    UPN = "UPN"
    RHS = "RHS"
    L = "L"
    C = "C"
    CUSTOM = "CUSTOM"


class ExposureClass(str, Enum):
    INTERIOR_DRY = "interior_dry"
    INTERIOR_WET = "interior_wet"
    EXTERIOR = "exterior"
    CORROSIVE = "corrosive"


class AntiVibrationType(str, Enum):
    NONE = "none"
    SPRINGS = "springs"
    SILENTBLOCKS = "silentblocks"


class OperationMode(str, Enum):
    DIMENSION = "dimension"
    VERIFY = "verify"


class ClassificationLevel(str, Enum):
    PRELIMINARY = "PRELIMINARY"
    ENGINEERING_ESTIMATE = "ENGINEERING_ESTIMATE"
    REQUIRES_SPECIALIST = "REQUIRES_SPECIALIST"


class CheckerStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    MARGINAL = "MARGINAL"
    DATASET_MISSING = "DATASET_MISSING"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    REQUIRES_SPECIALIST = "REQUIRES_SPECIALIST"
    WARNING = "WARNING"


class FanConnectionType(str, Enum):
    DIRECT_FLANGE = "direct_flange"  # flange do ventilador parafusa directamente na chapa
    FRAME_PLATFORM = "frame_platform"  # ventilador pousa num frame, frame fixa à estrutura
    BOTH = "both"  # utilizador define caso a caso


class FanType(str, Enum):
    AXIAL = "axial"
    CENTRIFUGAL = "centrifugal"
    MIXED_FLOW = "mixed_flow"
    INLINE = "inline"


# ── Conceitos separados (tarefa 1.4 / secção 10) ────────────────────────────


class WalkingSurfaceType(str, Enum):
    """Superfície superior de distribuição de carga — NÃO é base plate."""

    NONE = "none"
    STEEL_GRATING_TRAMEX = "steel_grating_tramex"
    CHECKER_PLATE = "checker_plate"
    SOLID_PLATE = "solid_plate"
    OTHER = "other"


class SupportFixationMedium(str, Enum):
    """Meio em que o suporte é fixado — decide betão (EN 1992-4) vs aço (EN 1993-1-8)."""

    CONCRETE = "concrete"
    STEEL_STRUCTURE = "steel_structure"
    MASONRY = "masonry"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class BasePlateRole(str, Enum):
    """Papel da chapa de base/ligação — distinto de superfície de piso."""

    NONE = "none"
    EQUIPMENT_SPREADER = "equipment_spreader"
    SUPPORT_FOOT_PLATE = "support_foot_plate"
    CONNECTION_PLATE_TO_STEEL = "connection_plate_to_steel"
    CONNECTION_PLATE_TO_CONCRETE = "connection_plate_to_concrete"


class SteelConnectionType(str, Enum):
    """Tipo de ligação aço-aço para fixação em estrutura metálica."""

    BOLTED = "bolted"
    WELDED = "welded"
    BOLTED_WELDED = "bolted_welded"


class BoltClass(str, Enum):
    C4_6 = "4.6"
    C5_6 = "5.6"
    C8_8 = "8.8"
    C10_9 = "10.9"


class SectionOrientation(str, Enum):
    """Orientação da secção — crítico em IPE/UPN (eixo forte vs fraco)."""

    STRONG_AXIS_VERTICAL = "strong_axis_vertical"
    WEAK_AXIS_VERTICAL = "weak_axis_vertical"
    CUSTOM_ROTATION = "custom_rotation"


class CalculationMode(str, Enum):
    """Modo de cálculo — evita comparar SFSC global com barras do Robot."""

    ENGINEERING_ESTIMATE = "engineering_estimate"
    ROBOT_BENCHMARK = "robot_benchmark"
    FULL_PRELIMINARY_DESIGN = "full_preliminary_design"


class CheckStatus(str, Enum):
    """Estado granular de uma verificação individual (tarefa 1.2)."""

    OK = "ok"
    MARGINAL = "marginal"
    FAIL = "fail"
    NOT_CHECKED = "not_checked"
    INFORMATIVE = "informative"


class ModuleId(str, Enum):
    """Identificador estável de cada módulo de cálculo (tarefa 1.1 / secção 3)."""

    STEEL_SECTION = "steel_section"
    LATERAL_TORSIONAL_BUCKLING = "lateral_torsional_buckling"
    BASE_PLATE = "base_plate"
    CONCRETE_ANCHORS = "concrete_anchors"
    STEEL_CONNECTIONS = "steel_connections"
    SEISMIC_EQUIVALENT_STATIC = "seismic_equivalent_static"
    SERVICEABILITY = "serviceability"
    LOAD_DISTRIBUTION_SURFACE = "load_distribution_surface"
    MODAL_FREQUENCY = "modal_frequency"


class ServiceabilityLimit(str, Enum):
    L_200 = "L/200"
    L_250 = "L/250"
    L_360 = "L/360"
    CUSTOM = "custom"


class LoadDistributionMethod(str, Enum):
    ONE_WAY = "one_way"
    TWO_WAY = "two_way"
    TRIBUTARY_WIDTH = "tributary_width"
    MANUAL = "manual"


class ManualLoadType(str, Enum):
    POINT = "point"
    LINE = "line"
    AREA = "area"


class LoadDirection(str, Enum):
    GLOBAL_X = "global_x"
    GLOBAL_Y = "global_y"
    GLOBAL_Z = "global_z"
    LOCAL_Y = "local_y"
    LOCAL_Z = "local_z"


class LoadCaseName(str, Enum):
    G = "G"
    Q = "Q"
    EQ = "EQ"
    MANUAL = "MANUAL"
