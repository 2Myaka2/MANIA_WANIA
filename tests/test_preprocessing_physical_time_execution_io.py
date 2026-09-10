"""Strict offline temporal reconstruction, deterministic JSON and atomic writes."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_preprocessing_physical_time_execution import context, loading

import mania.preprocessing.physical_time_execution as planning
import mania.preprocessing.physical_time_execution_io as module
from mania.preprocessing.physical_time_execution import (
    build_preprocessing_temporal_execution,
)
from mania.preprocessing.physical_time_execution_io import (
    PreprocessingTemporalExecutionReadError,
    read_preprocessing_temporal_execution,
    write_preprocessing_temporal_execution,
)


def execution(partial=False):
    source, _ = loading((0, 200, 600, 1000) if partial else tuple(range(0, 1001, 100)))
    return build_preprocessing_temporal_execution(source, context())


@pytest.mark.parametrize("partial", [False, True])
def test_round_trip_is_offline_and_exact(monkeypatch, tmp_path, partial):
    value = execution(partial)
    written = write_preprocessing_temporal_execution(value, tmp_path)
    assert (
        written.passed and written.output_path == tmp_path / "temporal_execution.json"
    )
    content = written.output_path.read_bytes()
    assert content.endswith(b"\n") and not content.endswith(b"\n\n")
    assert (
        content
        == (
            json.dumps(value.to_dict(), indent=2, ensure_ascii=False, allow_nan=False)
            + "\n"
        ).encode()
    )
    with monkeypatch.context() as guard:
        forbidden = Mock(side_effect=AssertionError("No planning or discovery on read"))
        guard.setattr(planning, "resolve_physical_time_sampling", forbidden)
        guard.setattr(planning, "plan_physical_time_windows", forbidden)
        guard.setattr(Path, "glob", forbidden)
        guard.setattr(Path, "rglob", forbidden)
        guard.setattr(Path, "iterdir", forbidden)
        recovered = read_preprocessing_temporal_execution(written.output_path)
        forbidden.assert_not_called()
    assert recovered == value and recovered.to_dict() == value.to_dict()


def test_atomic_overwrite_and_failed_publication(monkeypatch, tmp_path):
    value = execution()
    first = write_preprocessing_temporal_execution(value, tmp_path)
    old = first.output_path.read_bytes()
    assert not write_preprocessing_temporal_execution(execution(True), tmp_path).passed
    assert first.output_path.read_bytes() == old
    replace = Mock(wraps=module.os.replace)
    monkeypatch.setattr(module.os, "replace", replace)
    assert write_preprocessing_temporal_execution(
        execution(True), tmp_path, overwrite=True
    ).passed
    replace.assert_called_once()
    retained = first.output_path.read_bytes()
    replace.side_effect = OSError("private failure")
    failed = write_preprocessing_temporal_execution(value, tmp_path, overwrite=True)
    assert not failed.passed and failed.error == "Filesystem write failed."
    assert first.output_path.read_bytes() == retained
    assert sorted(p.name for p in tmp_path.iterdir()) == ["temporal_execution.json"]


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(schema_version="future"),
        lambda d: d.update(kind="future"),
        lambda d: d.update(status="partial"),
        lambda d: d.update(extra=True),
        lambda d: d.update(bindings=[]),
        lambda d: d["bindings"][0]["sampling_plan"].update(status="failed"),
        lambda d: d["bindings"][0]["sampling_plan"].update(sampled_frame_count=1),
        lambda d: d["bindings"][0]["sampling_plan"].update(match_abs_tolerance_ps=1),
        lambda d: d["bindings"][0]["window_plan"].update(schema_version="future"),
        lambda d: d["bindings"][0]["window_plan"].update(status="failed"),
        lambda d: d["bindings"][0]["window_plan"].update(window_count=999),
        lambda d: d["bindings"][0]["window_plan"]["windows"][0].update(
            source_frame_indexes=[1, 2]
        ),
        lambda d: d["bindings"][0]["dataset_spec"]["temporal"].update(
            frame_stride_ps=100
        ),
        lambda d: d["bindings"][0]["dataset_spec"]["temporal"].update(
            window_length_ns=0.8
        ),
        lambda d: d["bindings"][0]["dataset_spec"].update(kind="future"),
    ],
)
def test_invalid_contract_rejected(tmp_path, change):
    payload = execution().to_dict()
    change(payload)
    target = tmp_path / "invalid.json"
    target.write_text(json.dumps(payload))
    with pytest.raises(PreprocessingTemporalExecutionReadError):
        read_preprocessing_temporal_execution(target)


@pytest.mark.parametrize(
    "content", [b"{", b"[]", b'{"status":NaN}', b'{"kind":1,"kind":2}', b"\xff"]
)
def test_invalid_json_is_portable(tmp_path, content):
    path = tmp_path / "private.json"
    path.write_bytes(content)
    with pytest.raises(PreprocessingTemporalExecutionReadError) as caught:
        read_preprocessing_temporal_execution(path)
    assert str(tmp_path) not in str(caught.value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("requested_start_ns", 0.1),
        ("requested_end_ns", 0.5),
        ("right_endpoint_inclusive", True),
    ],
)
def test_window_schedule_cannot_disagree_with_temporal_request(tmp_path, field, value):
    payload = execution().to_dict()
    payload["bindings"][0]["window_plan"]["windows"][0][field] = value
    target = tmp_path / "invalid.json"
    target.write_text(json.dumps(payload))
    with pytest.raises(PreprocessingTemporalExecutionReadError):
        read_preprocessing_temporal_execution(target)
