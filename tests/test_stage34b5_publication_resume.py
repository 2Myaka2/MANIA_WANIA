"""Explicit annotation transport and frozen-only publication regressions."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from mania.biological_annotations import (
    CanonicalVariantSiteAnnotation,
    DatasetSystemBiologicalAnnotations,
    GlycosylationSiteAnnotation,
)
from mania.biological_annotations_io import write_dataset_system_biological_annotations
from mania.canonical_reference_io import load_default_napi2b_canonical_reference

spec = importlib.util.spec_from_file_location(
    "publication_resume",
    Path(__file__).parents[1] / "tools/stage34b5_publication_resume.py",
)
resume = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resume)


@pytest.fixture
def authority(tmp_path):
    reference = load_default_napi2b_canonical_reference()
    provenance = dict(
        system_identity=resume.IDENTITY,
        authority_kind="externally_supplied_complete_system_annotations",
        canonical_reference_id=reference.reference_id,
        canonical_reference_sequence_sha256=reference.sequence_sha256,
        categories={
            n: dict(
                accepted_positions=sites,
                scientific_authority="Test authority",
                independent_evidence="Test verification",
            )
            for n, sites in resume.SITES.items()
        },
    )
    annotations = DatasetSystemBiologicalAnnotations(
        *resume.KEY[:2],
        "complete_for_system",
        tuple(
            GlycosylationSiteAnnotation(
                n, "ASN", True, "FA2G2S2", "Test authority", "Test verification"
            )
            for n in (295, 308)
        ),
        tuple(
            CanonicalVariantSiteAnnotation(
                n, "CYS", "Test authority", "Test verification"
            )
            for n in (303, 322, 328, 350)
        ),
        (),
    )
    path = tmp_path / "annotations.json"
    assert write_dataset_system_biological_annotations(annotations, path).written
    return path, provenance


def test_exact_lists_scope_provenance_and_complete_negatives(authority):
    annotations, report = resume.validate_annotation_authority(*authority)
    assert report["status"] == "PASS"
    assert report["annotation_scope"] == "complete_for_system"
    for name, expected in resume.SITES.items():
        assert report[name] == expected
    table = resume.prior.publication_readiness(
        dict(status="PASS", aggregate_mismatches=0), (annotations,)
    )
    check = resume.annotation_output_check(table)
    assert check["true_counts"] == dict(
        is_ecd=128,
        is_mx35_region=31,
        is_glycosylation_site=2,
        is_disulfide_variant_site=4,
        is_cysteine_variant_site=0,
    )
    assert all(
        s.source == "Test authority" and s.verifier == "Test verification"
        for s in (
            *annotations.glycosylation_sites,
            *annotations.disulfide_variant_sites,
        )
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "glyco",
        "disulfide",
        "cysteine",
        "scope",
        "resname",
        "unknown",
        "system",
        "missing_scope",
    ],
)
def test_annotation_defects_rejected(authority, mutation):
    path, provenance = authority
    data = json.loads(path.read_text())
    if mutation in ("glyco", "disulfide"):
        data[
            "glycosylation_sites" if mutation == "glyco" else "disulfide_variant_sites"
        ].pop()
    elif mutation == "cysteine":
        data["cysteine_variant_sites"] = data["disulfide_variant_sites"][:1]
    elif mutation == "scope":
        data["annotation_scope"] = "observed_sites_only"
    elif mutation == "resname":
        data["glycosylation_sites"][0]["canonical_resname"] = "CYS"
    elif mutation == "unknown":
        data["condition"] = "PMm"
    elif mutation == "missing_scope":
        del data["annotation_scope"]
    else:
        data["system_id"] = "unrelated-system"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        resume.validate_annotation_authority(path, provenance)


@pytest.mark.parametrize(
    "mutation",
    [
        "psf_only",
        "missing_category",
        "wrong_positions",
        "condition",
        "reference",
        "source",
        "verifier",
    ],
)
def test_provenance_authority_required(authority, mutation):
    path, provenance = authority
    if mutation == "psf_only":
        provenance["authority_kind"] = "PSF topology only"
    elif mutation == "missing_category":
        del provenance["categories"]["cysteine_variant_sites"]
    elif mutation == "wrong_positions":
        provenance["categories"]["glycosylation_sites"]["accepted_positions"] = [295]
    elif mutation == "condition":
        provenance["system_identity"] = resume.IDENTITY | {"condition": None}
    elif mutation == "reference":
        provenance["canonical_reference_id"] = "another-reference"
    else:
        name = (
            "scientific_authority" if mutation == "source" else "independent_evidence"
        )
        provenance["categories"]["glycosylation_sites"][name] = "Different"
    with pytest.raises((ValueError, KeyError)):
        resume.validate_annotation_authority(path, provenance)


@pytest.mark.parametrize("target", list(resume.FROZEN_HASHES))
def test_every_frozen_hash_required(tmp_path, monkeypatch, target):
    def record(path):
        name = path.relative_to(tmp_path).as_posix()
        return dict(sha256="tampered" if name == target else resume.FROZEN_HASHES[name])

    monkeypatch.setattr(resume, "file_record", record)
    with pytest.raises(ValueError, match="Frozen identity differs"):
        resume.check_frozen_hashes(tmp_path)


def test_stop_does_not_execute_upstream_or_claim_release(tmp_path, monkeypatch):
    monkeypatch.setattr(resume, "checkpoint", lambda *_: "test-head")
    monkeypatch.setattr(
        resume, "bind_history", Mock(side_effect=ValueError("frozen mismatch"))
    )
    forbidden = Mock(side_effect=AssertionError("Upstream execution forbidden"))
    monkeypatch.setattr(resume.prior, "run_dataset_qc", forbidden)
    monkeypatch.setattr(resume.prior, "run_replica_aggregation", forbidden)
    monkeypatch.setattr(resume.prior.accepted, "aligned_rmsd", forbidden)
    publish = Mock(side_effect=AssertionError("Publication must stop"))
    monkeypatch.setattr(resume, "run_dataset_release", publish)
    report = resume.run(tmp_path, tmp_path, tmp_path, tmp_path, tmp_path)
    assert report["stage34b5_status"] == "STOP"
    assert report["stage34_status"] == "IN PROGRESS"
    assert report["interval_ns"] == [0.1, 0.5]
    for name in (
        "stage32_recomputed",
        "stage31_recomputed",
        "rmsd_recalculated",
        "replicas_2_3_run",
        "full_100ns_analysis",
        "all_33_run",
        "stage35_run",
        "final_dataset_release",
        "internal_mic",
    ):
        assert report[name] is False
    forbidden.assert_not_called()
    publish.assert_not_called()


def test_condition_copy_retains_temporal_science(tmp_path):
    from dataclasses import replace

    from test_dataset_release_metadata import temporal_evidence

    from mania.dataset_identity import DatasetTrajectoryIdentity
    from mania.preprocessing.physical_time_execution import (
        PreprocessingTemporalExecution,
    )
    from mania.preprocessing.physical_time_execution_io import (
        read_preprocessing_temporal_execution,
        write_preprocessing_temporal_execution,
    )

    # Wrong interval must fail before writing, even with the exact pilot identity.
    binding = temporal_evidence("1")
    binding = replace(
        binding,
        dataset_spec=binding.dataset_spec.model_copy(
            update={
                "identity": DatasetTrajectoryIdentity(**resume.prior.accepted.IDENTITY)
            }
        ),
    )
    source = tmp_path / "source"
    result = write_preprocessing_temporal_execution(
        PreprocessingTemporalExecution((binding,)), source
    )
    assert result.written
    frozen = tmp_path / "frozen"
    frozen.mkdir()
    (frozen / "temporal.json").write_bytes(result.output_path.read_bytes())
    with pytest.raises(ValueError, match="Smoke scope changed"):
        resume.bind_temporal(tmp_path, tmp_path)
    assert read_preprocessing_temporal_execution(result.output_path).bindings == (
        binding,
    )
    assert not (tmp_path / "publication_temporal").exists()


@pytest.mark.parametrize("mutation", ["value", "population", "identity"])
def test_independent_publication_rejects_science_substitution(mutation):
    from test_replica_protein_edge_aggregation import row

    source = row()
    published = source.to_dict()
    if mutation == "value":
        published["occupancy"] = 0.12345
    elif mutation == "identity":
        published["condition"] = "unrelated"
    with pytest.raises(ValueError, match="Publication"):
        resume.compare_published_rows(
            [source], [] if mutation == "population" else [published]
        )


def test_exact_source_copy_passes_without_mutating_science():
    from test_replica_protein_edge_aggregation import row

    source = row()
    before = source.to_dict()
    resume.compare_published_rows([source], [before.copy()])
    assert source.to_dict() == before


def test_negative_annotation_cannot_become_ambiguous(authority):
    from types import SimpleNamespace

    annotations, _ = resume.validate_annotation_authority(*authority)
    table = resume.prior.publication_readiness(
        dict(status="PASS", aggregate_mismatches=0), (annotations,)
    )
    rows = table.records()
    rows[0]["is_glycosylation_site"] = None
    with pytest.raises(ValueError, match="positive/negative"):
        resume.annotation_output_check(SimpleNamespace(records=lambda: rows))
