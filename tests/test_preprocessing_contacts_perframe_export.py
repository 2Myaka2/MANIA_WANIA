import csv
from pathlib import Path

from mania.preprocessing import (
    PreprocessingBackboneObservation,
    PreprocessingConditionContactsResult,
    PreprocessingContactDetectionOptions,
    PreprocessingContactFrameResult,
    PreprocessingContactPairResult,
    validate_contact_edges_csv,
    validate_contacts_perframe_csv,
    write_contact_edges_csv,
    write_contacts_perframe_csv,
)


def pair(edge_type: str, distance: float) -> PreprocessingContactPairResult:
    return PreprocessingContactPairResult(
        source_residue_index=0,
        target_residue_index=1,
        source_resname="PHE",
        target_resname="LYS",
        source_residue_id=10,
        target_residue_id=11,
        source_segid="A",
        target_segid="A",
        minimum_distance=distance,
        edge_type=edge_type,
    )


def typed_condition() -> PreprocessingConditionContactsResult:
    return PreprocessingConditionContactsResult(
        condition_name="normal",
        options=PreprocessingContactDetectionOptions(
            contact_selection="protein"
        ),
        frame_results=(
            PreprocessingContactFrameResult(
                condition_name="normal",
                frame_index=7,
                contacts=(
                    pair("residue_contact", 3.0),
                    pair("aromatic_pi", 5.0),
                    pair("cation_pi", 4.0),
                ),
                backbone_observations=(
                    PreprocessingBackboneObservation(
                        source_residue_index=0,
                        target_residue_index=1,
                        source_resname="PHE",
                        target_resname="LYS",
                        source_residue_id=10,
                        target_residue_id=11,
                        source_segid="A",
                        target_segid="A",
                        ca_distance=3.8,
                    ),
                ),
            ),
        ),
        status="computed",
    )


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def test_typed_exports_preserve_residue_contact_and_backbone_compatibility(
    tmp_path: Path,
) -> None:
    condition = typed_condition()
    perframe_path = tmp_path / "contacts_perframe.csv"
    aggregate_path = tmp_path / "contact_edges.csv"

    assert write_contacts_perframe_csv(condition, perframe_path).passed
    assert write_contact_edges_csv(condition, aggregate_path).passed

    perframe_rows = read_rows(perframe_path)
    aggregate_rows = read_rows(aggregate_path)
    assert {row["edge_type"] for row in perframe_rows} == {
        "residue_contact",
        "backbone",
        "aromatic_pi",
        "cation_pi",
    }
    assert {row["edge_type"] for row in aggregate_rows} == {
        "residue_contact",
        "aromatic_pi",
        "cation_pi",
    }
    assert {row["frame_index"] for row in perframe_rows} == {"7"}
    assert validate_contacts_perframe_csv(perframe_path).passed
    assert validate_contact_edges_csv(aggregate_path).passed


def test_unknown_aggregate_edge_type_fails_deterministically(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "contact_edges.csv"
    write_contact_edges_csv(typed_condition(), output_path)
    rows = read_rows(output_path)
    rows[0]["edge_type"] = "unknown_pi"

    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    result = validate_contact_edges_csv(output_path)
    assert result.passed is False
    assert "invalid_edge_type" in {issue.kind for issue in result.issues}
