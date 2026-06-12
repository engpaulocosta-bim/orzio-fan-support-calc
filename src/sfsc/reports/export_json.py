"""Canonical JSON export for Orzio integration workflows."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from uuid import uuid4

from .. import __version__
from ..assessment import assess_result
from ..config import get_assumptions
from ..models import ReportContext

SCHEMA_VERSION = "1.0"


def _expanded_assumptions(ids: list[str]) -> list[dict[str, object]]:
    by_id = {item.get("id"): item for item in get_assumptions().get("assumptions", [])}
    expanded: list[dict[str, object]] = []
    for assumption_id in ids:
        item = by_id.get(assumption_id)
        if item is None:
            expanded.append({"id": assumption_id, "description": "", "impact": ""})
        else:
            expanded.append(dict(item))
    return expanded


def _jsonable(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    return value


def export_report_dict(ctx: ReportContext, calc_id: str | None = None) -> dict[str, object]:
    """Build the schema-versioned JSON envelope for a ReportContext."""
    result = ctx.fan_support_result
    assessment = assess_result(result) if result is not None else None
    inp = ctx.fan_support_input

    return {
        "schema_version": SCHEMA_VERSION,
        "calc_id": calc_id or str(uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_id": ctx.project_name,
        "support_id": ctx.support_tag,
        "software_version": __version__,
        "dataset_provenance": ctx.dataset_provenance,
        "input": inp.model_dump(mode="json") if inp is not None else None,
        "result": result.model_dump(mode="json") if result is not None else None,
        "assessment": _jsonable(asdict(assessment)) if assessment is not None else None,
        "warnings": [item.model_dump(mode="json") for item in ctx.warnings],
        "citations": [item.model_dump(mode="json") for item in ctx.citations],
        "assumptions": _expanded_assumptions(ctx.assumptions_declared),
        "limitations": list(ctx.limitations),
    }


def generate_json(
    ctx: ReportContext,
    output_path: str | Path | None = None,
    calc_id: str | None = None,
) -> str:
    """Serialize the canonical JSON envelope."""
    payload = export_report_dict(ctx, calc_id=calc_id)
    json_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if output_path:
        Path(output_path).write_text(json_text, encoding="utf-8")
    return json_text
