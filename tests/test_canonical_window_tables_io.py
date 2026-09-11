"""Exact canonical CSV contracts, atomic publication, and offline cross-layer smoke."""

import csv
import os
import socket
import subprocess
import urllib.request
from dataclasses import fields, replace

import pytest
from test_canonical_window_tables import (
    COMMON,
    KINDS,
    METRICS,
    SOURCE_TYPES,
    bindings,
    build,
    mapped,
    mapping_table,
    source_row,
)

from mania import canonical_window_tables as model
from mania import canonical_window_tables_io as io
from mania.preprocessing import molecular_partner_metadata_io as atomic
from mania.preprocessing.protein_edge_window_table_io import (
    DATASET_PROTEIN_EDGE_WINDOW_CSV_COLUMNS,
)
from mania.preprocessing.specialized_contact_window_tables_io import (
    PROTEIN_GLYCAN_WINDOW_CSV_COLUMNS,
    PROTEIN_LIPID_WINDOW_CSV_COLUMNS,
)

COMMON_COLUMNS = (
    "dataset_id",
    "system_id",
    "trajectory_id",
    "variant_id",
    "engine",
    "condition",
    "replica_id",
    "disulfide_state",
    "window_id",
    "window_index",
    "requested_window_start_ns",
    "requested_window_end_ns",
    "right_endpoint_inclusive",
    "effective_window_start_ns",
    "effective_window_end_ns",
    "requested_sample_count",
    "resolved_frame_count",
    "missing_sample_count",
    "coverage_fraction",
)
METRIC_COLUMNS = (
    "n_contact_frames",
    "occupancy",
    "n_contact_episodes",
    "mean_episode_length_ns",
    "max_episode_length_ns",
)
PROTEIN_COLUMNS = (
    "protein_residue_index",
    "protein_chain_id",
    "protein_resid",
    "protein_resname",
    "canonical_residue_number",
    "canonical_resname",
)
EXPECTED_COLUMNS = {
    "edge": COMMON_COLUMNS
    + (
        "source_residue_index",
        "source_chain_id",
        "source_resid",
        "source_resname",
        "source_canonical_residue_number",
        "source_canonical_resname",
        "target_residue_index",
        "target_chain_id",
        "target_resid",
        "target_resname",
        "target_canonical_residue_number",
        "target_canonical_resname",
        "edge_type",
    )
    + METRIC_COLUMNS
    + ("edge_weight",),
    "lipid": COMMON_COLUMNS
    + PROTEIN_COLUMNS
    + (
        "lipid_partner_id",
        "lipid_partner_name",
        "lipid_component_residue_indexes",
    )
    + METRIC_COLUMNS
    + ("distance_mean_A", "distance_min_A"),
    "glycan": COMMON_COLUMNS
    + PROTEIN_COLUMNS
    + (
        "glycan_partner_id",
        "glycan_partner_name",
        "glycan_component_residue_indexes",
        "carrier_residue_index",
        "first_sugar_residue_index",
        "linkage_evidence",
        "carrier_link_atom_index",
        "first_sugar_link_atom_index",
    )
    + METRIC_COLUMNS
    + ("distance_mean_A", "distance_min_A"),
}
FILENAMES = {
    "edge": "protein_edges_by_window_canonical.csv",
    "lipid": "protein_lipid_contacts_by_window_canonical.csv",
    "glycan": "protein_glycan_contacts_by_window_canonical.csv",
}


def api(kind):
    return tuple(
        getattr(io, f"{action}_canonical_protein_{kind}_window_csv")
        for action in ("write", "read", "validate")
    )


def csv_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.reader(stream))


def write_rows(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        csv.writer(stream, lineterminator="\n").writerows(rows)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("count", (0, 1, 2))
def test_exact_headers_counts_roundtrips_and_deterministic_bytes(tmp_path, kind, count):
    base = build(kind)
    rows = (base.rows[0], replace(base.rows[0], replica_id="2"))[:count]
    table = type(base)(rows)
    write, read, validate = api(kind)
    first, second = write(table, tmp_path / "one"), write(table, tmp_path / "two")
    assert first.passed and second.passed
    assert first.output_path.name == FILENAMES[kind]
    assert (
        getattr(model, f"CANONICAL_PROTEIN_{kind.upper()}_WINDOW_CSV_FILENAME")
        == FILENAMES[kind]
    )
    columns = getattr(io, f"CANONICAL_PROTEIN_{kind.upper()}_WINDOW_CSV_COLUMNS")
    assert columns == EXPECTED_COLUMNS[kind]
    assert columns == tuple(f.name for f in fields(base.rows[0]))
    assert tuple(csv_rows(first.output_path)[0]) == columns
    assert len(columns) == {"edge": 38, "lipid": 35, "glycan": 40}[kind]
    original = {
        "edge": DATASET_PROTEIN_EDGE_WINDOW_CSV_COLUMNS,
        "lipid": PROTEIN_LIPID_WINDOW_CSV_COLUMNS,
        "glycan": PROTEIN_GLYCAN_WINDOW_CSV_COLUMNS,
    }[kind]
    assert len(original) == {"edge": 34, "lipid": 33, "glycan": 38}[kind]
    assert set(columns) - set(original) == (
        {
            "source_canonical_residue_number",
            "source_canonical_resname",
            "target_canonical_residue_number",
            "target_canonical_resname",
        }
        if kind == "edge"
        else {"canonical_residue_number", "canonical_resname"}
    )
    assert read(first.output_path) == table
    report = validate(first.output_path)
    assert report.passed and report.row_count == count and report.issues == ()
    assert report.to_dict()["passed"]
    assert first.to_dict()["written"]
    content = first.output_path.read_bytes()
    assert content == second.output_path.read_bytes()
    assert content.endswith(b"\n") and not content.endswith(b"\n\n")
    assert b"\r" not in content
    assert len(csv_rows(first.output_path)) == count + 1
    assert not write(table, tmp_path / "one").passed
    assert first.output_path.read_bytes() == content
    assert write(table, tmp_path / "one", overwrite=True).passed
    assert first.output_path.read_bytes() == content


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "damage",
    (
        "unknown_header",
        "reordered_header",
        "extra_header",
        "missing_header",
        "extra_cell",
        "missing_cell",
        "duplicate",
        "unsorted",
        "empty",
        "blank_row",
        "invalid_utf8",
        "unclosed_quote",
    ),
)
def test_strict_structure_order_and_identity(tmp_path, kind, damage):
    table = build(kind)
    table = type(table)((table.rows[0], replace(table.rows[0], replica_id="2")))
    write, read, validate = api(kind)
    path = write(table, tmp_path).output_path
    rows = csv_rows(path)
    if damage == "unknown_header":
        rows[0][0] = "unknown"
    elif damage == "reordered_header":
        rows[0] = rows[0][::-1]
    elif damage == "extra_header":
        rows[0].append("unknown")
    elif damage == "missing_header":
        rows[0].pop()
    elif damage == "extra_cell":
        rows[1].append("unknown")
    elif damage == "missing_cell":
        rows[1].pop()
    elif damage == "duplicate":
        rows[2] = rows[1].copy()
        rows[2][rows[0].index("condition")] = "different"
    elif damage == "unsorted":
        rows[1], rows[2] = rows[2], rows[1]
    elif damage == "empty":
        rows = []
    elif damage == "blank_row":
        rows.append([])
    write_rows(path, rows)
    if damage == "invalid_utf8":
        path.write_bytes(path.read_bytes() + b"\xff")
    elif damage == "unclosed_quote":
        path.write_bytes(path.read_bytes() + b'"unclosed')
    with pytest.raises(io.CanonicalWindowCsvReadError):
        read(path)
    report = validate(path)
    assert not report.passed and report.row_count is None and len(report.issues) == 1


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "field,value",
    (
        ("right_endpoint_inclusive", "True"),
        ("right_endpoint_inclusive", "1"),
        ("window_index", "00"),
        ("n_contact_frames", "2.0"),
        ("n_contact_frames", "+2"),
        ("n_contact_frames", " 2"),
        ("n_contact_frames", ""),
        ("occupancy", "NaN"),
        ("occupancy", "Infinity"),
        ("occupancy", "-Infinity"),
        ("occupancy", "1e999"),
        ("occupancy", "0.8"),
        ("coverage_fraction", "0.9"),
        ("condition", "None"),
        ("condition", "null"),
        ("condition", "NA"),
        ("canonical_number", ""),
        ("canonical_number", "0"),
        ("canonical_number", "691"),
        ("canonical_number", "330.0"),
        ("canonical_name", "MET"),
        ("canonical_name", ""),
        ("protein_resid", ""),
    ),
)
def test_strict_scalar_and_pinned_reference_validation(tmp_path, kind, field, value):
    write, read, validate = api(kind)
    path = write(build(kind), tmp_path).output_path
    rows = csv_rows(path)
    prefix = "target_" if kind == "edge" else ""
    field = {
        "canonical_number": f"{prefix}canonical_residue_number",
        "canonical_name": f"{prefix}canonical_resname",
        "protein_resid": "target_resid" if kind == "edge" else "protein_resid",
    }.get(field, field)
    rows[1][rows[0].index(field)] = value
    write_rows(path, rows)
    with pytest.raises(io.CanonicalWindowCsvReadError):
        read(path)
    assert not validate(path).passed


@pytest.mark.parametrize("kind", ("lipid", "glycan"))
@pytest.mark.parametrize("value", ("", "40;40", "41;40", "040;41", "40; 41", "(40,41)"))
def test_component_membership_encoding_is_strict(tmp_path, kind, value):
    write, read, _ = api(kind)
    path = write(build(kind), tmp_path).output_path
    rows = csv_rows(path)
    rows[1][rows[0].index(f"{kind}_component_residue_indexes")] = value
    write_rows(path, rows)
    with pytest.raises(io.CanonicalWindowCsvReadError):
        read(path)


@pytest.mark.parametrize("kind", KINDS)
def test_atomic_replace_and_task_owned_cleanup(tmp_path, monkeypatch, kind):
    write, read, _ = api(kind)
    original = build(kind)
    path = write(original, tmp_path).output_path
    replacement = type(original)((replace(original.rows[0], condition="changed"),))
    before = path.read_bytes()
    sentinel = tmp_path / "user-owned.tmp"
    sentinel.write_text("preserve", encoding="utf-8")
    real_replace = atomic.os.replace
    calls = []

    def replace_spy(temporary, target):
        assert path.read_bytes() == before
        assert read(temporary) == replacement
        assert temporary.parent == path.parent
        calls.append(temporary)
        real_replace(temporary, target)

    monkeypatch.setattr(atomic.os, "replace", replace_spy)
    assert write(replacement, tmp_path, overwrite=True).passed
    assert len(calls) == 1 and not calls[0].exists()
    assert read(path) == replacement
    preserved = path.read_bytes()

    def fail(*args, **kwargs):
        raise OSError("synthetic atomic publication failure")

    monkeypatch.setattr(atomic.os, "replace", fail)
    result = write(original, tmp_path, overwrite=True)
    assert not result.passed and result.error == "Filesystem write failed."
    assert path.read_bytes() == preserved
    assert set(tmp_path.iterdir()) == {path, sentinel}
    assert sentinel.read_text() == "preserve"


@pytest.mark.parametrize("kind", KINDS)
def test_no_clobber_race_and_temp_cleanup(tmp_path, monkeypatch, kind):
    write, _, _ = api(kind)
    real_link = atomic.os.link

    def competing_writer(temporary, target):
        target.write_bytes(b"concurrent writer\n")
        real_link(temporary, target)

    monkeypatch.setattr(atomic.os, "link", competing_writer)
    result = write(build(kind), tmp_path)
    assert not result.passed and result.error == "Target already exists."
    assert result.output_path.read_bytes() == b"concurrent writer\n"
    assert list(tmp_path.iterdir()) == [result.output_path]


@pytest.mark.parametrize("kind", KINDS)
def test_revalidation_before_writes_and_argument_checks(tmp_path, kind):
    write, read, validate = api(kind)
    table = build(kind)
    for bad in (object(), SOURCE_TYPES[kind](())):
        with pytest.raises(ValueError):
            write(bad, tmp_path)
    with pytest.raises(ValueError):
        write(table, tmp_path, overwrite=1)
    with pytest.raises(ValueError):
        write(table, "")
    object.__setattr__(table, "canonical_reference_id", "invalid")
    with pytest.raises(model.CanonicalWindowTableError):
        write(table, tmp_path)
    assert not list(tmp_path.iterdir())
    assert not validate(tmp_path / "missing").passed
    with pytest.raises(io.CanonicalWindowCsvReadError):
        read(tmp_path)
    table = build(kind)
    prefix = "target_" if kind == "edge" else ""
    object.__setattr__(table.rows[0], f"{prefix}canonical_resname", "MET")
    with pytest.raises(model.CanonicalWindowTableError):
        write(table, tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("kind", KINDS)
def test_validation_wrapper_calls_strict_reader_once(tmp_path, monkeypatch, kind):
    write, read, validate = api(kind)
    path = write(build(kind), tmp_path).output_path
    calls = []

    def spy(target):
        calls.append(target)
        return read(target)

    monkeypatch.setattr(io, f"read_canonical_protein_{kind}_window_csv", spy)
    assert validate(path).passed
    assert calls == [path]


def test_glycan_topology_linkage_atoms_survive_csv(tmp_path):
    row = source_row(
        "glycan",
        linkage_evidence="topology_connectivity",
        carrier_link_atom_index=80,
        first_sugar_link_atom_index=90,
    )
    table = build("glycan", (row,))
    write, read, _ = api("glycan")
    result = read(write(table, tmp_path).output_path).rows[0]
    for name in (
        "carrier_residue_index",
        "first_sugar_residue_index",
        "linkage_evidence",
        "carrier_link_atom_index",
        "first_sugar_link_atom_index",
    ):
        assert getattr(result, name) == getattr(row, name)
    assert result.carrier_residue_index == 9 and result.canonical_residue_number == 330


@pytest.mark.parametrize("engine", ("gromacs", "namd"))
def test_offline_cross_layer_variant_namespace_and_orientation_smoke(
    tmp_path, monkeypatch, engine
):
    def blocked(*args, **kwargs):
        raise AssertionError("Network/process/Git access forbidden in pure smoke")

    for owner, name in (
        (socket, "socket"),
        (socket, "create_connection"),
        (urllib.request, "urlopen"),
        (subprocess, "Popen"),
        (subprocess, "run"),
        (os, "system"),
        (os, "popen"),
    ):
        monkeypatch.setattr(owner, name, blocked)
    assigned = bindings(
        mapping_table(
            tuple(replace(r, source_engine=engine) for r in mapping_table().mappings)
        )
    )
    identities, temporal = [], []
    for kind in KINDS:
        row = source_row(
            kind, engine=engine, condition=None if engine == "namd" else "NORM"
        )
        table = build(kind, (row,), assigned)
        write, read, validate = api(kind)
        outcome = write(table, tmp_path / kind)
        assert outcome.passed and validate(outcome.output_path).passed
        actual = read(outcome.output_path).rows[0]
        identities.append(tuple(getattr(actual, name) for name in tuple(COMMON)[:8]))
        temporal.append(tuple(getattr(actual, name) for name in tuple(COMMON)[8:]))
        for name in METRICS:
            assert getattr(actual, name) == getattr(row, name)
        prefix = "target_" if kind == "edge" else ""
        source_prefix = "target_" if kind == "edge" else "protein_"
        assert (
            getattr(actual, f"{source_prefix}resid"),
            getattr(actual, f"{source_prefix}resname"),
            getattr(actual, f"{prefix}canonical_residue_number"),
            getattr(actual, f"{prefix}canonical_resname"),
        ) == ("330", "MET", 330, "THR")
        cells = dict(zip(*csv_rows(outcome.output_path), strict=True))
        if kind == "edge":
            assert (
                actual.source_residue_index == 20 and actual.target_residue_index == 10
            )
            assert (
                cells["source_resid"],
                cells["source_canonical_residue_number"],
            ) == ("311", "312")
            assert actual.edge_weight == row.edge_weight
        else:
            assert getattr(actual, f"{kind}_partner_id") == getattr(
                row, f"{kind}_partner_id"
            )
            assert getattr(actual, f"{kind}_component_residue_indexes") == (40, 41)
            assert actual.distance_mean_A == row.distance_mean_A
            assert actual.distance_min_A == row.distance_min_A
        if engine == "namd":
            assert actual.condition is None and cells["condition"] == ""
        empty = build(kind, (), model.DatasetCanonicalResidueMappingBindings(()))
        empty_path = write(empty, tmp_path / kind / "empty").output_path
        assert read(empty_path) == empty and validate(empty_path).row_count == 0
        with pytest.raises(model.CanonicalWindowTableError, match="No explicit"):
            build(kind, (row,), bindings(mapping_table(())))
    assert identities[0] == identities[1] == identities[2]
    assert temporal[0] == temporal[1] == temporal[2]
    numeric = source_row(
        "lipid", engine=engine, protein_resid="311", protein_resname="GLN"
    )
    table = build("lipid", (numeric,), assigned)
    write, read, validate = api("lipid")
    path = write(table, tmp_path / "numeric").output_path
    assert read(path).rows[0].canonical_residue_number == 312
    cells = dict(zip(*csv_rows(path), strict=True))
    assert (cells["protein_resid"], cells["canonical_residue_number"]) == ("311", "312")
    with pytest.raises(model.CanonicalWindowTableError, match="No explicit"):
        build("lipid", (numeric,), bindings(mapping_table((mapped(engine=engine),))))
    reverse = mapping_table(
        (mapped(number=400, engine=engine), mapped("311", "GLN", 300, engine=engine))
    )
    result = build(
        "edge", (source_row("edge", engine=engine),), bindings(reverse)
    ).rows[0]
    assert (
        result.source_canonical_residue_number,
        result.target_canonical_residue_number,
    ) == (300, 400)


@pytest.mark.parametrize("damage", ("reverse", "self_loop"))
def test_reader_rejects_invalid_canonical_edge_orientation(tmp_path, damage):
    write, read, _ = api("edge")
    path = write(build("edge"), tmp_path).output_path
    rows = csv_rows(path)
    values = dict(zip(rows[0], rows[1], strict=True))
    if damage == "reverse":
        for suffix in (
            "residue_index",
            "chain_id",
            "resid",
            "resname",
            "canonical_residue_number",
            "canonical_resname",
        ):
            source, target = f"source_{suffix}", f"target_{suffix}"
            values[source], values[target] = values[target], values[source]
    else:
        values["source_canonical_residue_number"] = "330"
        values["source_canonical_resname"] = "THR"
    rows[1] = [values[name] for name in rows[0]]
    write_rows(path, rows)
    with pytest.raises(io.CanonicalWindowCsvReadError):
        read(path)
