"""Full offline reconstruction rejects altered authority, lineage and projection."""

import json
import shutil

import pytest
from test_dataset_qc_run import completed_qc_run
from test_dataset_qc_run import stable_software_identity as stable_software_identity

from mania.dataset_qc_run import DECISION_ROLE, DERIVED_ROLE, OUTPUT_FILES, SUMMARY_ROLE
from mania.validation.unified import validate_run_artifacts


def rewrite(path, mutate):
    data = json.loads(path.read_text())
    mutate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def refresh_sizes(output, mappings):
    def update(data):
        for entry in data["artifacts"]:
            path = (
                mappings.get(entry["artifact_id"])
                if entry["direction"] == "input"
                else output / entry["path"]
            )
            if path is not None and path.exists():
                entry["byte_size"] = path.stat().st_size

    rewrite(output / "artifact_inventory.json", update)


@pytest.mark.parametrize(
    "mutation",
    [
        "decision_reason",
        "decision_release",
        "decision_evidence",
        "reviewer",
        "note",
        "summary_count",
        "summary_reason",
        "derived_available",
        "derived_reason",
        "derived_binding",
        "derived_name",
        "derived_membership",
        "missing_decision",
        "missing_summary",
        "missing_derived",
        "omit_decision",
        "omit_summary",
        "omit_derived",
        "provenance_reference",
        "inventory_reference",
        "count",
        "ready",
        "template_excluded",
        "template_window",
        "manual_control",
        "hard_evidence",
        "review_evidence",
        "input_role",
        "input_omitted",
        "bytes_only",
    ],
)
def test_mutations_fail_even_after_size_refresh(tmp_path, mutation):
    _, qc_path, output, mappings = completed_qc_run(tmp_path)
    decision_path = output / OUTPUT_FILES[DECISION_ROLE]
    derived_path = output / OUTPUT_FILES[DERIVED_ROLE]
    summary_path = output / OUTPUT_FILES[SUMMARY_ROLE]
    if mutation in (
        "decision_reason",
        "decision_release",
        "decision_evidence",
        "reviewer",
        "note",
    ):

        def change(data):
            r = next(r for r in data["records"] if r["decision_mode"] == "manual")
            field, value = {
                "decision_reason": (
                    "decision_reason_code",
                    "BASIC_METRIC_MAD_OUTLIER_REVIEW",
                ),
                "decision_release": ("release_decision", "available"),
                "decision_evidence": ("decision_evidence_ids", ["unknown"]),
                "reviewer": ("reviewer", "Changed Reviewer"),
                "note": ("decision_note", "Changed note"),
            }[mutation]
            r[field] = value

        rewrite(decision_path, change)
    elif mutation.startswith("summary_"):
        text = summary_path.read_text()
        if mutation == "summary_reason":
            text = text.replace(
                "Synthetic reviewer assessment.", "Changed reviewer reason."
            )
        else:
            lines = text.splitlines()
            cells = lines[1].split(",")
            cells[-1] = str(int(cells[-1]) + 1)
            lines[1] = ",".join(cells)
            text = "\n".join(lines) + "\n"
        summary_path.write_text(text)
    elif mutation.startswith("derived_"):

        def change(data):
            group = next(
                g for g in data["groups"] if g["spec"]["system_id"] == "wt-norm"
            )
            if mutation == "derived_available":
                group["members"][0].update(
                    availability_status="unavailable",
                    availability_reason="Invented technical reason",
                )
            elif mutation == "derived_reason":
                group["members"][0]["availability_reason"] = "Changed reason"
            else:
                correspondence = group["lipid_correspondences"]["correspondences"][0]
                if mutation == "derived_binding":
                    correspondence["members"][0]["local_partner_id"] = (
                        "lipid_reassigned"
                    )
                elif mutation == "derived_name":
                    correspondence["partner_correspondence_id"] += "_renamed"
                else:
                    correspondence["members"] = correspondence["members"][:-1]

        rewrite(derived_path, change)
    elif mutation.startswith("missing_"):
        role = {
            "missing_decision": DECISION_ROLE,
            "missing_summary": SUMMARY_ROLE,
            "missing_derived": DERIVED_ROLE,
        }[mutation]
        (output / OUTPUT_FILES[role]).unlink()
    elif mutation.startswith("omit_") or mutation in (
        "provenance_reference",
        "inventory_reference",
    ):
        role = {
            "omit_decision": DECISION_ROLE,
            "omit_summary": SUMMARY_ROLE,
            "omit_derived": DERIVED_ROLE,
        }.get(mutation, SUMMARY_ROLE)
        if mutation != "provenance_reference":
            rewrite(
                output / "artifact_inventory.json",
                lambda d: d.update(
                    artifacts=[e for e in d["artifacts"] if e["role"] != role],
                ),
            )
        if mutation != "inventory_reference":
            rewrite(
                output / "run_provenance.json",
                lambda d: d.update(
                    artifact_references=[
                        r for r in d["artifact_references"] if r["role"] != role
                    ],
                ),
            )
    elif mutation in ("count", "ready"):
        rewrite(
            output / "run_provenance.json",
            lambda d: d["resolved_configuration"].update(
                {"replica_count": 99}
                if mutation == "count"
                else {"production_ready": False},
            ),
        )
    elif mutation.startswith("template_"):
        path = next(p for k, p in mappings.items() if "manifest_template" in k)

        def change(data):
            g = data["groups"][0]
            if mutation == "template_excluded":
                g["members"][0].update(
                    availability_status="excluded", availability_reason="anonymous"
                )
                for family in ("lipid", "glycan"):
                    for c in g[f"{family}_correspondences"]["correspondences"]:
                        c["members"] = [
                            m
                            for m in c["members"]
                            if m["replica_id"] != g["members"][0]["replica_id"]
                        ]
            else:
                for window in (
                    g["spec"]["window"],
                    *(m["window"] for m in g["members"]),
                ):
                    window["window_id"] = "altered_window"

        rewrite(path, change)
    elif mutation == "manual_control":

        def change(data):
            next(r for r in data["replicas"] if r["manual_resolution"] is not None)[
                "manual_resolution"
            ]["reviewer"] = "Changed Reviewer"

        rewrite(qc_path, change)
    elif mutation in ("hard_evidence", "review_evidence"):
        role = (
            "dataset_hard_qc_evidence"
            if mutation == "hard_evidence"
            else "dataset_review_qc_evidence"
        )
        path = next(p for k, p in mappings.items() if role in k)
        if mutation == "hard_evidence":
            rewrite(
                path, lambda d: d["raw_integrity"].update(atom_order_consistent=False)
            )
        else:
            rewrite(path, lambda d: d["rmsd_drift"].update(drift_detected=True))
    elif mutation == "input_role":
        rewrite(
            output / "artifact_inventory.json",
            lambda d: d["artifacts"][1].update(
                role="dataset_hard_qc_evidence",
            ),
        )
    elif mutation == "input_omitted":
        rewrite(
            output / "artifact_inventory.json",
            lambda d: d.update(
                artifacts=d["artifacts"][1:],
            ),
        )
    else:
        decision_path.write_bytes(decision_path.read_bytes().replace(b"\n", b"\r\n"))
    # Keep generic inventory derived counts valid to exercise reconstruction.
    rewrite(
        output / "artifact_inventory.json",
        lambda d: d.update(
            artifact_count=len(d["artifacts"]),
            input_artifact_count=sum(e["direction"] == "input" for e in d["artifacts"]),
            output_artifact_count=sum(
                e["direction"] == "output" for e in d["artifacts"]
            ),
        ),
    )
    refresh_sizes(output, mappings)
    # Ignore surplus external mappings when testing an omitted inventory input.
    declared = json.loads((output / "artifact_inventory.json").read_text())["artifacts"]
    mappings = {
        k: v for k, v in mappings.items() if k in {e["artifact_id"] for e in declared}
    }
    report = validate_run_artifacts(
        output, scope="dataset_qc", input_artifact_paths=mappings
    )
    assert report.status == "failed" and not report.complete, report.to_dict()


@pytest.mark.parametrize("role", [DECISION_ROLE, DERIVED_ROLE])
def test_sha256_mutation_fails(tmp_path, role):
    _, _, output, mappings = completed_qc_run(tmp_path, mode="sha256")
    path = output / OUTPUT_FILES[role]
    content = path.read_bytes()
    path.write_bytes(
        content.replace(b"QC exclusion", b"QC EXCLUSION", 1)
        if role == DERIVED_ROLE
        else content.replace(b"Reviewer", b"REVIEWER", 1)
    )
    report = validate_run_artifacts(
        output, scope="dataset_qc", input_artifact_paths=mappings
    )
    assert report.status == "failed" and not report.complete
    assert any(
        r.sha256_matches is False for r in report.integrity_report.artifact_records
    )


def test_pending_forbids_uninventoried_derived_file(tmp_path):
    _, _, output, mappings = completed_qc_run(tmp_path, pending=True)
    (output / OUTPUT_FILES[DERIVED_ROLE]).write_text("unexpected")
    report = validate_run_artifacts(
        output, scope="dataset_qc", input_artifact_paths=mappings
    )
    assert report.status == "failed" and not report.complete


def test_unmapped_partial_and_portable_relocation(tmp_path, monkeypatch):
    original = tmp_path / "original"
    _, _, output, mappings = completed_qc_run(original)
    report = validate_run_artifacts(output, scope="dataset_qc")
    assert report.status == "partial" and not report.complete
    relocated = tmp_path / "relocated"
    shutil.copytree(original, relocated)
    mapped = {k: relocated / p.relative_to(original) for k, p in mappings.items()}
    shutil.rmtree(original)
    monkeypatch.chdir(tmp_path.parent)
    report = validate_run_artifacts(
        relocated / "qc", scope="dataset_qc", input_artifact_paths=mapped
    )
    assert report.status == "passed" and report.complete, report.to_dict()
