import json
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
    compute_manifest_rg,
    trajectory_rg,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RG_MODULE_PATH = (
    REPO_ROOT / "src" / "mania" / "preprocessing" / "trajectory_rg.py"
)


def make_runtime_input(
    condition_name: str,
    *,
    frame_time_ps: float | None = 2.5,
) -> PreprocessingConditionRuntimeInput:
    return PreprocessingConditionRuntimeInput(
        condition_name=condition_name,
        topology_path=Path(condition_name) / "topology.tpr",
        trajectory_paths=(Path(condition_name) / "trajectory.xtc",),
        frame_time_ps=frame_time_ps,
    )


def make_load_result(
    condition_name: str,
    *,
    runtime_object: object | None = None,
) -> PreprocessingConditionLoadResult:
    runtime_input = make_runtime_input(condition_name)
    runtime = PreprocessingConditionRuntime(
        condition_name=condition_name,
        runtime_object=(
            object() if runtime_object is None else runtime_object
        ),
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


def make_failed_load_result(
    condition_name: str,
) -> PreprocessingConditionLoadResult:
    return PreprocessingConditionLoadResult(
        condition_name=condition_name,
        runtime_input=make_runtime_input(condition_name),
        issues=(
            PreprocessingTrajectoryLoadIssue(
                kind="load_error",
                field="condition_runtime",
                message="Expected condition load failure.",
            ),
        ),
        status="failed",
    )


def make_rg_result(
    condition_name: str,
    *,
    passed: bool = True,
    frame_count: int = 1,
    rg_unit: str = "angstrom",
) -> PreprocessingConditionRgResult:
    frames: list[PreprocessingRgFrameResult] = []
    for frame_index in range(frame_count):
        issues: tuple[PreprocessingRgComputationIssue, ...] = ()
        rg_value: float | None = 10.0 + frame_index
        if not passed and frame_index == 0:
            issue = PreprocessingRgComputationIssue(
                kind="rg_computation_error",
                condition_name=condition_name,
                frame_index=frame_index,
                field="rg_value",
                message="Expected frame failure.",
            )
            issues = (issue,)
            rg_value = None
        frames.append(
            PreprocessingRgFrameResult(
                condition_name=condition_name,
                frame_index=frame_index,
                time_ps=float(frame_index),
                rg_value=rg_value,
                rg_unit=rg_unit,
                issues=issues,
            )
        )
    return PreprocessingConditionRgResult(
        condition_name=condition_name,
        status="computed" if passed else "partial",
        runtime_type="tests.FakeRuntime",
        topology_path=Path(condition_name) / "topology.tpr",
        trajectory_paths=(Path(condition_name) / "trajectory.xtc",),
        frame_time_ps=1.0,
        rg_unit=rg_unit,
        frame_results=tuple(frames),
    )


def test_public_export_and_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None
    assert compute_manifest_rg is not None


def test_manifest_composes_condition_results_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    normal = make_load_result("normal")
    tumor = make_load_result("tumor")
    calls: list[tuple[str, str]] = []

    def fake_compute(
        condition_result: PreprocessingConditionLoadResult,
        *,
        rg_unit: str = "angstrom",
    ) -> PreprocessingConditionRgResult:
        calls.append((condition_result.condition_name, rg_unit))
        return make_rg_result(
            condition_result.condition_name,
            rg_unit=rg_unit,
        )

    monkeypatch.setattr(trajectory_rg, "compute_condition_rg", fake_compute)

    result = compute_manifest_rg(
        PreprocessingManifestLoadResult(
            condition_results=(normal, tumor),
        )
    )

    assert calls == [("normal", "angstrom"), ("tumor", "angstrom")]
    assert isinstance(result, PreprocessingManifestRgResult)
    assert result.condition_names == ("normal", "tumor")
    assert result.total_conditions == 2


def test_custom_unit_is_passed_to_every_condition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_compute(
        condition_result: PreprocessingConditionLoadResult,
        *,
        rg_unit: str = "angstrom",
    ) -> PreprocessingConditionRgResult:
        calls.append(rg_unit)
        return make_rg_result(
            condition_result.condition_name,
            rg_unit=rg_unit,
        )

    monkeypatch.setattr(trajectory_rg, "compute_condition_rg", fake_compute)
    manifest = PreprocessingManifestLoadResult(
        condition_results=(
            make_load_result("normal"),
            make_load_result("tumor"),
        ),
    )

    result = compute_manifest_rg(manifest, rg_unit="test_unit")

    assert calls == ["test_unit", "test_unit"]
    assert all(
        condition.rg_unit == "test_unit"
        for condition in result.condition_results
    )


def test_partial_condition_does_not_stop_aggregation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_compute(
        condition_result: PreprocessingConditionLoadResult,
        *,
        rg_unit: str = "angstrom",
    ) -> PreprocessingConditionRgResult:
        return make_rg_result(
            condition_result.condition_name,
            passed=condition_result.condition_name != "normal",
            rg_unit=rg_unit,
        )

    monkeypatch.setattr(trajectory_rg, "compute_condition_rg", fake_compute)
    manifest = PreprocessingManifestLoadResult(
        condition_results=(
            make_load_result("normal"),
            make_load_result("tumor"),
        ),
    )

    result = compute_manifest_rg(manifest)

    assert result.condition_names == ("normal", "tumor")
    assert result.passed is False
    assert result.passed_condition_names == ("tumor",)
    assert result.failed_condition_names == ("normal",)


def test_failed_load_is_delegated_without_manifest_issue_duplication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failed = make_failed_load_result("normal")
    calls: list[str] = []

    def fake_compute(
        condition_result: PreprocessingConditionLoadResult,
        *,
        rg_unit: str = "angstrom",
    ) -> PreprocessingConditionRgResult:
        calls.append(condition_result.condition_name)
        return make_rg_result(
            condition_result.condition_name,
            passed=False,
            rg_unit=rg_unit,
        )

    monkeypatch.setattr(trajectory_rg, "compute_condition_rg", fake_compute)

    result = compute_manifest_rg(
        PreprocessingManifestLoadResult(condition_results=(failed,))
    )

    assert calls == ["normal"]
    assert result.failed_condition_names == ("normal",)
    assert result.issues == ()


def test_manifest_load_issues_become_rg_manifest_issues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        trajectory_rg,
        "compute_condition_rg",
        lambda result, *, rg_unit="angstrom": make_rg_result(
            result.condition_name,
            rg_unit=rg_unit,
        ),
    )
    source_issue = PreprocessingManifestLoadIssue(
        kind="condition_load_error",
        condition_name="tumor",
        field="condition_runtime",
        message="The condition loader raised an unexpected error.",
    )
    manifest = PreprocessingManifestLoadResult(
        condition_results=(make_load_result("normal"),),
        issues=(source_issue,),
    )

    result = compute_manifest_rg(manifest)

    assert result.passed is False
    assert len(result.issues) == 1
    assert result.issues[0].kind == "manifest_load_issue"
    assert result.issues[0].condition_name == "tumor"
    assert result.issues[0].field == source_issue.field
    assert result.issues[0].message == source_issue.message


def test_unexpected_condition_error_becomes_failed_result_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted: list[str] = []

    def fake_compute(
        condition_result: PreprocessingConditionLoadResult,
        *,
        rg_unit: str = "angstrom",
    ) -> PreprocessingConditionRgResult:
        attempted.append(condition_result.condition_name)
        if condition_result.condition_name == "normal":
            raise RuntimeError("private condition details")
        return make_rg_result(
            condition_result.condition_name,
            rg_unit=rg_unit,
        )

    monkeypatch.setattr(trajectory_rg, "compute_condition_rg", fake_compute)
    manifest = PreprocessingManifestLoadResult(
        condition_results=(
            make_load_result("normal"),
            make_load_result("tumor"),
        ),
    )

    result = compute_manifest_rg(manifest)

    assert attempted == ["normal", "tumor"]
    assert result.condition_names == ("normal", "tumor")
    assert result.passed is False
    failed = result.result_for_condition("normal")
    assert failed is not None
    assert failed.status == "failed"
    assert [issue.kind for issue in failed.issues] == [
        "condition_rg_error"
    ]
    assert failed.issues[0].field == "compute_condition_rg"
    assert "private condition details" not in failed.issues[0].message
    assert result.issues == ()


def test_empty_manifest_is_failed_and_serializable() -> None:
    result = compute_manifest_rg(
        PreprocessingManifestLoadResult(condition_results=())
    )

    assert result.passed is False
    assert result.condition_results == ()
    assert json.loads(json.dumps(result.to_dict())) == result.to_dict()


def test_manifest_serialization_counts_and_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    normal_rg = make_rg_result("normal", frame_count=2)
    tumor_rg = make_rg_result("tumor", passed=False, frame_count=3)
    results = {"normal": normal_rg, "tumor": tumor_rg}

    monkeypatch.setattr(
        trajectory_rg,
        "compute_condition_rg",
        lambda result, *, rg_unit="angstrom": results[
            result.condition_name
        ],
    )
    manifest = PreprocessingManifestLoadResult(
        condition_results=(
            make_load_result("normal"),
            make_load_result("tumor"),
        ),
    )

    result = compute_manifest_rg(manifest)
    payload = result.to_dict()

    assert result.total_conditions == 2
    assert result.passed_conditions == 1
    assert result.failed_conditions == 1
    assert result.total_frames == 5
    assert result.valid_frames == 4
    assert result.failed_frames == 1
    assert result.result_for_condition("normal") is normal_rg
    assert result.result_for_condition("missing") is None
    assert "runtime_object" not in repr(payload)
    assert json.loads(json.dumps(payload)) == payload


def test_manifest_function_does_not_inspect_runtime_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ExplodingRuntimeObject:
        def __getattribute__(self, name: str) -> object:
            if name.startswith("__"):
                return object.__getattribute__(self, name)
            raise AssertionError("manifest layer must not inspect runtime")

    condition = make_load_result(
        "normal",
        runtime_object=ExplodingRuntimeObject(),
    )
    monkeypatch.setattr(
        trajectory_rg,
        "compute_condition_rg",
        lambda result, *, rg_unit="angstrom": make_rg_result(
            result.condition_name,
            rg_unit=rg_unit,
        ),
    )

    result = compute_manifest_rg(
        PreprocessingManifestLoadResult(condition_results=(condition,))
    )

    assert result.passed is True


def test_source_stays_within_manifest_rg_scope() -> None:
    source_text = RG_MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "require_mdanalysis",
        "load_single_condition_runtime",
        "load_manifest_condition_runtimes",
        "collect_condition_runtime_metadata",
        "collect_manifest_runtime_metadata",
        "extract_condition_residue_names",
        "extract_manifest_residue_names",
        "run_residue_qc_from_manifest_options",
        "rg_timeseries",
        "comparison",
        "tolerance",
        "contacts",
        "graph",
        "edges",
        "nodes",
        "select_atoms",
        ".positions",
        ".coordinates",
    ):
        assert forbidden_text not in source_text


def test_source_has_no_forbidden_scientific_imports() -> None:
    forbidden_import_pattern = re.compile(
        r"^\s*(?:import|from)\s+"
        r"(?:MDAnalysis|numpy|pandas|networkx|pyarrow)"
        r"(?:\.|\s|$)"
    )

    for line in RG_MODULE_PATH.read_text(encoding="utf-8").splitlines():
        assert forbidden_import_pattern.match(line) is None


def test_explicit_mapping_routes_only_known_conditions_without_mutation():
    from test_preprocessing_pbc_observation_integration import SAMPLING, loading

    source, _ = loading()
    mapping = {"normal": (0, 4, 7)}
    result = compute_manifest_rg(
        source.runtime_load_result,
        frame_sampling=SAMPLING,
        source_frame_indexes_by_condition=mapping,
    )
    assert result.passed
    assert [r.condition_name for r in result.condition_results] == ["normal", "tumor"]
    assert [f.frame_index for f in result.condition_results[0].frame_results] == [
        0,
        4,
        7,
    ]
    assert [f.frame_index for f in result.condition_results[1].frame_results] == [
        1,
        3,
        5,
    ]
    assert mapping == {"normal": (0, 4, 7)}
    with pytest.raises(ValueError, match="unknown conditions"):
        compute_manifest_rg(
            source.runtime_load_result,
            source_frame_indexes_by_condition={"missing": (0,)},
        )
