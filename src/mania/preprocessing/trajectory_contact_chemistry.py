"""Deterministic residue chemistry for aromatic and cation-π contacts."""

from __future__ import annotations

from dataclasses import dataclass

from mania.preprocessing.trajectory_interaction_geometry import (
    AromaticRingGeometry,
    Coordinate,
    build_aromatic_ring_geometry,
    detect_aromatic_pi_geometry,
    detect_cation_pi_distance,
)

_AROMATIC_RING_ATOMS = {
    "PHE": ("CG", "CD1", "CD2", "CE1", "CE2", "CZ"),
    "TYR": ("CG", "CD1", "CD2", "CE1", "CE2", "CZ"),
    "TRP": (
        "CG",
        "CD1",
        "CD2",
        "NE1",
        "CE2",
        "CE3",
        "CZ2",
        "CZ3",
        "CH2",
    ),
    "HIS": ("CG", "ND1", "CD2", "CE1", "NE2"),
    "HID": ("CG", "ND1", "CD2", "CE1", "NE2"),
    "HIE": ("CG", "ND1", "CD2", "CE1", "NE2"),
    "HIP": ("CG", "ND1", "CD2", "CE1", "NE2"),
}
_CATION_CENTER_ATOMS = {
    "LYS": "NZ",
    "ARG": "CZ",
}
_PI_EDGE_TYPES = ("aromatic_pi", "cation_pi")


@dataclass(frozen=True)
class ResidueChemistryCandidate:
    """Selected residue identity and its available named coordinates."""

    residue_index: int
    residue_id: int | str | None
    resname: str
    segid: str | None
    atom_coordinates: tuple[tuple[str, Coordinate], ...]


@dataclass(frozen=True)
class AromaticRingCandidate:
    """One supported residue with a complete aromatic ring."""

    residue: ResidueChemistryCandidate
    geometry: AromaticRingGeometry


@dataclass(frozen=True)
class CationCenterCandidate:
    """One supported residue with a deterministic cation center."""

    residue: ResidueChemistryCandidate
    center: Coordinate


@dataclass(frozen=True)
class PiInteractionObservation:
    """One typed residue-pair interaction observed in one frame."""

    source: ResidueChemistryCandidate
    target: ResidueChemistryCandidate
    edge_type: str
    distance_A: float
    aromatic_pi_mode: str | None = None

    def __post_init__(self) -> None:
        if self.source.residue_index >= self.target.residue_index:
            raise ValueError("source residue index must precede target")
        if self.edge_type not in _PI_EDGE_TYPES:
            raise ValueError("edge_type must be aromatic_pi or cation_pi")


def build_aromatic_ring_candidate(
    residue: ResidueChemistryCandidate,
) -> AromaticRingCandidate | None:
    """Build a complete supported aromatic ring, skipping incomplete data."""
    required_names = _AROMATIC_RING_ATOMS.get(residue.resname.upper())
    if required_names is None:
        return None
    coordinates_by_name = dict(residue.atom_coordinates)
    if any(name not in coordinates_by_name for name in required_names):
        return None
    geometry = build_aromatic_ring_geometry(
        tuple(coordinates_by_name[name] for name in required_names)
    )
    if geometry is None:
        return None
    return AromaticRingCandidate(residue=residue, geometry=geometry)


def build_cation_center_candidate(
    residue: ResidueChemistryCandidate,
) -> CationCenterCandidate | None:
    """Return LYS NZ or ARG CZ as the supported cation center."""
    center_name = _CATION_CENTER_ATOMS.get(residue.resname.upper())
    if center_name is None:
        return None
    coordinates_by_name = dict(residue.atom_coordinates)
    center = coordinates_by_name.get(center_name)
    if center is None:
        return None
    return CationCenterCandidate(residue=residue, center=center)


def detect_pi_interactions(
    residues: tuple[ResidueChemistryCandidate, ...],
) -> tuple[PiInteractionObservation, ...]:
    """Detect aromatic π–π and cation-π contacts for selected residues."""
    ring_candidates: list[AromaticRingCandidate] = []
    cation_candidates: list[CationCenterCandidate] = []
    for residue in residues:
        ring_candidate = build_aromatic_ring_candidate(residue)
        if ring_candidate is not None:
            ring_candidates.append(ring_candidate)
        cation_candidate = build_cation_center_candidate(residue)
        if cation_candidate is not None:
            cation_candidates.append(cation_candidate)
    rings = tuple(ring_candidates)
    cations = tuple(cation_candidates)
    observations = [*_aromatic_pi_observations(rings)]
    observations.extend(_cation_pi_observations(cations, rings))
    return tuple(
        sorted(
            observations,
            key=lambda item: (
                item.source.residue_index,
                item.target.residue_index,
                item.edge_type,
                item.distance_A,
            ),
        )
    )


def _aromatic_pi_observations(
    rings: tuple[AromaticRingCandidate, ...],
) -> tuple[PiInteractionObservation, ...]:
    observations: list[PiInteractionObservation] = []
    for source_offset, source_ring in enumerate(rings):
        for target_ring in rings[source_offset + 1 :]:
            geometry = detect_aromatic_pi_geometry(
                source_ring.geometry,
                target_ring.geometry,
            )
            if geometry is None:
                continue
            source, target = _canonical_residues(
                source_ring.residue,
                target_ring.residue,
            )
            observations.append(
                PiInteractionObservation(
                    source=source,
                    target=target,
                    edge_type="aromatic_pi",
                    distance_A=geometry.distance_A,
                    aromatic_pi_mode=geometry.mode,
                )
            )
    return tuple(observations)


def _cation_pi_observations(
    cations: tuple[CationCenterCandidate, ...],
    rings: tuple[AromaticRingCandidate, ...],
) -> tuple[PiInteractionObservation, ...]:
    observations_by_pair: dict[
        tuple[int, int],
        PiInteractionObservation,
    ] = {}
    for cation in cations:
        for ring in rings:
            if cation.residue.residue_index == ring.residue.residue_index:
                continue
            distance = detect_cation_pi_distance(
                cation.center,
                ring.geometry.centroid,
            )
            if distance is None:
                continue
            source, target = _canonical_residues(
                cation.residue,
                ring.residue,
            )
            key = (source.residue_index, target.residue_index)
            observation = PiInteractionObservation(
                source=source,
                target=target,
                edge_type="cation_pi",
                distance_A=distance,
            )
            previous = observations_by_pair.get(key)
            if previous is None or distance < previous.distance_A:
                observations_by_pair[key] = observation
    return tuple(observations_by_pair.values())


def _canonical_residues(
    first: ResidueChemistryCandidate,
    second: ResidueChemistryCandidate,
) -> tuple[ResidueChemistryCandidate, ResidueChemistryCandidate]:
    if second.residue_index < first.residue_index:
        return second, first
    return first, second


__all__ = [
    "AromaticRingCandidate",
    "CationCenterCandidate",
    "PiInteractionObservation",
    "ResidueChemistryCandidate",
    "build_aromatic_ring_candidate",
    "build_cation_center_candidate",
    "detect_pi_interactions",
]
