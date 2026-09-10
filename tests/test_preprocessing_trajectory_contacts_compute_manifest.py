import json
import re
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionContactsResult,
    PreprocessingConditionLoadResult,
    PreprocessingConditionRuntime,
    PreprocessingConditionRuntimeInput,
    PreprocessingContactComputationIssue,
    PreprocessingContactComputationLimits,
    PreprocessingContactDetectionOptions,
    PreprocessingContactFrameResult,
    PreprocessingContactProgressEvent,
    PreprocessingManifestContactsResult,
    PreprocessingManifestLoadIssue,
    PreprocessingManifestLoadResult,
    PreprocessingTrajectoryLoadIssue,
    compute_manifest_contacts,
    trajectory_contacts,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTACTS_MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_contacts.py"
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
        runtime_object=object() if runtime_object is None else runtime_object,
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


def make_contacts_result(
    condition_name: str,
    *,
    passed: bool = True,
    frame_count: int = 1,
    options: PreprocessingContactDetectionOptions | None = None,
) -> PreprocessingConditionContactsResult:
    selected_options = options or PreprocessingContactDetectionOptions()
    frames: list[PreprocessingContactFrameResult] = []
    for frame_index in range(frame_count):
        issues: tuple[PreprocessingContactComputationIssue, ...] = ()
        if not passed and frame_index == 0:
            issues = (
                PreprocessingContactComputationIssue(
                    kind="contact_computation_error",
                    field=f"frames[{frame_index}]",
                    message="Expected frame failure.",
                ),
            )
        frames.append(
            PreprocessingContactFrameResult(
                condition_name=condition_name,
                frame_index=frame_index,
                time_ps=float(frame_index),
                contacts=(),
                issues=issues,
            )
        )
    return PreprocessingConditionContactsResult(
        condition_name=condition_name,
        options=selected_options,
        frame_results=tuple(frames),
        status="computed" if passed else "partial",
    )


def condition_names(
    result: PreprocessingManifestContactsResult,
) -> tuple[str, ...]:
    return tuple(
        condition_result.condition_name
        for condition_result in result.condition_results
    )


def test_public_export_and_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None
    assert compute_manifest_contacts is not None


def test_manifest_composes_condition_results_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    normal = make_load_result("normal")
    tumor = make_load_result("tumor")
    calls: list[tuple[str, PreprocessingContactDetectionOptions]] = []

    def fake_compute(
        condition_result: PreprocessingConditionLoadResult,
        *,
        options: PreprocessingContactDetectionOptions | None = None,
    ) -> PreprocessingConditionContactsResult:
        selected_options = options or PreprocessingContactDetectionOptions()
        calls.append((condition_result.condition_name, selected_options))
        return make_contacts_result(
            condition_result.condition_name,
            options=selected_options,
        )

    monkeypatch.setattr(
        trajectory_contacts,
        "compute_condition_contacts",
        fake_compute,
    )

    result = compute_manifest_contacts(
        PreprocessingManifestLoadResult(
            condition_results=(normal, tumor),
        )
    )

    assert [condition_name for condition_name, _ in calls] == [
        "normal",
        "tumor",
    ]
    assert all(
        call_options == PreprocessingContactDetectionOptions()
        for _, call_options in calls
    )
    assert isinstance(result, PreprocessingManifestContactsResult)
    assert condition_names(result) == ("normal", "tumor")
    assert result.condition_count == 2
    assert result.passed is True


def test_custom_options_are_passed_to_every_condition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    custom_options = PreprocessingContactDetectionOptions(
        cutoff_distance=6.0,
        atom_filter="all",
        skip_resnames=("HOH",),
    )
    calls: list[PreprocessingContactDetectionOptions | None] = []

    def fake_compute(
        condition_result: PreprocessingConditionLoadResult,
        *,
        options: PreprocessingContactDetectionOptions | None = None,
    ) -> PreprocessingConditionContactsResult:
        calls.append(options)
        return make_contacts_result(
            condition_result.condition_name,
            options=options,
        )

    monkeypatch.setattr(
        trajectory_contacts,
        "compute_condition_contacts",
        fake_compute,
    )
    manifest = PreprocessingManifestLoadResult(
        condition_results=(
            make_load_result("normal"),
            make_load_result("tumor"),
        ),
    )

    result = compute_manifest_contacts(manifest, options=custom_options)

    assert calls == [custom_options, custom_options]
    assert all(
        condition_result.options == custom_options
        for condition_result in result.condition_results
    )


def test_limits_and_progress_callback_are_passed_to_every_condition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limits = PreprocessingContactComputationLimits(
        max_residue_pairs_per_frame=5
    )
    events: list[PreprocessingContactProgressEvent] = []
    calls: list[
        tuple[
            PreprocessingContactComputationLimits | None,
            object | None,
        ]
    ] = []

    def fake_compute(
        condition_result: PreprocessingConditionLoadResult,
        *,
        options: PreprocessingContactDetectionOptions | None = None,
        computation_limits: PreprocessingContactComputationLimits | None = None,
        progress_callback: object | None = None,
    ) -> PreprocessingConditionContactsResult:
        calls.append((computation_limits, progress_callback))
        if callable(progress_callback):
            progress_callback(
                PreprocessingContactProgressEvent(
                    condition_name=condition_result.condition_name,
                    frame_index=None,
                    stage="condition_start",
                    message="starting contacts computation",
                )
            )
        return make_contacts_result(
            condition_result.condition_name,
            options=options,
        )

    monkeypatch.setattr(
        trajectory_contacts,
        "compute_condition_contacts",
        fake_compute,
    )
    manifest = PreprocessingManifestLoadResult(
        condition_results=(
            make_load_result("normal"),
            make_load_result("tumor"),
        ),
    )

    result = compute_manifest_contacts(
        manifest,
        computation_limits=limits,
        progress_callback=events.append,
    )

    assert calls == [(limits, events.append), (limits, events.append)]
    assert [event.condition_name for event in events] == ["normal", "tumor"]
    assert result.to_dict()["contact_computation_limits"] == limits.to_dict()


def test_partial_condition_does_not_stop_aggregation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_compute(
        condition_result: PreprocessingConditionLoadResult,
        *,
        options: PreprocessingContactDetectionOptions | None = None,
    ) -> PreprocessingConditionContactsResult:
        return make_contacts_result(
            condition_result.condition_name,
            passed=condition_result.condition_name != "normal",
            options=options,
        )

    monkeypatch.setattr(
        trajectory_contacts,
        "compute_condition_contacts",
        fake_compute,
    )
    manifest = PreprocessingManifestLoadResult(
        condition_results=(
            make_load_result("normal"),
            make_load_result("tumor"),
        ),
    )

    result = compute_manifest_contacts(manifest)

    assert condition_names(result) == ("normal", "tumor")
    assert result.passed is False
    assert result.failed_condition_count == 1
    assert result.condition_results[0].status == "partial"
    assert result.condition_results[1].status == "computed"


def test_failed_load_is_delegated_without_manifest_issue_duplication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failed = make_failed_load_result("normal")
    calls: list[str] = []

    def fake_compute(
        condition_result: PreprocessingConditionLoadResult,
        *,
        options: PreprocessingContactDetectionOptions | None = None,
    ) -> PreprocessingConditionContactsResult:
        calls.append(condition_result.condition_name)
        return make_contacts_result(
            condition_result.condition_name,
            passed=False,
            options=options,
        )

    monkeypatch.setattr(
        trajectory_contacts,
        "compute_condition_contacts",
        fake_compute,
    )

    result = compute_manifest_contacts(
        PreprocessingManifestLoadResult(condition_results=(failed,))
    )

    assert calls == ["normal"]
    assert result.failed_condition_count == 1
    assert result.issues == ()


def test_manifest_load_issues_become_contacts_manifest_issues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        trajectory_contacts,
        "compute_condition_contacts",
        lambda condition_result, *, options=None: make_contacts_result(
            condition_result.condition_name,
            options=options,
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

    result = compute_manifest_contacts(manifest)

    assert result.passed is False
    assert len(result.issues) == 1
    assert result.issues[0].kind == "manifest_load_issue"
    assert result.issues[0].field == "conditions[tumor].condition_runtime"
    assert result.issues[0].message == source_issue.message


def test_manifest_level_issue_without_condition_preserves_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        trajectory_contacts,
        "compute_condition_contacts",
        lambda condition_result, *, options=None: make_contacts_result(
            condition_result.condition_name,
            options=options,
        ),
    )
    source_issue = PreprocessingManifestLoadIssue(
        kind="no_conditions",
        condition_name=None,
        field="conditions",
        message="No manifest conditions are available to load.",
    )

    result = compute_manifest_contacts(
        PreprocessingManifestLoadResult((), issues=(source_issue,))
    )

    assert result.condition_results == ()
    assert len(result.issues) == 1
    assert result.issues[0].field == "conditions"


def test_unexpected_condition_error_becomes_failed_result_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted: list[str] = []

    def fake_compute(
        condition_result: PreprocessingConditionLoadResult,
        *,
        options: PreprocessingContactDetectionOptions | None = None,
    ) -> PreprocessingConditionContactsResult:
        attempted.append(condition_result.condition_name)
        if condition_result.condition_name == "normal":
            raise RuntimeError("private condition details")
        return make_contacts_result(
            condition_result.condition_name,
            options=options,
        )

    monkeypatch.setattr(
        trajectory_contacts,
        "compute_condition_contacts",
        fake_compute,
    )
    manifest = PreprocessingManifestLoadResult(
        condition_results=(
            make_load_result("normal"),
            make_load_result("tumor"),
        ),
    )

    result = compute_manifest_contacts(manifest)

    assert attempted == ["normal", "tumor"]
    assert condition_names(result) == ("normal", "tumor")
    assert result.passed is False
    failed = result.condition_results[0]
    assert failed.status == "failed"
    assert [issue.kind for issue in failed.issues] == [
        "condition_contacts_error"
    ]
    assert failed.issues[0].field == "compute_condition_contacts"
    assert "private condition details" not in failed.issues[0].message
    assert result.issues == ()


def test_empty_manifest_is_failed_and_serializable() -> None:
    result = compute_manifest_contacts(
        PreprocessingManifestLoadResult(condition_results=())
    )

    assert result.passed is False
    assert result.condition_results == ()
    assert json.loads(json.dumps(result.to_dict())) == result.to_dict()


def test_manifest_serialization_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    normal_contacts = make_contacts_result("normal", frame_count=2)
    tumor_contacts = make_contacts_result(
        "tumor",
        passed=False,
        frame_count=3,
    )
    results = {"normal": normal_contacts, "tumor": tumor_contacts}

    monkeypatch.setattr(
        trajectory_contacts,
        "compute_condition_contacts",
        lambda condition_result, *, options=None: results[
            condition_result.condition_name
        ],
    )
    manifest = PreprocessingManifestLoadResult(
        condition_results=(
            make_load_result("normal"),
            make_load_result("tumor"),
        ),
    )

    result = compute_manifest_contacts(manifest)
    payload = result.to_dict()

    assert result.condition_count == 2
    assert result.computed_condition_count == 1
    assert result.failed_condition_count == 1
    assert result.frame_count == 5
    assert result.passed_frame_count == 4
    assert result.failed_frame_count == 1
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
        trajectory_contacts,
        "compute_condition_contacts",
        lambda condition_result, *, options=None: make_contacts_result(
            condition_result.condition_name,
            options=options,
        ),
    )

    result = compute_manifest_contacts(
        PreprocessingManifestLoadResult(condition_results=(condition,))
    )

    assert result.passed is True


def test_source_stays_within_manifest_contacts_scope() -> None:
    source_text = CONTACTS_MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "load_single_condition_runtime",
        "load_manifest_condition_runtimes",
        "require_mdanalysis",
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
        assert forbidden_text not in source_text
    assert source_text.count("def _minimum_distance") == 1


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


def test_explicit_mapping_routes_only_known_conditions_without_mutation():
    from test_preprocessing_pbc_observation_integration import SAMPLING, loading

    source, _ = loading()
    mapping = {"normal": (0, 4, 7)}
    result = compute_manifest_contacts(
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
        compute_manifest_contacts(
            source.runtime_load_result,
            source_frame_indexes_by_condition={"missing": (0,)},
        )
