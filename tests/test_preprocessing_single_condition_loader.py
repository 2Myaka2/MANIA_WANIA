import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRuntimeInput,
    PreprocessingOptionalDependencyError,
    load_single_condition_runtime,
    require_mdanalysis,
    trajectory_loader,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
LOADER_PATH = (
    REPO_ROOT / "src" / "mania" / "preprocessing" / "trajectory_loader.py"
)


def make_runtime_input(
    topology_path: Path,
    trajectory_paths: tuple[Path, ...],
) -> PreprocessingConditionRuntimeInput:
    return PreprocessingConditionRuntimeInput(
        condition_name="normal",
        topology_path=topology_path,
        trajectory_paths=trajectory_paths,
    )


def fail_if_dependency_required() -> None:
    raise AssertionError("require_mdanalysis should not be called")


def test_public_export_and_existing_runtime_apis_work() -> None:
    assert mania.preprocessing is not None
    assert load_single_condition_runtime is not None
    assert require_mdanalysis is not None
    assert PreprocessingConditionRuntimeInput is not None
    assert PreprocessingConditionLoadResult is not None


def test_missing_topology_fails_before_dependency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    trajectory_path = tmp_path / "trajectory.xtc"
    trajectory_path.touch()
    monkeypatch.setattr(
        trajectory_loader,
        "require_mdanalysis",
        fail_if_dependency_required,
    )

    result = load_single_condition_runtime(
        make_runtime_input(tmp_path / "missing.tpr", (trajectory_path,))
    )

    assert result.status == "failed"
    assert result.passed is False
    assert [issue.kind for issue in result.issues] == [
        "missing_topology_path"
    ]
    assert result.runtime is None


def test_topology_directory_fails_before_dependency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    topology_path = tmp_path / "topology"
    topology_path.mkdir()
    trajectory_path = tmp_path / "trajectory.xtc"
    trajectory_path.touch()
    monkeypatch.setattr(
        trajectory_loader,
        "require_mdanalysis",
        fail_if_dependency_required,
    )

    result = load_single_condition_runtime(
        make_runtime_input(topology_path, (trajectory_path,))
    )

    assert [issue.kind for issue in result.issues] == ["topology_not_file"]


def test_empty_trajectory_paths_fail_before_dependency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    topology_path = tmp_path / "topology.tpr"
    topology_path.touch()
    monkeypatch.setattr(
        trajectory_loader,
        "require_mdanalysis",
        fail_if_dependency_required,
    )

    result = load_single_condition_runtime(
        make_runtime_input(topology_path, ())
    )

    assert [issue.kind for issue in result.issues] == [
        "missing_trajectory_path"
    ]
    assert result.issues[0].field == "trajectory_paths"
    assert result.issues[0].path is None


def test_missing_trajectory_fails_before_dependency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    topology_path = tmp_path / "topology.tpr"
    topology_path.touch()
    missing_path = tmp_path / "missing.xtc"
    monkeypatch.setattr(
        trajectory_loader,
        "require_mdanalysis",
        fail_if_dependency_required,
    )

    result = load_single_condition_runtime(
        make_runtime_input(topology_path, (missing_path,))
    )

    assert [issue.kind for issue in result.issues] == [
        "missing_trajectory_path"
    ]
    assert result.issues[0].field == "trajectory_paths[0]"
    assert result.issues[0].path == missing_path


def test_trajectory_directory_fails_before_dependency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    topology_path = tmp_path / "topology.tpr"
    topology_path.touch()
    trajectory_path = tmp_path / "trajectory"
    trajectory_path.mkdir()
    monkeypatch.setattr(
        trajectory_loader,
        "require_mdanalysis",
        fail_if_dependency_required,
    )

    result = load_single_condition_runtime(
        make_runtime_input(topology_path, (trajectory_path,))
    )

    assert [issue.kind for issue in result.issues] == [
        "trajectory_not_file"
    ]


def test_multiple_path_issues_are_collected_before_dependency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    trajectory_directory = tmp_path / "trajectory"
    trajectory_directory.mkdir()
    monkeypatch.setattr(
        trajectory_loader,
        "require_mdanalysis",
        fail_if_dependency_required,
    )

    result = load_single_condition_runtime(
        make_runtime_input(
            tmp_path / "missing.tpr",
            (tmp_path / "missing.xtc", trajectory_directory),
        )
    )

    assert [(issue.kind, issue.field) for issue in result.issues] == [
        ("missing_topology_path", "topology_path"),
        ("missing_trajectory_path", "trajectory_paths[0]"),
        ("trajectory_not_file", "trajectory_paths[1]"),
    ]


def test_missing_dependency_becomes_failed_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    topology_path = tmp_path / "topology.tpr"
    topology_path.touch()
    trajectory_path = tmp_path / "trajectory.xtc"
    trajectory_path.touch()

    def raise_missing_dependency() -> None:
        raise PreprocessingOptionalDependencyError(
            'MDAnalysis is unavailable. Install with ".[md]".'
        )

    monkeypatch.setattr(
        trajectory_loader,
        "require_mdanalysis",
        raise_missing_dependency,
    )

    result = load_single_condition_runtime(
        make_runtime_input(topology_path, (trajectory_path,))
    )

    assert result.status == "failed"
    assert result.passed is False
    assert len(result.issues) == 1
    assert result.issues[0].kind == "missing_optional_dependency"
    assert result.issues[0].field == "MDAnalysis"
    assert ".[md]" in result.issues[0].message
    assert result.runtime is None


def test_fake_universe_success_returns_loaded_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    topology_path = tmp_path / "topology.tpr"
    topology_path.touch()
    trajectory_path = tmp_path / "trajectory.xtc"
    trajectory_path.touch()
    calls: list[tuple[str, ...]] = []

    class FakeUniverse:
        def __init__(self, *paths: str) -> None:
            calls.append(paths)

        @property
        def atoms(self) -> object:
            raise AssertionError("atoms must not be accessed")

        @property
        def residues(self) -> object:
            raise AssertionError("residues must not be accessed")

        @property
        def trajectory(self) -> object:
            raise AssertionError("trajectory must not be accessed")

        @property
        def dimensions(self) -> object:
            raise AssertionError("dimensions must not be accessed")

        @property
        def frames(self) -> object:
            raise AssertionError("frames must not be accessed")

    monkeypatch.setattr(
        trajectory_loader,
        "require_mdanalysis",
        lambda: SimpleNamespace(Universe=FakeUniverse),
    )

    result = load_single_condition_runtime(
        make_runtime_input(topology_path, (trajectory_path,))
    )

    assert calls == [(str(topology_path), str(trajectory_path))]
    assert result.status == "loaded"
    assert result.passed is True
    assert result.runtime is not None
    assert isinstance(result.runtime.runtime_object, FakeUniverse)
    assert result.runtime.runtime_type == (
        f"{FakeUniverse.__module__}.{FakeUniverse.__qualname__}"
    )
    payload = result.to_dict()
    assert json.loads(json.dumps(payload)) == payload
    assert "runtime_object" not in payload["runtime"]


def test_multiple_trajectories_are_passed_to_universe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    topology_path = tmp_path / "topology.tpr"
    topology_path.touch()
    trajectory_paths = (
        tmp_path / "trajectory-1.xtc",
        tmp_path / "trajectory-2.xtc",
    )
    for path in trajectory_paths:
        path.touch()
    calls: list[tuple[str, ...]] = []

    def fake_universe(*paths: str) -> object:
        calls.append(paths)
        return object()

    monkeypatch.setattr(
        trajectory_loader,
        "require_mdanalysis",
        lambda: SimpleNamespace(Universe=fake_universe),
    )

    result = load_single_condition_runtime(
        make_runtime_input(topology_path, trajectory_paths)
    )

    assert result.passed is True
    assert calls == [
        (
            str(topology_path),
            str(trajectory_paths[0]),
            str(trajectory_paths[1]),
        )
    ]


def test_universe_error_becomes_load_issue(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    topology_path = tmp_path / "topology.tpr"
    topology_path.touch()
    trajectory_path = tmp_path / "trajectory.xtc"
    trajectory_path.touch()

    def raise_load_error(*_: str) -> object:
        raise ValueError("parser details must not appear")

    monkeypatch.setattr(
        trajectory_loader,
        "require_mdanalysis",
        lambda: SimpleNamespace(Universe=raise_load_error),
    )

    result = load_single_condition_runtime(
        make_runtime_input(topology_path, (trajectory_path,))
    )

    assert result.status == "failed"
    assert result.passed is False
    assert result.runtime is None
    assert len(result.issues) == 1
    assert result.issues[0].kind == "load_error"
    assert result.issues[0].field == "MDAnalysis.Universe"
    assert result.issues[0].path == topology_path
    assert "parser details" not in result.issues[0].message
    assert "Traceback" not in result.issues[0].message


def test_loader_source_has_no_scientific_computation_calls() -> None:
    source_text = LOADER_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "radius_of_gyration",
        "contacts",
        "residues.resnames",
        "run_residue_qc_from_manifest_options",
        "select_atoms",
    ):
        assert forbidden_text not in source_text


def test_loader_has_no_direct_scientific_imports() -> None:
    forbidden_import_pattern = re.compile(
        r"^\s*(?:import|from)\s+"
        r"(?:MDAnalysis|numpy|pandas|networkx|pyarrow)"
        r"(?:\.|\s|$)"
    )

    for line in LOADER_PATH.read_text(encoding="utf-8").splitlines():
        assert forbidden_import_pattern.match(line) is None
