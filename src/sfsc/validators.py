"""Validação de inputs do sistema SFSC."""
from __future__ import annotations
import math
from .exceptions import MissingInputError, ValidationError, OutOfScopeError
from .enums import OperationMode, SupportType


def validate_fan_support_input(inp) -> None:
    """Valida FanSupportInput antes de calcular. Lança excepção se inválido."""

    if not inp.fan_units:
        raise MissingInputError("fan_units", "definição do ventilador")

    total_weight = sum(u.operating_weight_kg for u in inp.fan_units)
    if not math.isfinite(total_weight):
        raise ValidationError("Peso total do ventilador deve ser finito", "operating_weight_kg")
    if total_weight <= 0:
        raise ValidationError("Peso total do ventilador deve ser > 0 kg", "operating_weight_kg")

    if total_weight > 2000:
        raise OutOfScopeError(
            "Peso total fora do âmbito do modelo",
            parameter="total_weight_kg",
            value=round(total_weight, 1),
            limit=2000,
        )

    if not math.isfinite(inp.installation_height_mm) or inp.installation_height_mm <= 0:
        raise MissingInputError("installation_height_mm", "geometria do suporte")

    if not math.isfinite(inp.span_mm) or inp.span_mm <= 0:
        raise MissingInputError("span_mm", "geometria do suporte")

    if not math.isfinite(inp.eccentricity_mm) or inp.eccentricity_mm < 0:
        raise ValidationError("Excentricidade do CG deve ser >= 0 e finita", "eccentricity_mm")

    if not math.isfinite(inp.dynamic_factor) or inp.dynamic_factor < 1.0:
        raise ValidationError("Factor dinamico deve ser >= 1.0 e finito", "dynamic_factor")

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
        if inp.base_plate_thickness_mm is not None and inp.base_plate_thickness_mm <= 0:
            raise ValidationError(
                "Espessura da chapa deve ser > 0 mm ou 0 para auto",
                "base_plate_thickness_mm",
            )

    if inp.anchorage_substrate.value == "steel_structure":
        valid_grades = {"5.8", "8.8", "10.9", "A4-70"}
        if inp.receiver_bolt_grade not in valid_grades:
            raise ValidationError("Classe de parafusos receptor invalida", "receiver_bolt_grade")
        for field_name in (
            "receiver_plate_thickness_mm",
            "receiver_edge_distance_mm",
            "receiver_spacing_mm",
        ):
            value = getattr(inp, field_name)
            if not math.isfinite(value) or value <= 0:
                raise ValidationError(f"{field_name} deve ser > 0 e finito", field_name)

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
