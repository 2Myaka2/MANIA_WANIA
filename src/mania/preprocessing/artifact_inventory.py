"""Adapt retained preprocessing inputs and successful outputs to inventory specs."""

import re
from pathlib import Path

from mania.artifact_inventory import ArtifactChecksumMode, ArtifactInventory
from mania.artifact_inventory_io import (
    ArtifactInventoryFileSpec,
    build_artifact_inventory,
)
from mania.preprocessing.run_provenance import PREPROCESSING_RUN_PROVENANCE_WORKFLOW
from mania.preprocessing.trajectory_graph_workflow import (
    PreprocessingGraphWorkflowAnalysisInputExportResult,
    PreprocessingGraphWorkflowDiagnosticsResult,
    PreprocessingGraphWorkflowGraphExportResult,
    PreprocessingGraphWorkflowReferenceComparisonResult,
    PreprocessingGraphWorkflowRuntimeLoadingResult,
    PreprocessingGraphWorkflowScientificCsvExportResult,
)
from mania.preprocessing.trajectory_manifest_loader import (
    PreprocessingManifestLoadResult,
)
from mania.preprocessing.trajectory_preprocessing_manifests import (
    PreprocessingManifestArtifactsWriteResult,
)
from mania.preprocessing.trajectory_protein_contact_export import (
    PreprocessingProteinContactCsvWriteResult,
)
from mania.preprocessing.trajectory_residue_table_export import (
    PreprocessingResidueTableCsvWriteResult,
)
from mania.preprocessing.trajectory_runtime import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRuntimeInput,
)

PREPROCESSING_ARTIFACT_INVENTORY_PATH = "artifact_inventory.json"
PREPROCESSING_ARTIFACT_INVENTORY_ROLE = "artifact_inventory"


class PreprocessingArtifactInventoryError(ValueError):
    """Retained workflow state cannot describe a complete portable inventory."""


def _format(path: Path) -> str:
    suffix = path.suffix[1:].lower()
    if not suffix or re.fullmatch(r"[a-z0-9+_\-]+", suffix) is None:
        raise PreprocessingArtifactInventoryError("File must have a usable suffix.")
    return suffix


def collect_preprocessing_input_file_specs(
    runtime_loading: PreprocessingGraphWorkflowRuntimeLoadingResult,
    *,
    reference_nodes_path: Path | None = None,
    reference_edges_path: Path | None = None,
    reference_graph_path: Path | None = None,
    include_reference_inputs: bool = False,
    parameter_table_local_path: Path | None = None,
) -> tuple[ArtifactInventoryFileSpec, ...]:
    """Describe all intended conditions, even when their runtime load failed."""
    if not isinstance(runtime_loading, PreprocessingGraphWorkflowRuntimeLoadingResult):
        raise PreprocessingArtifactInventoryError(
            "Authoritative runtime loading state is unavailable."
        )
    loaded = runtime_loading.runtime_load_result
    intended = runtime_loading.manifest_readiness.condition_names
    if (
        not runtime_loading.manifest_readiness.passed
        or not intended
        or len(set(intended)) != len(intended)
        or not isinstance(loaded, PreprocessingManifestLoadResult)
        or not all(
            isinstance(result, PreprocessingConditionLoadResult)
            and isinstance(result.runtime_input, PreprocessingConditionRuntimeInput)
            and result.runtime_input.condition_name == result.condition_name
            for result in loaded.condition_results
        )
        or tuple(result.condition_name for result in loaded.condition_results)
        != intended
    ):
        raise PreprocessingArtifactInventoryError(
            "Complete authoritative condition inputs are unavailable."
        )

    specs: list[ArtifactInventoryFileSpec] = []

    def add(
        artifact_id: str,
        role: str,
        path: Path,
        prefix: str,
        condition: str | None = None,
    ) -> None:
        try:
            specs.append(
                ArtifactInventoryFileSpec(
                    artifact_id,
                    "input",
                    role,
                    path,
                    f"{prefix}/{path.name}",
                    _format(path),
                    condition,
                )
            )
        except ValueError:
            raise PreprocessingArtifactInventoryError(
                f"Invalid input file metadata for '{artifact_id}'."
            ) from None

    add(
        "input:manifest",
        "input_manifest",
        runtime_loading.manifest_path,
        "inputs/manifest",
    )
    if parameter_table_local_path is not None:
        specs.append(ArtifactInventoryFileSpec(
            "input:dataset_parameter_table",
            "input",
            "dataset_parameter_table",
            parameter_table_local_path,
            "inputs/dataset/parameter_table.csv",
            "csv",
            None,
        ))
    for ordinal, result in enumerate(loaded.condition_results, 1):
        source = result.runtime_input
        identity = f"input:condition:{ordinal:04d}"
        prefix = f"inputs/conditions/{ordinal:04d}"
        condition = result.condition_name
        add(
            f"{identity}:topology",
            "condition_topology",
            source.topology_path,
            f"{prefix}/topology",
            condition,
        )
        for number, path in enumerate(source.trajectory_paths, 1):
            add(
                f"{identity}:trajectory:{number:04d}",
                "condition_trajectory",
                path,
                f"{prefix}/trajectories/{number:04d}",
                condition,
            )
        if source.reference_structure_path is not None:
            add(
                f"{identity}:reference_structure",
                "condition_reference_structure",
                source.reference_structure_path,
                f"{prefix}/reference_structure",
                condition,
            )
    if include_reference_inputs:
        for name, reference_path in (
            ("nodes", reference_nodes_path),
            ("edges", reference_edges_path),
            ("graph", reference_graph_path),
        ):
            if reference_path is not None:
                add(
                    f"input:reference:{name}",
                    f"reference_{name}",
                    reference_path,
                    f"inputs/reference/{name}",
                )
    return tuple(specs)


def collect_preprocessing_output_file_specs(
    *,
    output_root: Path,
    graph_export: PreprocessingGraphWorkflowGraphExportResult | None = None,
    analysis_input_export: PreprocessingGraphWorkflowAnalysisInputExportResult
    | None = None,
    scientific_csv_export: PreprocessingGraphWorkflowScientificCsvExportResult
    | None = None,
    diagnostics: PreprocessingGraphWorkflowDiagnosticsResult | None = None,
    reference_comparison: PreprocessingGraphWorkflowReferenceComparisonResult
    | None = None,
    runtime_metadata_path: Path | None = None,
    pbc_audit_path: Path | None = None,
) -> tuple[ArtifactInventoryFileSpec, ...]:
    """Describe supplied successful stages in execution order, without discovery.

    Omit stages that were not requested. Report paths must also be marked written.
    A failed stage contributes no entries, including any of its partial writes.
    """
    specs: list[ArtifactInventoryFileSpec] = []

    def add(
        role: str,
        path: Path | None,
        *,
        identity: str | None = None,
        condition: str | None = None,
    ) -> None:
        if path is None:
            raise PreprocessingArtifactInventoryError(
                "Successful output path is missing."
            )
        try:
            portable = path.relative_to(output_root).as_posix()
            if portable in (
                PREPROCESSING_ARTIFACT_INVENTORY_PATH,
                "run_provenance.json",
            ):
                raise ValueError("Technical metadata is excluded.")
            specs.append(
                ArtifactInventoryFileSpec(
                    identity or f"output:{role}",
                    "output",
                    role,
                    path,
                    portable,
                    _format(path),
                    condition,
                )
            )
        except ValueError:
            raise PreprocessingArtifactInventoryError(
                "Output path must be portable, inside the output root, "
                "and exclude inventory/provenance."
            ) from None

    if graph_export is not None and graph_export.passed:
        add("graph_nodes", graph_export.graph_nodes_csv_path)
        add("graph_edges", graph_export.graph_edges_csv_path)
        add("graph_json", graph_export.graph_json_path)

    if analysis_input_export is not None and analysis_input_export.passed:
        residues = analysis_input_export.residue_tables_result
        contacts = analysis_input_export.protein_contacts_result
        manifests = analysis_input_export.manifest_artifacts_result
        if (
            not isinstance(residues, PreprocessingResidueTableCsvWriteResult)
            or not isinstance(contacts, PreprocessingProteinContactCsvWriteResult)
            or not isinstance(manifests, PreprocessingManifestArtifactsWriteResult)
        ):
            raise PreprocessingArtifactInventoryError(
                "Authoritative analysis-input output records are unavailable."
            )
        conditions = analysis_input_export.graph_export.computation.condition_names
        for role, paths in (
            ("residue_table", residues.paths_by_condition),
            ("protein_contact_edges", contacts.edge_paths_by_condition),
            ("protein_contacts_perframe", contacts.perframe_paths_by_condition),
        ):
            if not set(paths).issubset(conditions):
                raise PreprocessingArtifactInventoryError(
                    "Analysis-input output has an unknown condition."
                )
            for ordinal, condition in enumerate(conditions, 1):
                if condition in paths:
                    add(
                        role,
                        paths[condition],
                        identity=f"output:condition:{ordinal:04d}:{role}",
                        condition=condition,
                    )
        roles = {
            "edge_semantics.json": "edge_semantics",
            "mania_residue_library.json": "residue_library",
            "mania_manifest.json": "preprocessing_manifest",
        }
        for path in manifests.paths:
            if path.name not in roles:
                raise PreprocessingArtifactInventoryError(
                    "Unrecognized analysis-input manifest output."
                )
            add(roles[path.name], path)

    if scientific_csv_export is not None and scientific_csv_export.passed:
        for role, scientific_path in (
            ("rg_timeseries", scientific_csv_export.rg_timeseries_csv_path),
            ("contact_edges", scientific_csv_export.contact_edges_csv_path),
            ("contacts_perframe", scientific_csv_export.contacts_perframe_csv_path),
        ):
            if scientific_csv_export.requested_exports[role]:
                add(role, scientific_path)
    if (
        diagnostics is not None
        and diagnostics.passed
        and diagnostics.diagnostics_report_json_written
    ):
        add("graph_diagnostics_report", diagnostics.diagnostics_report_json_path)
    if (
        reference_comparison is not None
        and reference_comparison.passed
        and reference_comparison.reference_comparison_enabled
        and not reference_comparison.reference_comparison_skipped
        and reference_comparison.reference_comparison_json_written
    ):
        add(
            "reference_comparison_report",
            reference_comparison.reference_comparison_json_path,
        )
    for role, technical_path in (
        ("runtime_metadata", runtime_metadata_path),
        ("pbc_audit", pbc_audit_path),
    ):
        if technical_path is not None:
            if technical_path != output_root / f"{role}.json":
                raise PreprocessingArtifactInventoryError(
                    "Technical output must use its exact preprocessing path."
                )
            add(role, technical_path)
    return tuple(specs)


def build_preprocessing_artifact_inventory(
    *,
    run_id: str,
    runtime_loading: PreprocessingGraphWorkflowRuntimeLoadingResult,
    output_root: Path,
    checksum_mode: ArtifactChecksumMode = "none",
    reference_nodes_path: Path | None = None,
    reference_edges_path: Path | None = None,
    reference_graph_path: Path | None = None,
    include_reference_inputs: bool = False,
    parameter_table_local_path: Path | None = None,
    graph_export: PreprocessingGraphWorkflowGraphExportResult | None = None,
    analysis_input_export: PreprocessingGraphWorkflowAnalysisInputExportResult
    | None = None,
    scientific_csv_export: PreprocessingGraphWorkflowScientificCsvExportResult
    | None = None,
    diagnostics: PreprocessingGraphWorkflowDiagnosticsResult | None = None,
    reference_comparison: PreprocessingGraphWorkflowReferenceComparisonResult
    | None = None,
    runtime_metadata_path: Path | None = None,
    pbc_audit_path: Path | None = None,
) -> ArtifactInventory:
    """Inspect authoritative files through the generic builder; never write."""
    inputs = collect_preprocessing_input_file_specs(
        runtime_loading,
        reference_nodes_path=reference_nodes_path,
        reference_edges_path=reference_edges_path,
        reference_graph_path=reference_graph_path,
        include_reference_inputs=include_reference_inputs,
        parameter_table_local_path=parameter_table_local_path,
    )
    outputs = collect_preprocessing_output_file_specs(
        output_root=output_root,
        graph_export=graph_export,
        analysis_input_export=analysis_input_export,
        scientific_csv_export=scientific_csv_export,
        diagnostics=diagnostics,
        reference_comparison=reference_comparison,
        runtime_metadata_path=runtime_metadata_path,
        pbc_audit_path=pbc_audit_path,
    )
    return build_artifact_inventory(
        run_id=run_id,
        workflow=PREPROCESSING_RUN_PROVENANCE_WORKFLOW,
        inventory_path=PREPROCESSING_ARTIFACT_INVENTORY_PATH,
        file_specs=inputs + outputs,
        checksum_mode=checksum_mode,
    )


__all__ = [
    "PREPROCESSING_ARTIFACT_INVENTORY_PATH",
    "PREPROCESSING_ARTIFACT_INVENTORY_ROLE",
    "PreprocessingArtifactInventoryError",
    "collect_preprocessing_input_file_specs",
    "collect_preprocessing_output_file_specs",
    "build_preprocessing_artifact_inventory",
]
