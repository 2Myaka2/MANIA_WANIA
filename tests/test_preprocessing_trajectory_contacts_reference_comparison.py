import csv
import json
from collections.abc import Sequence
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingContactsReferenceComparisonInput,
    PreprocessingContactsReferenceComparisonOptions,
    PreprocessingContactsReferenceComparisonResult,
    PreprocessingContactsReferenceComparisonRowResult,
    PreprocessingContactsReferenceComparisonTargetResult,
    compare_contacts_outputs,
)

PERFRAME_HEADER = (
    "condition_name",
    "frame_index",
    "time_ps",
    "source_residue_index",
    "target_residue_index",
    "source_residue_id",
    "target_residue_id",
    "source_resname",
    "target_resname",
    "source_segid",
    "target_segid",
    "minimum_distance",
    "distance_unit",
    "atom_filter",
    "frame_passed",
)
EDGES_HEADER = (
    "condition_name",
    "source_residue_index",
    "target_residue_index",
    "source_residue_id",
    "target_residue_id",
    "source_resname",
    "target_resname",
    "source_segid",
    "target_segid",
    "contact_frame_count",
    "total_frame_count",
    "contact_frequency",
    "minimum_distance",
    "mean_minimum_distance",
    "distance_unit",
    "atom_filter",
)


def write_csv(
    path: Path,
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    return path


def perframe_row(**updates: str) -> tuple[str, ...]:
    values = {
        "condition_name": "normal",
        "frame_index": "0",
        "time_ps": "0.0",
        "source_residue_index": "0",
        "target_residue_index": "1",
        "source_residue_id": "10",
        "target_residue_id": "11A",
        "source_resname": "ALA",
        "target_resname": "GLY",
        "source_segid": "PROA",
        "target_segid": "PROA",
        "minimum_distance": "3.25",
        "distance_unit": "angstrom",
        "atom_filter": "heavy",
        "frame_passed": "true",
    }
    values.update(updates)
    return tuple(values[field_name] for field_name in PERFRAME_HEADER)


def edges_row(**updates: str) -> tuple[str, ...]:
    values = {
        "condition_name": "normal",
        "source_residue_index": "0",
        "target_residue_index": "1",
        "source_residue_id": "10",
        "target_residue_id": "11A",
        "source_resname": "ALA",
        "target_resname": "GLY",
        "source_segid": "PROA",
        "target_segid": "PROA",
        "contact_frame_count": "1",
        "total_frame_count": "2",
        "contact_frequency": "0.5",
        "minimum_distance": "3.0",
        "mean_minimum_distance": "3.5",
        "distance_unit": "angstrom",
        "atom_filter": "heavy",
    }
    values.update(updates)
    return tuple(values[field_name] for field_name in EDGES_HEADER)


def comparison_input(
    tmp_path: Path,
    *,
    generated_perframe_rows: Sequence[Sequence[str]] | None = None,
    reference_perframe_rows: Sequence[Sequence[str]] | None = None,
    generated_edges_rows: Sequence[Sequence[str]] | None = None,
    reference_edges_rows: Sequence[Sequence[str]] | None = None,
    options: PreprocessingContactsReferenceComparisonOptions | None = None,
) -> PreprocessingContactsReferenceComparisonInput:
    tmp_path.mkdir(parents=True, exist_ok=True)
    if generated_perframe_rows is None:
        generated_perframe_rows = (perframe_row(),)
    if reference_perframe_rows is None:
        reference_perframe_rows = (perframe_row(),)
    if generated_edges_rows is None:
        generated_edges_rows = (edges_row(),)
    if reference_edges_rows is None:
        reference_edges_rows = (edges_row(),)
    return PreprocessingContactsReferenceComparisonInput(
        generated_contacts_perframe_csv=write_csv(
            tmp_path / "generated_contacts_perframe.csv",
            PERFRAME_HEADER,
            generated_perframe_rows,
        ),
        reference_contacts_perframe_csv=write_csv(
            tmp_path / "reference_contacts_perframe.csv",
            PERFRAME_HEADER,
            reference_perframe_rows,
        ),
        generated_contact_edges_csv=write_csv(
            tmp_path / "generated_contact_edges.csv",
            EDGES_HEADER,
            generated_edges_rows,
        ),
        reference_contact_edges_csv=write_csv(
            tmp_path / "reference_contact_edges.csv",
            EDGES_HEADER,
            reference_edges_rows,
        ),
        options=options or PreprocessingContactsReferenceComparisonOptions(),
    )


def row_issue_kinds(
    result: PreprocessingContactsReferenceComparisonResult,
) -> list[str]:
    return [
        issue.kind
        for target_result in result.target_results
        for row_result in target_result.row_results
        for issue in row_result.issues
    ]


def target_issue_kinds(
    result: PreprocessingContactsReferenceComparisonResult,
) -> list[str]:
    return [
        issue.kind
        for target_result in result.target_results
        for issue in target_result.issues
    ]


def global_issue_kinds(
    result: PreprocessingContactsReferenceComparisonResult,
) -> list[str]:
    return [issue.kind for issue in result.issues]


def test_public_exports_and_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None
    assert PreprocessingContactsReferenceComparisonRowResult is not None
    assert PreprocessingContactsReferenceComparisonTargetResult is not None
    assert PreprocessingContactsReferenceComparisonResult is not None
    assert compare_contacts_outputs is not None


def test_identical_contacts_outputs_pass(tmp_path: Path) -> None:
    result = compare_contacts_outputs(comparison_input(tmp_path))

    assert isinstance(result, PreprocessingContactsReferenceComparisonResult)
    assert result.passed is True
    assert result.input_validation_passed is True
    assert result.generated_row_count == 2
    assert result.reference_row_count == 2
    assert result.matched_row_count == 2
    assert result.failed_row_count == 0
    assert result.max_distance_abs_difference == 0.0
    assert result.max_frequency_abs_difference == 0.0
    assert result.perframe_result is not None
    assert isinstance(
        result.perframe_result,
        PreprocessingContactsReferenceComparisonTargetResult,
    )
    assert isinstance(
        result.perframe_result.row_results[0],
        PreprocessingContactsReferenceComparisonRowResult,
    )
    assert json.loads(json.dumps(result.to_dict())) == result.to_dict()


def test_can_compare_only_enabled_target(tmp_path: Path) -> None:
    generated_path = write_csv(
        tmp_path / "generated_contacts_perframe.csv",
        PERFRAME_HEADER,
        (perframe_row(),),
    )
    reference_path = write_csv(
        tmp_path / "reference_contacts_perframe.csv",
        PERFRAME_HEADER,
        (perframe_row(),),
    )
    comparison = PreprocessingContactsReferenceComparisonInput(
        generated_contacts_perframe_csv=generated_path,
        reference_contacts_perframe_csv=reference_path,
        options=PreprocessingContactsReferenceComparisonOptions(
            compare_contact_edges=False
        ),
    )

    result = compare_contacts_outputs(comparison)

    assert result.passed is True
    assert result.perframe_result is not None
    assert result.contact_edges_result is None
    assert result.generated_row_count == 1


def test_distance_tolerances_apply_to_perframe_and_edges(
    tmp_path: Path,
) -> None:
    options = PreprocessingContactsReferenceComparisonOptions(
        distance_abs_tolerance=0.2,
        distance_rel_tolerance=0.0,
    )

    result = compare_contacts_outputs(
        comparison_input(
            tmp_path,
            generated_perframe_rows=(perframe_row(minimum_distance="3.35"),),
            reference_perframe_rows=(perframe_row(minimum_distance="3.25"),),
            generated_edges_rows=(
                edges_row(minimum_distance="3.1", mean_minimum_distance="3.6"),
            ),
            reference_edges_rows=(edges_row(),),
            options=options,
        )
    )

    assert result.passed is True
    assert result.max_distance_abs_difference == pytest.approx(0.1)


def test_distance_outside_tolerances_fails(tmp_path: Path) -> None:
    result = compare_contacts_outputs(
        comparison_input(
            tmp_path,
            generated_perframe_rows=(perframe_row(minimum_distance="4.0"),),
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_contact_edges=False
            ),
        )
    )

    assert result.passed is False
    assert "minimum_distance_mismatch" in row_issue_kinds(result)


def test_frequency_tolerance_uses_frequency_options(tmp_path: Path) -> None:
    generated = edges_row(
        total_frame_count="3",
        contact_frequency="0.3333333333334",
    )
    reference = edges_row(
        contact_frame_count="1",
        total_frame_count="3",
        contact_frequency="0.3333333333333",
        mean_minimum_distance="3.5",
    )
    passing = compare_contacts_outputs(
        comparison_input(
            tmp_path / "passing",
            generated_edges_rows=(generated,),
            reference_edges_rows=(reference,),
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_perframe=False,
                frequency_abs_tolerance=1e-12,
                frequency_rel_tolerance=0.0,
            ),
        )
    )
    failing = compare_contacts_outputs(
        comparison_input(
            tmp_path / "failing",
            generated_edges_rows=(generated,),
            reference_edges_rows=(reference,),
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_perframe=False,
                frequency_abs_tolerance=0.0,
                frequency_rel_tolerance=0.0,
            ),
        )
    )

    assert passing.passed is True
    assert failing.passed is False
    assert "contact_frequency_mismatch" in row_issue_kinds(failing)


def test_exact_status_time_and_count_fields_fail(tmp_path: Path) -> None:
    result = compare_contacts_outputs(
        comparison_input(
            tmp_path,
            generated_perframe_rows=(
                perframe_row(time_ps="1.0", frame_passed="false"),
            ),
            generated_edges_rows=(
                edges_row(
                    contact_frame_count="2",
                    total_frame_count="4",
                    contact_frequency="0.5",
                ),
            ),
        )
    )

    assert result.passed is False
    kinds = set(row_issue_kinds(result))
    assert {
        "time_ps_mismatch",
        "frame_passed_mismatch",
        "contact_frame_count_mismatch",
        "total_frame_count_mismatch",
    } <= kinds


def test_missing_and_extra_rows_are_reported_by_exact_key(
    tmp_path: Path,
) -> None:
    result = compare_contacts_outputs(
        comparison_input(
            tmp_path,
            generated_perframe_rows=(
                perframe_row(source_residue_index="2", target_residue_index="3"),
            ),
            reference_perframe_rows=(perframe_row(),),
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_contact_edges=False
            ),
        )
    )

    assert result.passed is False
    assert result.missing_generated_row_count == 1
    assert result.extra_reference_row_count == 1
    assert result.missing_reference_row_count == 1
    assert result.extra_generated_row_count == 1
    assert {
        "missing_generated_row",
        "extra_reference_row",
        "missing_reference_row",
        "extra_generated_row",
    } <= set(row_issue_kinds(result))


def test_row_order_is_optional_and_can_be_enforced(tmp_path: Path) -> None:
    first = perframe_row(frame_index="0")
    second = perframe_row(
        frame_index="1",
        source_residue_index="2",
        target_residue_index="3",
    )
    default = compare_contacts_outputs(
        comparison_input(
            tmp_path / "default",
            generated_perframe_rows=(second, first),
            reference_perframe_rows=(first, second),
            options=PreprocessingContactsReferenceComparisonOptions(
                compare_contact_edges=False
            ),
        )
    )
    enforced = compare_contacts_outputs(
        comparison_input(
            tmp_path / "enforced",
            generated_perframe_rows=(second, first),
            reference_perframe_rows=(first, second),
            options=PreprocessingContactsReferenceComparisonOptions(
                require_exact_row_order=True,
                compare_contact_edges=False,
            ),
        )
    )

    assert default.passed is True
    assert enforced.passed is False
    assert target_issue_kinds(enforced) == ["row_order_mismatch"]
    assert enforced.failed_row_count == 0


def test_input_validation_failure_returns_empty_failed_report(
    tmp_path: Path,
) -> None:
    generated_path = write_csv(
        tmp_path / "generated_contacts_perframe.csv",
        tuple(reversed(PERFRAME_HEADER)),
        (perframe_row(),),
    )
    reference_path = write_csv(
        tmp_path / "reference_contacts_perframe.csv",
        PERFRAME_HEADER,
        (perframe_row(),),
    )
    comparison = PreprocessingContactsReferenceComparisonInput(
        generated_contacts_perframe_csv=generated_path,
        reference_contacts_perframe_csv=reference_path,
        options=PreprocessingContactsReferenceComparisonOptions(
            compare_contact_edges=False
        ),
    )

    result = compare_contacts_outputs(comparison)

    assert result.passed is False
    assert result.input_validation_passed is False
    assert result.target_results == ()
    assert result.generated_row_count == 0
    assert global_issue_kinds(result) == [
        "input_validation_failed",
        "perframe_validation_failed",
    ]
