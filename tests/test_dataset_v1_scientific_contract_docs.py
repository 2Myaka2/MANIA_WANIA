"""Protect scientific decisions without pinning paragraph wording or wrapping."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCIENTIFIC = ROOT / "docs/dataset_v1_scientific_contract.md"
IDENTITY = ROOT / "docs/dataset_identity_contract.md"


def normalized(text: str) -> str:
    return " ".join(text.replace("`", "").replace("**", "").split()).lower()


def section(path: Path, heading_pattern: str) -> str:
    sections = re.split(r"(?m)^## ", path.read_text(encoding="utf-8"))
    matches = [
        part
        for part in sections
        if re.search(heading_pattern, part.splitlines()[0], re.IGNORECASE)
    ]
    assert len(matches) == 1, heading_pattern
    return normalized(matches[0])


def test_dataset_composition_and_engine_specific_groups() -> None:
    text = section(SCIENTIFIC, "dataset composition")
    assert re.search(r"33 trajectories(?:/replicas)?\b", text)
    assert re.search(r"19 systems\b", text)
    for group, replicas, systems in (
        (r"gromacs", 12, 4),
        (r"namd disulfide", 9, 3),
        (r"namd ecd/cys", 12, 12),
    ):
        assert re.search(
            rf"{group}[^.]*\b{replicas} replicas\b[^.]*\b{systems} systems", text
        )
    for variant, condition, duration in (
        ("wt", "norm", 100),
        ("wt", "tumor", 100),
        ("t330m", "norm", 30),
        ("t330m", "tumor", 30),
    ):
        assert re.search(rf"\| {variant} \| {condition} \| 3 \| {duration} ns \|", text)
    for state in ("0ss", "1ss", "2ss"):
        assert re.search(rf"\| wt \| {state} \| 3 \|", text)
    assert re.search(r"1 wt system\b", text)
    assert re.search(r"11 cys-variant systems\b", text)
    assert re.search(r"one replica per system", text)


@pytest.mark.parametrize("path", [SCIENTIFIC, IDENTITY])
def test_condition_pending_and_scientific_labels_not_invented(path: Path) -> None:
    text = normalized(path.read_text(encoding="utf-8"))
    assert re.search(
        r"concrete namd condition (?:values|labels)[^.]*\b(?:pending|unresolved)", text
    )
    assert re.search(r"condition[^.]*none|none[^.]*condition", text)
    assert re.search(r"must not (?:invent|substitute)[^.]*labels", text)


def test_main_graph_and_separate_non_protein_layers() -> None:
    text = section(SCIENTIFIC, "protein graph")
    for concept in (
        "protein-only",
        "napi2b amino-acid",
        "protein-protein",
        "scientifically accepted",
        "protein_lipid_contacts_by_window",
        "protein_glycan_contacts_by_window",
        "when glycans are present",
    ):
        assert concept in text
    assert re.search(r"lipids and glycans must not[^.]*nodes", text)
    assert re.search(r"separate protein-lipid layer", text)
    assert re.search(r"separate protein-glycan layer", text)


def test_external_pbc_pipeline_and_observation_only_boundary() -> None:
    text = section(SCIENTIFIC, "external pbc")
    assert re.search(
        r"pbc correction must occur before mania[^.]*external preprocessing", text
    )
    for step in (
        "whole molecule",
        "remove jumps",
        "unwrap when required",
        "center on protein",
        "compact trajectory when required",
    ):
        assert step in text
    for retained in (
        "commands/scripts",
        "software version",
        "inputs",
        "outputs",
        "provenance",
    ):
        assert retained in text
    assert re.search(r"must not apply internal minimum-image correction", text)
    assert re.search(r"no internal minimum-image correction", text)
    assert re.search(r"must not[^.]*modify coordinates[^.]*unwrap[^.]*center", text)
    assert re.search(r"stage 25 pbc audit[^.]*observation/qc only", text)


def test_requested_time_units_and_stage27_boundary() -> None:
    text = section(SCIENTIFIC, "requested physical-time")
    for field in ("variant_id", "engine", "condition", "replica_id"):
        assert field in text
    for field, unit in (
        ("production_start_ns", "ns"),
        ("production_end_ns", "ns"),
        ("frame_stride_ps", "ps"),
        ("window_length_ns", "ns"),
        ("window_step_ns", "ns"),
        ("overlap_percent", "percent"),
    ):
        assert re.search(rf"\| {field} \| {unit} \|", text)
    assert "requested scientific parameters" in text
    assert "must not remain frame-count-only" in text
    assert re.search(r"stage 27[^.]*source/sampled frames[^.]*effective windows", text)
    assert re.search(r"no step/overlap consistency relation", text)


def test_occupancy_episode_continuity_and_breaks() -> None:
    text = section(SCIENTIFIC, "protein-protein occupancy")
    for formula in (
        "occupancy = n_contact_frames / n_frames_in_window",
        "edge_weight = occupancy",
        "gap_tolerance = 0",
    ):
        assert formula in text
    for concept in (
        "one window",
        "one replica",
        "adjacent selected mania frames",
        "contact is absent",
        "expected sampled frame is actually missing",
        "window boundary",
        "replica boundary",
    ):
        assert concept in text
    assert re.search(r"intentional frame stride does not[^.]*break an episode", text)
    for field in (
        "n_contact_frames",
        "occupancy",
        "n_contact_episodes",
        "mean_episode_length_ns",
        "max_episode_length_ns",
        "edge_weight",
    ):
        assert field in text


@pytest.mark.parametrize(
    ("layer", "cutoff", "partner"),
    [
        ("protein-lipid", "6.0", "one lipid molecule"),
        ("protein-glycan", "4.5", "the glycan"),
    ],
)
def test_separate_layer_distance_contract(
    layer: str, cutoff: str, partner: str
) -> None:
    text = section(SCIENTIFIC, rf"{layer} contacts")
    assert "separate layer" in text
    assert "heavy atoms of one amino-acid residue" in text
    assert re.search(rf"heavy atoms of {partner}", text)
    assert "minimum interatomic distance" in text
    assert f"{cutoff} å" in text
    for field in (
        "n_contact_frames",
        "occupancy",
        "n_contact_episodes",
        "mean_episode_length_ns",
        "max_episode_length_ns",
        "distance_mean_a",
        "distance_min_a",
    ):
        assert field in text
    if layer == "protein-glycan":
        assert re.search(
            r"covalent carrier-residue[^.]*first-sugar[^.]*must not[^.]*"
            r"occupancy/lifetime summaries",
            text,
        )


def test_canonical_reference_and_supplied_annotations() -> None:
    mapping = section(SCIENTIFIC, "canonical residue")
    for value in ("o95436", "npt2b_human", "slc34a2", "690 aa"):
        assert value in mapping
    for field in (
        "source_engine",
        "source_chain_id",
        "source_resid",
        "source_resname",
        "canonical_residue_number",
        "canonical_resname",
        "mapping_status",
    ):
        assert field in mapping
    assert re.search(r"publication tables[^.]*canonical numbering", mapping)
    assert re.search(
        r"gromacs and namd[^.]*must not[^.]*source resid[^.]*match", mapping
    )
    annotations = section(SCIENTIFIC, "supplied biological")
    assert re.search(r"ecd\s+234[–-]361", annotations)
    assert re.search(r"mx35\s+311[–-]341", annotations)
    for field in (
        "is_ecd",
        "is_mx35_region",
        "disulfide_variant_sites",
        "cysteine_variant_sites",
        "canonical site",
        "present in topology",
        "glycan type/name",
        "source",
        "verifier",
    ):
        assert field in annotations
    assert re.search(r"epitope_annotations.csv[^.]*not mandatory", annotations)
    assert re.search(r"must not infer or invent biological annotations", annotations)
    for group, owner in (
        ("wt/t330m gromacs", "ramila"),
        ("namd disulfide systems", "egor"),
        ("namd ecd cys variants", "alina"),
    ):
        assert re.search(rf"\| {group} \| {owner} \|", annotations)


def test_replica_statistics_and_no_cross_engine_aggregation() -> None:
    text = section(SCIENTIFIC, "replica aggregation")
    assert "independently retained" in text
    for field in (
        "mean_occupancy",
        "std_occupancy",
        "median_occupancy",
        "n_replicates_available",
        "n_replicates_supporting",
        "support_fraction",
    ):
        assert field in text
    assert "n_replicates_supporting = number of replicas where occupancy > 0" in text
    assert "support_fraction = n_replicates_supporting / n_replicates_available" in text
    assert "n_replicates_available = 1" in text
    assert "std_occupancy = null" in text
    assert re.search(r"must not fabricate inter-replica statistics", text)
    assert re.search(r"gromacs and namd must not[^.]*statistical group", text)
    assert re.search(r"engine must[^.]*publication tables", text)


def test_qc_thresholds_exclusions_and_manual_review() -> None:
    text = section(SCIENTIFIC, "dataset qc")
    technical, manual = text.split("manual review", 1)
    for failure in (
        "unreadable topology/trajectory",
        "atom count/order",
        "residue-mapping mismatch",
        "protein remains broken",
        "frame times duplicate or move backwards",
        "less than 95%",
        "expected production frames",
        "metadata/windows/nodes/edges missing",
        "schema/reference",
        "missing source/target nodes",
        "self-loops",
        "duplicates",
        "occupancy outside [0, 1]",
    ):
        assert failure in technical
    assert "not automatic exclusion" in manual
    for flag in (
        "rmsd drift",
        "more than 1%",
        "windows without protein-protein edges",
        "edge count",
        "contact-type fraction",
        "basic metrics",
        "median ± 3 mad",
        "appropriate replicate group",
    ):
        assert flag in manual
    assert re.search(r"rmsd alone must not[^.]*exclusion criterion", manual)
    assert re.search(r"mad == 0[^.]*must not[^.]*outlier", manual)
    for qc in ("technical qc", "pbc qc", "mapping qc", "graph qc"):
        assert qc in manual
    assert re.search(r"lack of replicate statistics[^;]*limitation", manual)


@pytest.mark.parametrize("stage", range(27, 34))
def test_future_owners_are_explicitly_not_implemented(stage: int) -> None:
    text = section(SCIENTIFIC, "status and implementation")
    row = re.search(rf"\| stage {stage} \| ([^|]+) \| ([^|]+) \|", text)
    assert row is not None
    assert "future" in row[2]
    assert re.search(r"not implemented", row[2])


@pytest.mark.parametrize("path", [SCIENTIFIC, IDENTITY])
def test_docs_preserve_stage_status_and_future_implementation_boundary(
    path: Path,
) -> None:
    text = normalized(path.read_text(encoding="utf-8"))
    assert re.search(r"stage 25 is complete", text)
    assert re.search(r"stage 26\.a is implemented", text)
    if path == SCIENTIFIC:
        # Preserve the frozen record's historical Stage 26.A status assertions.
        assert re.search(r"stage 26 remains incomplete", text)
        assert re.search(r"stage 26\.b[^;]*integration[^;]*next", text)
        assert not re.search(r"stage 26 (?:is |— )complete\b", text)
    else:
        status = section(path, "status and scope")
        assert re.search(r"stage 26\.a[^.]*accepted", status)
        assert re.search(r"stage 26\.b[^.]*accepted", status)
        assert re.search(r"stage 26\.c[^.]*implemented", status)
        assert re.search(r"stage 26 is complete\b", status)
        assert "stage 27 physical-time sampling/window engine is next" in status
        assert "no such engine is implemented yet" in status
    feature = (
        r"(?:physical-time frame selection|physical-time windows|contact episodes|"
        r"lifetime|protein-lipid contacts|protein-glycan contacts|canonical mapping|"
        r"replica aggregation|qc engine|publication exports)"
    )
    assert not re.search(
        rf"{feature}\s+(?:is|are|has been|have been)\s+(?:already\s+)?"
        r"(?:implemented|complete|available|operational)\b",
        text,
    )


def test_stage25_infrastructure_and_legacy_compatibility() -> None:
    text = section(SCIENTIFIC, "stage 25 infrastructure")
    for concept in (
        "required infrastructure",
        "softwareidentity",
        "run provenance",
        "artifact inventories",
        "checksum modes",
        "unified technical validation",
        "runtime/environment metadata",
        "observation-only pbc audit",
        "fair²",
    ):
        assert concept in text
    assert re.search(r"final csv/schema layout[^.]*not implemented or frozen", text)
    compatibility = section(IDENTITY, "backwards compatibility")
    for concept in (
        "no legacy manifest change",
        "trajectoryinputconfig",
        "preprocessinginputmanifest",
        "no manifest integration",
        "cli change",
        "runtime change",
        "sampling change",
        "scientific artifact change",
    ):
        assert concept in compatibility


@pytest.mark.parametrize("path", [SCIENTIFIC, IDENTITY])
def test_document_links_resolve(path: Path) -> None:
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8"))
    assert links
    for link in links:
        assert (path.parent / link).is_file(), link
