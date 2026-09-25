"""Stage 34.D.4d: complete all-layer observations and coordinate-free replay."""

import builtins
import csv
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_preprocessing_protein_edge_window_table import table_input
from test_preprocessing_specialized_contact_execution import retained

from mania import canonical_window_tables as canonical
from mania.canonical_reference_io import load_default_napi2b_canonical_reference
from mania.canonical_residue_mapping import (
    CanonicalResidueMappingRecord,
    CanonicalResidueMappingTable,
)
from mania.preprocessing import perframe_observations as persistence
from mania.preprocessing import specialized_contact_execution as specialized
from mania.preprocessing.physical_time_execution import PreprocessingTemporalExecution
from mania.preprocessing.physical_time_execution_io import (
    write_preprocessing_temporal_execution,
)
from mania.preprocessing.physical_time_windows import plan_physical_time_windows
from mania.preprocessing.protein_edge_window_execution import (
    build_preprocessing_protein_edge_window_source_table,
)
from mania.preprocessing.temporal_policy import (
    INCLUSIVE_BOUNDARY_PROFILE,
    LEGACY_BOUNDARY_PROFILE,
)
from mania.preprocessing.trajectory_contacts import (
    PreprocessingBackboneObservation,
    PreprocessingConditionContactsResult,
    PreprocessingContactDetectionOptions,
    PreprocessingContactFrameResult,
    PreprocessingContactPairResult,
    PreprocessingManifestContactsResult,
)
from mania.preprocessing.trajectory_contacts_export import write_contacts_perframe_csv
from mania.preprocessing.window_replay import replay_window_tables

PROFILES = (LEGACY_BOUNDARY_PROFILE, INCLUSIVE_BOUNDARY_PROFILE)


def case(profile=LEGACY_BOUNDARY_PROFILE, missing=(4,), *, kinds=(True, True)):
    binding = table_input(
        count=9, missing=missing, length=0.1, step=0.05, condition=None, engine="namd"
    ).temporal_execution
    binding = replace(
        binding,
        window_plan=plan_physical_time_windows(
            binding.sampling_plan,
            temporal=binding.dataset_spec.temporal,
            boundary_profile=profile,
        ),
    )
    _, _, result = retained(binding=binding, lipid=kinds[0], glycan=kinds[1])
    # A genuinely resolved zero-contact frame, including zero raw anchor contacts.
    for kind in ("lipid", "glycan"):
        frames = getattr(result, f"{kind}_frame_results")
        changed = tuple(
            replace(
                f,
                contacts=(),
                contact_count=0,
                **({"excluded_contact_count": 0} if kind == "glycan" else {}),
            )
            if f.frame_index == 1
            else f
            for f in frames
        )
        result = replace(result, **{f"{kind}_frame_results": changed})
    contact = PreprocessingContactPairResult(
        0, 1, "ALA", "GLY", 3.125, source_residue_id=10, target_residue_id="11"
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
                        () if s.requested_sample_index == 1 else (contact,),
                    )
                    for s in binding.sampling_plan.selected_samples
                ),
                status="computed",
            ),
        )
    )
    temporal = PreprocessingTemporalExecution((binding,))
    return (
        temporal,
        protein,
        specialized.PreprocessingSpecializedContactExecution((result,)),
    )


def mapping(temporal):
    reference = load_default_napi2b_canonical_reference()
    records = []
    for resid, name in (("10", "ALA"), ("11", "GLY")):
        number = next(
            i
            for i in range(1, 691)
            if reference.residue_at(i).canonical_resname == name
        )
        records.append(
            CanonicalResidueMappingRecord(
                "namd", None, resid, name, number, name, "mapped"
            )
        )
    return canonical.DatasetCanonicalResidueMappingBindings(
        tuple(
            canonical.DatasetCanonicalResidueMappingBinding(
                *b.dataset_spec.identity.replica_key,
                CanonicalResidueMappingTable(tuple(records)),
            )
            for b in temporal.bindings
        )
    )


def save(root, profile=LEGACY_BOUNDARY_PROFILE, missing=(4,), **kwargs):
    temporal, protein, special = case(profile, missing, **kwargs)
    persistence.write_perframe_observations(root, temporal, protein, special)
    assert write_preprocessing_temporal_execution(temporal, root).passed
    return temporal, protein, special


def mutate(path, change):
    value = json.loads(path.read_text())
    change(value)
    path.write_text(json.dumps(value))


@pytest.mark.parametrize("profile", PROFILES)
def test_exact_roundtrip_zero_missing_anchor_and_no_coordinates(
    tmp_path, profile, monkeypatch
):
    temporal, protein, special = save(tmp_path, profile)
    direct_protein = build_preprocessing_protein_edge_window_source_table(
        temporal, protein
    )
    direct_lipid, direct_glycan = specialized.build_specialized_contact_source_tables(
        special, temporal
    )
    bindings = mapping(temporal)
    expected = (direct_protein, direct_lipid, direct_glycan)
    profiles = {
        b.dataset_spec.identity.replica_key: b.window_plan.boundary_profile
        for b in temporal.bindings
    }
    expected_canonical = tuple(
        getattr(canonical, f"build_canonical_protein_{kind}_window_table")(
            table, mapping_bindings=bindings, boundary_profiles=profiles
        )
        for kind, table in zip(("edge", "lipid", "glycan"), expected, strict=True)
    )
    imported = builtins.__import__

    def guard(name, *args, **kwargs):
        assert not name.startswith("MDAnalysis"), "Offline replay imported MDAnalysis"
        return imported(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guard)
    forbidden = Mock(
        side_effect=AssertionError("Offline replay accessed geometry/trajectory")
    )
    for name in (
        "compute_protein_lipid_contacts",
        "compute_protein_glycan_contacts",
        "iter_selected_trajectory_frames",
        "adapt_molecular_partner_topology",
    ):
        monkeypatch.setattr(specialized, name, forbidden)
    from mania.preprocessing import trajectory_contacts

    monkeypatch.setattr(trajectory_contacts, "compute_condition_contacts", forbidden)
    original_open = Path.open
    allowed = {p.resolve() for p in tmp_path.rglob("*") if p.is_file()}
    allowed.add(
        Path(canonical.__file__).parent / "data/canonical/slc34a2_o95436_reference.json"
    )

    def guarded_open(path, *args, **kwargs):
        assert path.resolve() in allowed, f"Unexpected offline input: {path}"
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    restored = persistence.read_perframe_observations(tmp_path, temporal)
    assert restored.protein == protein
    assert restored.specialized == special
    replayed = replay_window_tables(
        tmp_path, tmp_path / "temporal_execution.json", mapping_bindings=bindings
    )
    assert (replayed.protein, replayed.lipid, replayed.glycan) == expected
    assert (
        replayed.canonical_protein,
        replayed.canonical_lipid,
        replayed.canonical_glycan,
    ) == expected_canonical
    forbidden.assert_not_called()
    index = json.loads(
        (tmp_path / persistence.PERFRAME_COMPLETION_FILENAME).read_text()
    )
    samples = index["bindings"][0]["samples"]
    assert samples[1]["state"] == "resolved"
    assert all(
        samples[1]["completion"][k]["contact_count"] == 0
        for k in ("protein", "lipid", "glycan")
    )
    assert samples[4]["state"] == "missing" and samples[4]["completion"] is None
    assert all(r.protein_residue_index != 0 for r in replayed.glycan.rows)
    anchors = [
        c
        for f in restored.specialized.condition_results[0].glycan_frame_results
        for c in f.contacts
        if c.standard_summary_excluded
    ]
    assert len(anchors) == 7 and all(c.minimum_distance_A == 1.0 for c in anchors)


@pytest.mark.parametrize(
    "damage",
    [
        "drop",
        "duplicate",
        "missing_as_zero",
        "resolved_as_missing",
        "count",
        "bool",
        "extra",
        "version",
        "complete",
        "reorder",
    ],
)
def test_completion_corruption_rejected(tmp_path, damage):
    temporal, _, _ = save(tmp_path)

    def change(value):
        samples = value["bindings"][0]["samples"]
        if damage == "drop":
            samples.pop()
        elif damage == "duplicate":
            samples[2] = samples[1]
        elif damage == "missing_as_zero":
            samples[4].update(
                state="resolved",
                completion=samples[1]["completion"],
                source_frame_index=4,
            )
        elif damage == "resolved_as_missing":
            samples[1].update(state="missing", completion=None)
        elif damage == "count":
            samples[0]["completion"]["protein"]["contact_count"] += 1
        elif damage == "bool":
            samples[1]["completion"]["protein"]["contact_count"] = False
        elif damage == "extra":
            value["extra"] = 1
        elif damage == "version":
            value["schema_version"] = "unknown"
        elif damage == "complete":
            value.pop("completion")
        else:
            samples.reverse()

    mutate(tmp_path / persistence.PERFRAME_COMPLETION_FILENAME, change)
    with pytest.raises(persistence.PerFrameObservationError):
        persistence.read_perframe_observations(tmp_path, temporal)


@pytest.mark.parametrize("kind", ("lipid", "glycan"))
@pytest.mark.parametrize(
    "damage",
    [
        "frame_drop",
        "frame_duplicate",
        "contact_drop",
        "contact_duplicate",
        "distance",
        "time",
        "partner",
        "anchor",
        "extra",
        "truncated",
        "duplicate_key",
        "count_bool",
    ],
)
def test_specialized_corruption_rejected(tmp_path, kind, damage):
    temporal, _, _ = save(tmp_path)
    path = tmp_path / persistence.SPECIALIZED_PERFRAME_FILES[kind]
    if damage == "truncated":
        path.write_text(path.read_text()[:-20])
    elif damage == "duplicate_key":
        path.write_text(
            path.read_text().replace(
                '"completion": "complete"',
                '"completion": "complete", "completion": "complete"',
            )
        )
    else:

        def change(value):
            frames = value["bindings"][0]["frames"]
            frame = frames[0]
            if damage == "frame_drop":
                frames.pop()
            elif damage == "frame_duplicate":
                frames.append(frame)
            elif damage == "contact_drop":
                frame["contacts"].pop()
            elif damage == "contact_duplicate":
                frame["contacts"].append(frame["contacts"][0])
            elif damage == "distance":
                frame["contacts"][0]["minimum_distance_A"] = 7.0
            elif damage == "time":
                frame["time_ps"] += 1
            elif damage == "partner":
                frame["contacts"][0][f"{kind}_partner_name"] = "invented"
            elif damage == "anchor":
                frame["contacts"][0]["standard_summary_excluded"] = False
            elif damage == "extra":
                frame["unexpected"] = 1
            else:
                frame["contact_count"] = True

        mutate(path, change)
    with pytest.raises(persistence.PerFrameObservationError):
        persistence.read_perframe_observations(tmp_path, temporal)


@pytest.mark.parametrize(
    "damage",
    [
        "drop",
        "duplicate",
        "reversed_duplicate",
        "header",
        "time",
        "empty",
        "extra_cell",
    ],
)
def test_protein_corruption_rejected(tmp_path, damage):
    temporal, _, _ = save(tmp_path)
    path = tmp_path / persistence.PROTEIN_PERFRAME_PATH
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    if damage == "drop":
        rows.pop()
    elif damage == "duplicate":
        rows.append(rows[-1])
    elif damage == "reversed_duplicate":
        rows[2] = rows[1]
    elif damage == "header":
        rows[0].append("unknown")
    elif damage == "time":
        rows[1][2] = "6000.0"
    elif damage == "empty":
        rows = rows[:1]
    else:
        rows[1].append("unknown")
    with path.open("w", newline="") as f:
        csv.writer(f).writerows(rows)
    with pytest.raises(persistence.PerFrameObservationError):
        persistence.read_perframe_observations(tmp_path, temporal)


def test_same_saved_frames_multiple_profiles_and_schedules(tmp_path):
    temporal, protein, special = save(tmp_path, missing=())
    files = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    results = []
    for profile in PROFILES:
        binding = temporal.bindings[0]
        execution = PreprocessingTemporalExecution(
            (
                replace(
                    binding,
                    window_plan=plan_physical_time_windows(
                        binding.sampling_plan,
                        temporal=binding.dataset_spec.temporal,
                        boundary_profile=profile,
                    ),
                ),
            )
        )
        result = replay_window_tables(
            tmp_path, execution, mapping_bindings=mapping(execution)
        )
        results.append(result)
        assert result.protein == build_preprocessing_protein_edge_window_source_table(
            execution, protein
        )
        assert (
            result.lipid,
            result.glycan,
        ) == specialized.build_specialized_contact_source_tables(special, execution)
        assert len({r.window_id for r in result.protein.rows}) == 7
    assert results[0].protein.rows[0].n_contact_frames == 1
    assert results[1].protein.rows[0].n_contact_frames == 2
    # Index 2 contributes at the right edge of the first inclusive window and
    # also to the next two windows, without recomputing a single observation.
    assert results[1].protein.rows[1].n_contact_frames == 2
    binding = temporal.bindings[0]
    spec = binding.dataset_spec.model_copy(
        update={
            "temporal": binding.dataset_spec.temporal.model_copy(
                update={"window_length_ns": 0.2, "window_step_ns": 0.1}
            )
        }
    )
    alternate = PreprocessingTemporalExecution(
        (
            replace(
                binding,
                dataset_spec=spec,
                window_plan=plan_physical_time_windows(
                    binding.sampling_plan, temporal=spec.temporal
                ),
            ),
        )
    )
    replay_window_tables(tmp_path, alternate)
    assert all(p.read_bytes() == data for p, data in files.items())


@pytest.mark.parametrize("kinds", [(False, False), (True, False), (False, True)])
def test_absent_partner_kind_is_not_applicable(tmp_path, kinds):
    temporal, _, special = save(tmp_path, kinds=kinds)
    restored = persistence.read_perframe_observations(tmp_path, temporal)
    assert restored.specialized == special
    replay_window_tables(tmp_path, temporal)


def test_writer_rejects_unprocessed_frames_duplicates_and_reuses_protein_format(
    tmp_path,
):
    temporal, protein, special = case()
    c = protein.condition_results[0]
    f = c.frame_results[0]
    for altered in (
        replace(c, frame_results=c.frame_results[:-1]),
        replace(
            c, frame_results=(replace(f, contacts=2 * f.contacts), *c.frame_results[1:])
        ),
    ):
        with pytest.raises(persistence.PerFrameObservationError):
            persistence.write_perframe_observations(
                tmp_path,
                temporal,
                replace(protein, condition_results=(altered,)),
                special,
            )
    expected = tmp_path / "expected.csv"
    assert write_contacts_perframe_csv(protein, expected).passed
    persistence.write_perframe_observations(tmp_path, temporal, protein, special)
    assert (
        tmp_path / persistence.PROTEIN_PERFRAME_PATH
    ).read_bytes() == expected.read_bytes()
    with pytest.raises(persistence.PerFrameObservationError):
        persistence.write_perframe_observations(tmp_path, temporal, protein, special)


def test_backbone_and_typed_protein_identity_roundtrip(tmp_path):
    temporal, protein, special = case()
    c = protein.condition_results[0]
    backbone = PreprocessingBackboneObservation(
        0, 1, "ALA", "GLY", 3.0, source_residue_id=10, target_residue_id="11"
    )
    protein = replace(
        protein,
        condition_results=(
            replace(
                c,
                frame_results=tuple(
                    replace(f, backbone_observations=(backbone,))
                    for f in c.frame_results
                ),
            ),
        ),
    )
    persistence.write_perframe_observations(tmp_path, temporal, protein, special)
    restored = persistence.read_perframe_observations(tmp_path, temporal)
    assert restored.protein == protein
    assert (
        type(
            restored.protein.condition_results[0]
            .frame_results[0]
            .contacts[0]
            .target_residue_id
        )
        is str
    )


def test_prepared_frame_identity_is_explicit_and_roundtrips(tmp_path):
    temporal, protein, special = case()
    binding = temporal.bindings[0]
    indexes = tuple(
        100 + i * 2 for i in range(len(binding.sampling_plan.selected_samples))
    )
    persistence.write_perframe_observations(
        tmp_path,
        temporal,
        protein,
        special,
        prepared_frame_indexes={binding.execution_condition: indexes},
    )
    restored = persistence.read_perframe_observations(tmp_path, temporal)
    assert restored.prepared_frame_indexes == ((binding.execution_condition, indexes),)
    replay_window_tables(tmp_path, temporal)
    mutate(
        tmp_path / persistence.PERFRAME_COMPLETION_FILENAME,
        lambda value: value["bindings"][0]["samples"][2].update(
            prepared_frame_index=100
        ),
    )
    with pytest.raises(persistence.PerFrameObservationError):
        persistence.read_perframe_observations(tmp_path, temporal)


def test_missing_breaks_episode_and_positive_distances_are_lossless(tmp_path):
    temporal, protein, special = case(INCLUSIVE_BOUNDARY_PROFILE)
    condition = special.condition_results[0]
    frames = tuple(
        replace(
            f,
            contacts=tuple(
                replace(c, minimum_distance_A=3.141592653589793 + f.frame_index / 10)
                for c in f.contacts
            ),
        )
        for f in condition.lipid_frame_results
    )
    special = replace(
        special, condition_results=(replace(condition, lipid_frame_results=frames),)
    )
    persistence.write_perframe_observations(tmp_path, temporal, protein, special)
    assert (
        persistence.read_perframe_observations(tmp_path, temporal).specialized
        == special
    )
    result = replay_window_tables(tmp_path, temporal)
    for table in (result.protein, result.lipid, result.glycan):
        rows = [r for r in table.rows if r.window_index == 3]
        assert rows
        for row in rows:
            assert row.n_contact_frames == row.resolved_frame_count == 2
            assert row.missing_sample_count == 1 and row.occupancy == 1.0
            assert row.n_contact_episodes == 2
            assert row.mean_episode_length_ns == row.max_episode_length_ns == 0.0


def test_interrupted_overwrite_invalidates_completion(tmp_path, monkeypatch):
    temporal, protein, special = save(tmp_path)
    original = persistence._write_json

    def fail(value, path, overwrite):
        if path.name == "protein_glycan_perframe.json":
            raise OSError("interrupted")
        return original(value, path, overwrite)

    monkeypatch.setattr(persistence, "_write_json", fail)
    with pytest.raises(OSError):
        persistence.write_perframe_observations(
            tmp_path, temporal, protein, special, overwrite=True
        )
    assert not (tmp_path / persistence.PERFRAME_COMPLETION_FILENAME).exists()
    with pytest.raises(persistence.PerFrameObservationError):
        persistence.read_perframe_observations(tmp_path, temporal)


@pytest.mark.parametrize("field", ["dataset_id", "replica_id"])
def test_replay_rejects_changed_dataset_identity(tmp_path, field):
    temporal, _, _ = save(tmp_path)
    binding = temporal.bindings[0]
    altered = replace(
        binding,
        dataset_spec=binding.dataset_spec.model_copy(
            update={
                "identity": binding.dataset_spec.identity.model_copy(
                    update={field: "different"}
                )
            }
        ),
    )
    with pytest.raises(persistence.PerFrameObservationError):
        replay_window_tables(tmp_path, PreprocessingTemporalExecution((altered,)))
