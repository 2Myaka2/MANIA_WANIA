import json
import math
import re
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRgResult,
    PreprocessingConditionRuntime,
    PreprocessingConditionRuntimeInput,
    PreprocessingManifestLoadIssue,
    PreprocessingManifestLoadResult,
    PreprocessingManifestRgResult,
    PreprocessingRgComputationIssue,
    PreprocessingRgFrameResult,
    PreprocessingTrajectoryLoadIssue,
    collect_condition_runtime_metadata,
    collect_manifest_runtime_metadata,
    extract_condition_residue_names,
    extract_manifest_residue_names,
    load_manifest_condition_runtimes,
    load_single_condition_runtime,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RG_MODULE_PATH = (
    REPO_ROOT / "src" / "mania" / "preprocessing" / "trajectory_rg.py"
)


def make_issue(
    *,
    condition_name: str | None = "normal",
    frame_index: int | None = 1,
) -> PreprocessingRgComputationIssue:
    return PreprocessingRgComputationIssue(
        kind="rg_computation_error",
        condition_name=condition_name,
        frame_index=frame_index,
        field="rg_value",
        message="Rg could not be computed.",
    )


def make_frame(
    condition_name: str = "normal",
    *,
    frame_index: int = 0,
    time_ps: float | None = 0.0,
    rg_value: float | None = 10.0,
    rg_unit: str | None = "angstrom",
    issues: tuple[PreprocessingRgComputationIssue, ...] = (),
) -> PreprocessingRgFrameResult:
    return PreprocessingRgFrameResult(
        condition_name=condition_name,
        frame_index=frame_index,
        time_ps=time_ps,
        rg_value=rg_value,
        rg_unit=rg_unit,
        issues=issues,
    )


def make_condition(
    condition_name: str = "normal",
    *,
    frame_results: tuple[PreprocessingRgFrameResult, ...] | None = None,
    issues: tuple[PreprocessingRgComputationIssue, ...] = (),
) -> PreprocessingConditionRgResult:
    if frame_results is None:
        frame_results = (
            make_frame(condition_name),
            make_frame(
                condition_name,
                frame_index=1,
                time_ps=10.0,
                rg_value=11.0,
            ),
        )
    return PreprocessingConditionRgResult(
        condition_name=condition_name,
        status="computed",
        runtime_type="tests.FakeRuntime",
        topology_path=Path(condition_name) / "topology.tpr",
        trajectory_paths=(Path(condition_name) / "trajectory.xtc",),
        frame_time_ps=10.0,
        rg_unit="angstrom",
        frame_results=frame_results,
        issues=issues,
    )


def test_public_exports_and_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None
    assert PreprocessingRgComputationIssue is not None
    assert PreprocessingRgFrameResult is not None
    assert PreprocessingConditionRgResult is not None
    assert PreprocessingManifestRgResult is not None


def test_issue_to_dict_is_json_serializable() -> None:
    issue = make_issue()

    payload = issue.to_dict()

    assert payload == {
        "kind": "rg_computation_error",
        "condition_name": "normal",
        "frame_index": 1,
        "field": "rg_value",
        "message": "Rg could not be computed.",
    }
    assert json.loads(json.dumps(payload)) == payload


def test_passed_frame_to_dict_is_json_serializable() -> None:
    frame = make_frame(frame_index=2, time_ps=20.0, rg_value=12.5)

    payload = frame.to_dict()

    assert payload["frame_index"] == 2
    assert payload["time_ps"] == 20.0
    assert payload["rg_value"] == 12.5
    assert payload["rg_unit"] == "angstrom"
    assert payload["passed"] is True
    assert json.loads(json.dumps(payload)) == payload


def test_frame_with_issue_is_failed_and_serializes_issue() -> None:
    issue = make_issue()
    frame = make_frame(rg_value=None, issues=(issue,))

    assert frame.passed is False
    assert frame.to_dict()["issues"] == [issue.to_dict()]


def test_frame_without_value_or_issue_is_failed() -> None:
    assert make_frame(rg_value=None).passed is False


@pytest.mark.parametrize("frame_index", [-1, True, False])
def test_invalid_frame_index_is_rejected(frame_index: object) -> None:
    with pytest.raises(ValueError, match="frame_index"):
        PreprocessingRgFrameResult(
            condition_name="normal",
            frame_index=frame_index,  # type: ignore[arg-type]
            time_ps=0.0,
            rg_value=10.0,
            rg_unit="angstrom",
        )


@pytest.mark.parametrize("time_ps", [-1.0, math.inf, math.nan])
def test_invalid_time_value_is_rejected(time_ps: float) -> None:
    with pytest.raises(ValueError, match="time_ps"):
        make_frame(time_ps=time_ps)


@pytest.mark.parametrize("rg_value", [-1.0, math.inf, math.nan])
def test_invalid_rg_value_is_rejected(rg_value: float) -> None:
    with pytest.raises(ValueError, match="rg_value"):
        make_frame(rg_value=rg_value)


def test_condition_result_aggregates_passed_frames() -> None:
    result = make_condition()

    assert result.passed is True
    assert result.frame_count == 2
    assert result.valid_frame_count == 2
    assert result.failed_frame_count == 0
    assert result.rg_values == (10.0, 11.0)
    assert result.time_values_ps == (0.0, 10.0)


def test_condition_result_fails_with_failed_frame() -> None:
    issue = make_issue(frame_index=1)
    result = make_condition(
        frame_results=(
            make_frame(),
            make_frame(
                frame_index=1,
                time_ps=10.0,
                rg_value=None,
                issues=(issue,),
            ),
        )
    )

    assert result.passed is False
    assert result.valid_frame_count == 1
    assert result.failed_frame_count == 1
    assert result.rg_values == (10.0,)
    assert result.time_values_ps == (0.0, 10.0)


def test_condition_result_fails_with_no_frames() -> None:
    assert make_condition(frame_results=()).passed is False


def test_condition_result_fails_with_condition_issue() -> None:
    assert make_condition(issues=(make_issue(frame_index=None),)).passed is False


def test_condition_rejects_mismatched_frame_condition_name() -> None:
    with pytest.raises(ValueError, match="condition_name"):
        make_condition(frame_results=(make_frame("tumor"),))


def test_condition_rejects_mismatched_frame_unit() -> None:
    with pytest.raises(ValueError, match="rg_unit"):
        make_condition(frame_results=(make_frame(rg_unit="nm"),))


@pytest.mark.parametrize("frame_time_ps", [-1.0, math.inf, math.nan])
def test_condition_rejects_invalid_frame_time(frame_time_ps: float) -> None:
    with pytest.raises(ValueError, match="frame_time_ps"):
        PreprocessingConditionRgResult(
            condition_name="normal",
            status="computed",
            runtime_type=None,
            topology_path=None,
            trajectory_paths=(),
            frame_time_ps=frame_time_ps,
            rg_unit=None,
        )


def test_condition_to_dict_serializes_paths_without_runtime_object() -> None:
    result = make_condition()

    payload = result.to_dict()

    assert payload["topology_path"] == "normal/topology.tpr"
    assert payload["trajectory_paths"] == ["normal/trajectory.xtc"]
    assert payload["passed"] is True
    assert payload["frame_count"] == 2
    assert "runtime_object" not in payload
    assert json.loads(json.dumps(payload)) == payload


def test_manifest_result_aggregates_conditions_in_order() -> None:
    normal = make_condition("normal")
    issue = make_issue(condition_name="tumor", frame_index=0)
    tumor = make_condition(
        "tumor",
        frame_results=(
            make_frame(
                "tumor",
                rg_value=None,
                issues=(issue,),
            ),
        ),
    )
    result = PreprocessingManifestRgResult(
        condition_results=(normal, tumor),
    )

    assert result.condition_names == ("normal", "tumor")
    assert result.passed_condition_names == ("normal",)
    assert result.failed_condition_names == ("tumor",)
    assert result.total_conditions == 2
    assert result.passed_conditions == 1
    assert result.failed_conditions == 1
    assert result.total_frames == 3
    assert result.valid_frames == 2
    assert result.failed_frames == 1


def test_manifest_result_lookup_and_serialization() -> None:
    normal = make_condition("normal")
    result = PreprocessingManifestRgResult(condition_results=(normal,))

    payload = result.to_dict()

    assert result.result_for_condition("normal") is normal
    assert result.result_for_condition("missing") is None
    assert json.loads(json.dumps(payload)) == payload


def test_manifest_result_fails_with_manifest_issue() -> None:
    issue = PreprocessingRgComputationIssue(
        kind="manifest_load_issue",
        condition_name=None,
        frame_index=None,
        field="conditions",
        message="Manifest loading failed.",
    )
    result = PreprocessingManifestRgResult(
        condition_results=(make_condition(),),
        issues=(issue,),
    )

    assert result.passed is False
    assert result.to_dict()["issues"] == [issue.to_dict()]


def test_empty_manifest_result_is_failed() -> None:
    assert PreprocessingManifestRgResult().passed is False


def test_contract_module_has_no_scientific_computation_or_runtime_calls() -> None:
    source_text = RG_MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "radius_of_gyration",
        "select_atoms",
        ".trajectory",
        ".positions",
        "for ts in",
        "contacts",
        "require_mdanalysis",
        "load_single_condition_runtime",
        "load_manifest_condition_runtimes",
        "collect_condition_runtime_metadata",
        "collect_manifest_runtime_metadata",
        "extract_condition_residue_names",
        "extract_manifest_residue_names",
    ):
        assert forbidden_text not in source_text


def test_contract_module_has_no_forbidden_scientific_imports() -> None:
    forbidden_import_pattern = re.compile(
        r"^\s*(?:import|from)\s+"
        r"(?:MDAnalysis|numpy|pandas|networkx|pyarrow)"
        r"(?:\.|\s|$)"
    )

    for line in RG_MODULE_PATH.read_text(encoding="utf-8").splitlines():
        assert forbidden_import_pattern.match(line) is None


def test_existing_stage_11_apis_remain_importable() -> None:
    stage_11_exports = (
        PreprocessingConditionLoadResult,
        PreprocessingConditionRuntime,
        PreprocessingConditionRuntimeInput,
        PreprocessingManifestLoadIssue,
        PreprocessingManifestLoadResult,
        PreprocessingTrajectoryLoadIssue,
        collect_condition_runtime_metadata,
        collect_manifest_runtime_metadata,
        extract_condition_residue_names,
        extract_manifest_residue_names,
        load_manifest_condition_runtimes,
        load_single_condition_runtime,
    )

    assert all(export is not None for export in stage_11_exports)
