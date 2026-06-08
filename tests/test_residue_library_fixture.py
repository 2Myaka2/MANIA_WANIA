import json
from pathlib import Path

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "residue_library_tiny.json"
EXPECTED_TOP_LEVEL_KEYS = (
    "format",
    "format_version",
    "topology_files",
    "stats",
    "residues",
    "patches",
)
EXPECTED_RESIDUE_KEYS = {
    "resname",
    "block_type",
    "category",
    "source_file",
    "atoms",
}
EXPECTED_ATOM_KEYS = {
    "name",
    "type",
    "charge",
}
EXPECTED_CATEGORIES = {
    "protein",
    "lipid",
    "glycan",
    "glycolipid",
}


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_tiny_residue_library_fixture_exists() -> None:
    assert FIXTURE_PATH.exists()


def test_tiny_residue_library_fixture_shape() -> None:
    fixture = load_fixture()

    assert tuple(fixture) == EXPECTED_TOP_LEVEL_KEYS
    assert fixture["format"] == "MANIA_residue_library"
    assert fixture["format_version"] == "0.1"


def test_tiny_residue_library_fixture_residues() -> None:
    fixture = load_fixture()
    residues = fixture["residues"]

    assert isinstance(residues, dict)
    assert len(residues) == 4
    assert set(residues) == {"ALA", "POPC", "NAG", "GLP1"}
    assert {residue["category"] for residue in residues.values()} == EXPECTED_CATEGORIES

    for resname, residue in residues.items():
        assert residue["resname"] == resname
        assert EXPECTED_RESIDUE_KEYS <= set(residue)
        assert isinstance(residue["atoms"], list)
        assert residue["atoms"]
        for atom in residue["atoms"]:
            assert EXPECTED_ATOM_KEYS <= set(atom)


def test_tiny_residue_library_fixture_patch() -> None:
    fixture = load_fixture()
    patches = fixture["patches"]

    assert isinstance(patches, dict)
    assert set(patches) == {"TINY_PATCH"}
    assert patches["TINY_PATCH"]["name"] == "TINY_PATCH"
