"""Verificação final e classificação do resultado."""
from __future__ import annotations
from ..models import FanSupportInput, FanSupportResult
from ..enums import CheckerStatus, ClassificationLevel


def run_checker(inp: FanSupportInput, result: FanSupportResult) -> CheckerStatus:
    """Consolida todos os ratios de utilização e retorna status global."""
    statuses: list[CheckerStatus] = []

    if result.section_verification:
        statuses.append(result.section_verification.status)
    if result.base_plate:
        statuses.append(result.base_plate.status)
    if result.anchor:
        statuses.append(result.anchor.status)

    if not statuses:
        return CheckerStatus.PASS

    priority = [
        CheckerStatus.FAIL,
        CheckerStatus.REQUIRES_SPECIALIST,
        CheckerStatus.DATASET_MISSING,
        CheckerStatus.OUT_OF_SCOPE,
        CheckerStatus.MARGINAL,
        CheckerStatus.WARNING,
        CheckerStatus.PASS,
    ]
    for p in priority:
        if p in statuses:
            return p
    return CheckerStatus.PASS


def classify(inp: FanSupportInput, result: FanSupportResult) -> ClassificationLevel:
    """Determina o nível de classificação do cálculo."""
    total_kg = inp.total_operating_weight_kg

    # Peso > 500 kg → especialista
    if total_kg > 500.0:
        return ClassificationLevel.REQUIRES_SPECIALIST

    # Combinação sísmica governa (ag > 0.15g)
    if result.seismic_factor_g > 0.15:
        return ClassificationLevel.REQUIRES_SPECIALIST

    # COMBINED com molas → vibração fora do âmbito
    from ..enums import SupportType, AntiVibrationType
    if (result.support_type == SupportType.COMBINED and
            inp.anti_vibration == AntiVibrationType.SPRINGS):
        return ClassificationLevel.REQUIRES_SPECIALIST

    return ClassificationLevel.ENGINEERING_ESTIMATE
