"""Condition-level graph diagnostics orchestration."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from mania.analysis.contract_graph import (
    ContractGraph,
    ContractGraphError,
    load_contract_graph_from_condition_dir,
)
from mania.analysis.graph_consistency import (
    GraphConsistencyError,
    GraphTopologyConsistencyReport,
    check_graph_topology_consistency,
    write_graph_topology_consistency_report,
)
from mania.analysis.graph_metrics import (
    GraphMetricsError,
    GraphTopologyMetrics,
    compute_graph_topology_metrics,
    write_graph_topology_metrics,
)
from mania.analysis.graph_qc import (
    GraphQCError,
    GraphQCReport,
    compute_graph_qc,
    write_graph_qc_report,
)


class GraphDiagnosticsError(Exception):
    """Raised when condition graph diagnostics cannot be completed."""


@dataclass(frozen=True)
class ConditionGraphDiagnostics:
    """Condition-level graph diagnostics result."""

    condition: str
    graph: ContractGraph
    qc_report: GraphQCReport
    topology_metrics: GraphTopologyMetrics
    topology_consistency: GraphTopologyConsistencyReport

    @property
    def passed_basic_qc(self) -> bool:
        """Return whether basic graph QC passed."""
        return self.qc_report.passed_basic_qc

    @property
    def passed_topology_consistency(self) -> bool:
        """Return whether topology consistency checks passed."""
        return self.topology_consistency.passed

    @property
    def passed(self) -> bool:
        """Return whether all condition graph diagnostics passed."""
        return self.passed_basic_qc and self.passed_topology_consistency

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable diagnostics dictionary."""
        return {
            "condition": self.condition,
            "n_nodes": self.graph.n_nodes,
            "n_edges": self.graph.n_edges,
            "passed": self.passed,
            "passed_basic_qc": self.passed_basic_qc,
            "passed_topology_consistency": self.passed_topology_consistency,
            "qc_report": self.qc_report.to_dict(),
            "topology_metrics": self.topology_metrics.to_dict(),
            "topology_consistency": self.topology_consistency.to_dict(),
        }


@dataclass(frozen=True)
class MultiConditionGraphDiagnostics:
    """Multi-condition graph diagnostics result."""

    conditions: tuple[str, ...]
    condition_diagnostics: Mapping[str, ConditionGraphDiagnostics]

    @property
    def passed(self) -> bool:
        """Return whether all condition diagnostics passed."""
        return all(
            self.condition_diagnostics[condition].passed
            for condition in self.conditions
        )

    @property
    def passed_conditions(self) -> tuple[str, ...]:
        """Return condition names with passing diagnostics in input order."""
        return tuple(
            condition
            for condition in self.conditions
            if self.condition_diagnostics[condition].passed
        )

    @property
    def failed_conditions(self) -> tuple[str, ...]:
        """Return condition names with failing diagnostics in input order."""
        return tuple(
            condition
            for condition in self.conditions
            if not self.condition_diagnostics[condition].passed
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable diagnostics dictionary."""
        return {
            "conditions": list(self.conditions),
            "passed": self.passed,
            "passed_conditions": list(self.passed_conditions),
            "failed_conditions": list(self.failed_conditions),
            "condition_diagnostics": {
                condition: self.condition_diagnostics[condition].to_dict()
                for condition in self.conditions
            },
        }


def run_condition_graph_diagnostics(
    condition_dir: str | Path,
    *,
    condition: str,
    abs_tol: float = 1e-6,
    weight_column: str = "contact_freq",
    degree_column: str = "degree",
    strength_column: str = "strength",
) -> ConditionGraphDiagnostics:
    """Run graph diagnostics for one condition artifact directory."""
    normalized_condition = _normalize_condition(condition)
    condition_path = _validate_condition_dir(condition_dir)
    graph = _load_graph(condition_path, normalized_condition)

    qc_report = _compute_qc(graph)
    topology_metrics = _compute_topology_metrics(graph, weight_column)
    topology_consistency = _check_topology_consistency(
        graph,
        abs_tol=abs_tol,
        weight_column=weight_column,
        degree_column=degree_column,
        strength_column=strength_column,
    )

    return ConditionGraphDiagnostics(
        condition=normalized_condition,
        graph=graph,
        qc_report=qc_report,
        topology_metrics=topology_metrics,
        topology_consistency=topology_consistency,
    )


def run_multi_condition_graph_diagnostics(
    output_root: str | Path,
    conditions: Iterable[str],
    *,
    abs_tol: float = 1e-6,
    weight_column: str = "contact_freq",
    degree_column: str = "degree",
    strength_column: str = "strength",
) -> MultiConditionGraphDiagnostics:
    """Run graph diagnostics for multiple condition artifact directories."""
    root = _validate_output_root(output_root)
    normalized_conditions = _normalize_conditions(conditions)
    condition_diagnostics: dict[str, ConditionGraphDiagnostics] = {}

    for condition in normalized_conditions:
        condition_diagnostics[condition] = run_condition_graph_diagnostics(
            root / condition,
            condition=condition,
            abs_tol=abs_tol,
            weight_column=weight_column,
            degree_column=degree_column,
            strength_column=strength_column,
        )

    return MultiConditionGraphDiagnostics(
        conditions=normalized_conditions,
        condition_diagnostics=MappingProxyType(condition_diagnostics),
    )


def write_condition_graph_diagnostics(
    diagnostics: ConditionGraphDiagnostics,
    output_dir: str | Path,
) -> Path:
    """Write combined condition graph diagnostics JSON and return its path."""
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    output_path = output_root / "graph_diagnostics.json"
    output_path.write_text(
        json.dumps(diagnostics.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_multi_condition_graph_diagnostics(
    diagnostics: MultiConditionGraphDiagnostics,
    output_dir: str | Path,
) -> Path:
    """Write combined multi-condition graph diagnostics JSON."""
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    output_path = output_root / "multi_condition_graph_diagnostics.json"
    output_path.write_text(
        json.dumps(diagnostics.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_condition_graph_diagnostics_bundle(
    diagnostics: ConditionGraphDiagnostics,
    output_dir: str | Path,
) -> tuple[Path, ...]:
    """Write combined and lower-level condition graph diagnostics reports."""
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    return (
        write_condition_graph_diagnostics(diagnostics, output_root),
        write_graph_qc_report(diagnostics.qc_report, output_root / "graph_qc.json"),
        write_graph_topology_metrics(
            diagnostics.topology_metrics,
            output_root / "graph_topology_metrics.json",
        ),
        write_graph_topology_consistency_report(
            diagnostics.topology_consistency,
            output_root / "graph_topology_consistency.json",
        ),
    )


def write_multi_condition_graph_diagnostics_bundle(
    diagnostics: MultiConditionGraphDiagnostics,
    output_dir: str | Path,
) -> tuple[Path, ...]:
    """Write multi-condition and per-condition graph diagnostics reports."""
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = [
        write_multi_condition_graph_diagnostics(diagnostics, output_root)
    ]
    for condition in diagnostics.conditions:
        paths.extend(
            write_condition_graph_diagnostics_bundle(
                diagnostics.condition_diagnostics[condition],
                output_root / condition,
            )
        )
    return tuple(paths)


def _normalize_condition(condition: str) -> str:
    normalized = condition.strip()
    if normalized == "":
        raise GraphDiagnosticsError("Condition must be non-empty")
    return normalized


def _normalize_conditions(conditions: Iterable[str]) -> tuple[str, ...]:
    if isinstance(conditions, str):
        raise GraphDiagnosticsError("Conditions must be an iterable of names")

    normalized_conditions: list[str] = []
    seen_conditions: set[str] = set()
    for condition in conditions:
        normalized = _normalize_condition(condition)
        if normalized in seen_conditions:
            raise GraphDiagnosticsError(f"Duplicate condition: {normalized!r}")
        normalized_conditions.append(normalized)
        seen_conditions.add(normalized)
    return tuple(normalized_conditions)


def _validate_output_root(output_root: str | Path) -> Path:
    root = Path(output_root)
    if not root.exists():
        raise GraphDiagnosticsError(f"Missing output root: {root}")
    if not root.is_dir():
        raise GraphDiagnosticsError(f"Output root is not a directory: {root}")
    return root


def _validate_condition_dir(condition_dir: str | Path) -> Path:
    condition_path = Path(condition_dir)
    if not condition_path.exists():
        raise GraphDiagnosticsError(f"Missing condition directory: {condition_path}")
    if not condition_path.is_dir():
        raise GraphDiagnosticsError(
            f"Condition path is not a directory: {condition_path}"
        )
    return condition_path


def _load_graph(condition_dir: Path, condition: str) -> ContractGraph:
    try:
        return load_contract_graph_from_condition_dir(
            condition_dir,
            condition=condition,
        )
    except ContractGraphError as exc:
        raise GraphDiagnosticsError(f"Could not load contract graph: {exc}") from exc


def _compute_qc(graph: ContractGraph) -> GraphQCReport:
    try:
        return compute_graph_qc(graph)
    except GraphQCError as exc:
        raise GraphDiagnosticsError(f"Could not compute graph QC: {exc}") from exc


def _compute_topology_metrics(
    graph: ContractGraph,
    weight_column: str,
) -> GraphTopologyMetrics:
    try:
        return compute_graph_topology_metrics(graph, weight_column=weight_column)
    except GraphMetricsError as exc:
        raise GraphDiagnosticsError(
            f"Could not compute graph topology metrics: {exc}"
        ) from exc


def _check_topology_consistency(
    graph: ContractGraph,
    *,
    abs_tol: float,
    weight_column: str,
    degree_column: str,
    strength_column: str,
) -> GraphTopologyConsistencyReport:
    try:
        return check_graph_topology_consistency(
            graph,
            abs_tol=abs_tol,
            weight_column=weight_column,
            degree_column=degree_column,
            strength_column=strength_column,
        )
    except GraphConsistencyError as exc:
        raise GraphDiagnosticsError(
            f"Could not check graph topology consistency: {exc}"
        ) from exc


__all__ = [
    "ConditionGraphDiagnostics",
    "GraphDiagnosticsError",
    "MultiConditionGraphDiagnostics",
    "run_condition_graph_diagnostics",
    "run_multi_condition_graph_diagnostics",
    "write_condition_graph_diagnostics",
    "write_condition_graph_diagnostics_bundle",
    "write_multi_condition_graph_diagnostics",
    "write_multi_condition_graph_diagnostics_bundle",
]
