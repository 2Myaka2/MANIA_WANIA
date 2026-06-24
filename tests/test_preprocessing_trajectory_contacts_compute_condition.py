import csv
import json
import math
import re
from collections.abc import Iterator
from pathlib import Path

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionContactsResult,
    PreprocessingConditionLoadResult,
    PreprocessingConditionRuntime,
    PreprocessingConditionRuntimeInput,
    PreprocessingContactDefinition,
    PreprocessingContactDetectionOptions,
    PreprocessingContactFrameResult,
    PreprocessingContactPairResult,
    PreprocessingFrameSamplingOptions,
    PreprocessingManifestContactsResult,
    PreprocessingTrajectoryLoadIssue,
    compute_condition_contacts,
    write_contact_edges_csv,
    write_contacts_perframe_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTACTS_MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_contacts.py"
)
MISSING = object()


class FakeAtom:
    def __init__(
        self,
        name: object = "CA",
        element: object = "C",
        position: object = (0.0, 0.0, 0.0),
    ) -> None:
        if name is not MISSING:
            self.name = name
        if element is not MISSING:
            self.element = element
        if position is not MISSING:
            self.position = position


class FakeAtomGroup:
    def __init__(
        self,
        atoms: list[FakeAtom],
        *,
        positions: object = MISSING,
    ) -> None:
        self._atoms = atoms
        if positions is not MISSING:
            self.positions = positions

    def __iter__(self) -> Iterator[FakeAtom]:
        return iter(self._atoms)


class FakeResidue:
    def __init__(
        self,
        resname: str,
        resid: object,
        atoms: list[FakeAtom],
        *,
        segid: object = "PROA",
        positions: object = MISSING,
    ) -> None:
        self.resname = resname
        self.resid = resid
        self.atoms = FakeAtomGroup(atoms, positions=positions)
        if segid is not MISSING:
            self.segid = segid


class FakeTimestep:
    def __init__(
        self,
        time: object = MISSING,
        *,
        positions: tuple[object, ...] | None = None,
    ) -> None:
        if time is not MISSING:
            self.time = time
        self.positions = positions


class FakeTrajectory:
    def __init__(
        self,
        frames: list[FakeTimestep],
        atoms: list[FakeAtom],
        *,
        fail_after: int | None = None,
    ) -> None:
        self.frames = frames
        self.atoms = atoms
        self.fail_after = fail_after

    def __iter__(self) -> Iterator[FakeTimestep]:
        for frame_index, frame in enumerate(self.frames):
            if self.fail_after == frame_index:
                raise RuntimeError("private iteration details")
            if frame.positions is not None:
                for atom, position in zip(
                    self.atoms,
                    frame.positions,
                    strict=True,
                ):
                    atom.position = position
            yield frame


class FakeRuntime:
    def __init__(self, residues: list[FakeResidue], trajectory: object) -> None:
        self.residues = residues
        self.trajectory = trajectory


def make_runtime_input(
    *,
    frame_time_ps: float | None = 2.5,
) -> PreprocessingConditionRuntimeInput:
    return PreprocessingConditionRuntimeInput(
        condition_name="normal",
        topology_path=Path("normal/topology.tpr"),
        trajectory_paths=(Path("normal/trajectory.xtc"),),
        frame_time_ps=frame_time_ps,
    )


def make_loaded_result(
    runtime_object: object,
    *,
    frame_time_ps: float | None = 2.5,
) -> PreprocessingConditionLoadResult:
    runtime_input = make_runtime_input(frame_time_ps=frame_time_ps)
    return PreprocessingConditionLoadResult(
        condition_name="normal",
        runtime_input=runtime_input,
        runtime=PreprocessingConditionRuntime(
            condition_name="normal",
            runtime_object=runtime_object,
            runtime_type="tests.FakeRuntime",
            topology_path=runtime_input.topology_path,
            trajectory_paths=runtime_input.trajectory_paths,
        ),
        status="loaded",
    )


def make_runtime(
    residues: list[FakeResidue],
    frames: list[FakeTimestep] | None = None,
    *,
    fail_after: int | None = None,
) -> FakeRuntime:
    if frames is None:
        frames = [FakeTimestep(0.0)]
    atoms = [
        atom
        for residue in residues
        for atom in residue.atoms
    ]
    return FakeRuntime(
        residues,
        FakeTrajectory(frames, atoms, fail_after=fail_after),
    )


def two_residue_runtime(
    distance: float,
    *,
    frames: list[FakeTimestep] | None = None,
) -> FakeRuntime:
    source = FakeAtom(position=(0.0, 0.0, 0.0))
    target = FakeAtom(position=(distance, 0.0, 0.0))
    return make_runtime(
        [
            FakeResidue("ALA", 10, [source]),
            FakeResidue("GLY", 11, [target]),
        ],
        frames,
    )


def test_public_exports_and_import_safety() -> None:
    assert mania.preprocessing is not None
    assert compute_condition_contacts is not None
    assert PreprocessingContactDefinition is not None
    assert PreprocessingContactDetectionOptions is not None
    assert PreprocessingContactPairResult is not None
    assert PreprocessingContactFrameResult is not None
    assert PreprocessingConditionContactsResult is not None
    assert PreprocessingManifestContactsResult is not None


def test_failed_load_maps_issues_without_runtime_introspection() -> None:
    runtime_input = make_runtime_input()
    failed = PreprocessingConditionLoadResult(
        condition_name="normal",
        runtime_input=runtime_input,
        issues=(
            PreprocessingTrajectoryLoadIssue(
                kind="load_error",
                field="runtime",
                message="Expected load failure.",
            ),
        ),
        status="failed",
    )

    result = compute_condition_contacts(failed)

    assert result.status == "failed"
    assert result.passed is False
    assert result.frame_results == ()
    assert [issue.kind for issue in result.issues] == [
        "condition_load_issue",
        "missing_runtime_object",
    ]


def test_failed_load_without_specific_issue_reports_not_loaded() -> None:
    result = compute_condition_contacts(
        PreprocessingConditionLoadResult(
            condition_name="normal",
            runtime_input=make_runtime_input(),
            status="failed",
        )
    )

    assert [issue.kind for issue in result.issues] == [
        "condition_not_loaded",
        "missing_runtime_object",
    ]


def test_loaded_result_without_runtime_reports_missing_runtime() -> None:
    result = compute_condition_contacts(
        PreprocessingConditionLoadResult(
            condition_name="normal",
            runtime_input=make_runtime_input(),
            status="loaded",
        )
    )

    assert result.status == "failed"
    assert [issue.kind for issue in result.issues] == [
        "missing_runtime_object"
    ]


def test_runtime_wrapper_without_object_reports_missing_runtime() -> None:
    result = compute_condition_contacts(make_loaded_result(None))

    assert result.status == "failed"
    assert [issue.kind for issue in result.issues] == [
        "missing_runtime_object"
    ]


def test_failed_wrapper_without_object_preserves_both_issue_kinds() -> None:
    loaded = make_loaded_result(None)
    failed = PreprocessingConditionLoadResult(
        condition_name=loaded.condition_name,
        runtime_input=loaded.runtime_input,
        runtime=loaded.runtime,
        issues=(
            PreprocessingTrajectoryLoadIssue(
                kind="load_error",
                field="runtime",
                message="Expected load failure.",
            ),
        ),
        status="failed",
    )

    result = compute_condition_contacts(failed)

    assert [issue.kind for issue in result.issues] == [
        "condition_load_issue",
        "missing_runtime_object",
    ]


def test_missing_trajectory_returns_failed_result() -> None:
    class RuntimeWithoutTrajectory:
        residues: list[object] = []

    result = compute_condition_contacts(
        make_loaded_result(RuntimeWithoutTrajectory())
    )

    assert result.status == "failed"
    assert [issue.kind for issue in result.issues] == ["missing_trajectory"]


def test_missing_residues_returns_failed_result() -> None:
    class RuntimeWithoutResidues:
        trajectory: list[FakeTimestep] = [FakeTimestep()]

    result = compute_condition_contacts(
        make_loaded_result(RuntimeWithoutResidues())
    )

    assert result.status == "failed"
    assert [issue.kind for issue in result.issues] == ["missing_residues"]


def test_unsupported_duplicate_pair_mode_fails() -> None:
    result = compute_condition_contacts(
        make_loaded_result(two_residue_runtime(1.0)),
        options=PreprocessingContactDetectionOptions(
            exclude_duplicate_pairs=False
        ),
    )

    assert result.status == "failed"
    assert [issue.kind for issue in result.issues] == [
        "unsupported_duplicate_pair_mode"
    ]


def test_single_frame_detects_contact_and_maps_pair_fields() -> None:
    result = compute_condition_contacts(
        make_loaded_result(two_residue_runtime(3.0))
    )

    assert result.status == "computed"
    assert result.passed is True
    assert result.frame_count == 1
    assert result.contact_count == 1
    contact = result.frame_results[0].contacts[0]
    assert contact.source_residue_index == 0
    assert contact.target_residue_index == 1
    assert contact.source_residue_id == 10
    assert contact.target_residue_id == 11
    assert contact.source_resname == "ALA"
    assert contact.target_resname == "GLY"
    assert contact.source_segid == "PROA"
    assert contact.target_segid == "PROA"
    assert contact.minimum_distance == 3.0
    assert contact.distance_unit == "angstrom"
    assert contact.atom_filter == "heavy"


def test_distance_beyond_cutoff_is_not_a_contact() -> None:
    result = compute_condition_contacts(
        make_loaded_result(two_residue_runtime(4.5001))
    )

    assert result.status == "computed"
    assert result.passed is True
    assert result.contact_count == 0


def test_distance_equal_to_cutoff_is_a_contact() -> None:
    result = compute_condition_contacts(
        make_loaded_result(two_residue_runtime(4.5))
    )

    assert result.contact_count == 1
    assert result.frame_results[0].contacts[0].minimum_distance == 4.5


def test_heavy_filter_excludes_hydrogen_only_proximity() -> None:
    residues = [
        FakeResidue(
            "ALA",
            1,
            [
                FakeAtom("CA", "C", (0.0, 0.0, 0.0)),
                FakeAtom("H1", "H", (10.0, 0.0, 0.0)),
            ],
        ),
        FakeResidue(
            "GLY",
            2,
            [
                FakeAtom("CA", "C", (20.0, 0.0, 0.0)),
                FakeAtom("H2", "H", (10.1, 0.0, 0.0)),
            ],
        ),
    ]

    result = compute_condition_contacts(
        make_loaded_result(make_runtime(residues))
    )

    assert result.status == "computed"
    assert result.contact_count == 0


def test_all_filter_includes_hydrogen_proximity() -> None:
    residues = [
        FakeResidue(
            "ALA",
            1,
            [
                FakeAtom("CA", "C", (0.0, 0.0, 0.0)),
                FakeAtom("H1", "H", (10.0, 0.0, 0.0)),
            ],
        ),
        FakeResidue(
            "GLY",
            2,
            [
                FakeAtom("CA", "C", (20.0, 0.0, 0.0)),
                FakeAtom("H2", "H", (10.1, 0.0, 0.0)),
            ],
        ),
    ]

    result = compute_condition_contacts(
        make_loaded_result(make_runtime(residues)),
        options=PreprocessingContactDetectionOptions(atom_filter="all"),
    )

    assert result.contact_count == 1
    assert math.isclose(
        result.frame_results[0].contacts[0].minimum_distance,
        0.1,
    )


def test_heavy_filter_falls_back_from_element_to_atom_name() -> None:
    residues = [
        FakeResidue("ALA", 1, [FakeAtom("H1", "C", (0.0, 0.0, 0.0))]),
        FakeResidue("GLY", 2, [FakeAtom("H2", "C", (0.1, 0.0, 0.0))]),
    ]

    result = compute_condition_contacts(
        make_loaded_result(make_runtime(residues))
    )

    assert result.status == "computed"
    assert result.contact_count == 0


def test_skip_resnames_excludes_residue() -> None:
    residues = [
        FakeResidue("ALA", 1, [FakeAtom(position=(0.0, 0.0, 0.0))]),
        FakeResidue("HOH", 2, [FakeAtom(position=(1.0, 0.0, 0.0))]),
    ]

    result = compute_condition_contacts(
        make_loaded_result(make_runtime(residues)),
        options=PreprocessingContactDetectionOptions(
            skip_resnames=("HOH",)
        ),
    )

    assert result.status == "computed"
    assert result.contact_count == 0


def test_same_residue_and_reverse_duplicate_are_not_emitted() -> None:
    residue = FakeResidue(
        "ALA",
        1,
        [
            FakeAtom(position=(0.0, 0.0, 0.0)),
            FakeAtom(position=(0.1, 0.0, 0.0)),
        ],
    )
    other = FakeResidue(
        "GLY",
        2,
        [FakeAtom(position=(0.2, 0.0, 0.0))],
    )

    result = compute_condition_contacts(
        make_loaded_result(make_runtime([residue, other]))
    )

    assert result.contact_count == 1
    assert [
        (
            contact.source_residue_index,
            contact.target_residue_index,
        )
        for contact in result.frame_results[0].contacts
    ] == [(0, 1)]


def test_multiple_pairs_are_sorted_by_original_residue_index() -> None:
    residues = [
        FakeResidue("SER", 30, [FakeAtom(position=(0.0, 0.0, 0.0))]),
        FakeResidue("ALA", 10, [FakeAtom(position=(1.0, 0.0, 0.0))]),
        FakeResidue("GLY", 20, [FakeAtom(position=(2.0, 0.0, 0.0))]),
    ]

    result = compute_condition_contacts(
        make_loaded_result(make_runtime(residues))
    )

    assert [
        (
            contact.source_residue_index,
            contact.target_residue_index,
        )
        for contact in result.frame_results[0].contacts
    ] == [(0, 1), (0, 2), (1, 2)]


def test_multiple_frames_use_trajectory_order_and_positions() -> None:
    source = FakeAtom(position=(0.0, 0.0, 0.0))
    target = FakeAtom(position=(10.0, 0.0, 0.0))
    residues = [
        FakeResidue("ALA", 1, [source]),
        FakeResidue("GLY", 2, [target]),
    ]
    frames = [
        FakeTimestep(7.0, positions=((0.0, 0.0, 0.0), (3.0, 0.0, 0.0))),
        FakeTimestep(9.0, positions=((0.0, 0.0, 0.0), (8.0, 0.0, 0.0))),
    ]

    result = compute_condition_contacts(
        make_loaded_result(make_runtime(residues, frames))
    )

    assert [frame.frame_index for frame in result.frame_results] == [0, 1]
    assert [frame.time_ps for frame in result.frame_results] == [7.0, 9.0]
    assert [frame.contact_count for frame in result.frame_results] == [1, 0]


def test_frame_stride_computes_sampled_source_frames_and_exports(
    tmp_path: Path,
) -> None:
    source = FakeAtom(position=(0.0, 0.0, 0.0))
    target = FakeAtom(position=(10.0, 0.0, 0.0))
    residues = [
        FakeResidue("ALA", 1, [source]),
        FakeResidue("GLY", 2, [target]),
    ]
    frames = [
        FakeTimestep(positions=((0.0, 0.0, 0.0), (3.0, 0.0, 0.0))),
        FakeTimestep(positions=((0.0, 0.0, 0.0), (3.0, 0.0, 0.0))),
        FakeTimestep(positions=((0.0, 0.0, 0.0), (8.0, 0.0, 0.0))),
        FakeTimestep(positions=((0.0, 0.0, 0.0), (3.0, 0.0, 0.0))),
    ]

    result = compute_condition_contacts(
        make_loaded_result(
            make_runtime(residues, frames),
            frame_time_ps=2.5,
        ),
        frame_sampling=PreprocessingFrameSamplingOptions(frame_stride=2),
    )

    assert result.status == "computed"
    assert result.passed is True
    assert result.frame_count == 2
    assert result.contact_count == 1
    assert [frame.frame_index for frame in result.frame_results] == [0, 2]
    assert [frame.time_ps for frame in result.frame_results] == [0.0, 5.0]
    assert [frame.contact_count for frame in result.frame_results] == [1, 0]

    perframe_path = tmp_path / "contacts_perframe.csv"
    edges_path = tmp_path / "contact_edges.csv"
    perframe_result = write_contacts_perframe_csv(result, perframe_path)
    edges_result = write_contact_edges_csv(result, edges_path)

    assert perframe_result.passed is True
    assert edges_result.passed is True
    with perframe_path.open(encoding="utf-8", newline="") as csv_file:
        perframe_rows = list(csv.DictReader(csv_file))
    with edges_path.open(encoding="utf-8", newline="") as csv_file:
        edge_rows = list(csv.DictReader(csv_file))

    assert [row["frame_index"] for row in perframe_rows] == ["0"]
    assert {row["frame_index"] for row in perframe_rows} == {"0"}
    assert len(edge_rows) == 1
    assert edge_rows[0]["contact_frame_count"] == "1"
    assert edge_rows[0]["total_frame_count"] == "2"
    assert float(edge_rows[0]["contact_frequency"]) == 0.5


def test_time_falls_back_to_declared_frame_interval() -> None:
    frames = [FakeTimestep(), FakeTimestep(), FakeTimestep()]

    result = compute_condition_contacts(
        make_loaded_result(
            two_residue_runtime(3.0, frames=frames),
            frame_time_ps=2.5,
        )
    )

    assert [frame.time_ps for frame in result.frame_results] == [
        0.0,
        2.5,
        5.0,
    ]


def test_invalid_timestep_time_falls_back_to_frame_interval() -> None:
    result = compute_condition_contacts(
        make_loaded_result(
            two_residue_runtime(
                3.0,
                frames=[FakeTimestep(float("nan"))],
            ),
            frame_time_ps=2.5,
        )
    )

    assert result.frame_results[0].time_ps == 0.0


def test_time_can_be_none_without_failing() -> None:
    result = compute_condition_contacts(
        make_loaded_result(
            two_residue_runtime(3.0, frames=[FakeTimestep()]),
            frame_time_ps=None,
        )
    )

    assert result.status == "computed"
    assert result.passed is True
    assert result.frame_results[0].time_ps is None


def test_invalid_atom_position_creates_recoverable_issue() -> None:
    residues = [
        FakeResidue("ALA", 1, [FakeAtom(position=(0.0, 1.0))]),
        FakeResidue("GLY", 2, [FakeAtom(position=(1.0, 0.0, 0.0))]),
    ]

    result = compute_condition_contacts(
        make_loaded_result(make_runtime(residues))
    )

    assert result.status == "partial"
    assert result.frame_count == 1
    assert result.contact_count == 0
    assert [issue.kind for issue in result.frame_results[0].issues] == [
        "invalid_atom_position"
    ]


def test_missing_atom_position_creates_recoverable_issue() -> None:
    residues = [
        FakeResidue("ALA", 1, [FakeAtom(position=MISSING)]),
        FakeResidue("GLY", 2, [FakeAtom(position=(1.0, 0.0, 0.0))]),
    ]

    result = compute_condition_contacts(
        make_loaded_result(make_runtime(residues))
    )

    assert result.status == "partial"
    assert [issue.kind for issue in result.frame_results[0].issues] == [
        "missing_atom_position"
    ]


def test_atom_group_positions_are_used_as_fallback() -> None:
    residues = [
        FakeResidue(
            "ALA",
            1,
            [FakeAtom(position=MISSING)],
            positions=((0.0, 0.0, 0.0),),
        ),
        FakeResidue(
            "GLY",
            2,
            [FakeAtom(position=MISSING)],
            positions=((1.0, 0.0, 0.0),),
        ),
    ]

    result = compute_condition_contacts(
        make_loaded_result(make_runtime(residues))
    )

    assert result.status == "computed"
    assert result.contact_count == 1


def test_iteration_failure_after_frame_preserves_partial_result() -> None:
    runtime = two_residue_runtime(
        3.0,
        frames=[FakeTimestep(0.0), FakeTimestep(1.0)],
    )
    runtime.trajectory.fail_after = 1

    result = compute_condition_contacts(make_loaded_result(runtime))

    assert result.status == "partial"
    assert result.frame_count == 1
    assert result.passed is False
    assert [issue.kind for issue in result.issues] == [
        "frame_iteration_error"
    ]


def test_empty_trajectory_fails_deterministically() -> None:
    result = compute_condition_contacts(
        make_loaded_result(two_residue_runtime(3.0, frames=[]))
    )

    assert result.status == "failed"
    assert result.frame_results == ()
    assert [issue.kind for issue in result.issues] == [
        "frame_iteration_error"
    ]


def test_no_selected_atoms_is_a_successful_zero_contact_frame() -> None:
    residues = [
        FakeResidue("ALA", 1, [FakeAtom("H1", "H", MISSING)]),
        FakeResidue("GLY", 2, [FakeAtom("H2", "H", MISSING)]),
    ]

    result = compute_condition_contacts(
        make_loaded_result(make_runtime(residues))
    )

    assert result.status == "computed"
    assert result.passed is True
    assert result.contact_count == 0
    assert result.frame_results[0].issues == ()


def test_result_is_nested_json_safe() -> None:
    result = compute_condition_contacts(
        make_loaded_result(two_residue_runtime(3.0))
    )

    payload = result.to_dict()

    assert payload["frame_results"] == [
        result.frame_results[0].to_dict()
    ]
    assert payload["frame_results"][0]["contacts"] == [
        result.frame_results[0].contacts[0].to_dict()
    ]
    assert json.loads(json.dumps(payload)) == payload


def test_source_boundary_excludes_loading_aggregation_and_exports() -> None:
    source = CONTACTS_MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "load_single_condition_runtime",
        "load_manifest_condition_runtimes",
        "require_mdanalysis",
        "compute_manifest_contacts",
        "write_contacts",
        "validate_contacts",
        "compare_contacts",
        "contacts_perframe",
        "contact_edges",
        "report_bundle",
        "nodes.csv",
        "edges.csv",
        "graph.json",
    ):
        assert forbidden_text not in source


def test_source_has_no_forbidden_scientific_imports() -> None:
    forbidden_import_pattern = re.compile(
        r"^\s*(?:import|from)\s+"
        r"(?:MDAnalysis|numpy|pandas|networkx|pyarrow)"
        r"(?:\.|\s|$)"
    )

    for line in CONTACTS_MODULE_PATH.read_text(
        encoding="utf-8"
    ).splitlines():
        assert forbidden_import_pattern.match(line) is None
