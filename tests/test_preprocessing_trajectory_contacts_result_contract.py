import json
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionContactsResult,
    PreprocessingContactComputationIssue,
    PreprocessingContactDefinition,
    PreprocessingContactDetectionOptions,
    PreprocessingContactFrameResult,
    PreprocessingContactPairResult,
    PreprocessingManifestContactsResult,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_contacts.py"
)


def make_issue(
    kind: str = "contact_computation_error",
) -> PreprocessingContactComputationIssue:
    return PreprocessingContactComputationIssue(
        kind=kind,
        field="contacts",
        message="Contact result is unavailable.",
    )


def make_pair(
    source_residue_index: int = 0,
    target_residue_index: int = 1,
    **overrides: object,
) -> PreprocessingContactPairResult:
    values: dict[str, object] = {
        "source_residue_index": source_residue_index,
        "target_residue_index": target_residue_index,
        "source_resname": "ALA",
        "target_resname": "GLY",
        "minimum_distance": 3.25,
        "source_residue_id": 10,
        "target_residue_id": "11A",
        "source_segid": "PROA",
        "target_segid": "PROA",
    }
    values.update(overrides)
    return PreprocessingContactPairResult(**values)


def make_frame(
    condition_name: str = "normal",
    frame_index: int = 0,
    *,
    contacts: tuple[PreprocessingContactPairResult, ...] | None = None,
    issues: tuple[PreprocessingContactComputationIssue, ...] = (),
) -> PreprocessingContactFrameResult:
    if contacts is None:
        contacts = (make_pair(),)
    return PreprocessingContactFrameResult(
        condition_name=condition_name,
        frame_index=frame_index,
        time_ps=float(frame_index),
        contacts=contacts,
        issues=issues,
    )


def make_condition(
    condition_name: str = "normal",
    *,
    frame_results: tuple[PreprocessingContactFrameResult, ...] | None = None,
    issues: tuple[PreprocessingContactComputationIssue, ...] = (),
    status: str = "computed",
) -> PreprocessingConditionContactsResult:
    if frame_results is None:
        frame_results = (make_frame(condition_name),)
    return PreprocessingConditionContactsResult(
        condition_name=condition_name,
        options=PreprocessingContactDetectionOptions(),
        frame_results=frame_results,
        issues=issues,
        status=status,
    )


def test_public_exports_and_stage_13_1a_exports_remain_available() -> None:
    assert mania.preprocessing is not None
    assert PreprocessingContactComputationIssue is not None
    assert PreprocessingContactPairResult is not None
    assert PreprocessingContactFrameResult is not None
    assert PreprocessingConditionContactsResult is not None
    assert PreprocessingManifestContactsResult is not None
    assert PreprocessingContactDefinition is not None
    assert PreprocessingContactDetectionOptions is not None


def test_issue_validates_normalizes_and_serializes() -> None:
    issue = PreprocessingContactComputationIssue(
        kind=" runtime_not_loaded ",
        field=" runtime ",
        message=" Runtime is unavailable. ",
    )

    assert issue.kind == "runtime_not_loaded"
    assert issue.field == "runtime"
    assert issue.message == "Runtime is unavailable."
    assert issue.to_dict() == {
        "kind": "runtime_not_loaded",
        "field": "runtime",
        "message": "Runtime is unavailable.",
    }
    json.dumps(issue.to_dict())


@pytest.mark.parametrize("field_name", ["kind", "field", "message"])
@pytest.mark.parametrize("invalid_value", ["", "   ", None])
def test_issue_rejects_empty_or_non_string_fields(
    field_name: str,
    invalid_value: object,
) -> None:
    values: dict[str, object] = {
        "kind": "frame_iteration_error",
        "field": "frame",
        "message": "Frame iteration failed.",
    }
    values[field_name] = invalid_value

    with pytest.raises(ValueError):
        PreprocessingContactComputationIssue(**values)


def test_contact_pair_validates_normalizes_and_serializes() -> None:
    pair = make_pair(
        source_resname=" ALA ",
        target_resname=" GLY ",
        distance_unit=" angstrom ",
        source_residue_id=" 10A ",
        target_residue_id=11,
        source_segid=" PROA ",
        target_segid=None,
    )

    assert pair.source_resname == "ALA"
    assert pair.target_resname == "GLY"
    assert pair.source_residue_id == "10A"
    assert pair.source_segid == "PROA"
    assert pair.to_dict() == {
        "source_residue_index": 0,
        "target_residue_index": 1,
        "source_resname": "ALA",
        "target_resname": "GLY",
        "minimum_distance": 3.25,
        "distance_unit": "angstrom",
        "atom_filter": "heavy",
        "source_residue_id": "10A",
        "target_residue_id": 11,
        "source_segid": "PROA",
        "target_segid": None,
    }
    json.dumps(pair.to_dict())


def test_contact_pair_rejects_same_residue_index() -> None:
    with pytest.raises(ValueError):
        make_pair(2, 2)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("source_residue_index", -1),
        ("source_residue_index", True),
        ("source_residue_index", 1.5),
        ("target_residue_index", -1),
        ("target_residue_index", False),
        ("target_residue_index", "1"),
    ],
)
def test_contact_pair_rejects_invalid_residue_indexes(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(ValueError):
        make_pair(**{field_name: invalid_value})


@pytest.mark.parametrize("field_name", ["source_resname", "target_resname"])
@pytest.mark.parametrize("invalid_value", ["", "   ", None])
def test_contact_pair_rejects_invalid_residue_names(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(ValueError):
        make_pair(**{field_name: invalid_value})


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("source_residue_id", ""),
        ("source_residue_id", "   "),
        ("source_residue_id", True),
        ("source_residue_id", 1.5),
        ("target_residue_id", object()),
        ("source_segid", ""),
        ("source_segid", "   "),
        ("target_segid", 1),
    ],
)
def test_contact_pair_rejects_invalid_optional_identifiers(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(ValueError):
        make_pair(**{field_name: invalid_value})


@pytest.mark.parametrize(
    "invalid_value",
    [-0.1, float("nan"), float("inf"), float("-inf"), True, "3.0"],
)
def test_contact_pair_rejects_invalid_distance(
    invalid_value: object,
) -> None:
    with pytest.raises(ValueError):
        make_pair(minimum_distance=invalid_value)


def test_contact_pair_accepts_zero_distance() -> None:
    assert make_pair(minimum_distance=0).minimum_distance == 0


@pytest.mark.parametrize("invalid_value", ["", "   ", None])
def test_contact_pair_rejects_invalid_distance_unit(
    invalid_value: object,
) -> None:
    with pytest.raises(ValueError):
        make_pair(distance_unit=invalid_value)


def test_contact_pair_rejects_unsupported_atom_filter() -> None:
    with pytest.raises(ValueError):
        make_pair(atom_filter="backbone")


def test_frame_result_summarizes_contacts_and_serializes() -> None:
    frame = make_frame(
        contacts=(
            make_pair(0, 1),
            make_pair(2, 3, source_resname="SER", target_resname="THR"),
        )
    )

    payload = frame.to_dict()

    assert frame.contact_count == 2
    assert frame.passed is True
    assert payload["contact_count"] == 2
    assert payload["contacts"] == [
        contact.to_dict() for contact in frame.contacts
    ]
    assert payload["issues"] == []
    json.dumps(payload)


def test_frame_result_with_issue_fails_and_serializes_issue() -> None:
    issue = make_issue("missing_atom_positions")
    frame = make_frame(issues=(issue,))

    assert frame.passed is False
    assert frame.to_dict()["issues"] == [issue.to_dict()]


@pytest.mark.parametrize("invalid_value", [-1, True, 1.5])
def test_frame_result_rejects_invalid_frame_index(
    invalid_value: object,
) -> None:
    with pytest.raises(ValueError):
        PreprocessingContactFrameResult(
            condition_name="normal",
            frame_index=invalid_value,
        )


@pytest.mark.parametrize(
    "invalid_value",
    [-0.1, float("nan"), float("inf"), float("-inf"), True, "1.0"],
)
def test_frame_result_rejects_invalid_time(invalid_value: object) -> None:
    with pytest.raises(ValueError):
        PreprocessingContactFrameResult(
            condition_name="normal",
            frame_index=0,
            time_ps=invalid_value,
        )


def test_frame_result_rejects_empty_condition_name() -> None:
    with pytest.raises(ValueError):
        PreprocessingContactFrameResult(condition_name=" ", frame_index=0)


def test_frame_result_rejects_invalid_contact_item() -> None:
    with pytest.raises(ValueError):
        PreprocessingContactFrameResult(
            condition_name="normal",
            frame_index=0,
            contacts=(object(),),
        )


def test_frame_result_rejects_invalid_issue_item() -> None:
    with pytest.raises(ValueError):
        PreprocessingContactFrameResult(
            condition_name="normal",
            frame_index=0,
            issues=(object(),),
        )


def test_condition_result_summarizes_frames_and_serializes() -> None:
    issue = make_issue("frame_iteration_error")
    condition = make_condition(
        frame_results=(
            make_frame(
                frame_index=0,
                contacts=(make_pair(0, 1), make_pair(2, 3)),
            ),
            make_frame(frame_index=1, contacts=(), issues=(issue,)),
        ),
        status="partial",
    )

    payload = condition.to_dict()

    assert condition.frame_count == 2
    assert condition.contact_count == 2
    assert condition.passed_frame_count == 1
    assert condition.failed_frame_count == 1
    assert condition.passed is False
    assert payload["options"] == condition.options.to_dict()
    assert payload["frame_results"] == [
        frame.to_dict() for frame in condition.frame_results
    ]
    json.dumps(payload)


def test_computed_condition_passes_when_all_frames_pass() -> None:
    assert make_condition(status="computed").passed is True


@pytest.mark.parametrize("status", ["not_computed", "partial", "failed"])
def test_non_computed_condition_status_does_not_pass(status: str) -> None:
    assert make_condition(status=status).passed is False


def test_condition_with_issue_does_not_pass() -> None:
    condition = make_condition(
        status="computed",
        issues=(make_issue("condition_contacts_failed"),),
    )

    assert condition.passed is False


def test_condition_rejects_invalid_options_object() -> None:
    with pytest.raises(ValueError):
        PreprocessingConditionContactsResult(
            condition_name="normal",
            options={},
        )


def test_condition_rejects_invalid_frame_result_item() -> None:
    with pytest.raises(ValueError):
        PreprocessingConditionContactsResult(
            condition_name="normal",
            options=PreprocessingContactDetectionOptions(),
            frame_results=(object(),),
        )


def test_condition_rejects_invalid_issue_item() -> None:
    with pytest.raises(ValueError):
        PreprocessingConditionContactsResult(
            condition_name="normal",
            options=PreprocessingContactDetectionOptions(),
            issues=(object(),),
        )


def test_condition_rejects_frame_condition_name_mismatch() -> None:
    with pytest.raises(ValueError):
        make_condition(
            condition_name="normal",
            frame_results=(make_frame("tumor"),),
        )


def test_condition_rejects_duplicate_frame_indexes() -> None:
    with pytest.raises(ValueError):
        make_condition(
            frame_results=(make_frame(frame_index=0), make_frame(frame_index=0))
        )


def test_condition_rejects_invalid_status() -> None:
    with pytest.raises(ValueError):
        make_condition(status="loaded")


def test_manifest_result_summarizes_conditions_and_serializes() -> None:
    normal = make_condition(
        "normal",
        frame_results=(make_frame("normal", 0), make_frame("normal", 1)),
    )
    frame_issue = make_issue("frame_iteration_error")
    tumor = make_condition(
        "tumor",
        frame_results=(
            make_frame("tumor", 0, contacts=()),
            make_frame("tumor", 1, contacts=(), issues=(frame_issue,)),
        ),
        status="partial",
    )
    manifest = PreprocessingManifestContactsResult(
        condition_results=(normal, tumor)
    )

    payload = manifest.to_dict()

    assert manifest.condition_count == 2
    assert manifest.computed_condition_count == 1
    assert manifest.failed_condition_count == 1
    assert manifest.frame_count == 4
    assert manifest.contact_count == 2
    assert manifest.passed_frame_count == 3
    assert manifest.failed_frame_count == 1
    assert manifest.passed is False
    assert payload["condition_results"] == [
        normal.to_dict(),
        tumor.to_dict(),
    ]
    json.dumps(payload)


def test_manifest_passes_only_when_all_conditions_pass() -> None:
    manifest = PreprocessingManifestContactsResult(
        condition_results=(make_condition("normal"), make_condition("tumor"))
    )

    assert manifest.passed is True
    assert manifest.failed_condition_count == 0


def test_manifest_fails_when_one_condition_fails() -> None:
    manifest = PreprocessingManifestContactsResult(
        condition_results=(
            make_condition("normal"),
            make_condition("tumor", status="failed"),
        )
    )

    assert manifest.passed is False
    assert manifest.failed_condition_count == 1


def test_manifest_rejects_duplicate_condition_names() -> None:
    with pytest.raises(ValueError):
        PreprocessingManifestContactsResult(
            condition_results=(
                make_condition("normal"),
                make_condition("normal"),
            )
        )


def test_empty_manifest_does_not_pass() -> None:
    manifest = PreprocessingManifestContactsResult()

    assert manifest.condition_count == 0
    assert manifest.passed is False


def test_manifest_rejects_invalid_condition_item() -> None:
    with pytest.raises(ValueError):
        PreprocessingManifestContactsResult(condition_results=(object(),))


def test_manifest_rejects_invalid_issue_item() -> None:
    with pytest.raises(ValueError):
        PreprocessingManifestContactsResult(issues=(object(),))


def test_manifest_issue_makes_result_fail() -> None:
    manifest = PreprocessingManifestContactsResult(
        condition_results=(make_condition(),),
        issues=(make_issue("manifest_load_issue"),),
    )

    assert manifest.passed is False


def test_all_result_contracts_are_json_serializable() -> None:
    issue = make_issue()
    pair = make_pair()
    frame = make_frame(contacts=(pair,))
    condition = make_condition(frame_results=(frame,))
    manifest = PreprocessingManifestContactsResult(
        condition_results=(condition,)
    )

    for result in (issue, pair, frame, condition, manifest):
        json.dumps(result.to_dict())


def test_nested_serialization_contains_dictionaries_not_dataclasses() -> None:
    pair = make_pair()
    frame = make_frame(contacts=(pair,))
    condition = make_condition(frame_results=(frame,))
    manifest = PreprocessingManifestContactsResult(
        condition_results=(condition,)
    )

    assert frame.to_dict()["contacts"] == [pair.to_dict()]
    assert condition.to_dict()["frame_results"] == [frame.to_dict()]
    assert manifest.to_dict()["condition_results"] == [condition.to_dict()]


def test_contacts_module_has_no_computation_or_runtime_loading() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "distance_array",
        "self_distance_array",
        "capped_distance",
        ".positions",
        ".trajectory",
        ".atoms",
        "radius_of_gyration",
        "load_single_condition_runtime",
        "load_manifest_condition_runtimes",
        "require_mdanalysis",
    ):
        assert forbidden_text not in source


def test_contacts_module_has_no_export_comparison_or_graph_output() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "write_contacts",
        "validate_contacts",
        "compare_contacts",
        "contacts_perframe",
        "contact_edges",
        "report_bundle",
        "graph.json",
        "nodes.csv",
        "edges.csv",
    ):
        assert forbidden_text not in source


def test_contacts_module_has_no_forbidden_scientific_imports() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_import in (
        "MDAnalysis",
        "numpy",
        "pandas",
        "networkx",
        "pyarrow",
        "scipy",
        "sklearn",
    ):
        assert forbidden_import not in source
