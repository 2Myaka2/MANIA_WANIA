"""Synthetic PBC observations only: no trajectory or coordinate calculations."""

import builtins
import io
import json
import os
import subprocess
import sys
import time
from dataclasses import FrozenInstanceError, fields, replace
from fractions import Fraction
from itertools import repeat
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

from mania.preprocessing import pbc_audit as pbc

BOX = (10.0, 20.0, 30.0, 90.0, 90.0, 90.0)


def observe(dimensions=BOX, *, index=0, condition="normal", time_ps=0.0):
    return pbc.observe_pbc_frame_dimensions(
        condition=condition,
        frame_index=index,
        time_ps=time_ps,
        dimensions=dimensions,
    )


def summary(*dimensions):
    return pbc.summarize_pbc_condition_observations(
        "normal",
        tuple(observe(box, index=index) for index, box in enumerate(dimensions)),
    )


def audit(**overrides):
    return pbc.build_pbc_audit(
        **{
            "run_id": "run-1",
            "workflow": "preprocessing_graph_export",
            "condition_names": ("normal",),
            "observations": (observe(),),
            **overrides,
        }
    )


@pytest.mark.parametrize("dimensions", [BOX, list(BOX), (10, 20, 30, 60, 80, 120)])
def test_valid_dimensions_preserve_lengths_and_non_orthogonal_angles(dimensions):
    result = observe(dimensions, time_ps=None)
    assert result.dimensions_present is True
    assert result.dimensions_valid is True
    assert result.box_lengths_A == tuple(dimensions[:3])
    assert result.box_angles_deg == tuple(dimensions[3:])
    assert result.time_ps is None
    assert json.loads(json.dumps(result.to_dict(), allow_nan=False)) == result.to_dict()
    assert list(result.to_dict()) == [
        "condition",
        "frame_index",
        "time_ps",
        "dimensions_present",
        "dimensions_valid",
        "box_lengths_A",
        "box_angles_deg",
    ]


def test_generic_scalar_iterables_are_copied_without_numpy():
    source = [Fraction(1, 2), 20, 30, 60, 80, 120]
    result = observe(iter(source))
    assert result.box_lengths_A == (0.5, 20.0, 30.0)
    assert result.box_angles_deg == (60.0, 80.0, 120.0)
    source[0] = 100
    assert result.box_lengths_A[0] == 0.5


def test_missing_dimensions():
    result = observe(None)
    assert result.dimensions_present is False
    assert result.dimensions_valid is False
    assert result.box_lengths_A is None and result.box_angles_deg is None


@pytest.mark.parametrize(
    "dimensions",
    [
        (),
        BOX[:5],
        (*BOX, 1),
        42,
        object(),
        "123456",
        b"123456",
        bytearray(b"123456"),
        dict.fromkeys(range(1, 7), 90),
        ("10", *BOX[1:]),
        (None, *BOX[1:]),
        (1j, *BOX[1:]),
        (True, *BOX[1:]),
        (float("nan"), *BOX[1:]),
        (float("inf"), *BOX[1:]),
        (0, *BOX[1:]),
        (-1, *BOX[1:]),
        (*BOX[:3], 0, 90, 90),
        (*BOX[:3], -1, 90, 90),
        (*BOX[:3], float("nan"), 90, 90),
        (*BOX[:3], True, 90, 90),
        (10**400, *BOX[1:]),
        ([10], *BOX[1:]),
    ],
)
def test_ordinary_malformed_dimensions_are_invalid_without_raising(dimensions):
    result = observe(dimensions)
    assert result.dimensions_present is True
    assert result.dimensions_valid is False
    assert result.box_lengths_A is None and result.box_angles_deg is None


def test_malformed_iterables_have_bounded_consumption_and_normal_errors_are_observed():
    assert observe(repeat(90.0)).dimensions_valid is False

    def broken():
        yield 10
        raise ValueError("malformed dimension sequence")

    assert observe(broken()).dimensions_valid is False
    reads = []

    def too_long():
        for index in range(8):
            reads.append(index)
            yield 90

    assert observe(too_long()).dimensions_valid is False
    assert reads == list(range(7))


@pytest.mark.parametrize(
    "name,invalid",
    [
        ("condition", ""),
        ("condition", " normal"),
        ("condition", None),
        ("frame_index", True),
        ("frame_index", -1),
        ("frame_index", 1.0),
        ("time_ps", True),
        ("time_ps", -1),
        ("time_ps", "1"),
        ("time_ps", float("nan")),
        ("time_ps", float("inf")),
        ("time_ps", 10**400),
        ("dimensions_present", 1),
        ("dimensions_valid", 1),
        ("dimensions_present", False),
        ("dimensions_valid", False),
        ("box_lengths_A", None),
        ("box_angles_deg", None),
        ("box_lengths_A", [1, 2, 3]),
        ("box_angles_deg", (90, 90)),
        ("box_lengths_A", (True, 2, 3)),
        ("box_lengths_A", (0, 2, 3)),
        ("box_angles_deg", (90, float("inf"), 90)),
    ],
)
def test_direct_frame_model_rejects_inconsistent_or_invalid_fields(name, invalid):
    with pytest.raises(ValueError):
        replace(observe(), **{name: invalid})


@pytest.mark.parametrize("name", ["box_lengths_A", "box_angles_deg"])
def test_missing_or_invalid_frame_cannot_carry_box_values(name):
    for observation in (observe(None), observe(())):
        with pytest.raises(ValueError):
            replace(observation, **{name: (1, 2, 3)})


@pytest.mark.parametrize(
    "dimensions,status,counts",
    [
        ((), "unavailable", (0, 0, 0, 0, 0)),
        ((None, None), "unavailable", (2, 0, 0, 2, 0)),
        (((), (0, 0)), "invalid", (2, 2, 0, 0, 2)),
        ((None, ()), "invalid", (2, 1, 0, 1, 1)),
        ((BOX, None), "partial", (2, 1, 1, 1, 0)),
        ((BOX, ()), "partial", (2, 2, 1, 0, 1)),
        ((BOX, None, ()), "partial", (3, 2, 1, 1, 1)),
        ((BOX, BOX, BOX), "complete", (3, 3, 3, 0, 0)),
    ],
)
def test_condition_status_and_exact_counts(dimensions, status, counts):
    result = summary(*dimensions)
    assert result.metadata_status == status
    assert (
        result.sampled_frame_count,
        result.dimensions_present_frame_count,
        result.dimensions_valid_frame_count,
        result.dimensions_missing_frame_count,
        result.dimensions_invalid_frame_count,
    ) == counts
    if counts[2] == 0:
        assert result.box_lengths_min_A is None and result.box_lengths_max_A is None
        assert result.box_angles_min_deg is None and result.box_angles_max_deg is None
        assert result.box_varies is None


def test_component_ranges_and_complete_smoke():
    dimensions = (BOX, (12, 18, 32, 80, 100, 90), (9, 22, 31, 100, 85, 120))
    result = summary(*dimensions)
    assert result.metadata_status == "complete"
    assert result.box_lengths_min_A == (9, 18, 30)
    assert result.box_lengths_max_A == (12, 22, 32)
    assert result.box_angles_min_deg == (80, 85, 90)
    assert result.box_angles_max_deg == (100, 100, 120)
    assert result.box_varies is True
    reversed_observations = tuple(
        observe(box, index=index)
        for index, box in reversed(tuple(enumerate(dimensions)))
    )
    assert (
        pbc.summarize_pbc_condition_observations("normal", reversed_observations)
        == result
    )
    payload = result.to_dict()
    assert list(payload) == [
        "condition",
        "metadata_status",
        "sampled_frame_count",
        "dimensions_present_frame_count",
        "dimensions_valid_frame_count",
        "dimensions_missing_frame_count",
        "dimensions_invalid_frame_count",
        "box_lengths_min_A",
        "box_lengths_max_A",
        "box_angles_min_deg",
        "box_angles_max_deg",
        "box_varies",
    ]
    assert json.loads(json.dumps(payload, allow_nan=False)) == payload
    payload["box_lengths_min_A"][0] = 1000
    assert result.box_lengths_min_A[0] == 9


def test_serialization_preserves_directly_supplied_numeric_components():
    first = replace(observe(), box_lengths_A=(2**53, 20, 30))
    second = replace(first, frame_index=1, box_lengths_A=(2**53 + 1, 20, 30))
    result = pbc.summarize_pbc_condition_observations("normal", (first, second))
    payload = json.loads(json.dumps(result.to_dict(), allow_nan=False))
    assert payload["box_lengths_min_A"][0] == 2**53
    assert payload["box_lengths_max_A"][0] == 2**53 + 1
    assert payload["box_varies"] is True


@pytest.mark.parametrize(
    "dimensions,varies",
    [
        ((BOX,), None),
        ((BOX, None, ()), None),
        ((BOX, BOX), False),
        ((BOX, (11, *BOX[1:])), True),
        ((BOX, (*BOX[:3], 80, 90, 90)), True),
    ],
)
def test_box_variation_is_based_only_on_valid_observations(dimensions, varies):
    assert summary(*dimensions).box_varies is varies


@pytest.mark.parametrize(
    "observations",
    [
        [],
        [observe()],
        (object(),),
        (observe(), observe()),
        (observe(condition="tumor"),),
    ],
)
def test_condition_summary_rejects_bad_container_duplicates_and_wrong_condition(
    observations,
):
    with pytest.raises(ValueError):
        pbc.summarize_pbc_condition_observations("normal", observations)


@pytest.mark.parametrize(
    "name",
    [
        "sampled_frame_count",
        "dimensions_present_frame_count",
        "dimensions_valid_frame_count",
        "dimensions_missing_frame_count",
        "dimensions_invalid_frame_count",
    ],
)
@pytest.mark.parametrize("invalid", [True, -1, 1.0, None, float("nan")])
def test_condition_counts_are_nonnegative_ints(name, invalid):
    with pytest.raises(ValueError):
        replace(summary(BOX, BOX), **{name: invalid})


@pytest.mark.parametrize(
    "changes",
    [
        {"sampled_frame_count": 3},
        {"dimensions_present_frame_count": 1},
        {"dimensions_valid_frame_count": 1},
        {"dimensions_missing_frame_count": 1},
        {"dimensions_invalid_frame_count": 1},
        {"metadata_status": "partial"},
        {"metadata_status": "approved"},
        {"box_lengths_min_A": None},
        {"box_angles_max_deg": None},
        {"box_lengths_min_A": (11, 20, 30)},
        {"box_angles_max_deg": (90, 80, 90)},
        {"box_lengths_min_A": (0, 20, 30)},
        {"box_angles_min_deg": [90, 90, 90]},
        {"box_varies": None},
        {"box_varies": True},
        {"box_varies": 0},
    ],
)
def test_condition_model_rejects_inconsistent_aggregates(changes):
    with pytest.raises(ValueError):
        replace(summary(BOX, BOX), **changes)


def test_ranges_and_variation_require_enough_valid_frames():
    with pytest.raises(ValueError):
        replace(summary(), box_lengths_min_A=(1, 2, 3))
    with pytest.raises(ValueError):
        replace(summary(BOX), box_varies=False)
    with pytest.raises(ValueError):
        replace(summary(BOX), box_lengths_max_A=(11, 20, 30))
    with pytest.raises(ValueError):
        replace(summary(BOX, (11, *BOX[1:])), box_varies=False)


def test_root_constants_order_json_and_fixed_scientific_boundary():
    assert pbc.PBC_AUDIT_SCHEMA_VERSION == "mania.pbc_audit.v0.1"
    assert pbc.PBC_AUDIT_KIND == "mania_pbc_audit"
    assert pbc.PBC_AUDIT_FILENAME == "pbc_audit.json"
    assert pbc.PBC_DISTANCE_SEMANTICS == (
        "euclidean_selected_atom_coordinates_without_mania_minimum_image_correction"
    )
    assert pbc.PBC_INTERNAL_MINIMUM_IMAGE_CORRECTION_APPLIED is False
    assert pbc.PBC_SCIENTIFIC_STATUS == "unresolved"
    root = audit()
    payload = root.to_dict()
    assert list(payload) == [
        "schema_version",
        "kind",
        "run_id",
        "workflow",
        "audit_path",
        "distance_semantics",
        "mania_internal_minimum_image_correction_applied",
        "external_pbc_preprocessing_status",
        "scientific_pbc_status",
        "conditions",
    ]
    assert payload["external_pbc_preprocessing_status"] == "undeclared"
    assert payload["mania_internal_minimum_image_correction_applied"] is False
    assert payload["scientific_pbc_status"] == "unresolved"
    assert json.loads(json.dumps(payload, allow_nan=False)) == payload
    assert {item.name for item in fields(root) if not item.init} == {
        "schema_version",
        "kind",
        "distance_semantics",
        "mania_internal_minimum_image_correction_applied",
        "scientific_pbc_status",
    }
    with pytest.raises(ValueError):
        replace(root, scientific_pbc_status="approved")
    with pytest.raises(ValueError):
        replace(root, mania_internal_minimum_image_correction_applied=True)
    assert not {
        "frames",
        "observations",
        "frame_index",
        "time_ps",
        "positions",
    }.intersection(payload["conditions"][0])


@pytest.mark.parametrize(
    "status", ["undeclared", "declared_applied", "declared_not_applied"]
)
def test_external_declarations_do_not_change_scientific_facts(status):
    result = audit(external_pbc_preprocessing_status=status)
    assert result.external_pbc_preprocessing_status == status
    assert result.mania_internal_minimum_image_correction_applied is False
    assert result.scientific_pbc_status == "unresolved"


def test_root_groups_interleaved_observations_and_preserves_declared_order():
    observations = (
        observe(condition="alpha", index=2),
        observe(condition="zeta", index=4),
        observe(None, condition="alpha", index=1),
        observe((), condition="zeta", index=1),
    )
    result = audit(
        condition_names=("zeta", "empty", "alpha"), observations=observations
    )
    assert tuple(item.condition for item in result.conditions) == (
        "zeta",
        "empty",
        "alpha",
    )
    assert tuple(item.metadata_status for item in result.conditions) == (
        "partial",
        "unavailable",
        "partial",
    )
    assert result.conditions[0].dimensions_invalid_frame_count == 1
    assert result.conditions[2].dimensions_missing_frame_count == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"condition_names": ()},
        {"condition_names": []},
        {"condition_names": ["normal"]},
        {"condition_names": ("normal", "normal")},
        {"condition_names": ("",)},
        {"condition_names": ([],)},
        {"condition_names": ("normal ",)},
        {"observations": []},
        {"observations": (object(),)},
        {"observations": (observe(condition="unknown"),)},
        {"observations": (observe(), observe())},
        {"external_pbc_preprocessing_status": "approved"},
        {"external_pbc_preprocessing_status": True},
        {"run_id": ""},
        {"workflow": " x"},
    ],
)
def test_root_builder_rejects_invalid_inputs(changes):
    with pytest.raises(ValueError):
        audit(**changes)


@pytest.mark.parametrize(
    "conditions", [[], [summary()], (object(),), (summary(), summary())]
)
def test_root_model_requires_tuple_of_unique_condition_audits(conditions):
    with pytest.raises(ValueError):
        replace(audit(), conditions=conditions)


@pytest.mark.parametrize("path", ["pbc_audit.json", "future/pbc_audit.json"])
def test_root_portable_path_accepted(path):
    assert audit(audit_path=path).audit_path == path


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/pbc_audit.json",
        "./pbc_audit.json",
        "../pbc_audit.json",
        "x/../pbc_audit.json",
        "x/./pbc_audit.json",
        "x//pbc_audit.json",
        "x\\pbc_audit.json",
        "C:pbc_audit.json",
        "C:/pbc_audit.json",
        "https://host/pbc_audit.json",
        "urn:pbc_audit.json",
        "pbc_audit.json/",
        "not_pbc_audit.json",
        "pbc_audit.JSON",
        " pbc_audit.json",
        "x\0/pbc_audit.json",
        "x\n/pbc_audit.json",
        None,
    ],
)
def test_root_rejects_invalid_portable_paths(path):
    with pytest.raises(ValueError):
        audit(audit_path=path)


@pytest.mark.parametrize(
    "factory,name",
    [
        (observe, "frame_index"),
        (summary, "metadata_status"),
        (audit, "scientific_pbc_status"),
    ],
)
def test_all_models_are_frozen(factory, name):
    with pytest.raises(FrozenInstanceError):
        setattr(factory(), name, "changed")


def test_observation_and_aggregation_do_not_access_external_or_coordinate_apis(
    monkeypatch,
):
    forbidden = Mock(side_effect=AssertionError("unexpected I/O or trajectory access"))
    dimensions = list(BOX)
    unchanged = dimensions.copy()

    class SuppliedDimensions:
        def __iter__(self):
            return iter(dimensions)

        def __getattr__(self, name):
            forbidden(name)

    with monkeypatch.context() as patch:
        for owner, names in (
            (builtins, ("open",)),
            (io, ("open",)),
            (
                Path,
                ("open", "read_text", "read_bytes", "iterdir", "glob", "rglob", "cwd"),
            ),
            (os, ("scandir", "listdir", "getcwd", "getenv", "system", "popen")),
            (time, ("time", "time_ns", "monotonic", "perf_counter", "process_time")),
            (subprocess, ("run", "Popen", "check_output", "call", "check_call")),
        ):
            for name in names:
                patch.setattr(owner, name, forbidden)
        observations = (observe(SuppliedDimensions()), observe(None, index=1))
        result = audit(observations=observations)
        payload = result.to_dict()
    forbidden.assert_not_called()
    assert dimensions == unchanged
    assert observations[0].box_lengths_A == BOX[:3]
    assert payload["conditions"][0]["metadata_status"] == "partial"


def test_module_has_only_standard_library_imports_and_no_transformation_api(
    monkeypatch,
):
    code = compile(Path(pbc.__file__).read_text(), pbc.__file__, "exec")
    isolated = ModuleType("_pbc_audit_boundary_test")
    original_import = builtins.__import__
    imported = []

    def guarded_import(name, *args, **kwargs):
        imported.append(name)
        assert name.split(".")[0] in sys.stdlib_module_names
        return original_import(name, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setitem(sys.modules, isolated.__name__, isolated)
        patch.setattr(builtins, "__import__", guarded_import)
        exec(code, isolated.__dict__)
    assert imported
    assert set(pbc.__all__) == {
        "PBC_AUDIT_FILENAME",
        "PBC_AUDIT_KIND",
        "PBC_AUDIT_SCHEMA_VERSION",
        "PBC_DISTANCE_SEMANTICS",
        "PBC_INTERNAL_MINIMUM_IMAGE_CORRECTION_APPLIED",
        "PBC_SCIENTIFIC_STATUS",
        "ExternalPbcPreprocessingStatus",
        "PbcAudit",
        "PbcConditionAudit",
        "PbcFrameObservation",
        "PbcMetadataStatus",
        "PbcObservationCallback",
        "build_pbc_audit",
        "observe_pbc_frame_dimensions",
        "observe_pbc_timestep_dimensions",
        "summarize_pbc_condition_observations",
    }
    for name in (
        "unwrap",
        "wrap",
        "center",
        "make_whole",
        "minimum_image",
        "apply_pbc_correction",
    ):
        assert not hasattr(pbc, name)
