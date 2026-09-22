"""Mapping-only regressions; synthetic topologies, no trajectories or real data."""

import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("MDAnalysis", reason="optional scientific dependency")

from mania.canonical_reference_io import load_default_napi2b_canonical_reference
from mania.canonical_residue_mapping import CanonicalResidueMappingTable
from mania.canonical_residue_mapping_io import (
    read_canonical_residue_mapping,
    write_canonical_residue_mapping,
)

SCRIPT = (
    Path(__file__).resolve().parents[1] / "tools/stage34b_namd_mapping_authority.py"
)
spec = importlib.util.spec_from_file_location("stage34b_mapping", SCRIPT)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


@pytest.fixture
def reference():
    return load_default_napi2b_canonical_reference()


@pytest.fixture
def rows(reference):
    # Noncanonical numbering is intentional, including noninteger source IDs.
    return [
        dict(
            zip(
                helper.IDENTITY_FIELDS,
                (
                    "PROA",
                    f"offset:{1000 + i}",
                    r.canonical_resname,
                    i * 2,
                    i + 1,
                ),
                strict=True,
            )
        )
        for i, r in enumerate(reference.residues())
    ]


def write_mapping(tmp_path, rows, reference):
    table = helper.build_mapping(rows, reference)
    path = tmp_path / "mapping.json"
    assert write_canonical_residue_mapping(table, path).passed
    return path, table


def test_full_length_exact_offset_mapping_is_deterministic(tmp_path, rows, reference):
    path, table = write_mapping(tmp_path, rows, reference)
    assert helper.build_mapping(rows, reference) == table
    assert (
        helper.verify_records(read_canonical_residue_mapping(path), rows, reference)[
            "canonical_coverage"
        ]
        == 690
    )
    assert all(r.source_resid.startswith("offset:") for r in table.mappings)
    assert {r.canonical_residue_number for r in table.mappings} == set(range(1, 691))


def test_numeric_resid_equality_cannot_authorize_wrong_sequence(rows, reference):
    for i, row in enumerate(rows, 1):
        row["source_resid"] = str(i)
    rows[0]["source_resname"], rows[1]["source_resname"] = (
        rows[1]["source_resname"],
        rows[0]["source_resname"],
    )
    with pytest.raises(ValueError, match="sequence mismatch"):
        helper.build_mapping(rows, reference)


@pytest.mark.parametrize("name", ["HSD", "HSE", "HSP"])
def test_histidine_identity_normalization_preserves_source(
    tmp_path, rows, reference, name
):
    for row in rows:
        if row["source_resname"] == "HIS":
            row["source_resname"] = name
    path, _ = write_mapping(tmp_path, rows, reference)
    persisted = read_canonical_residue_mapping(path)
    histidines = [r for r in persisted.mappings if r.canonical_resname == "HIS"]
    assert histidines and all(r.source_resname == name for r in histidines)
    assert helper.sequence_identity(rows, reference)[1]["status"] == "PASS"


@pytest.mark.parametrize(
    "change,message",
    [
        ("missing", "Missing source residue"),
        ("duplicate", "Duplicated source residue identity"),
        ("unknown", "Unresolved source amino-acid"),
        ("mismatch", "sequence mismatch"),
        ("insertion", "insertion/deletion"),
        ("order", "topology indexes"),
    ],
)
def test_invalid_source_fails(rows, reference, change, message):
    if change == "missing":
        rows.pop()
    elif change == "duplicate":
        rows[-1] = rows[0].copy()
    elif change == "unknown":
        rows[0]["source_resname"] = "UNK"
    elif change == "mismatch":
        rows[0]["source_resname"] = "ALA"
    elif change == "insertion":
        rows.append(
            {
                **rows[-1],
                "source_resid": "EXTRA",
                "source_topology_residue_index": 2000,
                "source_sequence_position": len(rows) + 1,
            }
        )
    else:
        rows[0]["source_topology_residue_index"] = 99
    with pytest.raises(ValueError, match=message):
        helper.build_mapping(rows, reference)


def test_wrong_reference_identity_rejected(rows, reference):
    # A forged dataclass must not bypass the standalone control's reference check.
    object.__setattr__(reference, "canonical_isoform_id", "O95436-2")
    with pytest.raises(ValueError, match="Wrong canonical reference"):
        helper.build_mapping(rows, reference)


@pytest.mark.parametrize(
    "change", ["missing", "duplicate_target", "wrong_reference", "source_name"]
)
def test_persisted_record_corruption_fails(tmp_path, rows, reference, change):
    path, _ = write_mapping(tmp_path, rows, reference)
    data = json.loads(path.read_text())
    if change == "missing":
        data["mappings"].pop()
        data["mapping_count"] -= 1
    elif change == "duplicate_target":
        for key in ("canonical_residue_number", "canonical_resname"):
            data["mappings"][1][key] = data["mappings"][0][key]
    elif change == "wrong_reference":
        data["canonical_reference_id"] = "uniprotkb:O95436-2:sequence-v3"
    else:
        data["mappings"][0]["source_resname"] = "ALA"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        helper.verify_records(read_canonical_residue_mapping(path), rows, reference)


def synthetic_psf(tmp_path, rows, reference):
    # A topology-only fixture for the independent text parser. Atom names convey
    # no amino-acid identity; glycan is interleaved and must remain unmapped.
    psf = tmp_path / "source.psf"
    atoms = [("PROA", str(1001 + i), r["source_resname"]) for i, r in enumerate(rows)]
    atoms.insert(2, ("GLYA", "1", "BGLCNA"))
    psf.write_text(
        "PSF EXT\n\n"
        + f"{len(atoms)} !NATOM\n"
        + "".join(
            f"{i} {seg} {resid} {name} XX C 0.0 12.0 0\n"
            for i, (seg, resid, name) in enumerate(atoms, 1)
        )
    )
    source = [
        {
            **r,
            "source_resid": str(1001 + i),
            "source_topology_residue_index": i + (i >= 2),
        }
        for i, r in enumerate(rows)
    ]
    binding = {
        "psf": helper.file_record(psf),
        "protein_residue_count": len(source),
        "protein_atom_count": len(source),
        "ordered_residue_identity_sha256": helper.ordered_signature(source),
        "canonical_reference_id": reference.reference_id,
        "canonical_sequence_sha256": reference.sequence_sha256,
        "source_sequence_sha256": reference.sequence_sha256,
    }
    return psf, source, binding


def test_independent_parser_checks_persisted_mapping(tmp_path, rows, reference):
    psf, source, binding = synthetic_psf(tmp_path, rows, reference)
    path, _ = write_mapping(tmp_path, source, reference)
    report = helper.independent_check(psf, path, binding)
    assert report["checked_records"] == 690
    assert report["ordered_residue_identity_sha256"] == helper.ordered_signature(source)


@pytest.mark.parametrize(
    "change,message",
    [
        ("psf", "Wrong PSF binding"),
        ("order", "Different ordered residue identity"),
        ("reference", "Wrong canonical reference identity"),
        ("sequence", "Different source sequence binding"),
    ],
)
def test_binding_fails(tmp_path, rows, reference, change, message):
    psf, source, binding = synthetic_psf(tmp_path, rows, reference)
    if change == "psf":
        psf.write_text(psf.read_text() + "\n")
    elif change == "order":
        source.reverse()
    elif change == "reference":
        binding["canonical_reference_id"] = "wrong"
    else:
        binding["source_sequence_sha256"] = "0" * 64
    with pytest.raises(ValueError, match=message):
        helper.check_binding(psf, source, binding)


def test_independent_check_rejects_valid_stage30_but_wrong_correspondence(
    tmp_path, rows, reference
):
    psf, source, binding = synthetic_psf(tmp_path, rows, reference)
    table = helper.build_mapping(source, reference)
    records = list(table.mappings)
    records[1] = replace(
        records[1], canonical_residue_number=1, canonical_resname="MET"
    )
    path = tmp_path / "wrong.json"
    # Sparse/many-source Stage 30 allows duplicate targets; this WT authority must not.
    assert write_canonical_residue_mapping(
        CanonicalResidueMappingTable(tuple(records)), path
    ).passed
    with pytest.raises(ValueError, match="Independent persisted mapping"):
        helper.independent_check(psf, path, binding)
