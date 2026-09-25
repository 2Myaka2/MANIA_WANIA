"""Publication population, canonical identity and shared seven-table CSV surface."""

import builtins
import copy
import io
import socket
import subprocess
from dataclasses import FrozenInstanceError, asdict, fields, replace
from pathlib import Path

import pytest
from test_dataset_release_metadata import (
    complete_annotations,
    contact_table,
    decision,
    replica_key,
    temporal_evidence,
)

from mania import canonical_window_tables as canonical
from mania import dataset_release_science as science
from mania import replica_aggregation_tables as aggregate
from mania.dataset_qc_contract import DatasetQCDecisionSet
from mania.dataset_qc_summary import build_dataset_qc_summary
from mania.dataset_qc_workflow import build_qc_derived_replica_aggregation_manifest
from mania.dataset_release_aggregates import DatasetReleaseAggregationAuthority
from mania.dataset_release_contract import PUBLICATION_TABLE_SPECS
from mania.dataset_release_csv import (
    DatasetReleaseCSVError,
    build_publication_table,
    publication_csv_bytes,
    publication_number,
    read_publication_csv,
    write_publication_csv,
)
from mania.dataset_release_metadata import (
    QCDerivedAggregationEvidence,
    build_dataset_release_metadata_tables,
)
from mania.dataset_release_metrics import AuthoritativePublicationMetric
from mania.preprocessing.temporal_policy import LEGACY_BOUNDARY_PROFILE
from mania.replica_aggregation_contract import (
    REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID,
    REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256,
    ReplicaAggregationGroupSpec,
    ReplicaAggregationMember,
    ReplicaAggregationWindowDefinition,
)
from mania.replica_aggregation_manifest import (
    ReplicaAggregationManifest,
    ReplicaAggregationWorkflowGroup,
)
from mania.replica_specialized_aggregation import (
    ReplicaSpecializedPartnerCorrespondenceMember,
    SpecializedPartnerCorrespondence,
    SpecializedPartnerCorrespondences,
)

FAMILIES = ("protein", "lipid", "glycan")
SOURCE_TYPES = (
    canonical.CanonicalProteinEdgeWindowTable,
    canonical.CanonicalProteinLipidWindowTable,
    canonical.CanonicalProteinGlycanWindowTable,
)
SOURCE_ROWS = (
    canonical.CanonicalProteinEdgeWindowRow,
    canonical.CanonicalProteinLipidWindowRow,
    canonical.CanonicalProteinGlycanWindowRow,
)
AGGREGATE_TYPES = (
    aggregate.CanonicalProteinEdgeReplicaAggregationTable,
    aggregate.CanonicalProteinLipidReplicaAggregationTable,
    aggregate.CanonicalProteinGlycanReplicaAggregationTable,
)
AGGREGATE_ROWS = (
    aggregate.CanonicalProteinEdgeReplicaAggregationRow,
    aggregate.CanonicalProteinLipidReplicaAggregationRow,
    aggregate.CanonicalProteinGlycanReplicaAggregationRow,
)
BUILDERS = (
    science.build_dataset_release_protein_edges,
    science.build_dataset_release_protein_lipid_contacts,
    science.build_dataset_release_protein_glycan_contacts,
)


def damaged(model, **changes):
    """Controlled constructible malformed frozen model, without mutating inputs."""
    result = copy.copy(model)
    for name, value in changes.items():
        object.__setattr__(result, name, value)
    return result


def metric(replica="1", **changes):
    return AuthoritativePublicationMetric(
        **{
            **dict(
                zip(
                    ("dataset_id", "system_id", "trajectory_id", "replica_id"),
                    replica_key(replica),
                    strict=True,
                )
            ),
            "metric_id": "source-metric-01",
            "window_id": None,
            "window_index": None,
            "metric_name": "synthetic explicit measurement",
            "metric_value": 0.12345678901234567,
            "unit": None,
            "source_artifact_role": "accepted_scientific_metric",
            "source_artifact_path": "evidence/explicit_metrics.csv",
            "source_record_key": "supplied-row-17",
            **changes,
        }
    )


def make_science_case(
    tmp_path,
    *,
    outcomes=("available", "excluded", "available"),
    unavailable=(),
    selected=None,
    boundary_profile=LEGACY_BOUNDARY_PROFILE,
):
    """Small accepted models; no trajectory, evaluator or release assembly."""
    decisions = DatasetQCDecisionSet(
        tuple(
            decision(str(i), "fail" if outcome == "excluded" else "pass", outcome)
            for i, outcome in enumerate(outcomes, 1)
        )
    )
    executions = tuple(temporal_evidence(str(i), boundary_profile=boundary_profile)
        for i in range(1, len(outcomes) + 1))
    windows = executions[0].window_plan.windows[-2:]
    groups = []
    for w in windows:
        window = ReplicaAggregationWindowDefinition(
            w.window_id,
            w.window_index,
            0,
            1,
            w.requested_start_ns,
            w.requested_end_ns,
            w.right_endpoint_inclusive,
            0.4,
            0.2,
            50,
            boundary_profile=boundary_profile,
        )
        spec = ReplicaAggregationGroupSpec(
            "synthetic-33b",
            "T330M",
            "namd",
            "T330M",
            None,
            None,
            tuple(str(i) for i in range(1, len(outcomes) + 1)),
            window,
        )
        members = tuple(
            ReplicaAggregationMember(
                *d.replica_key,
                "T330M",
                "namd",
                None,
                None,
                REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID,
                REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256,
                window,
                "unavailable" if d.replica_id in unavailable else "available",
                "Accepted technical absence" if d.replica_id in unavailable else None,
            )
            for d in decisions.records
        )
        correspondences = tuple(
            SpecializedPartnerCorrespondences(
                (
                    SpecializedPartnerCorrespondence(
                        f"{kind}-correspondence",
                        kind,
                        f"synthetic-{kind}",
                        tuple(
                            ReplicaSpecializedPartnerCorrespondenceMember(
                                *m.replica_key,
                                f"{kind}:local:{m.replica_id}",
                                f"synthetic-{kind}",
                            )
                            for m in members
                            if m.availability_status == "available"
                        ),
                    ),
                )
            )
            if any(m.availability_status == "available" for m in members)
            else SpecializedPartnerCorrespondences(())
            for kind in ("lipid", "glycan")
        )
        groups.append(ReplicaAggregationWorkflowGroup(spec, members, *correspondences))
    template = ReplicaAggregationManifest(
        (tmp_path / "protein.csv",),
        (tmp_path / "lipid.csv",),
        (tmp_path / "glycan.csv",),
        tuple(groups),
    )
    derived = build_qc_derived_replica_aggregation_manifest(template, decisions)
    if selected is None:
        selected = tuple(
            d.replica_key
            for d in decisions.records
            if d.release_decision == "available"
        )
    metadata = build_dataset_release_metadata_tables(
        decisions=decisions,
        summary=build_dataset_qc_summary(decisions),
        aggregation_authority=QCDerivedAggregationEvidence(
            derived,
            decisions,
            "qc_derived_replica_aggregation_manifest",
            "qc/replica_aggregation_manifest_qc_derived.json",
        ),
        scientific_release_replica_keys=selected,
        annotation_publication_system_keys=(("synthetic-33b", "T330M"),),
        temporal_evidence=executions,
        annotation_metadata=(complete_annotations(),),
        contact_definitions=tuple(
            contact_table(k)
            for k in ("protein-protein", "protein-lipid", "protein-glycan")
        ),
        software_version_records=(),
    )
    sources = []
    aggregates = []
    for family, row_type, table_type, agg_row_type, agg_table_type in zip(
        FAMILIES,
        SOURCE_ROWS,
        SOURCE_TYPES,
        AGGREGATE_ROWS,
        AGGREGATE_TYPES,
        strict=True,
    ):
        rows = []
        for d in decisions.records:
            for w in windows:
                common = dict(
                    dataset_id=d.dataset_id,
                    system_id=d.system_id,
                    trajectory_id=d.trajectory_id,
                    replica_id=d.replica_id,
                    variant_id="T330M",
                    engine="namd",
                    condition=None,
                    disulfide_state=None,
                    window_id=w.window_id,
                    window_index=w.window_index,
                    requested_window_start_ns=w.requested_start_ns,
                    requested_window_end_ns=w.requested_end_ns,
                    right_endpoint_inclusive=w.right_endpoint_inclusive,
                    boundary_profile=boundary_profile,
                    effective_window_start_ns=w.effective_start_time_ps / 1000,
                    effective_window_end_ns=w.effective_end_time_ps / 1000,
                    requested_sample_count=w.requested_sample_count,
                    resolved_frame_count=w.sampled_frame_count,
                    missing_sample_count=w.missing_sample_count,
                    coverage_fraction=w.coverage_fraction,
                    n_contact_frames=2,
                    occupancy=2 / w.sampled_frame_count,
                    n_contact_episodes=1,
                    mean_episode_length_ns=0.123456789012345,
                    max_episode_length_ns=0.123456789012345,
                )
                if family == "protein":
                    common.update(
                        source_residue_index=10,
                        source_chain_id="A",
                        source_resid="312",
                        source_resname="GLN",
                        source_canonical_residue_number=312,
                        source_canonical_resname="ILE",
                        target_residue_index=20,
                        target_chain_id="A",
                        target_resid="330",
                        target_resname="MET",
                        target_canonical_residue_number=330,
                        target_canonical_resname="THR",
                        edge_type="contact",
                        edge_weight=common["occupancy"],
                    )
                else:
                    common.update(
                        protein_residue_index=20,
                        protein_chain_id="A",
                        protein_resid="330",
                        protein_resname="MET",
                        canonical_residue_number=330,
                        canonical_resname="THR",
                        distance_mean_A=3.123456789012345,
                        distance_min_A=2.987654321098765,
                    )
                    common.update(
                        {
                            f"{family}_partner_id": f"{family}:local:{d.replica_id}",
                            f"{family}_partner_name": f"synthetic-{family}",
                            f"{family}_component_residue_indexes": (40, 41),
                        }
                    )
                    if family == "glycan":
                        common.update(
                            carrier_residue_index=9,
                            first_sugar_residue_index=40,
                            linkage_evidence="external_metadata",
                            carrier_link_atom_index=None,
                            first_sugar_link_atom_index=None,
                        )
                rows.append(row_type(**common))
        sources.append(table_type(tuple(sorted(rows, key=lambda r: r.row_order))))
        agg_rows = []
        for g in derived.groups:
            n = sum(m.availability_status == "available" for m in g.members)
            if not n:
                continue
            values = {
                name: getattr(g.spec, name)
                for name in (
                    "dataset_id",
                    "system_id",
                    "engine",
                    "variant_id",
                    "condition",
                    "disulfide_state",
                )
            }
            values.update(g.spec.window.to_dict())
            values.update(
                mean_occupancy=0.6 if n == 1 else 0.3,
                median_occupancy=0.6 if n == 1 else 0.2,
                std_occupancy=None if n == 1 else 0.36055512754639896,
                n_replicates_available=n,
                n_replicates_supporting=min(2, n),
                support_fraction=min(2, n) / n,
            )
            if family == "protein":
                values.update(
                    source_canonical_residue_number=312,
                    source_canonical_resname="ILE",
                    target_canonical_residue_number=330,
                    target_canonical_resname="THR",
                    edge_type="contact",
                )
            else:
                values.update(
                    canonical_residue_number=330,
                    canonical_resname="THR",
                    partner_correspondence_id=f"{family}-correspondence",
                    partner_name=f"synthetic-{family}",
                )
            agg_rows.append(agg_row_type(**values))
        aggregates.append(
            agg_table_type(tuple(sorted(agg_rows, key=lambda r: r.row_order)))
        )
    inputs = dict(
        metadata_tables=metadata,
        canonical_protein_edges=sources[0],
        canonical_protein_lipid_contacts=sources[1],
        canonical_protein_glycan_contacts=sources[2],
        aggregation_authority=DatasetReleaseAggregationAuthority(
            decisions, derived, derived
        ),
        protein_aggregate_table=aggregates[0],
        lipid_aggregate_table=aggregates[1],
        glycan_aggregate_table=aggregates[2],
        metrics=(metric(),) if replica_key() in selected else (),
    )
    return inputs, template


@pytest.fixture(scope="module")
def case(tmp_path_factory):
    return make_science_case(tmp_path_factory.mktemp("science"))[0]


def source_for(case, index):
    return case[
        (
            "canonical_protein_edges",
            "canonical_protein_lipid_contacts",
            "canonical_protein_glycan_contacts",
        )[index]
    ]


@pytest.mark.parametrize("index", range(3))
def test_included_only_lossless_canonical_science(case, index):
    source = source_for(case, index)
    snapshot = copy.deepcopy(source)
    table = BUILDERS[index](source, metadata_tables=case["metadata_tables"])
    assert source == snapshot
    assert {r["replica_id"] for r in table.records()} == {"1", "3"}
    assert len(source.rows) == 6 and table.row_count == 4
    for output in table.records():
        upstream = next(
            r
            for r in source.rows
            if r.replica_id == output["replica_id"]
            and r.window_id == output["window_id"]
        )
        for name, value in output.items():
            assert value == (
                source.canonical_reference_id
                if name == "canonical_reference_id"
                else getattr(upstream, name)
            )
        if index == 0:
            assert upstream.target_resname == "MET"
            assert output["target_canonical_residue_number"] == 330
            assert output["target_canonical_resname"] == "THR"
            assert output["edge_weight"] == output["occupancy"]
        else:
            assert upstream.protein_resname == "MET"
            assert output["canonical_resname"] == "THR"
            assert "edge_weight" not in output
        assert not set(output) & {
            "source_chain_id",
            "source_resid",
            "source_resname",
            "source_residue_index",
            "protein_residue_index",
            "carrier_residue_index",
            "linkage_evidence",
            "is_ecd",
            "is_mx35_region",
            "qc_status",
            "release_decision",
        }
    metadata = case["metadata_tables"]
    assert metadata.simulations.row_count == metadata.quality_control.row_count == 3
    assert "2" in {r["replica_id"] for r in metadata.quality_control_evidence.records()}


@pytest.mark.parametrize("index", range(3))
def test_unknown_full_replica_key_fails_even_when_not_selected(case, index):
    source = source_for(case, index)
    for field, value in (
        ("trajectory_id", "unknown"),
        ("dataset_id", "unknown"),
        ("system_id", "unknown"),
        ("replica_id", "unknown"),
    ):
        row = replace(source.rows[0], **{field: value})
        with pytest.raises(science.DatasetReleaseScienceError, match="full replica"):
            BUILDERS[index](
                type(source)((row,)), metadata_tables=case["metadata_tables"]
            )


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize(
    "field", ["canonical_reference_id", "canonical_reference_sequence_sha256"]
)
def test_reference_mismatch_fails_even_for_empty_family(case, index, field):
    source = damaged(SOURCE_TYPES[index](()), **{field: "wrong"})
    with pytest.raises(ValueError, match="reference"):
        BUILDERS[index](source, metadata_tables=case["metadata_tables"])


@pytest.mark.parametrize("index", range(3))
def test_sparse_and_duplicate_and_exact_source_type(case, index):
    source = source_for(case, index)
    empty = BUILDERS[index](
        SOURCE_TYPES[index](()), metadata_tables=case["metadata_tables"]
    )
    assert empty.rows == ()
    assert publication_csv_bytes(empty).count(b"\n") == 1
    with pytest.raises(ValueError, match="Duplicate"):
        BUILDERS[index](
            damaged(source, rows=(source.rows[0],) * 2),
            metadata_tables=case["metadata_tables"],
        )
    with pytest.raises(ValueError, match="Stage 30"):
        BUILDERS[index](empty, metadata_tables=case["metadata_tables"])


def test_inconsistent_edge_weight_fails_without_repair(case):
    source = source_for(case, 0)
    row = damaged(source.rows[0], edge_weight=0.25)
    with pytest.raises(ValueError, match="edge_weight"):
        BUILDERS[0](
            damaged(source, rows=(row,)), metadata_tables=case["metadata_tables"]
        )
    assert row.edge_weight == 0.25


@pytest.mark.parametrize(
    "field,value",
    [
        ("window_id", "other"),
        ("window_index", 999),
        ("requested_window_start_ns", 0.3),
        ("right_endpoint_inclusive", True),
        ("resolved_frame_count", 42),
        ("target_canonical_residue_number", 691),
        ("target_canonical_resname", "MET"),
        ("condition", "same-system-other-label"),
    ],
)
def test_exact_window_node_and_metadata_relationships(case, field, value):
    source = source_for(case, 0)
    row = damaged(source.rows[0], **{field: value})
    with pytest.raises(ValueError):
        BUILDERS[0](
            damaged(source, rows=(row,)), metadata_tables=case["metadata_tables"]
        )


def test_technical_unavailable_can_publish_and_unselected_available_is_omitted(
    tmp_path,
):
    inputs, _ = make_science_case(
        tmp_path, unavailable=("3",), selected=(replica_key("3"),)
    )
    bundle = science.build_dataset_release_scientific_tables(**inputs)
    for table in bundle.tables[:3]:
        assert {r["replica_id"] for r in table.records()} == {"3"}
    for table in bundle.tables[3:6]:
        assert {r["n_replicates_available"] for r in table.records()} == {1}
    rows = {r["replica_id"]: r for r in inputs["metadata_tables"].simulations.records()}
    assert rows["3"]["included_in_scientific_release"] is True
    assert rows["3"]["included_in_replica_aggregation"] is False
    assert rows["3"]["release_decision"] == "available"
    assert rows["1"]["included_in_replica_aggregation"] is True


def test_all_seven_roundtrip_deterministic_bytes_and_input_immutability(case, tmp_path):
    snapshot = copy.deepcopy(case)
    bundles = tuple(
        science.build_dataset_release_scientific_tables(**case) for _ in range(2)
    )
    expected = {
        s.table_id
        for s in PUBLICATION_TABLE_SPECS
        if s.relative_path.startswith(("science/", "aggregates/", "metrics/"))
    }
    assert {t.table_id for t in bundles[0].tables} == expected
    assert len(bundles[0].tables) == 7
    assert case == snapshot and bundles[0] == bundles[1]
    with pytest.raises(FrozenInstanceError):
        bundles[0].metrics = None
    with pytest.raises(ValueError, match="slot"):
        replace(bundles[0], metrics=bundles[0].protein_edges_by_window)
    for a, b in zip(bundles[0].tables, bundles[1].tables, strict=True):
        pa = write_publication_csv(a, tmp_path / "a" / a.relative_path)
        pb = write_publication_csv(b, tmp_path / "b" / b.relative_path)
        assert pa.read_bytes() == pb.read_bytes()
        assert read_publication_csv(a.table_id, pa) == a
        assert read_publication_csv(b.table_id, pb) == b
        assert a.spec.columns == next(
            s.columns for s in PUBLICATION_TABLE_SPECS if s.table_id == a.table_id
        )
        with pytest.raises(DatasetReleaseCSVError, match="path"):
            write_publication_csv(a, tmp_path / "wrong.csv")
    assert bundles[0].to_dict() == bundles[1].to_dict()


def test_all_empty_bundle_keeps_seven_schemas(case, tmp_path):
    inputs = dict(case)
    for name in (
        "canonical_protein_edges",
        "canonical_protein_lipid_contacts",
        "canonical_protein_glycan_contacts",
        "protein_aggregate_table",
        "lipid_aggregate_table",
        "glycan_aggregate_table",
    ):
        inputs[name] = type(inputs[name])(())
    inputs["metrics"] = ()
    bundle = science.build_dataset_release_scientific_tables(**inputs)
    assert len(bundle.tables) == 7
    for table in bundle.tables:
        assert table.rows == ()
        path = write_publication_csv(table, tmp_path / table.relative_path)
        assert path.read_bytes().count(b"\n") == 1
        assert read_publication_csv(table.table_id, path) == table


def test_builders_are_pure_and_do_not_recompute_science(case, monkeypatch):
    snapshot = copy.deepcopy(case)

    def forbidden(*args, **kwargs):
        raise AssertionError("Publication must not access runtime or recompute science")

    with monkeypatch.context() as patch:
        for owner, names in (
            (builtins, ("open",)),
            (io, ("open",)),
            (Path, ("open", "resolve", "stat", "glob", "rglob", "iterdir")),
            (socket, ("socket", "create_connection")),
            (subprocess, ("run", "Popen", "check_output")),
        ):
            for name in names:
                patch.setattr(owner, name, forbidden)
        # Calling accepted scientific builders is forbidden even when their
        # outputs would equal the already supplied upstream models.
        from mania import (
            dataset_qc_workflow,
            replica_protein_edge_aggregation,
            replica_specialized_aggregation,
        )

        for module in (
            canonical,
            dataset_qc_workflow,
            replica_protein_edge_aggregation,
            replica_specialized_aggregation,
        ):
            for name in vars(module):
                if name.startswith(
                    ("aggregate_", "build_canonical_", "evaluate_", "build_qc_derived_")
                ):
                    patch.setattr(module, name, forbidden)
        bundle = science.build_dataset_release_scientific_tables(**case)
    assert bundle.metrics.row_count == 1 and case == snapshot


def test_numeric_projection_uses_exact_upstream_binary_value(case):
    bundle = science.build_dataset_release_scientific_tables(**case)
    for table in bundle.tables:
        source = case["metrics"][0] if table.table_id == "metrics" else None
        for column in table.spec.columns:
            if source is not None and column.logical_type == "number":
                assert table.records()[0][column.name] == publication_number(
                    getattr(source, column.name)
                )
    assert tuple(f.name for f in fields(AuthoritativePublicationMetric)) == tuple(
        c.name for c in bundle.metrics.spec.columns
    )
    assert asdict(case["metrics"][0])["source_record_key"] == "supplied-row-17"


def test_foreign_key_helper_rejects_missing_simulation(case):
    table = BUILDERS[0](source_for(case, 0), metadata_tables=case["metadata_tables"])
    metadata = damaged(
        case["metadata_tables"], simulations=build_publication_table("simulations", ())
    )
    with pytest.raises(ValueError, match="simulations.*foreign key"):
        science.validate_dataset_release_scientific_relationships((table,), metadata)
