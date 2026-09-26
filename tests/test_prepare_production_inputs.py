"""External commands exercise the same portable synthetic preparation path."""

import json
import os
import shutil
import subprocess
import sys
import time

import pytest
from test_production_input_preparation import REPO, attestation, build_bundle, prep


@pytest.mark.parametrize("source_approval", [False, True])
def test_clean_external_prepare_confirm_validate(tmp_path, source_approval):
    bundle = build_bundle(tmp_path)
    # Copy only the two new tools. No old evidence, prepared artifacts, or helpers.
    tools = tmp_path / "standalone"
    tools.mkdir()
    for name in ("prepare_production_inputs.py", "production_input_preparation.py"):
        shutil.copyfile(REPO / "tools" / name, tools / name)
    attestation_path = tmp_path / "source_attestation.json"
    if source_approval:
        shutil.copyfile(
            REPO / "tools/production_source_attestation.py",
            tools / "production_source_attestation.py",
        )
        mapping = {}
        for row in prep.read_strict_json(
            bundle.package / "authority/source_inventory.json"
        ):
            files = dict(
                row["files"], trajectory_path=dict(path=row["expected_dcd_path"])
            )
            mapping[row["trajectory_id"]] = {
                role: dict(path=files[role]["path"], binding_path=files[role]["path"])
                for role in attestation.ROLES
            }
        attestation.save(
            attestation_path,
            source=bundle.root,
            trajectories=attestation.capture(bundle.root, mapping),
            reviewer="Synthetic reviewer",
            review_note="Synthetic sources only",
            repository_head="a" * 40,
            authority_inventory=prep.package_inventory(bundle.package),
        )
    script = tools / "prepare_production_inputs.py"
    common = [
        "--data-root",
        str(bundle.root),
        "--result-root",
        str(bundle.result),
        "--authority-package",
        str(bundle.package),
        "--trajectory-id",
        "namd_egor_wt_0ss_r1",
        "--min-free-bytes",
        "1",
    ]
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    def call(args):
        return subprocess.run(
            [sys.executable, str(script), *args],
            cwd=tools,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    prepared = call(["prepare", *common, "--workers", "1", "--threads", "1"])
    assert prepared.returncode == 0, prepared.stderr
    result = json.loads(prepared.stdout)
    assert result["status"] == "pending_review"
    args = [
        "confirm",
        *common,
        "--report-sha256",
        result["report_sha256"],
        "--production-output-root",
        str(bundle.output),
    ]
    missing = call(args)
    assert missing.returncode == 2 and "--approve" in missing.stderr
    # A separate review interval also accommodates this host's observed short
    # cross-process UTC regression. Production clock guards remain unchanged.
    time.sleep(1)
    if source_approval:
        approval = ["--source-attestation", str(attestation_path)]
        wrong = call([*args, *approval, "--reviewer", "Wrong reviewer"])
        assert wrong.returncode == 2 and "saved reviewer/note" in wrong.stderr
    else:
        approval = [
            "--approve",
            "--reviewer",
            "Synthetic reviewer",
            "--review-note",
            "Synthetic review only",
        ]
    confirmed = call([*args, *approval])
    assert confirmed.returncode == 0, confirmed.stderr
    outcome = json.loads(confirmed.stdout)
    assert outcome["status"] == "binding_materialized"
    env["MANIA_DATA_ROOT"] = str(bundle.root)
    validated = subprocess.run(
        [
            sys.executable,
            "-m",
            "mania",
            "production",
            "validate",
            "--catalog",
            str(bundle.package / "catalog/dataset.yaml"),
            "--trajectory-id",
            "namd_egor_wt_0ss_r1",
            "--output-root",
            str(bundle.output),
            "--input-binding",
            outcome["binding"],
        ],
        env=env,
        cwd=tools,
        text=True,
        capture_output=True,
        check=False,
    )
    assert validated.returncode == 0, validated.stderr
    assert json.loads(validated.stdout)["trajectory_pbc_qc_certified"] is False
    assert "production run" in outcome["commands"][1]
    failed = call(["prepare", *common, "--workers", "1", "--threads", "1"])
    assert failed.returncode == 1 and "protected" in failed.stderr
    assert not bundle.output.exists()


def test_help_requires_one_operation_only():
    result = subprocess.run(
        [sys.executable, str(REPO / "tools/prepare_production_inputs.py"), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0 and "{prepare,confirm}" in result.stdout
    assert "run-all" not in result.stdout
