import csv
import math
from collections.abc import Iterator
from pathlib import Path

from mania.constants import EDGE_TYPE_PRIORITY
from mania.preprocessing import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRuntime,
    PreprocessingConditionRuntimeInput,
    PreprocessingContactDetectionOptions,
    PreprocessingGraphEdgeMappingRecord,
    ResidueChemistryCandidate,
    compute_condition_contacts,
    detect_protein_rin_interactions,
    write_preprocessing_protein_contact_artifacts_csv,
)


def candidate(
    residue_index: int,
    resname: str,
    atoms: tuple[tuple[str, tuple[float, float, float]], ...],
    *,
    donor_hydrogens: tuple[
        tuple[str, tuple[tuple[float, float, float], ...]], ...
    ] = (),
) -> ResidueChemistryCandidate:
    return ResidueChemistryCandidate(
        residue_index=residue_index,
        residue_id=10 + residue_index,
        resname=resname,
        segid="A",
        atom_coordinates=atoms,
        donor_hydrogen_coordinates=donor_hydrogens,
    )


def detected_by_type(
    *residues: ResidueChemistryCandidate,
) -> dict[str, float]:
    return {
        observation.edge_type: observation.distance_A
        for observation in detect_protein_rin_interactions(residues)
    }


def test_hbond_requires_explicit_hydrogen_and_angle_geometry() -> None:
    donor = candidate(
        0,
        "SER",
        (("N", (0.0, 0.0, 0.0)), ("H", (1.0, 0.0, 0.0))),
        donor_hydrogens=(("N", ((1.0, 0.0, 0.0),)),),
    )
    acceptor = candidate(1, "ASP", (("OD1", (2.8, 0.0, 0.0)),))
    without_bonded_hydrogen = candidate(
        0,
        "SER",
        donor.atom_coordinates,
    )
    bad_angle_acceptor = candidate(1, "ASP", (("OD1", (1.0, 1.0, 0.0)),))

    assert math.isclose(detected_by_type(donor, acceptor)["hbond"], 2.8)
    assert "hbond" not in detected_by_type(without_bonded_hydrogen, acceptor)
    assert "hbond" not in detected_by_type(donor, bad_angle_acceptor)


def test_disulfide_uses_only_cysteine_sg_atoms_at_or_below_cutoff() -> None:
    first = candidate(0, "CYS", (("SG", (0.0, 0.0, 0.0)),))
    second = candidate(1, "CYS", (("SG", (2.2, 0.0, 0.0)),))
    wrong_residue = candidate(1, "MET", (("SG", (2.0, 0.0, 0.0)),))

    assert detected_by_type(first, second)["disulfide"] == 2.2
    assert "disulfide" not in detected_by_type(first, wrong_residue)


def test_vdw_uses_protein_heavy_atom_minimum_distance_window() -> None:
    first = candidate(
        0,
        "GLY",
        (("CA", (0.0, 0.0, 0.0)), ("H", (2.9, 0.0, 0.0))),
    )
    in_window = candidate(1, "SER", (("OG", (3.5, 0.0, 0.0)),))
    too_close = candidate(1, "SER", (("OG", (2.9, 0.0, 0.0)),))

    assert detected_by_type(first, in_window)["vdw"] == 3.5
    assert "vdw" not in detected_by_type(first, too_close)


def test_hydrophobic_requires_supported_pair_and_both_cb_atoms() -> None:
    ala = candidate(0, "ALA", (("CB", (0.0, 0.0, 0.0)),))
    tyr = candidate(1, "TYR", (("CB", (5.0, 0.0, 0.0)),))
    incomplete = candidate(1, "TYR", (("CA", (5.0, 0.0, 0.0)),))

    assert detected_by_type(ala, tyr)["hydrophobic"] == 5.0
    assert "hydrophobic" not in detected_by_type(ala, incomplete)


def test_ionic_and_salt_bridge_are_distinct_overlapping_semantics() -> None:
    lys = candidate(0, "LYS", (("NZ", (0.0, 0.0, 0.0)),))
    asp = candidate(1, "ASP", (("OD1", (3.8, 0.0, 0.0)),))
    histidine = candidate(0, "HIE", (("NE2", (0.0, 0.0, 0.0)),))
    glu = candidate(1, "GLU", (("OE1", (5.5, 0.0, 0.0)),))

    lys_asp = detected_by_type(lys, asp)
    his_glu = detected_by_type(histidine, glu)
    assert lys_asp["ionic"] == 3.8
    assert lys_asp["salt_bridge"] == 3.8
    assert his_glu["ionic"] == 5.5
    assert "salt_bridge" not in his_glu


class FakeBond:
    def __init__(self, first: "FakeAtom", second: "FakeAtom") -> None:
        self.first = first
        self.second = second

    def partner(self, atom: "FakeAtom") -> "FakeAtom":
        return self.second if atom is self.first else self.first


class FakeAtom:
    def __init__(
        self,
        name: str,
        element: str,
        position: tuple[float, float, float],
    ) -> None:
        self.name = name
        self.element = element
        self.position = position
        self.bonds: list[FakeBond] = []


class FakeAtomGroup:
    def __init__(self, atoms: list[FakeAtom]) -> None:
        self.atoms = atoms

    def __iter__(self) -> Iterator[FakeAtom]:
        return iter(self.atoms)


class FakeResidue:
    def __init__(self, resname: str, resid: int, atoms: list[FakeAtom]) -> None:
        self.resname = resname
        self.resid = resid
        self.segid = "A"
        self.atoms = FakeAtomGroup(atoms)


class FakeTimestep:
    def __init__(self, positions: tuple[tuple[float, float, float], ...]) -> None:
        self.positions = positions


class FakeTrajectory:
    def __init__(self, atoms: list[FakeAtom], frames: list[FakeTimestep]) -> None:
        self.atoms = atoms
        self.frames = frames

    def __iter__(self) -> Iterator[FakeTimestep]:
        for frame in self.frames:
            for atom, position in zip(self.atoms, frame.positions, strict=True):
                atom.position = position
            yield frame


class FakeSelection:
    def __init__(self, residues: list[FakeResidue]) -> None:
        self.residues = residues


class FakeRuntime:
    def __init__(
        self,
        residues: list[FakeResidue],
        frames: list[FakeTimestep],
    ) -> None:
        self.residues = residues
        atoms = [atom for residue in residues for atom in residue.atoms]
        self.trajectory = FakeTrajectory(atoms, frames)

    def select_atoms(self, selection: str) -> FakeSelection:
        assert selection == "protein"
        return FakeSelection(self.residues)


def loaded_result(runtime: FakeRuntime) -> PreprocessingConditionLoadResult:
    runtime_input = PreprocessingConditionRuntimeInput(
        condition_name="normal",
        topology_path=Path("normal/topology.tpr"),
        trajectory_paths=(Path("normal/trajectory.xtc"),),
        frame_time_ps=2.0,
    )
    return PreprocessingConditionLoadResult(
        condition_name="normal",
        runtime_input=runtime_input,
        runtime=PreprocessingConditionRuntime(
            condition_name="normal",
            runtime_object=runtime,
            runtime_type="tests.FakeRuntime",
            topology_path=runtime_input.topology_path,
            trajectory_paths=runtime_input.trajectory_paths,
        ),
        status="loaded",
    )


def test_sampled_pipeline_preserves_overlap_frequency_and_distance_aggregation(
    tmp_path: Path,
) -> None:
    lys = FakeAtom("NZ", "N", (0.0, 0.0, 0.0))
    asp = FakeAtom("OD1", "O", (3.8, 0.0, 0.0))
    runtime = FakeRuntime(
        [FakeResidue("LYS", 10, [lys]), FakeResidue("ASP", 20, [asp])],
        [
            FakeTimestep(((0.0, 0.0, 0.0), (3.8, 0.0, 0.0))),
            FakeTimestep(((0.0, 0.0, 0.0), (5.0, 0.0, 0.0))),
        ],
    )

    result = compute_condition_contacts(
        loaded_result(runtime),
        options=PreprocessingContactDetectionOptions(contact_selection="protein"),
    )

    assert result.passed
    assert [
        (
            contact.source_residue_index,
            contact.target_residue_index,
            contact.edge_type,
        )
        for contact in result.frame_results[0].contacts
    ] == [
        (0, 1, "ionic"),
        (0, 1, "residue_contact"),
        (0, 1, "salt_bridge"),
        (0, 1, "vdw"),
    ]
    aggregates = {row.edge_type: row for row in result.interaction_aggregates}
    assert aggregates["ionic"].contact_freq == 1.0
    assert math.isclose(aggregates["ionic"].mean_dist_A, 4.4)
    assert math.isclose(aggregates["ionic"].std_dist_A, 0.6)
    for edge_type in ("residue_contact", "salt_bridge", "vdw"):
        assert aggregates[edge_type].contact_freq == 0.5

    written = write_preprocessing_protein_contact_artifacts_csv(result, tmp_path)
    assert written.passed
    with written.artifacts[0].edge_path.open(encoding="utf-8", newline="") as file:
        edge_rows = list(csv.DictReader(file))
    assert [row["edge_type"] for row in edge_rows] == [
        "ionic",
        "residue_contact",
        "salt_bridge",
        "vdw",
    ]
    assert all(row["weight"] == row["contact_freq"] for row in edge_rows)


def test_pipeline_hbond_requires_runtime_bonded_hydrogen() -> None:
    donor = FakeAtom("N", "N", (0.0, 0.0, 0.0))
    hydrogen = FakeAtom("H", "H", (1.0, 0.0, 0.0))
    acceptor = FakeAtom("OD1", "O", (2.8, 0.0, 0.0))
    bond = FakeBond(donor, hydrogen)
    donor.bonds.append(bond)
    hydrogen.bonds.append(bond)
    runtime = FakeRuntime(
        [
            FakeResidue("SER", 10, [donor, hydrogen]),
            FakeResidue("ASP", 20, [acceptor]),
        ],
        [
            FakeTimestep(
                ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.8, 0.0, 0.0))
            )
        ],
    )

    result = compute_condition_contacts(
        loaded_result(runtime),
        options=PreprocessingContactDetectionOptions(
            contact_selection="protein"
        ),
    )

    assert "hbond" in {
        contact.edge_type for contact in result.frame_results[0].contacts
    }


def test_edge_priority_includes_fallback_and_preserves_all_types() -> None:
    assert EDGE_TYPE_PRIORITY == (
        "backbone",
        "hbond",
        "disulfide",
        "salt_bridge",
        "ionic",
        "cation_pi",
        "aromatic_pi",
        "hydrophobic",
        "vdw",
        "residue_contact",
    )
    edge = PreprocessingGraphEdgeMappingRecord(
        edge_id="overlap",
        source_node_id="n1",
        target_node_id="n2",
        condition_name="normal",
        edge_kind="residue_contact",
        all_edge_types=(
            "residue_contact",
            "vdw",
            "ionic",
            "salt_bridge",
            "hbond",
            "backbone",
        ),
    )

    assert edge.edge_kind == "backbone"
    assert edge.all_edge_types == (
        "backbone",
        "hbond",
        "salt_bridge",
        "ionic",
        "vdw",
        "residue_contact",
    )
