import json
import re
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRuntime,
    PreprocessingConditionRuntimeInput,
    PreprocessingInputManifest,
    PreprocessingManifestLoadIssue,
    PreprocessingManifestLoadResult,
    PreprocessingTrajectoryLoadIssue,
    load_manifest_condition_runtimes,
    load_single_condition_runtime,
    trajectory_manifest_loader,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
LOADER_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_manifest_loader.py"
)


def make_manifest() -> PreprocessingInputManifest:
    return PreprocessingInputManifest.model_validate(
        {
            "output_root": "output",
            "conditions": [
                {
                    "condition": "normal",
                    "topology_path": "normal/topology.tpr",
                    "trajectory_paths": ["normal/trajectory.xtc"],
                    "reference_structure_path": "normal/reference.pdb",
                },
                {
                    "condition": "tumor",
                    "topology_path": "tumor/topology.tpr",
                    "trajectory_paths": ["tumor/trajectory.xtc"],
                    "reference_structure_path": "tumor/reference.pdb",
                },
            ],
        }
    )


def make_loaded_result(
    runtime_input: PreprocessingConditionRuntimeInput,
) -> PreprocessingConditionLoadResult:
    runtime = PreprocessingConditionRuntime(
        condition_name=runtime_input.condition_name,
        runtime_object=object(),
        runtime_type="tests.FakeRuntime",
        topology_path=runtime_input.topology_path,
        trajectory_paths=runtime_input.trajectory_paths,
    )
    return PreprocessingConditionLoadResult(
        condition_name=runtime_input.condition_name,
        runtime_input=runtime_input,
        runtime=runtime,
        status="loaded",
    )


def make_failed_result(
    runtime_input: PreprocessingConditionRuntimeInput,
    *,
    kind: str = "load_error",
) -> PreprocessingConditionLoadResult:
    issue = PreprocessingTrajectoryLoadIssue(
        kind=kind,  # type: ignore[arg-type]
        field="condition_runtime",
        message="Expected condition failure.",
    )
    return PreprocessingConditionLoadResult(
        condition_name=runtime_input.condition_name,
        runtime_input=runtime_input,
        issues=(issue,),
        status="failed",
    )


def test_public_exports_and_existing_single_condition_api_work() -> None:
    assert mania.preprocessing is not None
    assert load_manifest_condition_runtimes is not None
    assert PreprocessingManifestLoadIssue is not None
    assert PreprocessingManifestLoadResult is not None
    assert load_single_condition_runtime is not None


def test_loads_all_conditions_in_manifest_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempted: list[PreprocessingConditionRuntimeInput] = []

    def fake_load(
        runtime_input: PreprocessingConditionRuntimeInput,
    ) -> PreprocessingConditionLoadResult:
        attempted.append(runtime_input)
        return make_loaded_result(runtime_input)

    monkeypatch.setattr(
        trajectory_manifest_loader,
        "load_single_condition_runtime",
        fake_load,
    )

    result = load_manifest_condition_runtimes(
        make_manifest(),
        base_dir=tmp_path,
    )

    assert [item.condition_name for item in attempted] == ["normal", "tumor"]
    assert result.passed is True
    assert result.loaded_condition_names == ("normal", "tumor")
    assert result.failed_condition_names == ()
    assert result.issues == ()
    assert [
        condition_result.condition_name
        for condition_result in result.condition_results
    ] == ["normal", "tumor"]


def test_relative_paths_resolve_against_explicit_base_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempted: list[PreprocessingConditionRuntimeInput] = []

    def fake_load(
        runtime_input: PreprocessingConditionRuntimeInput,
    ) -> PreprocessingConditionLoadResult:
        attempted.append(runtime_input)
        return make_loaded_result(runtime_input)

    monkeypatch.setattr(
        trajectory_manifest_loader,
        "load_single_condition_runtime",
        fake_load,
    )

    load_manifest_condition_runtimes(make_manifest(), base_dir=tmp_path)

    normal = attempted[0]
    assert normal.topology_path == tmp_path / "normal/topology.tpr"
    assert normal.trajectory_paths == (
        tmp_path / "normal/trajectory.xtc",
    )
    assert (
        normal.reference_structure_path
        == tmp_path / "normal/reference.pdb"
    )


def test_continues_after_normal_failed_condition_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted: list[str] = []

    def fake_load(
        runtime_input: PreprocessingConditionRuntimeInput,
    ) -> PreprocessingConditionLoadResult:
        attempted.append(runtime_input.condition_name)
        if runtime_input.condition_name == "normal":
            return make_failed_result(runtime_input)
        return make_loaded_result(runtime_input)

    monkeypatch.setattr(
        trajectory_manifest_loader,
        "load_single_condition_runtime",
        fake_load,
    )

    result = load_manifest_condition_runtimes(make_manifest())

    assert attempted == ["normal", "tumor"]
    assert result.passed is False
    assert result.failed_condition_names == ("normal",)
    assert result.loaded_condition_names == ("tumor",)
    assert result.issues == ()


def test_missing_dependency_stays_in_condition_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_load(
        runtime_input: PreprocessingConditionRuntimeInput,
    ) -> PreprocessingConditionLoadResult:
        return make_failed_result(
            runtime_input,
            kind="missing_optional_dependency",
        )

    monkeypatch.setattr(
        trajectory_manifest_loader,
        "load_single_condition_runtime",
        fake_load,
    )

    result = load_manifest_condition_runtimes(make_manifest())

    assert result.passed is False
    assert result.issues == ()
    assert result.failed_condition_names == ("normal", "tumor")
    assert all(
        condition_result.issues[0].kind == "missing_optional_dependency"
        for condition_result in result.condition_results
    )


def test_aggregate_to_dict_is_json_serializable_without_runtime_object() -> None:
    runtime_input = PreprocessingConditionRuntimeInput(
        condition_name="normal",
        topology_path=Path("normal/topology.tpr"),
        trajectory_paths=(Path("normal/trajectory.xtc"),),
    )
    loaded = make_loaded_result(runtime_input)
    failed_input = PreprocessingConditionRuntimeInput(
        condition_name="tumor",
        topology_path=Path("tumor/topology.tpr"),
        trajectory_paths=(Path("tumor/trajectory.xtc"),),
    )
    failed = make_failed_result(failed_input)
    result = PreprocessingManifestLoadResult(
        condition_results=(loaded, failed)
    )

    payload = result.to_dict()

    assert json.loads(json.dumps(payload)) == payload
    assert payload["passed"] is False
    assert payload["loaded_condition_names"] == ["normal"]
    assert payload["failed_condition_names"] == ["tumor"]
    loaded_payload = payload["condition_results"][0]
    assert isinstance(loaded_payload, dict)
    runtime_payload = loaded_payload["runtime"]
    assert isinstance(runtime_payload, dict)
    assert "runtime_object" not in runtime_payload
    assert loaded.runtime is not None
    assert repr(loaded.runtime.runtime_object) not in repr(payload)


def test_result_for_condition_uses_exact_condition_name() -> None:
    normal_input = PreprocessingConditionRuntimeInput(
        condition_name="normal",
        topology_path=Path("normal/topology.tpr"),
        trajectory_paths=(Path("normal/trajectory.xtc"),),
    )
    normal_result = make_loaded_result(normal_input)
    result = PreprocessingManifestLoadResult(
        condition_results=(normal_result,)
    )

    assert result.result_for_condition("normal") is normal_result
    assert result.result_for_condition("Normal") is None
    assert result.result_for_condition("missing") is None


def test_defensive_no_condition_result_is_serializable() -> None:
    issue = PreprocessingManifestLoadIssue(
        kind="no_conditions",
        condition_name=None,
        field="conditions",
        message="No manifest conditions are available to load.",
    )
    result = PreprocessingManifestLoadResult(
        condition_results=(),
        issues=(issue,),
    )

    assert result.passed is False
    assert result.loaded_condition_names == ()
    assert result.failed_condition_names == ()
    assert json.loads(json.dumps(result.to_dict())) == result.to_dict()


def test_no_condition_results_without_issues_do_not_pass() -> None:
    result = PreprocessingManifestLoadResult(condition_results=())

    assert result.passed is False


def test_conversion_error_becomes_manifest_issue_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = (
        PreprocessingConditionRuntimeInput.from_manifest_condition.__func__
    )
    attempted: list[str] = []

    def fake_from_manifest_condition(
        cls: type[PreprocessingConditionRuntimeInput],
        condition_name: str,
        condition: object,
        *,
        base_dir: str | Path | None = None,
    ) -> PreprocessingConditionRuntimeInput:
        if condition_name == "normal":
            raise ValueError("unexpected condition shape")
        return original(
            cls,
            condition_name,
            condition,  # type: ignore[arg-type]
            base_dir=base_dir,
        )

    def fake_load(
        runtime_input: PreprocessingConditionRuntimeInput,
    ) -> PreprocessingConditionLoadResult:
        attempted.append(runtime_input.condition_name)
        return make_loaded_result(runtime_input)

    monkeypatch.setattr(
        PreprocessingConditionRuntimeInput,
        "from_manifest_condition",
        classmethod(fake_from_manifest_condition),
    )
    monkeypatch.setattr(
        trajectory_manifest_loader,
        "load_single_condition_runtime",
        fake_load,
    )

    result = load_manifest_condition_runtimes(make_manifest())

    assert attempted == ["tumor"]
    assert result.passed is False
    assert result.loaded_condition_names == ("tumor",)
    assert len(result.issues) == 1
    assert result.issues[0].kind == "condition_input_error"
    assert result.issues[0].condition_name == "normal"
    assert "unexpected condition shape" not in result.issues[0].message


def test_unexpected_loader_error_becomes_manifest_issue_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted: list[str] = []

    def fake_load(
        runtime_input: PreprocessingConditionRuntimeInput,
    ) -> PreprocessingConditionLoadResult:
        attempted.append(runtime_input.condition_name)
        if runtime_input.condition_name == "normal":
            raise RuntimeError("unexpected loader details")
        return make_loaded_result(runtime_input)

    monkeypatch.setattr(
        trajectory_manifest_loader,
        "load_single_condition_runtime",
        fake_load,
    )

    result = load_manifest_condition_runtimes(make_manifest())

    assert attempted == ["normal", "tumor"]
    assert result.passed is False
    assert result.loaded_condition_names == ("tumor",)
    assert len(result.issues) == 1
    assert result.issues[0].kind == "condition_load_error"
    assert result.issues[0].condition_name == "normal"
    assert "unexpected loader details" not in result.issues[0].message


def test_loader_source_avoids_runtime_inspection_and_scientific_work() -> None:
    source_text = LOADER_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        ".atoms",
        ".residues",
        ".trajectory",
        "n_atoms",
        "n_residues",
        "n_frames",
        "metadata",
        "provenance",
        "residues.resnames",
        "run_residue_qc_from_manifest_options",
        "radius_of_gyration",
        "contacts",
        "select_atoms",
    ):
        assert forbidden_text not in source_text


def test_loader_has_no_direct_scientific_imports_or_require_call() -> None:
    source_lines = LOADER_PATH.read_text(encoding="utf-8").splitlines()
    forbidden_import_pattern = re.compile(
        r"^\s*(?:import|from)\s+"
        r"(?:MDAnalysis|numpy|pandas|networkx|pyarrow)"
        r"(?:\.|\s|$)"
    )

    assert not any(
        forbidden_import_pattern.match(line) for line in source_lines
    )
    assert "require_mdanalysis" not in "\n".join(source_lines)
