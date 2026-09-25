"""Synthetic production controls; publication never executes upstream science."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from test_dataset_hard_qc import inputs as hard_inputs
from test_dataset_hard_qc import plan
from test_dataset_release_metadata import (
    complete_annotations,
    contact_parameters,
    temporal_evidence,
)
from test_dataset_release_science import make_science_case
from test_dataset_review_qc import review

from mania import canonical_window_tables_io as canonical_io
from mania.biological_annotations_io import write_dataset_system_biological_annotations
from mania.dataset_identity import DatasetTrajectoryIdentity
from mania.dataset_qc_evidence_io import (
    ReplicaHardQCEvidence,
    write_replica_hard_qc_evidence,
    write_replica_review_qc_evidence,
)
from mania.dataset_qc_manifest import DatasetQCManifest, DatasetQCWorkflowReplica
from mania.dataset_qc_manifest_io import write_dataset_qc_manifest
from mania.dataset_qc_run import collect_dataset_qc_input_specs, run_dataset_qc
from mania.dataset_release_inputs_io import (
    PUBLICATION_INPUT_KIND,
    PUBLICATION_INPUT_SCHEMA_VERSION,
    write_dataset_release_publication_inputs,
)
from mania.dataset_release_manifest import (
    DatasetReleaseExportManifest,
    ReleaseAnnotationBinding,
    ReleaseCanonicalBinding,
    ReleaseInputBinding,
    ReleaseUpstreamRun,
)
from mania.dataset_release_manifest_io import write_dataset_release_export_manifest
from mania.dataset_release_workflow import build_dataset_release
from mania.preprocessing.physical_time_execution import PreprocessingTemporalExecution
from mania.preprocessing.physical_time_execution_io import (
    write_preprocessing_temporal_execution,
)
from mania.preprocessing.temporal_policy import LEGACY_BOUNDARY_PROFILE
from mania.replica_aggregation_manifest_io import write_replica_aggregation_manifest
from mania.replica_aggregation_run import (
    collect_replica_aggregation_input_specs,
    run_replica_aggregation,
)
from mania.replica_aggregation_workflow import FAMILIES
from mania.software_identity import SoftwareIdentity


def make_release_case(
    root,
    *,
    outcomes=("available", "excluded", "available"),
    unavailable=(),
    mode="none",
    empty=False,
    systems=("T330M",),
    condition=None,
    occupancies=None,
    boundary_profile=LEGACY_BOUNDARY_PROFILE,
):
    """Execute accepted synthetic QC then aggregation before release test guards."""
    root.mkdir(parents=True, exist_ok=True)
    case, template = make_science_case(
        root, outcomes=outcomes, unavailable=unavailable,
        boundary_profile=boundary_profile
    )
    labels = {"engine": "gromacs", "condition": condition} if condition else {}
    groups = []
    for system in systems:
        for group in template.groups:
            changes = {}
            for family in ("lipid", "glycan"):
                collection = getattr(group, f"{family}_correspondences")
                changes[f"{family}_correspondences"] = replace(
                    collection,
                    correspondences=tuple(
                        replace(
                            c,
                            members=tuple(
                                replace(m, system_id=system) for m in c.members
                            ),
                        )
                        for c in collection.correspondences
                    ),
                )
            groups.append(
                replace(
                    group,
                    spec=replace(group.spec, system_id=system, **labels),
                    members=tuple(
                        replace(m, system_id=system, **labels) for m in group.members
                    ),
                    **changes,
                )
            )
    template = replace(template, groups=tuple(groups))
    members = {m.replica_key: m for g in template.groups for m in g.members}
    replicas = tuple(sorted(members))
    executions = {}
    for key in replicas:
        evidence = temporal_evidence(key[-1], boundary_profile=boundary_profile)
        if condition is not None:
            evidence = replace(evidence, execution_condition=condition)
        spec = evidence.dataset_spec.model_copy(
            update={
                "identity": evidence.dataset_spec.identity.model_copy(
                    update={"system_id": key[1], **labels}
                ),
            }
        )
        if occupancies is not None:
            from mania.preprocessing.physical_time_sampling import (
                PhysicalTimeSourceFrame,
                resolve_physical_time_sampling,
            )
            from mania.preprocessing.physical_time_windows import (
                plan_physical_time_windows,
            )

            spec = spec.model_copy(
                update={
                    "temporal": spec.temporal.model_copy(
                        update={"frame_stride_ps": 40.0}
                    )
                }
            )
            sampling = resolve_physical_time_sampling(
                tuple(PhysicalTimeSourceFrame(i, float(i * 40)) for i in range(26)),
                temporal=spec.temporal,
            )
            evidence = replace(
                evidence,
                dataset_spec=spec,
                sampling_plan=sampling,
                window_plan=plan_physical_time_windows(
                    sampling, temporal=spec.temporal, boundary_profile=boundary_profile
                ),
            )
        else:
            evidence = replace(evidence, dataset_spec=spec)
        executions[key] = evidence
    canonical_paths = {}
    canonical_bindings = []
    for family, key, writer in zip(
        FAMILIES,
        (
            "canonical_protein_edges",
            "canonical_protein_lipid_contacts",
            "canonical_protein_glycan_contacts",
        ),
        (
            canonical_io.write_canonical_protein_edge_window_csv,
            canonical_io.write_canonical_protein_lipid_window_csv,
            canonical_io.write_canonical_protein_glycan_window_csv,
        ),
        strict=True,
    ):
        table = case[key]
        rows = []
        for system in systems:
            for source in table.rows:
                row = replace(source, system_id=system, **labels)
                if occupancies is not None:
                    occupancy = occupancies[int(row.replica_id) - 1]
                    if (
                        not occupancy
                        or row.window_index
                        != template.groups[0].spec.window.window_index
                    ):
                        continue
                    row_changes = dict(
                        requested_sample_count=10,
                        resolved_frame_count=10,
                        missing_sample_count=0,
                        coverage_fraction=1.0,
                        n_contact_frames=int(occupancy * 10),
                        occupancy=occupancy,
                        effective_window_start_ns=0.4,
                        effective_window_end_ns=0.76,
                    )
                    if family.name == "protein":
                        row_changes["edge_weight"] = occupancy
                    row = replace(row, **row_changes)
                rows.append(row)
        table = type(table)(tuple(sorted(rows, key=lambda r: r.row_order)))
        if empty:
            table = type(table)(())
        result = writer(table, root / "canonical")
        assert result.written
        canonical_paths[f"{family.name}_canonical_table_paths"] = (result.output_path,)
        canonical_bindings.append(
            ReleaseCanonicalBinding(
                family.name,
                result.output_path.relative_to(root).as_posix(),
                replicas,
            )
        )
    template = replace(template, **canonical_paths)
    qc_input = root / "qc_input"
    assert write_replica_aggregation_manifest(
        template, qc_input / "template.json"
    ).written
    members = {m.replica_key: m for g in template.groups for m in g.members}
    controls = []
    for index, key in enumerate(replicas):
        values = hard_inputs(
            sampling_plan=plan(
                expected=100,
                resolved=94 if outcomes[int(key[-1]) - 1] == "excluded" else 100,
            )
        )
        identity_values = dict(
            zip(
                ("dataset_id", "system_id", "trajectory_id", "replica_id"),
                key,
                strict=True,
            )
        )
        values["identity"] = DatasetTrajectoryIdentity(
            **(
                values["identity"].to_dict()
                | identity_values
                | {"engine": members[key].engine, "condition": members[key].condition}
            ),
        )
        values["mapping_binding"] = replace(
            values["mapping_binding"], **identity_values
        )
        hard_path, review_path = (
            Path(f"hard/{index}.json"),
            Path(f"review/{index}.json"),
        )
        assert write_replica_hard_qc_evidence(
            ReplicaHardQCEvidence(**values), qc_input / hard_path
        ).written
        assert write_replica_review_qc_evidence(
            review(key, engine=members[key].engine), qc_input / review_path
        ).written
        controls.append(DatasetQCWorkflowReplica(*key, hard_path, review_path, None))
    qc_manifest = DatasetQCManifest(Path("template.json"), tuple(controls))
    qc_path = qc_input / "dataset_qc_manifest.json"
    assert write_dataset_qc_manifest(qc_manifest, qc_path).written
    # Synthetic run identity is explicit; no Git or current package probing.
    identity = SoftwareIdentity(
        "MANIA", "mania-wania", "0.1.0", None, "unavailable", "unavailable"
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("mania.dataset_qc_run.get_software_identity", lambda: identity)
        patch.setattr(
            "mania.replica_aggregation_run.get_software_identity", lambda: identity
        )
        qc = run_dataset_qc(qc_path, root / "qc", checksum_mode=mode)
        derived_path = root / "qc" / "replica_aggregation_manifest_qc_derived.json"
        run_replica_aggregation(derived_path, root / "aggregation", checksum_mode=mode)
    derived = qc.outputs.derived_manifest
    assert derived is not None
    temporal_paths = []
    for key in replicas:
        output = root / "temporal" / key[1] / key[-1]
        assert write_preprocessing_temporal_execution(
            PreprocessingTemporalExecution((executions[key],)), output
        ).written
        temporal_paths.append(
            (output / "temporal_execution.json").relative_to(root).as_posix()
        )
    annotation_bindings = []
    for system in systems:
        annotation_path = root / f"annotations/{system}.json"
        assert write_dataset_system_biological_annotations(
            replace(complete_annotations(), system_id=system), annotation_path
        ).written
        annotation_bindings.append(
            ReleaseAnnotationBinding(
                replicas[0][0], system, annotation_path.relative_to(root).as_posix()
            )
        )
    publication_input = {
        "schema_version": PUBLICATION_INPUT_SCHEMA_VERSION,
        "kind": PUBLICATION_INPUT_KIND,
        "contact_definitions": [
            dict(
                replica_key=list(key),
                contact_definition_id=layer,
                contact_layer=layer,
                interaction_type=layer,
                parameters=contact_parameters(layer),
                source_artifact_role="accepted_contact_definition",
                source_artifact_path=f"contact-evidence/{layer}.json",
                units={"$/cutoff/value": "angstrom"},
            )
            for key in replicas
            for layer in ("protein-protein", "protein-lipid", "protein-glycan")
        ],
        "software_versions": [
            dict(
                dataset_id=replicas[0][0],
                source_artifact_path="qc/run_provenance.json",
                component_role=role,
                component_name=name,
                version=version,
                run_id=None,
                source_artifact_role="run_provenance",
            )
            for role, name, version in (
                ("package", "mania-wania", "0.1.0"),
                ("engine", "NAMD", None),
            )
        ],
        "metrics": [],
    }
    if not empty and outcomes[0] != "excluded":
        binding = next(b for b in canonical_bindings if b.family == "protein")
        source = canonical_io.read_canonical_protein_edge_window_csv(
            root / binding.path
        )
        row = next(r for r in source.rows if r.replica_id == "1")
        publication_input["metrics"].append(
            dict(
                **{
                    name: getattr(row, name)
                    for name in (
                        "dataset_id",
                        "system_id",
                        "trajectory_id",
                        "replica_id",
                        "window_id",
                        "window_index",
                    )
                },
                metric_id="window-metric",
                metric_name="explicit canonical occupancy",
                metric_value=row.occupancy,
                unit=None,
                source_artifact_role="canonical_protein_edge_window_table",
                source_artifact_path=binding.path,
                source_record_key=json.dumps(
                    row.row_identity, ensure_ascii=False, separators=(",", ":")
                ),
                source_value_field="occupancy",
            )
        )
    assert write_dataset_release_publication_inputs(
        publication_input, root / "publication_inputs.json"
    ).written

    def run_binding(directory, specs):
        return ReleaseUpstreamRun(
            f"{directory}/run_provenance.json",
            f"{directory}/artifact_inventory.json",
            tuple(
                ReleaseInputBinding(
                    s.artifact_id, s.local_path.relative_to(root).as_posix()
                )
                for s in specs
            ),
        )

    control = DatasetReleaseExportManifest(
        replicas[0][0],
        run_binding("qc", collect_dataset_qc_input_specs(qc_manifest, qc_path)),
        run_binding(
            "aggregation",
            collect_replica_aggregation_input_specs(derived, derived_path),
        ),
        "qc/dataset_qc_decision_set.json",
        "qc/dataset_qc_summary.csv",
        "qc/replica_aggregation_manifest_qc_derived.json",
        "qc/replica_aggregation_manifest_qc_derived.json",
        *(f"aggregation/{f.filename}" for f in FAMILIES),
        tuple(canonical_bindings),
        tuple(temporal_paths),
        tuple(annotation_bindings),
        "publication_inputs.json",
        tuple(
            r.replica_key
            for r in qc.outputs.decisions.records
            if r.release_decision == "available"
        ),
        tuple((replicas[0][0], system) for system in systems),
    )
    path = root / "dataset_release_export_manifest.json"
    assert write_dataset_release_export_manifest(control, path).written
    return path, control


def test_complete_release_build(tmp_path):
    path, _ = make_release_case(tmp_path)
    bundle = build_dataset_release(path)
    assert len(bundle.tables) == 17
    assert bundle.metadata.nodes.records()[329]["canonical_resname"] == "THR"
    assert bundle.metadata.simulations.row_count == 3
    assert bundle.metadata.residue_annotations.row_count == 690
    assert bundle.counts["excluded_simulation_count"] == 1
