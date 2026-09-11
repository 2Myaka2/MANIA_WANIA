"""Stage 30.A target identity, immutable coordinates, and sequence validation."""

import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from hashlib import md5, sha256

import pytest

from mania import canonical_reference as model
from mania.canonical_reference import (
    CanonicalProteinReference,
    CanonicalResidueReference,
)
from mania.canonical_reference_io import load_default_napi2b_canonical_reference

REFERENCE_FIELDS = (
    "uniprot_accession",
    "canonical_isoform_id",
    "uniprot_entry_name",
    "gene_symbol",
    "protein_name",
    "organism_name",
    "source_system",
    "source_record_url",
    "uniprot_sequence_version",
    "uniprot_sequence_last_updated",
    "uniprot_sequence_md5",
    "sequence_sha256",
    "sequence_length",
    "sequence",
    "schema_version",
    "kind",
)
STANDARD_CODES = (
    ("A", "ALA"),
    ("R", "ARG"),
    ("N", "ASN"),
    ("D", "ASP"),
    ("C", "CYS"),
    ("Q", "GLN"),
    ("E", "GLU"),
    ("G", "GLY"),
    ("H", "HIS"),
    ("I", "ILE"),
    ("L", "LEU"),
    ("K", "LYS"),
    ("M", "MET"),
    ("F", "PHE"),
    ("P", "PRO"),
    ("S", "SER"),
    ("T", "THR"),
    ("W", "TRP"),
    ("Y", "TYR"),
    ("V", "VAL"),
)


@pytest.fixture
def reference():
    return load_default_napi2b_canonical_reference()


def test_public_constants_and_api():
    expected = {
        "NAPI2B_CANONICAL_REFERENCE_SCHEMA_VERSION": "mania.canonical_reference.v0.1",
        "NAPI2B_CANONICAL_REFERENCE_KIND": "mania_canonical_protein_reference",
        "NAPI2B_UNIPROT_ACCESSION": "O95436",
        "NAPI2B_CANONICAL_ISOFORM_ID": "O95436-1",
        "NAPI2B_UNIPROT_ENTRY_NAME": "NPT2B_HUMAN",
        "NAPI2B_GENE_SYMBOL": "SLC34A2",
        "NAPI2B_CANONICAL_SEQUENCE_LENGTH": 690,
        "NAPI2B_UNIPROT_SEQUENCE_VERSION": 3,
        "NAPI2B_UNIPROT_SEQUENCE_MD5": "16C21D07D36DC8B416EA72769F0B0280",
        "NAPI2B_CANONICAL_SEQUENCE_SHA256": (
            "33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9"
        ),
    }
    assert {name: getattr(model, name) for name in expected} == expected
    assert set(model.__all__) == set(expected) | {
        "CanonicalProteinReference",
        "CanonicalResidueReference",
    }


def test_field_order_frozen_models_and_non_init_contract(reference):
    assert tuple(item.name for item in fields(reference)) == REFERENCE_FIELDS
    assert tuple(item.name for item in fields(CanonicalResidueReference)) == (
        "canonical_residue_number",
        "one_letter_code",
        "canonical_resname",
    )
    assert tuple(item.name for item in fields(reference) if not item.init) == (
        "schema_version",
        "kind",
    )
    for item in fields(reference):
        with pytest.raises(FrozenInstanceError):
            setattr(reference, item.name, None)
    residue = reference.residue_at(1)
    for item in fields(residue):
        with pytest.raises(FrozenInstanceError):
            setattr(residue, item.name, None)
    arguments = {name: getattr(reference, name) for name in REFERENCE_FIELDS[:-2]}
    for name in ("schema_version", "kind"):
        with pytest.raises(TypeError):
            CanonicalProteinReference(**arguments, **{name: getattr(reference, name)})


@pytest.mark.parametrize("letter,resname", STANDARD_CODES)
def test_standard_resname_semantics(reference, letter, resname):
    residue = reference.residue_at(reference.sequence.index(letter) + 1)
    assert residue.one_letter_code == letter
    assert residue.canonical_resname == resname
    assert CanonicalResidueReference(1, letter, resname).to_dict() == {
        "canonical_residue_number": 1,
        "one_letter_code": letter,
        "canonical_resname": resname,
    }


@pytest.mark.parametrize("position", [True, False, 0, -1, 691, 1.0, "1", None, []])
def test_invalid_canonical_positions(reference, position):
    with pytest.raises(ValueError, match="integer in 1..690"):
        reference.residue_at(position)
    with pytest.raises(ValueError, match="integer in 1..690"):
        CanonicalResidueReference(position, "M", "MET")


@pytest.mark.parametrize(
    "letter",
    ["", "AA", "a", "B", "J", "O", "U", "X", "Z", " A", "A\n", "Å", True, None, []],
)
def test_invalid_residue_letters(letter):
    with pytest.raises(ValueError, match="one_letter_code"):
        CanonicalResidueReference(1, letter, "ALA")


@pytest.mark.parametrize("resname", ["A", "ala", "ARG", "ALA ", "HID", None, 1])
def test_invalid_canonical_resnames(resname):
    with pytest.raises(ValueError, match="canonical_resname"):
        CanonicalResidueReference(1, "A", resname)


@pytest.mark.parametrize(
    "position,letter,resname",
    [
        (1, "M", "MET"),
        (234, "V", "VAL"),
        (311, "Q", "GLN"),
        (330, "T", "THR"),
        (341, "V", "VAL"),
        (361, "D", "ASP"),
        (690, "L", "LEU"),
    ],
)
def test_important_position_smoke(reference, position, letter, resname):
    assert reference.sequence[position - 1] == letter
    assert reference.residue_at(position) == CanonicalResidueReference(
        position, letter, resname
    )


def test_iteration_reconstructs_all_690_residues(reference):
    residues = reference.residues()
    assert isinstance(residues, tuple)
    assert len(residues) == 690
    assert tuple(residue.canonical_residue_number for residue in residues) == tuple(
        range(1, 691)
    )
    assert (
        "".join(residue.one_letter_code for residue in residues) == reference.sequence
    )
    assert residues == tuple(reference.residue_at(i) for i in range(1, 691))


@pytest.mark.parametrize(
    "name",
    [
        name
        for name in REFERENCE_FIELDS[:-2]
        if name not in ("sequence_length", "uniprot_sequence_version")
    ],
)
@pytest.mark.parametrize("value", [None, True, 1, [], {}, "", " "])
def test_strict_nonempty_strings(reference, name, value):
    with pytest.raises(ValueError, match=name):
        replace(reference, **{name: value})


@pytest.mark.parametrize(
    "name",
    [
        name
        for name in REFERENCE_FIELDS[:-2]
        if name not in ("sequence_length", "uniprot_sequence_version")
    ],
)
def test_text_must_already_be_normalized(reference, name):
    with pytest.raises(ValueError, match=name):
        replace(reference, **{name: " " + getattr(reference, name)})


@pytest.mark.parametrize("name", ["sequence_length", "uniprot_sequence_version"])
@pytest.mark.parametrize("value", [True, False, 0, -1, 3.0, "3", None])
def test_strict_positive_integers(reference, name, value):
    with pytest.raises(ValueError, match=name):
        replace(reference, **{name: value})


@pytest.mark.parametrize(
    "value",
    [
        "20101130",
        "2010-1-30",
        "2010-11-3",
        "2010-11-31",
        "0000-01-01",
        "2010-11-30T00:00:00",
        "2010-W48-2",
        "２０１０-11-30",
    ],
)
def test_strict_iso_date(reference, value):
    with pytest.raises(ValueError):
        replace(reference, uniprot_sequence_last_updated=value)


@pytest.mark.parametrize(
    "replacement", ["m", "X", "B", "Z", "J", "U", "O", " ", "\n", "\t", "Å"]
)
def test_sequence_alphabet_and_whitespace(reference, replacement):
    with pytest.raises(ValueError, match="standard uppercase amino acids"):
        replace(
            reference,
            sequence=reference.sequence[:9] + replacement + reference.sequence[10:],
        )


@pytest.mark.parametrize("length", [689, 691])
def test_declared_length_must_match_bytes(reference, length):
    with pytest.raises(ValueError, match="sequence_length"):
        replace(reference, sequence_length=length)


@pytest.mark.parametrize(
    "name,value",
    [
        ("uniprot_sequence_md5", "G" * 32),
        ("uniprot_sequence_md5", "0" * 31),
        ("uniprot_sequence_md5", "0" * 33),
        ("uniprot_sequence_md5", "0" * 32),
        ("sequence_sha256", "A" * 64),
        ("sequence_sha256", "g" * 64),
        ("sequence_sha256", "0" * 63),
        ("sequence_sha256", "0" * 65),
        ("sequence_sha256", "0" * 64),
    ],
)
def test_checksum_format_and_content(reference, name, value):
    with pytest.raises(ValueError, match=name):
        replace(reference, **{name: value})


def test_single_residue_mutation_with_stale_checksums(reference):
    with pytest.raises(ValueError, match="MD5 does not match"):
        replace(reference, sequence="A" + reference.sequence[1:])


@pytest.mark.parametrize("change", ["mutation", "truncation"])
def test_even_recomputed_checksums_cannot_replace_pinned_sequence(reference, change):
    sequence = (
        "A" + reference.sequence[1:]
        if change == "mutation"
        else reference.sequence[:-1]
    )
    with pytest.raises(ValueError, match="pinned NaPi2b reference"):
        replace(
            reference,
            sequence=sequence,
            sequence_length=len(sequence),
            uniprot_sequence_md5=md5(sequence.encode("ascii")).hexdigest().upper(),
            sequence_sha256=sha256(sequence.encode("ascii")).hexdigest(),
        )


@pytest.mark.parametrize(
    "name,value",
    [
        ("uniprot_accession", "P00000"),
        ("canonical_isoform_id", "O95436-2"),
        ("uniprot_entry_name", "OTHER_HUMAN"),
        ("gene_symbol", "OTHER"),
        ("protein_name", "Other protein"),
        ("organism_name", "Other organism"),
        ("source_system", "Other source"),
        ("uniprot_sequence_version", 4),
        ("uniprot_sequence_last_updated", "2010-12-01"),
        ("uniprot_sequence_md5", "16c21d07d36dc8b416ea72769f0b0280"),
    ],
)
def test_napi2b_only_identity_contract(reference, name, value):
    with pytest.raises(ValueError, match="pinned NaPi2b reference"):
        replace(reference, **{name: value})


def test_deterministic_identity_serialization_and_independent_dicts(reference):
    assert reference.reference_id == "uniprotkb:O95436-1:sequence-v3"
    assert tuple(reference.to_dict()) == REFERENCE_FIELDS
    encoded = json.dumps(reference.to_dict(), allow_nan=False, separators=(",", ":"))
    second = load_default_napi2b_canonical_reference()
    assert encoded == json.dumps(
        second.to_dict(), allow_nan=False, separators=(",", ":")
    )
    payload = reference.to_dict()
    payload["sequence"] = "changed"
    assert reference.sequence == second.sequence
    residue = reference.residue_at(1)
    residue.to_dict()["canonical_resname"] = "changed"
    assert residue.canonical_resname == "MET"


def test_no_source_mapping_api(reference):
    assert set(inspect.signature(reference.residue_at).parameters) == {
        "canonical_residue_number",
    }
    assert {
        name for name in vars(CanonicalProteinReference) if not name.startswith("_")
    } == {
        "schema_version",
        "kind",
        "reference_id",
        "residue_at",
        "residues",
        "to_dict",
    }
    for name in (
        "source_resid",
        "source_engine",
        "source_chain_id",
        "resid",
        "frame_index",
        "residue_index",
        "chain_id",
        "offset",
    ):
        with pytest.raises(TypeError):
            reference.residue_at(**{name: 311})
    for name in (
        "map_source_resid",
        "infer_canonical_number",
        "canonicalize_source_residue",
    ):
        assert not hasattr(model, name)
        assert not hasattr(reference, name)
