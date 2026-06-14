import csv
import json
from pathlib import Path

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingConditionRgResult,
    PreprocessingManifestRgResult,
    PreprocessingRgComputationIssue,
    PreprocessingRgCsvWriteIssue,
    PreprocessingRgCsvWriteResult,
    PreprocessingRgFrameResult,
    write_rg_timeseries_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORT_MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_rg_export.py"
)
CSV_HEADER = [
    "condition_name",
    "frame_index",
    "time_ps",
    "rg_value",
    "rg_unit",
    "frame_passed",
]


def make_issue(
    condition_name: str,
    frame_index: int,
) -> PreprocessingRgComputationIssue:
    return PreprocessingRgComputationIssue(
        kind="rg_computation_error",
        condition_name=condition_name,
        frame_index=frame_index,
        field="rg_value",
        message="Expected frame failure.",
    )


def make_frame(
    condition_name: str,
    frame_index: int,
    *,
    time_ps: float | None = 0.0,
    rg_value: float | None = 10.0,
    failed: bool = False,
) -> PreprocessingRgFrameResult:
    issues = (make_issue(condition_name, frame_index),) if failed else ()
    return PreprocessingRgFrameResult(
        condition_name=condition_name,
        frame_index=frame_index,
        time_ps=time_ps,
        rg_value=rg_value,
        rg_unit="angstrom" if rg_value is not None else None,
        issues=issues,
    )


def make_condition(
    condition_name: str = "normal",
    *,
    frames: tuple[PreprocessingRgFrameResult, ...] | None = None,
) -> PreprocessingConditionRgResult:
    if frames is None:
        frames = (
            make_frame(condition_name, 0),
            make_frame(
                condition_name,
                1,
                time_ps=2.5,
                rg_value=11.25,
            ),
        )
    return PreprocessingConditionRgResult(
        condition_name=condition_name,
        status="computed",
        runtime_type=None,
        topology_path=None,
        trajectory_paths=(),
        frame_time_ps=None,
        rg_unit="angstrom",
        frame_results=frames,
    )


def read_rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        return list(csv.reader(csv_file))


def test_public_exports_and_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None
    assert write_rg_timeseries_csv is not None
    assert PreprocessingRgCsvWriteIssue is not None
    assert PreprocessingRgCsvWriteResult is not None


def test_issue_to_dict_is_json_serializable() -> None:
    issue = PreprocessingRgCsvWriteIssue(
        kind="output_exists",
        field="output_path",
        message="Output exists.",
    )

    payload = issue.to_dict()

    assert payload == {
        "kind": "output_exists",
        "field": "output_path",
        "message": "Output exists.",
    }
    assert json.loads(json.dumps(payload)) == payload


def test_write_result_to_dict_is_json_serializable() -> None:
    issue = PreprocessingRgCsvWriteIssue(
        kind="write_error",
        field="output_path",
        message="Write failed.",
    )
    result = PreprocessingRgCsvWriteResult(
        output_path=Path("rg_timeseries.csv"),
        passed=False,
        rows_written=0,
        condition_count=1,
        frame_count=2,
        skipped_frame_count=2,
        issues=(issue,),
    )

    payload = result.to_dict()

    assert payload["output_path"] == "rg_timeseries.csv"
    assert set(payload) == {
        "output_path",
        "passed",
        "rows_written",
        "condition_count",
        "frame_count",
        "skipped_frame_count",
        "issues",
    }
    assert "rg_result" not in payload
    assert json.loads(json.dumps(payload)) == payload


def test_writes_manifest_result_in_condition_and_frame_order(
    tmp_path: Path,
) -> None:
    result = PreprocessingManifestRgResult(
        condition_results=(
            make_condition("normal"),
            make_condition(
                "tumor",
                frames=(
                    make_frame("tumor", 3, time_ps=7.5, rg_value=13.0),
                ),
            ),
        )
    )
    output_path = tmp_path / "rg_timeseries.csv"

    write_result = write_rg_timeseries_csv(result, output_path)

    assert write_result.passed is True
    assert write_result.rows_written == 3
    assert write_result.condition_count == 2
    assert write_result.frame_count == 3
    assert write_result.skipped_frame_count == 0
    assert read_rows(output_path) == [
        CSV_HEADER,
        ["normal", "0", "0.0", "10.0", "angstrom", "true"],
        ["normal", "1", "2.5", "11.25", "angstrom", "true"],
        ["tumor", "3", "7.5", "13.0", "angstrom", "true"],
    ]
    assert output_path.read_bytes().splitlines()[0] == b",".join(
        item.encode() for item in CSV_HEADER
    )


def test_writes_single_condition_result(tmp_path: Path) -> None:
    output_path = tmp_path / "rg_timeseries.csv"

    result = write_rg_timeseries_csv(make_condition(), output_path)

    assert result.passed is True
    assert result.condition_count == 1
    assert result.frame_count == 2
    assert read_rows(output_path)[1][0] == "normal"


def test_missing_time_is_written_as_empty_string(tmp_path: Path) -> None:
    condition = make_condition(
        frames=(make_frame("normal", 0, time_ps=None),)
    )
    output_path = tmp_path / "rg_timeseries.csv"

    result = write_rg_timeseries_csv(condition, output_path)

    assert result.passed is True
    assert read_rows(output_path)[1][2] == ""


def test_default_excludes_failed_frames(tmp_path: Path) -> None:
    condition = make_condition(
        frames=(
            make_frame("normal", 0),
            make_frame(
                "normal",
                1,
                time_ps=2.5,
                rg_value=None,
                failed=True,
            ),
        )
    )
    output_path = tmp_path / "rg_timeseries.csv"

    result = write_rg_timeseries_csv(condition, output_path)

    assert result.passed is True
    assert result.rows_written == 1
    assert result.frame_count == 2
    assert result.skipped_frame_count == 1
    assert read_rows(output_path) == [
        CSV_HEADER,
        ["normal", "0", "0.0", "10.0", "angstrom", "true"],
    ]


def test_include_failed_frames_writes_empty_values(tmp_path: Path) -> None:
    condition = make_condition(
        frames=(
            make_frame("normal", 0),
            make_frame(
                "normal",
                1,
                time_ps=None,
                rg_value=None,
                failed=True,
            ),
        )
    )
    output_path = tmp_path / "rg_timeseries.csv"

    result = write_rg_timeseries_csv(
        condition,
        output_path,
        include_failed_frames=True,
    )

    assert result.passed is True
    assert result.rows_written == 2
    assert result.skipped_frame_count == 0
    assert read_rows(output_path)[2] == [
        "normal",
        "1",
        "",
        "",
        "",
        "false",
    ]


def test_no_writable_frames_fails_without_creating_file(
    tmp_path: Path,
) -> None:
    condition = make_condition(
        frames=(
            make_frame("normal", 0, rg_value=None, failed=True),
        )
    )
    output_path = tmp_path / "rg_timeseries.csv"

    result = write_rg_timeseries_csv(condition, output_path)

    assert result.passed is False
    assert result.rows_written == 0
    assert result.skipped_frame_count == 1
    assert [issue.kind for issue in result.issues] == [
        "no_writable_frames"
    ]
    assert not output_path.exists()


def test_empty_manifest_fails_deterministically(tmp_path: Path) -> None:
    output_path = tmp_path / "rg_timeseries.csv"

    result = write_rg_timeseries_csv(
        PreprocessingManifestRgResult(),
        output_path,
    )

    assert result.passed is False
    assert result.condition_count == 0
    assert result.frame_count == 0
    assert [issue.kind for issue in result.issues] == ["empty_rg_result"]
    assert not output_path.exists()


def test_condition_without_frames_fails_deterministically(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "rg_timeseries.csv"

    result = write_rg_timeseries_csv(
        make_condition(frames=()),
        output_path,
    )

    assert result.passed is False
    assert result.condition_count == 1
    assert result.frame_count == 0
    assert [issue.kind for issue in result.issues] == [
        "no_writable_frames"
    ]
    assert not output_path.exists()


def test_missing_output_directory_fails(tmp_path: Path) -> None:
    output_path = tmp_path / "missing" / "rg_timeseries.csv"

    result = write_rg_timeseries_csv(make_condition(), output_path)

    assert result.passed is False
    assert [issue.kind for issue in result.issues] == [
        "output_directory_missing"
    ]
    assert not output_path.exists()


def test_output_path_directory_fails(tmp_path: Path) -> None:
    result = write_rg_timeseries_csv(make_condition(), tmp_path)

    assert result.passed is False
    assert [issue.kind for issue in result.issues] == [
        "output_path_is_directory"
    ]


def test_existing_output_without_overwrite_is_unchanged(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "rg_timeseries.csv"
    output_path.write_text("old content\n", encoding="utf-8")

    result = write_rg_timeseries_csv(
        make_condition(),
        output_path,
        overwrite=False,
    )

    assert result.passed is False
    assert [issue.kind for issue in result.issues] == ["output_exists"]
    assert output_path.read_text(encoding="utf-8") == "old content\n"


def test_existing_output_is_overwritten(tmp_path: Path) -> None:
    output_path = tmp_path / "rg_timeseries.csv"
    output_path.write_text("old content\n", encoding="utf-8")

    result = write_rg_timeseries_csv(
        make_condition(),
        output_path,
        overwrite=True,
    )

    assert result.passed is True
    assert output_path.read_text(encoding="utf-8").startswith(
        ",".join(CSV_HEADER) + "\n"
    )
    assert "old content" not in output_path.read_text(encoding="utf-8")


def test_writer_consumes_results_without_scientific_operations() -> None:
    source_text = EXPORT_MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "radius_of_gyration",
        ".trajectory",
        ".atoms",
        "compute_condition_rg",
        "compute_manifest_rg",
        "load_single_condition_runtime",
        "load_manifest_condition_runtimes",
        "require_mdanalysis",
    ):
        assert forbidden_text not in source_text


def test_writer_avoids_later_stage_features() -> None:
    source_text = EXPORT_MODULE_PATH.read_text(encoding="utf-8").lower()

    for forbidden_text in (
        "reference",
        "comparison",
        "tolerance",
        "backend",
        "contract",
        "contacts",
        "graph",
        "edges",
        "nodes",
    ):
        assert forbidden_text not in source_text


def test_writer_has_no_forbidden_scientific_imports() -> None:
    source_text = EXPORT_MODULE_PATH.read_text(encoding="utf-8")

    for package_name in (
        "MDAnalysis",
        "numpy",
        "pandas",
        "networkx",
        "pyarrow",
    ):
        assert f"import {package_name}" not in source_text
        assert f"from {package_name}" not in source_text
