"""Stage 32.C synthetic authority, raw MAD semantics and pure runtime boundary."""

import ast
import builtins
import copy
import inspect
import io
import json
import os
import socket
import subprocess
import time
from dataclasses import FrozenInstanceError, fields, replace
from decimal import ROUND_UP, Decimal, Inexact, localcontext
from pathlib import Path
from typing import get_args

import pytest

from mania import dataset_review_qc as qc
from mania.dataset_hard_qc import ReplicaHardQCEvaluation
from mania.dataset_identity import DatasetTrajectoryIdentity
from mania.dataset_qc_contract import QCEvidenceRecord, ReplicaQCCheckResult

KEY = ("synthetic", "Cys-system", "trajectory", "1")


def evidence(name="source"):
    return QCEvidenceRecord(
        name,
        "metric",
        "review_input",
        "review/observations.json",
        None,
        name,
        "synthetic explicit observation",
        None,
        "Synthetic authoritative evidence; requested windows and schemas are valid.",
    )


def hard(key=KEY, passed=True):
    return ReplicaHardQCEvaluation(
        *key,
        (
            ReplicaQCCheckResult(
                "synthetic_hard_check",
                "pass" if passed else "fail",
                None if passed else "PROTEIN_PBC_BROKEN",
                None if passed else "Supplied hard failure.",
                (evidence(),),
            ),
        ),
    )


def observation(value=10, key=KEY, **changes):
    return qc.ReplicaMADMetricObservation(
        **dict(
            zip(
                ("dataset_id", "system_id", "trajectory_id", "replica_id"),
                key,
                strict=True,
            )
        )
        | dict(
            engine="gromacs",
            metric_family="edge_count",
            metric_name="edge_total",
            value=value,
            unit=None,
            evidence=(evidence(),),
        )
        | changes
    )


def review(key=KEY, drift=False, empty=0, expected=100, metrics=(), **changes):
    return qc.ReplicaReviewQCEvidence(
        **dict(
            zip(
                ("dataset_id", "system_id", "trajectory_id", "replica_id"),
                key,
                strict=True,
            )
        )
        | dict(
            engine="gromacs",
            rmsd_drift=qc.RMSDDriftAssessment(
                drift, "supplied_authoritative_assessment", (evidence(),)
            ),
            protein_edge_empty_windows=qc.ProteinEdgeEmptyWindowEvidence(
                expected, empty, (evidence(),)
            ),
            mad_metrics=metrics,
        )
        | changes
    )


def cohort(values, *, family="edge_count", name="edge_total", failed=()):
    keys = tuple((*KEY[:3], str(i + 1)) for i in range(len(values)))
    return (
        tuple(hard(k, i not in failed) for i, k in enumerate(keys)),
        tuple(
            review(
                k, metrics=(observation(v, k, metric_family=family, metric_name=name),)
            )
            for k, v in zip(keys, values, strict=True)
        ),
    )


def findings(result, check_id="mad:edge_count:edge_total"):
    return tuple(
        next(c for c in r.checks if c.check_id == check_id) for r in result.evaluations
    )


def metrics(check):
    return {e.metric_name: e.observed_value for e in check.evidence}


def assert_check(check, status, reason=None):
    assert type(check) is ReplicaQCCheckResult
    assert check.status == status
    assert check.reason_code == reason
    assert bool(check.human_readable_reason) == (status == "review")
    assert check.evidence


def damaged(model, **changes):
    result = copy.copy(model)
    for name, value in changes.items():
        object.__setattr__(result, name, value)
    return result


def test_public_types_models_and_fields():
    assert get_args(qc.ReviewQCStatus) == ("pass", "review")
    assert get_args(qc.ReviewMADMetricFamily) == (
        "edge_count",
        "contact_fraction",
        "basic_metric",
    )
    assert issubclass(qc.DatasetReviewQCError, ValueError)
    assert [f.name for f in fields(qc.RMSDDriftAssessment)] == [
        "drift_detected",
        "assessment_method",
        "evidence",
    ]
    assert [f.name for f in fields(qc.ReplicaMADMetricObservation)] == [
        "dataset_id",
        "system_id",
        "trajectory_id",
        "replica_id",
        "engine",
        "metric_family",
        "metric_name",
        "value",
        "unit",
        "evidence",
    ]
    assert [f.name for f in fields(qc.ReplicaReviewQCEvidence)] == [
        "dataset_id",
        "system_id",
        "trajectory_id",
        "replica_id",
        "engine",
        "rmsd_drift",
        "protein_edge_empty_windows",
        "mad_metrics",
    ]
    assert [f.name for f in fields(qc.ReplicaReviewQCEvaluation)] == [
        "dataset_id",
        "system_id",
        "trajectory_id",
        "replica_id",
        "checks",
        "review_qc_status",
    ]


def test_all_public_models_frozen_and_json_compatible():
    supplied = review(metrics=(observation(),))
    result = qc.evaluate_dataset_review_qc((hard(),), (supplied,))
    for model in (
        supplied.rmsd_drift,
        supplied.protein_edge_empty_windows,
        supplied.mad_metrics[0],
        supplied,
        result.evaluations[0],
        result,
    ):
        name = fields(model)[0].name
        with pytest.raises(FrozenInstanceError):
            setattr(model, name, getattr(model, name))
        assert (
            json.loads(json.dumps(model.to_dict(), allow_nan=False)) == model.to_dict()
        )
        assert model.to_dict() == model.to_dict()
    assert supplied.replica_key == result.evaluations[0].replica_key == KEY
    assert supplied.mad_metrics[0].replica_key == KEY


def test_ordering_immutability_and_independent_serialization():
    hard_results, records = cohort((10, 20, 100, 1000), failed=(3,))
    records = tuple(
        replace(
            r,
            mad_metrics=(
                replace(r.mad_metrics[0], metric_name="z_metric"),
                r.mad_metrics[0],
            ),
        )
        for r in records
    )
    before = json.dumps(
        [[r.to_dict() for r in group] for group in (hard_results, records)]
    )
    result = qc.evaluate_dataset_review_qc(hard_results, records)
    shuffled = qc.evaluate_dataset_review_qc(hard_results[::-1], records[::-1])
    assert result.to_dict() == shuffled.to_dict()
    assert before == json.dumps(
        [[r.to_dict() for r in group] for group in (hard_results, records)]
    )
    assert result.skipped_hard_failed_replica_keys == (hard_results[-1].replica_key,)
    assert [c.check_id for c in result.evaluations[0].checks] == [
        "rmsd_drift",
        "protein_edge_empty_window_fraction",
        "mad:edge_count:edge_total",
        "mad:edge_count:z_metric",
    ]
    serialized = result.to_dict()
    serialized["evaluations"].clear()
    assert result.evaluations
    serialized = records[0].to_dict()
    serialized["rmsd_drift"]["evidence"].clear()
    assert records[0].rmsd_drift.evidence


@pytest.mark.parametrize("drift", [False, True])
def test_rmsd_supplied_boolean_smoke(drift):
    result = qc.evaluate_dataset_review_qc((hard(),), (review(drift=drift),))
    check = findings(result, "rmsd_drift")[0]
    assert_check(
        check, "review" if drift else "pass", "RMSD_DRIFT_REVIEW" if drift else None
    )
    assert metrics(check)["drift_detected"] == str(drift)
    assert metrics(check)["assessment_method"] == "supplied_authoritative_assessment"
    assert result.evaluations[0].review_qc_status == check.status


@pytest.mark.parametrize(
    "empty,expected,status",
    [
        (0, 100, "pass"),
        (1, 100, "pass"),
        (2, 100, "review"),
        (1, 101, "pass"),
        (2, 101, "review"),
    ],
)
def test_empty_window_exact_threshold_smoke(empty, expected, status):
    result = qc.evaluate_dataset_review_qc(
        (hard(),), (review(empty=empty, expected=expected),)
    )
    check = findings(result, "protein_edge_empty_window_fraction")[0]
    assert_check(
        check,
        status,
        "PROTEIN_EDGE_EMPTY_WINDOW_FRACTION_ABOVE_1_PERCENT"
        if status == "review"
        else None,
    )
    values = metrics(check)
    assert values["expected_window_count"] == str(expected)
    assert values["empty_window_count"] == str(empty)
    with localcontext() as context:
        context.prec = 50
        assert values["empty_window_fraction"] == str(
            Decimal(empty) / Decimal(expected)
        )
    assert check.evidence[0].expected_or_threshold == "<=0.01"


@pytest.mark.parametrize(
    "family,name,values,code,median,mad,lower,upper",
    [
        (
            "edge_count",
            "edge_total",
            (10, 20, 100),
            "EDGE_COUNT_MAD_OUTLIER_REVIEW",
            "20",
            "10",
            "-10",
            "50",
        ),
        (
            "contact_fraction",
            "hbond_fraction",
            (0.1, 0.2, 0.9),
            "CONTACT_FRACTION_MAD_OUTLIER_REVIEW",
            "0.2",
            "0.1",
            "-0.1",
            "0.5",
        ),
        (
            "basic_metric",
            "radius_of_gyration_mean_A",
            (-10, 0, 80),
            "BASIC_METRIC_MAD_OUTLIER_REVIEW",
            "0",
            "10",
            "-30",
            "30",
        ),
    ],
)
def test_normal_raw_mad_smokes(family, name, values, code, median, mad, lower, upper):
    result = qc.evaluate_dataset_review_qc(*cohort(values, family=family, name=name))
    checks = findings(result, f"mad:{family}:{name}")
    assert_check(checks[0], "pass")
    assert_check(checks[1], "pass")
    assert_check(checks[2], "review", code)
    for check, value in zip(checks, values, strict=True):
        observed = metrics(check)
        assert observed["target_value"] == str(value)
        assert observed["reference_count"] == "3"
        assert observed["median"] == median
        assert observed["mad"] == mad
        assert observed["lower_band"] == lower
        assert observed["upper_band"] == upper
        assert observed["unit"] == "None"
        assert observed["comparison"] == "raw_mad_band"


@pytest.mark.parametrize(
    "values,status",
    [
        ((-20, 10, 20), "pass"),
        ((-20.000000000000004, 10, 20), "review"),
        ((10, 20, 50), "pass"),
        ((10, 20, 50.00000000000001), "review"),
        ((10, 20, 51), "review"),
    ],
)
def test_strict_boundaries_and_unscaled_mad(values, status):
    result = qc.evaluate_dataset_review_qc(*cohort(values, family="basic_metric"))
    checks = findings(result, "mad:basic_metric:edge_total")
    target = checks[0] if values[0] < 0 else checks[-1]
    assert_check(
        target,
        status,
        "BASIC_METRIC_MAD_OUTLIER_REVIEW" if status == "review" else None,
    )
    # 51 passes a scaled 1.4826-MAD band; raw MAD must review it.


@pytest.mark.parametrize("values", [(10, 10, 100), (10, 10, 10)])
def test_zero_mad_and_all_equal_smokes(values):
    checks = findings(qc.evaluate_dataset_review_qc(*cohort(values)))
    for value, check in zip(values, checks, strict=True):
        assert_check(
            check,
            "pass" if value == 10 else "review",
            None if value == 10 else "MAD_ZERO_REFERENCE_DISTRIBUTION_REVIEW",
        )
        observed = metrics(check)
        assert observed["median"] == "10"
        assert observed["mad"] == "0"
        assert observed["lower_band"] == observed["upper_band"] == "not_applicable"
        assert observed["comparison"] == "zero_mad_reference_distribution"


@pytest.mark.parametrize("family", get_args(qc.ReviewMADMetricFamily))
def test_zero_mad_reason_is_shared_across_families(family):
    checks = findings(
        qc.evaluate_dataset_review_qc(*cohort((0, 0, 1), family=family)),
        f"mad:{family}:edge_total",
    )
    assert_check(checks[-1], "review", "MAD_ZERO_REFERENCE_DISTRIBUTION_REVIEW")


def test_single_replica_cys_smoke():
    result = qc.evaluate_dataset_review_qc(*cohort((10,)))
    check = findings(result)[0]
    assert_check(check, "pass")
    assert result.evaluations[0].system_id == "Cys-system"
    assert metrics(check)["reference_count"] == "1"
    assert metrics(check)["comparison"] == "not_applicable_single_replica"
    assert (
        metrics(check)["lower_band"] == metrics(check)["upper_band"] == "not_applicable"
    )


@pytest.mark.parametrize(
    "values,median,mad", [((10, 20), "15", "5"), ((0, 1, 2, 3), "1.5", "1.0")]
)
def test_even_median_two_replica_and_no_leave_one_out(values, median, mad):
    inputs = cohort(values)
    result = qc.evaluate_dataset_review_qc(*inputs)
    assert (
        result.to_dict()
        == qc.evaluate_dataset_review_qc(inputs[0][::-1], inputs[1][::-1]).to_dict()
    )
    for check in findings(result):
        assert_check(check, "pass")
        assert metrics(check)["median"] == median
        assert metrics(check)["mad"] == mad
        assert metrics(check)["reference_count"] == str(len(values))


def test_hard_failed_exclusion_smoke():
    hard_results, records = cohort((10, 20, 1000), failed=(2,))
    # Its local review evidence would also trigger REVIEW if evaluated.
    records = (
        *records[:2],
        replace(
            records[2],
            rmsd_drift=qc.RMSDDriftAssessment(True, "explicit", (evidence(),)),
            protein_edge_empty_windows=qc.ProteinEdgeEmptyWindowEvidence(
                100, 100, (evidence(),)
            ),
        ),
    )
    result = qc.evaluate_dataset_review_qc(hard_results, records)
    assert len(result.evaluations) == 2
    assert result.skipped_hard_failed_replica_keys == (hard_results[2].replica_key,)
    for check in findings(result):
        assert_check(check, "pass")
        assert metrics(check)["reference_count"] == "2"
        assert metrics(check)["median"] == "15"
        assert metrics(check)["mad"] == "5"
        assert metrics(check)["lower_band"] == "0"
        assert metrics(check)["upper_band"] == "30"
    assert (
        result.to_dict()
        == qc.evaluate_dataset_review_qc(hard_results, records[:2]).to_dict()
    )
    # Metric-set completeness also ignores failed replicas.
    assert (
        result.to_dict()
        == qc.evaluate_dataset_review_qc(
            hard_results, (*records[:2], replace(records[2], mad_metrics=()))
        ).to_dict()
    )


def test_empty_dataset_and_all_hard_failed_have_no_artificial_pass():
    assert qc.evaluate_dataset_review_qc((), ()).to_dict() == {
        "evaluations": [],
        "skipped_hard_failed_replica_keys": [],
    }
    hard_results, _ = cohort((10, 20), failed=(0, 1))
    result = qc.evaluate_dataset_review_qc(hard_results[::-1], ())
    assert result.evaluations == ()
    assert result.skipped_hard_failed_replica_keys == tuple(
        h.replica_key for h in hard_results
    )


@pytest.mark.parametrize("field", ["dataset_id", "system_id", "engine"])
@pytest.mark.parametrize("condition", [None, "same_condition"])
def test_cohort_isolation_and_condition_has_no_authority(field, condition):
    hard_results, records = cohort((10, 10, 100))
    changes = {field: "namd" if field == "engine" else "other"}
    separated = replace(
        records[2],
        **changes,
        mad_metrics=(replace(records[2].mad_metrics[0], **changes),),
    )
    records = (*records[:2], separated)
    hard_results = (*hard_results[:2], hard(separated.replica_key))
    # Legacy condition may be identical or absent; only the full key is passed.
    identities = tuple(
        DatasetTrajectoryIdentity(
            dataset_id=r.dataset_id,
            system_id=r.system_id,
            trajectory_id=r.trajectory_id,
            replica_id=r.replica_id,
            engine=r.engine,
            variant_id="synthetic",
            condition=condition,
        )
        for r in records
    )
    assert all(
        i.replica_key == r.replica_key for i, r in zip(identities, records, strict=True)
    )
    result = qc.evaluate_dataset_review_qc(hard_results, records)
    assert all(r.review_qc_status == "pass" for r in result.evaluations)
    check = next(
        c
        for r in result.evaluations
        if r.replica_key == separated.replica_key
        for c in r.checks
        if c.check_id.startswith("mad:")
    )
    assert metrics(check)["reference_count"] == "1"


def test_metric_family_name_isolation_and_units_preserved():
    hard_results, records = cohort((10, 20, 100))
    records = tuple(
        replace(
            r,
            mad_metrics=(
                r.mad_metrics[0],
                replace(r.mad_metrics[0], metric_name="second", value=3),
                replace(
                    r.mad_metrics[0], metric_family="basic_metric", value=-3, unit="A"
                ),
            ),
        )
        for r in records
    )
    result = qc.evaluate_dataset_review_qc(hard_results, records)
    assert_check(findings(result)[-1], "review", "EDGE_COUNT_MAD_OUTLIER_REVIEW")
    for check in findings(result, "mad:edge_count:second"):
        assert_check(check, "pass")
    for check in findings(result, "mad:basic_metric:edge_total"):
        assert_check(check, "pass")
        assert metrics(check)["unit"] == "A"


@pytest.mark.parametrize("missing", [(), (observation(metric_name="different"),)])
def test_incomplete_metric_cohort_is_malformed(missing):
    hard_results, records = cohort((10, 20))
    records = (replace(records[0], mad_metrics=missing), records[1])
    with pytest.raises(qc.DatasetReviewQCError, match="incomplete metric cohort"):
        qc.evaluate_dataset_review_qc(hard_results, records)


def test_empty_metric_sets_are_explicitly_valid():
    hard_results, records = cohort((10, 20))
    result = qc.evaluate_dataset_review_qc(
        hard_results, tuple(replace(r, mad_metrics=()) for r in records)
    )
    assert all(
        len(r.checks) == 2 and r.review_qc_status == "pass" for r in result.evaluations
    )


def test_mixed_units_are_rejected_not_converted_or_regrouped():
    hard_results, records = cohort((10, 20))
    records = (
        replace(
            records[0], mad_metrics=(replace(records[0].mad_metrics[0], unit="A"),)
        ),
        records[1],
    )
    with pytest.raises(qc.DatasetReviewQCError, match="units must match"):
        qc.evaluate_dataset_review_qc(hard_results, records)


@pytest.mark.parametrize(
    "hard_results,records,message",
    [
        ((hard(), hard()), (review(),), "duplicate hard"),
        ((hard(),), (review(), review()), "duplicate review"),
        ((hard(),), (), "lacks mandatory"),
        ((), (review(),), "no matching full hard replica key"),
        ([], (), "hard_evaluations"),
        ((), [], "review_evidence"),
        ((None,), (), "hard_evaluations"),
        ((hard(),), (None,), "review_evidence"),
    ],
)
def test_main_api_malformed_inputs(hard_results, records, message):
    with pytest.raises(qc.DatasetReviewQCError, match=message):
        qc.evaluate_dataset_review_qc(hard_results, records)


@pytest.mark.parametrize(
    "field", ["dataset_id", "system_id", "trajectory_id", "replica_id"]
)
def test_full_key_matching(field):
    with pytest.raises(qc.DatasetReviewQCError, match="full hard replica key"):
        qc.evaluate_dataset_review_qc((hard(),), (review(**{field: "different"}),))
    with pytest.raises(qc.DatasetReviewQCError):
        observation(**{field: " "})


@pytest.mark.parametrize("drift", [0, 1, "false", None])
def test_rmsd_exact_bool_required(drift):
    with pytest.raises(qc.DatasetReviewQCError):
        qc.RMSDDriftAssessment(drift, "explicit", (evidence(),))


@pytest.mark.parametrize(
    "method",
    [
        "",
        " ",
        None,
        "loaded from /home/person/source",
        r"C:\data\source",
        "~/source",
        "$DATA/source",
        "%DATA%/source",
        "line\nbreak",
    ],
)
def test_rmsd_method_must_be_nonempty_portable_text(method):
    with pytest.raises(qc.DatasetReviewQCError):
        qc.RMSDDriftAssessment(False, method, (evidence(),))


@pytest.mark.parametrize(
    "expected,empty",
    [
        (0, 0),
        (-1, 0),
        (True, 0),
        (100.0, 0),
        (100, True),
        (100, -1),
        (100, 101),
        (100, 0.0),
    ],
)
def test_malformed_window_counts(expected, empty):
    with pytest.raises(qc.DatasetReviewQCError):
        qc.ProteinEdgeEmptyWindowEvidence(expected, empty, (evidence(),))


@pytest.mark.parametrize(
    "changes",
    [
        {"value": True},
        {"value": "10"},
        {"value": None},
        {"value": Decimal("10")},
        {"value": float("nan")},
        {"value": float("inf")},
        {"value": -float("inf")},
        {"value": -1},
        {"value": 1.1},
        {"metric_name": " "},
        {"metric_family": "other"},
        {"metric_family": 1},
        {"engine": "GROMACS"},
        {"engine": " namd "},
        {"engine": None},
        {"unit": ""},
        {"metric_family": "contact_fraction", "value": -1e-20},
        {"metric_family": "contact_fraction", "value": 1.0000000000000002},
    ],
)
def test_malformed_metric_observations(changes):
    with pytest.raises(qc.DatasetReviewQCError):
        observation(**changes)


@pytest.mark.parametrize(
    "family,value",
    [
        ("edge_count", 0),
        ("edge_count", 10.0),
        ("edge_count", 10**100),
        ("contact_fraction", 0),
        ("contact_fraction", 1),
        ("basic_metric", -1e308),
        ("basic_metric", 5e-324),
    ],
)
def test_valid_metric_domains_without_rounding(family, value):
    assert observation(metric_family=family, value=value).value == value


@pytest.mark.parametrize("payload", [(), [], (None,), (evidence(), evidence())])
def test_required_evidence_tuples(payload):
    for constructor in (
        lambda: qc.RMSDDriftAssessment(False, "explicit", payload),
        lambda: qc.ProteinEdgeEmptyWindowEvidence(100, 0, payload),
        lambda: observation(evidence=payload),
    ):
        with pytest.raises(qc.DatasetReviewQCError):
            constructor()


@pytest.mark.parametrize(
    "record",
    [
        damaged(evidence(), artifact_path="/home/person/input.json"),
        replace(evidence(), details="Loaded from /tmp/private.json"),
        replace(evidence(), observed_value=r"C:\data\input"),
        replace(evidence(), evidence_type="manual_review"),
    ],
)
def test_no_local_path_or_manual_reviewer_evidence(record):
    with pytest.raises(qc.DatasetReviewQCError):
        qc.RMSDDriftAssessment(False, "explicit", (record,))


@pytest.mark.parametrize(
    "changes",
    [
        {"rmsd_drift": None},
        {"protein_edge_empty_windows": None},
        {"engine": "NAMD"},
        {"mad_metrics": []},
        {"mad_metrics": (None,)},
        {"mad_metrics": (observation(), observation())},
        {"mad_metrics": (observation(engine="namd"),)},
        {"mad_metrics": (observation(trajectory_id="other"),)},
    ],
)
def test_replica_evidence_completeness_identity_and_unique_metrics(changes):
    with pytest.raises(qc.DatasetReviewQCError):
        review(**changes)


def test_revalidation_catches_damaged_input_and_derived_status():
    for malformed in (
        damaged(review(), rmsd_drift=None),
        damaged(review(), rmsd_drift=damaged(review().rmsd_drift, drift_detected=1)),
    ):
        with pytest.raises(qc.DatasetReviewQCError):
            qc.evaluate_dataset_review_qc((hard(),), (malformed,))
    for malformed in (
        damaged(hard(), hard_qc_status="fail"),
        damaged(hard(), checks=()),
    ):
        with pytest.raises(qc.DatasetReviewQCError):
            qc.evaluate_dataset_review_qc((malformed,), (review(),))


def test_result_rejects_fail_empty_duplicate_and_manual_fields():
    result = qc.evaluate_dataset_review_qc((hard(),), (review(),)).evaluations[0]
    for checks in ((), [], (None,), hard(passed=False).checks, result.checks * 2):
        with pytest.raises(qc.DatasetReviewQCError):
            qc.ReplicaReviewQCEvaluation(*KEY, checks)
    with pytest.raises(qc.DatasetReviewQCError):
        qc.ReplicaReviewQCEvaluation(
            *KEY,
            (
                result.checks[0],
                replace(result.checks[0], check_id="another"),
            ),
        )
    for evaluations, skipped in (
        ((result, result), ()),
        ((result,), (KEY,)),
        ((), (KEY, KEY)),
        ((None,), ()),
        ([], ()),
        ((), (("short",),)),
        ((), (list(KEY),)),
        ((), ((None, *KEY[1:]),)),
    ):
        with pytest.raises(qc.DatasetReviewQCError):
            qc.DatasetReviewQCEvaluation(evaluations, skipped)
    for model in (
        qc.RMSDDriftAssessment,
        qc.ProteinEdgeEmptyWindowEvidence,
        qc.ReplicaMADMetricObservation,
        qc.ReplicaReviewQCEvidence,
        qc.ReplicaReviewQCEvaluation,
        qc.DatasetReviewQCEvaluation,
    ):
        assert not {f.name for f in fields(model)}.intersection(
            {
                "release_decision",
                "decision_mode",
                "available",
                "pending_review",
                "excluded",
                "reviewer",
                "decision_note",
                "condition",
            }
        )


def test_decimal_context_isolation_and_extreme_precision():
    inputs = cohort((1e-300, 2e-300, 1e300), family="basic_metric")
    baseline = qc.evaluate_dataset_review_qc(*inputs).to_dict()
    window_inputs = ((hard(),), (review(expected=101, empty=2),))
    windows = qc.evaluate_dataset_review_qc(*window_inputs).to_dict()
    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_UP
        context.Emax = 9
        context.Emin = -9
        context.traps[Inexact] = True
        snapshot = context.copy()
        assert qc.evaluate_dataset_review_qc(*inputs).to_dict() == baseline
        assert qc.evaluate_dataset_review_qc(*window_inputs).to_dict() == windows
        assert repr(context) == repr(snapshot)
        assert context.flags == snapshot.flags
    check = findings(
        qc.evaluate_dataset_review_qc(*inputs), "mad:basic_metric:edge_total"
    )[-1]
    assert Decimal(metrics(check)["mad"]) == Decimal("1e-300")
    assert_check(check, "review", "BASIC_METRIC_MAD_OUTLIER_REVIEW")
    # A value just above 1% cannot disappear in a rounded percentage.
    result = qc.evaluate_dataset_review_qc(
        (hard(),), (review(expected=10**80, empty=10**78 + 1),)
    )
    assert findings(result, "protein_edge_empty_window_fraction")[0].status == "review"


def test_no_io_network_git_clock_or_recomputation(monkeypatch):
    inputs = cohort((10, 20, 100, 1000), failed=(3,))
    expected = qc.evaluate_dataset_review_qc(*inputs).to_dict()

    def blocked(*args, **kwargs):
        raise AssertionError("Forbidden I/O, clock, runtime or recomputation")

    from mania import (
        canonical_reference_io,
        dataset_hard_qc,
        replica_aggregation_workflow,
    )

    with monkeypatch.context() as guard:
        for owner, names in (
            (builtins, ("open",)),
            (io, ("open",)),
            (os, ("system", "getenv", "stat", "listdir", "scandir")),
            (
                Path,
                (
                    "open",
                    "read_text",
                    "read_bytes",
                    "exists",
                    "write_text",
                    "write_bytes",
                ),
            ),
            (socket, ("socket", "create_connection")),
            (subprocess, ("run", "Popen", "check_call", "check_output")),
            (time, ("time", "monotonic", "perf_counter")),
            (dataset_hard_qc, ("evaluate_replica_hard_qc",)),
            (canonical_reference_io, ("load_default_napi2b_canonical_reference",)),
        ):
            for name in names:
                guard.setattr(owner, name, blocked)
        for name, function in vars(replica_aggregation_workflow).items():
            if inspect.isfunction(function):
                guard.setattr(replica_aggregation_workflow, name, blocked)
        assert qc.evaluate_dataset_review_qc(*inputs).to_dict() == expected
    tree = ast.parse(inspect.getsource(qc))
    allowed_imports = {
        "re",
        "dataclasses",
        "decimal",
        "typing",
        "mania.dataset_hard_qc",
        "mania.dataset_identity",
        "mania.dataset_qc_contract",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name in allowed_imports for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module in allowed_imports
            assert not {a.name for a in node.names}.intersection(
                {
                    "ReplicaQCDecisionRecord",
                    "QCReleaseDecision",
                    "evaluate_replica_hard_qc",
                    "build_dataset_qc_decision_set",
                }
            )
    assert "MDAnalysis" not in inspect.getsource(qc)
    assert (
        "condition" not in inspect.signature(qc.evaluate_dataset_review_qc).parameters
    )
