import builtins
import io
import json
import subprocess
from collections.abc import Mapping
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from pathlib import Path
from types import MappingProxyType
from typing import Any, get_args
from unittest.mock import Mock

import pytest

from mania import run_provenance, software_identity
from mania.run_provenance import (
    RUN_PROVENANCE_FILENAME,
    RUN_PROVENANCE_KIND,
    RUN_PROVENANCE_SCHEMA_VERSION,
    ConditionSamplingProvenance,
    EffectiveFrameSampling,
    PortableArtifactReference,
    RequestedFrameSampling,
    RunProvenance,
    RunProvenanceIssue,
)
from mania.software_identity import SoftwareIdentity

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
END = START + timedelta(seconds=2, microseconds=123456)
IDENTITY = SoftwareIdentity(
    "MANIA", "mania-wania", "0.1.0", None, "unavailable", "unavailable"
)
ROOT_KEYS = [
    "schema_version",
    "kind",
    "run_id",
    "workflow",
    "status",
    "started_at_utc",
    "ended_at_utc",
    "software_identity",
    "command",
    "resolved_configuration",
    "conditions",
    "sampling_by_condition",
    "artifact_references",
    "issues",
]


def make_provenance(**changes: Any) -> RunProvenance:
    values: dict[str, Any] = {
        "run_id": "run-001",
        "workflow": "preprocessing",
        "status": "completed",
        "started_at_utc": START,
        "ended_at_utc": END,
        "software_identity": IDENTITY,
        "command": ("mania", "run", "--config", "configs/example config.yaml"),
        "resolved_configuration": {},
        "conditions": ("normal",),
    }
    return RunProvenance(**(values | changes))


def make_effective(**changes: Any) -> EffectiveFrameSampling:
    values: dict[str, Any] = {
        "source_frame_count": 10,
        "sampled_frame_count": 3,
        "first_source_frame_index": 1,
        "last_source_frame_index": 5,
        "first_time_ps": 2.0,
        "last_time_ps": 10.0,
        "time_spacing_status": "uniform",
        "observed_time_spacing_ps": 4.0,
    }
    return EffectiveFrameSampling(**(values | changes))


def assert_plain_json(value: object) -> None:
    if type(value) is dict:
        for key, item in value.items():
            assert type(key) is str
            assert_plain_json(item)
    elif type(value) is list:
        for item in value:
            assert_plain_json(item)
    else:
        assert type(value) in (type(None), bool, int, float, str)


def test_constants_aliases_and_public_boundary() -> None:
    assert RUN_PROVENANCE_SCHEMA_VERSION == "mania.run_provenance.v0.1"
    assert RUN_PROVENANCE_KIND == "mania_run_provenance"
    assert RUN_PROVENANCE_FILENAME == "run_provenance.json"
    assert get_args(run_provenance.RunProvenanceStatus) == ("completed", "failed")
    assert get_args(run_provenance.RunProvenanceIssueSeverity) == ("warning", "error")
    assert get_args(run_provenance.TimeSpacingStatus) == (
        "uniform",
        "non_uniform",
        "unavailable",
    )
    assert set(run_provenance.__all__) == {
        "RUN_PROVENANCE_SCHEMA_VERSION",
        "RUN_PROVENANCE_KIND",
        "RUN_PROVENANCE_FILENAME",
        "RunProvenanceStatus",
        "RunProvenanceIssueSeverity",
        "TimeSpacingStatus",
        "RequestedFrameSampling",
        "EffectiveFrameSampling",
        "ConditionSamplingProvenance",
        "PortableArtifactReference",
        "RunProvenanceIssue",
        "RunProvenance",
    }
    assert all(hasattr(run_provenance, name) for name in run_provenance.__all__)
    assert {item.name for item in fields(RunProvenance) if not item.init} == {
        "schema_version",
        "kind",
    }


@pytest.mark.parametrize(
    "instance",
    [
        RequestedFrameSampling(),
        make_effective(),
        ConditionSamplingProvenance("normal", RequestedFrameSampling(), None),
        PortableArtifactReference("manifest", "mania_manifest.json"),
        RunProvenanceIssue("warning", "missing_times", "Time metadata unavailable"),
        make_provenance(),
    ],
)
def test_public_dataclasses_are_frozen(instance: Any) -> None:
    name = fields(instance)[0].name
    with pytest.raises(FrozenInstanceError):
        setattr(instance, name, getattr(instance, name))


def test_complete_contract_serialization() -> None:
    provenance = make_provenance(
        sampling_by_condition=(
            ConditionSamplingProvenance(
                "normal", RequestedFrameSampling(1, 8, 2, 3), make_effective()
            ),
        ),
        artifact_references=(
            PortableArtifactReference("preprocessing_manifest", "mania_manifest.json"),
        ),
        issues=(RunProvenanceIssue("warning", "example", "Example warning"),),
        resolved_configuration={"z": (True, None), "a": {"stride": 2}},
    )
    payload = provenance.to_dict()
    assert list(payload) == ROOT_KEYS
    assert payload == {
        "schema_version": "mania.run_provenance.v0.1",
        "kind": "mania_run_provenance",
        "run_id": "run-001",
        "workflow": "preprocessing",
        "status": "completed",
        "started_at_utc": "2026-01-02T03:04:05.000000Z",
        "ended_at_utc": "2026-01-02T03:04:07.123456Z",
        "software_identity": {
            "software_name": "MANIA",
            "distribution_name": "mania-wania",
            "version": "0.1.0",
            "commit_sha": None,
            "commit_source": "unavailable",
            "working_tree_status": "unavailable",
        },
        "command": ["mania", "run", "--config", "configs/example config.yaml"],
        "resolved_configuration": {"a": {"stride": 2}, "z": [True, None]},
        "conditions": ["normal"],
        "sampling_by_condition": [
            {
                "condition": "normal",
                "requested": {
                    "frame_start": 1,
                    "frame_stop": 8,
                    "frame_stride": 2,
                    "max_frames": 3,
                },
                "effective": {
                    "source_frame_count": 10,
                    "sampled_frame_count": 3,
                    "first_source_frame_index": 1,
                    "last_source_frame_index": 5,
                    "first_time_ps": 2.0,
                    "last_time_ps": 10.0,
                    "time_spacing_status": "uniform",
                    "observed_time_spacing_ps": 4.0,
                },
            }
        ],
        "artifact_references": [
            {"role": "preprocessing_manifest", "path": "mania_manifest.json"}
        ],
        "issues": [
            {
                "severity": "warning",
                "code": "example",
                "message": "Example warning",
                "stage": None,
                "condition": None,
            }
        ],
    }
    assert json.loads(json.dumps(payload, allow_nan=False)) == payload
    assert_plain_json(payload)


def test_utc_normalization_and_token_preservation() -> None:
    provenance = make_provenance(
        started_at_utc=START.astimezone(timezone(timedelta(hours=3))),
        ended_at_utc=END.astimezone(timezone(timedelta(hours=-5, minutes=-30))),
        command=("mania", " argument with spaces ", "$(literal)", " "),
    )
    assert provenance.started_at_utc.tzinfo is UTC
    assert provenance.ended_at_utc.tzinfo is UTC
    payload = provenance.to_dict()
    assert payload["started_at_utc"] == "2026-01-02T03:04:05.000000Z"
    assert payload["ended_at_utc"] == "2026-01-02T03:04:07.123456Z"
    assert payload["command"] == ["mania", " argument with spaces ", "$(literal)", " "]
    assert make_provenance(ended_at_utc=START).ended_at_utc == START


@pytest.mark.parametrize(
    "identity",
    [
        IDENTITY,
        replace(
            IDENTITY,
            commit_sha="a" * 40,
            commit_source="git_checkout",
            working_tree_status="clean",
        ),
        replace(
            IDENTITY,
            commit_sha="b" * 40,
            commit_source="git_checkout",
            working_tree_status="dirty",
        ),
        replace(IDENTITY, commit_sha="c" * 40, commit_source="git_checkout"),
    ],
)
def test_identity_is_supplied_without_collection_or_io(
    identity: SoftwareIdentity, monkeypatch: pytest.MonkeyPatch
) -> None:
    forbidden = Mock(side_effect=AssertionError("runtime collection or I/O attempted"))
    with monkeypatch.context() as patch:
        patch.setattr(software_identity, "get_software_identity", forbidden)
        patch.setattr(software_identity, "_run_git", forbidden)
        patch.setattr(subprocess, "Popen", forbidden)
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(io, "open", forbidden)
        for name in (
            "exists",
            "is_file",
            "is_dir",
            "stat",
            "resolve",
            "open",
            "write_text",
            "write_bytes",
        ):
            patch.setattr(Path, name, forbidden)
        reference = PortableArtifactReference("manifest", "absent/mania_manifest.json")
        provenance = make_provenance(
            software_identity=identity, artifact_references=(reference,)
        )
        payload = provenance.to_dict()
        json.dumps(payload, allow_nan=False)
    forbidden.assert_not_called()
    assert provenance.software_identity is identity
    assert payload["software_identity"] == identity.to_dict()
    payload["software_identity"]["version"] = "changed"
    assert provenance.to_dict()["software_identity"] == identity.to_dict()


def test_requested_defaults_and_bounded_sampling() -> None:
    assert RequestedFrameSampling().to_dict() == {
        "frame_start": 0,
        "frame_stop": None,
        "frame_stride": 1,
        "max_frames": None,
    }
    assert RequestedFrameSampling(2, 20, 3, 4).to_dict() == {
        "frame_start": 2,
        "frame_stop": 20,
        "frame_stride": 3,
        "max_frames": 4,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"frame_start": -1},
        {"frame_stop": -1},
        {"frame_stop": 0},
        {"frame_start": 2, "frame_stop": 2},
        {"frame_start": 2, "frame_stop": 1},
        {"frame_stride": -1},
        {"frame_stride": 0},
        {"max_frames": -1},
        {"max_frames": 0},
    ],
)
def test_invalid_requested_bounds(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        RequestedFrameSampling(**changes)


@pytest.mark.parametrize(
    "name", ["frame_start", "frame_stop", "frame_stride", "max_frames"]
)
@pytest.mark.parametrize("value", [True, False, 1.5, "1"])
def test_requested_rejects_non_integer_values(name: str, value: object) -> None:
    with pytest.raises(ValueError):
        RequestedFrameSampling(**{name: value})


@pytest.mark.parametrize("source_count", [None, 0, 10])
def test_zero_frame_observation(source_count: int | None) -> None:
    effective = EffectiveFrameSampling(
        source_count, 0, None, None, None, None, "unavailable", None
    )
    assert effective.to_dict() == {
        "source_frame_count": source_count,
        "sampled_frame_count": 0,
        "first_source_frame_index": None,
        "last_source_frame_index": None,
        "first_time_ps": None,
        "last_time_ps": None,
        "time_spacing_status": "unavailable",
        "observed_time_spacing_ps": None,
    }


@pytest.mark.parametrize(
    "name,value",
    [
        ("first_source_frame_index", 0),
        ("last_source_frame_index", 0),
        ("first_time_ps", 0.0),
        ("last_time_ps", 0.0),
        ("observed_time_spacing_ps", 1.0),
        ("time_spacing_status", "uniform"),
        ("time_spacing_status", "non_uniform"),
    ],
)
def test_zero_frame_rejects_observations(name: str, value: object) -> None:
    zero = EffectiveFrameSampling(None, 0, None, None, None, None, "unavailable", None)
    with pytest.raises(ValueError):
        replace(zero, **{name: value})


def test_one_frame_and_non_uniform_observations() -> None:
    one = EffectiveFrameSampling(None, 1, 3, 3, 6.0, 6.0, "unavailable", None)
    assert one.to_dict()["sampled_frame_count"] == 1
    non_uniform = make_effective(
        time_spacing_status="non_uniform", observed_time_spacing_ps=None
    )
    assert non_uniform.to_dict()["time_spacing_status"] == "non_uniform"
    assert non_uniform.to_dict()["observed_time_spacing_ps"] is None


@pytest.mark.parametrize("first,last", [(None, None), (None, 0.0), (0.0, None), (0, 0)])
@pytest.mark.parametrize(
    "status,spacing", [("uniform", 4.0), ("non_uniform", None), ("unavailable", None)]
)
def test_available_times_are_independent_of_spacing(
    first: float | None, last: float | None, status: str, spacing: float | None
) -> None:
    effective = make_effective(
        source_frame_count=None,
        first_time_ps=first,
        last_time_ps=last,
        time_spacing_status=status,
        observed_time_spacing_ps=spacing,
    )
    assert effective.to_dict()["first_time_ps"] == first
    assert effective.to_dict()["last_time_ps"] == last


@pytest.mark.parametrize(
    "changes",
    [
        {"sampled_frame_count": None},
        {"sampled_frame_count": 11},
        {"source_frame_count": 0},
        {"first_source_frame_index": None},
        {"last_source_frame_index": None},
        {"first_source_frame_index": 6},
        {"first_time_ps": 11.0},
        {"time_spacing_status": "unknown"},
        {"observed_time_spacing_ps": None},
        {"time_spacing_status": "non_uniform"},
        {"time_spacing_status": "unavailable"},
        {"sampled_frame_count": 1},
        {
            "sampled_frame_count": 1,
            "time_spacing_status": "non_uniform",
            "observed_time_spacing_ps": None,
        },
    ],
)
def test_effective_cross_field_validation(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        make_effective(**changes)


@pytest.mark.parametrize(
    "name",
    [
        "source_frame_count",
        "sampled_frame_count",
        "first_source_frame_index",
        "last_source_frame_index",
    ],
)
@pytest.mark.parametrize("value", [-1, True, False, 1.0, "1"])
def test_effective_integer_validation(name: str, value: object) -> None:
    with pytest.raises(ValueError):
        make_effective(**{name: value})


@pytest.mark.parametrize(
    "name", ["first_time_ps", "last_time_ps", "observed_time_spacing_ps"]
)
@pytest.mark.parametrize(
    "value",
    [
        -1.0,
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
        False,
        "1",
        10**400,
    ],
)
def test_effective_time_validation(name: str, value: object) -> None:
    with pytest.raises(ValueError):
        make_effective(**{name: value})


def test_zero_spacing_rejected_and_matching_source_count_accepted() -> None:
    with pytest.raises(ValueError):
        make_effective(observed_time_spacing_ps=0.0)
    assert make_effective(source_frame_count=3).sampled_frame_count == 3


def test_condition_sampling_can_be_unavailable() -> None:
    record = ConditionSamplingProvenance("normal", RequestedFrameSampling(), None)
    assert record.to_dict() == {
        "condition": "normal",
        "requested": RequestedFrameSampling().to_dict(),
        "effective": None,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"condition": ""},
        {"condition": " normal"},
        {"condition": "normal "},
        {"condition": 1},
        {"requested": {}},
        {"requested": None},
        {"effective": {}},
        {"effective": RequestedFrameSampling()},
    ],
)
def test_condition_sampling_validation(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        ConditionSamplingProvenance(
            **(
                {
                    "condition": "normal",
                    "requested": RequestedFrameSampling(),
                    "effective": None,
                }
                | changes
            )
        )


@pytest.mark.parametrize(
    "path", ["mania_manifest.json", "analysis/extended_metrics.json"]
)
def test_portable_references(path: str) -> None:
    assert PortableArtifactReference("manifest", path).to_dict() == {
        "role": "manifest",
        "path": path,
    }


@pytest.mark.parametrize(
    "path",
    [
        "",
        " ",
        "/manifest.json",
        "//host/manifest.json",
        "C:/manifest.json",
        "C:manifest.json",
        "c:",
        "normal\\manifest.json",
        "../manifest.json",
        "normal/../manifest.json",
        "./manifest.json",
        "normal/./manifest.json",
        ".",
        "..",
        "https://example.test/manifest.json",
        "normal//manifest.json",
        "normal/",
        "normal/manifest\0.json",
        Path("manifest.json"),
        None,
    ],
)
def test_invalid_portable_references(path: Any) -> None:
    with pytest.raises(ValueError):
        PortableArtifactReference("manifest", path)


@pytest.mark.parametrize("role", ["", " ", " manifest", "manifest ", None])
def test_invalid_reference_role(role: Any) -> None:
    with pytest.raises(ValueError):
        PortableArtifactReference(role, "manifest.json")


@pytest.mark.parametrize("severity", ["warning", "error"])
def test_issues(severity: Any) -> None:
    issue = RunProvenanceIssue(
        severity, "missing_times", "Times unavailable", "sampling", "normal"
    )
    assert issue.to_dict() == {
        "severity": severity,
        "code": "missing_times",
        "message": "Times unavailable",
        "stage": "sampling",
        "condition": "normal",
    }
    assert make_provenance(status="failed", issues=(issue,)).to_dict()["issues"] == [
        issue.to_dict()
    ]


@pytest.mark.parametrize(
    "changes",
    [
        {"severity": "info"},
        {"severity": None},
        {"code": ""},
        {"message": ""},
        {"code": " padded"},
        {"message": "padded "},
        {"message": ValueError("example")},
        {"stage": ""},
        {"stage": " padded"},
        {"condition": ""},
        {"condition": "normal "},
    ],
)
def test_issue_validation(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        RunProvenanceIssue(
            **(
                {
                    "severity": "warning",
                    "code": "example",
                    "message": "Example warning",
                }
                | changes
            )
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"run_id": ""},
        {"run_id": " run"},
        {"workflow": ""},
        {"workflow": "run "},
        {"status": "running"},
        {"status": None},
        {"software_identity": {}},
        {"started_at_utc": START.replace(tzinfo=None)},
        {"ended_at_utc": END.replace(tzinfo=None)},
        {"started_at_utc": "2026-01-02T03:04:05Z"},
        {"ended_at_utc": None},
        {"ended_at_utc": START - timedelta(microseconds=1)},
        {"command": ()},
        {"command": ("mania", "")},
        {"command": ("mania", 1)},
        {"command": ["mania"]},
        {"command": "mania"},
        {"conditions": ("normal", "normal")},
        {"conditions": ("",)},
        {"conditions": ("normal ",)},
        {"conditions": (1,)},
        {"conditions": ["normal"]},
        {"sampling_by_condition": []},
        {"sampling_by_condition": ({},)},
        {"artifact_references": []},
        {"artifact_references": ({},)},
        {"issues": []},
        {"issues": ({},)},
        {"resolved_configuration": []},
    ],
)
def test_root_validation(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        make_provenance(**changes)


def test_tzinfo_without_offset_is_naive() -> None:
    class NoOffset(tzinfo):
        def utcoffset(self, dt: datetime | None) -> None:
            return None

    with pytest.raises(ValueError):
        make_provenance(started_at_utc=START.replace(tzinfo=NoOffset()))


def test_sampling_and_issue_condition_invariants() -> None:
    record = ConditionSamplingProvenance("normal", RequestedFrameSampling(), None)
    with pytest.raises(ValueError, match="unique"):
        make_provenance(sampling_by_condition=(record, record))
    with pytest.raises(ValueError, match="appear in conditions"):
        make_provenance(sampling_by_condition=(replace(record, condition="unknown"),))
    with pytest.raises(ValueError, match="appear in conditions"):
        make_provenance(
            issues=(
                RunProvenanceIssue(
                    "error", "example", "Example error", condition="unknown"
                ),
            )
        )
    partial = make_provenance(
        conditions=("normal", "tumor"), sampling_by_condition=(record,)
    )
    assert partial.to_dict()["sampling_by_condition"] == [record.to_dict()]
    empty = make_provenance(conditions=()).to_dict()
    for key in ("conditions", "sampling_by_condition", "artifact_references", "issues"):
        assert empty[key] == []


def test_artifact_pairs_must_be_unique() -> None:
    reference = PortableArtifactReference("manifest", "mania_manifest.json")
    with pytest.raises(ValueError, match="unique"):
        make_provenance(artifact_references=(reference, reference))
    distinct = (
        reference,
        replace(reference, role="preprocessing_manifest"),
        replace(reference, path="analysis/extended_metrics.json"),
    )
    assert make_provenance(artifact_references=distinct).to_dict()[
        "artifact_references"
    ] == [item.to_dict() for item in distinct]


def test_configuration_defensive_snapshot_and_independent_exports() -> None:
    original = {
        "z": [1, {"b": [None, True, 2.5], "a": "label"}],
        "a": {"tuple": (False, "value"), "empty": {}},
        "n": 42,
    }
    provenance = make_provenance(resolved_configuration=original)
    expected = {
        "a": {"empty": {}, "tuple": [False, "value"]},
        "n": 42,
        "z": [1, {"a": "label", "b": [None, True, 2.5]}],
    }
    original["z"][1]["b"].append("mutated")
    original["a"]["tuple"] = ()
    original["extra"] = "mutated"
    assert provenance.to_dict()["resolved_configuration"] == expected
    stored = provenance.resolved_configuration
    assert list(stored) == ["a", "n", "z"]
    assert isinstance(stored["a"], Mapping)
    assert isinstance(stored["z"], tuple)
    with pytest.raises(TypeError):
        stored["extra"] = 1
    with pytest.raises(TypeError):
        stored["a"]["extra"] = 1
    with pytest.raises(TypeError):
        stored["z"][0] = 2
    with pytest.raises(TypeError):
        stored["z"][1]["a"] = "changed"
    with pytest.raises(AttributeError):
        stored["z"][1]["b"].append(3)
    first = provenance.to_dict()
    second = provenance.to_dict()
    assert first is not second
    assert first["resolved_configuration"] is not second["resolved_configuration"]
    first["resolved_configuration"]["z"][1]["b"].append("changed")
    first["conditions"].append("changed")
    first["command"][0] = "changed"
    assert second == provenance.to_dict()
    assert second["resolved_configuration"] == expected
    assert_plain_json(second)


def test_mapping_order_is_recursive_and_input_order_independent() -> None:
    one = make_provenance(
        resolved_configuration=MappingProxyType(
            {
                "z": [{"b": 2, "a": 1}],
                "a": MappingProxyType({"z": 0, "a": 1}),
            }
        )
    )
    two = make_provenance(
        resolved_configuration={
            "a": {"a": 1, "z": 0},
            "z": [{"a": 1, "b": 2}],
        }
    )
    output = one.to_dict()["resolved_configuration"]
    assert list(output) == ["a", "z"]
    assert list(output["a"]) == ["a", "z"]
    assert list(output["z"][0]) == ["a", "b"]
    assert json.dumps(one.to_dict(), allow_nan=False) == json.dumps(
        two.to_dict(), allow_nan=False
    )


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        Path("relative/path"),
        START,
        b"bytes",
        {1, 2},
        frozenset({1}),
        object(),
    ],
)
@pytest.mark.parametrize("nested", [False, True])
def test_configuration_rejects_non_json_values(value: object, nested: bool) -> None:
    configuration = {"value": [{"nested": value}] if nested else value}
    with pytest.raises(ValueError):
        make_provenance(resolved_configuration=configuration)


@pytest.mark.parametrize(
    "configuration",
    [
        {1: "value"},
        {"a": [{False: "value"}]},
        {"a": 1, None: 2},
    ],
)
def test_configuration_rejects_non_string_keys(configuration: Any) -> None:
    with pytest.raises(ValueError, match="keys must be strings"):
        make_provenance(resolved_configuration=configuration)


def test_configuration_rejects_cycles_but_allows_shared_input() -> None:
    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic
    with pytest.raises(ValueError, match="cycles"):
        make_provenance(resolved_configuration=cyclic)
    sequence: list[object] = []
    sequence.append(sequence)
    with pytest.raises(ValueError, match="cycles"):
        make_provenance(resolved_configuration={"sequence": sequence})
    shared = [1]
    provenance = make_provenance(resolved_configuration={"a": shared, "b": shared})
    assert provenance.to_dict()["resolved_configuration"] == {"a": [1], "b": [1]}


def test_configuration_strings_do_not_imply_path_semantics() -> None:
    config = {"text": "../literal string", "url": "https://example.test/value"}
    assert (
        make_provenance(resolved_configuration=config).to_dict()[
            "resolved_configuration"
        ]
        == config
    )


def test_existing_contract_ownership_is_documented() -> None:
    document = (
        Path(__file__).resolve().parents[1] / "docs" / "run_provenance_contract.md"
    ).read_text(encoding="utf-8")
    normalized = " ".join(document.split())
    assert "`RunMeta` remains unchanged in `src/mania/export/run_meta.py`" in normalized
    assert (
        "`mania_manifest.json` remains the preprocessing artifact manifest"
        in normalized
    )
    assert "`extended_metrics.json` remains the analysis manifest" in normalized
    assert "Run provenance is additive and does not replace these records" in normalized
