"""Strict source CSV contracts, nullable identity, duplicates, malformed scalars."""

import csv
from dataclasses import replace

import pytest
from test_preprocessing_protein_edge_window_table import table_input
from test_preprocessing_specialized_contact_windows import aggregate, frames

from mania.preprocessing import specialized_contact_window_tables as tables
from mania.preprocessing import specialized_contact_window_tables_io as io


def table(kind="lipid", *, empty=False, **kwargs):
    binding = table_input(condition=None, engine="namd", **kwargs).temporal_execution
    result = aggregate(
        binding, frames(binding, kind=kind, positive=() if empty else (0, 3)), kind
    )
    return getattr(tables, f"build_protein_{kind}_window_table")(((binding, result),))


@pytest.mark.parametrize("kind", ["lipid", "glycan"])
@pytest.mark.parametrize("empty", [False, True])
def test_source_roundtrip_exact_headers_and_blank_nullable_cells(tmp_path, kind, empty):
    value = table(kind, empty=empty)
    write = getattr(io, f"write_protein_{kind}_window_csv")
    read = getattr(io, f"read_protein_{kind}_window_csv")
    validate = getattr(io, f"validate_protein_{kind}_window_csv")
    written = write(value, tmp_path)
    assert written.passed and read(written.output_path) == value
    assert validate(written.output_path).passed
    with written.output_path.open(newline="") as stream:
        contents = list(csv.reader(stream))
    assert tuple(contents[0]) == getattr(
        io, f"PROTEIN_{kind.upper()}_WINDOW_CSV_COLUMNS"
    )
    assert len(contents) == 1 + value.row_count
    for forbidden in (
        "edge_weight",
        "canonical_residue_number",
        "canonical_resname",
        "mapping_status",
    ):
        assert forbidden not in contents[0]
    if not empty:
        row = dict(zip(contents[0], contents[1], strict=True))
        assert row["condition"] == row["protein_chain_id"] == ""
        assert row[f"{kind}_component_residue_indexes"] == "20"
        assert row["protein_resid"] == "11A"
        if kind == "glycan":
            assert (
                row["carrier_link_atom_index"]
                == row["first_sugar_link_atom_index"]
                == ""
            )
    content = written.output_path.read_bytes()
    assert not write(value, tmp_path).passed
    assert write(value, tmp_path, overwrite=True).passed
    assert written.output_path.read_bytes() == content


@pytest.mark.parametrize("kind", ["lipid", "glycan"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("component", "20;20"),
        ("component", "21;20"),
        ("component", "20; 21"),
        ("component", ""),
        ("component", "(20,)"),
        ("component", "020"),
        ("occupancy", "nan"),
        ("occupancy", "0.9"),
        ("distance_mean_A", "100"),
        ("distance_min_A", "4.0"),
        ("n_contact_frames", "2.0"),
        ("n_contact_frames", "0"),
        ("window_index", "2"),
        ("right_endpoint_inclusive", "True"),
        ("condition", "None"),
        ("condition", "null"),
        ("condition", "NA"),
        ("coverage_fraction", "0.5"),
        ("resolved_frame_count", "0"),
    ],
)
def test_strict_scalar_and_metric_validation(tmp_path, kind, field, value):
    written = getattr(io, f"write_protein_{kind}_window_csv")(table(kind), tmp_path)
    with written.output_path.open(newline="") as stream:
        rows = list(csv.reader(stream))
    field = f"{kind}_component_residue_indexes" if field == "component" else field
    rows[1][rows[0].index(field)] = value
    with written.output_path.open("w", newline="") as stream:
        csv.writer(stream).writerows(rows)
    assert not getattr(io, f"validate_protein_{kind}_window_csv")(
        written.output_path
    ).passed


@pytest.mark.parametrize("kind", ["lipid", "glycan"])
@pytest.mark.parametrize("damage", ["header", "extra", "missing", "duplicate", "order"])
def test_strict_structure_and_identity(tmp_path, kind, damage):
    first = table(kind).rows[0]
    second = replace(first, protein_residue_index=9)
    value = type(table(kind))((first, second))
    path = getattr(io, f"write_protein_{kind}_window_csv")(value, tmp_path).output_path
    with path.open(newline="") as stream:
        rows = list(csv.reader(stream))
    if damage == "header":
        rows[0] = list(reversed(rows[0]))
    elif damage == "extra":
        rows[1].append("unexpected")
    elif damage == "missing":
        rows[1].pop()
    elif damage == "duplicate":
        rows.append(rows[1])
    else:
        rows[1], rows[2] = rows[2], rows[1]
    with path.open("w", newline="") as stream:
        csv.writer(stream).writerows(rows)
    with pytest.raises(io.SpecializedContactWindowCsvReadError):
        getattr(io, f"read_protein_{kind}_window_csv")(path)


def test_components_encoding_and_independent_replica_identity(tmp_path):
    row = table().rows[0]
    row = replace(row, lipid_component_residue_indexes=(20, 21, 22))
    second = replace(row, replica_id="2")
    value = tables.ProteinLipidWindowTable((row, second))
    path = io.write_protein_lipid_window_csv(value, tmp_path).output_path
    assert "20;21;22" in path.read_text()
    assert io.read_protein_lipid_window_csv(path) == value
    with pytest.raises(ValueError):
        tables.ProteinLipidWindowTable((row, row))


@pytest.mark.parametrize("kind", ["lipid", "glycan"])
def test_single_observation_and_episode_statistics_must_agree(kind):
    row = table(kind).rows[0]
    with pytest.raises(ValueError, match="One positive frame"):
        replace(
            row,
            n_contact_frames=1,
            occupancy=0.2,
            n_contact_episodes=1,
            distance_mean_A=3.5,
        )
    with pytest.raises(ValueError, match="One episode"):
        replace(
            row,
            n_contact_episodes=1,
            mean_episode_length_ns=0.0,
            max_episode_length_ns=0.1,
        )
