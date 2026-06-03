"""Excepções customizadas do sistema SFSC."""


class SFSCBaseError(Exception):
    def __init__(self, message: str, code: str = "SFSC_ERROR"):
        self.message = message
        self.code = code
        super().__init__(f"[{code}] {message}")


class ValidationError(SFSCBaseError):
    def __init__(self, message: str, field: str = ""):
        self.field = field
        super().__init__(message, "VALIDATION_ERROR")


class MissingInputError(ValidationError):
    def __init__(self, field: str, context: str = ""):
        msg = f"Campo obrigatório '{field}' ausente" + (f" para '{context}'" if context else "")
        super().__init__(msg, field)
        self.code = "MISSING_INPUT"


class DatasetMissingError(SFSCBaseError):
    def __init__(self, dataset: str, context: str = ""):
        msg = f"Dataset '{dataset}' não disponível" + (f" — {context}" if context else "")
        super().__init__(msg, "DATASET_MISSING")
        self.dataset = dataset


class OutOfScopeError(SFSCBaseError):
    def __init__(self, message: str, parameter: str = "", value=None, limit=None):
        detail = message
        if parameter and value is not None:
            detail += f" | {parameter} = {value}"
        if limit is not None:
            detail += f" | limite = {limit}"
        super().__init__(detail, "OUT_OF_SCOPE")
        self.parameter = parameter
        self.value = value
        self.limit = limit


class SectionNotFoundError(DatasetMissingError):
    def __init__(self, family: str, designation: str = ""):
        ctx = f"perfil: {designation}" if designation else ""
        super().__init__(f"section:{family}", ctx)


class SteelGradeNotFoundError(DatasetMissingError):
    def __init__(self, grade: str):
        super().__init__(f"steel_grade:{grade}")


class SeismicDataMissingError(DatasetMissingError):
    def __init__(self, country: str, zone: str = ""):
        ctx = f"zona: {zone}" if zone else ""
        super().__init__(f"seismic:{country}", ctx)


class VerificationFailedError(SFSCBaseError):
    def __init__(self, check: str, ratio: float, section: str = ""):
        msg = f"Verificação '{check}' falhou: η = {ratio:.3f} > 1.0"
        if section:
            msg += f" (secção: {section})"
        super().__init__(msg, "VERIFICATION_FAILED")
        self.check = check
        self.ratio = ratio
