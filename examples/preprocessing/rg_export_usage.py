"""Run a dependency-free synthetic Rg CSV export and validation example."""

from pathlib import Path
from tempfile import TemporaryDirectory

from mania.preprocessing import (
    PreprocessingConditionRgResult,
    PreprocessingManifestRgResult,
    PreprocessingRgFrameResult,
    validate_rg_timeseries_csv,
    write_rg_timeseries_csv,
)


def build_demo_rg_result() -> PreprocessingManifestRgResult:
    """Build a small synthetic manifest-level Rg result."""
    condition_result = PreprocessingConditionRgResult(
        condition_name="demo_condition",
        status="computed",
        runtime_type=None,
        topology_path=None,
        trajectory_paths=(),
        frame_time_ps=10.0,
        rg_unit="angstrom",
        frame_results=(
            PreprocessingRgFrameResult(
                condition_name="demo_condition",
                frame_index=0,
                time_ps=0.0,
                rg_value=12.3,
                rg_unit="angstrom",
                issues=(),
            ),
            PreprocessingRgFrameResult(
                condition_name="demo_condition",
                frame_index=1,
                time_ps=10.0,
                rg_value=12.5,
                rg_unit="angstrom",
                issues=(),
            ),
        ),
        issues=(),
    )
    return PreprocessingManifestRgResult(
        condition_results=(condition_result,),
        issues=(),
    )


def main() -> None:
    """Write and validate a temporary synthetic Rg CSV file."""
    rg_result = build_demo_rg_result()

    with TemporaryDirectory() as temporary_directory:
        output_path = Path(temporary_directory) / "rg_timeseries.csv"
        write_result = write_rg_timeseries_csv(rg_result, output_path)
        validation_result = validate_rg_timeseries_csv(output_path)

        assert write_result.passed
        assert validation_result.passed
        print(write_result.to_dict())
        print(validation_result.to_dict())


if __name__ == "__main__":
    main()
