"""Stage 26.A identity validation, requested-value preservation and purity."""

import ast
import builtins
import datetime
import importlib.metadata
import inspect
import io
import json
import os
import subprocess
import time
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from mania import dataset_identity
from mania.dataset_identity import (
    DATASET_TRAJECTORY_SPEC_KIND,
    DATASET_TRAJECTORY_SPEC_SCHEMA_VERSION,
    DATASET_V1_EXPECTED_SYSTEM_COUNT,
    DATASET_V1_EXPECTED_TRAJECTORY_COUNT,
    DatasetEngine,
    DatasetTemporalParameters,
    DatasetTrajectoryIdentity,
    DatasetTrajectorySpec,
)

IDENTITY = {
    "dataset_id": "Dataset-v1.0",
    "system_id": "WT-NORM-gromacs",
    "trajectory_id": "WT-NORM-trajectory-A",
    "variant_id": "WT",
    "engine": "gromacs",
    "condition": "NORM",
    "replica_id": "replica-A",
    "disulfide_state": None,
}
TEMPORAL = {
    "production_start_ns": 0.0,
    "production_end_ns": 100.0,
    "frame_stride_ps": 25.0,
    "window_length_ns": 10.0,
    "window_step_ns": 5.0,
    "overlap_percent": 50.0,
}
ID_FIELDS = ("dataset_id", "system_id", "trajectory_id", "variant_id", "replica_id")
EXAMPLES = [
    pytest.param({}, {}, id="gromacs-wt-norm"),
    pytest.param(
        {
            "system_id": "T330M-TUMOR-gromacs",
            "trajectory_id": "T330M-TUMOR-B",
            "variant_id": "T330M",
            "condition": "TUMOR",
            "replica_id": "B",
        },
        {"production_end_ns": 30.0},
        id="gromacs-t330m-tumor",
    ),
    pytest.param(
        {
            "system_id": "WT-0SS-namd",
            "trajectory_id": "WT-0SS-A",
            "engine": "namd",
            "condition": None,
            "disulfide_state": "0SS",
        },
        {},
        id="namd-disulfide-0ss",
    ),
    pytest.param(
        {
            "system_id": "ECD-Cys-example",
            "trajectory_id": "ECD-Cys-example-A",
            "variant_id": "Cys-example",
            "engine": "namd",
            "condition": None,
        },
        {},
        id="namd-ecd-cys",
    ),
]


def make_identity(**changes: object) -> DatasetTrajectoryIdentity:
    return DatasetTrajectoryIdentity.model_validate(IDENTITY | changes)


def make_temporal(**changes: object) -> DatasetTemporalParameters:
    return DatasetTemporalParameters.model_validate(TEMPORAL | changes)


def test_constants_engine_and_public_api() -> None:
    assert (
        DATASET_TRAJECTORY_SPEC_SCHEMA_VERSION == "mania.dataset_trajectory_spec.v0.1"
    )
    assert DATASET_TRAJECTORY_SPEC_KIND == "mania_dataset_trajectory_spec"
    assert DATASET_V1_EXPECTED_TRAJECTORY_COUNT == 33
    assert DATASET_V1_EXPECTED_SYSTEM_COUNT == 19
    assert get_args(DatasetEngine) == ("gromacs", "namd")
    assert set(dataset_identity.__all__) == {
        "DATASET_TRAJECTORY_SPEC_KIND",
        "DATASET_TRAJECTORY_SPEC_SCHEMA_VERSION",
        "DATASET_V1_EXPECTED_SYSTEM_COUNT",
        "DATASET_V1_EXPECTED_TRAJECTORY_COUNT",
        "DatasetEngine",
        "DatasetTemporalParameters",
        "DatasetTrajectoryIdentity",
        "DatasetTrajectorySpec",
    }
    assert all(hasattr(dataset_identity, name) for name in dataset_identity.__all__)


@pytest.mark.parametrize(("identity_changes", "temporal_changes"), EXAMPLES)
def test_valid_specs_and_exact_json_serialization(
    identity_changes: dict[str, object],
    temporal_changes: dict[str, object],
) -> None:
    # NAMD temporal values and ECD/Cys IDs are synthetic examples, not dataset facts.
    identity = IDENTITY | identity_changes
    temporal = TEMPORAL | temporal_changes
    spec = DatasetTrajectorySpec.model_validate(
        {"identity": identity, "temporal": temporal}
    )
    assert isinstance(spec.identity, DatasetTrajectoryIdentity)
    assert isinstance(spec.temporal, DatasetTemporalParameters)
    expected = {
        "schema_version": "mania.dataset_trajectory_spec.v0.1",
        "kind": "mania_dataset_trajectory_spec",
        "identity": identity,
        "temporal": temporal,
    }
    assert spec.to_dict() == expected
    assert json.dumps(spec.to_dict(), allow_nan=False) == json.dumps(expected)
    assert json.loads(json.dumps(spec.to_dict(), allow_nan=False)) == expected
    assert list(spec.to_dict()) == ["schema_version", "kind", "identity", "temporal"]
    assert list(spec.identity.to_dict()) == list(IDENTITY)
    assert list(spec.temporal.to_dict()) == list(TEMPORAL)
    assert spec.identity.replica_key == (
        identity["dataset_id"],
        identity["system_id"],
        identity["trajectory_id"],
        identity["replica_id"],
    )
    assert isinstance(spec.identity.replica_key, tuple)


@pytest.mark.parametrize("field", ID_FIELDS)
def test_ids_trim_preserve_case_and_accept_non_numeric_naming(field: str) -> None:
    value = "Mixed Case : arbitrary-ID 7"
    identity = make_identity(**{field: f" \t{value}\n "})
    assert getattr(identity, field) == value
    assert identity.to_dict()[field] == value
    for other in ID_FIELDS:
        if other != field:
            assert getattr(identity, other) == IDENTITY[other]


@pytest.mark.parametrize("field", ID_FIELDS)
@pytest.mark.parametrize(
    "value", ["", " \t\n", True, False, 1, 1.5, None, b"ID", [], {}]
)
def test_invalid_identifiers(field: str, value: object) -> None:
    with pytest.raises(ValidationError) as error:
        make_identity(**{field: value})
    assert error.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" GROMACS\t", "gromacs"),
        ("NamD\n", "namd"),
        ("gromacs", "gromacs"),
        ("namd", "namd"),
    ],
)
def test_engine_normalization(value: str, expected: str) -> None:
    assert make_identity(engine=value).engine == expected


@pytest.mark.parametrize("value", ["other", "amber", "", "  ", True, 1, None, b"namd"])
def test_invalid_engine(value: object) -> None:
    with pytest.raises(ValidationError) as error:
        make_identity(engine=value)
    assert error.value.errors()[0]["loc"] == ("engine",)


@pytest.mark.parametrize("field", ["condition", "disulfide_state"])
@pytest.mark.parametrize("value", ["", " \t\n", True, 1, b"label", [], {}])
def test_invalid_optional_labels(field: str, value: object) -> None:
    with pytest.raises(ValidationError) as error:
        make_identity(**{field: value})
    assert error.value.errors()[0]["loc"] == (field,)


def test_optional_labels_are_retained_and_never_inferred() -> None:
    assert make_identity(condition=" NORM\t").condition == "NORM"
    for state in ("0SS", "1SS", "2SS", "synthetic design label"):
        identity = make_identity(
            engine="namd", condition=None, disulfide_state=f" {state} "
        )
        assert identity.disulfide_state == state
        assert identity.to_dict()["condition"] is None
    values = IDENTITY | {"engine": "namd", "condition": None, "variant_id": "WT-2SS"}
    values.pop("disulfide_state")
    identity = DatasetTrajectoryIdentity.model_validate(values)
    assert identity.disulfide_state is None
    assert identity.to_dict()["disulfide_state"] is None
    assert make_identity(condition=None).condition is None
    assert make_identity(condition=None).replica_key == make_identity().replica_key


@pytest.mark.parametrize("field", [*ID_FIELDS, "engine", "condition"])
def test_identity_required_fields_including_nullable_condition(field: str) -> None:
    values = dict(IDENTITY)
    values.pop(field)
    with pytest.raises(ValidationError) as error:
        DatasetTrajectoryIdentity.model_validate(values)
    assert error.value.errors()[0]["type"] == "missing"
    assert error.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize("field", TEMPORAL)
@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), -float("inf"), True, False]
)
def test_temporal_rejects_non_finite_and_booleans(field: str, value: object) -> None:
    with pytest.raises(ValidationError) as error:
        make_temporal(**{field: value})
    assert error.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("production_start_ns", -0.01),
        ("production_end_ns", 0),
        ("production_end_ns", -1),
        ("frame_stride_ps", 0),
        ("frame_stride_ps", -1),
        ("window_length_ns", 0),
        ("window_length_ns", -1),
        ("window_step_ns", 0),
        ("window_step_ns", -1),
        ("overlap_percent", -0.01),
        ("overlap_percent", 100),
        ("overlap_percent", 101),
        ("window_length_ns", 100.01),
    ],
)
def test_temporal_value_bounds(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        make_temporal(**{field: value})


@pytest.mark.parametrize("end", [19, 20])
def test_end_must_exceed_nonzero_start(end: float) -> None:
    with pytest.raises(ValidationError, match="production_end_ns"):
        make_temporal(production_start_ns=20, production_end_ns=end)


def test_window_length_is_checked_against_duration_not_end_time() -> None:
    with pytest.raises(ValidationError, match="production duration"):
        make_temporal(production_start_ns=20, production_end_ns=30, window_length_ns=11)
    temporal = make_temporal(
        production_start_ns=20, production_end_ns=30, window_length_ns=10
    )
    assert temporal.window_length_ns == 10.0


@pytest.mark.parametrize("field", TEMPORAL)
@pytest.mark.parametrize("value", [None, "invalid", [], {}])
def test_temporal_rejects_non_numeric_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        make_temporal(**{field: value})


@pytest.mark.parametrize("field", TEMPORAL)
def test_temporal_fields_are_required(field: str) -> None:
    values = dict(TEMPORAL)
    values.pop(field)
    with pytest.raises(ValidationError) as error:
        DatasetTemporalParameters.model_validate(values)
    assert error.value.errors()[0]["type"] == "missing"


@pytest.mark.parametrize("overlap", [0, 50, 99.999])
def test_requested_values_are_not_converted_or_reconciled(overlap: float) -> None:
    # Non-aligned, independent requests cannot silently become effective values.
    requested = {
        "production_start_ns": 0.125,
        "production_end_ns": 30.875,
        "frame_stride_ps": 17.3,
        "window_length_ns": 7.1,
        "window_step_ns": 3.7,
        "overlap_percent": overlap,
    }
    temporal = DatasetTemporalParameters.model_validate(requested)
    assert temporal.to_dict() == requested
    assert list(DatasetTemporalParameters.model_fields) == list(TEMPORAL)
    assert vars(temporal) == requested
    assert not DatasetTemporalParameters.model_computed_fields
    assert all(type(value) is float for value in temporal.to_dict().values())
    # No upper bound on step or stride is inferred from length or duration.
    assert make_temporal(window_step_ns=200, frame_stride_ps=1_000_000).to_dict() == (
        TEMPORAL | {"window_step_ns": 200.0, "frame_stride_ps": 1_000_000.0}
    )


@pytest.mark.parametrize(
    ("model", "payload", "field"),
    [
        (DatasetTrajectoryIdentity, IDENTITY, "variant_id"),
        (DatasetTemporalParameters, TEMPORAL, "window_length_ns"),
        (
            DatasetTrajectorySpec,
            {"identity": IDENTITY, "temporal": TEMPORAL},
            "identity",
        ),
    ],
)
def test_all_public_models_are_frozen_and_forbid_extra_fields(
    model: type[
        DatasetTrajectoryIdentity | DatasetTemporalParameters | DatasetTrajectorySpec
    ],
    payload: dict[str, object],
    field: str,
) -> None:
    instance = model.model_validate(payload)
    before = instance.to_dict()
    for operation in (
        lambda: setattr(instance, field, None),
        lambda: delattr(instance, field),
    ):
        with pytest.raises(ValidationError) as error:
            operation()
        assert error.value.errors()[0]["type"] == "frozen_instance"
    assert instance.to_dict() == before
    with pytest.raises(ValidationError) as error:
        model.model_validate(payload | {"unexpected": 1})
    assert error.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize("field", ["schema_version", "kind"])
def test_schema_tags_are_not_user_fields(field: str) -> None:
    spec = DatasetTrajectorySpec(identity=make_identity(), temporal=make_temporal())
    assert list(DatasetTrajectorySpec.model_fields) == ["identity", "temporal"]
    assert spec.model_dump() == {"identity": IDENTITY, "temporal": TEMPORAL}
    with pytest.raises(ValidationError, match="extra_forbidden"):
        DatasetTrajectorySpec.model_validate(
            {
                "identity": IDENTITY,
                "temporal": TEMPORAL,
                field: getattr(spec, field),
            }
        )
    with pytest.raises(ValidationError, match="frozen_instance"):
        setattr(spec, field, "replacement")


@pytest.mark.parametrize("field", ["identity", "temporal"])
@pytest.mark.parametrize("value", [None, "invalid", [], 1, {}])
def test_spec_validates_nested_input_types(field: str, value: object) -> None:
    values: dict[str, object] = {"identity": IDENTITY, "temporal": TEMPORAL}
    values[field] = value
    with pytest.raises(ValidationError) as error:
        DatasetTrajectorySpec.model_validate(values)
    assert error.value.errors()[0]["loc"][0] == field


@pytest.mark.parametrize(
    ("field", "bad_nested"),
    [
        ("identity", IDENTITY | {"condition": " "}),
        ("identity", IDENTITY | {"unexpected": 1}),
        ("temporal", TEMPORAL | {"frame_stride_ps": True}),
        ("temporal", TEMPORAL | {"unexpected": 1}),
    ],
)
def test_spec_does_not_bypass_nested_validation(
    field: str,
    bad_nested: dict[str, object],
) -> None:
    values: dict[str, object] = {"identity": IDENTITY, "temporal": TEMPORAL}
    values[field] = bad_nested
    with pytest.raises(ValidationError) as error:
        DatasetTrajectorySpec.model_validate(values)
    assert error.value.errors()[0]["loc"][0] == field


def test_serialized_dictionaries_do_not_mutate_models() -> None:
    spec = DatasetTrajectorySpec(identity=make_identity(), temporal=make_temporal())
    payload = spec.to_dict()
    assert isinstance(payload["identity"], dict)
    assert isinstance(payload["temporal"], dict)
    payload["identity"]["variant_id"] = "changed"
    payload["temporal"]["frame_stride_ps"] = 99
    assert spec.identity.to_dict() == IDENTITY
    assert spec.temporal.to_dict() == TEMPORAL


def test_module_does_not_import_runtime_or_discovery_modules() -> None:
    tree = ast.parse(inspect.getsource(dataset_identity))
    forbidden = {
        "os",
        "pathlib",
        "io",
        "subprocess",
        "time",
        "datetime",
        "importlib",
        "platform",
        "sys",
        "git",
        "MDAnalysis",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            assert name.split(".")[0] not in forbidden, name
            assert not name.startswith("mania."), name
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0


def test_construction_and_serialization_do_not_inspect_external_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Dataset spec must not inspect external state")

    class ForbiddenDateTime(datetime.datetime):
        now = forbidden
        utcnow = forbidden
        today = forbidden

    with monkeypatch.context() as guard:
        for target, names in (
            (builtins, ("open",)),
            (io, ("open",)),
            (
                Path,
                ("open", "read_text", "read_bytes", "stat", "exists", "resolve", "cwd"),
            ),
            (os, ("getenv", "getcwd", "stat", "listdir", "scandir", "system")),
            (type(os.environ), ("__getitem__", "__iter__")),
            (subprocess, ("run", "Popen", "check_output")),
            (time, ("time", "time_ns", "monotonic", "perf_counter")),
            (
                importlib.metadata,
                ("version", "distribution", "distributions", "packages_distributions"),
            ),
        ):
            for name in names:
                guard.setattr(target, name, forbidden)
        guard.setattr(datetime, "datetime", ForbiddenDateTime)
        specs = [
            DatasetTrajectorySpec(identity=make_identity(), temporal=make_temporal()),
            DatasetTrajectorySpec(
                identity=make_identity(engine="namd", condition=None),
                temporal=make_temporal(),
            ),
        ]
        payloads = [spec.to_dict() for spec in specs]
        encoded = json.dumps(payloads, allow_nan=False)

    assert json.loads(encoded) == payloads
    for payload in payloads:
        assert list(payload) == ["schema_version", "kind", "identity", "temporal"]
        assert isinstance(payload["identity"], dict)
        assert list(payload["identity"]) == list(IDENTITY)
        assert payload["temporal"] == TEMPORAL
    assert payloads[1]["identity"]["condition"] is None
