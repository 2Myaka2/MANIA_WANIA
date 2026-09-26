"""Public production CLI parsing, exact selection and blocking results."""

import json
import shutil
import sys
from pathlib import Path

import pytest
from test_dataset_release_workflow import make_release_case
from test_production_catalog import CATALOG, EGOR_IDS, technical_file
from test_production_run import install_runtime, make_case

from mania import cli


def invoke(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["mania", "production", *map(str, args)])
    code = 0
    try:
        cli.main()
    except SystemExit as exc:
        code = exc.code
    captured = capsys.readouterr()
    return code, json.loads(captured.out), captured.err


@pytest.mark.parametrize("trajectory_id", EGOR_IDS)
def test_validate_all_nine_cli(tmp_path, monkeypatch, capsys, trajectory_id):
    case = make_case(tmp_path, monkeypatch, trajectory_id)
    code, result, _ = invoke(
        monkeypatch,
        capsys,
        "validate",
        "--catalog",
        CATALOG,
        "--trajectory-id",
        trajectory_id,
        "--output-root",
        case.output,
        "--input-binding",
        case.binding,
        "--min-free-bytes",
        1,
    )
    assert code == 0 and result["status"] == "preflight_passed"
    assert not case.output.exists()


def test_public_run_and_resume(tmp_path, monkeypatch, capsys):
    case = make_case(tmp_path, monkeypatch)
    runtimes = install_runtime(monkeypatch)
    args = (
        "run",
        "--catalog",
        CATALOG,
        "--trajectory-id",
        case.selected.trajectory_id,
        "--output-root",
        case.output,
        "--min-free-bytes",
        1,
    )
    code, result, err = invoke(
        monkeypatch, capsys, *args, "--input-binding", case.binding
    )
    assert (code, err) == (0, "") and result["status"] == "science_complete"
    code, result, err = invoke(monkeypatch, capsys, *args, "--resume")
    assert (code, err) == (0, "") and result["reused"]
    assert len(runtimes) == 1


def test_public_technical_validate_run_resume_and_missing_option(
    tmp_path, monkeypatch, capsys
):
    case = make_case(tmp_path, monkeypatch)
    runtimes = install_runtime(monkeypatch)
    manifest = technical_file(tmp_path)
    args = (
        "--catalog",
        CATALOG,
        "--trajectory-id",
        EGOR_IDS[0],
        "--output-root",
        case.output,
        "--min-free-bytes",
        1,
    )
    code, result, err = invoke(
        monkeypatch,
        capsys,
        "validate",
        *args,
        "--input-binding",
        case.binding,
        "--technical-manifest",
        manifest,
    )
    assert (code, err) == (0, "")
    assert result["purpose"] == "technical_validation"
    assert result["production_eligible"] is False
    assert not case.output.exists() and not runtimes
    code, result, err = invoke(
        monkeypatch,
        capsys,
        "run",
        *args,
        "--input-binding",
        case.binding,
        "--technical-manifest",
        manifest,
    )
    assert (code, err) == (0, "") and result["status"] == "technical_complete"
    code, result, err = invoke(
        monkeypatch, capsys, "run", *args, "--resume", "--technical-manifest", manifest
    )
    assert (code, err) == (0, "") and result["reused"]
    code, result, err = invoke(monkeypatch, capsys, "run", *args, "--resume")
    assert (code, err) == (1, "") and "technical-manifest" in result["reason"]
    technical_file(tmp_path, end_ns=9)
    code, result, err = invoke(
        monkeypatch, capsys, "run", *args, "--resume", "--technical-manifest", manifest
    )
    assert (code, err) == (1, "") and "forbid resume" in result["reason"]
    assert len(runtimes) == 1


@pytest.mark.parametrize(
    "changes",
    [{"end_ns": 101}, {"frame_stride_ps": 100}, {"trajectory_id": EGOR_IDS[1]}],
)
def test_invalid_technical_cli_fails_before_runtime(
    tmp_path, monkeypatch, capsys, changes
):
    case = make_case(tmp_path, monkeypatch)
    runtimes = install_runtime(monkeypatch)
    code, result, err = invoke(
        monkeypatch,
        capsys,
        "run",
        "--catalog",
        CATALOG,
        "--trajectory-id",
        EGOR_IDS[0],
        "--output-root",
        case.output,
        "--min-free-bytes",
        1,
        "--input-binding",
        case.binding,
        "--technical-manifest",
        technical_file(tmp_path, **changes),
    )
    assert (code, err) == (1, "") and result["status"] == "blocked"
    assert not case.output.exists() and not runtimes


@pytest.mark.parametrize("role", ["canonical", "temporal", "upstream"])
def test_publication_rejects_relocated_technical_preprocessing(
    tmp_path, monkeypatch, capsys, role
):
    case = make_case(tmp_path, monkeypatch)
    install_runtime(monkeypatch)
    _, result, _ = invoke(
        monkeypatch,
        capsys,
        "run",
        "--catalog",
        CATALOG,
        "--trajectory-id",
        EGOR_IDS[0],
        "--output-root",
        case.output,
        "--min-free-bytes",
        1,
        "--input-binding",
        case.binding,
        "--technical-manifest",
        technical_file(tmp_path),
    )
    source = Path(result["output"]) / "preprocessing"
    manifest, _ = make_release_case(tmp_path / "release-source")
    shutil.copytree(source, manifest.parent / "relocated")
    payload = json.loads(manifest.read_text())
    if role == "canonical":
        payload["canonical_bindings"][0]["path"] = (
            "relocated/protein_edges_by_window_canonical.csv"
        )
    elif role == "temporal":
        payload["temporal_evidence_paths"] = ["relocated/temporal_execution.json"]
    else:
        payload["stage31_run"]["input_bindings"][0]["path"] = (
            "relocated/protein_edges_by_window_canonical.csv"
        )
    manifest.write_text(json.dumps(payload))
    output = tmp_path / "publication"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mania",
            "dataset",
            "publish",
            "--manifest",
            str(manifest),
            "--output",
            str(output),
        ],
    )
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert caught.value.code == 1
    assert (
        "Technical validation outputs cannot be production science"
        in capsys.readouterr().err
    )
    assert not output.exists()


@pytest.mark.parametrize(
    "kind", ["missing_binding", "unknown", "no_budget", "negative"]
)
def test_clear_blockers_without_writing(tmp_path, monkeypatch, capsys, kind):
    case = make_case(tmp_path, monkeypatch)
    args = [
        "run" if kind == "no_budget" else "validate",
        "--catalog",
        CATALOG,
        "--trajectory-id",
        "unknown" if kind == "unknown" else case.selected.trajectory_id,
        "--output-root",
        case.output,
    ]
    if kind == "negative":
        args += ["--min-free-bytes", -1, "--input-binding", case.binding]
    code, result, _ = invoke(monkeypatch, capsys, *args)
    assert code == 1 and result["status"] == "blocked"
    assert not case.output.exists()


def test_group_cli_dispatch_and_blocking(monkeypatch, capsys, tmp_path):
    import mania.production_run as production

    seen = []

    def assemble(catalog, group, output, **kwargs):
        seen.append((catalog, group, output, kwargs))
        return {"status": "pending_review", "science_preserved": True}

    monkeypatch.setattr(production, "assemble_production_group", assemble)
    code, result, _ = invoke(
        monkeypatch,
        capsys,
        "assemble-group",
        "--catalog",
        CATALOG,
        "--replica-group-id",
        "namd_egor_wt_0ss",
        "--output-root",
        tmp_path / "out",
        "--qc-manifest",
        tmp_path / "qc.json",
    )
    assert code == 1 and result["science_preserved"]
    assert seen[0][1] == "namd_egor_wt_0ss"
    assert seen[0][3]["qc_manifest"] == tmp_path / "qc.json"


@pytest.mark.parametrize(
    "command,option,value",
    [
        ("run", "--trajectory-id", EGOR_IDS[0]),
        ("assemble-group", "--replica-group-id", "namd_egor_wt_0ss"),
    ],
)
def test_duplicate_public_selection_rejected(command, option, value):
    with pytest.raises(SystemExit) as caught:
        cli.build_parser().parse_args(
            [
                "production",
                command,
                "--catalog",
                str(CATALOG),
                "--output-root",
                "out",
                option,
                value,
                option,
                value,
            ]
        )
    assert caught.value.code == 2
