"""Frozen headers, strict types, atomic writes and exact numeric serialization."""

import csv
import io
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext

import pytest
from test_dataset_release_metadata import contact_table, synthetic_inputs

import mania.dataset_release_csv as csv_layer
from mania.dataset_release_contract import PUBLICATION_TABLE_SPECS
from mania.dataset_release_csv import (
    METADATA_TABLE_IDS,
    DatasetReleaseTable,
    build_publication_table,
    publication_csv_bytes,
    publication_table_spec,
    read_publication_csv,
    write_publication_csv,
)
from mania.dataset_release_metadata import build_dataset_release_metadata_tables


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    return build_dataset_release_metadata_tables(
        **synthetic_inputs(tmp_path_factory.mktemp("csv-inputs"))
    )


def rewrite(table, tmp_path, transform):
    rows = list(csv.reader(io.StringIO(publication_csv_bytes(table).decode())))
    transform(rows)
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\n").writerows(rows)
    path = tmp_path / table.relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stream.getvalue(), encoding="utf-8")
    return path


def test_exact_headers_from_33a_and_one_final_newline(bundle):
    authority = {t.table_id: t for t in PUBLICATION_TABLE_SPECS}
    assert len(bundle.tables) == 10
    for table in bundle.tables:
        payload = publication_csv_bytes(table)
        assert payload.endswith(b"\n") and not payload.endswith(b"\n\n")
        assert b"\r\n" not in payload
        reader = csv.reader(io.StringIO(payload.decode("utf-8")))
        assert tuple(next(reader)) == tuple(
            c.name for c in authority[table.table_id].columns
        )
        assert table.spec is authority[table.table_id]
        assert table.row_count == len(table.rows)


@pytest.mark.parametrize("table_id", METADATA_TABLE_IDS)
def test_low_level_header_only_roundtrip(table_id, tmp_path):
    table = build_publication_table(table_id, ())
    path = write_publication_csv(table, tmp_path / table.relative_path)
    assert read_publication_csv(table_id, path) == table
    assert path.read_bytes().count(b"\n") == 1


@pytest.mark.parametrize("table_id", METADATA_TABLE_IDS)
def test_duplicate_primary_keys_rejected_in_builder_and_reader(
    bundle, table_id, tmp_path
):
    table = getattr(bundle, table_id)
    with pytest.raises(ValueError, match="Duplicate"):
        build_publication_table(table_id, (table.records()[0], table.records()[0]))
    path = rewrite(table, tmp_path, lambda rows: rows.append(rows[1]))
    with pytest.raises(ValueError, match="Duplicate"):
        read_publication_csv(table_id, path)


@pytest.mark.parametrize(
    "transform",
    [
        lambda rows: rows[0].reverse(),
        lambda rows: rows[0].append("unknown"),
        lambda rows: rows[0].pop(),
        lambda rows: rows[0].__setitem__(0, "unknown"),
        lambda rows: rows[1].append("extra"),
        lambda rows: rows[1].pop(),
        lambda rows: rows.append([]),
    ],
)
def test_strict_header_and_column_count(bundle, tmp_path, transform):
    path = rewrite(bundle.systems, tmp_path, transform)
    with pytest.raises(ValueError, match="header|column count"):
        read_publication_csv("systems", path)


@pytest.mark.parametrize("text", ["True", "False", "1", "0", "yes", "no", "", " true"])
def test_strict_boolean_encodings_rejected(bundle, tmp_path, text):
    def mutate(rows):
        rows[1][rows[0].index("included_in_scientific_release")] = text

    path = rewrite(bundle.simulations, tmp_path, mutate)
    with pytest.raises(ValueError, match="logical type"):
        read_publication_csv("simulations", path)


@pytest.mark.parametrize("text", ["1.0", "+1", "01", "-0", "1e0", " 1", "None"])
def test_strict_integer_encodings_rejected(bundle, tmp_path, text):
    def mutate(rows):
        rows[1][rows[0].index("window_index")] = text

    path = rewrite(bundle.time_windows, tmp_path, mutate)
    with pytest.raises(ValueError, match="logical type"):
        read_publication_csv("time_windows", path)


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), float("-inf"), Decimal("NaN"), True, "0.5"]
)
def test_invalid_model_numbers_rejected(bundle, value):
    row = bundle.time_windows.records()[0]
    row["coverage_fraction"] = value
    with pytest.raises(ValueError):
        build_publication_table("time_windows", (row,))


@pytest.mark.parametrize(
    "text", ["NaN", "Infinity", "-Infinity", "nan", " 1.2", ".5", "1_000", "null"]
)
def test_invalid_csv_numbers_rejected(bundle, tmp_path, text):
    def mutate(rows):
        rows[1][rows[0].index("coverage_fraction")] = text

    path = rewrite(bundle.time_windows, tmp_path, mutate)
    with pytest.raises(ValueError):
        read_publication_csv("time_windows", path)


def test_numeric_fidelity_independent_of_decimal_precision(bundle, tmp_path):
    row = bundle.time_windows.records()[0]
    values = {
        "coverage_fraction": 0.12345678901234567,
        "requested_production_start_ns": Decimal("0.12345678901234567890123456789"),
        "overlap_percent": 33.33333333333333,
        "requested_window_end_ns": 1.0000000000000002,
        "effective_start_ns": 5e-324,
        "effective_end_ns": 1.7976931348623157e308,
    }
    row.update(values)
    with localcontext() as context:
        context.prec = 2
        table = build_publication_table("time_windows", (row,))
        path = write_publication_csv(table, tmp_path / table.relative_path)
        restored = read_publication_csv("time_windows", path)
    assert restored == table
    for name, value in values.items():
        assert restored.records()[0][name] == value
        if type(value) is float:
            assert float(restored.records()[0][name]).hex() == value.hex()


def test_nullable_and_boolean_values_roundtrip_across_all_tables(bundle, tmp_path):
    observed_null_tables = set()
    for table in bundle.tables:
        path = write_publication_csv(table, tmp_path / table.relative_path)
        restored = read_publication_csv(table.table_id, path)
        assert restored == table
        cells = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8"))))[1:]
        for row, csv_row in zip(table.rows, cells, strict=True):
            for value, cell in zip(row, csv_row, strict=True):
                if value is None:
                    observed_null_tables.add(table.table_id)
                    assert cell == ""
                elif type(value) is bool:
                    assert cell == ("true" if value else "false")
    assert {
        "systems",
        "simulations",
        "quality_control",
        "time_windows",
        "residue_annotations",
        "software_versions",
    } <= observed_null_tables


@pytest.mark.parametrize(
    "literal", ["None", "null", "NA", "N/A", 'verbatim, text\nwith a quote: " and Δ']
)
def test_text_is_verbatim_and_not_a_null_sentinel(bundle, tmp_path, literal):
    row = bundle.software_versions.records()[0]
    row["component_name"] = literal
    table = build_publication_table("software_versions", (row,))
    path = write_publication_csv(table, tmp_path / table.relative_path)
    assert (
        read_publication_csv(table.table_id, path).records()[0]["component_name"]
        == literal
    )


def test_contact_empty_text_null_and_containers_remain_distinct(tmp_path):
    table = contact_table()
    path = write_publication_csv(table, tmp_path / table.relative_path)
    restored = read_publication_csv("contact_definitions", path)
    assert restored == table
    by_path = {r["parameter_path"]: r for r in restored.records()}
    assert by_path["$/extra/empty"]["string_value"] == ""
    assert by_path["$/extra/a~1b~0c/0"]["parameter_kind"] == "null"
    assert by_path["$/extra/array"]["parameter_kind"] == "array"
    assert by_path["$/extra/object"]["parameter_kind"] == "object"


def test_immutable_rows_schema_and_snapshot(bundle):
    table = bundle.systems
    with pytest.raises(FrozenInstanceError):
        table.rows = ()
    with pytest.raises(TypeError):
        table.rows[0][0] = "changed"
    with pytest.raises(ValueError):
        DatasetReleaseTable(table.spec, list(table.rows))
    with pytest.raises(ValueError):
        DatasetReleaseTable(table.spec, (list(table.rows[0]),))
    record = table.records()[0]
    record["system_id"] = "changed"
    assert table.records()[0]["system_id"] == "T330M"
    with pytest.raises(ValueError, match="frozen"):
        DatasetReleaseTable(
            replace(table.spec, columns=tuple(reversed(table.spec.columns))), table.rows
        )


@pytest.mark.parametrize(
    "table_id",
    [
        "dataset_manifest",
        "artifact_inventory",
        "provenance",
        "release/dataset_manifest.json",
        "release/artifact_inventory.json",
        "release/provenance.json",
        "replica_aggregation_manifest",
        "dataset_qc_decision_set",
        "protein_edges_by_window_canonical.csv",
        "trajectory_parameters.csv",
        "unknown.csv",
        "unknown",
    ],
)
def test_non_tabular_or_non_publication_ids_rejected(table_id, tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        publication_table_spec(table_id)
    with pytest.raises(ValueError, match="Unsupported"):
        build_publication_table(table_id, ())
    with pytest.raises(ValueError, match="Unsupported"):
        read_publication_csv(table_id, tmp_path / "unused.csv")
    spec = replace(publication_table_spec("systems"), table_id=table_id)
    with pytest.raises(ValueError, match="Unsupported"):
        DatasetReleaseTable(spec, ())
    malformed = build_publication_table("systems", ())
    object.__setattr__(malformed, "spec", spec)
    with pytest.raises(ValueError, match="Unsupported"):
        write_publication_csv(malformed, tmp_path / "unused.csv")
    assert not tuple(tmp_path.iterdir())


def test_exact_seventeen_tabular_publication_ids():
    expected = {
        "systems",
        "simulations",
        "time_windows",
        "contact_definitions",
        "software_versions",
        "quality_control",
        "quality_control_findings",
        "quality_control_evidence",
        "nodes",
        "residue_annotations",
        "protein_edges_by_window",
        "protein_lipid_contacts_by_window",
        "protein_glycan_contacts_by_window",
        "protein_edges_by_window_replica_aggregation",
        "protein_lipid_contacts_by_window_replica_aggregation",
        "protein_glycan_contacts_by_window_replica_aggregation",
        "metrics",
    }
    assert {s.table_id for s in PUBLICATION_TABLE_SPECS} == expected
    for spec in PUBLICATION_TABLE_SPECS:
        assert publication_table_spec(spec.table_id) is spec


@pytest.mark.parametrize(
    "spec", [s for s in PUBLICATION_TABLE_SPECS if s.table_id not in METADATA_TABLE_IDS]
)
def test_seven_science_schemas_use_shared_csv_layer(spec, tmp_path):
    table = build_publication_table(spec.table_id, ())
    assert table == DatasetReleaseTable(spec, ())
    path = write_publication_csv(table, tmp_path / spec.relative_path)
    assert read_publication_csv(spec.table_id, path) == table
    assert path.read_bytes() == (",".join(c.name for c in spec.columns) + "\n").encode()


def test_ten_metadata_models_and_bytes_match_legacy_lookup(bundle, monkeypatch):
    before = tuple((t, publication_csv_bytes(t)) for t in bundle.tables)

    def legacy_lookup(table_id):
        if table_id not in METADATA_TABLE_IDS:
            raise ValueError("Unsupported Stage 33.B table ID")
        return next(s for s in PUBLICATION_TABLE_SPECS if s.table_id == table_id)

    monkeypatch.setattr(csv_layer, "publication_table_spec", legacy_lookup)
    assert len(before) == 10
    for table, payload in before:
        legacy = build_publication_table(table.table_id, table.records())
        assert legacy == table
        assert publication_csv_bytes(legacy) == payload


def test_path_binding_and_atomic_overwrite_protection(bundle, tmp_path):
    with pytest.raises(ValueError, match="exact publication path"):
        write_publication_csv(bundle.systems, tmp_path / "metadata/simulations.csv")
    assert not tuple(tmp_path.iterdir())
    path = write_publication_csv(
        bundle.systems, tmp_path / bundle.systems.relative_path
    )
    before = path.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        write_publication_csv(bundle.systems, path)
    assert path.read_bytes() == before
    write_publication_csv(bundle.systems, path, overwrite=True)
    assert path.read_bytes() == before
    assert sorted(p.name for p in path.parent.iterdir()) == ["systems.csv"]


def test_atomic_failure_preserves_existing_file_and_cleans_temporary(
    bundle, tmp_path, monkeypatch
):
    path = write_publication_csv(
        bundle.systems, tmp_path / bundle.systems.relative_path
    )
    before = path.read_bytes()

    def denied(*args):
        raise OSError("injected atomic replacement failure")

    monkeypatch.setattr("os.replace", denied)
    with pytest.raises(ValueError, match="Filesystem write failed"):
        write_publication_csv(bundle.systems, path, overwrite=True)
    assert path.read_bytes() == before
    assert list(path.parent.iterdir()) == [path]


def test_reader_normalizes_row_order(bundle, tmp_path):
    path = rewrite(
        bundle.time_windows,
        tmp_path,
        lambda rows: rows.__setitem__(slice(1, None), list(reversed(rows[1:]))),
    )
    assert read_publication_csv("time_windows", path) == bundle.time_windows


def test_malformed_utf8_and_csv_fail(tmp_path):
    path = tmp_path / "metadata/systems.csv"
    path.parent.mkdir()
    for payload in (b"\xff", b'"unterminated,quote\n'):
        path.write_bytes(payload)
        with pytest.raises(ValueError):
            read_publication_csv("systems", path)


@pytest.mark.parametrize(
    "path",
    [
        "/absolute/evidence.json",
        "../secret",
        "a/../../secret",
        "~/private",
        "C:/private",
        "a\\b",
        "$HOME/private",
        "a/%HOME%/b",
    ],
)
def test_unsafe_evidence_paths_rejected(bundle, tmp_path, path):
    table = bundle.quality_control_evidence
    row = table.records()[0]
    row["artifact_path"] = path
    with pytest.raises(ValueError, match="portable"):
        build_publication_table(table.table_id, (row,))

    def mutate(rows):
        rows[1][rows[0].index("artifact_path")] = path

    target = rewrite(table, tmp_path, mutate)
    with pytest.raises(ValueError, match="portable"):
        read_publication_csv(table.table_id, target)


@pytest.mark.parametrize(
    "damage", ["root", "parent", "index", "escape", "identity", "discriminator"]
)
def test_contact_reader_rejects_invalid_trees_and_scalar_discriminators(
    tmp_path, damage
):
    table = contact_table()

    def mutate(rows):
        header = rows[0]
        paths = {row[header.index("parameter_path")]: row for row in rows[1:]}
        if damage in ("root", "parent"):
            rows.remove(paths["$" if damage == "root" else "$/extra"])
        elif damage == "index":
            paths["$/extra/a~1b~0c/0"][header.index("parameter_path")] = (
                "$/extra/a~1b~0c/99"
            )
        elif damage == "escape":
            paths["$/extra/empty"][header.index("parameter_path")] = "$/extra/bad~x"
        elif damage == "identity":
            paths["$/extra/empty"][header.index("interaction_type")] = "different"
        else:
            paths["$/extra/empty"][header.index("parameter_kind")] = "null"
            paths["$/extra/empty"][header.index("boolean_value")] = "true"

    path = rewrite(table, tmp_path, mutate)
    with pytest.raises(ValueError):
        read_publication_csv("contact_definitions", path)
