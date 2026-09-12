"""Explicit Dataset controls for the Stage 31 canonical postprocessing run."""

from dataclasses import dataclass, field, fields, replace
from pathlib import Path

from mania.replica_aggregation_contract import (
    REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID,
    REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256,
    ReplicaAggregationGroupSpec,
    ReplicaAggregationMember,
    build_compatible_replica_aggregation_group,
)
from mania.replica_specialized_aggregation import (
    CanonicalProteinGlycanReplicaAggregation,
    CanonicalProteinLipidReplicaAggregation,
    SpecializedPartnerCorrespondences,
)

REPLICA_AGGREGATION_MANIFEST_SCHEMA_VERSION = "mania.replica_aggregation_manifest.v0.1"
REPLICA_AGGREGATION_MANIFEST_KIND = "mania_replica_aggregation_manifest"
REPLICA_AGGREGATION_MANIFEST_FILENAME = "replica_aggregation_manifest.json"


def require_fixed_metadata(model: object) -> None:
    """Reject modified frozen contract fields, including reference identity."""
    for item in fields(model):  # type: ignore[arg-type]
        if not item.init and getattr(model, item.name) != item.default:
            raise ValueError("Fixed canonical contract metadata must match")


def aggregation_group_identity(spec: ReplicaAggregationGroupSpec) -> tuple[object, ...]:
    return (*spec.group_key, spec.window.window_id, spec.window.window_index)


@dataclass(frozen=True)
class ReplicaAggregationWorkflowGroup:
    spec: ReplicaAggregationGroupSpec
    members: tuple[ReplicaAggregationMember, ...]
    lipid_correspondences: SpecializedPartnerCorrespondences
    glycan_correspondences: SpecializedPartnerCorrespondences

    def __post_init__(self) -> None:
        group = build_compatible_replica_aggregation_group(self.spec, self.members)
        require_fixed_metadata(self.spec)
        replace(self.spec)
        replace(self.spec.window)
        for member in group.members:
            replace(member)
            replace(member.window)
        # Accepted result constructors check kind and complete coverage without
        # calculating any statistics or inspecting sparse scientific rows.
        CanonicalProteinLipidReplicaAggregation(
            group, self.lipid_correspondences, 0, ()
        )
        CanonicalProteinGlycanReplicaAggregation(
            group, self.glycan_correspondences, 0, ()
        )
        object.__setattr__(self, "members", group.members)

    def to_dict(self) -> dict[str, object]:
        return {
            "spec": self.spec.to_dict(),
            "members": [member.to_dict() for member in self.members],
            "lipid_correspondences": self.lipid_correspondences.to_dict(),
            "glycan_correspondences": self.glycan_correspondences.to_dict(),
        }


@dataclass(frozen=True)
class ReplicaAggregationManifest:
    protein_canonical_table_paths: tuple[Path, ...]
    lipid_canonical_table_paths: tuple[Path, ...]
    glycan_canonical_table_paths: tuple[Path, ...]
    groups: tuple[ReplicaAggregationWorkflowGroup, ...]
    schema_version: str = field(
        init=False, default=REPLICA_AGGREGATION_MANIFEST_SCHEMA_VERSION
    )
    kind: str = field(init=False, default=REPLICA_AGGREGATION_MANIFEST_KIND)
    canonical_reference_id: str = field(
        init=False, default=REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID
    )
    canonical_reference_sequence_sha256: str = field(
        init=False, default=REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256
    )

    def __post_init__(self) -> None:
        require_fixed_metadata(self)
        for family in ("protein", "lipid", "glycan"):
            name = f"{family}_canonical_table_paths"
            paths = getattr(self, name)
            if type(paths) is not tuple or any(not isinstance(p, Path) for p in paths):
                raise ValueError("Canonical paths must be a tuple of Paths")
            resolved = tuple(p.resolve() for p in paths)
            physical = [
                (p.stat().st_dev, p.stat().st_ino) if p.exists() else p
                for p in resolved
            ]
            if len(set(resolved)) != len(resolved) or len(set(physical)) != len(paths):
                raise ValueError("Canonical paths must identify unique physical files")
            object.__setattr__(self, name, resolved)
        if not any(
            (
                self.protein_canonical_table_paths,
                self.lipid_canonical_table_paths,
                self.glycan_canonical_table_paths,
            )
        ):
            raise ValueError("At least one canonical input table is required")
        if (
            type(self.groups) is not tuple
            or not self.groups
            or any(
                type(group) is not ReplicaAggregationWorkflowGroup
                for group in self.groups
            )
        ):
            raise ValueError(
                "groups must be a non-empty tuple of exact workflow groups"
            )
        identities = []
        for group in self.groups:
            replace(group)
            identities.append(aggregation_group_identity(group.spec))
            for family in ("lipid", "glycan"):
                if getattr(group, f"{family}_correspondences").correspondences and not (
                    getattr(self, f"{family}_canonical_table_paths")
                ):
                    raise ValueError(
                        "Specialized correspondence requires canonical input"
                    )
        if len(set(identities)) != len(identities):
            raise ValueError("Duplicate scientific aggregation group identity")
        object.__setattr__(
            self,
            "groups",
            tuple(
                sorted(
                    self.groups,
                    key=lambda g: (
                        g.spec.dataset_id,
                        g.spec.system_id,
                        g.spec.engine,
                        g.spec.window.window_index,
                        g.spec.window.physical_window_key,
                        g.spec.window.window_id,
                    ),
                )
            ),
        )
