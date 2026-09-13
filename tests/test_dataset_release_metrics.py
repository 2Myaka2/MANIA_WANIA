"""Explicit metric selections, source portability, finite values and window links."""

import copy
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest
from test_dataset_release_metadata import replica_key
from test_dataset_release_science import case as case
from test_dataset_release_science import damaged, make_science_case, metric

from mania.dataset_release_csv import (
    publication_number,
    read_publication_csv,
    write_publication_csv,
)
from mania.dataset_release_metrics import build_dataset_release_metrics


def test_global_and_window_metrics_preserve_explicit_values_and_source(case, tmp_path):
    window = case["canonical_protein_edges"].rows[0]
    inputs = (
        metric(metric_id="global", metric_name="arbitrary authoritative name"),
        metric(
            metric_id="window",
            window_id=window.window_id,
            window_index=window.window_index,
            unit="supplied-unit",
            metric_value=Decimal("0.123456789012345678901234567890123456789"),
        ),
    )
    snapshot = copy.deepcopy(inputs)
    table = build_dataset_release_metrics(
        reversed(inputs), metadata_tables=case["metadata_tables"]
    )
    assert inputs == snapshot
    assert [r["metric_id"] for r in table.records()] == ["global", "window"]
    for source, output in zip(inputs, table.records(), strict=True):
        assert output["metric_value"] == publication_number(source.metric_value)
        for name in (
            "source_artifact_role",
            "source_artifact_path",
            "source_record_key",
            "metric_name",
            "unit",
            "window_id",
            "window_index",
        ):
            assert output[name] == getattr(source, name)
    path = write_publication_csv(table, tmp_path / table.relative_path)
    assert read_publication_csv("metrics", path) == table
    with pytest.raises(FrozenInstanceError):
        inputs[0].metric_value = 0


@pytest.mark.parametrize("replica", ["2", "absent"])
def test_excluded_or_unknown_metric_selection_fails(case, replica):
    with pytest.raises(ValueError, match="science-included|foreign key"):
        build_dataset_release_metrics(
            (metric(replica),), metadata_tables=case["metadata_tables"]
        )


def test_qc_available_but_science_unselected_metric_is_rejected(tmp_path):
    inputs, _ = make_science_case(tmp_path, selected=(replica_key("3"),))
    with pytest.raises(ValueError, match="science-included"):
        build_dataset_release_metrics(
            (metric(),), metadata_tables=inputs["metadata_tables"]
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"window_id": "window_0001"},
        {"window_index": 0},
    ],
)
def test_half_window_identity_fails(changes):
    with pytest.raises(ValueError, match="pair"):
        metric(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"window_id": "unknown", "window_index": 0},
        {"window_id": "window_0001", "window_index": 999},
        {"trajectory_id": "other-trajectory"},
        {"system_id": "other-system"},
    ],
)
def test_exact_replica_and_window_foreign_keys(case, changes):
    with pytest.raises(ValueError, match="foreign key"):
        build_dataset_release_metrics(
            (metric(**changes),), metadata_tables=case["metadata_tables"]
        )


@pytest.mark.parametrize(
    "value",
    [None, True, "1.2", float("nan"), float("inf"), -float("inf"), Decimal("NaN")],
)
def test_metric_requires_finite_numeric_value(value):
    with pytest.raises(ValueError):
        metric(metric_value=value)


@pytest.mark.parametrize(
    "path",
    [
        "/home/user/metric.csv",
        "../metric.csv",
        "evidence/../metric.csv",
        "~/metric.csv",
        "C:/metric.csv",
        "evidence\\metric.csv",
        "$HOME/metric.csv",
        "evidence//metric.csv",
        "./metric.csv",
        "metric.csv\n",
    ],
)
def test_metric_source_must_be_portable_without_rewriting(path):
    with pytest.raises(ValueError, match="portable"):
        metric(source_artifact_path=path)


def test_metric_primary_key_is_replica_and_metric_id(case):
    original = metric()
    with pytest.raises(ValueError, match="Duplicate"):
        build_dataset_release_metrics(
            (original, replace(original, metric_name="different")),
            metadata_tables=case["metadata_tables"],
        )
    table = build_dataset_release_metrics(
        (original, replace(original, metric_id="another-source-row")),
        metadata_tables=case["metadata_tables"],
    )
    assert table.row_count == 2


def test_constructible_malformed_metric_and_audit_input_rejected(case):
    for supplied in (
        damaged(metric(), metric_value=float("nan")),
        case["aggregation_authority"].decisions.records[0],
    ):
        with pytest.raises(ValueError):
            build_dataset_release_metrics(
                (supplied,), metadata_tables=case["metadata_tables"]
            )
    assert (
        build_dataset_release_metrics((), metadata_tables=case["metadata_tables"]).rows
        == ()
    )
