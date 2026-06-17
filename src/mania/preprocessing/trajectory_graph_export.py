"""In-memory graph export mapping for preprocessing contacts results."""

from __future__ import annotations

import math
from dataclasses import dataclass

from mania.preprocessing.trajectory_contacts import (
    PreprocessingConditionContactsResult,
    PreprocessingContactFrameResult,
    PreprocessingContactPairResult,
    PreprocessingManifestContactsResult,
)

_NODE_KIND = "residue"
_EDGE_KIND = "residue_contact"
_SOURCE = "preprocessing_contacts"
_ID_SEPARATOR = "|"
_ID_ESCAPE = "\\"


@dataclass(frozen=True)
class PreprocessingGraphNodeMappingRecord:
    """One graph-ready preprocessing residue node mapping record."""

    node_id: str
    condition_name: str
    residue_index: int
    residue_id: str
    resname: str
    segid: str | None = None
    node_kind: str = _NODE_KIND
    source: str = _SOURCE

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "node_id",
            _non_empty_string(self.node_id, "node_id"),
        )
        object.__setattr__(
            self,
            "condition_name",
            _non_empty_string(self.condition_name, "condition_name"),
        )
        _require_non_negative_int(self.residue_index, "residue_index")
        object.__setattr__(
            self,
            "residue_id",
            _non_empty_string(self.residue_id, "residue_id"),
        )
        object.__setattr__(
            self,
            "resname",
            _non_empty_string(self.resname, "resname"),
        )
        _require_optional_string(self.segid, "segid")
        object.__setattr__(
            self,
            "node_kind",
            _non_empty_string(self.node_kind, "node_kind"),
        )
        object.__setattr__(
            self,
            "source",
            _non_empty_string(self.source, "source"),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe mapping dictionary."""
        return {
            "node_id": self.node_id,
            "condition_name": self.condition_name,
            "residue_index": self.residue_index,
            "residue_id": self.residue_id,
            "resname": self.resname,
            "segid": self.segid,
            "node_kind": self.node_kind,
            "source": self.source,
        }


@dataclass(frozen=True)
class PreprocessingGraphEdgeMappingRecord:
    """One graph-ready preprocessing aggregate contact edge mapping record."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    condition_name: str
    edge_kind: str = _EDGE_KIND
    source: str = _SOURCE
    contact_frame_count: int | None = None
    total_frame_count: int | None = None
    contact_frequency: float | None = None
    minimum_distance: float | None = None
    mean_minimum_distance: float | None = None
    distance_unit: str | None = None
    atom_filter: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "edge_id",
            _non_empty_string(self.edge_id, "edge_id"),
        )
        object.__setattr__(
            self,
            "source_node_id",
            _non_empty_string(self.source_node_id, "source_node_id"),
        )
        object.__setattr__(
            self,
            "target_node_id",
            _non_empty_string(self.target_node_id, "target_node_id"),
        )
        if self.source_node_id == self.target_node_id:
            raise ValueError("source_node_id and target_node_id must differ")
        object.__setattr__(
            self,
            "condition_name",
            _non_empty_string(self.condition_name, "condition_name"),
        )
        object.__setattr__(
            self,
            "edge_kind",
            _non_empty_string(self.edge_kind, "edge_kind"),
        )
        object.__setattr__(
            self,
            "source",
            _non_empty_string(self.source, "source"),
        )
        _require_optional_non_negative_int(
            self.contact_frame_count,
            "contact_frame_count",
        )
        _require_optional_non_negative_int(
            self.total_frame_count,
            "total_frame_count",
        )
        if (
            self.contact_frame_count is not None
            and self.total_frame_count is not None
            and self.contact_frame_count > self.total_frame_count
        ):
            raise ValueError(
                "contact_frame_count must not exceed total_frame_count"
            )
        _require_optional_non_negative_finite_number(
            self.contact_frequency,
            "contact_frequency",
        )
        _require_optional_non_negative_finite_number(
            self.minimum_distance,
            "minimum_distance",
        )
        _require_optional_non_negative_finite_number(
            self.mean_minimum_distance,
            "mean_minimum_distance",
        )
        _require_optional_string(self.distance_unit, "distance_unit")
        _require_optional_string(self.atom_filter, "atom_filter")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe mapping dictionary."""
        return {
            "edge_id": self.edge_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "condition_name": self.condition_name,
            "edge_kind": self.edge_kind,
            "source": self.source,
            "contact_frame_count": self.contact_frame_count,
            "total_frame_count": self.total_frame_count,
            "contact_frequency": self.contact_frequency,
            "minimum_distance": self.minimum_distance,
            "mean_minimum_distance": self.mean_minimum_distance,
            "distance_unit": self.distance_unit,
            "atom_filter": self.atom_filter,
        }


@dataclass(frozen=True)
class PreprocessingGraphExportMappingIssue:
    """One deterministic graph export mapping issue."""

    kind: str
    message: str
    record_id: str | None = None
    field: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "kind",
            _non_empty_string(self.kind, "kind"),
        )
        object.__setattr__(
            self,
            "message",
            _non_empty_string(self.message, "message"),
        )
        object.__setattr__(
            self,
            "record_id",
            _optional_non_empty_string(self.record_id, "record_id"),
        )
        object.__setattr__(
            self,
            "field",
            _optional_non_empty_string(self.field, "field"),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe issue dictionary."""
        return {
            "kind": self.kind,
            "message": self.message,
            "record_id": self.record_id,
            "field": self.field,
        }


@dataclass(frozen=True)
class PreprocessingGraphExportMappingResult:
    """In-memory graph export mapping result for preprocessing contacts."""

    nodes: tuple[PreprocessingGraphNodeMappingRecord, ...]
    edges: tuple[PreprocessingGraphEdgeMappingRecord, ...]
    issues: tuple[PreprocessingGraphExportMappingIssue, ...] = ()

    def __post_init__(self) -> None:
        nodes = tuple(self.nodes)
        edges = tuple(self.edges)
        issues = tuple(self.issues)

        for node in nodes:
            if not isinstance(node, PreprocessingGraphNodeMappingRecord):
                raise ValueError(
                    "nodes must contain PreprocessingGraphNodeMappingRecord"
                )
        for edge in edges:
            if not isinstance(edge, PreprocessingGraphEdgeMappingRecord):
                raise ValueError(
                    "edges must contain PreprocessingGraphEdgeMappingRecord"
                )
        for issue in issues:
            if not isinstance(issue, PreprocessingGraphExportMappingIssue):
                raise ValueError(
                    "issues must contain PreprocessingGraphExportMappingIssue"
                )

        duplicate_node_ids = _duplicates(tuple(node.node_id for node in nodes))
        if duplicate_node_ids:
            raise ValueError(
                "Duplicate node IDs: " + ", ".join(duplicate_node_ids)
            )
        duplicate_edge_ids = _duplicates(tuple(edge.edge_id for edge in edges))
        if duplicate_edge_ids:
            raise ValueError(
                "Duplicate edge IDs: " + ", ".join(duplicate_edge_ids)
            )

        node_ids = {node.node_id for node in nodes}
        for edge in edges:
            if edge.source_node_id not in node_ids:
                raise ValueError(
                    "Edge endpoint is missing from nodes: "
                    f"{edge.source_node_id}"
                )
            if edge.target_node_id not in node_ids:
                raise ValueError(
                    "Edge endpoint is missing from nodes: "
                    f"{edge.target_node_id}"
                )

        object.__setattr__(
            self,
            "nodes",
            tuple(sorted(nodes, key=lambda node: node.node_id)),
        )
        object.__setattr__(
            self,
            "edges",
            tuple(sorted(edges, key=lambda edge: edge.edge_id)),
        )
        object.__setattr__(
            self,
            "issues",
            tuple(
                sorted(
                    issues,
                    key=lambda issue: (
                        issue.kind,
                        issue.record_id or "",
                        issue.field or "",
                        issue.message,
                    ),
                )
            ),
        )

    @property
    def passed(self) -> bool:
        """Return whether the mapping has no issues."""
        return self.issues == ()

    @property
    def node_count(self) -> int:
        """Return the number of mapped nodes."""
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        """Return the number of mapped edges."""
        return len(self.edges)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe mapping result dictionary."""
        return {
            "passed": self.passed,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class _ResidueIdentity:
    condition_name: str
    residue_index: int
    residue_id: str
    resname: str
    segid: str | None


@dataclass(frozen=True)
class _AggregateKey:
    condition_name: str
    source_node_id: str
    target_node_id: str
    distance_unit: str
    atom_filter: str


def build_preprocessing_graph_export_mapping(
    contacts_result: object,
) -> PreprocessingGraphExportMappingResult:
    """Map accepted contacts results to in-memory graph-ready records."""
    try:
        condition_results, input_issues = _condition_results(contacts_result)
        if input_issues:
            return PreprocessingGraphExportMappingResult(
                nodes=(),
                edges=(),
                issues=input_issues,
            )

        nodes_by_id: dict[str, PreprocessingGraphNodeMappingRecord] = {}
        edge_records: list[PreprocessingGraphEdgeMappingRecord] = []
        issues: list[PreprocessingGraphExportMappingIssue] = []

        for condition_index, condition_result in enumerate(condition_results):
            condition_edges, condition_issues = _map_condition_result(
                condition_result,
                condition_index=condition_index,
                nodes_by_id=nodes_by_id,
            )
            edge_records.extend(condition_edges)
            issues.extend(condition_issues)

        if not nodes_by_id and not edge_records and not issues:
            issues.append(
                PreprocessingGraphExportMappingIssue(
                    kind="empty_contacts_result",
                    field="contacts_result",
                    message="Contacts result contains no graph-mappable contacts.",
                )
            )

        return PreprocessingGraphExportMappingResult(
            nodes=tuple(nodes_by_id.values()),
            edges=tuple(edge_records),
            issues=tuple(issues),
        )
    except ValueError as exc:
        return PreprocessingGraphExportMappingResult(
            nodes=(),
            edges=(),
            issues=(
                PreprocessingGraphExportMappingIssue(
                    kind="mapping_failed",
                    field="contacts_result",
                    message=f"Graph export mapping failed: {exc}",
                ),
            ),
        )


def _condition_results(
    contacts_result: object,
) -> tuple[
    tuple[PreprocessingConditionContactsResult, ...],
    tuple[PreprocessingGraphExportMappingIssue, ...],
]:
    if isinstance(contacts_result, PreprocessingManifestContactsResult):
        issues = tuple(
            PreprocessingGraphExportMappingIssue(
                kind="mapping_failed",
                field=f"contacts_result.issues[{index}]",
                message=issue.message,
            )
            for index, issue in enumerate(contacts_result.issues)
        )
        if not contacts_result.condition_results:
            issues = (
                *issues,
                PreprocessingGraphExportMappingIssue(
                    kind="empty_contacts_result",
                    field="contacts_result.condition_results",
                    message="Manifest contacts result contains no conditions.",
                ),
            )
        return contacts_result.condition_results, issues
    if isinstance(contacts_result, PreprocessingConditionContactsResult):
        return (contacts_result,), ()
    return (), (
        PreprocessingGraphExportMappingIssue(
            kind="unsupported_input_type",
            field="contacts_result",
            message=(
                "Contacts result must be a condition or manifest contacts "
                "result."
            ),
        ),
    )


def _map_condition_result(
    condition_result: PreprocessingConditionContactsResult,
    *,
    condition_index: int,
    nodes_by_id: dict[str, PreprocessingGraphNodeMappingRecord],
) -> tuple[
    tuple[PreprocessingGraphEdgeMappingRecord, ...],
    tuple[PreprocessingGraphExportMappingIssue, ...],
]:
    issues: list[PreprocessingGraphExportMappingIssue] = []
    if not condition_result.passed:
        issues.append(
            PreprocessingGraphExportMappingIssue(
                kind="mapping_failed",
                record_id=condition_result.condition_name,
                field=f"condition_results[{condition_index}]",
                message="Condition contacts result did not pass.",
            )
        )

    included_frame_count = 0
    aggregate_distances: dict[_AggregateKey, list[float]] = {}

    for frame_index, frame_result in enumerate(condition_result.frame_results):
        if not frame_result.passed:
            issues.append(
                PreprocessingGraphExportMappingIssue(
                    kind="mapping_failed",
                    record_id=condition_result.condition_name,
                    field=(
                        f"condition_results[{condition_index}]"
                        f".frame_results[{frame_index}]"
                    ),
                    message="Frame contacts result did not pass.",
                )
            )
            continue

        included_frame_count += 1
        frame_distances = _frame_distances(
            frame_result,
            condition_index=condition_index,
            frame_index=frame_index,
            nodes_by_id=nodes_by_id,
            issues=issues,
        )
        for key, distance in frame_distances.items():
            aggregate_distances.setdefault(key, []).append(distance)

    if included_frame_count == 0 or not aggregate_distances:
        issues.append(
            PreprocessingGraphExportMappingIssue(
                kind="empty_contacts_result",
                record_id=condition_result.condition_name,
                field=f"condition_results[{condition_index}]",
                message=(
                    "Condition contacts result contains no graph-mappable "
                    "passed-frame contacts."
                ),
            )
        )

    edges = tuple(
        _edge_record(key, distances, included_frame_count)
        for key, distances in sorted(
            aggregate_distances.items(),
            key=lambda item: _edge_id(item[0]),
        )
    )
    return edges, tuple(issues)


def _frame_distances(
    frame_result: PreprocessingContactFrameResult,
    *,
    condition_index: int,
    frame_index: int,
    nodes_by_id: dict[str, PreprocessingGraphNodeMappingRecord],
    issues: list[PreprocessingGraphExportMappingIssue],
) -> dict[_AggregateKey, float]:
    frame_distances: dict[_AggregateKey, float] = {}

    for contact in frame_result.contacts:
        source_identity = _source_identity(frame_result, contact)
        target_identity = _target_identity(frame_result, contact)
        source_node = _node_record(source_identity)
        target_node = _node_record(target_identity)
        nodes_by_id.setdefault(source_node.node_id, source_node)
        nodes_by_id.setdefault(target_node.node_id, target_node)

        key = _AggregateKey(
            condition_name=frame_result.condition_name,
            source_node_id=source_node.node_id,
            target_node_id=target_node.node_id,
            distance_unit=contact.distance_unit,
            atom_filter=contact.atom_filter,
        )
        previous_distance = frame_distances.get(key)
        if previous_distance is None:
            frame_distances[key] = contact.minimum_distance
            continue

        issues.append(
            PreprocessingGraphExportMappingIssue(
                kind="mapping_failed",
                record_id=frame_result.condition_name,
                field=(
                    f"condition_results[{condition_index}]"
                    f".frame_results[{frame_index}]"
                ),
                message="Duplicate contact pair was present in one frame.",
            )
        )
        frame_distances[key] = min(previous_distance, contact.minimum_distance)

    return frame_distances


def _source_identity(
    frame_result: PreprocessingContactFrameResult,
    contact: PreprocessingContactPairResult,
) -> _ResidueIdentity:
    return _ResidueIdentity(
        condition_name=frame_result.condition_name,
        residue_index=contact.source_residue_index,
        residue_id=_residue_id(contact.source_residue_id, contact.source_residue_index),
        resname=contact.source_resname,
        segid=contact.source_segid,
    )


def _target_identity(
    frame_result: PreprocessingContactFrameResult,
    contact: PreprocessingContactPairResult,
) -> _ResidueIdentity:
    return _ResidueIdentity(
        condition_name=frame_result.condition_name,
        residue_index=contact.target_residue_index,
        residue_id=_residue_id(contact.target_residue_id, contact.target_residue_index),
        resname=contact.target_resname,
        segid=contact.target_segid,
    )


def _node_record(identity: _ResidueIdentity) -> PreprocessingGraphNodeMappingRecord:
    return PreprocessingGraphNodeMappingRecord(
        node_id=_node_id(identity),
        condition_name=identity.condition_name,
        residue_index=identity.residue_index,
        residue_id=identity.residue_id,
        resname=identity.resname,
        segid=identity.segid,
    )


def _edge_record(
    key: _AggregateKey,
    distances: list[float],
    total_frame_count: int,
) -> PreprocessingGraphEdgeMappingRecord:
    contact_frame_count = len(distances)
    minimum_distance = min(distances)
    mean_minimum_distance = sum(distances) / contact_frame_count
    return PreprocessingGraphEdgeMappingRecord(
        edge_id=_edge_id(key),
        source_node_id=key.source_node_id,
        target_node_id=key.target_node_id,
        condition_name=key.condition_name,
        contact_frame_count=contact_frame_count,
        total_frame_count=total_frame_count,
        contact_frequency=contact_frame_count / total_frame_count,
        minimum_distance=minimum_distance,
        mean_minimum_distance=mean_minimum_distance,
        distance_unit=key.distance_unit,
        atom_filter=key.atom_filter,
    )


def _node_id(identity: _ResidueIdentity) -> str:
    return _join_identifier_parts(
        (
            identity.condition_name,
            identity.segid,
            identity.residue_index,
            identity.residue_id,
            identity.resname,
        )
    )


def _edge_id(key: _AggregateKey) -> str:
    return _join_identifier_parts(
        (
            key.condition_name,
            key.source_node_id,
            key.target_node_id,
            key.distance_unit,
            key.atom_filter,
        )
    )


def _join_identifier_parts(parts: tuple[object | None, ...]) -> str:
    return _ID_SEPARATOR.join(_identifier_part(part) for part in parts)


def _identifier_part(value: object | None) -> str:
    text = "" if value is None else str(value)
    return text.replace(_ID_ESCAPE, _ID_ESCAPE + _ID_ESCAPE).replace(
        _ID_SEPARATOR,
        _ID_ESCAPE + _ID_SEPARATOR,
    )


def _residue_id(value: int | str | None, residue_index: int) -> str:
    return str(residue_index if value is None else value)


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a non-empty string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must be a non-empty string")
    return stripped


def _optional_non_empty_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _non_empty_string(value, field_name)


def _require_optional_string(value: object, field_name: str) -> None:
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or None")


def _require_non_negative_int(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative int")


def _require_optional_non_negative_int(
    value: object,
    field_name: str,
) -> None:
    if value is not None:
        _require_non_negative_int(value, field_name)


def _require_optional_non_negative_finite_number(
    value: object,
    field_name: str,
) -> None:
    if value is None:
        return
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(
            f"{field_name} must be a finite non-negative number"
        )


def _duplicates(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    duplicate_set: set[str] = set()
    for value in values:
        if value in seen and value not in duplicate_set:
            duplicates.append(value)
            duplicate_set.add(value)
        seen.add(value)
    return tuple(sorted(duplicates))


__all__ = [
    "PreprocessingGraphEdgeMappingRecord",
    "PreprocessingGraphExportMappingIssue",
    "PreprocessingGraphExportMappingResult",
    "PreprocessingGraphNodeMappingRecord",
    "build_preprocessing_graph_export_mapping",
]
