"""Enumerações do sistema SFSC."""
from __future__ import annotations
from enum import Enum


class SupportType(str, Enum):
    HANGER       = "hanger"
    CANTILEVER_1 = "cantilever_1"
    CANTILEVER_2 = "cantilever_2"
    CANTILEVER_3 = "cantilever_3"
    PEDESTAL     = "pedestal"
    PLATFORM     = "platform"
    COMBINED     = "combined"


class CantileverSubtype(str, Enum):
    PURE      = "pure"       # consola horizontal pura
    BRACKETED = "bracketed"  # com diagonal (mão-francesa triangulada)


class Country(str, Enum):
    PORTUGAL   = "PT"
    SPAIN      = "ES"
    IRELAND    = "IE"
    EU_GENERIC = "EU"
    UK         = "UK"
    FRANCE     = "FR"
    BRAZIL     = "BR"
    CHILE      = "CL"


class StructuralCode(str, Enum):
    EC3_EN1993  = "EN1993-1-1"
    EC3_UK_NA   = "EN1993-1-1+UK_NA"
    EC3_NF_NA   = "EN1993-1-1+NF_NA"
    NBR_8800    = "NBR_8800:2008"
    NCH_427     = "NCh427:2020"


class SeismicCode(str, Enum):
    EC8         = "EN1998-1"
    EC8_UK      = "EN1998-1+UK_NA"
    NBR_15421   = "NBR_15421:2006"
    NCH_433     = "NCh433:2009"


class SteelGrade(str, Enum):
    S235      = "S235"
    S275      = "S275"
    S355      = "S355"
    A36       = "A36"
    A572_GR50 = "A572Gr50"
    AT500     = "AT-500"


class SectionFamily(str, Enum):
    HEA    = "HEA"
    HEB    = "HEB"
    IPE    = "IPE"
    UPN    = "UPN"
    RHS    = "RHS"
    L      = "L"
    C      = "C"
    CUSTOM = "CUSTOM"


class ExposureClass(str, Enum):
    INTERIOR_DRY = "interior_dry"
    INTERIOR_WET = "interior_wet"
    EXTERIOR     = "exterior"
    CORROSIVE    = "corrosive"


class AntiVibrationType(str, Enum):
    NONE         = "none"
    SPRINGS      = "springs"
    SILENTBLOCKS = "silentblocks"


class OperationMode(str, Enum):
    DIMENSION = "dimension"
    VERIFY    = "verify"


class ClassificationLevel(str, Enum):
    PRELIMINARY          = "PRELIMINARY"
    ENGINEERING_ESTIMATE = "ENGINEERING_ESTIMATE"
    REQUIRES_SPECIALIST  = "REQUIRES_SPECIALIST"


class CheckerStatus(str, Enum):
    PASS                = "PASS"
    FAIL                = "FAIL"
    MARGINAL            = "MARGINAL"
    DATASET_MISSING     = "DATASET_MISSING"
    OUT_OF_SCOPE        = "OUT_OF_SCOPE"
    REQUIRES_SPECIALIST = "REQUIRES_SPECIALIST"
    WARNING             = "WARNING"


class FanConnectionType(str, Enum):
    DIRECT_FLANGE = "direct_flange"   # flange do ventilador parafusa directamente na chapa
    FRAME_PLATFORM = "frame_platform" # ventilador pousa num frame, frame fixa à estrutura
    BOTH           = "both"           # utilizador define caso a caso


class AnchorageSubstrate(str, Enum):
    CONCRETE = "concrete"
    STEEL_STRUCTURE = "steel_structure"


class FanType(str, Enum):
    AXIAL         = "axial"
    CENTRIFUGAL   = "centrifugal"
    MIXED_FLOW    = "mixed_flow"
    INLINE        = "inline"
