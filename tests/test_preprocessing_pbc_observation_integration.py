"""Instrumented scientific passes prove observation adds no iteration or changes."""

import json
from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_preprocessing_pbc_audit import BOX
from test_preprocessing_trajectory_contacts_compute_condition import (
    FakeAtom,
    FakeResidue,
)
from test_preprocessing_trajectory_graph_workflow_computation import (
    runtime_loading_result,
)
from test_preprocessing_trajectory_rg_compute_manifest import make_load_result

from mania.preprocessing import (
    PreprocessingFrameSamplingOptions,
    PreprocessingManifestLoadResult,
    compute_condition_contacts,
    compute_condition_rg,
    compute_manifest_contacts,
    compute_manifest_rg,
    write_contact_edges_csv,
    write_contacts_perframe_csv,
    write_rg_timeseries_csv,
)
from mania.preprocessing import trajectory_graph_workflow as workflow
from mania.preprocessing.pbc_audit import (
    build_pbc_audit,
    observe_pbc_frame_dimensions,
    observe_pbc_timestep_dimensions,
)

SAMPLING = PreprocessingFrameSamplingOptions(
    frame_start=1,
    frame_stop=7,
    frame_stride=2,
    max_frames=3,
)


class Frame:
    """Only time and dimensions are available; no coordinate access is possible."""

    def __init__(self, index, box, trajectory):
        self._index = index
        self._box = box
        self._trajectory = trajectory
        self.time = index * 2.5

    @property
    def dimensions(self):
        self._trajectory.observed.append((self._trajectory.passes, self._index))
        if isinstance(self._box, Exception):
            raise self._box
        return self._box

    def __getattr__(self, name):
        raise AssertionError(f"Unexpected timestep access: {name}")


class Trajectory:
    n_frames = 8

    def __init__(self, boxes):
        self.passes = 0
        self.yields = 0
        self.observed = []
        self.frames = [Frame(i, box, self) for i, box in enumerate(boxes)]

    def __iter__(self):
        self.passes += 1
        for frame in self.frames:
            self.yields += 1
            yield frame


class Runtime:
    def __init__(self, boxes):
        self.trajectory = Trajectory(boxes)
        self.atoms = SimpleNamespace(radius_of_gyration=lambda: 12.5)
        self.residues = [
            FakeResidue("ALA", 1, [FakeAtom(position=(0, 0, 0))]),
            FakeResidue("GLY", 2, [FakeAtom(position=(3, 0, 0))]),
        ]

    def select_atoms(self, selection):
        assert selection == "protein"
        return SimpleNamespace(residues=self.residues)


def loading(boxes=None, names=("normal", "tumor")):
    if boxes is None:
        boxes = [BOX] * 8
    runtimes = [Runtime(boxes) for _ in names]
    loaded = PreprocessingManifestLoadResult(
        tuple(
            make_load_result(name, runtime_object=runtime)
            for name, runtime in zip(names, runtimes, strict=True)
        )
    )
    return runtime_loading_result(
        condition_names=names, runtime_load_result=loaded
    ), runtimes


def scientific_bytes(result):
    return json.dumps(result.to_dict(), allow_nan=False).encode()


@pytest.mark.parametrize("compute", [compute_condition_rg, compute_condition_contacts])
@pytest.mark.parametrize(
    "dimensions", [BOX, None, (0, 20, 30, 90, 90, 90), RuntimeError("unavailable")]
)
def test_condition_hooks_exact_sampling_and_identical_science(compute, dimensions):
    source, runtimes = loading([dimensions] * 8, ("normal",))
    loaded = source.runtime_load_result.condition_results[0]
    before = compute(loaded, frame_sampling=SAMPLING)
    assert before.passed
    trajectory = runtimes[0].trajectory
    assert trajectory.observed == []
    counts = (trajectory.passes, trajectory.yields)
    observations = []
    after = compute(
        loaded, frame_sampling=SAMPLING, pbc_observation_callback=observations.append
    )
    assert after.passed and scientific_bytes(before) == scientific_bytes(after)
    assert (trajectory.passes, trajectory.yields) == (2 * counts[0], 2 * counts[1])
    assert [o.frame_index for o in observations] == [1, 3, 5]
    assert [o.frame_index for o in observations] == [
        f.frame_index for f in after.frame_results
    ]
    assert [o.time_ps for o in observations] == [f.time_ps for f in after.frame_results]
    expected = None if isinstance(dimensions, Exception) else dimensions
    assert observations == [
        observe_pbc_frame_dimensions(
            condition="normal",
            frame_index=i,
            time_ps=i * 2.5,
            dimensions=expected,
        )
        for i in (1, 3, 5)
    ]
    if compute is compute_condition_contacts:
        assert after.contact_count == before.contact_count > 0
        assert all(
            pair.minimum_distance == 3.0
            for f in after.frame_results
            for pair in f.contacts
        )


@pytest.mark.parametrize(
    "rg,contacts", [(True, True), (True, False), (False, True), (False, False)]
)
def test_canonical_pass_adds_zero_iterations_and_preserves_bytes(
    monkeypatch,
    tmp_path,
    rg,
    contacts,
):
    source, runtimes = loading(names=("tumor", "normal"))
    rg_spy = Mock(wraps=compute_manifest_rg)
    contact_spy = Mock(wraps=compute_manifest_contacts)
    monkeypatch.setattr(workflow, "_manifest_rg_computer", lambda: rg_spy)
    monkeypatch.setattr(workflow, "_manifest_contacts_computer", lambda: contact_spy)
    before = workflow.compute_preprocessing_graph_workflow_rg_contacts(
        source,
        include_rg=rg,
        include_contacts=contacts,
        frame_sampling=SAMPLING,
    )
    counts = [(r.trajectory.passes, r.trajectory.yields) for r in runtimes]
    assert all(r.trajectory.observed == [] for r in runtimes)
    assert before.pbc_observations == ()
    for spy in (rg_spy, contact_spy):
        for call in spy.call_args_list:
            assert "pbc_observation_callback" not in call.kwargs
        spy.reset_mock()
    after = workflow.compute_preprocessing_graph_workflow_rg_contacts(
        source,
        include_rg=rg,
        include_contacts=contacts,
        frame_sampling=SAMPLING,
        collect_pbc_observations=True,
    )
    assert scientific_bytes(before) == scientific_bytes(after)
    assert after.passed == before.passed == (rg or contacts)
    for runtime, (passes, yields) in zip(runtimes, counts, strict=True):
        assert (runtime.trajectory.passes, runtime.trajectory.yields) == (
            2 * passes,
            2 * yields,
        )
        assert runtime.trajectory.observed == (
            [(passes + 1, i) for i in (1, 3, 5)] if rg or contacts else []
        )
    assert [(o.condition, o.frame_index) for o in after.pbc_observations] == (
        [(name, i) for name in ("tumor", "normal") for i in (1, 3, 5)]
        if rg or contacts
        else []
    )
    if rg:
        assert "pbc_observation_callback" in rg_spy.call_args.kwargs
        assert scientific_bytes(before.rg_result) == scientific_bytes(after.rg_result)
    if contacts:
        assert ("pbc_observation_callback" in contact_spy.call_args.kwargs) is (not rg)
        assert scientific_bytes(before.contacts_result) == scientific_bytes(
            after.contacts_result
        )
    for label, writer, old, new in (
        ("rg", write_rg_timeseries_csv, before.rg_result, after.rg_result),
        (
            "edges",
            write_contact_edges_csv,
            before.contacts_result,
            after.contacts_result,
        ),
        (
            "perframe",
            write_contacts_perframe_csv,
            before.contacts_result,
            after.contacts_result,
        ),
    ):
        if old is None:
            continue
        paths = [tmp_path / f"{label}-{side}.csv" for side in ("before", "after")]
        assert writer(old, paths[0]).passed and writer(new, paths[1]).passed
        assert paths[0].read_bytes() == paths[1].read_bytes()
    if contacts:
        graph_bytes = []
        for side, computation in (("before", before), ("after", after)):
            options = workflow.PreprocessingGraphWorkflowOptions(
                source.manifest_path,
                tmp_path / side,
            )
            layout = workflow.build_preprocessing_graph_workflow_plan(
                options
            ).output_layout
            exported = workflow.export_preprocessing_graph_workflow_artifacts(
                computation,
                layout,
            )
            assert exported.passed
            graph_bytes.append(
                tuple(
                    path.read_bytes()
                    for path in (
                        exported.graph_nodes_csv_path,
                        exported.graph_edges_csv_path,
                        exported.graph_json_path,
                    )
                )
            )
        assert graph_bytes[0] == graph_bytes[1]
    with pytest.raises(FrozenInstanceError):
        after.pbc_observations = ()
    with pytest.raises(ValueError, match="pbc_observations"):
        replace(after, pbc_observations=(object(),))


def test_varying_box_observes_only_sampled_frames():
    boxes = [(999, 999, 999, 99, 99, 99)] * 8
    boxes[1] = BOX
    boxes[3] = (12, 18, 35, 85, 100, 95)
    boxes[5] = (11, 22, 25, 95, 80, 100)
    source, _ = loading(boxes, ("normal",))
    result = workflow.compute_preprocessing_graph_workflow_rg_contacts(
        source,
        frame_sampling=SAMPLING,
        collect_pbc_observations=True,
    )
    assert result.passed
    audit = build_pbc_audit(
        run_id="run",
        workflow="preprocessing_graph_export",
        condition_names=result.condition_names,
        observations=result.pbc_observations,
    )
    condition = audit.conditions[0]
    assert condition.sampled_frame_count == 3 and condition.box_varies is True
    assert condition.box_lengths_min_A == (10, 18, 25)
    assert condition.box_lengths_max_A == (12, 22, 35)
    assert condition.box_angles_min_deg == (85, 80, 90)
    assert condition.box_angles_max_deg == (95, 100, 100)


def test_helper_reads_only_dimensions_once_and_handles_absence():
    accesses = []

    class Timestep:
        def __getattribute__(self, name):
            accesses.append(name)
            if name == "dimensions":
                raise RuntimeError("unavailable")
            raise AssertionError("Coordinates/trajectory must not be accessed")

    result = observe_pbc_timestep_dimensions(
        condition="normal",
        frame_index=3,
        time_ps=None,
        timestep=Timestep(),
    )
    assert accesses == ["dimensions"]
    assert result == observe_pbc_frame_dimensions(
        condition="normal",
        frame_index=3,
        time_ps=None,
        dimensions=None,
    )
    assert (
        observe_pbc_timestep_dimensions(
            condition="normal",
            frame_index=3,
            time_ps=None,
            timestep=object(),
        )
        == result
    )
