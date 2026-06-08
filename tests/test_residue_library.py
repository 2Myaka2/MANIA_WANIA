import csv
import json
from copy import deepcopy
from pathlib import Path

from mania.residue_library import (
    DEFAULT_SKIPPED_RESNAMES,
    EXPECTED_RESIDUE_LIBRARY_FORMAT,
    QC_STATUS_NOT_FOUND,
    QC_STATUS_OK,
    QC_STATUS_SKIP,
    SUPPORTED_RESIDUE_LIBRARY_FORMAT_VERSION,
    PatchEntry,
    ResidueAtom,
    ResidueEntry,
    ResidueLibrary,
    ResidueLibraryFormatError,
    ResidueLibraryQCError,
    ResidueLibraryValidationError,
    ResidueQCReport,
    ResidueQCRow,
    load_residue_library,
    run_residue_library_qc,
    write_residue_qc_report,
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


def rows_by_resname(report: ResidueQCReport) -> dict[str, ResidueQCRow]:
    return {row.resname: row for row in report.rows}


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


def test_residue_qc_returns_ok_rows_for_known_residues() -> None:
    library = load_residue_library(FIXTURE_PATH)
    report = run_residue_library_qc(
        {
            "normal": ("ALA", "POPC"),
            "tumor": ("ALA", "NAG", "GLP1"),
        },
        library,
    )
    rows = rows_by_resname(report)

    assert len(report.rows) == 4
    assert [row.resname for row in report.rows] == ["ALA", "GLP1", "NAG", "POPC"]
    assert all(row.status == QC_STATUS_OK for row in report.rows)
    assert report.status_counts()[QC_STATUS_OK] == 4
    assert not report.has_errors()
    assert report.unknown_resnames() == ()
    assert rows["ALA"].conditions == ("normal", "tumor")
    assert rows["ALA"].coverage == "full"
    assert rows["ALA"].block_type == "residue"
    assert rows["ALA"].source_file == "tiny_fixture_topology.rtf"


def test_residue_qc_skips_default_solvent_and_ion_residues() -> None:
    library = load_residue_library(FIXTURE_PATH)
    report = run_residue_library_qc(
        {
            "normal": ("ALA", "TIP3"),
            "tumor": ("SOD", "CLA"),
        },
        library,
    )
    rows = rows_by_resname(report)

    assert DEFAULT_SKIPPED_RESNAMES == frozenset({"CLA", "SOD", "TIP3"})
    assert rows["TIP3"].status == QC_STATUS_SKIP
    assert rows["SOD"].status == QC_STATUS_SKIP
    assert rows["CLA"].status == QC_STATUS_SKIP
    assert rows["TIP3"].coverage == "skipped"
    assert rows["TIP3"].block_type == ""
    assert rows["TIP3"].source_file == ""
    assert not report.has_errors()
    assert report.status_counts()[QC_STATUS_SKIP] == 3


def test_residue_qc_supports_custom_skip_set() -> None:
    library = load_residue_library(FIXTURE_PATH)
    report = run_residue_library_qc(
        {"normal": ("ALA", "WAT")},
        library,
        skip_resnames={"WAT"},
    )

    assert rows_by_resname(report)["WAT"].status == QC_STATUS_SKIP
    assert not report.has_errors()


def test_residue_qc_raises_on_unknown_residue_by_default() -> None:
    library = load_residue_library(FIXTURE_PATH)

    try:
        run_residue_library_qc({"normal": ("ALA", "UNKNOWN")}, library)
    except ResidueLibraryQCError:
        return
    raise AssertionError("Expected ResidueLibraryQCError")


def test_residue_qc_can_return_not_found_rows() -> None:
    library = load_residue_library(FIXTURE_PATH)
    report = run_residue_library_qc(
        {"normal": ("ALA", "UNKNOWN")},
        library,
        fail_on_error=False,
    )
    unknown = rows_by_resname(report)["UNKNOWN"]

    assert unknown.status == QC_STATUS_NOT_FOUND
    assert unknown.coverage == "missing"
    assert unknown.block_type == ""
    assert unknown.source_file == ""
    assert report.has_errors()
    assert report.unknown_resnames() == ("UNKNOWN",)
    assert report.status_counts()[QC_STATUS_NOT_FOUND] == 1


def test_residue_qc_normalizes_residue_names() -> None:
    library = load_residue_library(FIXTURE_PATH)
    report = run_residue_library_qc({"normal": (" ala ", "popc")}, library)

    assert tuple(row.resname for row in report.rows) == ("ALA", "POPC")
    assert all(row.status == QC_STATUS_OK for row in report.rows)


def test_write_residue_qc_report_writes_csv(tmp_path: Path) -> None:
    library = load_residue_library(FIXTURE_PATH)
    report = run_residue_library_qc(
        {
            "normal": ("ALA", "TIP3"),
            "tumor": ("ALA",),
        },
        library,
    )
    report_path = tmp_path / "residue_qc_report.csv"

    write_residue_qc_report(report, report_path)

    assert report_path.exists()
    with report_path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        assert reader.fieldnames == [
            "resname",
            "status",
            "coverage",
            "block_type",
            "source_file",
            "conditions",
        ]
        rows = {row["resname"]: row for row in reader}

    assert rows["ALA"]["conditions"] == "normal,tumor"
    assert rows["TIP3"]["conditions"] == "normal"


def test_residue_qc_uses_passed_library_object() -> None:
    custom_library = ResidueLibrary(
        format=EXPECTED_RESIDUE_LIBRARY_FORMAT,
        format_version=SUPPORTED_RESIDUE_LIBRARY_FORMAT_VERSION,
        topology_files=("custom.rtf",),
        stats={},
        residues={
            "USER1": ResidueEntry(
                resname="USER1",
                block_type="residue",
                category="custom",
                source_file="custom.rtf",
                atoms=(
                    ResidueAtom(
                        name="C1",
                        type="CT1",
                        charge=0.0,
                    ),
                ),
            )
        },
        patches={
            "CUSTOM_PATCH": PatchEntry(
                name="CUSTOM_PATCH",
                block_type="patch",
                category="patch",
                source_file="custom.rtf",
            )
        },
    )

    report = run_residue_library_qc({"normal": ("USER1",)}, custom_library)
    row = rows_by_resname(report)["USER1"]

    assert row.status == QC_STATUS_OK
    assert row.block_type == "residue"
    assert row.source_file == "custom.rtf"
