import json
from pathlib import Path

import pytest

from mania.preprocessing import (
    PreprocessingInputManifest,
    load_preprocessing_input_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "examples" / "preprocessing"
MINIMAL_MANIFEST_PATH = EXAMPLES_DIR / "minimal_manifest.yaml"
FULL_MANIFEST_PATH = EXAMPLES_DIR / "full_manifest.yaml"
EXAMPLE_PATHS = (MINIMAL_MANIFEST_PATH, FULL_MANIFEST_PATH)


def test_minimal_yaml_example_loads() -> None:
    manifest = load_preprocessing_input_manifest(MINIMAL_MANIFEST_PATH)

    assert isinstance(manifest, PreprocessingInputManifest)
    assert manifest.condition_names() == ("normal",)
    assert manifest.frame_time_ps is None
    assert manifest.residue_library.library_path is None
    assert manifest.residue_library.custom_residues_path is None
    assert manifest.conditions[0].topology_path == Path(
        "data/example/normal/topology.tpr"
    )
    assert manifest.conditions[0].trajectory_paths == (
        Path("data/example/normal/trajectory.xtc"),
    )


def test_full_yaml_example_loads() -> None:
    manifest = load_preprocessing_input_manifest(FULL_MANIFEST_PATH)

    assert isinstance(manifest, PreprocessingInputManifest)
    assert manifest.condition_names() == ("normal", "tumor")
    assert manifest.frame_time_ps == 100.0
    assert manifest.residue_library.library_path == Path(
        "residue_library/mania_residue_library.json"
    )
    assert manifest.residue_library.custom_residues_path == Path(
        "residue_library/custom_residues.json"
    )
    assert manifest.residue_library.skip_resnames == ("CLA", "SOD", "TIP3")
    assert manifest.residue_library.allow_user_overrides is False
    assert manifest.conditions[0].metadata == {
        "replicate": "rep1",
        "source": "placeholder-example",
    }
    assert manifest.conditions[1].metadata == {
        "replicate": "rep1",
        "source": "placeholder-example",
    }
    assert manifest.conditions[0].reference_structure_path == Path(
        "data/example/normal/reference.pdb"
    )


@pytest.mark.parametrize("manifest_path", EXAMPLE_PATHS)
def test_examples_are_json_serializable(manifest_path: Path) -> None:
    manifest = load_preprocessing_input_manifest(manifest_path)

    json.dumps(manifest.to_dict())


def test_examples_use_canonical_residue_library_field_name() -> None:
    minimal_text = MINIMAL_MANIFEST_PATH.read_text(encoding="utf-8")
    full_text = FULL_MANIFEST_PATH.read_text(encoding="utf-8")

    for manifest_text in (minimal_text, full_text):
        assert "user_overlay_path" not in manifest_text
        assert "user_residue_library_path" not in manifest_text
    assert "custom_residues_path" in full_text


@pytest.mark.parametrize("manifest_path", EXAMPLE_PATHS)
def test_examples_do_not_include_premature_preprocessing_fields(
    manifest_path: Path,
) -> None:
    manifest_text = manifest_path.read_text(encoding="utf-8")

    for forbidden_text in (
        "contact_cutoff_A",
        "rg",
        "contacts",
        "MDAnalysis",
        "GROMACS",
    ):
        assert forbidden_text not in manifest_text


@pytest.mark.parametrize("manifest_path", EXAMPLE_PATHS)
def test_examples_do_not_point_to_reference_data(manifest_path: Path) -> None:
    manifest_text = manifest_path.read_text(encoding="utf-8")

    assert "data/reference" not in manifest_text
