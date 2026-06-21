import json
from pathlib import Path

import pytest

import mania.preprocessing
from mania.preprocessing import (
    PreprocessingContactDefinition,
    PreprocessingContactDetectionOptions,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mania"
    / "preprocessing"
    / "trajectory_contacts.py"
)
CONTACTS_DOC_PATH = REPO_ROOT / "docs" / "preprocessing_contacts_mvp.md"
PREPROCESSING_DOC_PATH = (
    REPO_ROOT / "docs" / "preprocessing_before_trajectory_parsing.md"
)
ADR_PATH = (
    REPO_ROOT
    / "docs"
    / "adr"
    / "0001-optional-scientific-dependencies.md"
)
BOOLEAN_FIELDS = (
    "exclude_same_residue",
    "exclude_duplicate_pairs",
    "include_frame_index",
    "include_time_ps",
)


def test_public_exports_and_import_safety_without_mdanalysis() -> None:
    assert mania.preprocessing is not None
    assert PreprocessingContactDefinition is not None
    assert PreprocessingContactDetectionOptions is not None


def test_default_contact_definition_matches_mvp() -> None:
    definition = PreprocessingContactDefinition()

    assert definition.contact_level == "residue"
    assert definition.distance_definition == "minimum_selected_atom_distance"
    assert definition.frame_scope == "per_frame"
    assert definition.pair_scope == "distinct_residue_pair"
    assert definition.default_atom_filter == "heavy"
    assert definition.default_cutoff_distance == 4.5
    assert definition.distance_unit == "angstrom"


def test_contact_definition_to_dict_is_json_serializable() -> None:
    definition = PreprocessingContactDefinition()

    payload = definition.to_dict()

    assert payload == {
        "contact_level": "residue",
        "distance_definition": "minimum_selected_atom_distance",
        "frame_scope": "per_frame",
        "pair_scope": "distinct_residue_pair",
        "default_atom_filter": "heavy",
        "default_cutoff_distance": 4.5,
        "distance_unit": "angstrom",
    }
    assert json.loads(json.dumps(payload)) == payload


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("contact_level", "atom"),
        ("distance_definition", "center_of_mass_distance"),
        ("frame_scope", "per_condition"),
        ("pair_scope", "same_residue_pair"),
        ("default_atom_filter", "backbone"),
        ("default_cutoff_distance", 0),
        ("default_cutoff_distance", float("nan")),
        ("distance_unit", ""),
    ],
)
def test_contact_definition_rejects_invalid_values(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(ValueError):
        PreprocessingContactDefinition(**{field_name: invalid_value})


def test_default_contact_options_match_mvp() -> None:
    options = PreprocessingContactDetectionOptions()

    assert options.contact_level == "residue"
    assert options.atom_filter == "heavy"
    assert options.cutoff_distance == 4.5
    assert options.distance_unit == "angstrom"
    assert options.exclude_same_residue is True
    assert options.exclude_duplicate_pairs is True
    assert options.skip_resnames == ()
    assert options.include_frame_index is True
    assert options.include_time_ps is True


def test_contact_options_to_dict_is_json_serializable() -> None:
    options = PreprocessingContactDetectionOptions(skip_resnames=("HOH",))

    payload = options.to_dict()

    assert payload == {
        "cutoff_distance": 4.5,
        "distance_unit": "angstrom",
        "atom_filter": "heavy",
        "contact_level": "residue",
        "exclude_same_residue": True,
        "exclude_duplicate_pairs": True,
        "skip_resnames": ["HOH"],
        "include_frame_index": True,
        "include_time_ps": True,
    }
    assert isinstance(payload["skip_resnames"], list)
    assert json.loads(json.dumps(payload)) == payload


def test_skip_resnames_normalize_deterministically() -> None:
    options = PreprocessingContactDetectionOptions(
        skip_resnames=("HOH", " WAT ", "HOH", "NA")
    )

    assert options.skip_resnames == ("HOH", "WAT", "NA")


@pytest.mark.parametrize(
    "invalid_value",
    [0, -1.0, float("nan"), float("inf"), float("-inf"), True],
)
def test_invalid_cutoff_values_fail(invalid_value: object) -> None:
    with pytest.raises(ValueError):
        PreprocessingContactDetectionOptions(cutoff_distance=invalid_value)


@pytest.mark.parametrize("invalid_value", ["", "   ", 1])
def test_invalid_distance_unit_fails(invalid_value: object) -> None:
    with pytest.raises(ValueError):
        PreprocessingContactDetectionOptions(distance_unit=invalid_value)


def test_distance_unit_is_stripped() -> None:
    options = PreprocessingContactDetectionOptions(distance_unit=" angstrom ")

    assert options.distance_unit == "angstrom"


def test_unsupported_atom_filter_fails() -> None:
    with pytest.raises(ValueError):
        PreprocessingContactDetectionOptions(atom_filter="backbone")


def test_unsupported_contact_level_fails() -> None:
    with pytest.raises(ValueError):
        PreprocessingContactDetectionOptions(contact_level="atom")


@pytest.mark.parametrize("field_name", BOOLEAN_FIELDS)
@pytest.mark.parametrize("invalid_value", [0, 1, "true", None])
def test_non_bool_boolean_fields_fail(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(ValueError):
        PreprocessingContactDetectionOptions(
            **{field_name: invalid_value}
        )


@pytest.mark.parametrize(
    "skip_resnames",
    [("",), ("   ",), ("HOH", 1)],
)
def test_invalid_skip_resnames_fail(skip_resnames: tuple[object, ...]) -> None:
    with pytest.raises(ValueError):
        PreprocessingContactDetectionOptions(skip_resnames=skip_resnames)


def test_contacts_module_has_no_computation_or_runtime_loading() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "distance_array",
        "self_distance_array",
        "capped_distance",
        "radius_of_gyration",
        ".positions",
        ".trajectory",
        ".atoms",
        "load_single_condition_runtime",
        "load_manifest_condition_runtimes",
        "require_mdanalysis",
    ):
        assert forbidden_text not in source


def test_contacts_module_has_no_export_comparison_report_or_graph_output() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_text in (
        "contacts_perframe",
        "contact_edges",
        "write_",
        "validate_",
        "compare_",
        "report_bundle",
        "nodes.csv",
        "edges.csv",
        "graph.json",
    ):
        assert forbidden_text not in source


def test_contacts_module_has_no_forbidden_scientific_imports() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden_import in (
        "MDAnalysis",
        "numpy",
        "pandas",
        "networkx",
        "pyarrow",
        "scipy",
        "sklearn",
    ):
        assert forbidden_import not in source


def test_contacts_mvp_docs_define_contract_and_future_boundaries() -> None:
    text = CONTACTS_DOC_PATH.read_text(encoding="utf-8").lower()

    for phrase in (
        "residue-residue contact",
        "minimum distance",
        "selected atoms",
        "two distinct residues",
        "per trajectory frame",
        "heavy",
        "4.5",
        "angstrom",
        "skip_resnames",
        "no unit conversion",
        "no biological interpretation",
        "contract-only",
        "no contact computation",
        "no contact result dataclasses",
        "no `contacts_perframe.csv` writer",
        "no `contact_edges.csv` writer",
        "aggregate contacts table",
        "not backend graph edges.csv",
        "no backend graph `nodes.csv`",
        "no backend graph `edges.csv`",
        "no `graph.json`",
        "graph export belongs to a later stage",
    ):
        assert phrase in text


def test_stage_13_boundary_docs_preserve_optional_dependency_policy() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (PREPROCESSING_DOC_PATH, ADR_PATH)
    ).lower()

    for phrase in (
        "stage 12 rg mvp is complete",
        "stage 13 contacts",
        "definition and options contract",
        "no contacts computation",
        "no contacts export",
        "no graph export",
        "contacts-specific modules",
        "dependency-free",
        "mdanalysis remains optional",
        "already loaded runtimes",
        "default ci remains independent from real md data",
    ):
        assert phrase in text
