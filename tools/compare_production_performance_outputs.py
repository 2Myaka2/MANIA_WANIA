"""Fail-closed byte and field audit of two complete production trajectory roots.

Scientific CSVs and JSON must be byte-identical. The narrowly enumerated current
run fields below may differ; digest/size differences require verified references
to files that themselves passed this audit. Reports retain every differing field.
This supplements, and does not replace, MANIA strict validation and offline replay.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

REQUIRED = {
    "request.json",
    "technical_complete.json",
    "inputs/preprocessing.json",
    *(
        "preprocessing/" + name
        for name in [
            "artifact_inventory.json",
            "temporal_execution.json",
            "run_provenance.json",
            "runtime_metadata.json",
            "pbc_audit.json",
            "perframe_completion.json",
            "contacts/contacts_perframe.csv",
            "protein_lipid_perframe.json",
            "protein_glycan_perframe.json",
            "molecular_partner_catalog.json",
            "graph/nodes.csv",
            "graph/edges.csv",
            "graph/graph.json",
            "reports/graph_diagnostics_report.json",
            *(
                f"{family}_by_window_{kind}.csv"
                for family in [
                    "protein_edges",
                    "protein_lipid_contacts",
                    "protein_glycan_contacts",
                ]
                for kind in ["source", "canonical", "canonical_annotated"]
            ),
        ]
    ),
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def differences(left, right, pointer=()):
    if type(left) is not type(right):
        yield pointer, left, right
    elif isinstance(left, dict):
        for key in sorted(left.keys() | right.keys()):
            if key not in left or key not in right:
                yield (
                    (*pointer, key),
                    {"present": key in left},
                    {"present": key in right},
                )
            else:
                yield from differences(left[key], right[key], (*pointer, key))
    elif isinstance(left, list):
        if len(left) != len(right):
            yield (*pointer, "length"), len(left), len(right)
        for index, (a, b) in enumerate(zip(left, right, strict=False)):
            yield from differences(a, b, (*pointer, index))
    elif left != right:
        yield pointer, left, right


def load(path):
    if path.suffix == ".csv":
        with path.open(newline="") as stream:
            # Include header and exact text cells; no numeric tolerances.
            return list(csv.reader(stream))
    return json.loads(path.read_text())


def classify(relative, pointer, a, b, left, right, documents, accepted):
    # Added/deleted fields and type changes are never provenance allowances.
    if type(a) is not type(b) or isinstance(a, (dict, list)):
        return None
    if relative == "preprocessing/run_provenance.json":
        if (
            isinstance(a, str)
            and isinstance(b, str)
            and pointer in [("started_at_utc",), ("ended_at_utc",), ("run_id",)]
        ):
            return "current-run timestamp/identifier"
        if pointer in [
            ("software_identity", "commit_sha"),
            ("software_identity", "working_tree_status"),
        ]:
            return "current-run software identity"
    if relative == "preprocessing/runtime_metadata.json":
        if pointer in [
            ("performance", "wall_clock_seconds"),
            ("performance", "seconds_per_sampled_frame"),
        ]:
            return "current-run performance timing"
        if len(pointer) == 2 and pointer[0] == "environment":
            return "current-run environment metadata"

    local_path = (
        relative == "inputs/preprocessing.json" and pointer == ("output_root",)
    ) or (
        relative == "preprocessing/reports/graph_diagnostics_report.json"
        and pointer
        in [
            ("edges_csv_path",),
            ("nodes_csv_path",),
            ("graph_json_path",),
            ("sections", 1, "summary", "edges_csv_path"),
            ("sections", 1, "summary", "nodes_csv_path"),
            ("sections", 1, "summary", "graph_json_path"),
        ]
    )
    if local_path and isinstance(a, str) and isinstance(b, str):
        try:
            if Path(a).relative_to(left) == Path(b).relative_to(right):
                return "same relative artifact under current-run output root"
        except ValueError:
            pass

    referenced = None
    field = None
    if relative == "technical_complete.json" and len(pointer) == 2:
        if pointer[0] == "artifacts":
            referenced, field = "preprocessing/" + pointer[1], "sha256"
    if relative == "preprocessing/artifact_inventory.json" and len(pointer) == 3:
        if pointer[0] == "artifacts" and pointer[2] in ("sha256", "byte_size"):
            index = pointer[1]
            entries = [doc["artifacts"][index] for doc in documents]
            if all(e["direction"] == "output" for e in entries):
                if entries[0]["path"] == entries[1]["path"]:
                    referenced = "preprocessing/" + entries[0]["path"]
            elif all(e["artifact_id"] == "input:manifest" for e in entries):
                referenced = "inputs/preprocessing.json"
            field = pointer[2]
    if referenced and referenced in accepted:
        files = [left / referenced, right / referenced]
        if not all(
            p.resolve().is_relative_to(root)
            for p, root in zip(files, [left, right], strict=True)
        ):
            return None
        actual = [digest(p) if field == "sha256" else p.stat().st_size for p in files]
        if actual == [a, b]:
            return f"verified {field} of independently accepted {referenced}"
    return None


def compare(left, right):
    left, right = left.resolve(), right.resolve()
    files = []
    for root in [left, right]:
        files.append(
            {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file()}
        )
    reports = {}
    pending = []
    accepted = set()
    for relative in sorted(files[0].keys() | files[1].keys() | REQUIRED):
        if relative not in files[0] or relative not in files[1]:
            reports[relative] = {"passed": False, "reason": "missing file"}
            continue
        a, b = files[0][relative], files[1][relative]
        record = {
            "left_sha256": digest(a),
            "right_sha256": digest(b),
            "left_bytes": a.stat().st_size,
            "right_bytes": b.stat().st_size,
            "differences": [],
        }
        record["byte_identical"] = record["left_sha256"] == record["right_sha256"]
        record["passed"] = record["byte_identical"]
        reports[relative] = record
        if record["passed"]:
            accepted.add(relative)
        elif a.suffix not in (".json", ".csv"):
            record["reason"] = "non-tabular bytes differ"
        else:
            documents = [load(a), load(b)]
            diff = list(differences(*documents))
            if not diff:
                record["reason"] = (
                    "serialization bytes differ without field differences"
                )
            else:
                pending.append((relative, documents, diff))
    # Dependency order is inferred from independently accepted referenced files.
    while pending:
        progress = False
        remaining = []
        for relative, documents, diff in pending:
            fields = []
            for pointer, a, b in diff:
                reason = classify(
                    relative, pointer, a, b, left, right, documents, accepted
                )
                fields.append(
                    {
                        "pointer": list(pointer),
                        "left": a,
                        "right": b,
                        "classification": reason or "UNACCEPTED",
                    }
                )
            reports[relative]["differences"] = fields
            if all(d["classification"] != "UNACCEPTED" for d in fields):
                reports[relative]["passed"] = True
                accepted.add(relative)
                progress = True
            else:
                remaining.append((relative, documents, diff))
        if not progress:
            break
        pending = remaining
    return {
        "passed": bool(reports) and all(r["passed"] for r in reports.values()),
        "left_root": str(left),
        "right_root": str(right),
        "file_count": len(reports),
        "byte_identical_count": sum(
            r.get("byte_identical", False) for r in reports.values()
        ),
        "unaccepted_field_count": sum(
            d["classification"] == "UNACCEPTED"
            for r in reports.values()
            for d in r.get("differences", [])
        ),
        "files": reports,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = compare(args.left, args.right)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "files"}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
