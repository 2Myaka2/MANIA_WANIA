"""Dependency-light graph analysis APIs."""

from mania.analysis.graph_metrics import (
    AnalysisGraphMetricsIssue,
    AnalysisGraphMetricsOptions,
    AnalysisGraphMetricsResult,
    GraphMetricsError,
    GraphTopologyMetrics,
    NodeTopologyMetrics,
    compute_analysis_graph_metrics_from_graph_json,
    compute_graph_topology_metrics,
    write_graph_topology_metrics,
)
from mania.analysis.graph_metrics_export import (
    AnalysisGraphMetricsArtifacts,
    write_analysis_graph_metrics_artifacts,
)
from mania.analysis.static_rin_graph import (
    STATIC_RIN_GRAPH_SCHEMA_VERSION,
    StaticRinEdge,
    StaticRinGraph,
    StaticRinGraphError,
    StaticRinInteraction,
    StaticRinNode,
    build_static_rin_graph,
    write_static_rin_graph_json,
)

__all__ = [
    "AnalysisGraphMetricsArtifacts",
    "AnalysisGraphMetricsIssue",
    "AnalysisGraphMetricsOptions",
    "AnalysisGraphMetricsResult",
    "GraphMetricsError",
    "GraphTopologyMetrics",
    "NodeTopologyMetrics",
    "STATIC_RIN_GRAPH_SCHEMA_VERSION",
    "StaticRinEdge",
    "StaticRinGraph",
    "StaticRinGraphError",
    "StaticRinInteraction",
    "StaticRinNode",
    "build_static_rin_graph",
    "compute_analysis_graph_metrics_from_graph_json",
    "compute_graph_topology_metrics",
    "write_analysis_graph_metrics_artifacts",
    "write_graph_topology_metrics",
    "write_static_rin_graph_json",
]
