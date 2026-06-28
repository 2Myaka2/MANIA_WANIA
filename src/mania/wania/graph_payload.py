"""WANIA object JSON payload adapter for Stage 15 graph artifacts."""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import TypeAlias

WANIA_GRAPH_SCHEMA_VERSION = "wania_graph.v0.1"
_RESIDUE_CONTACT = "residue_contact"

JsonValue: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
    | list["JsonValue"]
    | dict[str, "JsonValue"]
)


@dataclass(frozen=True)
class WaniaGraphPayloadRunMetadata:
    """Explicit protein/run metadata for one WANIA graph payload."""

    protein_id: str | None
    protein_name: str | None
    run_name: str | None
    condition_names: Sequence[str] | None
    job_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "condition_names",
            _condition_tuple(self.condition_names),
        )


@dataclass(frozen=True)
class WaniaGraphPayloadArtifactPaths:
    """Stage 15 artifact paths referenced or consumed by the adapter."""

    graph_json_path: str | Path | None
    nodes_csv_path: str | Path | None = None
    edges_csv_path: str | Path | None = None
    diagnostics_report_json_path: str | Path | None = None
    rg_timeseries_csv_path: str | Path | None = None
    contact_edges_csv_path: str | Path | None = None
    contacts_perframe_csv_path: str | Path | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "graph_json_path",
            "nodes_csv_path",
            "edges_csv_path",
            "diagnostics_report_json_path",
            "rg_timeseries_csv_path",
            "contact_edges_csv_path",
            "contacts_perframe_csv_path",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_path(getattr(self, field_name)),
            )


@dataclass(frozen=True)
class WaniaGraphPayloadIssue:
    """One deterministic, JSON-safe WANIA graph payload adapter issue."""

    kind: str
    message: str
    fatal: bool = False
    field: str | None = None
    path: str | None = None
    condition: str | None = None
    record_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _required_string(self.kind, "kind"))
        object.__setattr__(
            self,
            "message",
            _required_string(self.message, "message"),
        )
        if not isinstance(self.fatal, bool):
            raise ValueError("fatal must be bool")
        for field_name in ("field", "path", "condition", "record_id"):
            object.__setattr__(
                self,
                field_name,
                _optional_string(getattr(self, field_name), field_name),
            )

    def to_dict(self) -> dict[str, JsonValue]:
        """Return a JSON-safe issue dictionary."""
        return {
            "kind": self.kind,
            "message": self.message,
            "fatal": self.fatal,
            "field": self.field,
            "path": self.path,
            "condition": self.condition,
            "record_id": self.record_id,
        }


@dataclass(frozen=True)
class WaniaGraphPayloadBuildResult:
    """Result of building one WANIA graph payload."""

    payload: dict[str, JsonValue]
    issues: tuple[WaniaGraphPayloadIssue, ...]
    node_count: int
    edge_count: int
    condition_names: tuple[str, ...]
    capabilities: Mapping[str, bool]

    def __post_init__(self) -> None:
        _require_non_negative_int(self.node_count, "node_count")
        _require_non_negative_int(self.edge_count, "edge_count")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be a dictionary")
        if not isinstance(self.issues, tuple):
            raise ValueError("issues must be a tuple of WaniaGraphPayloadIssue")
        for issue in self.issues:
            if not isinstance(issue, WaniaGraphPayloadIssue):
                raise ValueError("issues must contain WaniaGraphPayloadIssue")
        object.__setattr__(self, "condition_names", tuple(self.condition_names))
        object.__setattr__(self, "capabilities", dict(self.capabilities))

    @property
    def passed(self) -> bool:
        """Return whether the payload build had no fatal issues."""
        return not any(issue.fatal for issue in self.issues)

    @property
    def issue_count(self) -> int:
        """Return the number of build issues, including non-fatal warnings."""
        return len(self.issues)

    def to_dict(self) -> dict[str, JsonValue]:
        """Return a JSON-safe build result dictionary."""
        return {
            "passed": self.passed,
            "payload": self.payload,
            "issue_count": self.issue_count,
            "issues": [issue.to_dict() for issue in self.issues],
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "condition_names": list(self.condition_names),
            "capabilities": dict(self.capabilities),
        }


@dataclass(frozen=True)
class WaniaGraphPayloadWriteResult:
    """Result of writing one WANIA graph payload JSON file."""

    output_path: Path
    issues: tuple[WaniaGraphPayloadIssue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "output_path", Path(self.output_path))
        if not isinstance(self.issues, tuple):
            raise ValueError("issues must be a tuple of WaniaGraphPayloadIssue")
        for issue in self.issues:
            if not isinstance(issue, WaniaGraphPayloadIssue):
                raise ValueError("issues must contain WaniaGraphPayloadIssue")

    @property
    def passed(self) -> bool:
        """Return whether the write completed without issues."""
        return self.issues == ()

    @property
    def issue_count(self) -> int:
        """Return the number of write issues."""
        return len(self.issues)

    def to_dict(self) -> dict[str, JsonValue]:
        """Return a JSON-safe write result dictionary."""
        return {
            "output_path": str(self.output_path),
            "passed": self.passed,
            "issue_count": self.issue_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def build_wania_graph_payload_from_artifacts(
    *,
    run_metadata: WaniaGraphPayloadRunMetadata,
    artifact_paths: WaniaGraphPayloadArtifactPaths,
    output_root: str | Path,
) -> WaniaGraphPayloadBuildResult:
    """Build a WANIA object JSON payload from existing Stage 15 artifacts."""
    issues: list[WaniaGraphPayloadIssue] = []
    metadata_issues = _run_metadata_issues(run_metadata)
    issues.extend(metadata_issues)
    condition_names = _condition_tuple(run_metadata.condition_names)
    capabilities = _capabilities(artifact_paths)

    graph_path = _optional_path(artifact_paths.graph_json_path)
    if graph_path is None:
        issues.append(
            WaniaGraphPayloadIssue(
                kind="graph_json_missing",
                message="graph_json_path is required.",
                fatal=True,
                field="artifact_paths.graph_json_path",
            )
        )
        return _build_result(
            payload={},
            issues=issues,
            node_count=0,
            edge_count=0,
            condition_names=condition_names,
            capabilities=capabilities,
        )
    if not graph_path.is_file():
        issues.append(
            WaniaGraphPayloadIssue(
                kind="graph_json_missing",
                message="Backend graph JSON artifact is missing.",
                fatal=True,
                field="artifact_paths.graph_json_path",
                path=str(graph_path),
            )
        )
        return _build_result(
            payload={},
            issues=issues,
            node_count=0,
            edge_count=0,
            condition_names=condition_names,
            capabilities=capabilities,
        )

    graph = _read_graph_json(graph_path, issues)
    if graph is None:
        return _build_result(
            payload={},
            issues=issues,
            node_count=0,
            edge_count=0,
            condition_names=condition_names,
            capabilities=capabilities,
        )

    nodes_value = graph.get("nodes")
    edges_value = graph.get("edges")
    if not isinstance(nodes_value, list):
        issues.append(
            WaniaGraphPayloadIssue(
                kind="graph_json_invalid",
                message="Backend graph JSON must contain a nodes array.",
                fatal=True,
                field="nodes",
                path=str(graph_path),
            )
        )
    if not isinstance(edges_value, list):
        issues.append(
            WaniaGraphPayloadIssue(
                kind="graph_json_invalid",
                message="Backend graph JSON must contain an edges array.",
                fatal=True,
                field="edges",
                path=str(graph_path),
            )
        )
    if (
        any(issue.fatal for issue in issues)
        or not isinstance(nodes_value, list)
        or not isinstance(edges_value, list)
    ):
        return _build_result(
            payload={},
            issues=issues,
            node_count=0,
            edge_count=0,
            condition_names=condition_names,
            capabilities=capabilities,
        )

    nodes, node_conditions = _map_nodes(nodes_value, issues)
    edges, edge_conditions = _map_edges(edges_value, issues)
    graph_conditions = tuple(sorted(set(node_conditions) | set(edge_conditions)))
    _append_condition_issues(
        issues,
        metadata_conditions=condition_names,
        graph_conditions=graph_conditions,
    )

    diagnostics = _diagnostics_payload(
        _optional_path(artifact_paths.diagnostics_report_json_path),
        output_root=output_root,
        issues=issues,
    )

    if any(issue.fatal for issue in issues):
        return _build_result(
            payload={},
            issues=issues,
            node_count=len(nodes),
            edge_count=len(edges),
            condition_names=condition_names,
            capabilities=capabilities,
        )

    capabilities_payload: dict[str, JsonValue] = {
        key: value for key, value in capabilities.items()
    }
    payload: dict[str, JsonValue] = {
        "schema_version": WANIA_GRAPH_SCHEMA_VERSION,
        "run": _run_payload(run_metadata, condition_names),
        "capabilities": capabilities_payload,
        "graph": {
            "directed": graph.get("directed") is True,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "conditions": [
                {"id": condition, "label": condition}
                for condition in condition_names
            ],
            "components": [],
            "nodes": nodes,
            "edges": edges,
        },
        "temporal": {
            "available": False,
            "windows": [],
        },
        "artifacts": _artifacts_payload(artifact_paths, output_root),
        "diagnostics": diagnostics,
    }

    return _build_result(
        payload=payload,
        issues=issues,
        node_count=len(nodes),
        edge_count=len(edges),
        condition_names=condition_names,
        capabilities=capabilities,
    )


def write_wania_graph_payload_json(
    payload: Mapping[str, object],
    output_path: str | Path,
    *,
    overwrite: bool = True,
) -> WaniaGraphPayloadWriteResult:
    """Write a WANIA graph payload as deterministic UTF-8 JSON."""
    path = Path(output_path)
    if path.exists() and path.is_dir():
        return WaniaGraphPayloadWriteResult(
            output_path=path,
            issues=(
                WaniaGraphPayloadIssue(
                    kind="write_failed",
                    message="Output path is a directory.",
                    fatal=True,
                    field="output_path",
                    path=str(path),
                ),
            ),
        )
    if path.exists() and not overwrite:
        return WaniaGraphPayloadWriteResult(
            output_path=path,
            issues=(
                WaniaGraphPayloadIssue(
                    kind="write_failed",
                    message="Output path exists and overwrite is false.",
                    fatal=True,
                    field="output_path",
                    path=str(path),
                ),
            ),
        )

    temporary_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as payload_file:
            temporary_path = Path(payload_file.name)
            json.dump(
                payload,
                payload_file,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            payload_file.write("\n")
        temporary_path.replace(path)
    except (OSError, TypeError, ValueError) as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        return WaniaGraphPayloadWriteResult(
            output_path=path,
            issues=(
                WaniaGraphPayloadIssue(
                    kind="write_failed",
                    message=f"WANIA graph payload JSON could not be written: {exc}",
                    fatal=True,
                    field="output_path",
                    path=str(path),
                ),
            ),
        )
    return WaniaGraphPayloadWriteResult(output_path=path)


def _build_result(
    *,
    payload: dict[str, JsonValue],
    issues: list[WaniaGraphPayloadIssue],
    node_count: int,
    edge_count: int,
    condition_names: tuple[str, ...],
    capabilities: Mapping[str, bool],
) -> WaniaGraphPayloadBuildResult:
    return WaniaGraphPayloadBuildResult(
        payload=payload,
        issues=tuple(
            sorted(
                issues,
                key=lambda issue: (
                    issue.kind,
                    issue.field or "",
                    issue.condition or "",
                    issue.record_id or "",
                    issue.path or "",
                    issue.message,
                    issue.fatal,
                ),
            )
        ),
        node_count=node_count,
        edge_count=edge_count,
        condition_names=condition_names,
        capabilities=capabilities,
    )


def _run_metadata_issues(
    run_metadata: WaniaGraphPayloadRunMetadata,
) -> tuple[WaniaGraphPayloadIssue, ...]:
    issues: list[WaniaGraphPayloadIssue] = []
    for field_name in ("protein_id", "protein_name", "run_name"):
        if not _non_empty_string_or_none(getattr(run_metadata, field_name)):
            issues.append(
                WaniaGraphPayloadIssue(
                    kind="run_metadata_missing",
                    message=f"run_metadata.{field_name} is required.",
                    fatal=True,
                    field=f"run_metadata.{field_name}",
                )
            )
    if _condition_tuple(run_metadata.condition_names) == ():
        issues.append(
            WaniaGraphPayloadIssue(
                kind="run_metadata_missing",
                message="run_metadata.condition_names must be non-empty.",
                fatal=True,
                field="run_metadata.condition_names",
            )
        )
    return tuple(issues)


def _condition_tuple(conditions: Sequence[str] | None) -> tuple[str, ...]:
    if conditions is None:
        return ()
    values: tuple[str, ...]
    if isinstance(conditions, str):
        values = (conditions,)
    else:
        values = tuple(conditions)
    return tuple(
        value.strip()
        for value in values
        if isinstance(value, str) and value.strip() != ""
    )


def _optional_path(value: object) -> Path | None:
    if value is None:
        return None
    if isinstance(value, Path):
        path = value
    elif isinstance(value, str):
        path = Path(value)
    else:
        raise ValueError("path values must be strings, Paths, or None")
    if str(path).strip() == "":
        return None
    return path


def _read_graph_json(
    path: Path,
    issues: list[WaniaGraphPayloadIssue],
) -> dict[str, object] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError:
        issues.append(
            WaniaGraphPayloadIssue(
                kind="graph_json_invalid",
                message="Backend graph JSON could not be parsed.",
                fatal=True,
                field="artifact_paths.graph_json_path",
                path=str(path),
            )
        )
        return None
    except (OSError, UnicodeError):
        issues.append(
            WaniaGraphPayloadIssue(
                kind="graph_json_invalid",
                message="Backend graph JSON could not be read.",
                fatal=True,
                field="artifact_paths.graph_json_path",
                path=str(path),
            )
        )
        return None
    if not isinstance(raw, dict):
        issues.append(
            WaniaGraphPayloadIssue(
                kind="graph_json_invalid",
                message="Backend graph JSON top-level value must be an object.",
                fatal=True,
                field="artifact_paths.graph_json_path",
                path=str(path),
            )
        )
        return None
    return raw


def _map_nodes(
    nodes_value: list[object],
    issues: list[WaniaGraphPayloadIssue],
) -> tuple[list[JsonValue], tuple[str, ...]]:
    nodes: list[JsonValue] = []
    conditions: list[str] = []
    for index, raw_node in enumerate(nodes_value):
        if not isinstance(raw_node, dict):
            issues.append(
                WaniaGraphPayloadIssue(
                    kind="node_mapping_failed",
                    message="Backend graph node entry must be an object.",
                    fatal=True,
                    field=f"nodes[{index}]",
                )
            )
            continue
        node = _string_key_mapping(raw_node)
        node_id = _first_non_empty(
            _value_string(node.get("id")),
            _value_string(node.get("resid")),
        )
        condition = _value_string(node.get("condition"))
        if node_id is None:
            issues.append(
                WaniaGraphPayloadIssue(
                    kind="node_mapping_failed",
                    message="Backend graph node is missing id and resid.",
                    fatal=True,
                    field=f"nodes[{index}].id",
                )
            )
            continue
        if condition is None:
            issues.append(
                WaniaGraphPayloadIssue(
                    kind="node_mapping_failed",
                    message="Backend graph node is missing condition.",
                    fatal=True,
                    field=f"nodes[{index}].condition",
                    record_id=node_id,
                )
            )
            continue
        parsed = _parse_backend_node_id(node_id)
        residue_id = _first_non_empty(
            _value_string(node.get("residue_id")),
            parsed.residue_id,
            _value_string(node.get("resid")),
        )
        residue_index = _first_int(
            _value_string(node.get("residue_index")),
            parsed.residue_index,
            residue_id,
        )
        residue_name = _first_non_empty(
            _value_string(node.get("resname")),
            parsed.residue_name,
        )
        chain_id = _first_non_empty(
            _value_string(node.get("chain_id")),
            _value_string(node.get("segid")),
            parsed.chain_id,
        )
        if parsed.failed:
            issues.append(
                WaniaGraphPayloadIssue(
                    kind="node_mapping_failed",
                    message="Backend graph node id could not be fully parsed.",
                    fatal=False,
                    field=f"nodes[{index}].id",
                    record_id=node_id,
                )
            )

        field_prefix = f"nodes[{index}]"
        x = _node_coordinate(node, "x", "x_ca", issues, field_prefix)
        y = _node_coordinate(node, "y", "y_ca", issues, field_prefix)
        z = _node_coordinate(node, "z", "z_ca", issues, field_prefix)
        x_ca = _node_coordinate(node, "x_ca", "x", issues, field_prefix)
        y_ca = _node_coordinate(node, "y_ca", "y", issues, field_prefix)
        z_ca = _node_coordinate(node, "z_ca", "z", issues, field_prefix)

        nodes.append(
            {
                "id": node_id,
                "label": _node_label(node_id, residue_name, residue_id),
                "condition": condition,
                "component_id": None,
                "x": x,
                "y": y,
                "z": z,
                "x_ca": x_ca,
                "y_ca": y_ca,
                "z_ca": z_ca,
                "residue": {
                    "index": residue_index,
                    "id": residue_id,
                    "name": residue_name,
                    "chain_id": chain_id,
                },
                "metrics": {},
            }
        )
        conditions.append(condition)
    return nodes, tuple(conditions)


def _node_coordinate(
    node: Mapping[str, object],
    primary_key: str,
    fallback_key: str,
    issues: list[WaniaGraphPayloadIssue],
    field_prefix: str,
) -> float | None:
    raw_value = node.get(primary_key)
    source_key = primary_key
    if raw_value is None:
        raw_value = node.get(fallback_key)
        source_key = fallback_key
    raw = _value_string(raw_value)
    if raw is None:
        return None
    parsed = _number(raw)
    if not isinstance(parsed, float):
        issues.append(
            WaniaGraphPayloadIssue(
                kind="node_coordinates_invalid",
                message="Backend graph node coordinate could not be parsed.",
                fatal=False,
                field=f"{field_prefix}.{source_key}",
            )
        )
        return None
    return parsed


def _map_edges(
    edges_value: list[object],
    issues: list[WaniaGraphPayloadIssue],
) -> tuple[list[JsonValue], tuple[str, ...]]:
    edges: list[JsonValue] = []
    conditions: list[str] = []
    for index, raw_edge in enumerate(edges_value):
        if not isinstance(raw_edge, dict):
            issues.append(
                WaniaGraphPayloadIssue(
                    kind="edge_mapping_failed",
                    message="Backend graph edge entry must be an object.",
                    fatal=True,
                    field=f"edges[{index}]",
                )
            )
            continue
        edge = _string_key_mapping(raw_edge)
        source = _first_non_empty(
            _value_string(edge.get("source")),
            _value_string(edge.get("source_node_id")),
            _value_string(edge.get("resid_i")),
        )
        target = _first_non_empty(
            _value_string(edge.get("target")),
            _value_string(edge.get("target_node_id")),
            _value_string(edge.get("resid_j")),
        )
        condition = _value_string(edge.get("condition"))
        if source is None:
            issues.append(
                WaniaGraphPayloadIssue(
                    kind="edge_mapping_failed",
                    message="Backend graph edge is missing source.",
                    fatal=True,
                    field=f"edges[{index}].source",
                )
            )
            continue
        if target is None:
            issues.append(
                WaniaGraphPayloadIssue(
                    kind="edge_mapping_failed",
                    message="Backend graph edge is missing target.",
                    fatal=True,
                    field=f"edges[{index}].target",
                    record_id=source,
                )
            )
            continue
        if condition is None:
            issues.append(
                WaniaGraphPayloadIssue(
                    kind="edge_mapping_failed",
                    message="Backend graph edge is missing condition.",
                    fatal=True,
                    field=f"edges[{index}].condition",
                    record_id=f"{source}->{target}",
                )
            )
            continue

        primary_type = _first_non_empty(
            _value_string(edge.get("edge_type")),
            _value_string(edge.get("primary_edge_type")),
            _RESIDUE_CONTACT,
        ) or _RESIDUE_CONTACT
        all_types = _edge_types(edge.get("all_edge_types"), primary_type)
        edge_id = _first_non_empty(
            _value_string(edge.get("id")),
            _value_string(edge.get("edge_id")),
            _stable_edge_id(condition, source, target, primary_type),
        ) or _stable_edge_id(condition, source, target, primary_type)
        metrics = _edge_metrics(edge, issues, field_prefix=f"edges[{index}]")
        edges.append(
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "condition": condition,
                "source_component_id": None,
                "target_component_id": None,
                "is_inter_component": False,
                "interaction": {
                    "primary_type": primary_type,
                    "all_types": all_types,
                },
                "metrics": metrics,
            }
        )
        conditions.append(condition)
    return edges, tuple(conditions)


def _append_condition_issues(
    issues: list[WaniaGraphPayloadIssue],
    *,
    metadata_conditions: tuple[str, ...],
    graph_conditions: tuple[str, ...],
) -> None:
    metadata_set = set(metadata_conditions)
    graph_set = set(graph_conditions)
    for condition in sorted(graph_set - metadata_set):
        issues.append(
            WaniaGraphPayloadIssue(
                kind="condition_mismatch",
                message=(
                    "Backend graph condition is not listed in explicit "
                    "run metadata."
                ),
                fatal=True,
                field="condition",
                condition=condition,
            )
        )
    for condition in metadata_conditions:
        if condition not in graph_set:
            issues.append(
                WaniaGraphPayloadIssue(
                    kind="metadata_condition_absent_from_graph",
                    message=(
                        "Run metadata condition is not present in backend "
                        "graph nodes or edges."
                    ),
                    fatal=False,
                    field="run_metadata.condition_names",
                    condition=condition,
                )
            )


def _run_payload(
    run_metadata: WaniaGraphPayloadRunMetadata,
    condition_names: tuple[str, ...],
) -> dict[str, JsonValue]:
    return {
        "job_id": _value_string(run_metadata.job_id),
        "run_name": _value_string(run_metadata.run_name),
        "protein_id": _value_string(run_metadata.protein_id),
        "protein_name": _value_string(run_metadata.protein_name),
        "condition_names": list(condition_names),
    }


def _capabilities(
    artifact_paths: WaniaGraphPayloadArtifactPaths,
) -> dict[str, bool]:
    return {
        "static_contact_graph": True,
        "rg_timeseries": artifact_paths.rg_timeseries_csv_path is not None,
        "aggregate_contacts": artifact_paths.contact_edges_csv_path is not None,
        "contacts_perframe": artifact_paths.contacts_perframe_csv_path is not None,
        "typed_rin_interactions": False,
        "centrality_metrics": False,
        "community_detection": False,
        "node_structural_metrics": False,
        "conformational_states": False,
        "cross_condition_statistics": False,
        "temporal_rin": False,
        "inter_component_interactions": False,
        "cross_protein_comparison": False,
    }


def _artifacts_payload(
    artifact_paths: WaniaGraphPayloadArtifactPaths,
    output_root: str | Path,
) -> dict[str, JsonValue]:
    return {
        "backend_graph_json": _relative_artifact_path(
            _optional_path(artifact_paths.graph_json_path),
            output_root,
        ),
        "nodes_csv": _relative_artifact_path(
            _optional_path(artifact_paths.nodes_csv_path),
            output_root,
        ),
        "edges_csv": _relative_artifact_path(
            _optional_path(artifact_paths.edges_csv_path),
            output_root,
        ),
        "rg_timeseries_csv": _relative_artifact_path(
            _optional_path(artifact_paths.rg_timeseries_csv_path),
            output_root,
        ),
        "contact_edges_csv": _relative_artifact_path(
            _optional_path(artifact_paths.contact_edges_csv_path),
            output_root,
        ),
        "contacts_perframe_csv": _relative_artifact_path(
            _optional_path(artifact_paths.contacts_perframe_csv_path),
            output_root,
        ),
        "diagnostics_report_json": _relative_artifact_path(
            _optional_path(artifact_paths.diagnostics_report_json_path),
            output_root,
        ),
    }


def _diagnostics_payload(
    diagnostics_report_path: Path | None,
    *,
    output_root: str | Path,
    issues: list[WaniaGraphPayloadIssue],
) -> dict[str, JsonValue]:
    report_path = _relative_artifact_path(diagnostics_report_path, output_root)
    passed: bool | None = None
    if diagnostics_report_path is None:
        return {"passed": passed, "report_path": report_path}
    if not diagnostics_report_path.is_file():
        issues.append(
            WaniaGraphPayloadIssue(
                kind="diagnostics_report_missing",
                message="Diagnostics report JSON artifact is missing.",
                fatal=False,
                field="artifact_paths.diagnostics_report_json_path",
                path=str(diagnostics_report_path),
            )
        )
        return {"passed": passed, "report_path": report_path}
    try:
        raw = json.loads(diagnostics_report_path.read_text(encoding="utf-8"))
    except (JSONDecodeError, OSError, UnicodeError):
        issues.append(
            WaniaGraphPayloadIssue(
                kind="diagnostics_report_invalid",
                message="Diagnostics report JSON could not be parsed.",
                fatal=False,
                field="artifact_paths.diagnostics_report_json_path",
                path=str(diagnostics_report_path),
            )
        )
        return {"passed": passed, "report_path": report_path}
    if isinstance(raw, dict):
        raw_passed = raw.get("passed")
        if isinstance(raw_passed, bool):
            passed = raw_passed
        elif raw.get("status") == "passed":
            passed = True
        elif raw.get("status") == "failed":
            passed = False
    return {"passed": passed, "report_path": report_path}


@dataclass(frozen=True)
class _ParsedNodeId:
    chain_id: str | None
    residue_index: str | None
    residue_id: str | None
    residue_name: str | None
    failed: bool


def _parse_backend_node_id(node_id: str) -> _ParsedNodeId:
    parts = node_id.split("|")
    if len(parts) < 5:
        return _ParsedNodeId(
            chain_id=None,
            residue_index=None,
            residue_id=None,
            residue_name=None,
            failed=True,
        )
    return _ParsedNodeId(
        chain_id=_blank_to_none(parts[1]),
        residue_index=_blank_to_none(parts[2]),
        residue_id=_blank_to_none(parts[3]),
        residue_name=_blank_to_none(parts[4]),
        failed=False,
    )


def _node_label(
    node_id: str,
    residue_name: str | None,
    residue_id: str | None,
) -> str:
    if residue_name is not None and residue_id is not None:
        return f"{residue_name}{residue_id}"
    if residue_name is not None:
        return residue_name
    if residue_id is not None:
        return residue_id
    return node_id


def _edge_types(raw: object, primary_type: str) -> list[JsonValue]:
    values: tuple[str, ...]
    if isinstance(raw, list):
        values = tuple(
            value.strip()
            for value in raw
            if isinstance(value, str) and value.strip() != ""
        )
    else:
        raw_string = _value_string(raw)
        if raw_string is None:
            values = ()
        elif "|" in raw_string:
            values = tuple(
                value.strip()
                for value in raw_string.split("|")
                if value.strip() != ""
            )
        elif "," in raw_string:
            values = tuple(
                value.strip()
                for value in raw_string.split(",")
                if value.strip() != ""
            )
        else:
            values = (raw_string,)
    if not values:
        values = (primary_type,)
    return list(values)


def _edge_metrics(
    edge: Mapping[str, object],
    issues: list[WaniaGraphPayloadIssue],
    *,
    field_prefix: str,
) -> dict[str, JsonValue]:
    metric_fields = (
        ("contact_freq", "contact_frequency"),
        ("mean_dist_A", "mean_distance_A"),
        ("std_dist_A", "std_distance_A"),
        ("n_episodes", "n_episodes"),
        ("mean_lifetime_frames", "mean_lifetime_frames"),
        ("max_lifetime_frames", "max_lifetime_frames"),
        ("mean_lifetime_ns", "mean_lifetime_ns"),
        ("max_lifetime_ns", "max_lifetime_ns"),
        ("formation_count", "formation_count"),
        ("breakage_count", "breakage_count"),
        ("window_cv", "window_cv"),
    )
    metrics: dict[str, JsonValue] = {}
    for backend_key, payload_key in metric_fields:
        raw = _value_string(edge.get(backend_key))
        if raw is None:
            continue
        parsed = _number(
            raw,
            prefer_int=payload_key
            in {"n_episodes", "formation_count", "breakage_count"},
        )
        if parsed is None:
            issues.append(
                WaniaGraphPayloadIssue(
                    kind="edge_mapping_failed",
                    message="Backend edge metric could not be parsed.",
                    fatal=False,
                    field=f"{field_prefix}.{backend_key}",
                )
            )
            continue
        metrics[payload_key] = parsed
    return metrics


def _stable_edge_id(
    condition: str,
    source: str,
    target: str,
    primary_type: str,
) -> str:
    digest = hashlib.sha1(
        "\x1f".join((condition, source, target, primary_type)).encode("utf-8")
    ).hexdigest()
    return f"edge_{digest[:12]}"


def _relative_artifact_path(path: Path | None, output_root: str | Path) -> str | None:
    if path is None:
        return None
    root = Path(output_root)
    path_absolute = path if path.is_absolute() else Path.cwd() / path
    root_absolute = root if root.is_absolute() else Path.cwd() / root
    try:
        return path_absolute.resolve(strict=False).relative_to(
            root_absolute.resolve(strict=False)
        ).as_posix()
    except ValueError:
        if not path.is_absolute():
            return path.as_posix()
        return Path("..", Path(path).name).as_posix()


def _string_key_mapping(raw: Mapping[object, object]) -> dict[str, object]:
    return {str(key): value for key, value in raw.items()}


def _first_non_empty(*values: str | None) -> str | None:
    for value in values:
        normalized = _blank_to_none(value)
        if normalized is not None:
            return normalized
    return None


def _first_int(*values: str | None) -> int | None:
    for value in values:
        normalized = _blank_to_none(value)
        if normalized is None:
            continue
        try:
            return int(normalized)
        except ValueError:
            continue
    return None


def _number(value: str, *, prefer_int: bool = False) -> int | float | None:
    try:
        number = float(value)
    except ValueError:
        return None
    if not (number == number and abs(number) != float("inf")):
        return None
    if prefer_int and number.is_integer():
        return int(number)
    return number


def _value_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return _blank_to_none(value)
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int | float):
        return str(value)
    return None


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized == "":
        return None
    return normalized


def _required_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or None")
    return _blank_to_none(value)


def _non_empty_string_or_none(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _require_non_negative_int(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
