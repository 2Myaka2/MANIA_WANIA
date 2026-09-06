"""Pure analysis passports use accepted models and supplied execution context."""

import builtins
import io
import json
import subprocess
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import mania.analysis.run_provenance as adapter
import mania.software_identity as identity_module
from mania.analysis.orchestration import (
    AnalyzeConditionResult,
    AnalyzeRequest,
    AnalyzeRunResult,
)
from mania.software_identity import SoftwareIdentity

START = datetime(2026, 9, 6, 12, 3, 4, 123456, tzinfo=UTC)
END = START + timedelta(seconds=5)
IDENTITY = SoftwareIdentity(
    "MANIA", "mania-wania", "0.1.0", None, "unavailable", "unavailable"
)


def analysis_result(request: AnalyzeRequest, *, manifest=True) -> AnalyzeRunResult:
    root = request.output_root / "analysis"
    conditions = tuple(
        AnalyzeConditionResult(
            condition=name,
            graph_json=root / name / "graph.json",
            centrality_csv=root / name / f"centrality_{name}.csv",
            communities_csv=root / name / f"communities_{name}.csv",
            region_enrichment_csv=root / name / f"region_enrichment_{name}.csv",
            temporal_rin_csv=root / name / f"temporal_rin_{name}.csv",
            conformation_pca_csv=root / name / f"conformation_pca_{name}.csv",
            conformation_labels_csv=root / name / f"conformation_labels_{name}.csv",
            temporal_status="computed",
            region_enrichment_status="computed",
            pca_status="pca_unavailable",
            pca_n_components=0,
            clustering_status="computed",
            clustering_algorithm="kmeans",
            clustering_input_source="contact_fingerprint_matrix",
            clustering_pca_status="pca_unavailable",
            clustering_selected_k=2,
            pca_components_used_for_clustering=None,
            pca_max_components=10,
            pca_exported_component_count=0,
            pca_used_for_clustering=False,
        )
        for name in request.conditions
    )
    return AnalyzeRunResult(
        request=request,
        analysis_root=root,
        condition_results=conditions,
        comparison_csv=root / "comparison.csv",
        stats_csv=root / "stats.csv",
        extended_metrics_json=root / "extended_metrics.json" if manifest else None,
    )


def context():
    return {
        "run_id": "caller-supplied-analysis-id",
        "started_at_utc": START,
        "ended_at_utc": END,
        "software_identity": IDENTITY,
        "command": ("mania", "analyze", "--input", "prepared", "--output", "."),
        "resolved_configuration": {"conditions": ["tumor", "normal"]},
    }


def forbid_observation(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Pure provenance must not observe external state")

    class NoClock(datetime):
        @classmethod
        def now(cls, tz=None):
            forbidden()

        @classmethod
        def utcnow(cls):
            forbidden()

    monkeypatch.setattr(adapter, "datetime", NoClock)
    for owner, names in (
        (Path, ("resolve", "exists", "stat", "iterdir", "glob", "rglob", "open")),
        (builtins, ("open",)),
        (io, ("open",)),
        (subprocess, ("run", "Popen")),
        (time, ("time", "time_ns")),
        (identity_module, ("get_software_identity",)),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    return NoClock


def test_public_boundary_and_run_id(monkeypatch):
    assert adapter.__all__ == [
        "ANALYSIS_RUN_FAILURE_STAGE",
        "ANALYSIS_RUN_ID_PREFIX",
        "ANALYSIS_RUN_PROVENANCE_DIRNAME",
        "ANALYSIS_RUN_PROVENANCE_WORKFLOW",
        "AnalysisRunProvenanceBuildError",
        "analysis_run_id_from_started_at",
        "build_completed_analysis_run_provenance",
        "build_failed_analysis_run_provenance",
        "collect_analysis_artifact_references",
    ]
    assert adapter.ANALYSIS_RUN_FAILURE_STAGE == "analysis_execution"
    assert adapter.ANALYSIS_RUN_ID_PREFIX == "analysis"
    assert adapter.ANALYSIS_RUN_PROVENANCE_DIRNAME == "analysis"
    assert adapter.ANALYSIS_RUN_PROVENANCE_WORKFLOW == "analysis"
    shifted = START.astimezone(timezone(timedelta(hours=3)))
    with monkeypatch.context() as patch:
        no_clock = forbid_observation(patch)
        for value in (
            no_clock.fromisoformat(START.isoformat()),
            no_clock.fromisoformat(shifted.isoformat()),
        ):
            assert adapter.analysis_run_id_from_started_at(value) == (
                "analysis-20260906T120304123456Z"
            )
        assert adapter.analysis_run_id_from_started_at(
            no_clock.fromisoformat(START.isoformat()).replace(microsecond=0)
        ).endswith("04000000Z")


@pytest.mark.parametrize("value", [START.replace(tzinfo=None), None, "2026-09-06"])
def test_invalid_start_is_rejected(value):
    with pytest.raises(adapter.AnalysisRunProvenanceBuildError, match="aware"):
        adapter.analysis_run_id_from_started_at(value)


@pytest.mark.parametrize("conditions", [("normal",), ("tumor", "normal")])
@pytest.mark.parametrize("manifest", [False, True])
def test_artifact_reference_order_and_portability(
    tmp_path, monkeypatch, conditions, manifest
):
    request = AnalyzeRequest(tmp_path / "prepared", tmp_path / "out", conditions)
    result = analysis_result(request, manifest=manifest)
    expected = []
    for name in conditions:
        for role, filename in (
            ("graph", "graph.json"),
            ("centrality", f"centrality_{name}.csv"),
            ("communities", f"communities_{name}.csv"),
            ("region_enrichment", f"region_enrichment_{name}.csv"),
            ("temporal_rin", f"temporal_rin_{name}.csv"),
            ("conformation_pca", f"conformation_pca_{name}.csv"),
            ("conformation_labels", f"conformation_labels_{name}.csv"),
        ):
            expected.append(
                {"role": f"analysis_{role}", "path": f"analysis/{name}/{filename}"}
            )
    expected.extend(
        [
            {"role": "analysis_comparison", "path": "analysis/comparison.csv"},
            {"role": "analysis_stats", "path": "analysis/stats.csv"},
        ]
    )
    if manifest:
        expected.append(
            {"role": "analysis_manifest", "path": "analysis/extended_metrics.json"}
        )
    with monkeypatch.context() as patch:
        forbid_observation(patch)
        actual = adapter.collect_analysis_artifact_references(result)
    assert [reference.to_dict() for reference in actual] == expected
    assert all(set(reference.to_dict()) == {"role", "path"} for reference in actual)
    assert all("run_provenance.json" not in reference.path for reference in actual)


@pytest.mark.parametrize(
    "path",
    [
        "outside/graph.json",
        "out/../outside/graph.json",
        "out/run_provenance.json",
        "out/analysis/run_provenance.json",
    ],
)
def test_invalid_artifact_path_is_rejected_without_local_details(tmp_path, path):
    result = analysis_result(
        AnalyzeRequest(tmp_path / "in", tmp_path / "out", ("normal",))
    )
    result = replace(result, comparison_csv=tmp_path / path)
    with pytest.raises(adapter.AnalysisRunProvenanceBuildError) as error:
        adapter.collect_analysis_artifact_references(result)
    assert str(error.value) == (
        "Analysis artifact paths must be portable and inside the output root."
    )


def test_completed_builder_preserves_context_without_observation(tmp_path, monkeypatch):
    result = analysis_result(
        AnalyzeRequest(tmp_path / "prepared", tmp_path / "out", ("tumor", "normal"))
    )
    original = replace(result)
    supplied = context()
    with monkeypatch.context() as patch:
        forbid_observation(patch)
        provenance = adapter.build_completed_analysis_run_provenance(result, **supplied)
        payload = json.loads(json.dumps(provenance.to_dict(), allow_nan=False))
    assert provenance.workflow == "analysis"
    assert provenance.status == "completed"
    assert provenance.run_id == supplied["run_id"]
    assert provenance.started_at_utc == START
    assert provenance.ended_at_utc == END
    assert provenance.software_identity is IDENTITY
    assert provenance.command == supplied["command"]
    assert payload["resolved_configuration"] == supplied["resolved_configuration"]
    assert provenance.conditions == ("tumor", "normal")
    assert provenance.sampling_by_condition == ()
    assert provenance.issues == ()
    assert provenance.artifact_references == (
        adapter.collect_analysis_artifact_references(result)
    )
    assert result == original
    supplied["resolved_configuration"]["conditions"].append("later")
    assert provenance.to_dict()["resolved_configuration"]["conditions"] == [
        "tumor",
        "normal",
    ]


def test_failed_builder_is_pure_and_claims_no_partial_outputs(tmp_path, monkeypatch):
    request = AnalyzeRequest(tmp_path / "prepared", tmp_path / "out", ("normal",))
    with monkeypatch.context() as patch:
        forbid_observation(patch)
        provenance = adapter.build_failed_analysis_run_provenance(request, **context())
        payload = json.loads(json.dumps(provenance.to_dict(), allow_nan=False))
    assert provenance.workflow == "analysis"
    assert provenance.status == "failed"
    assert provenance.run_id == context()["run_id"]
    assert provenance.started_at_utc == START
    assert provenance.ended_at_utc == END
    assert provenance.software_identity is IDENTITY
    assert provenance.command == context()["command"]
    assert provenance.conditions == ("normal",)
    assert payload["sampling_by_condition"] == []
    assert payload["artifact_references"] == []
    assert payload["issues"] == [
        {
            "severity": "error",
            "code": "analysis_execution_failed",
            "message": "Analysis workflow failed.",
            "stage": "analysis_execution",
            "condition": None,
        }
    ]


@pytest.mark.parametrize(
    "builder",
    [
        adapter.build_completed_analysis_run_provenance,
        adapter.build_failed_analysis_run_provenance,
    ],
)
@pytest.mark.parametrize(
    "invalid",
    [
        {"run_id": ""},
        {"ended_at_utc": START - timedelta(seconds=1)},
        {"resolved_configuration": {"bad": Path("private")}},
    ],
)
def test_root_validation_errors_are_wrapped(tmp_path, builder, invalid):
    request = AnalyzeRequest(tmp_path / "prepared", tmp_path / "out", ("normal",))
    source = (
        request
        if builder is adapter.build_failed_analysis_run_provenance
        else analysis_result(request)
    )
    with pytest.raises(adapter.AnalysisRunProvenanceBuildError) as error:
        builder(source, **(context() | invalid))
    assert str(error.value) in {
        "Completed analysis metadata is invalid.",
        "Failed analysis metadata is invalid.",
    }


def test_exact_accepted_types_are_required(tmp_path):
    class RequestSubclass(AnalyzeRequest):
        pass

    class ResultSubclass(AnalyzeRunResult):
        pass

    request = AnalyzeRequest(tmp_path / "in", tmp_path / "out", ("normal",))
    result = analysis_result(request)
    for value in (
        None,
        SimpleNamespace(**vars(request)),
        RequestSubclass(**vars(request)),
    ):
        with pytest.raises(adapter.AnalysisRunProvenanceBuildError, match="request"):
            adapter.build_failed_analysis_run_provenance(value, **context())
    for value in (
        None,
        SimpleNamespace(**vars(result)),
        ResultSubclass(**vars(result)),
    ):
        with pytest.raises(adapter.AnalysisRunProvenanceBuildError, match="result"):
            adapter.build_completed_analysis_run_provenance(value, **context())
        with pytest.raises(adapter.AnalysisRunProvenanceBuildError, match="result"):
            adapter.collect_analysis_artifact_references(value)


@pytest.mark.parametrize("failed", [False, True])
def test_additional_references_append_after_scientific_outputs(
    tmp_path, monkeypatch, failed
):
    from mania.run_provenance import PortableArtifactReference

    request = AnalyzeRequest(tmp_path / "in", tmp_path / "out", ("normal",))
    result = analysis_result(request)
    builder = (
        adapter.build_failed_analysis_run_provenance
        if failed
        else adapter.build_completed_analysis_run_provenance
    )
    source = request if failed else result
    reference = PortableArtifactReference(
        "artifact_inventory", "analysis/artifact_inventory.json"
    )
    with monkeypatch.context() as patch:
        forbid_observation(patch)
        default = builder(source, **context())
        explicit_empty = builder(source, **context(), additional_artifact_references=())
        linked = builder(
            source, **context(), additional_artifact_references=(reference,)
        )
    assert default == explicit_empty
    assert linked.artifact_references == default.artifact_references + (reference,)
    assert linked.to_dict() == default.to_dict() | {
        "artifact_references": [r.to_dict() for r in linked.artifact_references]
    }


@pytest.mark.parametrize("failed", [False, True])
@pytest.mark.parametrize("references", [[], (object(),), (None,)])
def test_invalid_additional_references_use_existing_validation(
    tmp_path, failed, references
):
    request = AnalyzeRequest(tmp_path / "in", tmp_path / "out", ("normal",))
    builder = (
        adapter.build_failed_analysis_run_provenance
        if failed
        else adapter.build_completed_analysis_run_provenance
    )
    with pytest.raises(
        adapter.AnalysisRunProvenanceBuildError, match="metadata is invalid"
    ):
        builder(
            request if failed else analysis_result(request),
            **context(),
            additional_artifact_references=references,
        )
