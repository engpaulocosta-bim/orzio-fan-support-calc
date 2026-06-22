"""Phase 06 assisted BIM/IFC import review helpers."""

from __future__ import annotations

from collections import defaultdict, deque

from ..enums import SectionFamily, SteelGrade
from ..models import (
    ImportedElementPayload,
    ImportedMemberReview,
    ImportedModelPayload,
    ImportedModelReview,
    ImportedModelWarning,
    ImportedNodeReview,
    ImportedPoint3D,
    ImportedSupportReview,
)

_RECOGNISED_STRUCTURAL_CLASSES = {"beam", "column", "brace", "member", "ifcbeam", "ifccolumn"}
_NON_STRUCTURAL_CLASSES = {
    "plate",
    "grating",
    "tramex",
    "walkway",
    "equipment",
    "handrail",
    "cover",
    "ladder",
}
_SUPPORTED_SECTION_PREFIXES = {
    family.value for family in SectionFamily if family != SectionFamily.CUSTOM
}
_SUPPORTED_MATERIALS = {grade.value.upper() for grade in SteelGrade}


def _classification_token(value: str) -> str:
    return value.strip().lower().replace(" ", "").replace("_", "")


def _point_key(point: ImportedPoint3D) -> tuple[float, float, float]:
    return (round(point.x_m, 6), round(point.y_m, 6), round(point.z_m, 6))


def _point_distance(point_a: ImportedPoint3D, point_b: ImportedPoint3D) -> float:
    dx = point_a.x_m - point_b.x_m
    dy = point_a.y_m - point_b.y_m
    dz = point_a.z_m - point_b.z_m
    return (dx * dx + dy * dy + dz * dz) ** 0.5


def _is_supported_section_name(section_name: str | None) -> bool:
    if not section_name:
        return False
    normalized = section_name.upper().replace(" ", "")
    return any(normalized.startswith(prefix) for prefix in _SUPPORTED_SECTION_PREFIXES)


def _is_supported_material_name(material_name: str | None) -> bool:
    if not material_name:
        return False
    return material_name.upper().replace(" ", "") in _SUPPORTED_MATERIALS


def _append_warning(
    warnings: list[ImportedModelWarning],
    *,
    code: str,
    severity: str,
    message: str,
    element_id: str | None = None,
) -> None:
    warnings.append(
        ImportedModelWarning(
            code=code,
            severity=severity,
            message=message,
            element_id=element_id,
        )
    )


def _member_role(element: ImportedElementPayload) -> str | None:
    token = _classification_token(element.classification)
    if token in _NON_STRUCTURAL_CLASSES:
        return None
    if token in _RECOGNISED_STRUCTURAL_CLASSES:
        return token
    return None if not element.is_structural else "unknown_structural"


def build_import_review(
    payload: ImportedModelPayload,
    *,
    confirmed: bool,
    confirmed_by: str | None,
    confirmation_notes: str,
) -> ImportedModelReview:
    node_ids_by_key: dict[tuple[float, float, float], str] = {}
    merged_counts: dict[str, int] = defaultdict(int)
    nodes: list[ImportedNodeReview] = []
    node_counter = 0
    members: list[ImportedMemberReview] = []
    supports: list[ImportedSupportReview] = []
    warnings: list[ImportedModelWarning] = []
    adjacency: dict[str, set[str]] = defaultdict(set)
    support_keys: set[tuple[str, str, str]] = set()
    accepted_member_count = 0
    rejected_element_count = 0
    non_structural_count = 0

    def node_id_for(point: ImportedPoint3D) -> str:
        nonlocal node_counter
        key = _point_key(point)
        existing = node_ids_by_key.get(key)
        if existing is not None:
            merged_counts[existing] += 1
            return existing
        node_counter += 1
        node_id = f"import-node-{node_counter}"
        node_ids_by_key[key] = node_id
        nodes.append(
            ImportedNodeReview(
                id=node_id,
                x_m=key[0],
                y_m=key[1],
                z_m=key[2],
                merged_duplicate_count=0,
            )
        )
        return node_id

    for element in payload.elements:
        token = _classification_token(element.classification)
        role = _member_role(element)
        member_warnings: list[str] = []

        if not element.is_structural or token in _NON_STRUCTURAL_CLASSES:
            non_structural_count += 1
            rejected_element_count += 1
            members.append(
                ImportedMemberReview(
                    id=element.id,
                    classification=element.classification,
                    accepted=False,
                    section_name=element.section_name,
                    material_name=element.material_name,
                    orientation_deg=element.orientation_deg,
                    rejection_reason="non_structural_element",
                    warnings=["Element ignored because it is not a structural member candidate."],
                )
            )
            continue

        if element.start is None or element.end is None:
            rejected_element_count += 1
            _append_warning(
                warnings,
                code="W-IFC-001",
                severity="CRITICAL",
                message="Imported element rejected because start/end geometry is incomplete.",
                element_id=element.id,
            )
            members.append(
                ImportedMemberReview(
                    id=element.id,
                    classification=element.classification,
                    accepted=False,
                    section_name=element.section_name,
                    material_name=element.material_name,
                    orientation_deg=element.orientation_deg,
                    rejection_reason="missing_geometry",
                    warnings=["Missing start or end point."],
                )
            )
            continue

        if _point_distance(element.start, element.end) <= 1e-9:
            rejected_element_count += 1
            _append_warning(
                warnings,
                code="W-IFC-002",
                severity="CRITICAL",
                message="Imported member rejected because it has zero length.",
                element_id=element.id,
            )
            members.append(
                ImportedMemberReview(
                    id=element.id,
                    classification=element.classification,
                    accepted=False,
                    section_name=element.section_name,
                    material_name=element.material_name,
                    orientation_deg=element.orientation_deg,
                    rejection_reason="zero_length",
                    warnings=["Zero-length member."],
                )
            )
            continue

        if role == "unknown_structural":
            member_warnings.append(
                "Structural class is not explicitly recognised and needs review."
            )
            _append_warning(
                warnings,
                code="W-IFC-003",
                severity="WARNING",
                message="Imported structural classification is not explicitly recognised.",
                element_id=element.id,
            )

        if not element.section_name:
            member_warnings.append("Section name missing.")
            _append_warning(
                warnings,
                code="W-IFC-004",
                severity="WARNING",
                message="Imported member is missing a section name.",
                element_id=element.id,
            )
        elif not _is_supported_section_name(element.section_name):
            member_warnings.append("Section name is not mapped to a supported profile family.")
            _append_warning(
                warnings,
                code="W-IFC-005",
                severity="WARNING",
                message="Imported member section name is not mapped to a supported SFSC profile.",
                element_id=element.id,
            )

        if not element.material_name:
            member_warnings.append("Material name missing.")
            _append_warning(
                warnings,
                code="W-IFC-006",
                severity="WARNING",
                message="Imported member is missing material data.",
                element_id=element.id,
            )
        elif not _is_supported_material_name(element.material_name):
            member_warnings.append("Material name is not mapped to a supported steel grade.")
            _append_warning(
                warnings,
                code="W-IFC-007",
                severity="WARNING",
                message="Imported member material is not mapped to a supported SFSC steel grade.",
                element_id=element.id,
            )

        if element.orientation_deg is not None and (element.orientation_deg % 180.0) not in (
            0.0,
            90.0,
        ):
            member_warnings.append(
                "Profile orientation is not one of the supported 0/90 degree cases."
            )
            _append_warning(
                warnings,
                code="W-IFC-008",
                severity="WARNING",
                message="Imported member orientation is outside the supported 0/90 degree cases.",
                element_id=element.id,
            )

        start_node_id = node_id_for(element.start)
        end_node_id = node_id_for(element.end)
        adjacency[start_node_id].add(end_node_id)
        adjacency[end_node_id].add(start_node_id)
        accepted_member_count += 1

        members.append(
            ImportedMemberReview(
                id=element.id,
                classification=element.classification,
                accepted=True,
                start_node_id=start_node_id,
                end_node_id=end_node_id,
                section_name=element.section_name,
                material_name=element.material_name,
                orientation_deg=element.orientation_deg,
                warnings=member_warnings,
            )
        )

        if element.start_support_condition:
            support_key = (start_node_id, element.start_support_condition, element.id)
            if support_key not in support_keys:
                support_keys.add(support_key)
                supports.append(
                    ImportedSupportReview(
                        node_id=start_node_id,
                        support_condition=element.start_support_condition,
                        source_element_id=element.id,
                    )
                )
        if element.end_support_condition:
            support_key = (end_node_id, element.end_support_condition, element.id)
            if support_key not in support_keys:
                support_keys.add(support_key)
                supports.append(
                    ImportedSupportReview(
                        node_id=end_node_id,
                        support_condition=element.end_support_condition,
                        source_element_id=element.id,
                    )
                )

    for node in nodes:
        node.merged_duplicate_count = merged_counts.get(node.id, 0)

    if accepted_member_count > 0 and not supports:
        _append_warning(
            warnings,
            code="W-IFC-009",
            severity="WARNING",
            message="Imported model has no explicit support conditions; supports must not be guessed.",
        )

    if accepted_member_count > 0:
        visited: set[str] = set()
        components = 0
        for node_id in adjacency:
            if node_id in visited:
                continue
            components += 1
            queue: deque[str] = deque([node_id])
            visited.add(node_id)
            while queue:
                current = queue.popleft()
                for next_node in adjacency[current]:
                    if next_node not in visited:
                        visited.add(next_node)
                        queue.append(next_node)
        if components > 1:
            _append_warning(
                warnings,
                code="W-IFC-010",
                severity="WARNING",
                message="Imported structural members form disconnected groups and require review.",
            )

    requires_engineer_review = (
        accepted_member_count == 0
        or rejected_element_count > 0
        or any(item.severity in {"WARNING", "CRITICAL"} for item in warnings)
    )

    assumptions = [
        "Imported BIM/IFC geometry is treated as assisted input only and requires user review.",
    ]
    if supports:
        assumptions.append(
            "Support conditions were imported only where explicitly present in the source data."
        )

    return ImportedModelReview(
        source=payload.source,
        imported_elements_count=len(payload.elements),
        accepted_members_count=accepted_member_count,
        rejected_elements_count=rejected_element_count,
        non_structural_elements_count=non_structural_count,
        warnings=warnings,
        nodes=nodes,
        members=members,
        supports=supports,
        confirmed=confirmed,
        confirmed_by=confirmed_by,
        confirmation_notes=confirmation_notes,
        requires_engineer_review=requires_engineer_review,
        assumptions=assumptions,
    )
