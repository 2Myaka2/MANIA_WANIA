import csv
import json
from pathlib import Path

import mania.preprocessing
from mania.preprocessing import (
    RESIDUE_TABLE_COLUMNS,
    PreprocessingGraphExportMappingIssue,
    PreprocessingGraphExportMappingResult,
    PreprocessingGraphNodeMappingRecord,
    PreprocessingResidueTableArtifact,
    PreprocessingResidueTableCsvWriteIssue,
    PreprocessingResidueTableCsvWriteResult,
    write_preprocessing_residue_tables_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_residue_table_export.py"
)


def node(
    node_id: str,
    *,
    condition: str = "normal",
    residue_index: int = 0,
    resid: str = "10",
    resname: str = "ALA",
    segment_id: str | None = "A",
    coordinates: tuple[float, float, float] | None = (1.25, 2.5, 3.75),
) -> PreprocessingGraphNodeMappingRecord:
    x_ca, y_ca, z_ca = coordinates or (None, None, None)
    return PreprocessingGraphNodeMappingRecord(
        node_id=node_id,
        condition_name=condition,
        residue_index=residue_index,
        residue_id=resid,
        resname=resname,
        segid=segment_id,
        x_ca=x_ca,
        y_ca=y_ca,
        z_ca=z_ca,
    )


def mapping(
    *nodes: PreprocessingGraphNodeMappingRecord,
) -> PreprocessingGraphExportMappingResult:
    return PreprocessingGraphExportMappingResult(nodes=tuple(nodes), edges=())


def read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return tuple(reader.fieldnames or ()), list(reader)


def test_public_exports_and_result_are_json_safe(tmp_path: Path) -> None:
    assert mania.preprocessing.RESIDUE_TABLE_COLUMNS == RESIDUE_TABLE_COLUMNS
    assert PreprocessingResidueTableArtifact is not None
    assert PreprocessingResidueTableCsvWriteIssue is not None
    assert PreprocessingResidueTableCsvWriteResult is not None
    assert callable(write_preprocessing_residue_tables_csv)

    result = write_preprocessing_residue_tables_csv(
        mapping(node("normal|A|0|10|ALA")),
        tmp_path,
    )

    assert result.passed
    assert result.rows_written == 1
    json.dumps(result.to_dict(), sort_keys=True)


def test_writer_emits_per_condition_residue_tables_with_explicit_identity(
    tmp_path: Path,
) -> None:
    result = write_preprocessing_residue_tables_csv(
        mapping(
            node(
                "tumor|B|4|20|GLY",
                condition="tumor",
                residue_index=4,
                resid="20",
                resname="GLY",
                segment_id="B",
            ),
            node("normal|A|0|10|ALA"),
        ),
        tmp_path,
    )

    assert result.passed
    assert result.rows_written == 2
    assert result.paths_by_condition == {
        "normal": tmp_path / "residue_table_normal.csv",
        "tumor": tmp_path / "residue_table_tumor.csv",
    }
    normal_header, normal_rows = read_csv(
        tmp_path / "residue_table_normal.csv"
    )
    _, tumor_rows = read_csv(tmp_path / "residue_table_tumor.csv")
    assert normal_header == RESIDUE_TABLE_COLUMNS
    assert normal_rows[0]["condition"] == "normal"
    assert normal_rows[0]["residue_index"] == "0"
    assert normal_rows[0]["resid"] == "10"
    assert normal_rows[0]["resname"] == "ALA"
    assert normal_rows[0]["segment_id"] == "A"
    assert tumor_rows[0]["condition"] == "tumor"
    assert tumor_rows[0]["residue_index"] == "4"
    assert tumor_rows[0]["resid"] == "20"
    assert tumor_rows[0]["resname"] == "GLY"
    assert tumor_rows[0]["segment_id"] == "B"


def test_coordinates_are_scientific_ca_values_and_missing_values_are_empty(
    tmp_path: Path,
) -> None:
    result = write_preprocessing_residue_tables_csv(
        mapping(
            node("normal|A|0|10|ALA"),
            node(
                "normal||1|11|GLY",
                residue_index=1,
                resid="11",
                resname="GLY",
                segment_id=None,
                coordinates=None,
            ),
        ),
        tmp_path,
    )

    _, rows = read_csv(result.paths_by_condition["normal"])
    assert rows[0]["x_ca"] == "1.25"
    assert rows[0]["y_ca"] == "2.5"
    assert rows[0]["z_ca"] == "3.75"
    assert rows[1]["segment_id"] == ""
    for column in (
        "region",
        "x_ca",
        "y_ca",
        "z_ca",
        "tm_relative_z",
        "rmsf_A",
        "sasa_A2",
        "ss",
    ):
        assert rows[1][column] == ""


def test_writer_is_csv_safe_and_deterministic(tmp_path: Path) -> None:
    result = write_preprocessing_residue_tables_csv(
        mapping(
            node(
                "treated group|chain,1|2|A,10|GLY,ALT",
                condition="treated group",
                residue_index=2,
                resid="A,10",
                resname="GLY,ALT",
                segment_id="chain,1",
            ),
            node(
                "treated group|A|1|5|ALA",
                condition="treated group",
                residue_index=1,
                resid="5",
            ),
        ),
        tmp_path,
    )

    path = tmp_path / "residue_table_treated_group.csv"
    _, rows = read_csv(path)
    assert result.passed
    assert result.paths_by_condition == {"treated group": path}
    assert [row["residue_index"] for row in rows] == ["1", "2"]
    assert rows[1]["resid"] == "A,10"
    assert rows[1]["resname"] == "GLY,ALT"
    assert rows[1]["segment_id"] == "chain,1"


def test_writer_reports_filename_collision_without_writing(tmp_path: Path) -> None:
    result = write_preprocessing_residue_tables_csv(
        mapping(
            node("A B|A|0|1|ALA", condition="A B", resid="1"),
            node("A_B|A|0|1|ALA", condition="A_B", resid="1"),
        ),
        tmp_path,
    )

    assert not result.passed
    assert result.issues[0].kind == "condition_filename_collision"
    assert list(tmp_path.iterdir()) == []


def test_failed_mapping_is_not_written(tmp_path: Path) -> None:
    failed_mapping = PreprocessingGraphExportMappingResult(
        nodes=(),
        edges=(),
        issues=(
            PreprocessingGraphExportMappingIssue(
                kind="mapping_failed",
                message="Synthetic failure.",
            ),
        ),
    )

    result = write_preprocessing_residue_tables_csv(failed_mapping, tmp_path)

    assert not result.passed
    assert result.issues[0].kind == "mapping_result_failed"
    assert list(tmp_path.iterdir()) == []


def test_export_is_dependency_free_and_does_not_touch_wania_contract() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "MDAnalysis",
        "numpy",
        "pandas",
        "pyarrow",
        "mania.wania",
        "wania_graph_payload",
    ):
        assert forbidden not in source
