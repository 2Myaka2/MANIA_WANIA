"""Stage 32.B synthetic evidence, exact thresholds and authority boundaries."""

import ast
import builtins
import copy
import inspect
import io
import json
import os
import socket
import subprocess
import time
from dataclasses import FrozenInstanceError, asdict, fields, replace
from decimal import Decimal, Inexact, localcontext
from pathlib import Path
from typing import get_args

import pytest

from mania import dataset_hard_qc as qc
from mania.canonical_residue_mapping import (
    CanonicalResidueMappingRecord,
    CanonicalResidueMappingTable,
)
from mania.canonical_window_tables import (
    CanonicalProteinEdgeWindowRow,
    CanonicalProteinEdgeWindowTable,
    CanonicalProteinGlycanWindowRow,
    CanonicalProteinGlycanWindowTable,
    CanonicalProteinLipidWindowRow,
    CanonicalProteinLipidWindowTable,
    DatasetCanonicalResidueMappingBinding,
)
from mania.dataset_identity import DatasetTemporalParameters, DatasetTrajectoryIdentity
from mania.dataset_qc_contract import QCEvidenceRecord, ReplicaQCCheckResult
from mania.preprocessing.physical_time_sampling import (
    PhysicalTimeSourceFrame,
    resolve_physical_time_sampling,
)

KEY = ("synthetic", "T330M", "trajectory", "1")
SOURCE_KEY = ("gromacs", "A", "330", "MET")
FAMILIES = ("protein_edge", "protein_lipid", "protein_glycan")
TABLE_TYPES = (
    CanonicalProteinEdgeWindowTable,
    CanonicalProteinLipidWindowTable,
    CanonicalProteinGlycanWindowTable,
)


def evidence(name="observation", kind="metric"):
    return QCEvidenceRecord(
        name,
        kind,
        None,
        None,
        None,
        name,
        "explicit synthetic observation",
        None,
        "Synthetic authoritative evidence supplied by the test.",
    )


def identity(**changes):
    return DatasetTrajectoryIdentity(
        **dict(
            dataset_id=KEY[0],
            system_id=KEY[1],
            trajectory_id=KEY[2],
            replica_id=KEY[3],
            variant_id="T330M",
            engine="gromacs",
            condition=None,
        )
        | changes
    )


def raw(**changes):
    return qc.ReplicaRawIntegrityEvidence(
        **dict(
            topology_readable=True,
            trajectory_readable=True,
            topology_atom_count=10000,
            trajectory_atom_count=10000,
            atom_order_consistent=True,
            atom_universe_id="all_atoms",
            topology_evidence=evidence("topology"),
            trajectory_evidence=evidence("trajectory"),
            atom_order_evidence=evidence("order"),
        )
        | changes
    )


def mapping(records=None, **changes):
    if records is None:
        records = (CanonicalResidueMappingRecord(*SOURCE_KEY, 330, "THR", "mapped"),)
    return DatasetCanonicalResidueMappingBinding(
        **dict(
            dataset_id=KEY[0],
            system_id=KEY[1],
            trajectory_id=KEY[2],
            replica_id=KEY[3],
            mapping_table=CanonicalResidueMappingTable(records),
        )
        | changes
    )


def plan(expected=100, resolved=100, extra=0, times=None):
    # Closed Stage 27 production grid: 101 samples is 50..100 ns by 500 ps.
    temporal = DatasetTemporalParameters(
        production_start_ns=50,
        production_end_ns=50 + (expected - 1) * 0.5,
        frame_stride_ps=500,
        window_length_ns=0.5,
        window_step_ns=0.5,
        overlap_percent=0,
    )
    if times is None:
        times = [50000 + i * 500 for i in range(resolved)]
        times += [150000 + i * 500 for i in range(extra)]
    return resolve_physical_time_sampling(
        tuple(PhysicalTimeSourceFrame(i, float(t)) for i, t in enumerate(times)),
        temporal=temporal,
    )


def row(family="protein_edge", **changes):
    common = dict(
        dataset_id=KEY[0],
        system_id=KEY[1],
        trajectory_id=KEY[2],
        replica_id=KEY[3],
        variant_id="T330M",
        engine="gromacs",
        condition=None,
        disulfide_state=None,
        window_id="window_0001",
        window_index=0,
        requested_window_start_ns=50.0,
        requested_window_end_ns=50.5,
        right_endpoint_inclusive=False,
        effective_window_start_ns=50.0,
        effective_window_end_ns=50.4,
        requested_sample_count=5,
        resolved_frame_count=4,
        missing_sample_count=1,
        coverage_fraction=0.8,
        n_contact_frames=2,
        occupancy=0.5,
        n_contact_episodes=1,
        mean_episode_length_ns=0.05,
        max_episode_length_ns=0.05,
    )
    if family == "protein_edge":
        common.update(
            source_residue_index=10,
            source_chain_id="A",
            source_resid="311",
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
            edge_weight=0.5,
        )
        cls = CanonicalProteinEdgeWindowRow
    else:
        partner = "lipid" if family == "protein_lipid" else "glycan"
        common.update(
            protein_residue_index=20,
            protein_chain_id="A",
            protein_resid="330",
            protein_resname="MET",
            canonical_residue_number=330,
            canonical_resname="THR",
            distance_mean_A=3.5,
            distance_min_A=3.0,
        )
        common.update(
            {
                f"{partner}_partner_id": "330",
                f"{partner}_partner_name": "synthetic",
                f"{partner}_component_residue_indexes": (40, 41),
            }
        )
        cls = CanonicalProteinLipidWindowRow
        if partner == "glycan":
            cls = CanonicalProteinGlycanWindowRow
            common.update(
                carrier_residue_index=9,
                first_sugar_residue_index=40,
                linkage_evidence="external_metadata",
                carrier_link_atom_index=None,
                first_sugar_link_atom_index=None,
            )
    return cls(**common | changes)


def damaged(model, **changes):
    """Synthetic stored-model damage; never weaken accepted constructors/readers."""
    result = copy.copy(model)
    for name, value in changes.items():
        object.__setattr__(result, name, value)
    return result


def artifact(family="protein_edge", rows=(), **changes):
    cls = TABLE_TYPES[FAMILIES.index(family)]
    return qc.RequiredArtifactEvidence(
        **dict(
            item_id=family,
            present=True,
            schema_valid=True,
            evidence=evidence(family),
            canonical_family=family,
            canonical_table=cls(rows),
        )
        | changes
    )


def inputs(**changes):
    return (
        dict(
            identity=identity(),
            raw_integrity=raw(),
            mapping_binding=mapping(),
            required_source_keys=(SOURCE_KEY,),
            protein_pbc=qc.ReplicaProteinPBCEvidence(False, evidence("pbc", "pbc")),
            sampling_plan=plan(),
            required_metadata=(),
            required_artifacts=(artifact(),),
        )
        | changes
    )


def evaluate(**changes):
    return qc.evaluate_replica_hard_qc(**inputs(**changes))


def check(result, name):
    return next(c for c in result.checks if c.check_id == name)


def assert_finding(result, name, status, code=None):
    finding = check(result, name)
    assert finding.status == status
    assert finding.reason_code == code
    assert finding.evidence
    assert all(e.to_dict() for e in finding.evidence)
    if status == "fail":
        assert finding.human_readable_reason
        assert result.hard_qc_status == "fail"
    else:
        assert finding.human_readable_reason is None
    return finding


def test_result_model_and_authority():
    result = evaluate()
    assert tuple(f.name for f in fields(result)) == (
        "dataset_id",
        "system_id",
        "trajectory_id",
        "replica_id",
        "checks",
        "hard_qc_status",
    )
    assert result.replica_key == KEY
    assert result.hard_qc_status == "pass"
    assert get_args(qc.HardQCStatus) == ("pass", "fail")
    assert not fields(result)[-1].init
    for field_name in ("release_decision", "decision_mode", "review", "condition"):
        assert not hasattr(result, field_name)
        assert field_name not in result.to_dict()
    with pytest.raises(FrozenInstanceError):
        result.replica_id = "2"
    assert all(type(c) is ReplicaQCCheckResult for c in result.checks)


def test_determinism_and_input_immutability():
    original = inputs(
        required_artifacts=tuple(artifact(f, (row(f),)) for f in FAMILIES)
    )
    before = (
        repr(original),
        json.dumps(asdict(original["mapping_binding"])),
        [a.canonical_table.to_dict() for a in original["required_artifacts"]],
        original["sampling_plan"].to_dict(),
        original["identity"].to_dict(),
    )
    first = qc.evaluate_replica_hard_qc(**original)
    second = qc.evaluate_replica_hard_qc(**original)
    assert json.dumps(first.to_dict(), allow_nan=False) == json.dumps(second.to_dict())
    assert before == (
        repr(original),
        json.dumps(asdict(original["mapping_binding"])),
        [a.canonical_table.to_dict() for a in original["required_artifacts"]],
        original["sampling_plan"].to_dict(),
        original["identity"].to_dict(),
    )
    payload = first.to_dict()
    payload["checks"].clear()
    assert first.checks


@pytest.mark.parametrize("condition", [None, "NORM", "different-label"])
def test_condition_is_not_authority(condition):
    assert (
        evaluate(identity=identity(condition=condition)).to_dict()
        == evaluate().to_dict()
    )


@pytest.mark.parametrize(
    "name", ["dataset_id", "system_id", "trajectory_id", "replica_id"]
)
def test_mapping_binding_uses_every_replica_key_field(name):
    with pytest.raises(qc.DatasetHardQCError, match="full replica key"):
        evaluate(mapping_binding=mapping(**{name: "other"}))
    result = evaluate(
        identity=identity(**{name: "other"}), mapping_binding=mapping(**{name: "other"})
    )
    assert getattr(result, name) == "other"


@pytest.mark.parametrize(
    "source,code",
    [
        ("topology", "TOPOLOGY_UNREADABLE"),
        ("trajectory", "TRAJECTORY_UNREADABLE"),
    ],
)
@pytest.mark.parametrize("readable", [True, False])
def test_readability(source, code, readable):
    result = evaluate(raw_integrity=raw(**{f"{source}_readable": readable}))
    assert_finding(
        result,
        f"{source}_readable",
        "pass" if readable else "fail",
        None if readable else code,
    )
    if not readable:
        assert not any(
            c.check_id.startswith("topology_trajectory") for c in result.checks
        )
        assert check(result, "required_artifact:protein_edge").status == "pass"


def test_unreadable_sources_omit_unavailable_dependent_checks():
    result = evaluate(
        raw_integrity=raw(
            topology_readable=False,
            trajectory_readable=False,
            topology_atom_count=None,
            trajectory_atom_count=None,
            atom_order_consistent=None,
            atom_order_evidence=None,
        ),
        sampling_plan=None,
        mapping_binding=None,
        protein_pbc=None,
    )
    ids = {c.check_id for c in result.checks}
    assert not ids.intersection(
        {
            "canonical_mapping_complete",
            "protein_pbc_integrity",
            "frame_time_strictly_increasing",
            "production_frame_coverage",
            "topology_trajectory_atom_count",
            "topology_trajectory_atom_order",
        }
    )
    assert check(result, "schema:protein_edge").status == "pass"


@pytest.mark.parametrize(
    "count,status,code",
    [
        (10000, "pass", None),
        (9999, "fail", "TOPOLOGY_TRAJECTORY_ATOM_COUNT_MISMATCH"),
    ],
)
def test_atom_counts(count, status, code):
    assert_finding(
        evaluate(raw_integrity=raw(trajectory_atom_count=count)),
        "topology_trajectory_atom_count",
        status,
        code,
    )


@pytest.mark.parametrize(
    "order,status,code",
    [
        (None, "fail", "REQUIRED_METADATA_MISSING"),
        (True, "pass", None),
        (False, "fail", "TOPOLOGY_TRAJECTORY_ATOM_ORDER_MISMATCH"),
    ],
)
def test_primary_equal_counts_do_not_prove_atom_order(order, status, code):
    result = evaluate(
        raw_integrity=raw(
            atom_order_consistent=order,
            atom_order_evidence=None if order is None else evidence(),
        )
    )
    assert_finding(result, "topology_trajectory_atom_count", "pass")
    assert_finding(result, "topology_trajectory_atom_order", status, code)


@pytest.mark.parametrize(
    "changes",
    [
        {"topology_readable": 1},
        {"trajectory_readable": "true"},
        {"topology_atom_count": True},
        {"trajectory_atom_count": -1},
        {"topology_atom_count": 2.0},
        {"trajectory_atom_count": None},
        {"atom_order_consistent": 1},
        {"atom_order_evidence": None},
        {"atom_universe_id": " "},
        {"topology_evidence": None},
    ],
)
def test_raw_malformed_inputs(changes):
    with pytest.raises(qc.DatasetHardQCError):
        raw(**changes)


def test_t330m_mapping_and_required_source_scope():
    result = evaluate()
    assert_finding(result, "canonical_mapping_complete", "pass")
    mapped = mapping().mapping_table.mappings[0]
    assert (mapped.source_resname, mapped.canonical_resname) == ("MET", "THR")
    extra = CanonicalResidueMappingRecord(
        "gromacs", "Z", "999", "UNK", None, None, "unmapped"
    )
    assert_finding(
        evaluate(mapping_binding=mapping((mapped, extra))),
        "canonical_mapping_complete",
        "pass",
    )
    # No rule requires all 690 canonical positions in the source topology.
    assert len(mapping().mapping_table.mappings) == 1


@pytest.mark.parametrize(
    "records",
    [(), (CanonicalResidueMappingRecord(*SOURCE_KEY, None, None, "unmapped"),)],
)
def test_mapping_incomplete_or_required_record_removed(records):
    assert_finding(
        evaluate(mapping_binding=mapping(records)),
        "canonical_mapping_complete",
        "fail",
        "CANONICAL_MAPPING_INCOMPLETE",
    )


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"mapping_binding": None}, "REQUIRED_ARTIFACT_MISSING"),
        ({"required_source_keys": None}, "REQUIRED_METADATA_MISSING"),
    ],
)
def test_missing_mapping_evidence_is_not_incomplete_mapping(changes, code):
    assert_finding(evaluate(**changes), "canonical_mapping_complete", "fail", code)


@pytest.mark.parametrize(
    "broken,status,code",
    [
        (False, "pass", None),
        (True, "fail", "PROTEIN_PBC_BROKEN"),
    ],
)
def test_pbc(broken, status, code):
    assert_finding(
        evaluate(
            protein_pbc=qc.ReplicaProteinPBCEvidence(broken, evidence("pbc", "pbc"))
        ),
        "protein_pbc_integrity",
        status,
        code,
    )


def test_missing_pbc_evidence_fails():
    assert_finding(
        evaluate(protein_pbc=None),
        "protein_pbc_integrity",
        "fail",
        "REQUIRED_METADATA_MISSING",
    )


@pytest.mark.parametrize("times", [[50000, 50000], [50500, 50000]])
def test_accepted_stage27_equal_or_backwards_source_diagnostic(times):
    observed = plan(times=times)
    assert not observed.selected_samples
    assert_finding(
        evaluate(sampling_plan=observed),
        "frame_time_strictly_increasing",
        "fail",
        "FRAME_TIME_NOT_STRICTLY_INCREASING",
    )


@pytest.mark.parametrize("times", [(), (50000,), (50000, 50500, 51500)])
def test_sparse_and_increasing_actual_time_evidence(times):
    result = evaluate(sampling_plan=plan(times=times))
    assert_finding(result, "frame_time_strictly_increasing", "pass")
    assert_finding(
        result,
        "production_frame_coverage",
        "fail",
        "PRODUCTION_FRAME_COVERAGE_BELOW_95_PERCENT",
    )


@pytest.mark.parametrize("time_value", [50000, 49999.99999999999])
def test_actual_selected_times_are_compared_without_epsilon(time_value):
    observed = plan()
    samples = list(observed.selected_samples)
    samples[1] = damaged(samples[1], actual_time_ps=time_value)
    observed = damaged(observed, selected_samples=tuple(samples))
    assert_finding(
        evaluate(sampling_plan=observed),
        "frame_time_strictly_increasing",
        "fail",
        "FRAME_TIME_NOT_STRICTLY_INCREASING",
    )


@pytest.mark.parametrize(
    "resolved,expected,status",
    [
        (95, 100, "pass"),
        (94, 100, "fail"),
        (19, 20, "pass"),
        (18, 20, "fail"),
        (101, 101, "pass"),
        (96, 101, "pass"),
        (95, 101, "fail"),
    ],
)
def test_exact_coverage_smokes(resolved, expected, status):
    result = evaluate(sampling_plan=plan(expected, resolved))
    finding = assert_finding(
        result,
        "production_frame_coverage",
        status,
        None if status == "pass" else "PRODUCTION_FRAME_COVERAGE_BELOW_95_PERCENT",
    )
    assert finding.evidence[0].metric_name == "production_frame_coverage"
    assert finding.evidence[0].expected_or_threshold == ">=0.95"
    with localcontext():
        assert abs(
            Decimal(finding.evidence[0].observed_value)
            - Decimal(resolved) / Decimal(expected)
        ) < Decimal("1e-27")


def test_coverage_ignores_extra_frames_and_ambient_decimal_context():
    baseline = evaluate(sampling_plan=plan(101, 95))
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = True
        extra = evaluate(sampling_plan=plan(101, 95, 50))
    assert extra.to_dict() == baseline.to_dict()
    assert extra.hard_qc_status == "fail"


def test_missing_samples_never_get_synthetic_timestamps():
    observed = plan(times=[50000, 51000])
    before = observed.to_dict()
    result = evaluate(sampling_plan=observed)
    assert check(result, "frame_time_strictly_increasing").status == "pass"
    assert observed.to_dict() == before
    assert all("actual_time_ps" not in m.to_dict() for m in observed.missing_samples)


@pytest.mark.parametrize("present", [False, True])
def test_required_metadata_and_nullable_condition(present):
    required = qc.RequiredMetadataEvidence("window_definition", present, evidence())
    result = evaluate(required_metadata=(required,))
    assert_finding(
        result,
        "required_metadata:window_definition",
        "pass" if present else "fail",
        None if present else "REQUIRED_METADATA_MISSING",
    )
    assert (
        evaluate(identity=identity(engine="namd", condition=None)).hard_qc_status
        == "pass"
    )


def test_missing_artifact_and_missing_window_are_distinct_from_empty_edges():
    missing = qc.RequiredArtifactEvidence("requested_window", False, None, evidence())
    result = evaluate(required_artifacts=(artifact(), missing))
    assert_finding(
        result,
        "required_artifact:requested_window",
        "fail",
        "REQUIRED_ARTIFACT_MISSING",
    )
    assert not any(c.check_id == "schema:requested_window" for c in result.checks)
    for name in (
        "required_artifact:protein_edge",
        "schema:protein_edge",
        "forbidden_self_loops",
        "duplicate_records",
        "occupancy_range",
    ):
        assert_finding(result, name, "pass")


def test_primary_header_only_table_is_present_and_schema_valid():
    result = evaluate()
    assert artifact().canonical_table.row_count == 0
    assert result.hard_qc_status == "pass"
    assert not any(c.reason_code == "REQUIRED_ARTIFACT_MISSING" for c in result.checks)
    assert not any("review" in c.check_id for c in result.checks)


@pytest.mark.parametrize(
    "valid,code", [(False, "SCHEMA_INVALID"), (None, "REQUIRED_METADATA_MISSING")]
)
def test_schema_failure_or_missing_validation_evidence(valid, code):
    a = artifact(schema_valid=valid, canonical_table=None)
    result = evaluate(required_artifacts=(a,))
    assert_finding(result, "schema:protein_edge", "fail", code)
    assert not {
        "forbidden_self_loops",
        "duplicate_records",
        "occupancy_range",
    }.intersection(c.check_id for c in result.checks)


def test_present_validated_canonical_artifact_needs_structural_model_evidence():
    result = evaluate(required_artifacts=(artifact(canonical_table=None),))
    assert_finding(
        result,
        "schema:protein_edge:canonical_model",
        "fail",
        "REQUIRED_METADATA_MISSING",
    )


@pytest.mark.parametrize(
    "field_name", ["canonical_reference_id", "canonical_reference_sequence_sha256"]
)
@pytest.mark.parametrize("origin", ["mapping", "table"])
def test_canonical_reference_exact(field_name, origin):
    if origin == "mapping":
        b = mapping(
            mapping_table=damaged(mapping().mapping_table, **{field_name: "wrong"})
        )
        result = evaluate(mapping_binding=b)
    else:
        a = artifact(
            canonical_table=damaged(artifact().canonical_table, **{field_name: "wrong"})
        )
        result = evaluate(required_artifacts=(a,))
    assert_finding(
        result, "canonical_reference", "fail", "CANONICAL_REFERENCE_MISMATCH"
    )


def test_forbidden_self_loop_is_a_finding_and_is_not_repaired():
    bad = damaged(row(), target_canonical_residue_number=312)
    table = damaged(artifact().canonical_table, rows=(bad,))
    before = table.to_dict()
    result = evaluate(
        required_artifacts=(artifact(canonical_table=table, schema_valid=False),)
    )
    assert_finding(result, "forbidden_self_loops", "fail", "FORBIDDEN_SELF_LOOP")
    assert table.to_dict() == before


@pytest.mark.parametrize("family", FAMILIES)
def test_duplicate_uses_exact_accepted_row_identity(family):
    original = row(family)
    # Condition and scientific values are not part of Stage 30 identity.
    other = replace(original, condition="another-label")
    table = damaged(artifact(family).canonical_table, rows=(original, other))
    result = evaluate(required_artifacts=(artifact(family, canonical_table=table),))
    assert_finding(result, "duplicate_records", "fail", "DUPLICATE_RECORD")


@pytest.mark.parametrize("family", FAMILIES)
def test_duplicate_scope_and_specialized_partner_is_not_a_self_loop(family):
    r = row(family)
    other_window = replace(r, window_id="window_0002", window_index=1)
    other_replica = replace(r, replica_id="2")
    other_system = replace(r, system_id="Z")
    table = damaged(
        artifact(family).canonical_table,
        rows=(r, other_window, other_replica, other_system),
    )
    result = evaluate(required_artifacts=(artifact(family, canonical_table=table),))
    assert_finding(result, "duplicate_records", "pass")
    if family != "protein_edge":
        assert not any(c.check_id == "forbidden_self_loops" for c in result.checks)


def test_duplicate_families_and_edge_types_are_separate():
    edge = row()
    typed = replace(edge, edge_type="hydrogen_bond")
    result = evaluate(
        required_artifacts=(
            artifact(rows=(edge, typed)),
            artifact("protein_lipid", (row("protein_lipid"),)),
            artifact("protein_glycan", (row("protein_glycan"),)),
        )
    )
    assert_finding(result, "duplicate_records", "pass")
    assert_finding(result, "forbidden_self_loops", "pass")


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize(
    "occupancy,status",
    [
        (0, "pass"),
        (1, "pass"),
        (0.5, "pass"),
        (-1e-15, "fail"),
        (1.000000000000001, "fail"),
        (float("nan"), "fail"),
        (float("inf"), "fail"),
        (-float("inf"), "fail"),
    ],
)
def test_stored_occupancy_in_every_canonical_family(family, occupancy, status):
    stored = damaged(row(family), occupancy=occupancy)
    table = damaged(artifact(family).canonical_table, rows=(stored,))
    result = evaluate(required_artifacts=(artifact(family, canonical_table=table),))
    assert_finding(
        result,
        "occupancy_range",
        status,
        None if status == "pass" else "OCCUPANCY_OUT_OF_RANGE",
    )
    # Even non-finite negative evidence is deterministic JSON text.
    json.dumps(result.to_dict(), allow_nan=False)
    assert table.rows[0] is stored


def test_check_order_and_evidence_completeness():
    a, z = (qc.RequiredMetadataEvidence(i, True, evidence()) for i in ("a", "z"))
    extras = tuple(
        qc.RequiredArtifactEvidence(i, True, True, evidence()) for i in ("a", "z")
    )
    result = evaluate(
        required_metadata=(z, a), required_artifacts=(extras[1], artifact(), extras[0])
    )
    fixed = qc.HARD_QC_FIXED_CHECK_IDS
    assert tuple(c.check_id for c in result.checks) == (
        *fixed[:8],
        "required_metadata:a",
        "required_metadata:z",
        "required_artifact:a",
        "required_artifact:protein_edge",
        "required_artifact:z",
        "schema:a",
        "schema:protein_edge",
        "schema:z",
        *fixed[8:],
    )
    assert all(c.evidence for c in result.checks)
    ids = [e.evidence_id for c in result.checks for e in c.evidence]
    assert len(ids) == len(set(ids))
    assert (
        result.to_dict()
        == evaluate(
            required_metadata=(a, z),
            required_artifacts=(extras[0], extras[1], artifact()),
        ).to_dict()
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"identity": {}},
        {"raw_integrity": None},
        {"mapping_binding": {}},
        {"protein_pbc": True},
        {"sampling_plan": {}},
        {"required_metadata": []},
        {"required_artifacts": []},
        {"required_source_keys": [SOURCE_KEY]},
        {"required_source_keys": (("gromacs",),)},
        {"required_source_keys": (SOURCE_KEY, SOURCE_KEY)},
        {"required_artifacts": (artifact(), artifact())},
        {
            "required_metadata": (qc.RequiredMetadataEvidence("x", True, evidence()),)
            * 2
        },
    ],
)
def test_malformed_evaluator_contract_raises_public_error(changes):
    with pytest.raises(qc.DatasetHardQCError):
        evaluate(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"present": 1},
        {"schema_valid": "true"},
        {"evidence": None},
        {"item_id": " "},
        {"canonical_family": "other"},
        {
            "canonical_family": "protein_glycan",
            "canonical_table": artifact().canonical_table,
        },
        {"present": False, "schema_valid": True},
    ],
)
def test_artifact_evidence_contract(changes):
    with pytest.raises(qc.DatasetHardQCError):
        artifact(**changes)


def test_result_rejects_review_empty_and_duplicate_findings():
    review = ReplicaQCCheckResult(
        "review", "review", "RMSD_DRIFT_REVIEW", "Review.", (evidence(),)
    )
    for findings in ((), (review,), (evaluate().checks[0],) * 2, []):
        with pytest.raises(qc.DatasetHardQCError):
            qc.ReplicaHardQCEvaluation(*KEY, findings)
    with pytest.raises(qc.DatasetHardQCError):
        qc.ReplicaHardQCEvaluation(" ", *KEY[1:], evaluate().checks)


def test_no_io_clock_network_runtime_or_recomputation(monkeypatch):
    supplied = inputs(
        required_artifacts=tuple(artifact(f, (row(f),)) for f in FAMILIES)
    )
    expected = qc.evaluate_replica_hard_qc(**supplied).to_dict()

    def blocked(*args, **kwargs):
        raise AssertionError("Forbidden I/O, clock, runtime or recomputation")

    from mania import canonical_reference_io, canonical_window_tables
    from mania.preprocessing import physical_time_sampling

    with monkeypatch.context() as guard:
        for owner, names in (
            (builtins, ("open",)),
            (io, ("open",)),
            (os, ("system", "getenv", "stat")),
            (Path, ("open", "read_text", "read_bytes", "exists")),
            (socket, ("socket", "create_connection")),
            (subprocess, ("run", "Popen", "check_output", "check_call")),
            (time, ("time", "monotonic", "perf_counter")),
            (canonical_reference_io, ("load_default_napi2b_canonical_reference",)),
            (physical_time_sampling, ("resolve_physical_time_sampling",)),
            (
                canonical_window_tables,
                (
                    "load_default_napi2b_canonical_reference",
                    "build_canonical_protein_edge_window_table",
                    "build_canonical_protein_lipid_window_table",
                    "build_canonical_protein_glycan_window_table",
                ),
            ),
        ):
            for name in names:
                guard.setattr(owner, name, blocked)
        assert qc.evaluate_replica_hard_qc(**supplied).to_dict() == expected
    tree = ast.parse(inspect.getsource(qc))
    forbidden = {
        "open",
        "resolve_physical_time_sampling",
        "ReplicaQCDecisionRecord",
        "build_dataset_qc_decision_set",
        "load_default_napi2b_canonical_reference",
    }
    calls = {
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert not calls.intersection(forbidden)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not any(
                word in (node.module or "")
                for word in (
                    "replica_aggregation",
                    "workflow",
                    "runtime",
                    "MDAnalysis",
                    "contacts",
                    "inventory",
                    "provenance",
                    "validation",
                    "cli",
                )
            )
