"""Publication command surface and normal error reporting."""

import json
import sys

import pytest
from test_dataset_release_workflow import make_release_case

from mania.cli import build_parser, main


def test_publish_cli(tmp_path, monkeypatch, capsys):
    path, _ = make_release_case(tmp_path / "inputs")
    output = tmp_path / "release"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mania",
            "dataset",
            "publish",
            "--manifest",
            str(path),
            "--output",
            str(output),
        ],
    )
    main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["publication_csv_count"] == 17
    assert payload["simulation_count"] == 3
    assert payload["scientific_release_replica_count"] == 2
    assert payload["excluded_simulation_count"] == 1
    assert payload["production_aggregate_lineage_verified"] is True
    assert payload["release_version"] == "1.0"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mania",
            "artifacts",
            "validate",
            str(output),
            "--scope",
            "dataset_release",
            "--input-artifact-path",
            f"input:dataset_release_export_manifest={path}",
        ],
    )
    main()
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "passed" and report["complete"]


def test_publish_failure_has_prefix_without_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mania",
            "dataset",
            "publish",
            "--manifest",
            str(tmp_path / "missing.json"),
            "--output",
            str(tmp_path / "release"),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    error = capsys.readouterr().err
    assert error.startswith("Dataset release manifest failed:")
    assert "Traceback" not in error


@pytest.mark.parametrize(
    "option",
    [
        "--parquet",
        "--include-excluded",
        "--coverage-threshold",
        "--contact-cutoff",
        "--aggregate-ddof",
    ],
)
def test_no_scientific_or_parquet_options(option):
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            [
                "dataset",
                "publish",
                "--manifest",
                "control.json",
                "--output",
                "release",
                option,
            ]
        )
