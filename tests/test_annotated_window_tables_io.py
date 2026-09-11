"""Exact annotated CSV contracts, byte determinism, strict reads, atomic writes."""

import csv
from dataclasses import fields, replace

import pytest
from test_annotated_window_tables import annotate, assigned
from test_biological_annotations import glyco, metadata
from test_canonical_window_tables import KINDS, build

from mania import annotated_window_tables_io as io


def api(kind, action):
    return getattr(io, f"{action}_annotated_canonical_protein_{kind}_window_csv")


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("empty", [False, True])
def test_exact_header_round_trip_determinism_none_and_overwrite(tmp_path, kind, empty):
    original = build(kind)
    original = replace(
        original,
        rows=()
        if empty
        else (replace(original.rows[0], engine="namd", condition=None),),
    )
    table = annotate(kind, original, assigned(metadata(glycosylation_sites=(glyco(),))))
    paths = []
    for root in (tmp_path / "a", tmp_path / "b"):
        written = api(kind, "write")(table, root)
        assert written.passed
        assert api(kind, "read")(written.output_path) == table
        assert api(kind, "validate")(written.output_path).passed
        assert not api(kind, "write")(table, root).passed
        assert api(kind, "write")(table, root, overwrite=True).passed
        paths.append(written.output_path)
    assert paths[0].read_bytes() == paths[1].read_bytes()
    columns = getattr(
        io, f"ANNOTATED_CANONICAL_PROTEIN_{kind.upper()}_WINDOW_CSV_COLUMNS"
    )
    assert tuple(next(csv.reader(paths[0].open()))) == columns
    assert len(list(csv.reader(paths[0].open()))) == (1 if empty else 2)
    if not empty:
        assert columns == tuple(f.name for f in fields(table.rows[0]))


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "mutation",
    [
        "header",
        "extra",
        "missing",
        "bool",
        "region",
        "duplicate",
        "name",
        "details",
        "nan",
        "utf8",
    ],
)
def test_strict_corruption(tmp_path, kind, mutation):
    path = api(kind, "write")(annotate(kind), tmp_path).output_path
    rows = list(csv.reader(path.open()))
    prefix = "source_" if kind == "edge" else ""
    if mutation == "utf8":
        path.write_bytes(b"\xff")
    else:
        if mutation == "header":
            rows[0][0] = "unknown"
        if mutation == "extra":
            rows[1].append("extra")
        if mutation == "missing":
            rows[1].pop()
        if mutation == "bool":
            rows[1][rows[0].index(prefix + "is_ecd")] = "1"
        if mutation == "region":
            rows[1][rows[0].index(prefix + "is_ecd")] = "false"
        if mutation == "duplicate":
            rows.append(rows[1])
        if mutation == "name":
            rows[1][rows[0].index(prefix + "canonical_resname")] = "UNK"
        if mutation == "details":
            rows[1][rows[0].index(prefix + "glycan_name")] = "invented"
        if mutation == "nan":
            rows[1][rows[0].index("occupancy")] = "nan"
        with path.open("w", newline="") as stream:
            csv.writer(stream).writerows(rows)
    with pytest.raises(io.AnnotatedWindowCsvReadError):
        api(kind, "read")(path)
    assert not api(kind, "validate")(path).passed


@pytest.mark.parametrize("kind", KINDS)
def test_atomic_failure(tmp_path, monkeypatch, kind):
    import os

    table = annotate(kind)
    path = api(kind, "write")(table, tmp_path).output_path
    before = path.read_bytes()

    def fail(*args, **kwargs):
        raise OSError("private error")

    monkeypatch.setattr(os, "replace", fail)
    result = api(kind, "write")(table, tmp_path, overwrite=True)
    assert not result.passed
    assert "private" not in result.error
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]
