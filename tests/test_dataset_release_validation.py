"""Defensive relationships across all 17 publication models and authority."""

from dataclasses import replace

import pytest
from test_dataset_release_science import damaged
from test_dataset_release_workflow import make_release_case

from mania.dataset_release_csv import build_publication_table
from mania.dataset_release_validation import validate_dataset_release_tables
from mania.dataset_release_workflow import build_dataset_release


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    path, _ = make_release_case(tmp_path_factory.mktemp("relationships"))
    return build_dataset_release(path)


@pytest.mark.parametrize(
    "table_id,field,value",
    [
        ("simulations", "system_id", "orphan"),
        ("simulations", "qc_status", "fail"),
        ("systems", "condition", "contradictory"),
        ("quality_control_findings", "replica_id", "unknown"),
        ("quality_control_evidence", "check_id", "unknown"),
        ("nodes", "canonical_resname", "MET"),
        ("residue_annotations", "system_id", "orphan"),
        ("residue_annotations", "canonical_residue_number", 691),
        ("protein_edges_by_window", "replica_id", "2"),
        ("protein_edges_by_window", "window_id", "other"),
        ("protein_edges_by_window", "window_index", 999),
        ("protein_edges_by_window", "target_canonical_resname", "MET"),
        ("protein_edges_by_window_replica_aggregation", "window_id", "other"),
        ("protein_edges_by_window_replica_aggregation", "n_replicates_available", 3),
        (
            "protein_lipid_contacts_by_window_replica_aggregation",
            "partner_correspondence_id",
            "unknown",
        ),
        (
            "protein_glycan_contacts_by_window_replica_aggregation",
            "partner_correspondence_id",
            "unknown",
        ),
        ("metrics", "replica_id", "2"),
        ("metrics", "window_index", 999),
    ],
)
def test_cross_table_mutation_fails(bundle, table_id, field, value):
    owner = bundle.metadata if hasattr(bundle.metadata, table_id) else bundle.science
    table = getattr(owner, table_id)
    rows = list(table.records())
    rows[329 if table_id == "nodes" else 0][field] = value
    with pytest.raises(ValueError):
        mutation = build_publication_table(table_id, rows)
        changed = damaged(owner, **{table_id: mutation})
        validate_dataset_release_tables(
            changed if owner is bundle.metadata else bundle.metadata,
            changed if owner is bundle.science else bundle.science,
            bundle.aggregation_authority,
            bundle.control,
        )


@pytest.mark.parametrize(
    "table_id",
    [
        "simulations",
        "quality_control",
        "quality_control_findings",
        "quality_control_evidence",
    ],
)
def test_excluded_history_cannot_be_removed(bundle, table_id):
    table = getattr(bundle.metadata, table_id)
    changed = damaged(
        bundle.metadata,
        **{
            table_id: build_publication_table(
                table_id, (r for r in table.records() if r["replica_id"] != "2")
            )
        },
    )
    with pytest.raises(ValueError):
        validate_dataset_release_tables(
            changed, bundle.science, bundle.aggregation_authority, bundle.control
        )


def test_annotation_coverage_and_sparse_artifact_requirement(bundle):
    rows = bundle.metadata.residue_annotations.records()[:-1]
    changed = damaged(
        bundle.metadata,
        residue_annotations=build_publication_table("residue_annotations", rows),
    )
    with pytest.raises(ValueError, match="690"):
        validate_dataset_release_tables(
            changed, bundle.science, bundle.aggregation_authority, bundle.control
        )
    control = replace(
        bundle.control,
        canonical_bindings=tuple(
            b for b in bundle.control.canonical_bindings if b.family != "lipid"
        ),
    )
    with pytest.raises(ValueError, match="coverage"):
        validate_dataset_release_tables(
            bundle.metadata, bundle.science, bundle.aggregation_authority, control
        )
