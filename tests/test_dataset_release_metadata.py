"""Stage 33.B candidate history, explicit authorities and lossless metadata."""

import copy
import json
from dataclasses import asdict, replace
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from mania.biological_annotations import (
    CanonicalVariantSiteAnnotation,
    DatasetSystemBiologicalAnnotations,
    GlycosylationSiteAnnotation,
)
from mania.canonical_reference_io import load_default_napi2b_canonical_reference
from mania.dataset_identity import DatasetTrajectorySpec
from mania.dataset_qc_contract import (
    DatasetQCDecisionSet,
    QCEvidenceRecord,
    ReplicaQCCheckResult,
    ReplicaQCDecisionRecord,
)
from mania.dataset_qc_summary import build_dataset_qc_summary
from mania.dataset_qc_workflow import build_qc_derived_replica_aggregation_manifest
from mania.dataset_release_csv import (
    METADATA_TABLE_IDS,
    build_publication_table,
    publication_csv_bytes,
    read_publication_csv,
    write_publication_csv,
)
from mania.dataset_release_metadata import (
    QCDerivedAggregationEvidence,
    build_dataset_release_contact_definition,
    build_dataset_release_metadata_tables,
    build_dataset_release_simulations,
    build_dataset_release_software_versions,
    build_dataset_release_systems,
    build_dataset_release_time_windows,
)
from mania.preprocessing.contact_episodes import CONTACT_EPISODE_GAP_TOLERANCE
from mania.preprocessing.pbc_audit import (
    PBC_INTERNAL_MINIMUM_IMAGE_CORRECTION_APPLIED,
    PBC_SCIENTIFIC_STATUS,
)
from mania.preprocessing.physical_time_execution import (
    PreprocessingConditionTemporalExecution,
)
from mania.preprocessing.physical_time_sampling import (
    PhysicalTimeSourceFrame,
    resolve_physical_time_sampling,
)
from mania.preprocessing.physical_time_windows import plan_physical_time_windows
from mania.preprocessing.protein_glycan_contacts import (
    PROTEIN_GLYCAN_CONTACT_CUTOFF_A,
    PROTEIN_GLYCAN_COVALENT_EXCLUSION_REASON,
    PROTEIN_GLYCAN_DISTANCE_DEFINITION,
    PROTEIN_GLYCAN_DISTANCE_UNIT,
)
from mania.preprocessing.protein_lipid_contacts import (
    PROTEIN_LIPID_CONTACT_CUTOFF_A,
    PROTEIN_LIPID_DISTANCE_DEFINITION,
    PROTEIN_LIPID_DISTANCE_UNIT,
)
from mania.preprocessing.trajectory_contacts import PreprocessingContactDetectionOptions
from mania.preprocessing.trajectory_preprocessing_manifests import (
    build_edge_semantics_manifest,
)
from mania.replica_aggregation_contract import (
    ReplicaAggregationGroupSpec,
    ReplicaAggregationMember,
    ReplicaAggregationWindowDefinition,
)
from mania.replica_aggregation_manifest import (
    ReplicaAggregationManifest,
    ReplicaAggregationWorkflowGroup,
)
from mania.replica_specialized_aggregation import SpecializedPartnerCorrespondences


def replica_key(replica="1"):
    return ("synthetic-33b", "T330M", f"trajectory-{replica}", replica)


def decision(replica="1", status="pass", release="available"):
    findings = []
    for check in ("mapping", "schema"):
        evidence = QCEvidenceRecord(
            f"{check}-evidence",
            "artifact",
            "accepted-evidence",
            f"evidence/{replica}/{check}.json",
            None,
            None,
            None,
            None,
            None,
        )
        findings.append(ReplicaQCCheckResult(check, "pass", None, None, (evidence,)))
    reason = prose = None
    ids = ()
    if status != "pass":
        reason = "TRAJECTORY_UNREADABLE" if status == "fail" else "RMSD_DRIFT_REVIEW"
        prose = "Accepted reason, with exact punctuation."
        evidence = tuple(
            QCEvidenceRecord(
                f"decision-{i}",
                "metric",
                None,
                None,
                "window_0001",
                "rmsd",
                "0.12345678901234567",
                "caller evidence",
                f"Observation {i}",
            )
            for i in (1, 2)
        )
        findings.append(
            ReplicaQCCheckResult("review-or-fail", status, reason, prose, evidence)
        )
        ids = ("decision-1",)
    manual = status == "review" and release != "pending_review"
    return ReplicaQCDecisionRecord(
        *replica_key(replica),
        status,
        tuple(findings),
        release,
        "manual" if manual else "automatic",
        reason,
        prose,
        ids,
        "Reviewer A" if manual else None,
        "Accepted manual note." if manual else None,
    )


def temporal_evidence(replica="1", *, length=0.4, step=0.2):
    spec = DatasetTrajectorySpec.model_validate(
        {
            "identity": dict(
                zip(
                    ("dataset_id", "system_id", "trajectory_id", "replica_id"),
                    replica_key(replica),
                    strict=True,
                ),
                engine="namd",
                variant_id="T330M",
                condition=None,
                disulfide_state=None,
            ),
            "temporal": dict(
                production_start_ns=0,
                production_end_ns=1,
                frame_stride_ps=100,
                window_length_ns=length,
                window_step_ns=step,
                overlap_percent=(1 - step / length) * 100,
            ),
        }
    )
    # Accepted synthetic sampling evidence: first window empty, later windows
    # partial/complete. No trajectory reader participates in these fixtures.
    samples = resolve_physical_time_sampling(
        tuple(
            PhysicalTimeSourceFrame(i, t) for i, t in enumerate((400, 600, 700, 900))
        ),
        temporal=spec.temporal,
    )
    windows = plan_physical_time_windows(samples, temporal=spec.temporal)
    return PreprocessingConditionTemporalExecution(
        "execution-only", spec, samples, windows
    )


def complete_annotations():
    reference = load_default_napi2b_canonical_reference()
    glyco = reference.residue_at(300)
    return DatasetSystemBiologicalAnnotations(
        "synthetic-33b",
        "T330M",
        "complete_for_system",
        (
            GlycosylationSiteAnnotation(
                300,
                glyco.canonical_resname,
                True,
                "synthetic glycan",
                "supplied glycosylation source",
                "supplied glycosylation verifier",
            ),
        ),
        (
            CanonicalVariantSiteAnnotation(
                330, "THR", "disulfide source", "disulfide verifier"
            ),
        ),
        (
            CanonicalVariantSiteAnnotation(
                330, "THR", "cysteine source", "cysteine verifier"
            ),
        ),
    )


def contact_parameters(kind="protein-lipid"):
    options = PreprocessingContactDetectionOptions(
        cutoff_distance=4.123456789012345,
        contact_selection="protein",
        skip_resnames=("SYNTHETIC",),
    )
    specialized = kind != "protein-protein"
    lipid = kind == "protein-lipid"
    value = (
        (PROTEIN_LIPID_CONTACT_CUTOFF_A if lipid else PROTEIN_GLYCAN_CONTACT_CUTOFF_A)
        if specialized
        else options.cutoff_distance
    )
    unit = (
        (PROTEIN_LIPID_DISTANCE_UNIT if lipid else PROTEIN_GLYCAN_DISTANCE_UNIT)
        if specialized
        else options.distance_unit
    )
    return dict(
        atom_selections=(
            [
                "protein heavy atoms",
                "one lipid molecule heavy atoms"
                if lipid
                else "whole glycan heavy atoms",
            ]
            if specialized
            else options.to_dict(include_contact_selection=True)
        ),
        distance_definition=(
            PROTEIN_LIPID_DISTANCE_DEFINITION
            if lipid
            else PROTEIN_GLYCAN_DISTANCE_DEFINITION
        )
        if specialized
        else "minimum residue atom distance",
        cutoff={"value": value, "unit": unit, "comparison": "<="},
        type_specific_parameters=(
            {"carrier_summary_exclusion": PROTEIN_GLYCAN_COVALENT_EXCLUSION_REASON}
            if kind == "protein-glycan"
            else {}
        )
        if specialized
        else {
            "options": options.to_dict(include_contact_selection=True),
            "accepted_typed_semantics": build_edge_semantics_manifest(),
        },
        pbc_correction_status={
            "mania_internal_minimum_image_correction_applied": (
                PBC_INTERNAL_MINIMUM_IMAGE_CORRECTION_APPLIED
            ),
            "scientific_pbc_status": PBC_SCIENTIFIC_STATUS,
            "external_preprocessing": "undeclared",
            "audit_semantics": "observation only",
        },
        occupancy_denominator_semantics="resolved frames in this window",
        episode_continuity_semantics=(
            "consecutive requested indexes; missing or negative breaks"
        ),
        gap_tolerance=CONTACT_EPISODE_GAP_TOLERANCE,
        lifetime_semantics=(
            "last minus first actual positive time in ns; singleton zero"
        ),
        specialized_distance_semantics="positive frames only" if specialized else None,
        extra={
            "empty": "",
            "array": [],
            "object": {},
            "a/b~c": [None, False, "null", "None"],
        },
    )


def contact_table(kind="protein-lipid", parameters=None):
    return build_dataset_release_contact_definition(
        replica_key=replica_key(),
        contact_definition_id=kind,
        contact_layer=kind,
        interaction_type="residue_contact" if kind == "protein-protein" else kind,
        parameters=contact_parameters(kind) if parameters is None else parameters,
        source_artifact_role="accepted_contact_definition",
        source_artifact_path=f"evidence/{kind}.json",
        units={"$/cutoff/value": "angstrom"},
    )


def synthetic_inputs(tmp_path):
    decisions = DatasetQCDecisionSet(
        (
            decision("5", "review", "available"),
            decision("2", "fail", "excluded"),
            decision("4", "review", "excluded"),
            decision("3"),
            decision(),
        )
    )
    temporal = temporal_evidence()
    groups = []
    reference = load_default_napi2b_canonical_reference()
    for w in temporal.window_plan.windows:
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
        )
        spec = ReplicaAggregationGroupSpec(
            "synthetic-33b",
            "T330M",
            "namd",
            "T330M",
            None,
            None,
            ("1", "2", "3", "4", "5"),
            window,
        )
        members = tuple(
            ReplicaAggregationMember(
                *r.replica_key,
                "T330M",
                "namd",
                None,
                None,
                reference.reference_id,
                reference.sequence_sha256,
                window,
                "unavailable" if r.replica_id == "3" else "available",
                "Accepted technical missing aggregate input"
                if r.replica_id == "3"
                else None,
            )
            for r in decisions.records
        )
        groups.append(
            ReplicaAggregationWorkflowGroup(
                spec,
                members,
                SpecializedPartnerCorrespondences(()),
                SpecializedPartnerCorrespondences(()),
            )
        )
    template = ReplicaAggregationManifest(
        (tmp_path / "unread-science.csv",), (), (), tuple(groups)
    )
    derived = build_qc_derived_replica_aggregation_manifest(template, decisions)
    return dict(
        decisions=decisions,
        summary=build_dataset_qc_summary(decisions),
        aggregation_authority=QCDerivedAggregationEvidence(
            derived,
            decisions,
            "qc_derived_replica_aggregation_manifest",
            "qc/replica_aggregation_manifest_qc_derived.json",
        ),
        scientific_release_replica_keys=(replica_key(), replica_key("3")),
        annotation_publication_system_keys=(("synthetic-33b", "T330M"),),
        temporal_evidence=(temporal, temporal_evidence("2")),
        annotation_metadata=(complete_annotations(),),
        contact_definitions=tuple(
            contact_table(k)
            for k in (
                "protein-glycan",
                "protein-protein",
                "protein-lipid",
            )
        ),
        software_version_records=tuple(
            dict(
                dataset_id="synthetic-33b",
                component_role=role,
                component_name=name,
                version=version,
                run_id=None,
                source_artifact_role="run_provenance",
                source_artifact_path="evidence/run_provenance.json",
            )
            for role, name, version in (
                ("package", "mania-wania", "0.1.0"),
                ("engine", "NAMD", None),
            )
        ),
    )


@pytest.fixture(scope="module")
def inputs(tmp_path_factory):
    return synthetic_inputs(tmp_path_factory.mktemp("release-inputs"))


@pytest.fixture(scope="module")
def bundle(inputs):
    return build_dataset_release_metadata_tables(**inputs)


def test_candidate_history_and_explicit_inclusion(bundle, inputs):
    assert tuple(t.table_id for t in bundle.tables) == METADATA_TABLE_IDS
    assert bundle.systems.row_count == 1
    assert bundle.simulations.row_count == bundle.quality_control.row_count == 5
    rows = {r["replica_id"]: r for r in bundle.simulations.records()}
    assert all(r["condition"] is None for r in rows.values())
    assert rows["2"]["release_decision"] == "excluded"
    assert rows["4"]["qc_status"] == "review"
    for key in ("2", "4"):
        assert rows[key]["aggregation_availability_status"] == "excluded"
        assert not rows[key]["included_in_scientific_release"]
        assert not rows[key]["included_in_replica_aggregation"]
        assert rows[key]["decision_reason_code"]
        assert (
            rows[key]["human_readable_reason"]
            == "Accepted reason, with exact punctuation."
        )
    assert rows["3"]["release_decision"] == "available"
    assert rows["3"]["aggregation_availability_status"] == "unavailable"
    assert not rows["3"]["included_in_replica_aggregation"]
    assert rows["3"]["included_in_scientific_release"]
    assert not rows["5"]["included_in_scientific_release"]
    assert rows["5"]["included_in_replica_aggregation"]
    table = build_dataset_release_simulations(
        inputs["decisions"],
        inputs["aggregation_authority"],
        scientific_release_replica_keys=(replica_key("5"),),
    )
    changed = {r["replica_id"]: r for r in table.records()}
    assert changed["5"]["included_in_scientific_release"]
    assert not changed["3"]["included_in_scientific_release"]


@pytest.mark.parametrize(
    "keys",
    [
        (replica_key("2"),),
        (replica_key("4"),),
        (replica_key("unknown"),),
        (replica_key(), replica_key()),
        (("1",),),
        (list(replica_key()),),
    ],
)
def test_invalid_scientific_selection_fails(inputs, keys):
    with pytest.raises(ValueError):
        build_dataset_release_simulations(
            inputs["decisions"],
            inputs["aggregation_authority"],
            scientific_release_replica_keys=keys,
        )


def test_qc_derived_authority_is_required(inputs):
    authority = inputs["aggregation_authority"]
    with pytest.raises(ValueError, match="QC-derived"):
        build_dataset_release_simulations(
            inputs["decisions"],
            authority.manifest,
            scientific_release_replica_keys=(),
        )
    with pytest.raises(ValueError, match="QC-derived"):
        replace(authority, source_artifact_role="pre_qc_template")


@pytest.mark.parametrize("change", ["missing", "extra", "other_decisions"])
def test_exact_candidate_coverage_and_binding(inputs, change):
    records = inputs["decisions"].records
    if change == "missing":
        records = records[:-1]
    elif change == "extra":
        records = (*records, decision("6"))
    else:
        records = (*records[:-1], decision("5", "review", "excluded"))
    decisions = DatasetQCDecisionSet(records)
    authority = inputs["aggregation_authority"]
    if change != "other_decisions":
        authority = replace(authority, decisions=decisions)
    with pytest.raises(ValueError, match="coverage|different decisions"):
        build_dataset_release_simulations(
            decisions, authority, scientific_release_replica_keys=()
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("engine", "gromacs"),
        ("variant_id", "WT"),
        ("condition", "supplied-label"),
        ("disulfide_state", "supplied-state"),
    ],
)
def test_system_metadata_disagreement_fails(inputs, field, value):
    member = inputs["aggregation_authority"].manifest.groups[0].members[0]
    other = replace(member, replica_id="other", trajectory_id="other", **{field: value})
    with pytest.raises(ValueError, match="System-level"):
        build_dataset_release_systems((member, other))
    separate = replace(other, system_id="separate", condition=member.condition)
    assert build_dataset_release_systems((member, separate)).row_count == 2


@pytest.mark.parametrize("state", ["unavailable", "excluded"])
def test_repeated_window_availability_disagreement_fails(inputs, state):
    authority = inputs["aggregation_authority"]
    group = authority.manifest.groups[-1]
    changed = replace(
        group.members[0], availability_status=state, availability_reason="Other state"
    )
    group = replace(group, members=(changed, *group.members[1:]))
    manifest = replace(
        authority.manifest, groups=(*authority.manifest.groups[:-1], group)
    )
    with pytest.raises(ValueError, match="differs across windows"):
        build_dataset_release_simulations(
            inputs["decisions"],
            replace(authority, manifest=manifest),
            scientific_release_replica_keys=(),
        )


def test_repeated_window_reason_disagreement_fails(inputs):
    authority = inputs["aggregation_authority"]
    group = authority.manifest.groups[-1]
    group = replace(
        group,
        members=tuple(
            replace(m, availability_reason="Different reason")
            if m.replica_id == "3"
            else m
            for m in group.members
        ),
    )
    manifest = replace(
        authority.manifest, groups=(*authority.manifest.groups[:-1], group)
    )
    with pytest.raises(ValueError, match="differs across windows"):
        build_dataset_release_simulations(
            inputs["decisions"],
            replace(authority, manifest=manifest),
            scientific_release_replica_keys=(),
        )


def test_time_windows_copy_history_counts_and_requested_effective(bundle, inputs):
    rows = bundle.time_windows.records()
    assert len(rows) == 8
    assert {r["replica_id"] for r in rows} == {"1", "2"}
    assert rows[0]["effective_start_ns"] is None
    assert rows[0]["effective_end_ns"] is None
    row = rows[1]
    assert row["requested_window_start_ns"] == Decimal.from_float(0.2)
    assert row["effective_start_ns"] == Decimal("0.4")
    assert row["requested_production_end_ns"] == 1
    for source, published in zip(
        inputs["temporal_evidence"][0].window_plan.windows, rows[:4], strict=True
    ):
        assert published["coverage_fraction"] == source.coverage_fraction
        assert published["expected_sample_count"] == source.requested_sample_count
        assert published["resolved_sample_count"] == source.sampled_frame_count
        assert published["missing_sample_count"] == source.missing_sample_count
    assert not rows[0]["right_endpoint_inclusive"]
    assert rows[3]["right_endpoint_inclusive"]


def test_conflicting_temporal_definitions_fail():
    with pytest.raises(ValueError):
        build_dataset_release_time_windows(
            (temporal_evidence(), temporal_evidence(length=0.6, step=0.3))
        )
    with pytest.raises(ValueError, match="Duplicate"):
        build_dataset_release_time_windows((temporal_evidence(), temporal_evidence()))


def test_contact_definition_is_a_lossless_projection():
    for kind in ("protein-protein", "protein-lipid", "protein-glycan"):
        parameters = contact_parameters(kind)
        before = copy.deepcopy(parameters)
        table = contact_table(kind, parameters)
        records = {r["parameter_path"]: r for r in table.records()}
        assert parameters == before
        assert (
            records["$/cutoff/value"]["number_value"] == parameters["cutoff"]["value"]
        )
        assert records["$/cutoff/comparison"]["string_value"] == "<="
        assert records["$/gap_tolerance"]["integer_value"] == 0
        assert (
            records[
                "$/pbc_correction_status/mania_internal_minimum_image_correction_applied"
            ]["boolean_value"]
            is False
        )
        assert records["$/extra/a~1b~0c/2"]["string_value"] == "null"
        assert records["$/extra/empty"]["string_value"] == ""
        if kind == "protein-glycan":
            assert (
                records["$/type_specific_parameters/carrier_summary_exclusion"][
                    "string_value"
                ]
                == PROTEIN_GLYCAN_COVALENT_EXCLUSION_REASON
            )
        if kind == "protein-protein":
            assert (
                records["$/type_specific_parameters/options/contact_selection"][
                    "string_value"
                ]
                == "protein"
            )
            criteria = [r for p, r in records.items() if "detection_criteria" in p]
            assert any(r["number_value"] == 120 for r in criteria)
            assert any(
                "max_distance_A_exclusive" in r["parameter_path"] for r in criteria
            )
        assert publication_csv_bytes(
            contact_table(kind, parameters)
        ) == publication_csv_bytes(table)


def test_missing_contact_authority_and_conflicting_software_fail(inputs):
    parameters = contact_parameters()
    del parameters["gap_tolerance"]
    with pytest.raises(ValueError, match="required"):
        contact_table(parameters=parameters)
    software = inputs["software_version_records"][0]
    with pytest.raises(ValueError, match="Duplicate"):
        build_dataset_release_software_versions(
            (software, {**software, "version": "other"})
        )
    records = build_dataset_release_software_versions(
        inputs["software_version_records"]
    ).records()
    assert {r["component_name"]: r["version"] for r in records} == {
        "NAMD": None,
        "mania-wania": "0.1.0",
    }


@pytest.mark.parametrize(
    "table_id,field",
    [
        ("simulations", "system_id"),
        ("time_windows", "replica_id"),
        ("quality_control", "trajectory_id"),
        ("quality_control_findings", "replica_id"),
        ("quality_control_evidence", "check_id"),
        ("residue_annotations", "system_id"),
        ("residue_annotations", "canonical_reference_id"),
        ("contact_definitions", "replica_id"),
    ],
)
def test_bundle_validates_in_scope_foreign_keys(bundle, table_id, field):
    table = getattr(bundle, table_id)
    rows = list(table.records())
    rows[0][field] = "unknown-reference"
    if table_id == "contact_definitions":
        for row in rows:
            row[field] = "unknown-reference"
    with pytest.raises(ValueError, match="foreign key"):
        replace(bundle, **{table_id: build_publication_table(table_id, rows)})


def test_protein_interaction_identities_and_type_specific_parameters_are_retained():
    base = contact_parameters("protein-protein")
    definitions = []
    for edge in build_edge_semantics_manifest()["edge_types"]:
        parameters = {
            **base,
            "distance_definition": edge["definition"],
            "cutoff": edge["detection_criteria"],
            "type_specific_parameters": edge,
        }
        definitions.append(
            build_dataset_release_contact_definition(
                replica_key=replica_key(),
                contact_definition_id=edge["name"],
                contact_layer="protein-protein",
                interaction_type=edge["name"],
                parameters=parameters,
                source_artifact_role="edge_semantics",
                source_artifact_path="evidence/edge_semantics.json",
            )
        )
    table = build_publication_table(
        "contact_definitions",
        (r for d in definitions for r in d.records()),
    )
    assert {r["interaction_type"] for r in table.records()} == {
        "backbone",
        "hbond",
        "disulfide",
        "salt_bridge",
        "ionic",
        "cation_pi",
        "aromatic_pi",
        "hydrophobic",
        "vdw",
        "residue_contact",
    }
    for definition in definitions:
        rows = definition.records()
        interaction = rows[0]["interaction_type"]
        source = next(
            e
            for e in build_edge_semantics_manifest()["edge_types"]
            if e["name"] == interaction
        )
        observed = {r["parameter_path"]: r for r in rows}
        for name, value in source["detection_criteria"].items():
            if isinstance(value, (float, int)):
                assert observed[f"$/cutoff/{name}"]["number_value"] == value


def test_pending_review_fails_the_main_bundle(inputs):
    pending = decision("5", "review", "pending_review")
    decisions = replace(
        inputs["decisions"], records=(*inputs["decisions"].records[:-1], pending)
    )
    changed = {
        **inputs,
        "decisions": decisions,
        "summary": build_dataset_qc_summary(decisions),
    }
    with pytest.raises(ValueError, match="pending_review"):
        build_dataset_release_metadata_tables(**changed)


def test_bundle_annotation_selection_subset_and_missing_authority(inputs):
    outside = replace(complete_annotations(), system_id="outside")
    with pytest.raises(ValueError, match="subset of systems"):
        build_dataset_release_metadata_tables(
            **{
                **inputs,
                "annotation_metadata": (outside,),
                "annotation_publication_system_keys": (
                    (outside.dataset_id, outside.system_id),
                ),
            }
        )
    with pytest.raises(ValueError, match="complete_for_system"):
        build_dataset_release_metadata_tables(**{**inputs, "annotation_metadata": ()})


def test_time_evidence_must_match_candidate_labels(inputs):
    evidence = inputs["temporal_evidence"][0]
    spec = evidence.dataset_spec.model_copy(
        update={
            "identity": evidence.dataset_spec.identity.model_copy(
                update={"variant_id": "other"}
            ),
        }
    )
    evidence = replace(evidence, dataset_spec=spec)
    with pytest.raises(ValueError, match="candidate identity"):
        build_dataset_release_metadata_tables(
            **{**inputs, "temporal_evidence": (evidence,)}
        )


def test_accepted_window_counts_are_validated_before_projection():
    evidence = copy.deepcopy(temporal_evidence())
    object.__setattr__(evidence.window_plan.windows[0], "missing_sample_count", 999)
    with pytest.raises(ValueError):
        build_dataset_release_time_windows((evidence,))


def snapshot(inputs):
    return json.dumps(
        {
            "decisions": inputs["decisions"].to_dict(),
            "summary": asdict(inputs["summary"]),
            "manifest": asdict(inputs["aggregation_authority"].manifest),
            "temporal": [x.to_dict() for x in inputs["temporal_evidence"]],
            "annotations": [x.to_dict() for x in inputs["annotation_metadata"]],
            "reference": load_default_napi2b_canonical_reference().to_dict(),
        },
        sort_keys=True,
        default=str,
    )


def test_pure_builder_and_input_immutability(inputs, monkeypatch):
    before = snapshot(inputs)

    def denied(*args, **kwargs):
        raise AssertionError("Publication must not access caller files or run science")

    # Pinned resource reads are the sole I/O in accepted canonical public APIs.
    # These guards catch source inspection, directory assembly and replanning.
    with monkeypatch.context() as guard:
        for name in (
            "stat",
            "exists",
            "resolve",
            "glob",
            "rglob",
            "iterdir",
            "mkdir",
            "write_text",
            "write_bytes",
        ):
            guard.setattr(Path, name, denied)
        guard.setattr(
            "mania.preprocessing.physical_time_sampling.resolve_physical_time_sampling",
            denied,
        )
        guard.setattr(
            "mania.preprocessing.physical_time_windows.plan_physical_time_windows",
            denied,
        )
        guard.setattr("mania.dataset_hard_qc.evaluate_replica_hard_qc", denied)
        guard.setattr("mania.dataset_review_qc.evaluate_dataset_review_qc", denied)
        guard.setattr("importlib.metadata.version", denied)
        first = build_dataset_release_metadata_tables(**inputs)
    assert snapshot(inputs) == before
    second = build_dataset_release_metadata_tables(**inputs)
    assert first == second
    assert first.to_dict() == second.to_dict()


def test_all_ten_tables_deterministic_bytes_and_roundtrip(inputs, tmp_path):
    first = build_dataset_release_metadata_tables(**inputs)
    with localcontext() as context:
        context.prec = 2
        second = build_dataset_release_metadata_tables(**inputs)
    assert first == second
    for left, right in zip(first.tables, second.tables, strict=True):
        a = write_publication_csv(left, tmp_path / "a" / left.relative_path)
        b = write_publication_csv(right, tmp_path / "b" / right.relative_path)
        assert a.read_bytes() == b.read_bytes()
        assert read_publication_csv(left.table_id, a) == left


def offline_smoke(root):
    """Reusable installed-wheel acceptance without trajectory runtime."""
    inputs = synthetic_inputs(root)
    bundle = build_dataset_release_metadata_tables(**inputs)
    test_candidate_history_and_explicit_inclusion(bundle, inputs)
    test_time_windows_copy_history_counts_and_requested_effective(bundle, inputs)
    assert bundle.quality_control_findings.row_count == 13
    assert bundle.quality_control_evidence.row_count == 16
    assert (
        sum(r["used_for_decision"] for r in bundle.quality_control_evidence.records())
        == 3
    )
    assert bundle.nodes.row_count == bundle.residue_annotations.row_count == 690
    assert bundle.nodes.records()[329]["canonical_resname"] == "THR"
    annotation = bundle.residue_annotations.records()[329]
    assert annotation["canonical_resname"] == "THR"
    assert annotation["is_ecd"] and annotation["is_mx35_region"]
    assert annotation["disulfide_variant_source"] == "disulfide source"
    test_all_ten_tables_deterministic_bytes_and_roundtrip(inputs, root)
    print(
        "Stage 33.B offline wheel: ten tables, history, QC, nodes, annotations, "
        "temporal, CSV PASS"
    )
