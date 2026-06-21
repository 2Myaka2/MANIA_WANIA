from pathlib import Path

from mania.io.paths import (
    as_path,
    get_condition_artifact_path,
    get_condition_output_dir,
    get_cross_condition_artifact_path,
)


def test_as_path_accepts_str() -> None:
    assert as_path("mania_output") == Path("mania_output")


def test_as_path_accepts_path() -> None:
    path = Path("mania_output")

    assert as_path(path) is path


def test_get_condition_output_dir() -> None:
    assert get_condition_output_dir("mania_output", "normal") == (
        Path("mania_output") / "normal"
    )


def test_get_condition_artifact_path() -> None:
    assert get_condition_artifact_path("mania_output", "normal", "nodes.csv") == (
        Path("mania_output") / "normal" / "nodes.csv"
    )


def test_get_cross_condition_artifact_path() -> None:
    assert get_cross_condition_artifact_path("mania_output", "comparison.csv") == (
        Path("mania_output") / "comparison.csv"
    )


def test_comparison_csv_is_not_under_condition_dirs() -> None:
    comparison_path = get_cross_condition_artifact_path(
        "mania_output",
        "comparison.csv",
    )

    assert comparison_path != Path("mania_output") / "normal" / "comparison.csv"
    assert comparison_path != Path("mania_output") / "tumor" / "comparison.csv"


def test_stats_csv_is_not_under_condition_dirs() -> None:
    stats_path = get_cross_condition_artifact_path("mania_output", "stats.csv")

    assert stats_path != Path("mania_output") / "normal" / "stats.csv"
    assert stats_path != Path("mania_output") / "tumor" / "stats.csv"


def test_helpers_do_not_require_files_or_directories_to_exist() -> None:
    output_dir = Path("missing_output") / "nested"

    assert get_condition_output_dir(output_dir, "normal") == output_dir / "normal"
    assert get_condition_artifact_path(output_dir, "normal", "nodes.csv") == (
        output_dir / "normal" / "nodes.csv"
    )
    assert get_cross_condition_artifact_path(output_dir, "stats.csv") == (
        output_dir / "stats.csv"
    )
