"""Run a dependency-free synthetic contacts CSV export example."""

from pathlib import Path
from tempfile import TemporaryDirectory

from mania.preprocessing import (
    PreprocessingConditionContactsResult,
    PreprocessingContactDetectionOptions,
    PreprocessingContactFrameResult,
    PreprocessingContactPairResult,
    PreprocessingManifestContactsResult,
    validate_contact_edges_csv,
    validate_contacts_perframe_csv,
    write_contact_edges_csv,
    write_contacts_perframe_csv,
)


def build_synthetic_contacts_result() -> PreprocessingManifestContactsResult:
    """Build a small manifest-level contacts result from synthetic rows."""
    repeated_pair_first_frame = PreprocessingContactPairResult(
        source_residue_index=0,
        target_residue_index=1,
        source_residue_id=10,
        target_residue_id="11A",
        source_resname="ALA",
        target_resname="GLY",
        source_segid="PROA",
        target_segid="PROA",
        minimum_distance=3.0,
        distance_unit="angstrom",
        atom_filter="heavy",
    )
    repeated_pair_second_frame = PreprocessingContactPairResult(
        source_residue_index=0,
        target_residue_index=1,
        source_residue_id=10,
        target_residue_id="11A",
        source_resname="ALA",
        target_resname="GLY",
        source_segid="PROA",
        target_segid="PROA",
        minimum_distance=4.0,
        distance_unit="angstrom",
        atom_filter="heavy",
    )
    second_pair = PreprocessingContactPairResult(
        source_residue_index=2,
        target_residue_index=3,
        source_residue_id=None,
        target_residue_id=None,
        source_resname="SER",
        target_resname="THR",
        source_segid=None,
        target_segid=None,
        minimum_distance=3.5,
        distance_unit="angstrom",
        atom_filter="heavy",
    )
    condition_result = PreprocessingConditionContactsResult(
        condition_name="demo_condition",
        options=PreprocessingContactDetectionOptions(),
        frame_results=(
            PreprocessingContactFrameResult(
                condition_name="demo_condition",
                frame_index=0,
                time_ps=0.0,
                contacts=(repeated_pair_first_frame, second_pair),
            ),
            PreprocessingContactFrameResult(
                condition_name="demo_condition",
                frame_index=1,
                time_ps=10.0,
                contacts=(repeated_pair_second_frame,),
            ),
        ),
        issues=(),
        status="computed",
    )
    return PreprocessingManifestContactsResult(
        condition_results=(condition_result,),
        issues=(),
    )


def main() -> None:
    """Write and validate temporary synthetic contacts CSV files."""
    contacts_result = build_synthetic_contacts_result()

    with TemporaryDirectory() as temporary_directory:
        output_directory = Path(temporary_directory)
        perframe_path = output_directory / "contacts_perframe.csv"
        edges_path = output_directory / "contact_edges.csv"

        perframe_write = write_contacts_perframe_csv(
            contacts_result,
            perframe_path,
        )
        edges_write = write_contact_edges_csv(contacts_result, edges_path)
        perframe_validation = validate_contacts_perframe_csv(perframe_path)
        edges_validation = validate_contact_edges_csv(edges_path)

        assert perframe_write.passed
        assert edges_write.passed
        assert perframe_validation.passed
        assert edges_validation.passed
        print(f"contacts_perframe.csv validation passed: {perframe_validation.passed}")
        print(f"contact_edges.csv validation passed: {edges_validation.passed}")


if __name__ == "__main__":
    main()
