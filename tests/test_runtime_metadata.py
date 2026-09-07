"""Deterministic contract and observation-boundary tests for Stage 25.E.1."""

import builtins
import importlib
import io
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from importlib import metadata
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

from mania import runtime_metadata as runtime

ENVIRONMENT = {
    "python_version": "3.12.0",
    "python_implementation": "CPython",
    "platform_system": "Linux",
    "platform_release": "6.8.0",
    "platform_machine": "x86_64",
    "numpy_version": "2.0.0",
    "mdanalysis_version": None,
    "pydantic_version": "2.7.0",
    "pyyaml_version": "6.0.0",
}
START = datetime(2026, 1, 1, tzinfo=UTC)


def environment():
    return runtime.RuntimeEnvironment(**ENVIRONMENT)


def performance(**overrides):
    return runtime.RuntimePerformance(
        **{
            "wall_clock_seconds": 12.5,
            "condition_count": 2,
            "sampled_frame_count": 5,
            "seconds_per_sampled_frame": 2.5,
            "contact_frame_count": 4,
            "contact_observation_count": 17,
            **overrides,
        }
    )


def metadata_model(**overrides):
    return runtime.build_runtime_metadata(
        **{
            "run_id": "run-1",
            "workflow": "preprocessing_graph_export",
            "scope": "preprocessing",
            "metadata_path": "runtime_metadata.json",
            "environment": environment(),
            "performance": performance(),
            **overrides,
        }
    )


def guard_observation_io(patch):
    forbidden = Mock(side_effect=AssertionError("unexpected runtime inspection"))
    for owner, names in (
        (builtins, ("open",)),
        (io, ("open",)),
        (Path, ("open", "read_text", "read_bytes", "iterdir", "glob", "rglob", "cwd")),
        (os, ("getenv", "getcwd", "getcwdb", "scandir", "listdir", "system", "popen")),
        (type(os.environ), ("__getitem__", "__iter__", "__len__")),
        (platform, ("node",)),
        (subprocess, ("run", "Popen", "check_output", "call", "check_call")),
        (time, ("time", "time_ns", "monotonic", "perf_counter", "process_time")),
    ):
        for name in names:
            patch.setattr(owner, name, forbidden)
    return forbidden


def test_constants_serialization_order_and_identity_ownership():
    assert runtime.RUNTIME_METADATA_SCHEMA_VERSION == "mania.runtime_metadata.v0.1"
    assert runtime.RUNTIME_METADATA_KIND == "mania_runtime_metadata"
    assert runtime.RUNTIME_METADATA_FILENAME == "runtime_metadata.json"
    root = metadata_model()
    payload = root.to_dict()
    assert list(payload) == [
        "schema_version",
        "kind",
        "run_id",
        "workflow",
        "scope",
        "metadata_path",
        "environment",
        "performance",
    ]
    assert list(payload["environment"]) == list(ENVIRONMENT)
    assert payload["environment"] == ENVIRONMENT
    assert list(payload["performance"]) == [
        "wall_clock_seconds",
        "condition_count",
        "sampled_frame_count",
        "seconds_per_sampled_frame",
        "contact_frame_count",
        "contact_observation_count",
    ]
    assert json.loads(json.dumps(payload, allow_nan=False)) == payload
    assert "software_identity" not in payload and "commit_sha" not in payload
    assert {item.name for item in fields(root)} == set(payload)
    assert {item.name for item in fields(root.environment)} == set(ENVIRONMENT)
    payload["environment"]["python_version"] = "changed"
    assert root.environment.python_version == "3.12.0"
    assert {item.name for item in fields(root) if not item.init} == {
        "schema_version",
        "kind",
    }


@pytest.mark.parametrize(
    "factory,attribute",
    [
        (environment, "python_version"),
        (performance, "wall_clock_seconds"),
        (metadata_model, "run_id"),
    ],
)
def test_dataclasses_are_frozen(factory, attribute):
    with pytest.raises(FrozenInstanceError):
        setattr(factory(), attribute, "changed")


@pytest.mark.parametrize("name", ENVIRONMENT)
@pytest.mark.parametrize("invalid", ["", " ", " value", "value ", 1, False])
def test_environment_requires_stripped_strings(name, invalid):
    with pytest.raises(ValueError):
        runtime.RuntimeEnvironment(**{**ENVIRONMENT, name: invalid})


@pytest.mark.parametrize("name", list(ENVIRONMENT)[:5])
def test_required_environment_fields_cannot_be_none(name):
    with pytest.raises(ValueError):
        runtime.RuntimeEnvironment(**{**ENVIRONMENT, name: None})


@pytest.mark.parametrize("missing", [None, "numpy", "MDAnalysis", "pydantic", "PyYAML"])
def test_collector_uses_only_allowlisted_platform_and_package_metadata(
    monkeypatch, missing
):
    distributions = {
        "numpy": "2.0.0",
        "MDAnalysis": "2.9.0",
        "pydantic": "2.7.0",
        "PyYAML": "6.0.0",
    }
    calls = []

    def version(name):
        calls.append(name)
        if name == missing:
            raise metadata.PackageNotFoundError(name)
        return distributions[name]

    with monkeypatch.context() as patch:
        forbidden = guard_observation_io(patch)
        patch.setattr(importlib, "import_module", forbidden)
        patch.setattr(runtime, "datetime", Mock(now=forbidden, utcnow=forbidden))
        patch.setattr(metadata, "version", version)
        for function, name in (
            ("python_version", "python_version"),
            ("python_implementation", "python_implementation"),
            ("system", "platform_system"),
            ("release", "platform_release"),
            ("machine", "platform_machine"),
        ):
            patch.setattr(platform, function, Mock(return_value=ENVIRONMENT[name]))
        patch.setattr(builtins, "__import__", forbidden)
        collected = runtime.collect_runtime_environment().to_dict()
    assert calls == ["numpy", "MDAnalysis", "pydantic", "PyYAML"]
    assert list(collected) == list(ENVIRONMENT)
    assert list(collected.values())[:5] == list(ENVIRONMENT.values())[:5]
    for name, distribution in zip(list(ENVIRONMENT)[5:], calls, strict=True):
        assert collected[name] == (
            None if distribution == missing else distributions[distribution]
        )
    forbidden.assert_not_called()


@pytest.mark.parametrize(
    "duration,sampled,per_frame",
    [
        (0, 5, 0.0),
        (12.5, 5, 2.5),
        (0.000001, 2, 0.0000005),
        (12.5, 0, None),
        (12.5, None, None),
    ],
)
def test_performance_duration_and_retained_counters(duration, sampled, per_frame):
    result = runtime.build_runtime_performance(
        started_at_utc=START,
        ended_at_utc=START + timedelta(seconds=duration),
        condition_count=2,
        sampled_frame_count=sampled,
        contact_frame_count=4,
        contact_observation_count=17,
    )
    assert result.wall_clock_seconds == duration
    assert result.seconds_per_sampled_frame == per_frame
    assert result.contact_frame_count == 4
    assert result.contact_observation_count == 17
    assert result.sampled_frame_count == sampled


def test_performance_normalizes_non_utc_offsets_before_subtracting():
    start = datetime(2026, 1, 1, 3, tzinfo=timezone(timedelta(hours=3)))
    end = datetime(
        2025, 12, 31, 19, 0, 12, 500000, tzinfo=timezone(timedelta(hours=-5))
    )
    result = runtime.build_runtime_performance(
        started_at_utc=start,
        ended_at_utc=end,
        condition_count=1,
        sampled_frame_count=5,
    )
    assert result.wall_clock_seconds == 12.5
    assert result.seconds_per_sampled_frame == 2.5


def test_performance_normalizes_a_shared_timezone_across_a_fold():
    class FoldTimezone(tzinfo):
        def utcoffset(self, dt):
            return timedelta(hours=2 - dt.fold)

    zone = FoldTimezone()
    start = datetime(2026, 10, 25, 2, tzinfo=zone, fold=0)
    end = datetime(2026, 10, 25, 2, tzinfo=zone, fold=1)
    result = runtime.build_runtime_performance(
        started_at_utc=start,
        ended_at_utc=end,
        condition_count=1,
        sampled_frame_count=2,
    )
    assert result.wall_clock_seconds == 3600.0
    assert result.seconds_per_sampled_frame == 1800.0


@pytest.mark.parametrize("name", ["started_at_utc", "ended_at_utc"])
@pytest.mark.parametrize("invalid", [datetime(2026, 1, 1), None, "2026-01-01"])
def test_performance_requires_aware_datetimes(name, invalid):
    with pytest.raises(ValueError, match="timezone-aware"):
        runtime.build_runtime_performance(
            **{
                "started_at_utc": START,
                "ended_at_utc": START,
                "condition_count": 0,
                name: invalid,
            }
        )


def test_performance_rejects_end_before_start():
    with pytest.raises(ValueError, match="precede"):
        runtime.build_runtime_performance(
            started_at_utc=START,
            ended_at_utc=START - timedelta(microseconds=1),
            condition_count=1,
        )


@pytest.mark.parametrize("name", ["wall_clock_seconds", "seconds_per_sampled_frame"])
@pytest.mark.parametrize(
    "invalid",
    [True, False, -1, "1", float("nan"), float("inf"), -float("inf"), 10**400],
)
def test_performance_rejects_invalid_numbers(name, invalid):
    with pytest.raises(ValueError):
        performance(**{name: invalid})


@pytest.mark.parametrize(
    "name",
    [
        "condition_count",
        "sampled_frame_count",
        "contact_frame_count",
        "contact_observation_count",
    ],
)
@pytest.mark.parametrize(
    "invalid", [True, False, -1, 1.0, "1", float("nan"), float("inf")]
)
def test_performance_rejects_invalid_counters_in_model_and_builder(name, invalid):
    with pytest.raises(ValueError):
        performance(**{name: invalid})
    with pytest.raises(ValueError):
        runtime.build_runtime_performance(
            **{
                "started_at_utc": START,
                "ended_at_utc": START,
                "condition_count": 1,
                name: invalid,
            }
        )


@pytest.mark.parametrize("sampled,seconds", [(None, 0), (0, 0), (1, None)])
def test_performance_requires_seconds_per_frame_consistent_with_availability(
    sampled, seconds
):
    with pytest.raises(ValueError):
        performance(sampled_frame_count=sampled, seconds_per_sampled_frame=seconds)


def test_performance_optional_counters_and_zero_conditions():
    result = runtime.RuntimePerformance(0.0, 0)
    assert list(result.to_dict().values()) == [0.0, 0, None, None, None, None]
    with pytest.raises(ValueError):
        replace(result, condition_count=None)


@pytest.mark.parametrize(
    "scope,path",
    [
        ("preprocessing", "runtime_metadata.json"),
        ("analysis", "analysis/runtime_metadata.json"),
        ("analysis", "runtime_metadata.json"),
        ("preprocessing", "future/runtime_metadata.json"),
    ],
)
def test_portable_paths_without_premature_scope_enforcement(scope, path):
    assert metadata_model(scope=scope, metadata_path=path).metadata_path == path


@pytest.mark.parametrize(
    "path",
    [
        "",
        " runtime_metadata.json",
        "/runtime_metadata.json",
        "./runtime_metadata.json",
        "x/../runtime_metadata.json",
        "x/./runtime_metadata.json",
        "x//runtime_metadata.json",
        "x\\runtime_metadata.json",
        "C:runtime_metadata.json",
        "C:/runtime_metadata.json",
        "https://host/runtime_metadata.json",
        "urn:runtime_metadata.json",
        "x/runtime_metadata.json/",
        "x/not_runtime_metadata.json",
        "runtime_metadata.JSON",
        "x\0/runtime_metadata.json",
        "x\n/runtime_metadata.json",
        None,
    ],
)
def test_invalid_portable_paths_rejected(path):
    with pytest.raises(ValueError):
        metadata_model(metadata_path=path)


@pytest.mark.parametrize(
    "name,invalid",
    [
        ("run_id", ""),
        ("run_id", " x"),
        ("workflow", "x "),
        ("workflow", None),
        ("scope", "other"),
        ("scope", True),
        ("scope", None),
        ("environment", {}),
        ("environment", None),
        ("performance", {}),
        ("performance", None),
    ],
)
def test_metadata_rejects_invalid_caller_fields(name, invalid):
    with pytest.raises(ValueError):
        metadata_model(**{name: invalid})


def test_metadata_requires_exact_nested_models():
    class EnvironmentSubclass(runtime.RuntimeEnvironment):
        pass

    class PerformanceSubclass(runtime.RuntimePerformance):
        pass

    for override in (
        {"environment": EnvironmentSubclass(**ENVIRONMENT)},
        {"performance": PerformanceSubclass(0.0, 0)},
    ):
        with pytest.raises(ValueError, match="exact"):
            metadata_model(**override)


def test_builders_are_pure_and_preserve_input_objects(monkeypatch):
    env = environment()
    snapshot = env.to_dict()

    class GuardedDatetime(datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            raise AssertionError("clock read")

        @classmethod
        def utcnow(cls):
            raise AssertionError("clock read")

    start = GuardedDatetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(seconds=12.5)
    with monkeypatch.context() as patch:
        forbidden = guard_observation_io(patch)
        patch.setattr(runtime, "datetime", GuardedDatetime)
        patch.setattr(metadata, "version", forbidden)
        patch.setattr(runtime, "collect_runtime_environment", forbidden)
        perf = runtime.build_runtime_performance(
            started_at_utc=start,
            ended_at_utc=end,
            condition_count=2,
            sampled_frame_count=5,
        )
        root = runtime.build_runtime_metadata(
            run_id="run-1",
            workflow="analysis",
            scope="analysis",
            metadata_path="analysis/runtime_metadata.json",
            environment=env,
            performance=perf,
        )
        payload = root.to_dict()
    forbidden.assert_not_called()
    assert payload["performance"]["seconds_per_sampled_frame"] == 2.5
    assert root.environment is env and root.performance is perf
    assert env.to_dict() == snapshot
    assert start == START


def test_module_imports_only_standard_library_and_has_exact_public_api(monkeypatch):
    code = compile(Path(runtime.__file__).read_text(), runtime.__file__, "exec")
    isolated = ModuleType("_runtime_metadata_boundary_test")
    original_import = builtins.__import__
    imported = []

    def guarded_import(name, *args, **kwargs):
        imported.append(name)
        assert name.split(".")[0] in sys.stdlib_module_names
        return original_import(name, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setitem(sys.modules, isolated.__name__, isolated)
        patch.setattr(builtins, "__import__", guarded_import)
        patch.setattr(
            metadata, "version", Mock(side_effect=AssertionError("lookup on import"))
        )
        exec(code, isolated.__dict__)
    assert imported
    assert set(runtime.__all__) == {
        "RUNTIME_METADATA_FILENAME",
        "RUNTIME_METADATA_KIND",
        "RUNTIME_METADATA_SCHEMA_VERSION",
        "RuntimeEnvironment",
        "RuntimeMetadata",
        "RuntimeMetadataScope",
        "RuntimePerformance",
        "build_runtime_metadata",
        "build_runtime_performance",
        "collect_runtime_environment",
    }
