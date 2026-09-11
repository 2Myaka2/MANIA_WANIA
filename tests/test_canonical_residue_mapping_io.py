"""Strict mapping persistence, atomic failure handling, and offline smoke."""

import ast
import inspect
import json
import os
import socket
import subprocess
import time
import urllib.request
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

from mania import canonical_residue_mapping as model
from mania import canonical_residue_mapping_io as mapping_io
from mania.canonical_reference_io import load_default_napi2b_canonical_reference
from mania.canonical_residue_mapping import (
    CanonicalResidueMappingError,
    CanonicalResidueMappingRecord,
    CanonicalResidueMappingTable,
    canonical_residue_for_mapping,
    find_source_residue_mapping,
    require_mapped_source_residue,
    require_source_residue_mapping,
    validate_canonical_residue_mapping_table,
)
from mania.canonical_residue_mapping_io import (
    CANONICAL_RESIDUE_MAPPING_FILENAME,
    CanonicalResidueMappingReadError,
    CanonicalResidueMappingValidationIssue,
    CanonicalResidueMappingValidationReport,
    CanonicalResidueMappingWriteResult,
    read_canonical_residue_mapping,
    validate_canonical_residue_mapping,
    write_canonical_residue_mapping,
)

ROOT_FIELDS = (
    "schema_version",
    "kind",
    "canonical_reference_id",
    "canonical_reference_sequence_sha256",
    "mapping_count",
    "mappings",
)
ROW_FIELDS = (
    "source_engine",
    "source_chain_id",
    "source_resid",
    "source_resname",
    "canonical_residue_number",
    "canonical_resname",
    "mapping_status",
)


@pytest.fixture
def table():
    reference = load_default_napi2b_canonical_reference()
    return CanonicalResidueMappingTable(
        (
            # Synthetic namespace regression, not a biological mapping claim.
            CanonicalResidueMappingRecord(
                "gromacs",
                "A",
                "311",
                "GLN",
                312,
                reference.residue_at(312).canonical_resname,
                "mapped",
            ),
            CanonicalResidueMappingRecord(
                "gromacs",
                "A",
                "330",
                "MET",
                330,
                "THR",
                "mapped",
            ),
            CanonicalResidueMappingRecord(
                "namd",
                None,
                "X42",
                "SER",
                None,
                None,
                "unmapped",
            ),
        )
    )


@pytest.fixture
def payload(table):
    return table.to_dict()


def put_payload(tmp_path, payload):
    path = tmp_path / CANONICAL_RESIDUE_MAPPING_FILENAME
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def assert_rejected(path):
    with pytest.raises(CanonicalResidueMappingReadError) as caught:
        read_canonical_residue_mapping(path)
    assert str(caught.value) == "Invalid or unreadable canonical residue mapping."
    report = validate_canonical_residue_mapping(path)
    assert not report.passed
    assert report.mapping_path == path
    assert (report.mapping_count, report.mapped_count, report.unmapped_count) == (
        None,
        None,
        None,
    )
    assert report.issues == (
        CanonicalResidueMappingValidationIssue(
            "mapping", "Invalid or unreadable canonical residue mapping."
        ),
    )


def test_io_public_api_and_result_contract(tmp_path):
    assert CANONICAL_RESIDUE_MAPPING_FILENAME == "canonical_residue_mapping.json"
    assert set(mapping_io.__all__) == {
        "CANONICAL_RESIDUE_MAPPING_FILENAME",
        "CanonicalResidueMappingReadError",
        "CanonicalResidueMappingValidationIssue",
        "CanonicalResidueMappingValidationReport",
        "CanonicalResidueMappingWriteResult",
        "read_canonical_residue_mapping",
        "validate_canonical_residue_mapping",
        "write_canonical_residue_mapping",
    }
    assert issubclass(CanonicalResidueMappingReadError, ValueError)
    issue = CanonicalResidueMappingValidationIssue("mapping", "Invalid mapping.")
    report = CanonicalResidueMappingValidationReport(
        tmp_path, None, None, None, (issue,)
    )
    result = CanonicalResidueMappingWriteResult(tmp_path, False, "Write failed.")
    assert not report.passed and not result.passed
    for instance, names in (
        (issue, ("field", "message")),
        (
            report,
            (
                "mapping_path",
                "mapping_count",
                "mapped_count",
                "unmapped_count",
                "issues",
            ),
        ),
        (result, ("output_path", "written", "error")),
    ):
        assert tuple(f.name for f in fields(instance)) == names
        for name in names:
            with pytest.raises(FrozenInstanceError):
                setattr(instance, name, None)


def test_deterministic_utf8_roundtrip_keys_newline_and_counts(tmp_path, table):
    # Source spellings are unrestricted topology evidence, including UTF-8.
    table = replace(
        table,
        mappings=(
            *table.mappings[:-1],
            replace(table.mappings[-1], source_resid="Ω42", source_resname="sEr*"),
        ),
    )
    path = tmp_path / "nested" / CANONICAL_RESIDUE_MAPPING_FILENAME
    other = tmp_path / "second.json"
    expected = (
        json.dumps(
            table.to_dict(),
            indent=2,
            sort_keys=False,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    for destination in (path, other):
        result = write_canonical_residue_mapping(table, destination)
        assert result == CanonicalResidueMappingWriteResult(destination, True, None)
        assert result.passed
        assert destination.read_bytes() == expected
    assert expected.endswith(b"\n") and not expected.endswith(b"\n\n")
    assert b"\\u03a9" not in expected
    decoded = json.loads(expected)
    assert tuple(decoded) == ROOT_FIELDS
    assert all(tuple(row) == ROW_FIELDS for row in decoded["mappings"])
    assert read_canonical_residue_mapping(str(path)) == table
    restored = read_canonical_residue_mapping(path)
    assert type(restored.mappings[1].source_resid) is str
    assert restored.mappings[1].source_resid == "330"
    assert restored.mappings[-1].source_chain_id is None
    assert restored.mappings[-1].source_resname == "sEr*"
    assert validate_canonical_residue_mapping(
        path
    ) == CanonicalResidueMappingValidationReport(path, 3, 2, 1, ())
    assert not tuple(path.parent.glob(".*.tmp"))


@pytest.mark.parametrize(
    "selection,counts",
    [
        ((), (0, 0, 0)),
        ((0, 1), (2, 2, 0)),
        ((2,), (1, 0, 1)),
    ],
)
def test_empty_and_single_status_roundtrips(tmp_path, table, selection, counts):
    selected = CanonicalResidueMappingTable(tuple(table.mappings[i] for i in selection))
    path = tmp_path / CANONICAL_RESIDUE_MAPPING_FILENAME
    assert write_canonical_residue_mapping(selected, path).passed
    assert read_canonical_residue_mapping(path) == selected
    report = validate_canonical_residue_mapping(path)
    assert report.passed
    assert (report.mapping_count, report.mapped_count, report.unmapped_count) == counts


def test_overwrite_false_and_true(tmp_path, table):
    path = tmp_path / CANONICAL_RESIDUE_MAPPING_FILENAME
    path.write_bytes(b"existing user data\n")
    assert write_canonical_residue_mapping(
        table, path
    ) == CanonicalResidueMappingWriteResult(path, False, "Target already exists.")
    assert path.read_bytes() == b"existing user data\n"
    assert write_canonical_residue_mapping(table, path, overwrite=True).passed
    assert read_canonical_residue_mapping(path) == table


@pytest.mark.parametrize("overwrite", [False, True])
def test_atomic_publication_observes_complete_temp_only(
    tmp_path, monkeypatch, table, overwrite
):
    path = tmp_path / CANONICAL_RESIDUE_MAPPING_FILENAME
    if overwrite:
        path.write_bytes(b"old bytes")
    name = "replace" if overwrite else "link"
    publish = getattr(os, name)
    seen = []

    def checked(source, destination):
        source = Path(source)
        assert source.parent == path.parent and source != path
        assert read_canonical_residue_mapping(source) == table
        assert path.read_bytes() == b"old bytes" if overwrite else not path.exists()
        seen.append(source)
        return publish(source, destination)

    monkeypatch.setattr(os, name, checked)
    assert write_canonical_residue_mapping(table, path, overwrite=overwrite).passed
    assert len(seen) == 1 and not seen[0].exists()
    assert read_canonical_residue_mapping(path) == table


@pytest.mark.parametrize("overwrite", [False, True])
def test_publication_failure_preserves_destination_and_unrelated_temp(
    tmp_path,
    monkeypatch,
    table,
    overwrite,
):
    path = tmp_path / CANONICAL_RESIDUE_MAPPING_FILENAME
    if overwrite:
        path.write_bytes(b"old bytes")
    unrelated = tmp_path / f".{path.name}.user.tmp"
    unrelated.write_bytes(b"user-owned temporary file")

    def fail(*args):
        raise OSError("Sensitive local path must not appear in errors")

    monkeypatch.setattr(os, "replace" if overwrite else "link", fail)
    result = write_canonical_residue_mapping(table, path, overwrite=overwrite)
    assert not result.passed and result.error == "Filesystem write failed."
    assert path.read_bytes() == b"old bytes" if overwrite else not path.exists()
    assert tuple(tmp_path.glob(".*.tmp")) == (unrelated,)
    assert unrelated.read_bytes() == b"user-owned temporary file"


def test_no_overwrite_race(tmp_path, monkeypatch, table):
    path = tmp_path / CANONICAL_RESIDUE_MAPPING_FILENAME
    link = os.link

    def concurrent_create(source, destination):
        path.write_bytes(b"other writer")
        link(source, destination)

    monkeypatch.setattr(os, "link", concurrent_create)
    result = write_canonical_residue_mapping(table, path)
    assert not result.passed and result.error == "Target already exists."
    assert path.read_bytes() == b"other writer"
    assert not tuple(tmp_path.glob(".*.tmp"))


def test_existing_dangling_symlink_is_protected(tmp_path, table):
    path = tmp_path / CANONICAL_RESIDUE_MAPPING_FILENAME
    target = tmp_path / "absent.json"
    path.symlink_to(target)
    assert (
        write_canonical_residue_mapping(table, path).error == "Target already exists."
    )
    assert path.is_symlink() and not target.exists()


def test_encoding_failure_cleans_only_own_temporary(tmp_path, table):
    record = replace(table.mappings[0], source_resname="\ud800")
    table = CanonicalResidueMappingTable((record,))
    path = tmp_path / CANONICAL_RESIDUE_MAPPING_FILENAME
    path.write_bytes(b"old bytes")
    result = write_canonical_residue_mapping(table, path, overwrite=True)
    assert not result.passed and result.error == "JSON serialization failed."
    assert path.read_bytes() == b"old bytes"
    assert not tuple(tmp_path.glob(".*.tmp"))


def test_cleanup_failure_is_reported(tmp_path, monkeypatch, table):
    path = tmp_path / CANONICAL_RESIDUE_MAPPING_FILENAME
    unlink = Path.unlink

    def fail_temporary(self, *args, **kwargs):
        if self.suffix == ".tmp":
            raise OSError("cleanup failed")
        return unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_temporary)
    result = write_canonical_residue_mapping(table, path)
    assert not result.passed and result.error == "Temporary file cleanup failed."
    assert read_canonical_residue_mapping(path) == table
    # Remove only this test's temp after exercising the reported failure.
    for temporary in tmp_path.glob(".*.tmp"):
        unlink(temporary)


def test_invalid_table_fails_reference_validation_before_write(tmp_path, table):
    wrong = replace(table.mappings[1], canonical_resname="MET")
    path = tmp_path / "not-created" / CANONICAL_RESIDUE_MAPPING_FILENAME
    for invalid in (None, CanonicalResidueMappingTable((wrong,))):
        with pytest.raises(CanonicalResidueMappingError):
            write_canonical_residue_mapping(invalid, path)
        assert not path.parent.exists()


@pytest.mark.parametrize("overwrite", [None, 0, 1, "true"])
def test_strict_overwrite_argument(tmp_path, table, overwrite):
    with pytest.raises(ValueError, match="overwrite must be a bool"):
        write_canonical_residue_mapping(
            table, tmp_path / "out.json", overwrite=overwrite
        )


@pytest.mark.parametrize(
    "content",
    [
        b"{",
        b"",
        b"[]",
        b"null",
        b"true",
        b"42",
        b'"text"',
        b"{} {}",
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b"\xff",
        b"\xef\xbb\xbf{}",
    ],
)
def test_malformed_or_wrong_root_json(tmp_path, content):
    path = tmp_path / "bad.json"
    path.write_bytes(content)
    assert_rejected(path)


def test_missing_and_directory_paths(tmp_path):
    assert_rejected(tmp_path / "missing.json")
    assert_rejected(tmp_path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "mania.canonical_residue_mapping.v9"),
        ("kind", "other"),
        ("canonical_reference_id", "uniprotkb:O95436-2:sequence-v3"),
        ("canonical_reference_sequence_sha256", "0" * 64),
        ("mapping_count", 2),
        ("mapping_count", -1),
        ("mapping_count", True),
        ("mapping_count", 3.0),
        ("mapping_count", "3"),
        ("mapping_count", None),
        ("mappings", None),
        ("mappings", {}),
        ("mappings", "rows"),
    ],
)
def test_invalid_root_values(tmp_path, payload, field, value):
    payload[field] = value
    assert_rejected(put_payload(tmp_path, payload))


@pytest.mark.parametrize("field", ROOT_FIELDS[:4])
@pytest.mark.parametrize("value", [None, True, 1, [], {}])
def test_strict_root_identity_scalar_types(tmp_path, payload, field, value):
    payload[field] = value
    assert_rejected(put_payload(tmp_path, payload))


@pytest.mark.parametrize("field", ROOT_FIELDS)
def test_missing_root_fields(tmp_path, payload, field):
    del payload[field]
    assert_rejected(put_payload(tmp_path, payload))


@pytest.mark.parametrize("field", ROW_FIELDS)
def test_missing_row_fields(tmp_path, payload, field):
    del payload["mappings"][0][field]
    assert_rejected(put_payload(tmp_path, payload))


@pytest.mark.parametrize("where", ["root", "row"])
@pytest.mark.parametrize(
    "field", ["extra", "condition", "dataset_id", "source_residue_index"]
)
def test_unknown_fields_rejected(tmp_path, payload, where, field):
    target = payload if where == "root" else payload["mappings"][0]
    target[field] = None
    assert_rejected(put_payload(tmp_path, payload))


@pytest.mark.parametrize("where", ["root", "row"])
def test_object_key_order_is_strict(tmp_path, payload, where):
    if where == "root":
        payload = dict(reversed(tuple(payload.items())))
    else:
        payload["mappings"][0] = dict(reversed(tuple(payload["mappings"][0].items())))
    assert_rejected(put_payload(tmp_path, payload))


@pytest.mark.parametrize(
    "fragment",
    [
        '"mapping_count": 3',
        '"source_resid": "330"',
    ],
)
def test_duplicate_json_object_keys(tmp_path, payload, fragment):
    text = json.dumps(payload)
    assert fragment in text
    path = tmp_path / "duplicate.json"
    path.write_text(
        text.replace(fragment, fragment + ", " + fragment), encoding="utf-8"
    )
    assert_rejected(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_engine", "GROMACS"),
        ("source_engine", "NAMD"),
        ("source_engine", "gromac"),
        ("source_engine", 1),
        ("source_chain_id", ""),
        ("source_chain_id", 1),
        ("source_chain_id", " A"),
        ("source_resid", 330),
        ("source_resid", True),
        ("source_resid", 330.0),
        ("source_resid", None),
        ("source_resid", "330 "),
        ("source_resname", ""),
        ("source_resname", 1),
        ("source_resname", None),
        ("canonical_residue_number", None),
        ("canonical_residue_number", True),
        ("canonical_residue_number", 0),
        ("canonical_residue_number", 691),
        ("canonical_residue_number", 330.0),
        ("canonical_residue_number", "330"),
        ("canonical_resname", None),
        ("canonical_resname", 330),
        ("canonical_resname", "thr"),
        ("canonical_resname", "MET"),
        ("canonical_resname", "UNK"),
        ("mapping_status", "unmapped"),
        ("mapping_status", "guessed"),
        ("mapping_status", True),
    ],
)
def test_invalid_mapped_fields_and_reference_name(tmp_path, payload, field, value):
    payload["mappings"][1][field] = value
    assert_rejected(put_payload(tmp_path, payload))


@pytest.mark.parametrize(
    "field,value",
    [
        ("canonical_residue_number", 0),
        ("canonical_residue_number", -1),
        ("canonical_residue_number", False),
        ("canonical_residue_number", 330),
        ("canonical_resname", "UNK"),
        ("canonical_resname", "NA"),
        ("canonical_resname", "SER"),
        ("mapping_status", "mapped"),
    ],
)
def test_unmapped_null_contract(tmp_path, payload, field, value):
    payload["mappings"][2][field] = value
    assert_rejected(put_payload(tmp_path, payload))


@pytest.mark.parametrize("row", [None, [], "record", 1])
def test_non_object_mapping_rows(tmp_path, payload, row):
    payload["mappings"][0] = row
    assert_rejected(put_payload(tmp_path, payload))


def test_duplicate_source_keys_and_unsorted_rows(tmp_path, payload):
    payload["mappings"].reverse()
    assert_rejected(put_payload(tmp_path, payload))
    payload["mappings"].reverse()
    payload["mappings"].insert(0, payload["mappings"][0])
    payload["mapping_count"] += 1
    assert_rejected(put_payload(tmp_path, payload))


def test_validation_wrapper_uses_strict_reader_once(tmp_path, table, monkeypatch):
    calls = []

    def reader(path):
        calls.append(path)
        return table

    monkeypatch.setattr(mapping_io, "read_canonical_residue_mapping", reader)
    path = tmp_path / "delegated.json"
    assert validate_canonical_residue_mapping(path).mapping_count == 3
    assert calls == [path]


@pytest.mark.parametrize(
    "change",
    [
        {"mapping_path": "file.json"},
        {"mapping_count": True},
        {"mapped_count": -1},
        {"unmapped_count": 1.0},
        {"mapping_count": None},
        {"mapping_count": 4},
        {"issues": []},
        {"issues": ("invalid",)},
    ],
)
def test_validation_report_rejects_invalid_counts_and_types(tmp_path, change):
    report = CanonicalResidueMappingValidationReport(tmp_path, 3, 2, 1, ())
    with pytest.raises(ValueError):
        replace(report, **change)


def test_offline_scientific_and_namespace_smoke(tmp_path, monkeypatch, table):
    def blocked(*args, **kwargs):
        raise AssertionError(
            "Network, subprocess, Git, clock, and environment are blocked"
        )

    decoy = tmp_path / "data/canonical/slc34a2_o95436_reference.json"
    decoy.parent.mkdir(parents=True)
    decoy.write_text("invalid decoy", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    for owner, names in (
        (socket, ("socket", "create_connection", "getaddrinfo")),
        (urllib.request, ("urlopen", "urlretrieve")),
        (urllib.request.OpenerDirector, ("open",)),
        (subprocess, ("Popen", "run", "call", "check_call", "check_output")),
        (time, ("time", "time_ns", "monotonic", "monotonic_ns", "perf_counter")),
        (
            os,
            (
                "system",
                "popen",
                "getenv",
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
        lambda: socket.socket(),
        lambda: urllib.request.urlopen("https://unavailable.invalid"),
        lambda: subprocess.run(["git", "rev-parse", "HEAD"]),
        lambda: os.system("git --version"),
        lambda: time.time(),
    ):
        with pytest.raises(AssertionError, match="are blocked"):
            action()
    reference = load_default_napi2b_canonical_reference()
    assert reference.reference_id == model.CANONICAL_RESIDUE_MAPPING_REFERENCE_ID
    # Scientific smoke specifies a numeric-looking explicit unmapped resid too.
    table = replace(
        table,
        mappings=(*table.mappings[:-1], replace(table.mappings[-1], source_resid="42")),
    )
    assert validate_canonical_residue_mapping_table(table, reference=reference) is table
    path = tmp_path / CANONICAL_RESIDUE_MAPPING_FILENAME
    assert write_canonical_residue_mapping(table, path).passed
    assert read_canonical_residue_mapping(path) == table
    assert validate_canonical_residue_mapping(path).passed
    synthetic, variant, unmapped = table.mappings
    assert (variant.source_resname, variant.canonical_resname) == ("MET", "THR")
    assert canonical_residue_for_mapping(variant, reference) == reference.residue_at(
        330
    )
    unmapped_key = dict(zip(ROW_FIELDS[:4], unmapped.source_key, strict=True))
    assert require_source_residue_mapping(table, **unmapped_key) is unmapped
    with pytest.raises(CanonicalResidueMappingError, match="explicitly unmapped"):
        require_mapped_source_residue(table, **unmapped_key)
    assert synthetic.source_resid == "311" and synthetic.canonical_residue_number == 312
    assert reference.residue_at(311).canonical_resname == "GLN"
    key = dict(zip(ROW_FIELDS[:4], synthetic.source_key, strict=True))
    assert find_source_residue_mapping(table, **key) is synthetic
    assert (
        find_source_residue_mapping(
            CanonicalResidueMappingTable((variant, unmapped)),
            **key,
        )
        is None
    )


@pytest.mark.parametrize("module", [model, mapping_io])
def test_production_imports_exclude_network_process_and_clock(module):
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
        "time",
        "datetime",
        "uuid",
    )
    assert not {
        name
        for name in imported
        if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)
    }
