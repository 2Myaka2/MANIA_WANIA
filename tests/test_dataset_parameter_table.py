"""Stage 26.B external input validation and requested-value preservation."""

import ast
import builtins
import csv
import importlib.metadata
import inspect
import io
import json
import os
import subprocess
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from mania import dataset_parameter_table
from mania.dataset_identity import DatasetTrajectorySpec
from mania.dataset_parameter_table import (
    DATASET_PARAMETER_TABLE_COLUMNS,
    DATASET_PARAMETER_TABLE_KIND,
    DATASET_PARAMETER_TABLE_SCHEMA_VERSION,
    DatasetParameterTable,
    DatasetParameterTableReadError,
    read_dataset_parameter_table_csv,
)

COLUMNS = (
    "dataset_id",
    "system_id",
    "trajectory_id",
    "variant_id",
    "engine",
    "condition",
    "replica_id",
    "disulfide_state",
    "production_start_ns",
    "production_end_ns",
    "frame_stride_ps",
    "window_length_ns",
    "window_step_ns",
    "overlap_percent",
)
ROW = {
    "dataset_id": "development-subset",
    "system_id": "WT-NORM-gromacs",
    "trajectory_id": "trajectory-B",
    "variant_id": "WT",
    "engine": " GROMACS ",
    "condition": "NORM",
    "replica_id": "replica-B",
    "disulfide_state": "",
    "production_start_ns": "0.125",
    "production_end_ns": "100",
    "frame_stride_ps": "17.3",
    "window_length_ns": "7.1",
    "window_step_ns": "3.7",
    "overlap_percent": "42",
}
REQUESTED = {
    "production_start_ns": 0.125,
    "production_end_ns": 100.0,
    "frame_stride_ps": 17.3,
    "window_length_ns": 7.1,
    "window_step_ns": 3.7,
    "overlap_percent": 42.0,
}


def write_table(
    tmp_path: Path,
    rows: list[dict[str, str]],
    columns: tuple[str, ...] = COLUMNS,
) -> Path:
    path = tmp_path / "parameters.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows([row[column] for column in COLUMNS] for row in rows)
    return path


def make_spec(**identity_changes: object) -> DatasetTrajectorySpec:
    return DatasetTrajectorySpec.model_validate(
        {
            "identity": {
                "dataset_id": "development-subset",
                "system_id": "WT-NORM-gromacs",
                "trajectory_id": "trajectory-B",
                "variant_id": "WT",
                "engine": "gromacs",
                "condition": "NORM",
                "replica_id": "replica-B",
            }
            | identity_changes,
            "temporal": REQUESTED,
        }
    )


def test_constants_and_public_api() -> None:
    assert DATASET_PARAMETER_TABLE_COLUMNS == COLUMNS
    assert (
        DATASET_PARAMETER_TABLE_SCHEMA_VERSION == "mania.dataset_parameter_table.v0.1"
    )
    assert DATASET_PARAMETER_TABLE_KIND == "mania_dataset_parameter_table"
    assert issubclass(DatasetParameterTableReadError, ValueError)
    assert set(dataset_parameter_table.__all__) == {
        "DATASET_PARAMETER_TABLE_COLUMNS",
        "DATASET_PARAMETER_TABLE_KIND",
        "DATASET_PARAMETER_TABLE_SCHEMA_VERSION",
        "DatasetParameterTable",
        "DatasetParameterTableReadError",
        "read_dataset_parameter_table_csv",
    }


def test_valid_rows_preserve_order_replicas_and_requested_values(
    tmp_path: Path,
) -> None:
    # NAMD IDs and durations here are synthetic test inputs, not dataset facts.
    rows = [ROW | {"replica_id": replica} for replica in ("B", "A", "C")]
    rows += [
        ROW
        | {
            "trajectory_id": "synthetic-disulfide",
            "engine": " NamD ",
            "condition": "",
            "disulfide_state": "1SS",
        },
        ROW
        | {
            "trajectory_id": "synthetic-ECD",
            "variant_id": "Cys-example",
            "engine": "NAMD",
            "condition": " \t",
            "disulfide_state": " \t",
        },
    ]
    table = read_dataset_parameter_table_csv(write_table(tmp_path, rows))

    assert table.row_count == 5
    assert isinstance(table.specs, tuple)
    assert all(isinstance(spec, DatasetTrajectorySpec) for spec in table.specs)
    assert [spec.identity.replica_id for spec in table.specs[:3]] == ["B", "A", "C"]
    assert [spec.identity.trajectory_id for spec in table.specs] == [
        "trajectory-B",
        "trajectory-B",
        "trajectory-B",
        "synthetic-disulfide",
        "synthetic-ECD",
    ]
    assert [spec.identity.condition for spec in table.specs] == [
        "NORM",
        "NORM",
        "NORM",
        None,
        None,
    ]
    assert [spec.identity.engine for spec in table.specs] == [
        "gromacs",
        "gromacs",
        "gromacs",
        "namd",
        "namd",
    ]
    assert [spec.identity.disulfide_state for spec in table.specs] == [
        None,
        None,
        None,
        "1SS",
        None,
    ]
    for spec in table.specs:
        assert spec.temporal.to_dict() == REQUESTED
        assert vars(spec.temporal) == REQUESTED


def test_single_row_and_string_path_are_valid(tmp_path: Path) -> None:
    table = read_dataset_parameter_table_csv(str(write_table(tmp_path, [ROW])))
    assert table.row_count == 1
    assert table.specs == (make_spec(),)


@pytest.mark.parametrize("field", ["condition", "disulfide_state"])
@pytest.mark.parametrize("value", ["unknown", "pending", "N/A", "none", "null"])
def test_nonempty_optional_labels_are_ordinary_strings(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    table = read_dataset_parameter_table_csv(
        write_table(tmp_path, [ROW | {field: value}])
    )
    assert getattr(table.specs[0].identity, field) == value


def test_csv_quoting_unicode_and_textual_numbers(tmp_path: Path) -> None:
    row = ROW | {
        "dataset_id": 'Subset, "quoted" \u03b1\nsecond line',
        "frame_stride_ps": " 1.73e1 ",
    }
    table = read_dataset_parameter_table_csv(write_table(tmp_path, [row]))
    assert table.specs[0].identity.dataset_id == row["dataset_id"]
    assert table.specs[0].temporal.to_dict() == REQUESTED


@pytest.mark.parametrize(
    "header",
    [
        COLUMNS[:-1],
        COLUMNS + ("extra",),
        (COLUMNS[1], COLUMNS[0], *COLUMNS[2:]),
        (*COLUMNS[:-1], COLUMNS[0]),
    ],
)
def test_header_must_match_exact_columns_and_order(
    tmp_path: Path,
    header: tuple[str, ...],
) -> None:
    with pytest.raises(DatasetParameterTableReadError, match="header must equal"):
        read_dataset_parameter_table_csv(write_table(tmp_path, [ROW], header))


@pytest.mark.parametrize("contents", ["", ",".join(COLUMNS) + "\n"])
def test_empty_and_header_only_files_fail(tmp_path: Path, contents: str) -> None:
    path = tmp_path / "empty.csv"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(DatasetParameterTableReadError):
        read_dataset_parameter_table_csv(path)


@pytest.mark.parametrize(
    "data",
    [
        '"unterminated',
        '"closed"trailing,data\n',
        ",".join(ROW.values()) + ",extra\n",
        ",".join(list(ROW.values())[:-1]) + "\n",
        "\n",
    ],
)
def test_malformed_csv_and_wrong_row_width_fail(tmp_path: Path, data: str) -> None:
    path = tmp_path / "malformed.csv"
    path.write_text(",".join(COLUMNS) + "\n" + data, encoding="utf-8")
    with pytest.raises(DatasetParameterTableReadError):
        read_dataset_parameter_table_csv(path)


@pytest.mark.parametrize("field", COLUMNS[:5] + ("replica_id",))
@pytest.mark.parametrize("value", ["", " \t"])
def test_blank_required_identity_fields_fail(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    with pytest.raises(DatasetParameterTableReadError, match="line 2"):
        read_dataset_parameter_table_csv(write_table(tmp_path, [ROW | {field: value}]))


@pytest.mark.parametrize("engine", ["amber", "other"])
def test_invalid_engine_fails(tmp_path: Path, engine: str) -> None:
    with pytest.raises(DatasetParameterTableReadError, match="engine"):
        read_dataset_parameter_table_csv(
            write_table(tmp_path, [ROW | {"engine": engine}])
        )


@pytest.mark.parametrize("field", COLUMNS[8:])
@pytest.mark.parametrize(
    "value", ["", " \t", "bad", "true", "NaN", "inf", "-Infinity", "1e999"]
)
def test_invalid_numeric_cells_fail(tmp_path: Path, field: str, value: str) -> None:
    with pytest.raises(DatasetParameterTableReadError, match="line 2"):
        read_dataset_parameter_table_csv(write_table(tmp_path, [ROW | {field: value}]))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("production_start_ns", "-1"),
        ("production_end_ns", "0.125"),
        ("production_end_ns", "0"),
        ("frame_stride_ps", "0"),
        ("window_length_ns", "0"),
        ("window_length_ns", "100"),
        ("window_step_ns", "0"),
        ("overlap_percent", "-1"),
        ("overlap_percent", "100"),
    ],
)
def test_stage26a_temporal_constraints_are_authoritative(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    with pytest.raises(DatasetParameterTableReadError):
        read_dataset_parameter_table_csv(write_table(tmp_path, [ROW | {field: value}]))


def test_duplicate_replica_keys_fail_in_reader_and_model(tmp_path: Path) -> None:
    # Scientific labels and engine cannot disambiguate the exact identity key.
    duplicate = ROW | {"condition": "TUMOR", "variant_id": "T330M", "engine": "namd"}
    with pytest.raises(
        DatasetParameterTableReadError, match="Duplicate Dataset replica_key"
    ):
        read_dataset_parameter_table_csv(write_table(tmp_path, [ROW, duplicate]))
    with pytest.raises(ValidationError, match="Duplicate Dataset replica_key"):
        DatasetParameterTable(specs=(make_spec(), make_spec(condition=None)))


@pytest.mark.parametrize(
    "field", ["dataset_id", "system_id", "trajectory_id", "replica_id"]
)
def test_each_replica_key_component_can_distinguish_specs(field: str) -> None:
    table = DatasetParameterTable(
        specs=(make_spec(), make_spec(**{field: "different"}))
    )
    assert table.row_count == 2


@pytest.mark.parametrize("specs", [[], (), [None], ["spec"], [1], [{}], "spec", None])
def test_model_rejects_empty_or_invalid_specs(specs: object) -> None:
    with pytest.raises(ValidationError):
        DatasetParameterTable.model_validate({"specs": specs})


def test_model_is_frozen_with_non_user_schema_tags() -> None:
    table = DatasetParameterTable(specs=(make_spec(),))
    assert list(DatasetParameterTable.model_fields) == ["specs"]
    for field in ("specs", "schema_version", "kind", "row_count"):
        with pytest.raises(ValidationError, match="frozen_instance"):
            setattr(table, field, None)
    for field in ("unexpected", "schema_version", "kind", "row_count"):
        with pytest.raises(ValidationError, match="extra_forbidden"):
            DatasetParameterTable.model_validate({"specs": table.specs, field: "value"})


def test_serialization_order_nested_contract_and_independent_data() -> None:
    specs = (make_spec(), make_spec(replica_id="A", condition=None))
    table = DatasetParameterTable(specs=specs)
    expected = {
        "schema_version": "mania.dataset_parameter_table.v0.1",
        "kind": "mania_dataset_parameter_table",
        "row_count": 2,
        "specs": [spec.to_dict() for spec in specs],
    }
    payload = table.to_dict()
    assert list(payload) == ["schema_version", "kind", "row_count", "specs"]
    assert json.dumps(payload, allow_nan=False) == json.dumps(expected)
    payload["specs"][0]["identity"]["condition"] = "changed"
    assert table.to_dict() == expected
    reconstructed = DatasetParameterTable.model_validate(
        {
            "specs": [spec.model_dump() for spec in specs],
        }
    )
    assert reconstructed == table


@pytest.mark.parametrize("kind", ["missing", "directory", "fifo", "invalid-utf8"])
def test_file_errors_use_public_exception(tmp_path: Path, kind: str) -> None:
    path = tmp_path / "input.csv"
    if kind == "directory":
        path.mkdir()
    elif kind == "fifo":
        if not hasattr(os, "mkfifo"):
            pytest.skip("Named pipes unavailable")
        os.mkfifo(path)
    elif kind == "invalid-utf8":
        path.write_bytes(b"\xff")
    with pytest.raises(DatasetParameterTableReadError):
        read_dataset_parameter_table_csv(path)


def test_module_imports_only_contract_dependencies() -> None:
    tree = ast.parse(inspect.getsource(dataset_parameter_table))
    allowed = {"__future__", "csv", "pathlib", "pydantic", "mania.dataset_identity"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name in allowed for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert node.module in allowed


def test_reading_only_opens_explicit_csv_and_never_runs_science(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = write_table(tmp_path, [ROW])
    real_open = io.open
    opened: list[Path] = []

    def explicit_open(file: object, *args: object, **kwargs: object) -> object:
        assert Path(file) == path
        opened.append(Path(file))
        return real_open(file, *args, **kwargs)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            "Parameter input must not inspect external state or run science"
        )

    real_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object) -> object:
        assert not name.startswith(
            ("MDAnalysis", "mania.preprocessing", "mania.analysis")
        )
        return real_import(name, *args, **kwargs)

    with monkeypatch.context() as guard:
        guard.setattr(io, "open", explicit_open)
        guard.setattr(builtins, "open", forbidden)
        guard.setattr(builtins, "__import__", guarded_import)
        for target, names in (
            (Path, ("glob", "rglob", "iterdir", "cwd", "resolve")),
            (os, ("listdir", "scandir", "getenv", "system")),
            (subprocess, ("run", "Popen", "check_output")),
            (time, ("time", "time_ns", "monotonic", "perf_counter")),
            (importlib.metadata, ("version", "distribution", "distributions")),
        ):
            for name in names:
                guard.setattr(target, name, forbidden)
        table = read_dataset_parameter_table_csv(path)
        payload = table.to_dict()

    assert opened == [path]
    assert vars(table.specs[0].temporal) == REQUESTED
    assert payload["specs"] == [make_spec().to_dict()]
