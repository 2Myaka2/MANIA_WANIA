import json
import re
from pathlib import Path

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRuntime,
    PreprocessingConditionRuntimeInput,
    PreprocessingTrajectoryLoadIssue,
    TrajectoryInputConfig,
    get_mdanalysis_status,
    is_mdanalysis_available,
    require_mdanalysis,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_MODULE_PATH = (
    REPO_ROOT / "src" / "mania" / "preprocessing" / "trajectory_runtime.py"
)
RUNTIME_SOURCE_DIR = REPO_ROOT / "src" / "mania"


def make_runtime_input() -> PreprocessingConditionRuntimeInput:
    return PreprocessingConditionRuntimeInput(
        condition_name="normal",
        topology_path=Path("normal/topology.tpr"),
        trajectory_paths=(
            Path("normal/trajectory-1.xtc"),
            Path("normal/trajectory-2.xtc"),
        ),
        reference_structure_path=Path("normal/reference.pdb"),
        frame_time_ps=10.0,
    )


def make_runtime() -> PreprocessingConditionRuntime:
    return PreprocessingConditionRuntime(
        condition_name="normal",
        runtime_object=object(),
        runtime_type="fake-runtime",
        topology_path=Path("normal/topology.tpr"),
        trajectory_paths=(Path("normal/trajectory.xtc"),),
    )


def test_public_preprocessing_import_does_not_require_mdanalysis() -> None:
    assert mania.preprocessing is not None


def test_public_trajectory_runtime_exports_work() -> None:
    assert PreprocessingTrajectoryLoadIssue is not None
    assert PreprocessingConditionRuntimeInput is not None
    assert PreprocessingConditionRuntime is not None
    assert PreprocessingConditionLoadResult is not None


def test_load_issue_to_dict_is_json_serializable() -> None:
    issue = PreprocessingTrajectoryLoadIssue(
        kind="missing_topology_path",
        field="topology_path",
        message="Topology path is unavailable",
        path=Path("normal/topology.tpr"),
    )

    payload = issue.to_dict()

    assert json.loads(json.dumps(payload)) == payload
    assert payload["path"] == "normal/topology.tpr"


def test_runtime_input_to_dict_is_json_serializable() -> None:
    payload = make_runtime_input().to_dict()

    assert json.loads(json.dumps(payload)) == payload
    assert payload["topology_path"] == "normal/topology.tpr"
    assert payload["trajectory_paths"] == [
        "normal/trajectory-1.xtc",
        "normal/trajectory-2.xtc",
    ]
    assert payload["reference_structure_path"] == "normal/reference.pdb"
    assert payload["frame_time_ps"] == 10.0


def test_from_manifest_condition_resolves_relative_paths(
    tmp_path: Path,
) -> None:
    condition = TrajectoryInputConfig(
        condition="manifest-normal",
        topology_path="inputs/topology.tpr",
        trajectory_paths=["inputs/trajectory.xtc"],
        reference_structure_path="inputs/reference.pdb",
    )

    runtime_input = PreprocessingConditionRuntimeInput.from_manifest_condition(
        "normal",
        condition,
        base_dir=tmp_path,
    )

    assert runtime_input.condition_name == "normal"
    assert runtime_input.topology_path == tmp_path / "inputs/topology.tpr"
    assert runtime_input.trajectory_paths == (
        tmp_path / "inputs/trajectory.xtc",
    )
    assert (
        runtime_input.reference_structure_path
        == tmp_path / "inputs/reference.pdb"
    )
    assert runtime_input.frame_time_ps is None


def test_from_manifest_condition_keeps_absolute_paths(
    tmp_path: Path,
) -> None:
    topology_path = tmp_path / "topology.tpr"
    trajectory_path = tmp_path / "trajectory.xtc"
    reference_path = tmp_path / "reference.pdb"
    condition = TrajectoryInputConfig(
        condition="normal",
        topology_path=topology_path,
        trajectory_paths=[trajectory_path],
        reference_structure_path=reference_path,
    )

    runtime_input = PreprocessingConditionRuntimeInput.from_manifest_condition(
        "normal",
        condition,
        base_dir=tmp_path / "unrelated",
    )

    assert runtime_input.topology_path == topology_path
    assert runtime_input.trajectory_paths == (trajectory_path,)
    assert runtime_input.reference_structure_path == reference_path


def test_from_manifest_condition_without_base_keeps_relative_paths() -> None:
    condition = TrajectoryInputConfig(
        condition="normal",
        topology_path="topology.tpr",
        trajectory_paths=["trajectory.xtc"],
    )

    runtime_input = PreprocessingConditionRuntimeInput.from_manifest_condition(
        "normal",
        condition,
    )

    assert runtime_input.topology_path == Path("topology.tpr")
    assert runtime_input.trajectory_paths == (Path("trajectory.xtc"),)
    assert runtime_input.reference_structure_path is None


def test_runtime_wrapper_does_not_serialize_runtime_object() -> None:
    runtime_object = object()
    runtime = PreprocessingConditionRuntime(
        condition_name="normal",
        runtime_object=runtime_object,
        runtime_type="fake-runtime",
        topology_path=Path("topology.tpr"),
        trajectory_paths=(Path("trajectory.xtc"),),
    )

    payload = runtime.to_dict()

    assert runtime.runtime_object is runtime_object
    assert "runtime_object" not in payload
    assert repr(runtime_object) not in repr(payload)
    assert payload["has_runtime_object"] is True
    assert json.loads(json.dumps(payload)) == payload


def test_load_result_passed_semantics() -> None:
    runtime_input = make_runtime_input()
    runtime = make_runtime()
    issue = PreprocessingTrajectoryLoadIssue(
        kind="load_error",
        field="runtime",
        message="Expected fake failure",
    )

    not_loaded = PreprocessingConditionLoadResult(
        condition_name="normal",
        runtime_input=runtime_input,
    )
    failed = PreprocessingConditionLoadResult(
        condition_name="normal",
        runtime_input=runtime_input,
        issues=(issue,),
        status="failed",
    )
    loaded = PreprocessingConditionLoadResult(
        condition_name="normal",
        runtime_input=runtime_input,
        runtime=runtime,
        status="loaded",
    )
    loaded_with_issues = PreprocessingConditionLoadResult(
        condition_name="normal",
        runtime_input=runtime_input,
        runtime=runtime,
        issues=(issue,),
        status="loaded",
    )
    loaded_without_runtime = PreprocessingConditionLoadResult(
        condition_name="normal",
        runtime_input=runtime_input,
        status="loaded",
    )

    assert not_loaded.passed is False
    assert failed.passed is False
    assert loaded.passed is True
    assert loaded_with_issues.passed is False
    assert loaded_without_runtime.passed is False


def test_load_result_to_dict_is_json_serializable() -> None:
    runtime = make_runtime()
    issue = PreprocessingTrajectoryLoadIssue(
        kind="metadata_error",
        field="runtime.metadata",
        message="Metadata is not collected yet",
    )
    result = PreprocessingConditionLoadResult(
        condition_name="normal",
        runtime_input=make_runtime_input(),
        runtime=runtime,
        issues=(issue,),
        status="loaded",
    )

    payload = result.to_dict()

    assert json.loads(json.dumps(payload)) == payload
    assert payload["runtime_input"]["topology_path"] == "normal/topology.tpr"
    assert payload["issues"] == [issue.to_dict()]
    assert payload["runtime"] == runtime.to_dict()
    runtime_payload = payload["runtime"]
    assert isinstance(runtime_payload, dict)
    assert "runtime_object" not in runtime_payload
    assert repr(runtime.runtime_object) not in repr(payload)


def test_new_module_has_no_scientific_loading_calls() -> None:
    source_text = RUNTIME_MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "import MDAnalysis",
        "from MDAnalysis import",
        "MDAnalysis.Universe",
        "require_mdanalysis",
        "Universe(",
        ".exists(",
        ".is_file(",
        ".read_text(",
        ".open(",
    ):
        assert forbidden_text not in source_text


def test_runtime_source_has_no_direct_scientific_imports() -> None:
    forbidden_import_pattern = re.compile(
        r"^\s*(?:import|from)\s+"
        r"(?:MDAnalysis|numpy|pandas|networkx|pyarrow)"
        r"(?:\.|\s|$)"
    )

    for source_path in sorted(RUNTIME_SOURCE_DIR.rglob("*.py")):
        for line in source_path.read_text(encoding="utf-8").splitlines():
            assert forbidden_import_pattern.match(line) is None


def test_stage_11_1_public_api_remains_importable() -> None:
    assert get_mdanalysis_status is not None
    assert is_mdanalysis_available is not None
    assert require_mdanalysis is not None
