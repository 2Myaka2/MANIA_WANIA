from collections.abc import Iterator

from mania.preprocessing.trajectory_contacts import (
    PreprocessingContactDetectionOptions,
    build_atom_cache,
)


class FakeAtom:
    def __init__(self, name: str, element: str) -> None:
        self.name = name
        self.element = element
        self.position = (0.0, 0.0, 0.0)


class FakeAtomGroup:
    def __init__(self, atoms: list[FakeAtom]) -> None:
        self._atoms = atoms
        self.iteration_count = 0

    def __iter__(self) -> Iterator[FakeAtom]:
        self.iteration_count += 1
        return iter(self._atoms)


class FakeResidue:
    def __init__(
        self,
        resname: str,
        resid: int,
        segid: str,
        atoms: list[FakeAtom],
    ) -> None:
        self.resname = resname
        self.resid = resid
        self.segid = segid
        self.atoms = FakeAtomGroup(atoms)


def test_build_atom_cache_preserves_residue_metadata_and_atom_counts() -> None:
    residues = [
        FakeResidue("ALA", 10, "PROA", [FakeAtom("CA", "C")]),
        FakeResidue(
            "GLY",
            11,
            "PROB",
            [FakeAtom("CA", "C"), FakeAtom("O", "O")],
        ),
    ]

    cache = build_atom_cache(
        residues,
        options=PreprocessingContactDetectionOptions(atom_filter="all"),
    )

    assert len(cache) == 2
    assert [entry.residue_index for entry in cache] == [0, 1]
    assert [entry.residue_id for entry in cache] == [10, 11]
    assert [entry.resname for entry in cache] == ["ALA", "GLY"]
    assert [entry.segid for entry in cache] == ["PROA", "PROB"]
    assert [entry.atom_count for entry in cache] == [1, 2]
    assert [residue.atoms.iteration_count for residue in residues] == [1, 1]


def test_build_atom_cache_heavy_filter_uses_existing_hydrogen_rules() -> None:
    residue = FakeResidue(
        "ALA",
        10,
        "PROA",
        [
            FakeAtom("CA", "C"),
            FakeAtom("1H", "H"),
            FakeAtom("H2", "C"),
            FakeAtom("O", "O"),
        ],
    )

    heavy_cache = build_atom_cache(
        [residue],
        options=PreprocessingContactDetectionOptions(atom_filter="heavy"),
    )
    all_cache = build_atom_cache(
        [residue],
        options=PreprocessingContactDetectionOptions(atom_filter="all"),
    )

    assert [atom.name for atom in heavy_cache[0].atoms] == ["CA", "O"]
    assert heavy_cache[0].atom_indexes == (0, 3)
    assert heavy_cache[0].atom_count == 2
    assert all_cache[0].atom_count == 4


def test_build_atom_cache_keeps_empty_filtered_residue_entry() -> None:
    residue = FakeResidue(
        "GLY",
        11,
        "PROA",
        [FakeAtom("H1", "H")],
    )

    cache = build_atom_cache(
        [residue],
        options=PreprocessingContactDetectionOptions(atom_filter="heavy"),
    )

    assert len(cache) == 1
    assert cache[0].contact_eligible is True
    assert cache[0].atoms == ()
    assert cache[0].atom_count == 0
    assert cache[0].issues == ()
