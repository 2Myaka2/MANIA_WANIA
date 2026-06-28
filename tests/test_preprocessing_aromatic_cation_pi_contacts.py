import csv
import math
from collections.abc import Iterator
from pathlib import Path

from mania.preprocessing import (
    PreprocessingConditionLoadResult,
    PreprocessingConditionRuntime,
    PreprocessingConditionRuntimeInput,
    PreprocessingContactComputationLimits,
    PreprocessingContactDetectionOptions,
    PreprocessingFrameSamplingOptions,
    compute_condition_contacts,
    validate_contact_edges_csv,
    validate_contacts_perframe_csv,
    write_contact_edges_csv,
    write_contacts_perframe_csv,
)

RING_NAMES = ("CG", "CD1", "CD2", "CE1", "CE2", "CZ")


class FakeAtom:
    def __init__(
        self,
        name: str,
        position: tuple[float, float, float],
    ) -> None:
        self.name = name
        self.element = "N" if name.startswith("N") else "C"
        self.position = position


class FakeAtomGroup:
    def __init__(self, atoms: list[FakeAtom]) -> None:
        self._atoms = atoms

    def __iter__(self) -> Iterator[FakeAtom]:
        return iter(self._atoms)


class FakeResidue:
    def __init__(
        self,
        resname: str,
        resid: int,
        atoms: list[FakeAtom],
    ) -> None:
        self.resname = resname
        self.resid = resid
        self.segid = "A"
        self.atoms = FakeAtomGroup(atoms)


class FakeTimestep:
    def __init__(
        self,
        positions: tuple[tuple[float, float, float], ...],
    ) -> None:
        self.positions = positions


class FakeTrajectory:
    def __init__(
        self,
        atoms: list[FakeAtom],
        frames: list[FakeTimestep],
    ) -> None:
        self.atoms = atoms
        self.frames = frames

    def __iter__(self) -> Iterator[FakeTimestep]:
        for frame in self.frames:
            for atom, position in zip(
                self.atoms,
                frame.positions,
                strict=True,
            ):
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
        *,
        protein_residues: list[FakeResidue] | None = None,
    ) -> None:
        self.residues = residues
        self._protein_residues = protein_residues
        atoms = [atom for residue in residues for atom in residue.atoms]
        self.trajectory = FakeTrajectory(atoms, frames)

    def select_atoms(self, selection: str) -> FakeSelection:
        assert selection == "protein"
        if self._protein_residues is None:
            raise AssertionError("protein selection was not configured")
        return FakeSelection(self._protein_residues)


def ring_positions(z: float) -> tuple[tuple[float, float, float], ...]:
    return tuple(
        (
            math.cos(index * math.pi / 3.0),
            math.sin(index * math.pi / 3.0),
            z,
        )
        for index in range(6)
    )


def aromatic_runtime(
    *,
    protein_residues: str = "all",
) -> FakeRuntime:
    phe_atoms = [
        FakeAtom(name, position)
        for name, position in zip(RING_NAMES, ring_positions(0.0), strict=True)
    ]
    tyr_atoms = [
        FakeAtom(name, position)
        for name, position in zip(RING_NAMES, ring_positions(4.0), strict=True)
    ]
    lys_atoms = [FakeAtom("NZ", (0.0, 0.0, 5.0))]
    residues = [
        FakeResidue("PHE", 10, phe_atoms),
        FakeResidue("TYR", 20, tyr_atoms),
        FakeResidue("LYS", 30, lys_atoms),
    ]
    frames = [
        FakeTimestep((*ring_positions(0.0), *ring_positions(4.0), (0.0, 0.0, 5.0))),
        FakeTimestep((*ring_positions(0.0), *ring_positions(4.0), (0.0, 0.0, 5.0))),
        FakeTimestep((*ring_positions(0.0), *ring_positions(8.0), (0.0, 0.0, 5.0))),
        FakeTimestep((*ring_positions(0.0), *ring_positions(8.0), (0.0, 0.0, 5.0))),
    ]
    selected = residues if protein_residues == "all" else [residues[0]]
    return FakeRuntime(residues, frames, protein_residues=selected)


def loaded_result(runtime: FakeRuntime) -> PreprocessingConditionLoadResult:
    runtime_input = PreprocessingConditionRuntimeInput(
        condition_name="normal",
        topology_path=Path("normal/topology.tpr"),
        trajectory_paths=(Path("normal/trajectory.xtc"),),
        frame_time_ps=2.5,
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


def computed_pi_result() -> object:
    return compute_condition_contacts(
        loaded_result(aromatic_runtime()),
        frame_sampling=PreprocessingFrameSamplingOptions(frame_stride=2),
    )


def read_dict_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def test_pi_contacts_flow_to_accumulator_with_sampled_source_frames() -> None:
    result = computed_pi_result()

    assert result.status == "computed"
    assert [frame.frame_index for frame in result.frame_results] == [0, 2]
    edge_types = {
        contact.edge_type
        for frame in result.frame_results
        for contact in frame.contacts
    }
    assert {"aromatic_pi", "cation_pi"} <= edge_types

    aggregates = {
        (row.resid_i, row.resid_j, row.edge_type): row
        for row in result.interaction_aggregates
    }
    aromatic = aggregates[(0, 1, "aromatic_pi")]
    assert aromatic.sampled_frame_count == 2
    assert aromatic.contact_freq == 0.5
    assert aromatic.first_seen_frame == 0
    assert aromatic.last_seen_frame == 0
    assert math.isclose(aromatic.mean_dist_A, 4.0)

    cation = aggregates[(0, 2, "cation_pi")]
    assert cation.sampled_frame_count == 2
    assert cation.contact_freq == 1.0
    assert cation.first_seen_frame == 0
    assert cation.last_seen_frame == 2
    assert math.isclose(cation.mean_dist_A, 5.0)


def test_typed_perframe_and_aggregate_csvs_write_and_validate(
    tmp_path: Path,
) -> None:
    result = computed_pi_result()
    perframe_path = tmp_path / "contacts_perframe.csv"
    aggregate_path = tmp_path / "contact_edges.csv"

    perframe_write = write_contacts_perframe_csv(result, perframe_path)
    aggregate_write = write_contact_edges_csv(result, aggregate_path)

    assert perframe_write.passed
    assert aggregate_write.passed
    perframe_rows = read_dict_rows(perframe_path)
    aggregate_rows = read_dict_rows(aggregate_path)
    assert {"aromatic_pi", "cation_pi"} <= {
        row["edge_type"] for row in perframe_rows
    }
    assert {"aromatic_pi", "cation_pi"} <= {
        row["edge_type"] for row in aggregate_rows
    }
    assert {
        row["frame_index"]
        for row in perframe_rows
        if row["edge_type"] in {"aromatic_pi", "cation_pi"}
    } == {"0", "2"}
    aromatic_row = next(
        row
        for row in aggregate_rows
        if row["edge_type"] == "aromatic_pi"
    )
    assert aromatic_row["contact_frame_count"] == "1"
    assert aromatic_row["total_frame_count"] == "2"
    assert float(aromatic_row["contact_frequency"]) == 0.5
    assert validate_contacts_perframe_csv(perframe_path).passed
    assert validate_contact_edges_csv(aggregate_path).passed


def test_typed_csv_validator_rejects_unknown_and_compact_edge_names(
    tmp_path: Path,
) -> None:
    result = computed_pi_result()
    output_path = tmp_path / "contacts_perframe.csv"
    write_contacts_perframe_csv(result, output_path)
    rows = read_dict_rows(output_path)
    fieldnames = list(rows[0])

    for invalid_edge_type in ("aromaticpi", "metal_coordination"):
        invalid_path = tmp_path / f"{invalid_edge_type}.csv"
        invalid_rows = [row.copy() for row in rows]
        invalid_rows[0]["edge_type"] = invalid_edge_type
        with invalid_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(invalid_rows)

        validation = validate_contacts_perframe_csv(invalid_path)
        assert validation.passed is False
        assert "invalid_edge_type" in {
            issue.kind for issue in validation.issues
        }


def test_contact_selection_protein_limits_pi_candidates_without_fallback() -> None:
    result = compute_condition_contacts(
        loaded_result(aromatic_runtime(protein_residues="phe_only")),
        options=PreprocessingContactDetectionOptions(
            contact_selection="protein"
        ),
    )

    assert result.status == "computed"
    assert all(
        contact.edge_type not in {"aromatic_pi", "cation_pi"}
        for frame in result.frame_results
        for contact in frame.contacts
    )


def test_contact_limit_prevents_pi_detection_and_fake_aggregates() -> None:
    result = compute_condition_contacts(
        loaded_result(aromatic_runtime()),
        computation_limits=PreprocessingContactComputationLimits(
            max_residue_pairs_per_frame=1
        ),
    )

    assert result.status == "partial"
    assert all(frame.contacts == () for frame in result.frame_results)
    assert result.interaction_aggregates == ()
    assert {
        issue.kind
        for frame in result.frame_results
        for issue in frame.issues
    } == {"contact_frame_limit_exceeded"}
