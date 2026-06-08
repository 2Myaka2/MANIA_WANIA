import json
from copy import deepcopy
from pathlib import Path

from mania.residue_library import (
    EXPECTED_RESIDUE_LIBRARY_FORMAT,
    SUPPORTED_RESIDUE_LIBRARY_FORMAT_VERSION,
    ResidueAtom,
    ResidueLibrary,
    ResidueLibraryFormatError,
    ResidueLibraryValidationError,
    load_residue_library,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "residue_library_tiny.json"


def load_fixture_payload() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def assert_load_raises(
    expected_exception: type[Exception],
    path: Path,
) -> None:
    try:
        load_residue_library(path)
    except expected_exception:
        return
    raise AssertionError(f"Expected {expected_exception.__name__}")


def test_load_valid_tiny_fixture() -> None:
    library = load_residue_library(FIXTURE_PATH)

    assert isinstance(library, ResidueLibrary)
    assert library.format == EXPECTED_RESIDUE_LIBRARY_FORMAT
    assert library.format_version == SUPPORTED_RESIDUE_LIBRARY_FORMAT_VERSION
    assert len(library.residues) == 4
    assert len(library.patches) == 1
    assert library.topology_files == ("tiny_fixture_topology.rtf",)


def test_normalized_lookup() -> None:
    library = load_residue_library(FIXTURE_PATH)
    ala = library.get_residue("ALA")

    assert ala is not None
    assert library.get_residue(" ala ") == ala
    assert library.has_residue("popc")
    assert not library.has_residue("UNKNOWN")


def test_classification() -> None:
    library = load_residue_library(FIXTURE_PATH)

    assert library.classify_residue("ALA") == "protein"
    assert library.classify_residue("POPC") == "lipid"
    assert library.classify_residue("NAG") == "glycan"
    assert library.classify_residue("GLP1") == "glycolipid"
    assert library.classify_residue("UNKNOWN") is None


def test_atom_parsing() -> None:
    library = load_residue_library(FIXTURE_PATH)
    ala = library.get_residue("ALA")

    assert ala is not None
    assert ala.atoms
    atom = ala.atoms[0]
    assert isinstance(atom, ResidueAtom)
    assert atom.name
    assert atom.type
    assert isinstance(atom.charge, (float, int))


def test_invalid_format_raises_format_error(tmp_path: Path) -> None:
    payload = load_fixture_payload()
    payload["format"] = "WRONG"
    path = write_json(tmp_path / "wrong_format.json", payload)

    assert_load_raises(ResidueLibraryFormatError, path)


def test_unsupported_format_version_raises_format_error(tmp_path: Path) -> None:
    payload = load_fixture_payload()
    payload["format_version"] = "9.9"
    path = write_json(tmp_path / "wrong_version.json", payload)

    assert_load_raises(ResidueLibraryFormatError, path)


def test_missing_top_level_key_raises_validation_error(tmp_path: Path) -> None:
    payload = load_fixture_payload()
    del payload["residues"]
    path = write_json(tmp_path / "missing_residues.json", payload)

    assert_load_raises(ResidueLibraryValidationError, path)


def test_malformed_residue_entry_raises_validation_error(tmp_path: Path) -> None:
    payload = load_fixture_payload()
    residues = payload["residues"]
    assert isinstance(residues, dict)
    residue = deepcopy(residues["ALA"])
    assert isinstance(residue, dict)
    del residue["atoms"]
    residues["ALA"] = residue
    path = write_json(tmp_path / "malformed_residue.json", payload)

    assert_load_raises(ResidueLibraryValidationError, path)


def test_malformed_atom_entry_raises_validation_error(tmp_path: Path) -> None:
    payload = load_fixture_payload()
    residues = payload["residues"]
    assert isinstance(residues, dict)
    residue = deepcopy(residues["ALA"])
    assert isinstance(residue, dict)
    atoms = residue["atoms"]
    assert isinstance(atoms, list)
    atom = deepcopy(atoms[0])
    assert isinstance(atom, dict)
    del atom["charge"]
    atoms[0] = atom
    residues["ALA"] = residue
    path = write_json(tmp_path / "malformed_atom.json", payload)

    assert_load_raises(ResidueLibraryValidationError, path)


def test_malformed_patch_entry_raises_validation_error(tmp_path: Path) -> None:
    payload = load_fixture_payload()
    patches = payload["patches"]
    assert isinstance(patches, dict)
    patch = deepcopy(patches["TINY_PATCH"])
    assert isinstance(patch, dict)
    del patch["source_file"]
    patches["TINY_PATCH"] = patch
    path = write_json(tmp_path / "malformed_patch.json", payload)

    assert_load_raises(ResidueLibraryValidationError, path)
