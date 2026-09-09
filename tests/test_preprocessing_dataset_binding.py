"""Exact Dataset identity binding without scientific work or inferred labels."""

import ast
import builtins
import csv
import io
import os
import subprocess
import time
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from test_preprocessing_dataset_spec_manifest import (
    LEGACY_ENTRY,
    REQUESTED,
    spec_payload,
)

import mania.preprocessing.dataset_binding as binding
from mania.dataset_identity import DatasetTrajectorySpec
from mania.dataset_parameter_table import DATASET_PARAMETER_TABLE_COLUMNS
from mania.preprocessing.input_manifest import PreprocessingInputManifest


def spec(**changes):
    return DatasetTrajectorySpec.model_validate(spec_payload(**changes))


def reference(value):
    return dict(
        zip(
            ("dataset_id", "system_id", "trajectory_id", "replica_id"),
            value.identity.replica_key,
            strict=True,
        )
    )


def manifest(*entries, table=None):
    return PreprocessingInputManifest.model_validate(
        {
            "output_root": "out",
            "conditions": entries,
            "dataset_parameter_table_path": table,
        }
    )


def table_bytes(*specs):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=DATASET_PARAMETER_TABLE_COLUMNS)
    writer.writeheader()
    for value in specs:
        writer.writerow(value.identity.to_dict() | value.temporal.to_dict())
    return stream.getvalue().encode("utf-8")


def write_table(path, *specs):
    path.write_bytes(table_bytes(*specs))
    return path


def forbid(*args, **kwargs):
    raise AssertionError("Unexpected filesystem, runtime, clock, or process access")


@pytest.mark.parametrize("inline", [False, True])
def test_no_table_is_pure_and_requested_values_are_inert(monkeypatch, inline):
    value = spec()
    source = manifest(LEGACY_ENTRY | ({"dataset_spec": value} if inline else {}))
    with monkeypatch.context() as guard:
        for name in (
            "open",
            "exists",
            "is_file",
            "resolve",
            "iterdir",
            "glob",
            "rglob",
        ):
            guard.setattr(Path, name, forbid)
        guard.setattr(builtins, "open", forbid)
        guard.setattr(io, "open", forbid)
        guard.setattr(os, "walk", forbid)
        guard.setattr(subprocess, "run", forbid)
        guard.setattr(subprocess, "Popen", forbid)
        guard.setattr(time, "time", forbid)
        guard.setattr(time, "monotonic", forbid)
        reader = Mock(side_effect=forbid)
        guard.setattr(binding, "read_dataset_parameter_table_csv", reader)
        result = binding.resolve_preprocessing_dataset_context(source)
        reader.assert_not_called()
    assert result.parameter_table_local_path is None
    if inline:
        item = result.context.bindings[0]
        assert item.source == "inline_manifest"
        assert item.dataset_spec.to_dict() == value.to_dict()
        assert item.dataset_spec.temporal.to_dict() == REQUESTED
    else:
        assert result.context is None


def test_order_and_portable_strict_reconstruction():
    source = manifest(
        LEGACY_ENTRY | {"condition": "second", "dataset_spec": spec(condition=None)},
        LEGACY_ENTRY | {"condition": "legacy"},
        LEGACY_ENTRY
        | {"condition": "first", "dataset_spec": spec(condition=None, replica_id="B")},
    )
    result = binding.resolve_preprocessing_dataset_context(source)
    context = result.context
    assert [b.execution_condition for b in context.bindings] == ["second", "first"]
    data = context.to_dict()
    assert list(data) == ["schema_version", "kind", "bindings"]
    assert list(data["bindings"][0]) == [
        "execution_condition",
        "source",
        "dataset_spec",
    ]
    assert binding.PreprocessingDatasetContext.from_dict(data) == context
    assert not hasattr(result, "to_dict")
    with pytest.raises(FrozenInstanceError):
        result.context = None
    with pytest.raises(ValidationError):
        context.bindings = ()
    assert all(b.dataset_spec.identity.condition is None for b in context.bindings)


@pytest.mark.parametrize("condition", ["NORM", None])
def test_table_exact_key_among_repeated_conditions_and_unused_rows(tmp_path, condition):
    specs = [
        spec(engine="namd", condition=condition, replica_id=str(n)) for n in range(3)
    ]
    table = write_table(tmp_path / "parameters.csv", *specs)
    source = manifest(
        LEGACY_ENTRY | {"dataset_ref": reference(specs[2])}, table=table.name
    )
    resolved = binding.resolve_preprocessing_dataset_context(source, base_dir=tmp_path)
    assert resolved.parameter_table_local_path == table
    item = resolved.context.bindings[0]
    assert item.source == "parameter_table"
    assert item.dataset_spec == specs[2]
    assert item.dataset_spec.identity.condition == condition
    assert str(tmp_path) not in str(resolved.context.to_dict())
    with pytest.raises(
        binding.PreprocessingDatasetBindingError, match="explicit base_dir"
    ):
        binding.resolve_preprocessing_dataset_context(source)


@pytest.mark.parametrize("with_ref", [False, True])
def test_identical_inline_and_table(tmp_path, with_ref):
    value = spec()
    table = write_table(tmp_path / "parameters.csv", value)
    entry = LEGACY_ENTRY | {"dataset_spec": value}
    if with_ref:
        entry["dataset_ref"] = reference(value)
    result = binding.resolve_preprocessing_dataset_context(manifest(entry, table=table))
    assert result.context.bindings[0].source == "inline_and_parameter_table"
    assert result.context.bindings[0].dataset_spec.to_dict() == value.to_dict()


@pytest.mark.parametrize(
    "section,field,value",
    [
        ("temporal", field, value)
        for field, value in (
            ("production_start_ns", 0.25),
            ("production_end_ns", 99.0),
            ("frame_stride_ps", 19.0),
            ("window_length_ns", 8.0),
            ("window_step_ns", 4.0),
            ("overlap_percent", 43.0),
        )
    ]
    + [
        ("identity", "engine", "namd"),
        ("identity", "condition", None),
        ("identity", "disulfide_state", "0SS"),
        ("identity", "variant_id", "different"),
    ],
)
def test_full_spec_conflicts_fail(tmp_path, section, field, value):
    changed = spec_payload()
    changed[section][field] = value
    table = write_table(
        tmp_path / "parameters.csv", DatasetTrajectorySpec.model_validate(changed)
    )
    source = manifest(LEGACY_ENTRY | {"dataset_spec": spec()}, table=table)
    with pytest.raises(binding.PreprocessingDatasetBindingError, match="conflicts"):
        binding.resolve_preprocessing_dataset_context(source)


@pytest.mark.parametrize("inline", [False, True])
def test_no_fallback_for_missing_key_even_if_condition_matches(tmp_path, inline):
    table = write_table(tmp_path / "parameters.csv", spec(replica_id="different"))
    entry = LEGACY_ENTRY | (
        {"dataset_spec": spec()} if inline else {"dataset_ref": reference(spec())}
    )
    with pytest.raises(
        binding.PreprocessingDatasetBindingError, match="no row for replica_key"
    ):
        binding.resolve_preprocessing_dataset_context(manifest(entry, table=table))


def test_table_scientific_condition_checked_after_identity_lookup(tmp_path):
    value = spec(condition="TUMOR")
    table = write_table(tmp_path / "parameters.csv", value)
    source = manifest(LEGACY_ENTRY | {"dataset_ref": reference(value)}, table=table)
    with pytest.raises(
        binding.PreprocessingDatasetBindingError, match="scientific condition"
    ):
        binding.resolve_preprocessing_dataset_context(source)


@pytest.mark.parametrize("content", [None, b"bad csv\n", b"\xff"])
def test_table_read_errors_are_portable(tmp_path, content):
    table = tmp_path / "private-name.csv"
    if content is not None:
        table.write_bytes(content)
    source = manifest(LEGACY_ENTRY | {"dataset_ref": reference(spec())}, table=table)
    with pytest.raises(binding.PreprocessingDatasetBindingError) as caught:
        binding.resolve_preprocessing_dataset_context(source)
    assert (
        str(caught.value) == "Dataset parameter table could not be read or validated."
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "schema",
        "extra",
        "empty",
        "duplicate",
        "source",
        "spec_tag",
        "spec_extra",
        "missing_identity",
        "condition",
        "whitespace",
    ],
)
def test_context_rejects_malformed_portable_data(mutation):
    context = binding.resolve_preprocessing_dataset_context(
        manifest(LEGACY_ENTRY | {"dataset_spec": spec()})
    ).context
    data = deepcopy(context.to_dict())
    item = data["bindings"][0]
    if mutation == "schema":
        data["schema_version"] = "future"
    elif mutation == "extra":
        data["local_path"] = "private"
    elif mutation == "empty":
        data["bindings"] = []
    elif mutation == "duplicate":
        data["bindings"].append(deepcopy(item))
    elif mutation == "source":
        item["source"] = "guessed"
    elif mutation == "spec_tag":
        item["dataset_spec"]["kind"] = "future"
    elif mutation == "spec_extra":
        item["dataset_spec"]["frames"] = []
    elif mutation == "missing_identity":
        del item["dataset_spec"]["identity"]
    elif mutation == "condition":
        item["execution_condition"] = "different"
    else:
        item["execution_condition"] = " NORM "
    with pytest.raises(
        binding.PreprocessingDatasetBindingError, match="Invalid Dataset context"
    ):
        binding.PreprocessingDatasetContext.from_dict(data)


def test_resolution_local_path_invariant():
    inline = binding.resolve_preprocessing_dataset_context(
        manifest(LEGACY_ENTRY | {"dataset_spec": spec()})
    ).context
    table = binding.PreprocessingDatasetContext(
        bindings=(
            binding.PreprocessingDatasetBinding(
                execution_condition="NORM",
                source="parameter_table",
                dataset_spec=spec(),
            ),
        )
    )
    for context, path in (
        (None, Path("table.csv")),
        (inline, Path("table.csv")),
        (table, None),
    ):
        with pytest.raises(ValueError):
            binding.PreprocessingDatasetResolution(context, path)


def test_binding_module_imports_only_input_contracts():
    tree = ast.parse(Path(binding.__file__).read_text())
    imports = [
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    assert set(imports) <= {
        "dataclasses",
        "pathlib",
        "typing",
        "pydantic",
        "mania.dataset_identity",
        "mania.dataset_parameter_table",
        "mania.preprocessing.input_manifest",
    }
