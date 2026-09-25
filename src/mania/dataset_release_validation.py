"""Pure complete-release relationships, without recalculating upstream science."""

from dataclasses import replace

from mania.dataset_qc_summary import build_dataset_qc_summary
from mania.dataset_release_aggregates import DatasetReleaseAggregationAuthority
from mania.dataset_release_canonical import build_dataset_release_nodes
from mania.dataset_release_contract import (
    PUBLICATION_TABLE_SPECS,
    REPLICA_KEY,
    SYSTEM_KEY,
)
from mania.dataset_release_csv import DatasetReleaseTable, publication_number
from mania.dataset_release_manifest import DatasetReleaseExportManifest
from mania.dataset_release_metadata import (
    DatasetReleaseMetadataTables,
    QCDerivedAggregationEvidence,
    build_dataset_release_simulations,
)
from mania.dataset_release_qc import build_dataset_release_qc_tables
from mania.dataset_release_science import (
    DatasetReleaseScientificTables,
    validate_dataset_release_scientific_relationships,
)


def validate_dataset_release_tables(
    metadata: DatasetReleaseMetadataTables,
    science: DatasetReleaseScientificTables,
    authority: DatasetReleaseAggregationAuthority,
    control: DatasetReleaseExportManifest,
) -> None:
    """Enforce frozen FKs plus exact historical population and aggregate authority."""
    replace(metadata)
    replace(science)
    replace(authority)
    replace(control)
    if any(
        g.spec.window.boundary_profile != metadata.boundary_profile
        for g in authority.qc_derived_aggregation_manifest.groups
    ):
        raise ValueError("Release temporal boundary profile differs from authority")
    tables = (*metadata.tables, *science.tables)
    if {t.spec for t in tables} != set(PUBLICATION_TABLE_SPECS) or len(tables) != 17:
        raise ValueError(
            "Release must contain exactly the 17 frozen publication tables"
        )
    for table in tables:
        DatasetReleaseTable(table.spec, table.rows)
    # 33.B checks every metadata FK; 33.C checks every science/aggregate/metric
    # FK, including the explicitly nullable replica-global metric window link.
    validate_dataset_release_scientific_relationships(science.tables, metadata)
    if metadata.nodes != build_dataset_release_nodes():
        raise ValueError("Release nodes must equal the accepted 690-position reference")
    expected_qc = build_dataset_release_qc_tables(
        authority.decisions,
        build_dataset_qc_summary(authority.decisions),
    )
    for name in (
        "quality_control",
        "quality_control_findings",
        "quality_control_evidence",
    ):
        if getattr(metadata, name) != getattr(expected_qc, name):
            raise ValueError(
                "QC historical population and all findings/evidence must remain exact"
            )
    if metadata.simulations != build_dataset_release_simulations(
        authority.decisions,
        QCDerivedAggregationEvidence(
            authority.qc_derived_aggregation_manifest,
            authority.decisions,
            "qc_derived_replica_aggregation_manifest",
            control.qc_derived_manifest_path,
        ),
        scientific_release_replica_keys=control.scientific_release_replica_keys,
    ):
        raise ValueError("Simulation historical population/decisions/inclusion differs")
    systems = {tuple(r[n] for n in SYSTEM_KEY): r for r in metadata.systems.records()}
    if set(systems) != set(control.annotation_publication_system_keys):
        raise ValueError(
            "Every published system requires complete annotation selection"
        )
    if set(systems) != {
        tuple(r[n] for n in SYSTEM_KEY) for r in metadata.simulations.records()
    }:
        raise ValueError("System population must equal historical simulation systems")
    for row in metadata.simulations.records():
        system = systems[tuple(row[n] for n in SYSTEM_KEY)]
        if any(
            row[n] != system[n]
            for n in ("engine", "variant_id", "condition", "disulfide_state")
        ):
            raise ValueError("Duplicated system/simulation metadata differs")
    for key in systems:
        annotations = [
            r
            for r in metadata.residue_annotations.records()
            if tuple(r[n] for n in SYSTEM_KEY) == key
        ]
        if len(annotations) != 690 or {
            r["canonical_residue_number"] for r in annotations
        } != set(range(1, 691)):
            raise ValueError("Selected systems require all 690 annotation rows")
    nodes = {r["canonical_residue_number"]: r for r in metadata.nodes.records()}
    for row in metadata.residue_annotations.records():
        if (
            row["canonical_resname"]
            != nodes[row["canonical_residue_number"]]["canonical_resname"]
        ):
            raise ValueError("Annotation canonical name differs from pinned node")
    # Explicit sparse coverage is carried by files, never by a positive row count.
    candidates = {
        tuple(r[n] for n in REPLICA_KEY) for r in metadata.simulations.records()
    }
    for family in ("protein", "lipid", "glycan"):
        coverage = {
            k
            for b in control.canonical_bindings
            if b.family == family
            for k in b.replica_keys
        }
        if (
            not coverage <= candidates
            or not set(control.scientific_release_replica_keys) <= coverage
        ):
            raise ValueError("Required scientific family artifact coverage is missing")
    groups = authority.qc_derived_aggregation_manifest.groups
    for family, table in (
        ("protein", science.protein_edges_by_window_replica_aggregation),
        ("lipid", science.protein_lipid_contacts_by_window_replica_aggregation),
        ("glycan", science.protein_glycan_contacts_by_window_replica_aggregation),
    ):
        for row in table.records():
            matches = []
            for group in groups:
                spec = group.spec
                expected = {
                    **{
                        n: getattr(spec, n)
                        for n in (
                            *SYSTEM_KEY,
                            "engine",
                            "variant_id",
                            "condition",
                            "disulfide_state",
                        )
                    },
                    **{
                        k: v for k, v in spec.window.to_dict().items()
                        if k != "boundary_profile"
                    },
                }
                if all(
                    row[n] == (publication_number(v) if type(v) is float else v)
                    for n, v in expected.items()
                ):
                    matches.append(group)
            if len(matches) != 1:
                raise ValueError(
                    "Aggregate lacks exact authoritative system/group/window"
                )
            group = matches[0]
            if row["n_replicates_available"] != sum(
                m.availability_status == "available" for m in group.members
            ):
                raise ValueError(
                    "Aggregate denominator differs from authoritative members"
                )
            if family != "protein":
                correspondences = getattr(
                    group, f"{family}_correspondences"
                ).correspondences
                if not any(
                    c.partner_correspondence_id == row["partner_correspondence_id"]
                    and c.partner_name == row["partner_name"]
                    for c in correspondences
                ):
                    raise ValueError(
                        "Aggregate correspondence lacks exact group/family authority"
                    )
