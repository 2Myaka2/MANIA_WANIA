"""Adapt authoritative analysis execution paths to the generic inventory contract."""

import re
from pathlib import Path

from mania.analysis.orchestration import (
    AnalyzeConditionInputPaths,
    AnalyzeRequest,
    AnalyzeRunResult,
    _validate_resolved_input_paths,
)
from mania.analysis.run_provenance import ANALYSIS_RUN_PROVENANCE_WORKFLOW
from mania.artifact_inventory import (
    ArtifactChecksumMode,
    ArtifactDirection,
    ArtifactInventory,
)
from mania.artifact_inventory_io import (
    ArtifactInventoryFileSpec,
    build_artifact_inventory,
)

ANALYSIS_ARTIFACT_INVENTORY_PATH = "analysis/artifact_inventory.json"
ANALYSIS_ARTIFACT_INVENTORY_ROLE = "artifact_inventory"


class AnalysisArtifactInventoryError(ValueError):
    """Authoritative analysis paths cannot describe a portable inventory."""


def _file_spec(
    *,
    artifact_id: str,
    direction: ArtifactDirection,
    role: str,
    local_path: Path,
    path: str,
    condition: str | None = None,
) -> ArtifactInventoryFileSpec:
    suffix = local_path.suffix[1:].lower()
    if not suffix or re.fullmatch(r"[a-z0-9+_\-]+", suffix) is None:
        raise AnalysisArtifactInventoryError("File must have a usable suffix.")
    if local_path.name in {"artifact_inventory.json", "run_provenance.json"}:
        raise AnalysisArtifactInventoryError("Technical metadata is not an artifact.")
    return ArtifactInventoryFileSpec(
        artifact_id=artifact_id,
        direction=direction,
        role=role,
        local_path=local_path,
        path=path,
        format=suffix,
        condition=condition,
    )


def collect_analysis_input_file_specs(
    *,
    request: AnalyzeRequest,
    resolved_input_paths: tuple[AnalyzeConditionInputPaths, ...],
) -> tuple[ArtifactInventoryFileSpec, ...]:
    """Describe only supplied inputs; shared root inputs precede condition tables."""
    try:
        _validate_resolved_input_paths(request, resolved_input_paths)
        specs: list[ArtifactInventoryFileSpec] = []
        for field, key, role, filename in (
            (
                "mania_manifest",
                "mania_manifest",
                "preprocessing_manifest",
                "mania_manifest.json",
            ),
            (
                "edge_semantics",
                "edge_semantics",
                "edge_semantics",
                "edge_semantics.json",
            ),
            (
                "mania_residue_library",
                "residue_library",
                "residue_library",
                "mania_residue_library.json",
            ),
        ):
            root_path = getattr(resolved_input_paths[0], field)
            if any(
                getattr(paths, field) != root_path for paths in resolved_input_paths
            ):
                raise AnalysisArtifactInventoryError(
                    "Optional root input paths must agree across conditions."
                )
            if root_path is not None:
                specs.append(
                    _file_spec(
                        artifact_id=f"input:root:{key}",
                        direction="input",
                        role=role,
                        local_path=root_path,
                        path=f"inputs/root/{filename}",
                    )
                )
        for ordinal, paths in enumerate(resolved_input_paths, start=1):
            for role, local_path in (
                ("residue_table", paths.residue_table),
                ("protein_contact_edges", paths.protein_contact_edges),
                ("contacts_perframe", paths.contacts_perframe),
            ):
                specs.append(
                    _file_spec(
                        artifact_id=f"input:condition:{ordinal:04d}:{role}",
                        direction="input",
                        role=role,
                        local_path=local_path,
                        path=f"inputs/conditions/{ordinal:04d}/{role}/{local_path.name}",
                        condition=paths.condition,
                    )
                )
        return tuple(specs)
    except AnalysisArtifactInventoryError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise AnalysisArtifactInventoryError(
            "Analysis inputs must match the request and have portable file metadata."
        ) from None


def collect_analysis_output_file_specs(
    result: AnalyzeRunResult,
) -> tuple[ArtifactInventoryFileSpec, ...]:
    """Describe completed result paths lexically, without inspecting outputs."""
    if type(result) is not AnalyzeRunResult:
        raise AnalysisArtifactInventoryError("result must be AnalyzeRunResult")
    specs: list[ArtifactInventoryFileSpec] = []

    def add(
        artifact_id: str,
        role: str,
        local_path: Path,
        condition: str | None = None,
    ) -> None:
        specs.append(
            _file_spec(
                artifact_id=artifact_id,
                direction="output",
                role=role,
                local_path=local_path,
                path=local_path.relative_to(result.request.output_root).as_posix(),
                condition=condition,
            )
        )

    try:
        for ordinal, condition in enumerate(result.condition_results, start=1):
            for key, path in (
                ("graph", condition.graph_json),
                ("centrality", condition.centrality_csv),
                ("communities", condition.communities_csv),
                ("region_enrichment", condition.region_enrichment_csv),
                ("temporal_rin", condition.temporal_rin_csv),
                ("conformation_pca", condition.conformation_pca_csv),
                ("conformation_labels", condition.conformation_labels_csv),
            ):
                add(
                    f"output:condition:{ordinal:04d}:{key}",
                    f"analysis_{key}",
                    path,
                    condition.condition,
                )
        add("output:comparison", "analysis_comparison", result.comparison_csv)
        add("output:stats", "analysis_stats", result.stats_csv)
        if result.extended_metrics_json is not None:
            add(
                "output:extended_metrics",
                "analysis_manifest",
                result.extended_metrics_json,
            )
        return tuple(specs)
    except AnalysisArtifactInventoryError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise AnalysisArtifactInventoryError(
            "Analysis output paths must be portable and inside the output root."
        ) from None


def build_analysis_artifact_inventory(
    *,
    run_id: str,
    request: AnalyzeRequest,
    resolved_input_paths: tuple[AnalyzeConditionInputPaths, ...],
    result: AnalyzeRunResult | None,
    checksum_mode: ArtifactChecksumMode,
) -> ArtifactInventory:
    """Inspect declared inputs and completed outputs through the generic builder."""
    inputs = collect_analysis_input_file_specs(
        request=request,
        resolved_input_paths=resolved_input_paths,
    )
    outputs: tuple[ArtifactInventoryFileSpec, ...] = ()
    if result is not None:
        if type(result) is not AnalyzeRunResult:
            raise AnalysisArtifactInventoryError("result must be AnalyzeRunResult")
        if result.request != request:
            raise AnalysisArtifactInventoryError("result.request must match request")
        outputs = collect_analysis_output_file_specs(result)
    return build_artifact_inventory(
        run_id=run_id,
        workflow=ANALYSIS_RUN_PROVENANCE_WORKFLOW,
        inventory_path=ANALYSIS_ARTIFACT_INVENTORY_PATH,
        file_specs=inputs + outputs,
        checksum_mode=checksum_mode,
    )


__all__ = [
    "ANALYSIS_ARTIFACT_INVENTORY_PATH",
    "ANALYSIS_ARTIFACT_INVENTORY_ROLE",
    "AnalysisArtifactInventoryError",
    "build_analysis_artifact_inventory",
    "collect_analysis_input_file_specs",
    "collect_analysis_output_file_specs",
]
