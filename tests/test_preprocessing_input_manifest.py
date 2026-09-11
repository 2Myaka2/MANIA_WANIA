import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from mania.preprocessing import (
    PreprocessingInputManifest,
    ResidueLibraryInputConfig,
    load_preprocessing_input_manifest,
)


def minimal_manifest_payload() -> dict[str, object]:
    return {
        "output_root": "tmp/mania_output",
        "conditions": [
            {
                "condition": "normal",
                "topology_path": "data/normal/topology.tpr",
                "trajectory_paths": ["data/normal/traj.xtc"],
            }
        ],
    }


def test_minimal_valid_manifest_works() -> None:
    manifest = PreprocessingInputManifest.model_validate(minimal_manifest_payload())

    assert manifest.output_root == Path("tmp/mania_output")
    assert manifest.conditions[0].topology_path == Path(
        "data/normal/topology.tpr"
    )
    assert manifest.conditions[0].trajectory_paths == (
        Path("data/normal/traj.xtc"),
    )
    assert manifest.condition_names() == ("normal",)
    assert manifest.residue_library == ResidueLibraryInputConfig()
    assert manifest.frame_time_ps is None
    assert manifest.conditions[0].dataset_spec is None
    assert manifest.dataset_specs() == ()


def test_full_valid_manifest_works() -> None:
    payload = minimal_manifest_payload()
    payload["frame_time_ps"] = 100.0
    payload["residue_library"] = {
        "library_path": "residue_library/mania_residue_library.json",
        "custom_residues_path": "residue_library/custom_residues.json",
        "skip_resnames": [" cla ", "SOD", "tip3"],
        "allow_user_overrides": True,
    }
    payload["conditions"] = [
        {
            "condition": " normal ",
            "topology_path": "data/normal/topology.tpr",
            "trajectory_paths": [
                "data/normal/traj-1.xtc",
                "data/normal/traj-2.xtc",
            ],
            "reference_structure_path": "data/normal/reference.pdb",
            "metadata": {"replicate": "rep1"},
        },
        {
            "condition": "Tumor",
            "topology_path": "data/tumor/topology.tpr",
            "trajectory_paths": ["data/tumor/traj.xtc"],
        },
    ]

    manifest = PreprocessingInputManifest.model_validate(payload)

    assert manifest.condition_names() == ("normal", "Tumor")
    assert manifest.frame_time_ps == 100.0
    assert manifest.residue_library.library_path == Path(
        "residue_library/mania_residue_library.json"
    )
    assert manifest.residue_library.custom_residues_path == Path(
        "residue_library/custom_residues.json"
    )
    assert manifest.residue_library.skip_resnames == ("CLA", "SOD", "TIP3")
    assert manifest.residue_library.allow_user_overrides is True
    assert manifest.conditions[0].reference_structure_path == Path(
        "data/normal/reference.pdb"
    )
    assert manifest.conditions[0].metadata == {"replicate": "rep1"}


def test_duplicate_condition_fails() -> None:
    payload = minimal_manifest_payload()
    payload["conditions"] = [
        {
            "condition": "normal",
            "topology_path": "normal.tpr",
            "trajectory_paths": ["normal.xtc"],
        },
        {
            "condition": " normal ",
            "topology_path": "duplicate.tpr",
            "trajectory_paths": ["duplicate.xtc"],
        },
    ]

    with pytest.raises(ValidationError):
        PreprocessingInputManifest.model_validate(payload)


@pytest.mark.parametrize("conditions", ("normal", []))
def test_conditions_require_non_empty_collection(conditions: object) -> None:
    payload = minimal_manifest_payload()
    payload["conditions"] = conditions

    with pytest.raises(ValidationError):
        PreprocessingInputManifest.model_validate(payload)


@pytest.mark.parametrize("condition", ("", "   "))
def test_empty_condition_fails(condition: str) -> None:
    payload = minimal_manifest_payload()
    conditions = payload["conditions"]
    assert isinstance(conditions, list)
    conditions[0]["condition"] = condition

    with pytest.raises(ValidationError):
        PreprocessingInputManifest.model_validate(payload)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("output_root", ""),
        ("output_root", " "),
        ("topology_path", ""),
        ("topology_path", " "),
        ("trajectory_path", ""),
        ("trajectory_path", " "),
        ("reference_structure_path", ""),
        ("reference_structure_path", " "),
        ("library_path", ""),
        ("library_path", " "),
        ("custom_residues_path", ""),
        ("custom_residues_path", " "),
    ),
)
def test_empty_path_strings_fail(field_name: str, value: str) -> None:
    payload = minimal_manifest_payload()
    conditions = payload["conditions"]
    assert isinstance(conditions, list)
    condition = conditions[0]

    if field_name == "output_root":
        payload["output_root"] = value
    elif field_name == "trajectory_path":
        condition["trajectory_paths"] = [value]
    elif field_name in {"library_path", "custom_residues_path"}:
        payload["residue_library"] = {field_name: value}
    else:
        condition[field_name] = value

    with pytest.raises(ValidationError):
        PreprocessingInputManifest.model_validate(payload)


def test_trajectory_paths_cannot_be_string() -> None:
    payload = minimal_manifest_payload()
    conditions = payload["conditions"]
    assert isinstance(conditions, list)
    conditions[0]["trajectory_paths"] = "traj.xtc"

    with pytest.raises(ValidationError):
        PreprocessingInputManifest.model_validate(payload)


def test_trajectory_paths_cannot_be_empty() -> None:
    payload = minimal_manifest_payload()
    conditions = payload["conditions"]
    assert isinstance(conditions, list)
    conditions[0]["trajectory_paths"] = []

    with pytest.raises(ValidationError):
        PreprocessingInputManifest.model_validate(payload)


@pytest.mark.parametrize(
    "frame_time_ps",
    (0, -1.0, float("nan"), float("inf")),
)
def test_invalid_frame_time_ps_fails(frame_time_ps: float) -> None:
    payload = minimal_manifest_payload()
    payload["frame_time_ps"] = frame_time_ps

    with pytest.raises(ValidationError):
        PreprocessingInputManifest.model_validate(payload)


def test_skip_resnames_normalization() -> None:
    config = ResidueLibraryInputConfig(
        skip_resnames=[" cla ", "CLA", "sod"],
    )

    assert config.skip_resnames == ("CLA", "SOD")


def test_skip_resnames_cannot_be_string() -> None:
    with pytest.raises(ValidationError):
        ResidueLibraryInputConfig(skip_resnames="CLA")


@pytest.mark.parametrize("resname", ("", "   "))
def test_skip_resnames_cannot_contain_empty_values(resname: str) -> None:
    with pytest.raises(ValidationError):
        ResidueLibraryInputConfig(skip_resnames=[resname])


def test_get_condition_works() -> None:
    manifest = PreprocessingInputManifest.model_validate(minimal_manifest_payload())

    assert manifest.get_condition("normal") is manifest.conditions[0]
    assert manifest.get_condition(" normal ") is manifest.conditions[0]
    with pytest.raises(KeyError):
        manifest.get_condition("NORMAL")
    with pytest.raises(KeyError):
        manifest.get_condition("")
    with pytest.raises(KeyError):
        manifest.get_condition("   ")


def test_to_dict_is_json_serializable() -> None:
    payload = minimal_manifest_payload()
    payload["residue_library"] = {
        "library_path": "library.json",
        "custom_residues_path": "custom.json",
        "skip_resnames": ["cla"],
    }
    manifest = PreprocessingInputManifest.model_validate(payload)

    serialized = manifest.to_dict()
    json.dumps(serialized)

    assert serialized["output_root"] == "tmp/mania_output"
    conditions = serialized["conditions"]
    assert isinstance(conditions, list)
    assert conditions[0]["topology_path"] == "data/normal/topology.tpr"
    assert conditions[0]["trajectory_paths"] == ["data/normal/traj.xtc"]
    assert "dataset_spec" not in conditions[0]
    assert conditions[0]["reference_structure_path"] is None
    assert conditions[0]["metadata"] == {}
    assert serialized["frame_time_ps"] is None
    residue_library = serialized["residue_library"]
    assert isinstance(residue_library, dict)
    assert residue_library["library_path"] == "library.json"
    assert residue_library["skip_resnames"] == ["CLA"]


def test_loads_json_manifest(tmp_path: Path) -> None:
    path = tmp_path / "preprocessing.json"
    path.write_text(json.dumps(minimal_manifest_payload()), encoding="utf-8")

    manifest = load_preprocessing_input_manifest(path)

    assert isinstance(manifest, PreprocessingInputManifest)
    assert manifest.condition_names() == ("normal",)


@pytest.mark.parametrize("suffix", (".yaml", ".yml"))
def test_loads_yaml_manifest(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"preprocessing{suffix}"
    path.write_text(
        yaml.safe_dump(minimal_manifest_payload()),
        encoding="utf-8",
    )

    manifest = load_preprocessing_input_manifest(path)

    assert isinstance(manifest, PreprocessingInputManifest)
    assert manifest.condition_names() == ("normal",)


def test_loader_missing_manifest_fails(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_preprocessing_input_manifest(tmp_path / "missing.json")


def test_loader_directory_path_fails(tmp_path: Path) -> None:
    with pytest.raises(IsADirectoryError):
        load_preprocessing_input_manifest(tmp_path)


def test_loader_unsupported_suffix_fails(tmp_path: Path) -> None:
    path = tmp_path / "preprocessing.txt"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError):
        load_preprocessing_input_manifest(path)


def test_loader_invalid_json_fails(tmp_path: Path) -> None:
    path = tmp_path / "preprocessing.json"
    path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(ValueError):
        load_preprocessing_input_manifest(path)


def test_loader_invalid_yaml_fails(tmp_path: Path) -> None:
    path = tmp_path / "preprocessing.yaml"
    path.write_text("conditions: [", encoding="utf-8")

    with pytest.raises(ValueError):
        load_preprocessing_input_manifest(path)


@pytest.mark.parametrize("payload", ([], "manifest", 1, True, None))
def test_loader_non_object_payload_fails(tmp_path: Path, payload: object) -> None:
    path = tmp_path / "preprocessing.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError):
        load_preprocessing_input_manifest(path)


def test_declared_scientific_input_paths_are_not_checked(tmp_path: Path) -> None:
    manifest = PreprocessingInputManifest(
        output_root=tmp_path / "missing-output",
        conditions=[
            {
                "condition": "normal",
                "topology_path": tmp_path / "missing-topology.tpr",
                "trajectory_paths": [tmp_path / "missing-trajectory.xtc"],
                "reference_structure_path": tmp_path / "missing-reference.pdb",
            }
        ],
        residue_library={
            "library_path": tmp_path / "missing-library.json",
            "custom_residues_path": tmp_path / "missing-custom-residues.json",
        },
    )

    assert manifest.condition_names() == ("normal",)


def test_custom_residue_library_naming_is_canonical() -> None:
    manifest = PreprocessingInputManifest.model_validate(minimal_manifest_payload())
    residue_library = manifest.to_dict()["residue_library"]

    assert isinstance(residue_library, dict)
    assert "custom_residues_path" in residue_library
    assert "user_overlay_path" not in residue_library
    assert "user_residue_library_path" not in residue_library
@pytest.mark.parametrize("value", ["", "  ", 1, True, None, b"replica"])
def test_dataset_reference_requires_actual_nonempty_strings(value):
    from mania.preprocessing.input_manifest import DatasetTrajectoryReference

    with pytest.raises(ValueError):
        DatasetTrajectoryReference(
            dataset_id=value, system_id="S", trajectory_id="T", replica_id="R"
        )


def test_dataset_reference_normalization_and_frozen_extra_boundary():
    from mania.preprocessing.input_manifest import DatasetTrajectoryReference

    ref = DatasetTrajectoryReference(
        dataset_id=" D ", system_id=" S ", trajectory_id=" T ", replica_id=" R "
    )
    assert ref.replica_key == ("D", "S", "T", "R")
    with pytest.raises(ValueError):
        ref.dataset_id = "changed"
    with pytest.raises(ValueError):
        DatasetTrajectoryReference(**ref.model_dump(), condition="NORM")


def test_dataset_manifest_mixed_migration_and_legacy_serialization():
    from test_preprocessing_dataset_binding import manifest, reference, spec
    from test_preprocessing_dataset_spec_manifest import LEGACY_ENTRY

    value = spec(condition=None)
    legacy = manifest(LEGACY_ENTRY)
    assert "dataset_parameter_table_path" not in legacy.to_dict()
    assert "dataset_ref" not in legacy.to_dict()["conditions"][0]
    explicit_null = manifest(LEGACY_ENTRY | {"dataset_ref": None, "dataset_spec": None})
    assert explicit_null.to_dict() == legacy.to_dict()
    mixed = manifest(
        LEGACY_ENTRY,
        LEGACY_ENTRY | {"condition": "table", "dataset_ref": reference(value)},
        LEGACY_ENTRY
        | {"condition": "inline", "dataset_spec": spec(condition=None, replica_id="B")},
        table="does-not-need-to-exist.csv",
    )
    data = mixed.to_dict()
    assert data["dataset_parameter_table_path"] == "does-not-need-to-exist.csv"
    assert data["conditions"][0] == legacy.to_dict()["conditions"][0]
    assert data["conditions"][1]["dataset_ref"] == reference(value)
    assert "dataset_spec" not in data["conditions"][1]
    assert "dataset_ref" not in data["conditions"][2]


@pytest.mark.parametrize("inline", [False, True])
def test_dataset_reference_requires_table_even_with_inline(inline):
    from test_preprocessing_dataset_binding import manifest, reference, spec
    from test_preprocessing_dataset_spec_manifest import LEGACY_ENTRY

    entry = LEGACY_ENTRY | {"dataset_ref": reference(spec())}
    if inline:
        entry["dataset_spec"] = spec()
    with pytest.raises(ValueError, match="dataset_ref requires"):
        manifest(entry)


@pytest.mark.parametrize("table", ["", "  ", "parameters.csv"])
def test_dataset_table_rejects_empty_path_or_legacy_only(table):
    from test_preprocessing_dataset_binding import manifest
    from test_preprocessing_dataset_spec_manifest import LEGACY_ENTRY

    with pytest.raises(ValueError):
        manifest(LEGACY_ENTRY, table=table)


def test_dataset_reference_mismatch_and_duplicate_effective_keys():
    from test_preprocessing_dataset_binding import manifest, reference, spec
    from test_preprocessing_dataset_spec_manifest import LEGACY_ENTRY

    value = spec(condition=None)
    with pytest.raises(ValueError, match="replica_key must match"):
        manifest(
            LEGACY_ENTRY
            | {
                "dataset_spec": value,
                "dataset_ref": reference(spec(replica_id="B")),
            },
            table="parameters.csv",
        )
    for first in ({"dataset_spec": value}, {"dataset_ref": reference(value)}):
        with pytest.raises(ValueError, match="Duplicate Dataset replica_key"):
            manifest(
                LEGACY_ENTRY | first,
                LEGACY_ENTRY
                | {"condition": "different", "dataset_ref": reference(value)},
                table="parameters.csv",
            )


def test_partner_metadata_path_is_optional_execution_metadata():
    from mania.preprocessing.input_manifest import PreprocessingInputManifest

    payload = {
        "output_root": "out",
        "conditions": [
            {
                "condition": "route",
                "topology_path": "topology.tpr",
                "trajectory_paths": ["trajectory.xtc"],
            }
        ],
    }
    legacy = PreprocessingInputManifest.model_validate(payload)
    assert legacy.conditions[0].molecular_partner_metadata_path is None
    assert "molecular_partner_metadata_path" not in legacy.conditions[0].model_dump(
        mode="json"
    )
    assert "molecular_partner_metadata_path" not in legacy.to_dict()["conditions"][0]
    payload["conditions"][0]["molecular_partner_metadata_path"] = (
        "controls/partners.json"
    )
    manifest = PreprocessingInputManifest.model_validate(payload)
    assert (
        str(manifest.conditions[0].molecular_partner_metadata_path)
        == "controls/partners.json"
    )
    assert (
        manifest.to_dict()["conditions"][0]["molecular_partner_metadata_path"]
        == "controls/partners.json"
    )
    assert manifest.conditions[0].dataset_spec is None
    payload["conditions"][0]["molecular_partner_metadata_path"] = " "
    with pytest.raises(ValueError):
        PreprocessingInputManifest.model_validate(payload)


@pytest.mark.parametrize("annotations", [False, True])
def test_stage30_paths_are_optional_relative_dataset_controls(annotations):
    from test_preprocessing_dataset_binding import manifest, spec
    from test_preprocessing_dataset_spec_manifest import LEGACY_ENTRY

    legacy = manifest(LEGACY_ENTRY)
    for values in (
        legacy.to_dict()["conditions"][0],
        legacy.conditions[0].model_dump(mode="json"),
    ):
        assert "canonical_residue_mapping_path" not in values
        assert "biological_annotation_metadata_path" not in values
    entry = LEGACY_ENTRY | {
        "dataset_spec": spec(condition=None),
        "canonical_residue_mapping_path": "controls/mapping.json",
    }
    if annotations:
        entry["biological_annotation_metadata_path"] = "controls/biology.json"
    result = manifest(entry, LEGACY_ENTRY | {"condition": "legacy-other"})
    assert result.conditions[0].canonical_residue_mapping_path == Path(
        "controls/mapping.json"
    )
    assert (
        result.to_dict()["conditions"][0]["canonical_residue_mapping_path"]
        == "controls/mapping.json"
    )
    assert (
        result.conditions[0].biological_annotation_metadata_path is not None
    ) is annotations
    assert "canonical_residue_mapping_path" not in result.to_dict()["conditions"][1]
    assert result.conditions[0].dataset_spec.identity.condition is None


@pytest.mark.parametrize(
    "case",
    [
        "annotation_only",
        "legacy_mapping",
        "legacy_both",
        "empty_mapping",
        "empty_annotation",
    ],
)
def test_stage30_manifest_relationships(case):
    from test_preprocessing_dataset_binding import manifest, spec
    from test_preprocessing_dataset_spec_manifest import LEGACY_ENTRY

    entry = LEGACY_ENTRY.copy()
    if not case.startswith("legacy"):
        entry["dataset_spec"] = spec(condition=None)
    if case != "annotation_only":
        entry["canonical_residue_mapping_path"] = (
            "" if case == "empty_mapping" else "mapping.json"
        )
    if case != "legacy_mapping":
        entry["biological_annotation_metadata_path"] = (
            " " if case == "empty_annotation" else "biology.json"
        )
    with pytest.raises(ValueError):
        manifest(entry)
