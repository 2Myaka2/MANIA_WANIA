import csv
import json
from pathlib import Path

import mania.preprocessing
from mania.preprocessing import (
    PROTEIN_CONTACT_EDGE_COLUMNS,
    PROTEIN_CONTACT_PERFRAME_COLUMNS,
    PreprocessingConditionContactsResult,
    PreprocessingContactDetectionOptions,
    PreprocessingContactFrameResult,
    PreprocessingContactPairResult,
    PreprocessingManifestContactsResult,
    PreprocessingProteinContactArtifact,
    PreprocessingProteinContactCsvWriteIssue,
    PreprocessingProteinContactCsvWriteResult,
    write_preprocessing_protein_contact_artifacts_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_protein_contact_export.py"
)


def pair(
    source_index: int,
    target_index: int,
    *,
    source_resid: int | str,
    target_resid: int | str,
    source_resname: str,
    target_resname: str,
    source_segment: str,
    target_segment: str,
    distance_A: float,
    edge_type: str = "residue_contact",
) -> PreprocessingContactPairResult:
    return PreprocessingContactPairResult(
        source_residue_index=source_index,
        target_residue_index=target_index,
        source_residue_id=source_resid,
        target_residue_id=target_resid,
        source_resname=source_resname,
        target_resname=target_resname,
        source_segid=source_segment,
        target_segid=target_segment,
        minimum_distance=distance_A,
        distance_unit="angstrom",
        edge_type=edge_type,
    )


def frame(
    condition: str,
    frame_index: int,
    *contacts: PreprocessingContactPairResult,
) -> PreprocessingContactFrameResult:
    return PreprocessingContactFrameResult(
        condition_name=condition,
        frame_index=frame_index,
        time_ps=frame_index * 2.5,
        contacts=contacts,
    )


def condition(
    name: str,
    *frames: PreprocessingContactFrameResult,
    contact_selection: str = "protein",
) -> PreprocessingConditionContactsResult:
    return PreprocessingConditionContactsResult(
        condition_name=name,
        options=PreprocessingContactDetectionOptions(
            contact_selection=contact_selection
        ),
        frame_results=frames,
        status="computed",
    )


def read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return tuple(reader.fieldnames or ()), list(reader)


def test_public_exports_and_result_are_json_safe(tmp_path: Path) -> None:
    assert (
        mania.preprocessing.PROTEIN_CONTACT_EDGE_COLUMNS
        == PROTEIN_CONTACT_EDGE_COLUMNS
    )
    assert (
        mania.preprocessing.PROTEIN_CONTACT_PERFRAME_COLUMNS
        == PROTEIN_CONTACT_PERFRAME_COLUMNS
    )
    assert PreprocessingProteinContactArtifact is not None
    assert PreprocessingProteinContactCsvWriteIssue is not None
    assert PreprocessingProteinContactCsvWriteResult is not None

    result = write_preprocessing_protein_contact_artifacts_csv(
        condition("normal", frame("normal", 0)),
        tmp_path,
    )

    assert result.passed
    json.dumps(result.to_dict(), sort_keys=True)


def test_writes_one_artifact_pair_per_condition(tmp_path: Path) -> None:
    normal_pair = pair(
        1,
        4,
        source_resid="10A",
        target_resid=20,
        source_resname="PHE",
        target_resname="LYS",
        source_segment="A",
        target_segment="B",
        distance_A=3.0,
    )
    tumor_pair = pair(
        2,
        8,
        source_resid=30,
        target_resid=40,
        source_resname="ALA",
        target_resname="GLY",
        source_segment="A",
        target_segment="A",
        distance_A=4.0,
        edge_type="aromatic_pi",
    )
    result = write_preprocessing_protein_contact_artifacts_csv(
        PreprocessingManifestContactsResult(
            condition_results=(
                condition("tumor", frame("tumor", 7, tumor_pair)),
                condition("normal", frame("normal", 3, normal_pair)),
            )
        ),
        tmp_path,
    )

    assert result.passed
    assert [artifact.condition for artifact in result.artifacts] == [
        "normal",
        "tumor",
    ]
    assert result.edge_paths_by_condition == {
        "normal": tmp_path / "protein_contact_edges_undirected_normal.csv",
        "tumor": tmp_path / "protein_contact_edges_undirected_tumor.csv",
    }
    assert result.perframe_paths_by_condition == {
        "normal": tmp_path / "contacts_perframe_normal.csv",
        "tumor": tmp_path / "contacts_perframe_tumor.csv",
    }
    _, tumor_rows = read_csv(result.edge_paths_by_condition["tumor"])
    assert tumor_rows[0]["condition"] == "tumor"
    assert tumor_rows[0]["edge_type"] == "aromatic_pi"


def test_aggregate_uses_sampled_frames_population_std_and_weight(
    tmp_path: Path,
) -> None:
    forward = pair(
        1,
        4,
        source_resid="10A",
        target_resid=20,
        source_resname="PHE",
        target_resname="LYS",
        source_segment="A",
        target_segment="B",
        distance_A=3.0,
    )
    reverse = pair(
        4,
        1,
        source_resid=20,
        target_resid="10A",
        source_resname="LYS",
        target_resname="PHE",
        source_segment="B",
        target_segment="A",
        distance_A=5.0,
    )
    result = write_preprocessing_protein_contact_artifacts_csv(
        condition(
            "normal",
            frame("normal", 0, forward),
            frame("normal", 2, reverse),
            frame("normal", 4),
            frame("normal", 6),
        ),
        tmp_path,
    )

    header, rows = read_csv(result.edge_paths_by_condition["normal"])
    assert header == PROTEIN_CONTACT_EDGE_COLUMNS
    assert rows == [
        {
            "condition": "normal",
            "residue_index_i": "1",
            "resid_i": "10A",
            "resname_i": "PHE",
            "segment_id_i": "A",
            "residue_index_j": "4",
            "resid_j": "20",
            "resname_j": "LYS",
            "segment_id_j": "B",
            "edge_type": "residue_contact",
            "contact_frame_count": "2",
            "sampled_frame_count": "4",
            "contact_freq": "0.5",
            "mean_dist_A": "4.0",
            "std_dist_A": "1.0",
            "weight": "0.5",
        }
    ]


def test_perframe_rows_preserve_source_frame_and_canonical_identity(
    tmp_path: Path,
) -> None:
    reverse = pair(
        9,
        3,
        source_resid=90,
        target_resid=30,
        source_resname="LYS",
        target_resname="PHE",
        source_segment="B",
        target_segment="A",
        distance_A=4.25,
    )
    result = write_preprocessing_protein_contact_artifacts_csv(
        condition("treated group", frame("treated group", 11, reverse)),
        tmp_path,
    )

    path = tmp_path / "contacts_perframe_treated_group.csv"
    header, rows = read_csv(path)
    assert result.perframe_paths_by_condition == {"treated group": path}
    assert header == PROTEIN_CONTACT_PERFRAME_COLUMNS
    assert rows == [
        {
            "condition": "treated group",
            "frame_index": "11",
            "time_ps": "27.5",
            "residue_index_i": "3",
            "resid_i": "30",
            "resname_i": "PHE",
            "segment_id_i": "A",
            "residue_index_j": "9",
            "resid_j": "90",
            "resname_j": "LYS",
            "segment_id_j": "B",
            "edge_type": "residue_contact",
            "distance_A": "4.25",
        }
    ]


def test_rejects_non_protein_selection_without_writing(tmp_path: Path) -> None:
    result = write_preprocessing_protein_contact_artifacts_csv(
        condition(
            "normal",
            frame("normal", 0),
            contact_selection="all",
        ),
        tmp_path,
    )

    assert not result.passed
    assert result.issues[0].kind == "non_protein_contact_selection"
    assert list(tmp_path.iterdir()) == []


def test_export_is_dependency_free_and_does_not_touch_wania_contract() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "MDAnalysis",
        "numpy",
        "pandas",
        "pyarrow",
        "fastparquet",
        "mania.wania",
        "wania_graph_payload",
    ):
        assert forbidden not in source
