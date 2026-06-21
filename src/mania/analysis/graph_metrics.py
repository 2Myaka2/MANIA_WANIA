"""Lightweight topology metrics for contract graphs."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from mania.analysis.contract_graph import ContractEdge, ContractGraph


class GraphMetricsError(Exception):
    """Raised when graph topology metrics cannot be computed."""


@dataclass(frozen=True)
class NodeTopologyMetrics:
    """Topology metrics for one graph node."""

    node_id: str
    degree: int
    strength: float


@dataclass(frozen=True)
class GraphTopologyMetrics:
    """Per-node topology metrics for a contract graph."""

    condition: str
    node_metrics: tuple[NodeTopologyMetrics, ...]

    @property
    def node_ids(self) -> tuple[str, ...]:
        """Return node IDs in graph node order."""
        return tuple(metric.node_id for metric in self.node_metrics)

    @property
    def by_node_id(self) -> Mapping[str, NodeTopologyMetrics]:
        """Return metrics keyed by node ID."""
        return {metric.node_id: metric for metric in self.node_metrics}

    def get(self, node_id: str) -> NodeTopologyMetrics:
        """Return metrics for a known node ID."""
        metrics = self.by_node_id
        if node_id not in metrics:
            raise GraphMetricsError(f"Unknown node ID: {node_id!r}")
        return metrics[node_id]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable metrics dictionary."""
        return {
            "condition": self.condition,
            "node_metrics": [
                {
                    "node_id": metric.node_id,
                    "degree": metric.degree,
                    "strength": metric.strength,
                }
                for metric in self.node_metrics
            ],
        }


def compute_graph_topology_metrics(
    graph: ContractGraph,
    *,
    weight_column: str = "contact_freq",
) -> GraphTopologyMetrics:
    """Compute unweighted degree and weighted strength for each graph node."""
    strengths = {node_id: 0.0 for node_id in graph.node_ids}

    for edge in graph.edges:
        weight = _parse_edge_weight(edge, weight_column)
        strengths[edge.source] += weight
        if edge.target != edge.source:
            strengths[edge.target] += weight

    node_metrics = tuple(
        NodeTopologyMetrics(
            node_id=node_id,
            degree=graph.degree(node_id),
            strength=strengths[node_id],
        )
        for node_id in graph.node_ids
    )
    return GraphTopologyMetrics(
        condition=graph.condition,
        node_metrics=node_metrics,
    )


def write_graph_topology_metrics(
    metrics: GraphTopologyMetrics,
    path: str | Path,
) -> Path:
    """Write graph topology metrics as JSON and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(metrics.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _parse_edge_weight(edge: ContractEdge, weight_column: str) -> float:
    if weight_column not in edge.row:
        raise GraphMetricsError(
            f"Missing weight column {weight_column!r} for edge "
            f"{edge.source!r}-{edge.target!r}"
        )
    raw_value = edge.row[weight_column].strip()
    if raw_value == "":
        raise GraphMetricsError(
            f"Empty weight value {weight_column!r} for edge "
            f"{edge.source!r}-{edge.target!r}"
        )
    try:
        weight = float(raw_value)
    except ValueError as exc:
        raise GraphMetricsError(
            f"Invalid weight value {raw_value!r} in column {weight_column!r}"
        ) from exc
    if not math.isfinite(weight):
        raise GraphMetricsError(
            f"Non-finite weight value {raw_value!r} in column {weight_column!r}"
        )
    return weight


__all__ = [
    "GraphMetricsError",
    "GraphTopologyMetrics",
    "NodeTopologyMetrics",
    "compute_graph_topology_metrics",
    "write_graph_topology_metrics",
]
