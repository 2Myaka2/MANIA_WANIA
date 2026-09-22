#!/usr/bin/env python3
"""Exact B.3 derivative binding and explicit, source-reviewed NAMD partners.

This standalone pilot never changes production formulas or prepares coordinates.
The reviewed source compositions below apply ONLY to the pinned replica-1 PSF.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import shutil
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import numpy as np

_spec = importlib.util.spec_from_file_location(
    "stage34b4_accepted_b3", Path(__file__).with_name("stage34b_namd_real_pilot.py")
)
b3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b3)
# Reuse general topology traversal and independent arithmetic, never its catalog,
# GROMACS classifier, coordinate preparation, or execution entry point.
shared = b3.helper("stage34a_specialized_normal_pilot")
require, dump, file_record = b3.require, b3.dump, b3.file_record
B3_DIRECTORY = "stage34b_namd_real_20260922T163031Z_d5711581c4494dc58936d4b91a334ebd"
B3_CHECKPOINT = "b05f88b4c03c4cb82d45cfc4fe4c02dec74827ed"
PREPARED_SHA256 = "3f9ac9353ad0a6c551845d166651a0ade0436ee5b815c297ff45f9dfa3d0b28c"
# Exact supplied source descriptions, not a universal residue allow-list.
REVIEWED_DEFINITIONS = {
    "CHL1": ("toppar_all36_lipid_cholesterol.str", "cholesterol"),
    "POPC": ("top_all36_lipid.rtf", "Phosphatidylcholine"),
    "PLPC": ("toppar_all36_lipid_miscellaneous.str", "Phosphatidylcholine"),
    "SSM": ("toppar_all36_lipid_sphingo.str", "sphingomyelin"),
    "NSM": ("toppar_all36_lipid_sphingo.str", "sphingomyelin"),
    "POPE": ("top_all36_lipid.rtf", "Phosphatidylethanolamine"),
    "PAPE": ("toppar_all36_lipid_miscellaneous.str", "Phosphatidylethanolamine"),
    "POPI": ("toppar_all36_lipid_inositol.str", "inositol"),
    "PAPS": ("toppar_all36_lipid_miscellaneous.str", "Phosphatidylserine"),
    "POPA": ("top_all36_lipid.rtf", "Phosphatidic acid"),
    "CER160": ("toppar_all36_lipid_sphingo.str", "CERAMIDE"),
    "BGLC": ("top_all36_carb.rtf", "beta-D-glucose"),
    "TIP3": ("toppar_water_ions.str", "water"),
    "SOD": ("toppar_water_ions.str", "sodium"),
    "CLA": ("toppar_water_ions.str", "chloride"),
}
LIMITATIONS = (
    "Stage 34.B.4: one real NAMD replica; source frames 0..4 only, 100..500 ps.\n"
    "Accepted B.3 protein science and Variant C preparation are reused unchanged.\n"
    "scientific_pbc_status=unresolved; MANIA internal MIC=false.\n"
    "No PBC transformation, source DCD coordinate read, or full DCD checksum.\n"
    "Partner IDs are topology-local; no cross-replica identity is assigned.\n"
    "Dataset condition remains null. No Dataset release or biological interpretation.\n"
    "Raw inputs and prepared trajectory bytes are excluded from the evidence ZIP.\n"
)


def checkpoint(repo, work):
    commands = [
        ["git", "branch", "--show-current"],
        ["git", "rev-parse", "HEAD"],
        ["git", "status", "--short"],
        ["git", "rev-parse", "develop"],
        ["git", "merge-base", "--is-ancestor", "develop", "HEAD"],
        ["git", "merge-base", "--is-ancestor", B3_CHECKPOINT, "HEAD"],
        ["git", "log", "--oneline", "--decorate", "-40"],
    ]
    outputs = []
    for argv in commands:
        result = subprocess.run(argv, cwd=repo, capture_output=True, text=True)
        b3.record_command(
            work,
            argv,
            exit_code=result.returncode,
            output=result.stdout + result.stderr,
        )
        require(result.returncode == 0, "Required repository ancestor/check failed")
        outputs.append(result.stdout)
    require(outputs[0].strip() == "FAIR", "Required branch FAIR")
    for name in (
        "tools/stage34b_namd_real_pilot.py",
        "tests/test_stage34b_namd_real_pilot.py",
        "docs/stage34b_namd_authority.md",
    ):
        subprocess.run(["git", "cat-file", "-e", f"HEAD:{name}"], cwd=repo, check=True)
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", name],
            cwd=repo,
            capture_output=True,
            check=True,
        )
    (work / "git_state.txt").write_text("\n".join(outputs))
    return outputs[1].strip()


def validate_frame_records(records):
    require(len(records) == 5, "Prepared evidence must have exactly five frames")
    for actual, expected in zip(records, b3.frame_map(), strict=True):
        require(
            all(actual.get(k) == v for k, v in expected.items()),
            "Accepted prepared frame map changed",
        )
        require(
            actual.get("passed") is True and all(actual["checks"].values()),
            "Accepted prepared identity did not pass",
        )


def bind_accepted(root, work):
    accepted = root / B3_DIRECTORY
    prepared = accepted / "prepared_variant_c.xtc"
    record = b3.require_hash(prepared, PREPARED_SHA256, "accepted prepared XTC")
    historical = {}
    for name in (*b3.REQUIRED_EVIDENCE, "stage34b_real_pilot_summary", "pbc_audit"):
        path = accepted / f"{name}.json"
        historical[name] = json.loads(path.read_text())
    summary = historical["stage34b_real_pilot_summary"]
    require(
        summary["stage34b3_status"] == "PASS"
        and summary["repository_verification"] == "PASS",
        "B.3 not accepted",
    )
    require(
        summary["scientific_pbc_status"] == "unresolved"
        and summary["internal_mic"] is False,
        "B.3 PBC status changed",
    )
    identity = historical["prepared_trajectory_identity"]
    require(all(identity[k] == record[k] for k in record), "Prepared binding changed")
    validate_frame_records(identity["frames"])
    for name in ("variant_c_pbc_diagnostic", "persisted_pbc_validation"):
        b3.require_representation(historical[name]["frames"])
    values = b3.validate_authorities(root, work)
    u, psf, _, lookup, _, mapping_path, mapping, features = values
    original_binding = historical["accepted_authority_bindings"]
    new_binding = json.loads((work / "accepted_authority_bindings.json").read_text())
    require(new_binding == original_binding, "Accepted B.3 authority binding changed")
    source = historical["source_input_observations"]
    require(features == source["topology_features"], "Accepted carrier/bond changed")
    before = {
        k: getattr(u.atoms, k).copy()
        for k in (
            "indices",
            "ids",
            "names",
            "resindices",
            "resids",
            "resnames",
            "segindices",
            "segids",
        )
    }
    u.load_new(str(prepared))
    require(len(u.trajectory) == 5, "Prepared derivative must have exactly five frames")
    frames = []
    for i in b3.FRAMES:
        ts = u.trajectory[i]
        expected = historical["selected_frames"]["frames"][i]
        require(float(ts.time) == b3.TIMES_PS[i], "Prepared scientific time changed")
        require(np.isfinite(ts.positions).all(), "Invalid prepared coordinates")
        require(
            np.allclose(ts.dimensions, expected["box"], rtol=0, atol=2e-5),
            "Prepared box changed",
        )
        require(
            all(np.array_equal(v, getattr(u.atoms, k)) for k, v in before.items()),
            "Prepared atom/residue/segment identity changed",
        )
        frames.append(
            {
                **b3.frame_map()[i],
                "box": ts.dimensions.tolist(),
                "identity_passed": True,
            }
        )
    from mania.preprocessing.physical_time_execution_io import (
        read_preprocessing_temporal_execution,
    )

    temporal_path = accepted / "output/temporal_execution.json"
    temporal = read_preprocessing_temporal_execution(temporal_path)
    require(len(temporal.bindings) == 1, "Expected one accepted temporal binding")
    binding = temporal.bindings[0]
    _, samples, windows = b3.sampling_contract()
    require(
        binding.sampling_plan == samples and binding.window_plan == windows,
        "Accepted B.3 physical-time plans changed",
    )
    evidence = {
        "status": "PASS",
        "prepared": record,
        "authorities": new_binding,
        "frames": frames,
        "topology_identity_fields": list(before),
        "topology_features": features,
        "scientific_pbc_status": "unresolved",
        "internal_mic": False,
        "source_dcd_coordinate_reads": 0,
        "preparation_recomputed": False,
        "protein_science_recomputed": False,
        "historical_evidence": [
            file_record(accepted / f"{n}.json") for n in historical
        ],
        "temporal": file_record(temporal_path),
        "mapping": file_record(mapping_path),
    }
    dump(work / "accepted_b3_bindings.json", evidence)
    shutil.copyfile(temporal_path, work / "temporal_execution.json")
    return u, psf, lookup, mapping, temporal


def source_blocks(path, keyword, name):
    """Read exact source declarations; names locate evidence, never assign elements."""
    blocks, current = [], None
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        tokens = line.split("!", 1)[0].split()
        if tokens and tokens[0].upper() in ("RESI", "PRES", "END"):
            current = None
            if len(tokens) > 1 and tokens[0].upper() == keyword and tokens[1] == name:
                current = {
                    "source": file_record(path),
                    "line": line_no,
                    "declaration": line,
                    "atoms": {},
                    "delete": [],
                    "bonds": [],
                    "lines": [],
                }
                blocks.append(current)
        if current is None:
            continue
        current["lines"].append(line)
        if not tokens:
            continue
        key = tokens[0].upper()
        if key == "ATOM":
            current["atoms"][tokens[1]] = tokens[2]
        elif key == "DELE" and len(tokens) > 2 and tokens[1].upper() == "ATOM":
            current["delete"].append(tokens[2])
        elif key in ("BOND", "DOUBLE"):
            current["bonds"].extend(
                [tokens[i : i + 2] for i in range(1, len(tokens), 2)]
            )
    require(blocks, f"Missing source declaration: {keyword} {name}")
    return blocks


def load_classification_sources(toppar):
    definitions = {}
    for name, (filename, description) in REVIEWED_DEFINITIONS.items():
        blocks = source_blocks(toppar / filename, "RESI", name)
        require(
            any(description.lower() in "\n".join(b["lines"]).lower() for b in blocks),
            f"Source description not confirmed: {name}",
        )
        definitions[name] = blocks
    patch = source_blocks(toppar / "toppar_all36_carb_glycolipid.str", "PRES", "CERB")
    require(
        len(patch) == 1 and ["1O1", "2C1S"] in patch[0]["bonds"],
        "Missing exact ceramide/sugar linkage source",
    )
    definitions["CERB"] = patch
    return definitions


def classify_component(residues, inter_residue_bonds, definitions):
    """Exact atom/type membership plus source review and connectivity, PSF-bound."""
    composition = Counter(r["resname"] for r in residues)
    if len(residues) == 1:
        r = residues[0]
        name = r["resname"]
        if name not in definitions or name in ("BGLC", "CER160", "CERB"):
            raise ValueError(f"Unreviewed complete composition: {dict(composition)}")
        matches = [b for b in definitions[name] if b["atoms"] == r["atom_types"]]
        require(matches, f"Source atom/type membership mismatch: {name}")
        kind = "non_partner" if name in ("TIP3", "SOD", "CLA") else "lipid"
        return kind, name, [f"{name}:{b['line']}" for b in matches]
    require(
        composition == {"BGLC": 1, "CER160": 1},
        f"Unreviewed multi-residue composition: {dict(composition)}",
    )
    patch = definitions["CERB"][0]
    for prefix, name in (("1", "BGLC"), ("2", "CER160")):
        residue = next(r for r in residues if r["resname"] == name)
        expected = dict(definitions[name][0]["atoms"])
        for key in patch["delete"]:
            if key.startswith(prefix):
                expected.pop(key[1:])
        expected.update(
            {k[1:]: v for k, v in patch["atoms"].items() if k.startswith(prefix)}
        )
        require(expected == residue["atom_types"], f"CERB patched membership: {name}")
    require(
        inter_residue_bonds == [(("BGLC", "O1"), ("CER160", "C1S"))],
        "CERB inter-residue linkage differs",
    )
    return "lipid", "BGLC:1+CER160:1", ["BGLC", "CER160", "CERB"]


def inventory(u, psf, work):
    # Enforce the review's exact topology scope even for a direct function caller.
    b3.require_hash(psf, b3.PSF_SHA256, "classification PSF")
    definitions = load_classification_sources(psf.parent / "toppar")
    dump(
        work / "partner_classification_evidence.json",
        {
            "psf": file_record(psf),
            "authority": "User/Egor PMm system metadata; exact supplied CHARMM "
            "residue definitions and CERB patch; PSF connectivity",
            "scope": "Only the pinned NAMD WT 2SS replica-1 PSF, not a production list",
            "definitions": definitions,
            "glycan_authority": {"Asn295": "FA2G2S2", "Asn308": "FA2G2S2"},
        },
    )
    context = b3.pbc.topology_context(u)
    heavy = context["heavy"]
    require(heavy is not None, "Authoritative elements required")
    glycans = shared.glycan_components(u, context, heavy)
    dump(work / "glycan_anchor_metadata.json", glycans)
    partners = list(glycans)
    nonpartners, unresolved = [], []
    bonds = context["bonds"]
    cross = bonds[u.atoms.resindices[bonds[:, 0]] != u.atoms.resindices[bonds[:, 1]]]
    cross_by_component = defaultdict(list)
    for a, b in cross:
        pair = sorted(
            (
                (str(u.atoms[a].resname), str(u.atoms[a].name)),
                (str(u.atoms[b].resname), str(u.atoms[b].name)),
            )
        )
        cross_by_component[int(context["components"][a])].append(tuple(pair))
    for fragment in u.atoms.fragments:
        indexes = fragment.indices
        if context["protein_connected"][indexes].any():
            continue
        component_id = int(context["components"][indexes[0]])
        records = []
        for r in fragment.residues:
            require(len(set(r.atoms.names)) == len(r.atoms), "Duplicate atom names")
            records.append(
                {
                    **shared.residue_record(r),
                    "atom_types": dict(zip(r.atoms.names, r.atoms.types, strict=True)),
                }
            )
        try:
            kind, name, sources = classify_component(
                records, sorted(cross_by_component[component_id]), definitions
            )
        except ValueError as exc:
            record = shared.component_record(u, indexes, component_id, heavy)
            unresolved.append(
                {**record, "classification": "unresolved", "reason": str(exc)}
            )
            continue
        if kind == "non_partner":
            nonpartners.append(
                {
                    "component_id": component_id,
                    "name": name,
                    "residue_indexes": fragment.residues.ix.tolist(),
                    "atom_indexes": indexes.tolist(),
                    "sources": sources,
                }
            )
            continue
        record = shared.component_record(u, indexes, component_id, heavy)
        require(
            set(indexes) == set(fragment.residues.atoms.indices),
            "Incomplete partner residue membership",
        )
        record.update(
            partner_id=f"namd_membrane_{component_id:06d}",
            partner_kind=kind,
            partner_name=name,
            classification_evidence=sources,
            inter_residue_bonds=cross_by_component[component_id],
        )
        partners.append(record)
    for p in partners:
        indexes = np.asarray(p["atom_indexes"], dtype=int)
        p["heavy_atom_indexes"] = indexes[heavy[indexes]].tolist()
        p["connectivity_evidence"] = (
            "Complete PSF connected component; glycans traversed after removal "
            "of their exact protein carrier bond"
        )
    result = {
        "status": "BLOCKED" if unresolved else "PASS",
        "partners": partners,
        "nonpartners": nonpartners,
        "unresolved": unresolved,
        "counts": {
            "membrane": sum(p["partner_kind"] == "lipid" for p in partners),
            "glycan": len(glycans),
            "nonpartner": len(nonpartners),
            "unresolved": len(unresolved),
        },
        "membrane_compositions": dict(
            sorted(
                Counter(
                    p["composition_label"]
                    for p in partners
                    if p["partner_kind"] == "lipid"
                ).items()
            )
        ),
        "nonpartner_compositions": dict(
            sorted(Counter(p["name"] for p in nonpartners).items())
        ),
    }
    dump(work / "namd_partner_inventory.json", result)
    require(
        not unresolved, f"Ambiguous components: {len(unresolved)}; contacts stopped"
    )
    catalog = shared.build_metadata(
        u, partners, work / "molecular_partner_metadata.json"
    )
    require(catalog.glycan_partner_count == 2, "Exactly two FA2G2S2 glycans required")
    return partners, catalog, result


def execute_science(u, temporal, work):
    from mania.preprocessing.molecular_partner_metadata_io import (
        read_molecular_partner_metadata,
    )
    from mania.preprocessing.specialized_contact_execution import (
        PreprocessingSpecializedContactExecution,
        build_specialized_contact_source_tables,
        execute_specialized_contact_condition,
    )

    metadata = read_molecular_partner_metadata(work / "molecular_partner_metadata.json")
    result = execute_specialized_contact_condition(u, temporal.bindings[0], metadata)
    execution = PreprocessingSpecializedContactExecution((result,))
    dump(work / "specialised_production_frames.json", execution.to_dict())
    tables = build_specialized_contact_source_tables(execution, temporal)
    return execution, tables


def export_validate(execution, tables, mapping, temporal, work):
    from mania import canonical_window_tables as canonical
    from mania import canonical_window_tables_io as canonical_io
    from mania.preprocessing import specialized_contact_window_tables_io as source_io
    from mania.preprocessing.molecular_partner_catalog_io import (
        cross_check_specialized_source_tables,
        read_molecular_partner_catalog,
        validate_molecular_partner_catalog,
        write_molecular_partner_catalog,
    )

    identity = temporal.bindings[0].dataset_spec.identity
    bindings = canonical.DatasetCanonicalResidueMappingBindings(
        (
            canonical.DatasetCanonicalResidueMappingBinding(
                identity.dataset_id,
                identity.system_id,
                identity.trajectory_id,
                identity.replica_id,
                mapping,
            ),
        )
    )
    output = work / "output"
    output.mkdir()
    catalog = execution.catalog()
    require(
        write_molecular_partner_catalog(catalog, work).passed, "Catalog write failed"
    )
    require(
        read_molecular_partner_catalog(work / "molecular_partner_catalog.json")
        == catalog,
        "Catalog roundtrip differs",
    )
    cross_check_specialized_source_tables(
        catalog, temporal, *tables, (temporal.bindings[0].execution_condition,)
    )
    reports = []
    report = validate_molecular_partner_catalog(work / "molecular_partner_catalog.json")
    require(report.passed, "Catalog validation failed")
    reports.append({"validator": "molecular_partner_catalog", "passed": True})
    comparisons = {}
    for kind, table in zip(("lipid", "glycan"), tables, strict=True):
        write = getattr(source_io, f"write_protein_{kind}_window_csv")(table, output)
        require(write.passed, "Source CSV write failed")
        source_path = output / f"protein_{kind}_contacts_by_window_source.csv"
        source_read = getattr(source_io, f"read_protein_{kind}_window_csv")(source_path)
        require(source_read == table, "Source CSV roundtrip differs")
        canonical_table = getattr(
            canonical, f"build_canonical_protein_{kind}_window_table"
        )(table, mapping_bindings=bindings)
        write = getattr(canonical_io, f"write_canonical_protein_{kind}_window_csv")(
            canonical_table, output
        )
        require(write.passed, "Canonical CSV write failed")
        canonical_path = output / f"protein_{kind}_contacts_by_window_canonical.csv"
        canonical_read = getattr(
            canonical_io, f"read_canonical_protein_{kind}_window_csv"
        )(canonical_path)
        require(canonical_read == canonical_table, "Canonical CSV roundtrip differs")
        for label, path, module, function in (
            ("source", source_path, source_io, f"validate_protein_{kind}_window_csv"),
            (
                "canonical",
                canonical_path,
                canonical_io,
                f"validate_canonical_protein_{kind}_window_csv",
            ),
        ):
            report = getattr(module, function)(path)
            require(report.passed, f"{kind} {label} validator failed")
            reports.append(
                {
                    "validator": f"{kind}_{label}",
                    "passed": True,
                    "artifact": file_record(path),
                }
            )
        with source_path.open() as stream:
            source_rows = list(csv.DictReader(stream))
        with canonical_path.open() as stream:
            canonical_rows = list(csv.DictReader(stream))
        differences = shared.compare_canonical(
            source_rows, canonical_rows, kind, mapping
        )
        comparisons[kind] = {
            "source_rows": len(source_rows),
            "canonical_rows": len(canonical_rows),
            "scientific_value_mismatches": len(differences),
            "differences": differences,
        }
    dump(work / "canonical_specialised_check.json", comparisons)
    require(
        all(not c["differences"] for c in comparisons.values()),
        "Canonical specialized science changed",
    )
    reports.extend(
        [
            {"validator": "catalog_temporal_source_cross_check", "passed": True},
            {"validator": "exact_source_canonical_equality", "passed": True},
            {"validator": "accepted_temporal_strict_read_and_binding", "passed": True},
            {"validator": "explicit_partner_metadata_strict_roundtrip", "passed": True},
        ]
    )
    report = {
        "status": "passed",
        "complete": True,
        "error_count": 0,
        "warning_count": 0,
        "unsupported_count": 0,
        "scope": "All applicable standalone Stage 29/30 artifact validators; "
        "no new preprocessing run/provenance or release validation claimed",
        "checks": reports,
    }
    dump(work / "technical_validation.json", report)
    return comparisons, report


def independent_observations(u, partners):
    heavy = np.asarray(u.atoms.elements) != "H"
    protein = [
        (int(r.ix), r.atoms.indices[heavy[r.atoms.indices]])
        for r in u.select_atoms("protein").residues
    ]
    observations = []
    for frame_index in b3.FRAMES:
        ts = u.trajectory[frame_index]
        require(float(ts.time) == b3.TIMES_PS[frame_index], "Independent time mismatch")
        coords = u.atoms.positions.astype(np.float64)
        for residue_index, indexes in protein:
            for partner in partners:
                distance = shared.minimum_distance(
                    coords[indexes], coords[partner["heavy_atom_indexes"]]
                )
                kind = partner["partner_kind"]
                if distance <= (6.0 if kind == "lipid" else 4.5):
                    observations.append(
                        {
                            "prepared_frame_index": frame_index,
                            "authoritative_time_ps": b3.TIMES_PS[frame_index],
                            "protein_residue_index": residue_index,
                            "partner_kind": kind,
                            "partner_id": partner["partner_id"],
                            "minimum_distance_A": distance,
                            "standard_summary_excluded": kind == "glycan"
                            and residue_index
                            == partner["carrier_residue"]["residue_index"],
                        }
                    )
        print(
            f"Independent frame {frame_index}: all residue/partner pairs checked",
            flush=True,
        )
    return observations


def compare_independent(observations, result, tables):
    expected = {
        (
            r["partner_kind"],
            r["prepared_frame_index"],
            r["protein_residue_index"],
            r["partner_id"],
        ): r
        for r in observations
    }
    require(len(expected) == len(observations), "Duplicate independent observation")
    actual = {}
    for kind in ("lipid", "glycan"):
        frames = getattr(result, f"{kind}_frame_results")
        require(
            tuple(f.frame_index for f in frames) == b3.FRAMES,
            "Production frame population changed",
        )
        for frame in frames:
            require(
                frame.time_ps == b3.TIMES_PS[frame.frame_index],
                "Production time mismatch",
            )
            for contact in frame.contacts:
                c = contact.to_dict()
                key = (
                    kind,
                    frame.frame_index,
                    c["protein_residue_index"],
                    c[f"{kind}_partner_id"],
                )
                require(key not in actual, "Duplicate production observation")
                actual[key] = c
    report = {
        "missing_positives": len(expected.keys() - actual.keys()),
        "extra_positives": len(actual.keys() - expected.keys()),
        "geometry_mismatches": 0,
        "anchor_exclusion_mismatches": 0,
        "missing_window_rows": 0,
        "extra_window_rows": 0,
        **{f"{m}_mismatches": 0 for m in shared.METRICS},
        "max_geometry_delta_A": 0.0,
    }
    for key in expected.keys() & actual.keys():
        a, b = expected[key], actual[key]
        delta = abs(a["minimum_distance_A"] - b["minimum_distance_A"])
        report["max_geometry_delta_A"] = max(report["max_geometry_delta_A"], delta)
        report["geometry_mismatches"] += delta > 1e-12
        report["anchor_exclusion_mismatches"] += a[
            "standard_summary_excluded"
        ] != b.get("standard_summary_excluded", False)
    summaries = shared.aggregate_observations(observations, times=b3.TIMES_PS)
    for kind, table in zip(("lipid", "glycan"), tables, strict=True):
        actual_rows = {
            (kind, r.protein_residue_index, getattr(r, f"{kind}_partner_id")): r
            for r in table.rows
        }
        expected_rows = {k: v for k, v in summaries.items() if k[0] == kind}
        require(len(actual_rows) == len(table.rows), "Duplicate source window row")
        report["missing_window_rows"] += len(expected_rows.keys() - actual_rows.keys())
        report["extra_window_rows"] += len(actual_rows.keys() - expected_rows.keys())
        for key in expected_rows.keys() & actual_rows.keys():
            row = actual_rows[key]
            require(row.resolved_frame_count == 5, "Wrong window denominator")
            for metric in shared.METRICS:
                left, right = expected_rows[key][metric], getattr(row, metric)
                same = (
                    left == right
                    if metric.startswith("n_")
                    else math.isclose(left, right, abs_tol=1e-12, rel_tol=0)
                )
                report[f"{metric}_mismatches"] += not same
    report["status"] = (
        "PASS"
        if not any(v for k, v in report.items() if k != "max_geometry_delta_A")
        else "FAIL"
    )
    report["comparison"] = (
        "Exact identities/integers; float64 direct distances and metrics "
        "abs_tol=1e-12, rel_tol=0; no tolerance in cutoff membership"
    )
    return report


def run(root, work):
    started = time.perf_counter()
    summary = {
        "stage34b4_status": "BLOCKED",
        "stage34b5_status": "NOT RUN",
        "stage34c_prep_status": "NOT RUN",
        "scientific_pbc_status": "unresolved",
        "internal_mic": False,
        "new_specialized_science_executed": False,
        "reused_protein_observations": 27841,
        "reused_protein_window_rows": 6514,
        "production_code_changes": [],
        "repository_verification": "pending",
    }
    timings = {}
    u = None
    phase = "accepted_binding"
    try:
        summary["starting_head"] = checkpoint(Path(__file__).resolve().parents[1], work)
        u, psf, _, mapping, temporal = bind_accepted(root, work)
        timings["accepted_binding_seconds"] = time.perf_counter() - started
        print("Accepted B.3 binding PASS; no source DCD coordinates read", flush=True)
        phase = "partner_catalog"
        start = time.perf_counter()
        partners, catalog, inventory_result = inventory(u, psf, work)
        timings["partner_catalog_seconds"] = time.perf_counter() - start
        summary["inventory"] = {
            k: v
            for k, v in inventory_result.items()
            if k not in ("partners", "nonpartners", "unresolved")
        }
        dump(
            work / "partner_catalog_gate.json",
            {"status": "PASS", "partner_count": catalog.partner_count},
        )
        print(f"Explicit catalog PASS: {catalog.partner_count} partners", flush=True)
        phase = "production_specialized_science"
        start = time.perf_counter()
        summary["new_specialized_science_executed"] = True
        execution, tables = execute_science(u, temporal, work)
        timings["production_specialized_seconds"] = time.perf_counter() - start
        print("Production Stage 29 geometry and windows complete", flush=True)
        phase = "canonicalization_validation"
        start = time.perf_counter()
        canonical, technical = export_validate(
            execution, tables, mapping, temporal, work
        )
        timings["canonicalization_validation_seconds"] = time.perf_counter() - start
        phase = "independent_verification"
        start = time.perf_counter()
        observations = independent_observations(u, partners)
        shared.write_csv(work / "specialised_per_frame_independent.csv", observations)
        report = compare_independent(
            observations, execution.condition_results[0], tables
        )
        dump(work / "specialised_window_independent_check.json", report)
        timings["independent_verification_seconds"] = time.perf_counter() - start
        require(report["status"] == "PASS", "Independent specialized mismatch")
        counts = {
            "membrane_partners": catalog.lipid_partner_count,
            "glycan_partners": catalog.glycan_partner_count,
            "membrane_partners_with_contacts": len(
                {r["partner_id"] for r in observations if r["partner_kind"] == "lipid"}
            ),
            "lipid_raw_positives": sum(
                r["partner_kind"] == "lipid" for r in observations
            ),
            "glycan_raw_positives": sum(
                r["partner_kind"] == "glycan" for r in observations
            ),
            "anchor_observations_excluded": sum(
                r["standard_summary_excluded"] for r in observations
            ),
        }
        counts["ordinary_glycan_positives"] = (
            counts["glycan_raw_positives"] - counts["anchor_observations_excluded"]
        )
        summary.update(
            stage34b4_status="PASS",
            counts=counts,
            canonical=canonical,
            independent=report,
            technical=technical,
        )
    except Exception as exc:
        summary.update(
            stage34b4_status="BLOCKED"
            if phase in ("accepted_binding", "partner_catalog")
            else "FAIL",
            blocker_phase=phase,
            blocker=str(exc),
        )
        (work / "failure_traceback.txt").write_text(traceback.format_exc())
    finally:
        if u is not None and hasattr(u, "trajectory"):
            u.trajectory.close()
        timings["total_b4_seconds"] = time.perf_counter() - started
        dump(work / "timings.json", timings)
        summary["timings"] = timings
        dump(work / "stage34b4_summary.json", summary)
        (work / "warnings_limitations.txt").write_text(LIMITATIONS)
        for name in (
            "accepted_b3_bindings",
            "namd_partner_inventory",
            "molecular_partner_catalog",
            "partner_classification_evidence",
            "glycan_anchor_metadata",
            "specialised_per_frame_independent",
            "specialised_window_independent_check",
            "canonical_specialised_check",
            "technical_validation",
        ):
            path = work / f"{name}.json"
            if not path.exists() and not (work / f"{name}.csv").exists():
                dump(
                    path, {"status": "NOT RUN", "reason": summary.get("blocker", phase)}
                )
        if summary["stage34b4_status"] != "PASS":
            dump(
                work / "downstream_not_run.json",
                {
                    "B.5": "NOT RUN",
                    "C-prep": "NOT RUN",
                    "reason": "B.4 did not completely pass",
                    "stage31_32_33_executed": False,
                },
            )
        b3.package(work)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-root", type=Path, default=Path("local_md"))
    parser.add_argument("--evidence-directory", type=Path)
    args = parser.parse_args(argv)
    root = args.local_root.resolve()
    work = args.evidence_directory or root / (
        f"stage34b4_namd_specialized_{datetime.now(UTC):%Y%m%dT%H%M%SZ}_{uuid4().hex}"
    )
    work.mkdir(parents=True, exist_ok=False)
    dump(work / "commands.json", [])
    summary = run(root, work)
    print(json.dumps({"evidence_directory": str(work), "summary": summary}, indent=2))
    return 0 if summary["stage34b4_status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
