"""Stage 25.F documentation coverage against the accepted local contracts."""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUIDE = "docs/reproducibility.md"
BRIDGE = "docs/software_release_reference.md"
PBC = "docs/pbc_runtime_metadata.md"


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def normalized(text: str) -> str:
    return " ".join(text.replace("`", "").replace("**", "").split())


def section(name: str, heading: str) -> str:
    sections = re.split(r"(?m)^## ", read(name))
    return normalized(next(part for part in sections if part.startswith(heading)))


def test_reproduction_commands_and_scope_specific_artifacts() -> None:
    preprocessing = section(GUIDE, "Reproduce preprocessing")
    analysis = section(GUIDE, "Reproduce analysis")
    assert "mania preprocessing run-graph-export" in preprocessing
    for option in ("--manifest", "--output", "--contact-selection protein",
                   "--export-analysis-inputs", "--artifact-checksum-mode none",
                   "--artifact-checksum-mode sha256"):
        assert option in preprocessing
    for name in ("runtime_metadata.json", "pbc_audit.json",
                 "artifact_inventory.json", "run_provenance.json"):
        assert name in preprocessing
    assert "mania analyze" in analysis
    for option in ("--input", "--output", "--condition", "--enable-pca"):
        assert option in analysis
    for name in ("runtime_metadata.json", "artifact_inventory.json",
                 "run_provenance.json", "extended_metrics.json"):
        assert f"analysis/{name}" in analysis
    assert re.search(r"[Aa]nalysis does not write a PBC audit", analysis)
    assert "separate scientific/analysis metadata" in analysis


@pytest.mark.parametrize("name", [
    GUIDE, BRIDGE, "docs/unified_artifact_validation.md",
    "docs/stage25_reproducibility_hardening.md",
])
def test_future_publication_gate_keeps_partial_exit_semantics(name: str) -> None:
    text = normalized(read(name))
    assert 'report.status == "passed"' in text
    assert "report.complete is True" in text
    assert "Stage 25.G" in text
    assert "publication" in text.lower()
    if name == GUIDE:
        for status, code in (("passed", 0), ("partial", 0), ("failed", 1)):
            assert re.search(rf"\| {status} \|[^|]+\| {code} \|", text)
        assert "report.passed" in text
        assert "report.complete is false" in text
    else:
        for status, code in (("passed", 0), ("partial", 0), ("failed", 1)):
            assert f"{status} -> exit {code}" in text


def test_validation_requires_explicit_external_input_mapping() -> None:
    text = section(GUIDE, "Validate a run")
    for command in ("mania artifacts validate out --scope preprocessing",
                    "mania artifacts validate out --scope analysis",
                    "--input-artifact-path ARTIFACT_ID=PATH",
                    "input:condition:0001:trajectory:0001=source/trajectory.xtc"):
        assert command in text
    assert "all required inputs" in text
    assert "Analysis inputs also need explicit mapping" in text
    assert "one input only" in text
    assert re.search(r"adds no --require-complete", text)


@pytest.mark.parametrize("name", [GUIDE, PBC])
def test_pbc_sample_scope_units_and_scientific_limit(name: str) -> None:
    text = normalized(read(name))
    assert "sampled frames only" in text
    assert "actually observed" in text
    assert "1001" in text and "101" in text
    assert re.search(r"(?:not|do not)[^.]*\b(?:whole|entire)\b[^.]*trajectory", text)
    assert "Rg pass" in text and "contacts pass" in text
    assert re.search(r"double[- ]count", text)
    for field in ("box_lengths_A", "box_lengths_min_A", "box_lengths_max_A"):
        assert re.search(rf"\|[^|]*\b{field}\b[^|]*\|[^|]*Å", text)
    for field in ("box_angles_deg", "box_angles_min_deg", "box_angles_max_deg"):
        assert re.search(rf"\|[^|]*\b{field}\b[^|]*\|[^|]*degrees", text)
    assert "box_varies" in text and "valid observations" in text
    assert re.search(r"(?:correction_applied = false|correction is false)", text)
    assert re.search(r"[Ss]cientific PBC status remains unresolved", text)
    assert (
        "euclidean_selected_atom_coordinates_without_mania_minimum_image_correction"
        in text
    )
    assert "undeclared" in text
    assert re.search(
        r"[Bb]ox metadata presence (?:is not evidence|does not establish)", text
    )
    for boundary in ("made whole", "centered", "unwrapped", "PBC-correct"):
        assert boundary in text
    assert not re.search(
        r"PBC correctness of (?:the )?whole trajectory (?:was|is) verified", text
    )


@pytest.mark.parametrize("name", [GUIDE, PBC])
def test_runtime_privacy_and_optional_distribution_discovery(name: str) -> None:
    text = normalized(read(name))
    assert "importlib.metadata.version()" in text
    assert "distribution" in text and "None" in text and "null" in text
    assert re.search(r"(?:not imported|must not (?:require importing|import))", text)
    assert "Analysis-only metadata collection must not" in text
    assert "MDAnalysis" in text
    assert re.search(r"(?:collection excludes|metadata must exclude)", text)
    for forbidden in ("username", "hostname", "home-directory path",
                      "absolute local paths", "environment variables",
                      "machine serial identifiers"):
        assert forbidden in text


@pytest.mark.parametrize(("source", "model", "doc"), [
    ("src/mania/software_identity.py", "SoftwareIdentity", GUIDE),
    ("src/mania/runtime_metadata.py", "RuntimeEnvironment", GUIDE),
    ("src/mania/runtime_metadata.py", "RuntimePerformance", GUIDE),
    ("src/mania/preprocessing/pbc_audit.py", "PbcConditionAudit", GUIDE),
])
def test_documented_fields_match_existing_source(
    source: str, model: str, doc: str,
) -> None:
    tree = ast.parse(read(source))
    definition = next(node for node in tree.body
                      if isinstance(node, ast.ClassDef) and node.name == model)
    fields = [node.target.id for node in definition.body
              if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)]
    text = read(doc)
    for field in fields:
        assert f"`{field}`" in text, (model, field)
    if model == "SoftwareIdentity":
        identity = section(doc, "Identify the exact software")
        table_fields = re.findall(r"\| ([a-z_]+) \|", identity)
        assert table_fields == fields


def test_inventory_lineage_checksums_and_acyclic_provenance() -> None:
    text = section(GUIDE, "Interpret artifact inventory")
    for field in ("direction", "role", "path", "byte_size", "checksum_mode",
                  "sha256", "artifact_id"):
        assert field in text
    assert "input" in text and "output" in text and "portable" in text
    assert re.search(r"does not include or hash itself", text)
    assert re.search(r"does not include the corresponding run provenance", text)
    assert "NOT dataset publication membership" in text
    preprocessing = section(GUIDE, "Reproduce preprocessing")
    assert "size-only" in preprocessing
    assert "streams every inventoried input and output" in preprocessing
    assert "large trajectories in full" in preprocessing
    provenance = section(GUIDE, "Interpret run provenance")
    assert "portable reference" in provenance
    assert "no reciprocal checksum loop" in provenance


def test_software_reference_refresh_and_dataset_separation() -> None:
    text = normalized(read(BRIDGE))
    assert "MANIA software release/commit is not a dataset release" in text
    assert "canonical software repository url" in text.lower()
    refresh = section(BRIDGE, "Refresh-before-dataset-generation rule")
    for concept in ("production dataset generation", "actual generation run provenance",
                    "full commit SHA", "working-tree status",
                    "Refresh the consumer software-reference record"):
        assert concept in refresh
    assert "A tag must not replace exact commit identity" in text
    assert "Do not copy MANIA backend source into the dataset repository" in text
    assert "Raw MD inventory does not imply dataset membership" in text
    assert "does not require copying raw trajectories" in text
    assert "not a new machine schema" in text
    example = section(BRIDGE, "NaPi2b example (non-normative)")
    assert "napi2b-dynrin-fair2" in example
    assert "provenance/software/MANIA_RELEASE.json" in example
    assert (
        "neither changes that repository nor declares Dataset v1.0 released"
        in example
    )
    evidence = section(BRIDGE, "Recommended provenance material")
    for artifact in ("run_provenance.json", "artifact_inventory.json",
                     "runtime_metadata.json", "pbc_audit.json"):
        assert artifact in evidence
    assert "analysis/runtime_metadata.json" in evidence
    assert "mania artifacts validate" in evidence
    assert "consumer chooses its own" in evidence


def test_scientific_and_publication_decisions_remain_deferred() -> None:
    validation = section(GUIDE, "Validate a run")
    assert "Technical validity is not scientific acceptance" in validation
    assert "it does not establish scientific PBC correctness" in validation
    for concept in ("contact lifetime", "physical-time windows", "replica aggregation",
                    "cross-engine mapping", "Dataset v1.0 scientific approval",
                    "publication readiness"):
        assert concept in validation
    fair = section(BRIDGE, "FAIR² interpretation")
    assert "PBC correction is not implemented" in fair
    assert "outside this task's implementation/approval scope" in fair
    assert "final Dataset v1.0 schema and final Croissant remain deferred" in fair


def test_contract_docs_align_completed_stage25f_and_next_stage25g() -> None:
    for name in (
        PBC,
        "docs/unified_artifact_validation.md",
        "docs/run_provenance_contract.md",
        "docs/artifact_inventory_contract.md",
        "docs/stage25_reproducibility_hardening.md",
    ):
        text = normalized(read(name))
        assert re.search(r"Stage 25\.F[^.;]*is complete", text), name
        assert re.search(r"Stage 25\.G[^.;]*is next", text), name
        assert not re.search(r"Stage 25\.[EF][^.;]*is next", text), name
        assert not re.search(r"Stages 25\.F[/–-](?:25\.)?G remain planned", text), name
        assert re.search(r"Stage 25 (?:as a whole|overall) remains incomplete", text)


@pytest.mark.parametrize("name", [GUIDE, BRIDGE])
def test_new_guides_have_resolvable_local_links_and_no_pinned_development_sha(
    name: str,
) -> None:
    text = read(name)
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
    assert links
    for link in links:
        assert (ROOT / name).parent.joinpath(link).is_file(), link
    assert not re.search(r"\b[0-9a-f]{40}\b", text)
    assert not re.search(r"/(?:home|Users)/[\w.-]+", text)
