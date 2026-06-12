"""Pure Python API for SFSC calculations."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError as PydanticValidationError

from .engines.selector import run_full_calculation
from .exceptions import SFSCBaseError
from .models import FanSupportInput
from .reports.export_json import export_report_dict


def _pydantic_errors(exc: PydanticValidationError) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for item in exc.errors():
        loc = ".".join(str(part) for part in item.get("loc", ())) or "__root__"
        errors.append(
            {
                "field": loc,
                "code": str(item.get("type", "validation_error")),
                "message": str(item.get("msg", "")),
            }
        )
    return errors


def run_calculation(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate payload and run the SFSC calculation without Streamlit.

    Success response:
        {"ok": True, "report": <canonical JSON envelope>}

    Error response:
        {"ok": False, "errors": [{"field", "code", "message"}]}
    """
    try:
        inp = FanSupportInput.model_validate(payload)
        ctx = run_full_calculation(inp)
        return {"ok": True, "report": export_report_dict(ctx)}
    except PydanticValidationError as exc:
        return {"ok": False, "errors": _pydantic_errors(exc)}
    except SFSCBaseError as exc:
        field = getattr(exc, "field", "") or getattr(exc, "parameter", "") or ""
        return {
            "ok": False,
            "errors": [{"field": field, "code": exc.code, "message": exc.message}],
        }
