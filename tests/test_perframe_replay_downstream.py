"""Replayed canonical CSVs enter the unchanged Stage 31 and 33 interfaces."""

import json
from dataclasses import replace

import pytest
from test_dataset_release_workflow import make_release_case
from test_perframe_observation_replay import PROFILES, mapping
from test_preprocessing_specialized_contact_execution import retained

from mania import canonical_window_tables_io as canonical_io
from mania.dataset_release_workflow import build_dataset_release
from mania.preprocessing.molecular_partner_entities import MolecularPartnerCatalog
from mania.preprocessing.perframe_observations import write_perframe_observations
from mania.preprocessing.physical_time_execution_io import (
    read_preprocessing_temporal_execution,
)
from mania.preprocessing.specialized_contact_execution import (
    PreprocessingSpecializedContactExecution,
)
from mania.preprocessing.trajectory_contacts import (
    PreprocessingConditionContactsResult,
    PreprocessingContactDetectionOptions,
    PreprocessingContactFrameResult,
    PreprocessingContactPairResult,
    PreprocessingManifestContactsResult,
)
from mania.preprocessing.window_replay import replay_window_tables
from mania.replica_aggregation_run import run_replica_aggregation
from mania.replica_aggregation_workflow import FAMILIES


@pytest.mark.parametrize("profile", PROFILES)
def test_stage31_and_stage33_accept_replayed_positive_canonical_tables(
    tmp_path, profile
):
    manifest_path, control = make_release_case(tmp_path, boundary_profile=profile)
    tables = {f.name: [] for f in FAMILIES}
    for path in control.temporal_evidence_paths:
        temporal = read_preprocessing_temporal_execution(tmp_path / path)
        binding = temporal.bindings[0]
        replica = binding.dataset_spec.identity.replica_id
        _, _, result = retained(binding=binding)
        # Use only the explicit synthetic correspondence identities supplied by
        # make_release_case. This test establishes no real partner correspondence.
        partners = tuple(
            replace(
                p,
                partner_id=f"{p.partner_kind}:local:{replica}",
                partner_name=f"synthetic-{p.partner_kind}",
            )
            for p in result.partner_catalog.partners
        )
        changes = {"partner_catalog": MolecularPartnerCatalog(partners)}
        for kind in ("lipid", "glycan"):
            frames = []
            for frame in getattr(result, f"{kind}_frame_results"):
                contacts = (
                    tuple(
                        replace(
                            c,
                            **{
                                f"{kind}_partner_id": f"{kind}:local:{replica}",
                                f"{kind}_partner_name": f"synthetic-{kind}",
                            },
                        )
                        for c in frame.contacts
                    )
                    if frame.time_ps >= 700
                    else ()
                )
                frames.append(
                    replace(
                        frame,
                        contacts=contacts,
                        contact_count=len(contacts),
                        **(
                            {
                                "excluded_contact_count": sum(
                                    c.standard_summary_excluded for c in contacts
                                )
                            }
                            if kind == "glycan"
                            else {}
                        ),
                    )
                )
            changes[f"{kind}_frame_results"] = tuple(frames)
        result = replace(result, **changes)
        contact = PreprocessingContactPairResult(
            0, 1, "ALA", "GLY", 3.0, source_residue_id=10, target_residue_id=11
        )
        protein = PreprocessingManifestContactsResult(
            (
                PreprocessingConditionContactsResult(
                    binding.execution_condition,
                    PreprocessingContactDetectionOptions(contact_selection="protein"),
                    frame_results=tuple(
                        PreprocessingContactFrameResult(
                            binding.execution_condition,
                            s.source_frame_index,
                            s.actual_time_ps,
                            (contact,) if s.actual_time_ps >= 700 else (),
                        )
                        for s in binding.sampling_plan.selected_samples
                    ),
                    status="computed",
                ),
            )
        )
        output = tmp_path / "observations" / replica
        write_perframe_observations(
            output,
            temporal,
            protein,
            PreprocessingSpecializedContactExecution((result,)),
        )
        replayed = replay_window_tables(
            output, temporal, mapping_bindings=mapping(temporal)
        )
        for family in FAMILIES:
            tables[family.name].extend(
                getattr(replayed, f"canonical_{family.name}").rows
            )
    for family, kind in zip(FAMILIES, ("edge", "lipid", "glycan"), strict=True):
        table = family.canonical_table(
            tuple(sorted(tables[family.name], key=lambda r: r.row_order))
        )
        assert table.rows
        assert getattr(canonical_io, f"write_canonical_protein_{kind}_window_csv")(
            table, tmp_path / "canonical", overwrite=True
        ).passed
    # Fixture-only metric evidence referenced the old fixture contact identity.
    # No article metric is added or inferred from replay.
    path = tmp_path / "publication_inputs.json"
    inputs = json.loads(path.read_text())
    inputs["metrics"] = []
    path.write_text(json.dumps(inputs))
    aggregation = run_replica_aggregation(
        tmp_path / "qc/replica_aggregation_manifest_qc_derived.json",
        tmp_path / "aggregation",
        overwrite=True,
    )
    assert aggregation
    bundle = build_dataset_release(manifest_path)
    assert len(bundle.tables) == 17
    assert all(f.reader(tmp_path / "aggregation" / f.filename).rows for f in FAMILIES)
