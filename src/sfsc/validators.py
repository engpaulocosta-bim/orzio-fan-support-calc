"""Validação de inputs do sistema SFSC."""
from __future__ import annotations
from .exceptions import MissingInputError, ValidationError, OutOfScopeError
from .enums import OperationMode, SupportType
from .policy import WeightBand, weight_band, WEIGHT_BLOCK_KG, WEIGHT_PRODUCT_MAX_KG


def validate_fan_support_input(inp) -> None:
    """Valida FanSupportInput antes de calcular. Lança excepção se inválido."""

    if not inp.fan_units:
        raise MissingInputError("fan_units", "definição do ventilador")

    total_weight = sum(u.operating_weight_kg for u in inp.fan_units)
    if total_weight <= 0:
        raise ValidationError("Peso total do ventilador deve ser > 0 kg", "operating_weight_kg")

    band = weight_band(total_weight)
    if band == WeightBand.BLOCKED:
        raise OutOfScopeError(
            "Peso total fora do âmbito do modelo (política de escopo SFSC)",
            parameter="total_weight_kg",
            value=round(total_weight, 1),
            limit=WEIGHT_BLOCK_KG,
        )
    if band == WeightBand.EXTENDED and not inp.confirm_extended_range:
        raise OutOfScopeError(
            "Peso total fora da faixa do produto. Utilização entre "
            f"{WEIGHT_PRODUCT_MAX_KG:.0f} e {WEIGHT_BLOCK_KG:.0f} kg exige "
            "confirmação explícita (confirm_extended_range=True) e revisão "
            "por engenheiro estrutural qualificado",
            parameter="total_weight_kg",
            value=round(total_weight, 1),
            limit=WEIGHT_PRODUCT_MAX_KG,
        )

    if inp.installation_height_mm <= 0:
        raise MissingInputError("installation_height_mm", "geometria do suporte")

    if inp.span_mm <= 0:
        raise MissingInputError("span_mm", "geometria do suporte")

    if inp.operation_mode == OperationMode.VERIFY:
        if not inp.received_section_tag:
            raise MissingInputError("received_section_tag", "modo verificar")
        if inp.received_section_family is None:
            raise MissingInputError("received_section_family", "modo verificar")

    if inp.support_type == SupportType.CANTILEVER_1:
        if inp.cantilever_subtype is None:
            raise MissingInputError("cantilever_subtype", "CANTILEVER_1")

    if inp.include_base_plate:
        if inp.fan_connection_type is None:
            raise MissingInputError("fan_connection_type", "mesa activada")

    if inp.anti_vibration.value == "springs":
        if inp.anti_vibration_static_deflection_mm is None:
            raise MissingInputError(
                "anti_vibration_static_deflection_mm",
                "anti-vibração por molas"
            )
        if inp.anti_vibration_static_deflection_mm <= 0:
            raise ValidationError(
                "Deflexão estática das molas deve ser > 0 mm",
                "anti_vibration_static_deflection_mm"
            )
