"""QC-authoritative publication projections of accepted Stage 31 aggregate rows."""

from dataclasses import dataclass, replace
from pathlib import Path

from mania.dataset_qc_contract import DatasetQCDecisionSet
from mania.dataset_release_csv import DatasetReleaseTable
from mania.dataset_release_metadata import DatasetReleaseMetadataTables
from mania.dataset_release_science import (
    DatasetReleaseScienceError,
    project_publication_rows,
    publication_metadata_index,
    require_publication_reference,
    validate_dataset_release_scientific_relationships,
)
from mania.replica_aggregation_manifest import (
    ReplicaAggregationManifest,
    ReplicaAggregationWorkflowGroup,
    aggregation_group_identity,
    require_fixed_metadata,
)
from mania.replica_aggregation_tables import (
    CanonicalProteinEdgeReplicaAggregationRow,
    CanonicalProteinEdgeReplicaAggregationTable,
    CanonicalProteinGlycanReplicaAggregationRow,
    CanonicalProteinGlycanReplicaAggregationTable,
    CanonicalProteinLipidReplicaAggregationRow,
    CanonicalProteinLipidReplicaAggregationTable,
)


@dataclass(frozen=True)
class DatasetReleaseAggregationAuthority:
    """Pure model-level QC/manifest/run binding; 33.D proves file provenance.

    The caller supplies the manifest from the completed Stage 32 bridge and the
    exact manifest used by the supplied Stage 31 run. A boolean attestation or a
    pre-QC template is insufficient. No QC or aggregation evaluator is invoked.
    """

    decisions: DatasetQCDecisionSet
    qc_derived_aggregation_manifest: ReplicaAggregationManifest
    aggregation_manifest_used: ReplicaAggregationManifest

    def __post_init__(self) -> None:
        if type(self.decisions) is not DatasetQCDecisionSet or any(
            type(m) is not ReplicaAggregationManifest
            for m in (
                self.qc_derived_aggregation_manifest,
                self.aggregation_manifest_used,
            )
        ):
            raise DatasetReleaseScienceError("Expected accepted Stage 32/31 authority")
        require_fixed_metadata(self.decisions)
        replace(self.decisions)
        for decision in self.decisions.records:
            if replace(decision) != decision:
                raise DatasetReleaseScienceError("QC decision model is inconsistent")
            if decision.release_decision == "pending_review":
                raise DatasetReleaseScienceError("Pending review forbids publication")
        manifest = self.qc_derived_aggregation_manifest
        if self.aggregation_manifest_used != manifest:
            raise DatasetReleaseScienceError(
                "Aggregation manifest used must equal the QC-derived manifest"
            )
        require_fixed_metadata(manifest)
        require_publication_reference(manifest)
        # The accepted manifest constructor resolves/stats paths. Validate its
        # structure here without reconstructing it or accessing source artifacts.
        paths = (
            manifest.protein_canonical_table_paths,
            manifest.lipid_canonical_table_paths,
            manifest.glycan_canonical_table_paths,
        )
        if not any(paths) or any(
            type(ps) is not tuple
            or any(not isinstance(p, Path) for p in ps)
            or len(set(ps)) != len(ps)
            for ps in paths
        ):
            raise DatasetReleaseScienceError("Invalid accepted manifest source paths")
        if type(manifest.groups) is not tuple or not manifest.groups:
            raise DatasetReleaseScienceError("Authority requires manifest groups")
        keys = set()
        members = set()
        decisions = {d.replica_key: d for d in self.decisions.records}
        for group in manifest.groups:
            if type(group) is not ReplicaAggregationWorkflowGroup or (
                replace(group) != group
            ):
                raise DatasetReleaseScienceError("Invalid accepted manifest group")
            key = aggregation_group_identity(group.spec)
            if key in keys:
                raise DatasetReleaseScienceError("Duplicate aggregation group")
            keys.add(key)
            for family in ("lipid", "glycan"):
                if getattr(group, f"{family}_correspondences").correspondences and not (
                    getattr(manifest, f"{family}_canonical_table_paths")
                ):
                    raise DatasetReleaseScienceError(
                        "Correspondence lacks source family"
                    )
            for member in group.members:
                members.add(member.replica_key)
                member_decision = decisions.get(member.replica_key)
                if member_decision is None or (
                    member.availability_status != "unavailable"
                    and member.availability_status != member_decision.release_decision
                ):
                    raise DatasetReleaseScienceError(
                        "QC decisions and derived availability disagree"
                    )
        if members != decisions.keys():
            raise DatasetReleaseScienceError("QC/manifest replica coverage must match")


def _build_aggregates(
    source: CanonicalProteinEdgeReplicaAggregationTable
    | CanonicalProteinLipidReplicaAggregationTable
    | CanonicalProteinGlycanReplicaAggregationTable,
    table_type: type,
    row_type: type,
    table_id: str,
    family: str,
    authority: DatasetReleaseAggregationAuthority,
    metadata_tables: DatasetReleaseMetadataTables,
) -> DatasetReleaseTable:
    if type(authority) is not DatasetReleaseAggregationAuthority:
        raise DatasetReleaseScienceError(
            "Explicit QC-derived aggregate authority required"
        )
    replace(authority)
    if type(source) is not table_type:
        raise DatasetReleaseScienceError("Expected exact Stage 31 aggregate table")
    require_publication_reference(source)
    if type(source.rows) is not tuple or any(
        type(row) is not row_type for row in source.rows
    ):
        raise DatasetReleaseScienceError("Expected immutable accepted aggregate rows")
    simulations = publication_metadata_index(metadata_tables, "simulations")
    groups = {
        aggregation_group_identity(g.spec): g
        for g in authority.qc_derived_aggregation_manifest.groups
    }
    decisions = {d.replica_key: d for d in authority.decisions.records}
    for group in groups.values():
        for member in group.members:
            simulation = simulations.get(member.replica_key)
            if simulation is None:
                raise DatasetReleaseScienceError("Aggregate member lacks simulation")
            available = member.availability_status == "available"
            if simulation["included_in_replica_aggregation"] is not available or (
                simulation["aggregation_availability_status"]
                != member.availability_status
            ):
                raise DatasetReleaseScienceError(
                    "Simulation aggregation inclusion disagrees"
                )
            if (
                any(
                    simulation[n] != getattr(member, n)
                    for n in ("engine", "variant_id", "condition", "disulfide_state")
                )
                or simulation["release_decision"]
                != decisions[member.replica_key].release_decision
            ):
                raise DatasetReleaseScienceError(
                    "Aggregate simulation metadata disagrees"
                )
    for row in source.rows:
        row_group = groups.get(row.group_identity)
        if row_group is None:
            raise DatasetReleaseScienceError("Aggregate row lacks exact group/window")
        if any(
            getattr(row, n) != getattr(row_group.spec, n)
            for n in ("variant_id", "condition", "disulfide_state")
        ):
            raise DatasetReleaseScienceError("Aggregate group metadata disagrees")
        available_count = sum(
            m.availability_status == "available" for m in row_group.members
        )
        if not available_count or row.n_replicates_available != available_count:
            raise DatasetReleaseScienceError(
                "Aggregate available denominator disagrees"
            )
        if family != "protein":
            assert isinstance(
                row,
                (
                    CanonicalProteinLipidReplicaAggregationRow,
                    CanonicalProteinGlycanReplicaAggregationRow,
                ),
            )
            correspondences = getattr(
                row_group, f"{family}_correspondences"
            ).correspondences
            matched = tuple(
                c
                for c in correspondences
                if c.partner_correspondence_id == row.partner_correspondence_id
            )
            if len(matched) != 1 or matched[0].partner_name != row.partner_name:
                raise DatasetReleaseScienceError(
                    "Unknown or inconsistent correspondence"
                )
    table = project_publication_rows(
        table_id, source.rows, source.canonical_reference_id
    )
    validate_dataset_release_scientific_relationships((table,), metadata_tables)
    return table


def build_dataset_release_protein_aggregates(
    source: CanonicalProteinEdgeReplicaAggregationTable,
    *,
    authority: DatasetReleaseAggregationAuthority,
    metadata_tables: DatasetReleaseMetadataTables,
) -> DatasetReleaseTable:
    return _build_aggregates(
        source,
        CanonicalProteinEdgeReplicaAggregationTable,
        CanonicalProteinEdgeReplicaAggregationRow,
        "protein_edges_by_window_replica_aggregation",
        "protein",
        authority,
        metadata_tables,
    )


def build_dataset_release_lipid_aggregates(
    source: CanonicalProteinLipidReplicaAggregationTable,
    *,
    authority: DatasetReleaseAggregationAuthority,
    metadata_tables: DatasetReleaseMetadataTables,
) -> DatasetReleaseTable:
    return _build_aggregates(
        source,
        CanonicalProteinLipidReplicaAggregationTable,
        CanonicalProteinLipidReplicaAggregationRow,
        "protein_lipid_contacts_by_window_replica_aggregation",
        "lipid",
        authority,
        metadata_tables,
    )


def build_dataset_release_glycan_aggregates(
    source: CanonicalProteinGlycanReplicaAggregationTable,
    *,
    authority: DatasetReleaseAggregationAuthority,
    metadata_tables: DatasetReleaseMetadataTables,
) -> DatasetReleaseTable:
    return _build_aggregates(
        source,
        CanonicalProteinGlycanReplicaAggregationTable,
        CanonicalProteinGlycanReplicaAggregationRow,
        "protein_glycan_contacts_by_window_replica_aggregation",
        "glycan",
        authority,
        metadata_tables,
    )
