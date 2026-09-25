"""Stage 33.A schema acceptance and compatibility, without generating releases."""

import ast
import json
import subprocess
import sys
import tomllib
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from typing import get_args

import pytest

from mania import dataset_release_contract as release
from mania.biological_annotations import CanonicalVariantSiteAnnotation
from mania.canonical_reference_io import load_default_napi2b_canonical_reference
from mania.canonical_window_tables import (
    CanonicalProteinEdgeWindowRow,
    CanonicalProteinGlycanWindowRow,
    CanonicalProteinLipidWindowRow,
)
from mania.dataset_identity import DatasetTrajectoryIdentity
from mania.dataset_qc_contract import QCEvidenceRecord, ReplicaQCCheckResult
from mania.dataset_qc_summary import DatasetQCSummaryRow
from mania.replica_aggregation_tables import (
    CanonicalProteinEdgeReplicaAggregationRow,
    CanonicalProteinGlycanReplicaAggregationRow,
    CanonicalProteinLipidReplicaAggregationRow,
)

ROOT = Path(__file__).resolve().parents[1]
TABLES = {t.table_id: t for t in release.PUBLICATION_TABLE_SPECS}
EXPECTED_TABLE_PATHS = {
    "metadata/systems.csv",
    "metadata/simulations.csv",
    "metadata/time_windows.csv",
    "metadata/contact_definitions.csv",
    "metadata/software_versions.csv",
    "metadata/quality_control.csv",
    "metadata/quality_control_findings.csv",
    "metadata/quality_control_evidence.csv",
    "canonical/nodes.csv",
    "canonical/residue_annotations.csv",
    "science/protein_edges_by_window.csv",
    "science/protein_lipid_contacts_by_window.csv",
    "science/protein_glycan_contacts_by_window.csv",
    "aggregates/protein_edges_by_window_replica_aggregation.csv",
    "aggregates/protein_lipid_contacts_by_window_replica_aggregation.csv",
    "aggregates/protein_glycan_contacts_by_window_replica_aggregation.csv",
    "metrics/metrics.csv",
}
EXPECTED_JSON_PATHS = {
    "release/dataset_manifest.json",
    "release/artifact_inventory.json",
    "release/provenance.json",
}
REPLICA_KEY = ("dataset_id", "system_id", "trajectory_id", "replica_id")
WINDOW_KEY = (*REPLICA_KEY, "window_id", "window_index")


def columns(table):
    return {c.name: c for c in TABLES[table].columns}


def assert_projection(table, row_type, omitted=()):
    """Accepted scalar scientific values remain representable without type loss."""
    # D.4c retains one release-wide profile in the versioned release manifest.
    # The inclusive integration tests verify this authority without new CSV columns.
    omitted = (*omitted, "boundary_profile")
    published = columns(table)
    for field in fields(row_type):
        if field.name in omitted:
            continue
        assert field.name in published, field.name
        annotation = field.type
        nullable = type(None) in get_args(annotation)
        scalar = next(
            (a for a in get_args(annotation) if a is not type(None)), annotation
        )
        expected = {str: "string", int: "integer", float: "number", bool: "boolean"}
        if scalar in expected:
            assert published[field.name].logical_type == expected[scalar]
        assert published[field.name].nullable == nullable


def test_constants_reference_types_and_paths():
    assert (
        release.DATASET_RELEASE_CONTRACT_SCHEMA_VERSION
        == "mania.dataset_release_contract.v0.1"
    )
    assert release.DATASET_RELEASE_VERSION == "1.0"
    assert (
        release.DATASET_RELEASE_CANONICAL_REFERENCE_ID
        == "uniprotkb:O95436-1:sequence-v3"
    )
    assert release.DATASET_RELEASE_CANONICAL_REFERENCE_SHA256 == (
        "33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9"
    )
    assert get_args(release.PublicationArtifactClass) == (
        "control",
        "audit",
        "publication",
    )
    assert get_args(release.PublicationLogicalType) == (
        "string",
        "integer",
        "number",
        "boolean",
    )
    assert set(release.PUBLICATION_TABLE_PATHS) == EXPECTED_TABLE_PATHS
    assert set(release.REQUIRED_RELEASE_JSON_PATHS) == EXPECTED_JSON_PATHS
    artifacts = release.PUBLICATION_ARTIFACT_REGISTRY.artifacts
    assert len(artifacts) == 20
    assert len({a.artifact_id for a in artifacts}) == len(artifacts)
    assert len({a.relative_path for a in artifacts}) == len(artifacts)
    assert all(a.artifact_class == "publication" and a.required for a in artifacts)
    assert tuple(a.relative_path for a in artifacts) == tuple(
        sorted(EXPECTED_TABLE_PATHS | EXPECTED_JSON_PATHS)
    )
    assert release.PublicationArtifactRegistry(tuple(reversed(artifacts))) == (
        release.PUBLICATION_ARTIFACT_REGISTRY
    )


@pytest.mark.parametrize(
    "descriptor",
    [
        TABLES["systems"].columns[0],
        TABLES["systems"],
        TABLES["simulations"].foreign_keys[0],
        release.PUBLICATION_ARTIFACT_REGISTRY,
        release.PUBLICATION_ARTIFACT_REGISTRY.artifacts[0],
        release.PublicationJSONSpec(("dataset_id",), "Identity."),
    ],
)
def test_all_public_descriptors_frozen(descriptor):
    with pytest.raises(FrozenInstanceError):
        setattr(descriptor, fields(descriptor)[0].name, None)


def test_deterministic_serialization_is_detached_and_finite():
    first = release.dataset_release_contract_to_dict()
    encoded = json.dumps(
        first, allow_nan=False, ensure_ascii=False, separators=(",", ":")
    )
    assert encoded == json.dumps(
        release.dataset_release_contract_to_dict(),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    first["registry"]["artifacts"][0]["logical_schema"]["columns"][0]["name"] = (
        "changed"
    )
    assert encoded == json.dumps(
        release.dataset_release_contract_to_dict(),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"name": ""},
        {"name": "  "},
        {"name": " id"},
        {"logical_type": "float64"},
        {"logical_type": "array"},
        {"nullable": 1},
        {"description": ""},
    ],
)
def test_bad_columns_rejected(changes):
    with pytest.raises(ValueError):
        replace(TABLES["systems"].columns[0], **changes)


@pytest.mark.parametrize(
    "key", [(), ("dataset_id", "dataset_id"), ("missing",), ("condition",)]
)
def test_bad_primary_keys_rejected(key):
    with pytest.raises(ValueError):
        replace(TABLES["systems"], primary_key=key)


@pytest.mark.parametrize(
    "path",
    [
        "/absolute.csv",
        "../escape.csv",
        "metadata/../escape.csv",
        "./systems.csv",
        "metadata//systems.csv",
        "metadata/",
        r"metadata\systems.csv",
        "C:/systems.csv",
        "~/systems.csv",
        "~user/systems.csv",
        "metadata/\x00systems.csv",
        "",
        "metadata/\nsystems.csv",
    ],
)
def test_nonportable_paths_rejected(path):
    with pytest.raises(ValueError):
        replace(TABLES["systems"], relative_path=path)
    with pytest.raises(ValueError):
        replace(release.PUBLICATION_ARTIFACT_REGISTRY.artifacts[-1], relative_path=path)


@pytest.mark.parametrize(
    "changes",
    [
        {"local_columns": ()},
        {"local_columns": ("a", "a")},
        {"local_columns": ("missing",)},
        {"target_columns": ("a", "a")},
        {"target_columns": ()},
        {"target_table": ""},
    ],
)
def test_bad_foreign_key_descriptors_rejected(changes):
    with pytest.raises(ValueError):
        replace(TABLES["simulations"].foreign_keys[0], **changes)


def test_table_validation_rejects_duplicate_columns_keys_and_mutable_inputs():
    table = TABLES["simulations"]
    for changes in (
        {"columns": (*table.columns, table.columns[0])},
        {"columns": ()},
        {"columns": list(table.columns)},
        {"foreign_keys": list(table.foreign_keys)},
        {"foreign_keys": (*table.foreign_keys, table.foreign_keys[0])},
        {
            "foreign_keys": (
                release.PublicationForeignKeySpec(("missing",), "nodes", ("id",)),
            )
        },
        {"primary_key": list(table.primary_key)},
        {"required": 1},
        {"artifact_class": "intermediate"},
        {"table_id": ""},
    ):
        with pytest.raises(ValueError):
            replace(table, **changes)


def test_registry_rejects_duplicate_ids_paths_and_invalid_targets():
    registry = release.PUBLICATION_ARTIFACT_REGISTRY
    with pytest.raises(ValueError, match="duplicates"):
        release.PublicationArtifactRegistry(
            (*registry.artifacts, registry.artifacts[0])
        )
    json_artifact = next(
        a for a in registry.artifacts if a.mandatory_encoding == "json"
    )
    with pytest.raises(ValueError, match="duplicates"):
        release.PublicationArtifactRegistry(
            (*registry.artifacts, replace(json_artifact, artifact_id="different"))
        )
    with pytest.raises(ValueError, match="primary key"):
        release.PublicationArtifactRegistry(
            tuple(a for a in registry.artifacts if a.artifact_id != "nodes")
        )
    for target_columns in (("dataset_id", "missing"), ("system_id", "dataset_id")):
        table = replace(
            TABLES["simulations"],
            foreign_keys=(
                release.PublicationForeignKeySpec(
                    ("dataset_id", "system_id"), "systems", target_columns
                ),
            ),
        )
        artifacts = tuple(
            replace(a, logical_schema=table) if a.artifact_id == "simulations" else a
            for a in registry.artifacts
        )
        with pytest.raises(ValueError, match="primary key"):
            release.PublicationArtifactRegistry(artifacts)
    table = replace(
        TABLES["systems"],
        columns=tuple(
            replace(c, logical_type="integer") if c.name == "system_id" else c
            for c in TABLES["systems"].columns
        ),
    )
    with pytest.raises(ValueError, match="types must match"):
        release.PublicationArtifactRegistry(
            tuple(
                replace(a, logical_schema=table) if a.artifact_id == "systems" else a
                for a in registry.artifacts
            )
        )


def test_artifact_encoding_validation():
    table_artifact = release.PUBLICATION_ARTIFACT_REGISTRY.artifacts[0]
    for changes in (
        {"artifact_id": "mismatch"},
        {"mandatory_encoding": "parquet"},
        {"optional_encodings": ("csv",)},
        {"optional_encodings": ("parquet", "parquet")},
        {"required_lineage": ("x", "x")},
        {"required": False},
        {"artifact_class": "audit"},
        {"logical_schema": {}},
    ):
        with pytest.raises(ValueError):
            replace(table_artifact, **changes)
    artifact = next(
        a
        for a in release.PUBLICATION_ARTIFACT_REGISTRY.artifacts
        if a.mandatory_encoding == "json"
    )
    for changes in (
        {"mandatory_encoding": "csv"},
        {"optional_encodings": ("parquet",)},
        {"relative_path": "release/wrong.csv"},
    ):
        with pytest.raises(ValueError):
            replace(artifact, **changes)


def test_systems_and_all_candidate_simulations_use_authoritative_identity():
    assert TABLES["systems"].primary_key == ("dataset_id", "system_id")
    assert TABLES["simulations"].primary_key == REPLICA_KEY
    for table in ("systems", "simulations"):
        assert columns(table)["condition"].nullable
        assert columns(table)["disulfide_state"].nullable
        assert not columns(table)["variant_id"].nullable
    identity = DatasetTrajectoryIdentity(
        dataset_id="d",
        system_id="s",
        trajectory_id="t",
        replica_id="r",
        variant_id="T330M",
        engine="namd",
        condition=None,
    )
    assert identity.replica_key == ("d", "s", "t", "r")
    assert identity.condition is None
    assert all("condition" not in table.primary_key for table in TABLES.values())


def test_excluded_replica_can_be_represented_with_full_decision_history():
    excluded = {
        "dataset_id": "d",
        "system_id": "s",
        "trajectory_id": "t",
        "replica_id": "r",
        "engine": "namd",
        "variant_id": "T330M",
        "condition": None,
        "disulfide_state": None,
        "qc_status": "fail",
        "release_decision": "excluded",
        "decision_mode": "automatic",
        "decision_reason_code": "TRAJECTORY_UNREADABLE",
        "human_readable_reason": "Authoritative hard-QC failure.",
        "aggregation_availability_status": "excluded",
        "aggregation_availability_reason": "Authoritative hard-QC failure.",
        "included_in_scientific_release": False,
        "included_in_replica_aggregation": False,
    }
    assert set(excluded) == set(columns("simulations"))
    for name, value in excluded.items():
        spec = columns("simulations")[name]
        assert value is not None or spec.nullable
    rules = " ".join(release.PUBLICATION_POPULATION_RULES)
    for phrase in (
        "All production candidate replicas",
        "simulations, QC and provenance",
        "required per-replica scientific evidence",
        "technically unavailable",
        "missing technical science does not become QC exclusion",
        "Excluded replicas never enter the denominator",
    ):
        assert phrase in rules


def test_time_windows_separate_physical_request_from_observation():
    assert TABLES["time_windows"].primary_key == WINDOW_KEY
    cols = columns("time_windows")
    assert {
        "requested_production_start_ns",
        "requested_production_end_ns",
        "requested_window_start_ns",
        "requested_window_end_ns",
        "right_endpoint_inclusive",
        "window_length_ns",
        "window_step_ns",
        "overlap_percent",
        "frame_stride_ps",
        "expected_sample_count",
        "resolved_sample_count",
        "missing_sample_count",
        "coverage_fraction",
        "effective_start_ns",
        "effective_end_ns",
    } <= cols.keys()
    assert cols["effective_start_ns"].nullable and cols["effective_end_ns"].nullable
    assert not cols["requested_window_start_ns"].nullable


def test_normalized_qc_preserves_accepted_summary_findings_and_evidence():
    assert_projection("quality_control", DatasetQCSummaryRow)
    assert TABLES["quality_control"].primary_key == REPLICA_KEY
    assert TABLES["quality_control_findings"].primary_key == (*REPLICA_KEY, "check_id")
    assert TABLES["quality_control_evidence"].primary_key == (
        *REPLICA_KEY,
        "check_id",
        "evidence_id",
    )
    assert {f.name for f in fields(ReplicaQCCheckResult)} - {"evidence"} <= (
        columns("quality_control_findings").keys()
    )
    assert_projection("quality_control_evidence", QCEvidenceRecord)
    assert (
        "decision_evidence_ids"
        in columns("quality_control_evidence")["used_for_decision"].description
    )
    assert columns("quality_control")["review_qc_status"].nullable
    assert columns("quality_control")["reviewer"].nullable
    assert (
        "including PASS" in columns("quality_control_findings")["check_id"].description
    )
    assert "evidence_id" not in columns("quality_control_findings")


def test_nodes_and_annotations_preserve_reference_and_system_evidence():
    reference = load_default_napi2b_canonical_reference()
    assert release.CANONICAL_NODE_COUNT == len(reference.sequence) == 690
    assert release.CANONICAL_RESIDUE_RANGE == (1, 690)
    assert reference.residue_at(330).canonical_resname == "THR"
    assert TABLES["nodes"].primary_key == (
        "canonical_reference_id",
        "canonical_residue_number",
    )
    assert TABLES["residue_annotations"].primary_key == (
        "dataset_id",
        "system_id",
        "canonical_residue_number",
    )
    cols = columns("residue_annotations")
    assert {
        "canonical_resname",
        "annotation_scope",
        "is_ecd",
        "is_mx35_region",
        "is_glycosylation_site",
        "glycosylation_present_in_topology",
        "glycan_name",
        "glycosylation_source",
        "glycosylation_verifier",
        "is_disulfide_variant_site",
        "is_cysteine_variant_site",
    } <= cols.keys()
    assert {"source", "verifier"} <= {
        f.name for f in fields(CanonicalVariantSiteAnnotation)
    }
    for kind in ("disulfide", "cysteine"):
        assert cols[f"{kind}_variant_source"].nullable
        assert cols[f"{kind}_variant_verifier"].nullable
    assert "complete_for_system" in cols["annotation_scope"].description


def test_protein_science_is_lossless_canonical_projection():
    omitted = {
        f"{side}_{suffix}"
        for side in ("source", "target")
        for suffix in ("residue_index", "chain_id", "resid", "resname")
    }
    assert_projection("protein_edges_by_window", CanonicalProteinEdgeWindowRow, omitted)
    cols = columns("protein_edges_by_window")
    assert omitted.isdisjoint(cols)
    assert "source_engine" not in cols
    assert {
        "n_contact_frames",
        "resolved_frame_count",
        "occupancy",
        "edge_weight",
        "n_contact_episodes",
        "mean_episode_length_ns",
        "max_episode_length_ns",
    } <= cols.keys()
    assert "source_canonical_residue_number" in cols
    assert "target_canonical_residue_number" in cols
    assert "canonical 330 THR" in " ".join(release.SCIENTIFIC_PUBLICATION_RULES)
    assert "creates no all-pairs zero edges" in " ".join(
        release.SCIENTIFIC_PUBLICATION_RULES
    )


@pytest.mark.parametrize(
    "kind,row_type",
    [
        ("lipid", CanonicalProteinLipidWindowRow),
        ("glycan", CanonicalProteinGlycanWindowRow),
    ],
)
def test_specialized_science_preserves_metrics_and_local_partners(kind, row_type):
    omitted = {
        "protein_residue_index",
        "protein_chain_id",
        "protein_resid",
        "protein_resname",
        f"{kind}_component_residue_indexes",
        "carrier_residue_index",
        "first_sugar_residue_index",
        "linkage_evidence",
        "carrier_link_atom_index",
        "first_sugar_link_atom_index",
    }
    name = f"protein_{kind}_contacts_by_window"
    assert_projection(name, row_type, omitted)
    assert "edge_weight" not in columns(name)
    assert "Topology-local" in columns(name)[f"{kind}_partner_id"].description
    assert (
        "contact-positive frames only" in columns(name)["distance_mean_A"].description
    )
    assert "never reenter ordinary contact summaries" in " ".join(
        release.SCIENTIFIC_PUBLICATION_RULES
    )


@pytest.mark.parametrize(
    "name,row_type",
    [
        (
            "protein_edges_by_window_replica_aggregation",
            CanonicalProteinEdgeReplicaAggregationRow,
        ),
        (
            "protein_lipid_contacts_by_window_replica_aggregation",
            CanonicalProteinLipidReplicaAggregationRow,
        ),
        (
            "protein_glycan_contacts_by_window_replica_aggregation",
            CanonicalProteinGlycanReplicaAggregationRow,
        ),
    ],
)
def test_aggregates_preserve_exact_stage31_fields_and_lineage(name, row_type):
    assert_projection(name, row_type)
    cols = columns(name)
    assert {
        "mean_occupancy",
        "std_occupancy",
        "median_occupancy",
        "n_replicates_available",
        "n_replicates_supporting",
        "support_fraction",
    } <= cols.keys()
    assert {
        "trajectory_id",
        "replica_id",
        "edge_weight",
        "n_contact_frames",
    }.isdisjoint(cols)
    assert not any("distance" in n or "episode" in n or "lifetime" in n for n in cols)
    assert cols["std_occupancy"].nullable
    artifact = next(
        a
        for a in release.PUBLICATION_ARTIFACT_REGISTRY.artifacts
        if a.artifact_id == name
    )
    assert artifact.required_lineage == release.AGGREGATE_PUBLICATION_REQUIRED_LINEAGE
    assert len(artifact.required_lineage) == 3
    if "contacts" in name:
        assert (
            "not canonical/chemical/cross-system ID"
            in cols["partner_correspondence_id"].description
        )


def test_metrics_contact_parameters_and_software_are_explicit_and_lossless():
    metrics = columns("metrics")
    assert {
        "metric_name",
        "metric_value",
        "unit",
        "source_artifact_role",
        "source_artifact_path",
        "window_id",
        "window_index",
    } <= metrics.keys()
    assert metrics["window_id"].nullable and metrics["window_index"].nullable
    assert TABLES["metrics"].primary_key == (*REPLICA_KEY, "metric_id")
    assert "no closed vocabulary" in metrics["metric_name"].description
    contact = columns("contact_definitions")
    assert {
        "contact_layer",
        "interaction_type",
        "parameter_path",
        "parameter_kind",
        "string_value",
        "integer_value",
        "number_value",
        "boolean_value",
    } <= contact.keys()
    for kind in ("string", "integer", "number", "boolean"):
        assert contact[f"{kind}_value"].logical_type == kind
        assert contact[f"{kind}_value"].nullable
    assert "preserves empty containers" in contact["parameter_kind"].description
    assert columns("software_versions")["version"].nullable
    assert {
        "component_role",
        "component_name",
        "source_artifact_role",
        "source_artifact_path",
    } <= (columns("software_versions").keys())


def test_required_foreign_keys_and_nonnullable_primary_keys():
    targets = {
        "simulations": {"systems", "quality_control"},
        "time_windows": {"simulations"},
        "quality_control": {"simulations"},
        "quality_control_findings": {"quality_control"},
        "quality_control_evidence": {"quality_control_findings"},
        "residue_annotations": {"systems", "nodes"},
    }
    for name, table in TABLES.items():
        assert all(not columns(name)[n].nullable for n in table.primary_key)
        if table.relative_path.startswith("science/"):
            targets[name] = {"simulations", "time_windows", "nodes"}
        if table.relative_path.startswith("aggregates/"):
            targets[name] = {"systems", "nodes"}
    for name, expected in targets.items():
        assert {fk.target_table for fk in TABLES[name].foreign_keys} == expected


def test_production_dag_manifest_and_pre_qc_authority_boundary():
    assert release.DEVELOPMENT_ORDER == ("27", "28", "29", "30", "31", "32", "33")
    assert release.PRODUCTION_EXECUTION_DAG == (
        "stage27_30_per_replica_science",
        "stage32_authoritative_qc_decisions",
        "stage32_qc_derived_stage31_manifest",
        "stage31_replica_aggregation",
        "stage33_publication",
    )
    artifacts = {
        a.artifact_id: a for a in release.PUBLICATION_ARTIFACT_REGISTRY.artifacts
    }
    manifest = artifacts["dataset_manifest"].logical_schema
    assert {
        "production_dag_id",
        "authoritative_stage32_qc_decision_source",
        "authoritative_qc_derived_stage31_manifest_source",
        "authoritative_stage31_aggregation_run_source",
        "publication_artifacts",
    } <= set(manifest.required_fields)
    assert (
        "candidate_replica_lineage"
        in artifacts["provenance"].logical_schema.required_fields
    )
    assert "pre-QC Stage 31 aggregate is not publication-authoritative" in " ".join(
        release.PUBLICATION_POPULATION_RULES
    )


def test_formats_null_booleans_and_dependency_boundary():
    for artifact in release.PUBLICATION_ARTIFACT_REGISTRY.artifacts:
        if isinstance(artifact.logical_schema, release.PublicationTableSpec):
            assert artifact.mandatory_encoding == "csv"
            assert artifact.optional_encodings == ("parquet",)
        else:
            assert artifact.mandatory_encoding == "json"
            assert artifact.optional_encodings == ()
    rules = " ".join(release.SERIALIZATION_RULES)
    for phrase in (
        "Logical null is None",
        "CSV uses a blank cell",
        "JSON null",
        "Parquet native null",
        "lowercase true/false",
        "No rounding or recalculation",
        "round-trip losslessly",
        "equal logical models",
        "optional-adapter error",
    ):
        assert phrase in rules
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    dependencies = metadata["project"]["dependencies"] + [
        dependency
        for group in metadata["project"]["optional-dependencies"].values()
        for dependency in group
    ]
    assert not any(
        name in dep.lower()
        for dep in dependencies
        for name in ("pandas", "pyarrow", "fastparquet")
    )
    tree = ast.parse((ROOT / "src/mania/dataset_release_contract.py").read_text())
    imports = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert imports == {"dataclasses", "typing", "mania.canonical_reference"}
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))


def test_documented_contact_parameters_and_artifact_class_boundaries():
    text = " ".join((ROOT / "docs/dataset_release_contract.md").read_text().split())
    for path in EXPECTED_TABLE_PATHS | EXPECTED_JSON_PATHS:
        assert path in text
    assert release.CONTACT_DEFINITION_REQUIRED_PARAMETERS == (
        "atom_selections",
        "distance_definition",
        "cutoff",
        "type_specific_parameters",
        "pbc_correction_status",
        "occupancy_denominator_semantics",
        "episode_continuity_semantics",
        "gap_tolerance",
        "lifetime_semantics",
        "specialized_distance_semantics",
    )
    for name in release.CONTACT_DEFINITION_REQUIRED_PARAMETERS:
        assert name in text
    for phrase in (
        "trajectory_parameters.csv",
        "not automatically `simulations.csv`",
        "replica_aggregation_manifest.json",
        "dataset_qc_manifest.json",
        "dataset_qc_decision_set.json",
        "Intermediate/audit canonical science",
        "Hydrogen bond",
        "angle ≥120°",
        "**strict** distance `<6.0 Å`",
        "empty containers",
        "missing-value",
        "source_record_key",
    ):
        if phrase == "missing-value":
            assert phrase in " ".join(release.SERIALIZATION_RULES)
        else:
            assert phrase in text


@pytest.mark.parametrize("names", [(), ("id", "id"), ("",), ["id"]])
def test_invalid_hierarchical_requirements_rejected(names):
    with pytest.raises(ValueError):
        release.PublicationJSONSpec(names, "Release identity.")


# Also executed against the installed wheel, outside the checkout. Interpreter
# module loading is allowed; contract operations after import deny filesystem I/O.
OFFLINE_CONTRACT_SMOKE = r"""
import builtins
import importlib.abc
import io
import json
import os
import sys
import time


class Blocked(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {
            "socket",
            "urllib",
            "requests",
            "subprocess",
            "git",
            "MDAnalysis",
            "pandas",
            "pyarrow",
            "fastparquet",
            "uuid",
        }:
            raise ImportError("Blocked dependency: " + fullname)


def denied(*args, **kwargs):
    raise AssertionError("Forbidden external operation")


sys.meta_path.insert(0, Blocked())
sys.dont_write_bytecode = True
import mania.dataset_release_contract as c

module_location = c.__file__
builtins.open = io.open = os.open = os.stat = os.listdir = os.scandir = denied
os.system = os.getenv = time.time = time.monotonic = time.perf_counter = denied


def audit(event, args):
    if event.startswith(("socket.", "subprocess.", "os.spawn", "os.exec")):
        denied()


sys.addaudithook(audit)
assert (
    c.PublicationArtifactRegistry(c.PUBLICATION_ARTIFACT_REGISTRY.artifacts)
    == c.PUBLICATION_ARTIFACT_REGISTRY
)
payload = c.dataset_release_contract_to_dict()
assert len(c.PUBLICATION_TABLE_PATHS) == 17
assert set(c.PUBLICATION_TABLE_PATHS) == {
    "metadata/systems.csv",
    "metadata/simulations.csv",
    "metadata/time_windows.csv",
    "metadata/contact_definitions.csv",
    "metadata/software_versions.csv",
    "metadata/quality_control.csv",
    "metadata/quality_control_findings.csv",
    "metadata/quality_control_evidence.csv",
    "canonical/nodes.csv",
    "canonical/residue_annotations.csv",
    "science/protein_edges_by_window.csv",
    "science/protein_lipid_contacts_by_window.csv",
    "science/protein_glycan_contacts_by_window.csv",
    "aggregates/protein_edges_by_window_replica_aggregation.csv",
    "aggregates/protein_lipid_contacts_by_window_replica_aggregation.csv",
    "aggregates/protein_glycan_contacts_by_window_replica_aggregation.csv",
    "metrics/metrics.csv",
}
assert set(c.REQUIRED_RELEASE_JSON_PATHS) == {
    "release/dataset_manifest.json",
    "release/artifact_inventory.json",
    "release/provenance.json",
}
assert c.PRODUCTION_EXECUTION_DAG == (
    "stage27_30_per_replica_science",
    "stage32_authoritative_qc_decisions",
    "stage32_qc_derived_stage31_manifest",
    "stage31_replica_aggregation",
    "stage33_publication",
)
tables = {t.table_id: t for t in c.PUBLICATION_TABLE_SPECS}
replica_key = ("dataset_id", "system_id", "trajectory_id", "replica_id")
assert tables["simulations"].primary_key == replica_key
assert {
    "qc_status",
    "release_decision",
    "decision_reason_code",
    "human_readable_reason",
    "included_in_scientific_release",
    "included_in_replica_aggregation",
} <= {col.name for col in tables["simulations"].columns}
assert tables["quality_control"].primary_key == replica_key
assert tables["quality_control_findings"].primary_key == (*replica_key, "check_id")
assert tables["quality_control_evidence"].primary_key == (
    *replica_key,
    "check_id",
    "evidence_id",
)
assert tables["nodes"].primary_key == (
    "canonical_reference_id",
    "canonical_residue_number",
)
assert tables["residue_annotations"].primary_key == (
    "dataset_id",
    "system_id",
    "canonical_residue_number",
)
assert c.CANONICAL_NODE_COUNT == 690
for artifact in c.PUBLICATION_ARTIFACT_REGISTRY.artifacts:
    if artifact.relative_path.startswith("aggregates/"):
        assert artifact.required_lineage == c.AGGREGATE_PUBLICATION_REQUIRED_LINEAGE
        assert len(artifact.required_lineage) == 3
    if artifact.mandatory_encoding == "csv":
        assert artifact.optional_encodings == ("parquet",)
assert json.dumps(payload, allow_nan=False) == json.dumps(
    c.dataset_release_contract_to_dict(), allow_nan=False
)
print(
    "Offline contract smoke: PASS; 17 CSV + 3 JSON, DAG, history, QC, canonical, "
    "lineage, optional Parquet, deterministic; operations deny "
    "filesystem/network/Git/subprocess/clock."
)
print("Imported:", module_location)
"""


def test_contract_import_and_operations_without_external_capabilities():
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; sys.path.insert(0, sys.argv[1])\n" + OFFLINE_CONTRACT_SMOKE,
            str(ROOT / "src"),
        ],
        cwd=ROOT.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Offline contract smoke: PASS" in completed.stdout
