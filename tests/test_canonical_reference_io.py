"""Pinned payload regression, strict local reads, and executable offline guards."""

import ast
import inspect
import json
import os
import socket
import subprocess
import urllib.request
from hashlib import md5, sha256
from importlib.resources import files
from pathlib import Path

import pytest

from mania import canonical_reference as model
from mania import canonical_reference_io as reference_io
from mania.canonical_reference_io import (
    CanonicalReferenceReadError,
    load_default_napi2b_canonical_reference,
    read_canonical_reference,
)

RESOURCE_PATH = Path("data/canonical/slc34a2_o95436_reference.json")
# Independent approved test fixture, never a production sequence authority.
APPROVED_SEQUENCE = (
    "MAPWPELGDAQPNPDKYLEGAAGQQPTAPDKSKETNKTDNTEAPVTKIELLPSYSTATLIDEPTEVDDPWNL"
    "PTLQDSGIKWSERDTKGKILCFFQGIGRLILLLGFLYFFVCSLDILSSAFQLVGGKMAGQFFSNSSIMSN"
    "PLLGLVIGVLVTVLVQSSSTSTSIVVSMVSSSLLTVRAAIPIIMGANIGTSITNTIVALMQVGDRSEFRRAF"
    "AGATVHDFFNWLSVLVLLPVEVATHYLEIITQLIVESFHFKNGEDAPDLLKVITKPFTKLIVQLDKKVISQI"
    "AMNDEKAKNKSLVKIWCKTFTNKTQINVTVPSTANCTSPSLCWTDGIQNWTMKNVTYKENIAKCQHIFVNFH"
    "LPDLAVGTILLILSLLVLCGCLIMIVKILGSVLKGQVATVIKKTINTDFPFPFAWLTGYLAILVGAGMTFIV"
    "QSSSVFTSALTPLIGIGVITIERAYPLTLGSNIGTTTTAILAALASPGNALRSSLQIALCHFFFNISGILLWY"
    "PIPFTRLPIRMAKGLGNISAKYRWFAVFYLIIFFFLIPLTVFGLSLAGWRVLVGVGVPVVFIIILVLCLRLL"
    "QSRCPRVLPKKLQNWNFLPLWMRSLKPWDAVVSKFTGCFQMRCCCCCRVCCRACCLLCDCPKCCRCSKCCEDL"
    "EEAQEGQDVPVKAPETFDNITISREAQGEVPASDSKTECTAL"
)


@pytest.fixture
def payload():
    resource = files("mania").joinpath(*RESOURCE_PATH.parts)
    return json.loads(resource.read_text(encoding="utf-8"))


def write_payload(tmp_path, payload):
    path = tmp_path / "reference.json"
    path.write_text(json.dumps(payload, allow_nan=False), encoding="utf-8")
    return path


def test_strict_valid_read_roundtrip_and_public_api(tmp_path, payload):
    path = write_payload(tmp_path, payload)
    reference = read_canonical_reference(path)
    assert reference == read_canonical_reference(str(path))
    assert reference == load_default_napi2b_canonical_reference()
    assert reference.to_dict() == payload
    assert reference == read_canonical_reference(
        write_payload(tmp_path, reference.to_dict())
    )
    assert reference_io.__all__ == [
        "CanonicalReferenceReadError",
        "load_default_napi2b_canonical_reference",
        "read_canonical_reference",
    ]


def test_exact_packaged_sequence_identity_and_independent_checksums(payload):
    reference = load_default_napi2b_canonical_reference()
    assert reference.uniprot_accession == "O95436"
    assert reference.canonical_isoform_id == "O95436-1"
    assert reference.uniprot_entry_name == "NPT2B_HUMAN"
    assert reference.gene_symbol == "SLC34A2"
    assert reference.protein_name == "Sodium-dependent phosphate transport protein 2B"
    assert reference.organism_name == "Homo sapiens"
    assert reference.source_system == "UniProtKB/Swiss-Prot"
    assert (
        reference.source_record_url
        == "https://www.uniprot.org/uniprotkb/O95436-1/entry"
    )
    assert reference.uniprot_sequence_last_updated == "2010-11-30"
    assert reference.uniprot_sequence_version == 3
    assert reference.reference_id == "uniprotkb:O95436-1:sequence-v3"
    assert reference.sequence_length == len(APPROVED_SEQUENCE) == 690
    assert reference.sequence == payload["sequence"] == APPROVED_SEQUENCE
    sequence_bytes = reference.sequence.encode("ascii")
    assert b"\n" not in sequence_bytes
    assert (
        md5(sequence_bytes).hexdigest().upper()
        == reference.uniprot_sequence_md5
        == ("16C21D07D36DC8B416EA72769F0B0280")
    )
    assert (
        sha256(sequence_bytes).hexdigest()
        == reference.sequence_sha256
        == ("33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9")
    )
    assert "".join(reference.residue_at(i).one_letter_code for i in range(1, 691)) == (
        APPROVED_SEQUENCE
    )


@pytest.mark.parametrize("loader", ["path", "default"])
@pytest.mark.parametrize(
    "damage",
    [
        "schema",
        "kind",
        "extra",
        "missing",
        "accession",
        "isoform",
        "entry",
        "gene",
        "length",
        "md5",
        "sha256",
        "mutation",
        "recomputed_mutation",
        "alphabet",
        "whitespace",
        "lowercase",
        "date",
        "version",
    ],
)
def test_corruption_rejected_by_both_loaders(
    tmp_path, monkeypatch, payload, damage, loader
):
    changes = {
        "schema": ("schema_version", "mania.canonical_reference.v9"),
        "kind": ("kind", "another_kind"),
        "extra": ("unexpected", "value"),
        "accession": ("uniprot_accession", "P00000"),
        "isoform": ("canonical_isoform_id", "O95436-2"),
        "entry": ("uniprot_entry_name", "OTHER_HUMAN"),
        "gene": ("gene_symbol", "OTHER"),
        "length": ("sequence_length", 689),
        "md5": ("uniprot_sequence_md5", "0" * 32),
        "sha256": ("sequence_sha256", "0" * 64),
        "mutation": ("sequence", "A" + payload["sequence"][1:]),
        "alphabet": ("sequence", "X" + payload["sequence"][1:]),
        "whitespace": (
            "sequence",
            payload["sequence"][:10] + " " + payload["sequence"][11:],
        ),
        "lowercase": ("sequence", payload["sequence"].lower()),
        "date": ("uniprot_sequence_last_updated", "2010-11-31"),
        "version": ("uniprot_sequence_version", 4),
    }
    if damage == "missing":
        del payload["sequence"]
    elif damage == "recomputed_mutation":
        payload["sequence"] = "A" + payload["sequence"][1:]
        encoded = payload["sequence"].encode("ascii")
        payload["uniprot_sequence_md5"] = md5(encoded).hexdigest().upper()
        payload["sequence_sha256"] = sha256(encoded).hexdigest()
    else:
        name, value = changes[damage]
        payload[name] = value
    if loader == "path":
        path = write_payload(tmp_path, payload)
        with pytest.raises(
            CanonicalReferenceReadError,
            match=r"^Invalid or unreadable canonical reference\.$",
        ):
            read_canonical_reference(path)
    else:
        path = tmp_path / RESOURCE_PATH
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(reference_io, "files", lambda package: tmp_path)
        with pytest.raises(
            CanonicalReferenceReadError,
            match=r"^Invalid or unreadable packaged NaPi2b canonical reference\.$",
        ):
            load_default_napi2b_canonical_reference()


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "kind",
        "uniprot_accession",
        "canonical_isoform_id",
        "uniprot_entry_name",
        "gene_symbol",
        "protein_name",
        "organism_name",
        "source_system",
        "source_record_url",
        "uniprot_sequence_last_updated",
        "uniprot_sequence_md5",
        "sequence_sha256",
        "sequence",
    ],
)
@pytest.mark.parametrize("value", [None, True, 1, [], {}])
def test_reader_strict_string_types(tmp_path, payload, field, value):
    payload[field] = value
    with pytest.raises(CanonicalReferenceReadError):
        read_canonical_reference(write_payload(tmp_path, payload))


@pytest.mark.parametrize("field", ["uniprot_sequence_version", "sequence_length"])
@pytest.mark.parametrize("value", [None, True, False, "3", [], {}])
def test_reader_strict_integer_types(tmp_path, payload, field, value):
    payload[field] = value
    with pytest.raises(CanonicalReferenceReadError):
        read_canonical_reference(write_payload(tmp_path, payload))


@pytest.mark.parametrize("field", ["uniprot_sequence_version", "sequence_length"])
def test_equal_valued_floats_are_not_integers(tmp_path, payload, field):
    payload[field] = float(payload[field])
    with pytest.raises(CanonicalReferenceReadError):
        read_canonical_reference(write_payload(tmp_path, payload))


@pytest.mark.parametrize(
    "damage",
    [
        "malformed",
        "duplicate",
        "nan",
        "infinity",
        "negative_infinity",
        "array",
        "null",
        "number",
        "utf8",
        "utf16",
        "bom",
    ],
)
def test_invalid_json_and_encoding(tmp_path, payload, damage):
    encoded = json.dumps(payload)
    invalid = {
        "malformed": b"{",
        "duplicate": encoded.replace(
            '"kind":', '"kind": "duplicate", "kind":', 1
        ).encode(),
        "nan": encoded.replace(
            '"sequence_length": 690', '"sequence_length": NaN'
        ).encode(),
        "infinity": encoded.replace(
            '"sequence_length": 690', '"sequence_length": Infinity'
        ).encode(),
        "negative_infinity": encoded.replace(
            '"sequence_length": 690', '"sequence_length": -Infinity'
        ).encode(),
        "array": b"[]",
        "null": b"null",
        "number": b"1",
        "utf8": b"\xff",
        "utf16": encoded.encode("utf-16"),
        "bom": b"\xef\xbb\xbf" + encoded.encode(),
    }
    path = tmp_path / "invalid.json"
    path.write_bytes(invalid[damage])
    with pytest.raises(CanonicalReferenceReadError):
        read_canonical_reference(path)


def test_unreadable_paths_and_missing_or_corrupt_resource(tmp_path, monkeypatch):
    for path in (tmp_path / "absent.json", tmp_path):
        with pytest.raises(CanonicalReferenceReadError):
            read_canonical_reference(path)
    monkeypatch.setattr(reference_io, "files", lambda package: tmp_path)
    expected = "Invalid or unreadable packaged NaPi2b canonical reference."
    with pytest.raises(CanonicalReferenceReadError) as missing:
        load_default_napi2b_canonical_reference()
    assert str(missing.value) == expected
    path = tmp_path / RESOURCE_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff")
    with pytest.raises(CanonicalReferenceReadError) as corrupt:
        load_default_napi2b_canonical_reference()
    assert str(corrupt.value) == expected


def test_source_url_is_non_live_provenance(tmp_path, payload):
    original = load_default_napi2b_canonical_reference()
    payload["source_record_url"] = "https://unavailable.invalid/reference"
    altered = read_canonical_reference(write_payload(tmp_path, payload))
    assert altered.reference_id == original.reference_id
    assert altered.sequence == original.sequence
    assert altered.source_record_url == payload["source_record_url"]
    assert load_default_napi2b_canonical_reference() == original


def test_offline_loading_no_subprocess_git_or_cwd_dependency(tmp_path, monkeypatch):
    resource = files("mania").joinpath(*RESOURCE_PATH.parts)
    before = resource.read_bytes()
    # A corrupt cwd decoy must never replace the importlib package resource.
    decoy = tmp_path / RESOURCE_PATH
    decoy.parent.mkdir(parents=True)
    decoy.write_text("invalid", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def blocked(*args, **kwargs):
        raise AssertionError("Network, subprocess, and Git execution are blocked")

    for owner, names in (
        (socket, ("create_connection", "getaddrinfo")),
        (socket.socket, ("connect", "connect_ex")),
        (urllib.request, ("urlopen", "urlretrieve")),
        (urllib.request.OpenerDirector, ("open",)),
        (subprocess, ("Popen", "run", "call", "check_call", "check_output")),
        (
            os,
            (
                "system",
                "popen",
                "posix_spawn",
                "posix_spawnp",
                "spawnv",
                "spawnve",
                "spawnvp",
                "spawnvpe",
                "execv",
                "execve",
                "execvp",
                "execvpe",
            ),
        ),
    ):
        for name in names:
            if hasattr(owner, name):
                monkeypatch.setattr(owner, name, blocked)
    for action in (
        lambda: socket.create_connection(("unavailable.invalid", 443)),
        lambda: urllib.request.urlopen("https://unavailable.invalid"),
        lambda: subprocess.run(["git", "rev-parse", "HEAD"]),
        lambda: os.system("git --version"),
    ):
        with pytest.raises(AssertionError, match="are blocked"):
            action()
    reference = load_default_napi2b_canonical_reference()
    assert reference.reference_id == "uniprotkb:O95436-1:sequence-v3"
    assert reference.sequence == APPROVED_SEQUENCE
    assert "".join(r.one_letter_code for r in reference.residues()) == APPROVED_SEQUENCE
    assert resource.read_bytes() == before


@pytest.mark.parametrize("module", [model, reference_io])
def test_production_imports_have_no_network_or_process_clients(module):
    imported = set()
    for node in ast.walk(ast.parse(inspect.getsource(module))):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
    forbidden = (
        "requests",
        "urllib.request",
        "http.client",
        "socket",
        "httpx",
        "urllib3",
        "aiohttp",
        "subprocess",
        "git",
    )
    assert not {
        name
        for name in imported
        if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)
    }
