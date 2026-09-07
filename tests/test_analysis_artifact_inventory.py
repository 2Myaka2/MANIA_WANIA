"""Authoritative analysis inputs and portable inventory without discovery or new I/O."""

import builtins
import hashlib
import io
import json
import os
import subprocess
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_analysis_run_provenance import analysis_result
from test_cli_analyze import _write_stage20_root

import mania.analysis.artifact_inventory as adapter
import mania.analysis.orchestration as orchestration
import mania.artifact_inventory_io as inventory_io
from mania.analysis.orchestration import (
    AnalyzeConditionInputPaths,
    AnalyzeError,
    AnalyzeRequest,
    resolve_analysis_input_paths,
    run_analysis,
)
from mania.constants import EDGE_TYPE_PRIORITY


def forbid_discovery(monkeypatch, *, resolve=True):
    forbidden = Mock(side_effect=AssertionError("No filesystem discovery"))
    for name in ("glob", "rglob", "iterdir") + (("resolve",) if resolve else ()):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(os, "walk", forbidden)
    return forbidden


def forbid_observation(monkeypatch):
    forbidden = forbid_discovery(monkeypatch)
    for owner, names in (
        (Path, ("open", "stat", "exists", "read_text", "read_bytes")),
        (builtins, ("open",)),
        (io, ("open",)),
        (subprocess, ("run", "Popen")),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    return forbidden


def declared_inputs(request, *, optional=True):
    root = request.input_root
    return tuple(
        AnalyzeConditionInputPaths(
            condition=name,
            residue_table=root / str(index) / "residues.CSV",
            protein_contact_edges=root / str(index) / "edges.csv",
            contacts_perframe=root / str(index) / "frames.csv",
            edge_semantics=root / "edge_semantics.json" if optional else None,
            mania_manifest=root / "mania_manifest.json" if optional else None,
            mania_residue_library=(
                root / "mania_residue_library.json" if optional else None
            ),
        )
        for index, name in enumerate(request.conditions)
    )


def write_custom_stage20_root(root, conditions):
    _write_stage20_root(root, conditions)
    produced = []
    for ordinal, condition in enumerate(conditions, start=1):
        for role, old, new in (
            ("residue table", f"residue_table_{condition}.csv", "residues"),
            (
                "protein contact edges",
                f"protein_contact_edges_undirected_{condition}.csv",
                "edges",
            ),
            (
                "per-frame protein contacts",
                f"contacts_perframe_{condition}.csv",
                "frames",
            ),
        ):
            filename = f"custom_{ordinal}_{new}.csv"
            (root / old).rename(root / filename)
            produced.append(
                {"role": role, "condition": condition, "filename": filename}
            )
    for filename, payload in (
        (
            "mania_manifest.json",
            {"conditions": list(conditions), "produced_artifacts": produced},
        ),
        ("edge_semantics.json", {"edge_priority": list(EDGE_TYPE_PRIORITY)}),
        (
            "mania_residue_library.json",
            {"conditions": [{"condition": c} for c in conditions]},
        ),
    ):
        (root / filename).write_text(json.dumps(payload), encoding="utf-8")


def test_public_boundary_and_frozen_paths(tmp_path):
    request = AnalyzeRequest(tmp_path / "in", tmp_path / "out", ("normal",))
    paths = declared_inputs(request)[0]
    with pytest.raises(FrozenInstanceError):
        paths.condition = "changed"
    assert not hasattr(paths, "to_dict")
    assert "AnalyzeConditionInputPaths" in orchestration.__all__
    assert "resolve_analysis_input_paths" in orchestration.__all__
    import mania.analysis as analysis

    assert not hasattr(analysis, "AnalyzeConditionInputPaths")
    assert not hasattr(analysis, "resolve_analysis_input_paths")
    assert adapter.__all__ == [
        "ANALYSIS_ARTIFACT_INVENTORY_PATH",
        "ANALYSIS_ARTIFACT_INVENTORY_ROLE",
        "AnalysisArtifactInventoryError",
        "build_analysis_artifact_inventory",
        "collect_analysis_input_file_specs",
        "collect_analysis_output_file_specs",
    ]


@pytest.mark.parametrize("custom", [False, True])
def test_resolution_and_reuse_preserve_science(tmp_path, monkeypatch, custom):
    request = AnalyzeRequest(tmp_path / "in", tmp_path / "out", ("tumor", "normal"))
    writer = write_custom_stage20_root if custom else _write_stage20_root
    writer(request.input_root, request.conditions)
    read_text = Path.read_text
    manifest_reads = []

    def read(path, *args, **kwargs):
        if path.name == "mania_manifest.json":
            manifest_reads.append(path)
        return read_text(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        forbidden = forbid_discovery(patch)
        patch.setattr(Path, "read_text", read)
        resolved = resolve_analysis_input_paths(request)
        assert tuple(p.condition for p in resolved) == request.conditions
        assert len(manifest_reads) == int(custom)
        forbidden.assert_not_called()
    if custom:
        assert resolved[0].residue_table.name == "custom_1_residues.csv"
        assert all(p.mania_manifest is not None for p in resolved)
    else:
        assert resolved[0].residue_table.name == "residue_table_tumor.csv"
        assert all(p.mania_manifest is None for p in resolved)
        assert all(p.edge_semantics is None for p in resolved)
        assert all(p.mania_residue_library is None for p in resolved)
    legacy = run_analysis(request)
    original_bytes = {p: p.read_bytes() for p in legacy.artifacts}
    with monkeypatch.context() as patch:
        # Existing scientific manifest validation still reads its supplied path;
        # the orchestration resolver must never parse it again for path selection.
        forbidden = Mock(side_effect=AssertionError("Inputs resolved twice"))
        patch.setattr(orchestration, "resolve_analysis_input_paths", forbidden)
        patch.setattr(orchestration, "_manifest_produced_artifacts", forbidden)
        reused = run_analysis(request, resolved_input_paths=resolved)
        forbidden.assert_not_called()
    assert reused == legacy
    assert reused.to_summary() == legacy.to_summary()
    assert {p: p.read_bytes() for p in reused.artifacts} == original_bytes


@pytest.mark.parametrize("invalid", ["list", "duck", "subclass", "reverse", "missing"])
def test_supplied_paths_reject_invalid_type_count_or_order(tmp_path, invalid):
    request = AnalyzeRequest(tmp_path / "in", tmp_path / "out", ("tumor", "normal"))
    _write_stage20_root(request.input_root, request.conditions)
    resolved = resolve_analysis_input_paths(request)

    class Subclass(AnalyzeConditionInputPaths):
        pass

    values = {
        "list": list(resolved),
        "duck": (SimpleNamespace(**vars(resolved[0])), resolved[1]),
        "subclass": (Subclass(**vars(resolved[0])), resolved[1]),
        "reverse": resolved[::-1],
        "missing": resolved[:1],
    }
    with pytest.raises(AnalyzeError, match="resolved_input_paths"):
        run_analysis(request, resolved_input_paths=values[invalid])
    with pytest.raises(adapter.AnalysisArtifactInventoryError):
        adapter.collect_analysis_input_file_specs(
            request=request, resolved_input_paths=values[invalid]
        )


def test_resolver_requires_exact_request(tmp_path):
    class Subclass(AnalyzeRequest):
        pass

    for value in (None, Subclass(tmp_path, tmp_path, ("normal",))):
        with pytest.raises(TypeError, match="AnalyzeRequest"):
            resolve_analysis_input_paths(value)


@pytest.mark.parametrize("optional", [False, True])
def test_input_specs_are_ordered_deduplicated_and_pure(tmp_path, monkeypatch, optional):
    request = AnalyzeRequest(
        tmp_path / "private", tmp_path / "out", ("tumor", "normal")
    )
    resolved = declared_inputs(request, optional=optional)
    with monkeypatch.context() as patch:
        forbidden = forbid_observation(patch)
        specs = adapter.collect_analysis_input_file_specs(
            request=request, resolved_input_paths=resolved
        )
        forbidden.assert_not_called()
    offset = 3 if optional else 0
    assert len(specs) == offset + 6
    if optional:
        assert [(s.artifact_id, s.path, s.role, s.condition) for s in specs[:3]] == [
            (
                "input:root:mania_manifest",
                "inputs/root/mania_manifest.json",
                "preprocessing_manifest",
                None,
            ),
            (
                "input:root:edge_semantics",
                "inputs/root/edge_semantics.json",
                "edge_semantics",
                None,
            ),
            (
                "input:root:residue_library",
                "inputs/root/mania_residue_library.json",
                "residue_library",
                None,
            ),
        ]
    for ordinal, condition in enumerate(request.conditions, start=1):
        selected = specs[offset + (ordinal - 1) * 3 : offset + ordinal * 3]
        for spec, role, filename in zip(
            selected,
            ("residue_table", "protein_contact_edges", "contacts_perframe"),
            ("residues.CSV", "edges.csv", "frames.csv"),
            strict=True,
        ):
            assert spec.artifact_id == f"input:condition:{ordinal:04d}:{role}"
            assert spec.path == f"inputs/conditions/{ordinal:04d}/{role}/{filename}"
            assert spec.condition == condition
            assert spec.format == "csv"
            assert condition not in spec.artifact_id
            assert condition not in spec.path
    assert len({s.path for s in specs}) == len(specs)
    assert all(str(tmp_path) not in s.path for s in specs)
    assert all(
        s.local_path.name not in {"artifact_inventory.json", "run_provenance.json"}
        for s in specs
    )


@pytest.mark.parametrize(
    "field", ["mania_manifest", "edge_semantics", "mania_residue_library"]
)
@pytest.mark.parametrize("conflict", [None, Path("different.json")])
def test_conflicting_optional_roots_are_rejected(tmp_path, field, conflict):
    request = AnalyzeRequest(tmp_path, tmp_path, ("tumor", "normal"))
    paths = declared_inputs(request)
    paths = (paths[0], replace(paths[1], **{field: conflict}))
    with pytest.raises(adapter.AnalysisArtifactInventoryError, match="must agree"):
        adapter.collect_analysis_input_file_specs(
            request=request, resolved_input_paths=paths
        )


@pytest.mark.parametrize(
    "filename",
    [
        "no_suffix",
        "bad.",
        "bad.é",
        "bad.c sv",
        "artifact_inventory.json",
        "run_provenance.json",
    ],
)
def test_unusable_input_metadata_rejected_without_local_details(tmp_path, filename):
    request = AnalyzeRequest(tmp_path, tmp_path, ("normal",))
    paths = (replace(declared_inputs(request)[0], residue_table=tmp_path / filename),)
    with pytest.raises(adapter.AnalysisArtifactInventoryError) as error:
        adapter.collect_analysis_input_file_specs(
            request=request, resolved_input_paths=paths
        )
    assert str(tmp_path) not in str(error.value)


@pytest.mark.parametrize("conditions", [("normal",), ("tumor", "normal")])
@pytest.mark.parametrize("manifest", [False, True])
def test_output_specs_use_result_order_and_lexical_paths(
    tmp_path, monkeypatch, conditions, manifest
):
    request = AnalyzeRequest(tmp_path / "in", tmp_path / "out", conditions)
    result = analysis_result(request, manifest=manifest)
    with monkeypatch.context() as patch:
        forbidden = forbid_observation(patch)
        specs = adapter.collect_analysis_output_file_specs(result)
        forbidden.assert_not_called()
    assert tuple(s.local_path for s in specs) == result.artifacts
    assert tuple(s.path for s in specs) == tuple(
        p.relative_to(request.output_root).as_posix() for p in result.artifacts
    )
    keys = (
        "graph",
        "centrality",
        "communities",
        "region_enrichment",
        "temporal_rin",
        "conformation_pca",
        "conformation_labels",
    )
    expected = [
        (f"output:condition:{i:04d}:{key}", f"analysis_{key}", name)
        for i, name in enumerate(conditions, start=1)
        for key in keys
    ]
    expected += [
        ("output:comparison", "analysis_comparison", None),
        ("output:stats", "analysis_stats", None),
    ]
    if manifest:
        expected.append(("output:extended_metrics", "analysis_manifest", None))
    assert [(s.artifact_id, s.role, s.condition) for s in specs] == expected
    assert all(s.direction == "output" for s in specs)


@pytest.mark.parametrize(
    "path",
    [
        "outside/x.csv",
        "out/../x.csv",
        "out/artifact_inventory.json",
        "out/run_provenance.json",
        "out/analysis/artifact_inventory.json",
        "out/analysis/run_provenance.json",
    ],
)
def test_output_escape_and_technical_metadata_are_rejected(tmp_path, path):
    request = AnalyzeRequest(tmp_path / "in", tmp_path / "out", ("normal",))
    result = replace(analysis_result(request), comparison_csv=tmp_path / path)
    with pytest.raises(adapter.AnalysisArtifactInventoryError) as error:
        adapter.collect_analysis_output_file_specs(result)
    assert str(tmp_path) not in str(error.value)


@pytest.mark.parametrize("completed", [False, True])
@pytest.mark.parametrize("mode", ["none", "sha256"])
def test_builder_delegates_sizes_and_hashes_without_mutation(
    tmp_path, monkeypatch, completed, mode
):
    request = AnalyzeRequest(tmp_path / "in", tmp_path / "out", ("tumor", "normal"))
    paths = declared_inputs(request)
    result = analysis_result(request) if completed else None
    specs = adapter.collect_analysis_input_file_specs(
        request=request, resolved_input_paths=paths
    )
    if result is not None:
        specs += adapter.collect_analysis_output_file_specs(result)
    contents = {}
    for index, spec in enumerate(specs):
        spec.local_path.parent.mkdir(parents=True, exist_ok=True)
        contents[spec.path] = f"small artifact {index}\n".encode()
        spec.local_path.write_bytes(contents[spec.path])
    original = (
        replace(request),
        tuple(replace(p) for p in paths),
        replace(result) if result else None,
    )
    generic = Mock(wraps=adapter.build_artifact_inventory)
    hashing = Mock(wraps=inventory_io.stream_file_sha256)
    with monkeypatch.context() as patch:
        forbidden = forbid_discovery(patch)
        patch.setattr(adapter, "build_artifact_inventory", generic)
        patch.setattr(inventory_io, "stream_file_sha256", hashing)
        if mode == "none":
            patch.setattr(Path, "open", forbidden)
        inventory = adapter.build_analysis_artifact_inventory(
            run_id="analysis-test",
            request=request,
            resolved_input_paths=paths,
            result=result,
            checksum_mode=mode,
        )
        forbidden.assert_not_called()
    generic.assert_called_once()
    assert generic.call_args.kwargs["checksum_mode"] == mode
    assert inventory.run_id == "analysis-test"
    assert inventory.workflow == "analysis"
    assert inventory.inventory_path == "analysis/artifact_inventory.json"
    assert inventory.input_artifact_count == 9
    assert inventory.output_artifact_count == (17 if completed else 0)
    assert [s.path for s in specs] == [a.path for a in inventory.artifacts]
    for entry in inventory.artifacts:
        assert entry.byte_size == len(contents[entry.path])
        assert entry.sha256 == (
            hashlib.sha256(contents[entry.path]).hexdigest()
            if mode == "sha256"
            else None
        )
    assert hashing.call_count == (len(specs) if mode == "sha256" else 0)
    assert (request, paths, result) == original
    assert str(tmp_path) not in json.dumps(inventory.to_dict())


def test_builder_rejects_wrong_result_and_request_before_io(tmp_path, monkeypatch):
    request = AnalyzeRequest(tmp_path / "in", tmp_path / "out", ("normal",))
    result = analysis_result(request)

    class Subclass(type(result)):
        pass

    values = (
        SimpleNamespace(**vars(result)),
        Subclass(**vars(result)),
        replace(result, request=replace(request, enable_pca=True)),
    )
    with monkeypatch.context() as patch:
        forbidden = forbid_observation(patch)
        for value in values:
            with pytest.raises(adapter.AnalysisArtifactInventoryError):
                adapter.build_analysis_artifact_inventory(
                    run_id="test",
                    request=request,
                    resolved_input_paths=declared_inputs(request),
                    result=value,
                    checksum_mode="none",
                )
        forbidden.assert_not_called()


def test_runtime_output_is_explicit_last(tmp_path, monkeypatch):
    from test_analysis_run_provenance import analysis_result

    request = AnalyzeRequest(tmp_path / "in", tmp_path / "out", ("normal", "tumor"))
    result = analysis_result(request)
    path = request.output_root / "analysis/runtime_metadata.json"
    before = adapter.collect_analysis_output_file_specs(result)
    with monkeypatch.context() as patch:
        forbid_discovery(patch)
        after = adapter.collect_analysis_output_file_specs(
            result, runtime_metadata_path=path,
        )
    assert after[:-1] == before
    entry = after[-1]
    assert entry.artifact_id == "output:runtime_metadata"
    assert entry.role == "runtime_metadata"
    assert entry.path == "analysis/runtime_metadata.json"
    assert entry.local_path is path
    assert entry.format == "json" and entry.condition is None
    with pytest.raises(adapter.AnalysisArtifactInventoryError):
        adapter.collect_analysis_output_file_specs(
            result, runtime_metadata_path=request.output_root / "runtime_metadata.json",
        )
