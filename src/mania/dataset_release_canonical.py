"""Pinned canonical nodes and explicitly selected complete system annotations."""

from collections.abc import Iterable
from dataclasses import asdict, replace

from mania.biological_annotations import DatasetSystemBiologicalAnnotations
from mania.canonical_reference_io import load_default_napi2b_canonical_reference
from mania.dataset_release_csv import DatasetReleaseTable, build_publication_table


class DatasetReleaseCanonicalError(ValueError):
    """Missing complete-system authority or invalid annotation selection."""


def build_dataset_release_nodes() -> DatasetReleaseTable:
    """Use only the accepted packaged reference API, never observed residues."""
    reference = load_default_napi2b_canonical_reference()
    return build_publication_table(
        "nodes",
        (
            dict(
                canonical_reference_id=reference.reference_id,
                canonical_reference_sequence_sha256=reference.sequence_sha256,
                canonical_residue_number=r.canonical_residue_number,
                canonical_resname=r.canonical_resname,
            )
            for r in reference.residues()
        ),
    )


def build_dataset_release_residue_annotations(
    metadata: tuple[DatasetSystemBiologicalAnnotations, ...],
    *,
    annotation_publication_system_keys: Iterable[tuple[str, str]],
) -> DatasetReleaseTable:
    selected = tuple(annotation_publication_system_keys)
    if any(
        type(k) is not tuple
        or len(k) != 2
        or any(type(v) is not str or not v.strip() for v in k)
        for k in selected
    ) or len(set(selected)) != len(selected):
        raise DatasetReleaseCanonicalError(
            "Selected system keys must be exact and unique"
        )
    if type(metadata) is not tuple or any(
        type(m) is not DatasetSystemBiologicalAnnotations for m in metadata
    ):
        raise DatasetReleaseCanonicalError("Expected accepted Stage 30 system metadata")
    by_key = {}
    for item in metadata:
        replace(item)  # Accepted complete_for_system and nested site validation.
        key = (item.dataset_id, item.system_id)
        if key in by_key:
            raise DatasetReleaseCanonicalError("Duplicate annotation system metadata")
        by_key[key] = item
    if not set(selected) <= by_key.keys():
        raise DatasetReleaseCanonicalError(
            "Selected system lacks complete_for_system metadata"
        )
    reference = load_default_napi2b_canonical_reference()
    rows: list[dict[str, object]] = []
    for key in sorted(selected):
        system = by_key[key]
        variants = {
            "disulfide": {
                s.canonical_residue_number: s for s in system.disulfide_variant_sites
            },
            "cysteine": {
                s.canonical_residue_number: s for s in system.cysteine_variant_sites
            },
        }
        for residue in reference.residues():
            number = residue.canonical_residue_number
            row: dict[str, object] = dict(
                dataset_id=key[0],
                system_id=key[1],
                canonical_reference_id=reference.reference_id,
                annotation_scope=system.annotation_scope,
                **asdict(system.annotation_for_residue(number)),
            )
            # The accepted per-residue annotation omits variant provenance, but
            # the authoritative system site records and frozen 33.A schema keep it.
            for kind, sites in variants.items():
                site = sites.get(number)
                row[f"{kind}_variant_source"] = site.source if site else None
                row[f"{kind}_variant_verifier"] = site.verifier if site else None
            rows.append(row)
    return build_publication_table("residue_annotations", rows)
