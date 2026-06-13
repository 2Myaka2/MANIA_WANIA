import json
import re
from pathlib import Path

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRuntime,
    PreprocessingConditionRuntimeInput,
    PreprocessingConditionRuntimeMetadata,
    PreprocessingManifestLoadIssue,
    PreprocessingManifestLoadResult,
    PreprocessingManifestRuntimeMetadata,
    PreprocessingRuntimeMetadataIssue,
    PreprocessingTrajectoryLoadIssue,
    collect_condition_runtime_metadata,
    collect_manifest_runtime_metadata,
    load_manifest_condition_runtimes,
    load_single_condition_runtime,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = (
    REPO_ROOT / "src" / "mania" / "preprocessing" / "trajectory_metadata.py"
)


class CountCollection:
    def __init__(self, count_name: str, count: int) -> None:
        setattr(self, count_name, count)


class LenCollection:
    def __init__(self, count: int) -> None:
        self.count = count

    def __len__(self) -> int:
        return self.count


class CountRuntime:
    def __init__(self) -> None:
        self.atoms = CountCollection("n_atoms", 10)
        self.residues = CountCollection("n_residues", 4)
        self.segments = CountCollection("n_segments", 2)
        self.trajectory = CountCollection("n_frames", 20)


class LenRuntime:
    def __init__(self) -> None:
        self.atoms = LenCollection(11)
        self.residues = LenCollection(5)
        self.segments = LenCollection(3)
        self.trajectory = LenCollection(21)


def make_runtime_input(
    condition_name: str = "normal",
) -> PreprocessingConditionRuntimeInput:
    return PreprocessingConditionRuntimeInput(
        condition_name=condition_name,
        topology_path=Path(condition_name) / "topology.tpr",
        trajectory_paths=(
            Path(condition_name) / "trajectory-1.xtc",
            Path(condition_name) / "trajectory-2.xtc",
        ),
        reference_structure_path=Path(condition_name) / "reference.pdb",
        frame_time_ps=10.0,
    )


def make_loaded_result(
    runtime_object: object,
    *,
    condition_name: str = "normal",
) -> PreprocessingConditionLoadResult:
    runtime_input = make_runtime_input(condition_name)
    runtime = PreprocessingConditionRuntime(
        condition_name=condition_name,
        runtime_object=runtime_object,
        runtime_type="tests.FakeRuntime",
        topology_path=runtime_input.topology_path,
        trajectory_paths=runtime_input.trajectory_paths,
    )
    return PreprocessingConditionLoadResult(
        condition_name=condition_name,
        runtime_input=runtime_input,
        runtime=runtime,
        status="loaded",
    )


def make_failed_result(
    condition_name: str = "tumor",
) -> PreprocessingConditionLoadResult:
    issue = PreprocessingTrajectoryLoadIssue(
        kind="load_error",
        field="condition_runtime",
        message="Expected load failure.",
    )
    return PreprocessingConditionLoadResult(
        condition_name=condition_name,
        runtime_input=make_runtime_input(condition_name),
        issues=(issue,),
        status="failed",
    )


def test_public_exports_and_existing_stage_11_apis_work() -> None:
    assert mania.preprocessing is not None
    assert collect_condition_runtime_metadata is not None
    assert collect_manifest_runtime_metadata is not None
    assert PreprocessingRuntimeMetadataIssue is not None
    assert PreprocessingConditionRuntimeMetadata is not None
    assert PreprocessingManifestRuntimeMetadata is not None
    assert load_single_condition_runtime is not None
    assert load_manifest_condition_runtimes is not None
    assert PreprocessingConditionLoadResult is not None
    assert PreprocessingManifestLoadResult is not None


def test_failed_condition_does_not_introspect_runtime() -> None:
    class ExplodingRuntime:
        def __getattribute__(self, name: str) -> object:
            if name.startswith("__"):
                return object.__getattribute__(self, name)
            raise AssertionError("failed runtime must remain opaque")

    runtime_input = make_runtime_input()
    runtime = PreprocessingConditionRuntime(
        condition_name="normal",
        runtime_object=ExplodingRuntime(),
        runtime_type="tests.ExplodingRuntime",
        topology_path=runtime_input.topology_path,
        trajectory_paths=runtime_input.trajectory_paths,
    )
    result = PreprocessingConditionLoadResult(
        condition_name="normal",
        runtime_input=runtime_input,
        runtime=runtime,
        issues=(
            PreprocessingTrajectoryLoadIssue(
                kind="load_error",
                field="condition_runtime",
                message="Expected load failure.",
            ),
        ),
        status="failed",
    )

    metadata = collect_condition_runtime_metadata(result)

    assert metadata.passed is False
    assert metadata.status == "failed"
    assert metadata.runtime_type == "tests.ExplodingRuntime"
    assert metadata.topology_path == runtime_input.topology_path
    assert metadata.trajectory_paths == runtime_input.trajectory_paths
    assert metadata.reference_structure_path == (
        runtime_input.reference_structure_path
    )
    assert metadata.frame_time_ps == 10.0
    assert metadata.trajectory_count == 2
    assert metadata.atom_count is None
    assert metadata.residue_count is None
    assert metadata.segment_count is None
    assert metadata.frame_count is None
    assert [issue.kind for issue in metadata.issues] == [
        "condition_not_loaded"
    ]
    json.dumps(metadata.to_dict())


def test_loaded_runtime_collects_preferred_counts() -> None:
    metadata = collect_condition_runtime_metadata(
        make_loaded_result(CountRuntime())
    )

    assert metadata.passed is True
    assert metadata.runtime_type == "tests.FakeRuntime"
    assert metadata.atom_count == 10
    assert metadata.residue_count == 4
    assert metadata.segment_count == 2
    assert metadata.frame_count == 20
    assert metadata.trajectory_count == 2
    assert metadata.issues == ()
    assert json.loads(json.dumps(metadata.to_dict())) == metadata.to_dict()


def test_loaded_runtime_falls_back_to_len() -> None:
    metadata = collect_condition_runtime_metadata(
        make_loaded_result(LenRuntime())
    )

    assert metadata.passed is True
    assert metadata.atom_count == 11
    assert metadata.residue_count == 5
    assert metadata.segment_count == 3
    assert metadata.frame_count == 21


def test_runtime_object_is_not_serialized() -> None:
    runtime_object = CountRuntime()
    metadata = collect_condition_runtime_metadata(
        make_loaded_result(runtime_object)
    )

    payload = metadata.to_dict()

    assert "runtime_object" not in payload
    assert repr(runtime_object) not in repr(payload)
    assert json.loads(json.dumps(payload)) == payload


def test_count_access_failure_becomes_issue_and_other_counts_survive() -> None:
    class FailingAtoms:
        @property
        def n_atoms(self) -> int:
            raise RuntimeError("private details")

    runtime = CountRuntime()
    runtime.atoms = FailingAtoms()

    metadata = collect_condition_runtime_metadata(
        make_loaded_result(runtime)
    )

    assert metadata.passed is False
    assert metadata.atom_count is None
    assert metadata.residue_count == 4
    assert metadata.segment_count == 2
    assert metadata.frame_count == 20
    assert [(issue.kind, issue.field) for issue in metadata.issues] == [
        ("runtime_attribute_error", "atom_count")
    ]
    assert "private details" not in metadata.issues[0].message
    json.dumps(metadata.to_dict())


def test_forbidden_runtime_properties_are_not_accessed() -> None:
    class SafeAtoms(CountCollection):
        @property
        def positions(self) -> object:
            raise AssertionError("positions must not be accessed")

    class SafeResidues(CountCollection):
        @property
        def resnames(self) -> object:
            raise AssertionError("resnames must not be accessed")

    class SafeTrajectory(CountCollection):
        def __iter__(self) -> object:
            raise AssertionError("trajectory must not be iterated")

    runtime = CountRuntime()
    runtime.atoms = SafeAtoms("n_atoms", 10)
    runtime.residues = SafeResidues("n_residues", 4)
    runtime.trajectory = SafeTrajectory("n_frames", 20)

    metadata = collect_condition_runtime_metadata(
        make_loaded_result(runtime)
    )

    assert metadata.passed is True
    assert metadata.atom_count == 10
    assert metadata.residue_count == 4
    assert metadata.frame_count == 20


def test_loaded_like_result_without_runtime_reports_runtime_missing() -> None:
    result = PreprocessingConditionLoadResult(
        condition_name="normal",
        runtime_input=make_runtime_input(),
        runtime=None,
        status="loaded",
    )

    metadata = collect_condition_runtime_metadata(result)

    assert metadata.passed is False
    assert metadata.runtime_type is None
    assert [issue.kind for issue in metadata.issues] == ["runtime_missing"]
    assert metadata.atom_count is None
    assert metadata.frame_count is None


def test_runtime_without_supported_counts_reports_unsupported() -> None:
    metadata = collect_condition_runtime_metadata(
        make_loaded_result(object())
    )

    assert metadata.passed is False
    assert [issue.kind for issue in metadata.issues] == [
        "unsupported_runtime"
    ]


def test_partial_runtime_reports_missing_count_issue() -> None:
    class PartialRuntime:
        atoms = CountCollection("n_atoms", 10)

    metadata = collect_condition_runtime_metadata(
        make_loaded_result(PartialRuntime())
    )

    assert metadata.atom_count == 10
    assert metadata.residue_count is None
    assert metadata.segment_count is None
    assert metadata.frame_count is None
    assert [issue.field for issue in metadata.issues] == [
        "residue_count",
        "segment_count",
        "frame_count",
    ]


def test_manifest_metadata_preserves_order_and_summaries() -> None:
    loaded = make_loaded_result(CountRuntime(), condition_name="normal")
    failed = make_failed_result("tumor")
    report = collect_manifest_runtime_metadata(
        PreprocessingManifestLoadResult(
            condition_results=(loaded, failed),
        )
    )

    assert report.condition_names == ("normal", "tumor")
    assert report.loaded_condition_names == ("normal",)
    assert report.failed_condition_names == ("tumor",)
    assert report.total_conditions == 2
    assert report.loaded_conditions == 1
    assert report.failed_conditions == 1
    assert report.passed is False
    assert report.issues == ()


def test_manifest_metadata_converts_manifest_issues() -> None:
    loaded = make_loaded_result(CountRuntime())
    source_issue = PreprocessingManifestLoadIssue(
        kind="condition_load_error",
        condition_name="tumor",
        field="condition_runtime",
        message="The condition loader raised an unexpected error.",
    )
    report = collect_manifest_runtime_metadata(
        PreprocessingManifestLoadResult(
            condition_results=(loaded,),
            issues=(source_issue,),
        )
    )

    assert report.condition_names == ("normal",)
    assert report.passed is False
    assert len(report.issues) == 1
    assert report.issues[0].kind == "manifest_load_issue"
    assert report.issues[0].condition_name == "tumor"
    assert report.issues[0].field == "condition_runtime"
    assert report.issues[0].message == source_issue.message


def test_manifest_metadata_serialization_and_lookup() -> None:
    loaded = make_loaded_result(CountRuntime(), condition_name="normal")
    report = collect_manifest_runtime_metadata(
        PreprocessingManifestLoadResult(condition_results=(loaded,))
    )

    payload = report.to_dict()

    assert report.passed is True
    assert report.metadata_for_condition("normal") is report.condition_metadata[0]
    assert report.metadata_for_condition("Normal") is None
    assert report.metadata_for_condition("missing") is None
    assert "runtime_object" not in repr(payload)
    assert json.loads(json.dumps(payload)) == payload


def test_empty_manifest_metadata_does_not_pass() -> None:
    report = PreprocessingManifestRuntimeMetadata(
        condition_metadata=(),
        issues=(),
    )

    assert report.passed is False
    assert report.total_conditions == 0


def test_metadata_source_has_no_loaders_or_scientific_operations() -> None:
    source_text = METADATA_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "require_mdanalysis",
        "load_single_condition_runtime",
        "load_manifest_condition_runtimes",
        "residues.resnames",
        ".resnames",
        "radius_of_gyration",
        "contacts",
        "run_residue_qc_from_manifest_options",
        "select_atoms",
        "positions",
    ):
        assert forbidden_text not in source_text


def test_metadata_source_has_no_forbidden_imports() -> None:
    forbidden_import_pattern = re.compile(
        r"^\s*(?:import|from)\s+"
        r"(?:MDAnalysis|numpy|pandas|networkx|pyarrow)"
        r"(?:\.|\s|$)"
    )

    for line in METADATA_PATH.read_text(encoding="utf-8").splitlines():
        assert forbidden_import_pattern.match(line) is None
