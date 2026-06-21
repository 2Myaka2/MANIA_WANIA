import json
import re
from pathlib import Path

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionResidueNames,
    PreprocessingConditionRuntime,
    PreprocessingConditionRuntimeInput,
    PreprocessingManifestLoadIssue,
    PreprocessingManifestLoadResult,
    PreprocessingManifestResidueNames,
    PreprocessingResidueNameExtractionIssue,
    PreprocessingTrajectoryLoadIssue,
    collect_condition_runtime_metadata,
    collect_manifest_runtime_metadata,
    extract_condition_residue_names,
    extract_manifest_residue_names,
    load_manifest_condition_runtimes,
    load_single_condition_runtime,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR_PATH = (
    REPO_ROOT / "src" / "mania" / "preprocessing" / "trajectory_residues.py"
)


class FakeResidues:
    def __init__(self, residue_names: object) -> None:
        self.resnames = residue_names


class FakeRuntime:
    def __init__(self, residue_names: object) -> None:
        self.residues = FakeResidues(residue_names)


def make_runtime_input(
    condition_name: str = "normal",
) -> PreprocessingConditionRuntimeInput:
    return PreprocessingConditionRuntimeInput(
        condition_name=condition_name,
        topology_path=Path(condition_name) / "topology.tpr",
        trajectory_paths=(Path(condition_name) / "trajectory.xtc",),
    )


def make_loaded_result(
    residue_names: object,
    *,
    condition_name: str = "normal",
    runtime_object: object | None = None,
) -> PreprocessingConditionLoadResult:
    runtime_input = make_runtime_input(condition_name)
    runtime = PreprocessingConditionRuntime(
        condition_name=condition_name,
        runtime_object=(
            runtime_object
            if runtime_object is not None
            else FakeRuntime(residue_names)
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


def make_failed_result(
    condition_name: str = "tumor",
) -> PreprocessingConditionLoadResult:
    return PreprocessingConditionLoadResult(
        condition_name=condition_name,
        runtime_input=make_runtime_input(condition_name),
        issues=(
            PreprocessingTrajectoryLoadIssue(
                kind="load_error",
                field="condition_runtime",
                message="Expected load failure.",
            ),
        ),
        status="failed",
    )


def test_public_exports_and_existing_stage_11_apis_work() -> None:
    assert mania.preprocessing is not None
    assert extract_condition_residue_names is not None
    assert extract_manifest_residue_names is not None
    assert PreprocessingResidueNameExtractionIssue is not None
    assert PreprocessingConditionResidueNames is not None
    assert PreprocessingManifestResidueNames is not None
    assert load_single_condition_runtime is not None
    assert load_manifest_condition_runtimes is not None
    assert collect_condition_runtime_metadata is not None
    assert collect_manifest_runtime_metadata is not None


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

    report = extract_condition_residue_names(result)

    assert report.passed is False
    assert report.runtime_type == "tests.ExplodingRuntime"
    assert report.topology_path == runtime_input.topology_path
    assert report.trajectory_paths == runtime_input.trajectory_paths
    assert report.residue_names == ()
    assert report.unique_residue_names == ()
    assert report.residue_count is None
    assert report.unique_residue_count is None
    assert [issue.kind for issue in report.issues] == [
        "condition_not_loaded"
    ]
    json.dumps(report.to_dict())


def test_loaded_runtime_extracts_ordered_and_unique_names() -> None:
    report = extract_condition_residue_names(
        make_loaded_result(["ALA", "GLY", "ALA", "SOD"])
    )

    assert report.passed is True
    assert report.runtime_type == "tests.FakeRuntime"
    assert report.residue_names == ("ALA", "GLY", "ALA", "SOD")
    assert report.unique_residue_names == ("ALA", "GLY", "SOD")
    assert report.residue_count == 4
    assert report.unique_residue_count == 3
    assert report.issues == ()
    assert json.loads(json.dumps(report.to_dict())) == report.to_dict()


def test_runtime_object_is_not_serialized() -> None:
    runtime_object = FakeRuntime(["ALA"])
    report = extract_condition_residue_names(
        make_loaded_result([], runtime_object=runtime_object)
    )

    payload = report.to_dict()

    assert "runtime_object" not in payload
    assert repr(runtime_object) not in repr(payload)
    assert json.loads(json.dumps(payload)) == payload


def test_loaded_like_result_without_runtime_reports_runtime_missing() -> None:
    result = PreprocessingConditionLoadResult(
        condition_name="normal",
        runtime_input=make_runtime_input(),
        runtime=None,
        status="loaded",
    )

    report = extract_condition_residue_names(result)

    assert report.passed is False
    assert [issue.kind for issue in report.issues] == ["runtime_missing"]


def test_missing_residues_reports_issue() -> None:
    report = extract_condition_residue_names(
        make_loaded_result([], runtime_object=object())
    )

    assert report.passed is False
    assert [issue.kind for issue in report.issues] == ["residues_missing"]


def test_missing_residue_names_reports_issue() -> None:
    class RuntimeWithoutNames:
        residues = object()

    report = extract_condition_residue_names(
        make_loaded_result([], runtime_object=RuntimeWithoutNames())
    )

    assert report.passed is False
    assert [issue.kind for issue in report.issues] == [
        "residue_names_missing"
    ]


def test_residue_name_access_failure_reports_issue() -> None:
    class FailingResidues:
        @property
        def resnames(self) -> object:
            raise RuntimeError("private details")

    class FailingRuntime:
        residues = FailingResidues()

    report = extract_condition_residue_names(
        make_loaded_result([], runtime_object=FailingRuntime())
    )

    assert report.passed is False
    assert [issue.kind for issue in report.issues] == ["residue_name_error"]
    assert "private details" not in report.issues[0].message


def test_invalid_names_are_excluded_with_indexed_issues() -> None:
    report = extract_condition_residue_names(
        make_loaded_result(["ALA", "", "   ", None, "GLY"])
    )

    assert report.passed is False
    assert report.residue_names == ("ALA", "GLY")
    assert report.unique_residue_names == ("ALA", "GLY")
    assert report.residue_count == 2
    assert report.unique_residue_count == 2
    assert [issue.field for issue in report.issues] == [
        "runtime_object.residues.resnames[1]",
        "runtime_object.residues.resnames[2]",
        "runtime_object.residues.resnames[3]",
    ]


def test_names_are_stripped_case_preserved_and_values_converted() -> None:
    report = extract_condition_residue_names(
        make_loaded_result([" ALA ", "gly", 123])
    )

    assert report.passed is True
    assert report.residue_names == ("ALA", "gly", "123")


def test_unique_names_preserve_first_seen_order() -> None:
    report = extract_condition_residue_names(
        make_loaded_result(["B", "A", "B", "C", "A"])
    )

    assert report.unique_residue_names == ("B", "A", "C")


def test_extraction_avoids_other_runtime_paths() -> None:
    class GuardedRuntime(FakeRuntime):
        @property
        def atoms(self) -> object:
            raise AssertionError("atoms must not be accessed")

        @property
        def trajectory(self) -> object:
            raise AssertionError("trajectory must not be accessed")

        @property
        def positions(self) -> object:
            raise AssertionError("positions must not be accessed")

        @property
        def coordinates(self) -> object:
            raise AssertionError("coordinates must not be accessed")

    report = extract_condition_residue_names(
        make_loaded_result([], runtime_object=GuardedRuntime(["ALA"]))
    )

    assert report.passed is True
    assert report.residue_names == ("ALA",)


def test_residue_name_collection_failure_reports_error() -> None:
    class BrokenNames:
        def __iter__(self) -> object:
            raise RuntimeError("iteration details")

    report = extract_condition_residue_names(
        make_loaded_result(BrokenNames())
    )

    assert report.passed is False
    assert [issue.kind for issue in report.issues] == ["residue_name_error"]


def test_all_invalid_names_have_zero_counts() -> None:
    report = extract_condition_residue_names(
        make_loaded_result([None, "", " "])
    )

    assert report.residue_names == ()
    assert report.unique_residue_names == ()
    assert report.residue_count == 0
    assert report.unique_residue_count == 0
    assert report.passed is False


def test_manifest_reports_preserve_order_and_summaries() -> None:
    normal = make_loaded_result(["ALA", "GLY"], condition_name="normal")
    tumor = make_failed_result("tumor")
    report = extract_manifest_residue_names(
        PreprocessingManifestLoadResult(
            condition_results=(normal, tumor),
        )
    )

    assert report.condition_names == ("normal", "tumor")
    assert report.loaded_condition_names == ("normal",)
    assert report.failed_condition_names == ("tumor",)
    assert report.total_conditions == 2
    assert report.loaded_conditions == 1
    assert report.failed_conditions == 1
    assert report.passed is False


def test_manifest_all_unique_names_preserve_first_seen_order() -> None:
    normal = make_loaded_result(["B", "A"], condition_name="normal")
    tumor = make_loaded_result(["A", "C", "B"], condition_name="tumor")
    report = extract_manifest_residue_names(
        PreprocessingManifestLoadResult(
            condition_results=(normal, tumor),
        )
    )

    assert report.all_unique_residue_names == ("B", "A", "C")


def test_manifest_load_issues_are_preserved() -> None:
    source_issue = PreprocessingManifestLoadIssue(
        kind="condition_load_error",
        condition_name="tumor",
        field="condition_runtime",
        message="The condition loader raised an unexpected error.",
    )
    report = extract_manifest_residue_names(
        PreprocessingManifestLoadResult(
            condition_results=(make_loaded_result(["ALA"]),),
            issues=(source_issue,),
        )
    )

    assert report.passed is False
    assert len(report.issues) == 1
    assert report.issues[0].kind == "manifest_load_issue"
    assert report.issues[0].condition_name == "tumor"
    assert report.issues[0].field == "condition_runtime"
    assert report.issues[0].message == source_issue.message


def test_manifest_serialization_and_lookup() -> None:
    report = extract_manifest_residue_names(
        PreprocessingManifestLoadResult(
            condition_results=(make_loaded_result(["ALA"]),),
        )
    )

    payload = report.to_dict()

    assert report.passed is True
    assert report.residue_names_for_condition("normal") is (
        report.condition_residue_names[0]
    )
    assert report.residue_names_for_condition("Normal") is None
    assert report.residue_names_for_condition("missing") is None
    assert "runtime_object" not in repr(payload)
    assert json.loads(json.dumps(payload)) == payload


def test_empty_manifest_report_does_not_pass() -> None:
    report = PreprocessingManifestResidueNames(
        condition_residue_names=(),
        issues=(),
    )

    assert report.passed is False
    assert report.total_conditions == 0


def test_extractor_source_has_only_allowed_runtime_paths() -> None:
    source_text = EXTRACTOR_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "require_mdanalysis",
        "load_single_condition_runtime",
        "load_manifest_condition_runtimes",
        "collect_condition_runtime_metadata",
        "collect_manifest_runtime_metadata",
        "run_residue_qc_from_manifest_options",
        "radius_of_gyration",
        "contacts",
        "select_atoms",
        ".atoms",
        ".trajectory",
        ".positions",
        "coordinates",
    ):
        assert forbidden_text not in source_text

    assert ".residues" in source_text
    assert ".resnames" in source_text


def test_extractor_has_no_forbidden_imports() -> None:
    forbidden_import_pattern = re.compile(
        r"^\s*(?:import|from)\s+"
        r"(?:MDAnalysis|numpy|pandas|networkx|pyarrow)"
        r"(?:\.|\s|$)"
    )

    for line in EXTRACTOR_PATH.read_text(encoding="utf-8").splitlines():
        assert forbidden_import_pattern.match(line) is None
