from __future__ import annotations

import json
from pathlib import Path

import pytest

from mania.validation.manifest import (
    ManifestValidationError,
    load_manifest_json,
    validate_global_features,
)


def write_manifest(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def feature_block(
    *,
    rg_mean_A: object = 36.0,
    rg_std_A: object = 1.5,
    n_rg_frames: object = 12,
) -> dict[str, object]:
    return {
        "rg_mean_A": rg_mean_A,
        "rg_std_A": rg_std_A,
        "n_rg_frames": n_rg_frames,
    }


def test_validate_global_features_with_explicit_conditions(
    tmp_path: Path,
) -> None:
    path = write_manifest(
        tmp_path / "manifest.json",
        {"global_features": {"A": feature_block(), "B": feature_block()}},
    )

    result = validate_global_features(path, expected_conditions=("A", "B"))

    assert result.is_valid
    assert result.conditions == ("A", "B")
    assert result.feature_conditions == ("A", "B")


def test_validate_global_features_uses_manifest_conditions(tmp_path: Path) -> None:
    path = write_manifest(
        tmp_path / "manifest.json",
        {
            "conditions": ["A", "B"],
            "global_features": {"A": feature_block(), "B": feature_block()},
        },
    )

    result = validate_global_features(path)

    assert result.is_valid
    assert result.conditions == ("A", "B")


def test_validate_global_features_derives_conditions_from_features(
    tmp_path: Path,
) -> None:
    path = write_manifest(
        tmp_path / "manifest.json",
        {"global_features": {"A": feature_block(), "B": feature_block()}},
    )

    result = validate_global_features(path)

    assert result.is_valid
    assert result.conditions == ("A", "B")


def test_validate_global_features_requires_global_features(tmp_path: Path) -> None:
    path = write_manifest(tmp_path / "manifest.json", {"conditions": ["A"]})

    with pytest.raises(ManifestValidationError):
        validate_global_features(path)


def test_validate_global_features_requires_global_features_mapping(
    tmp_path: Path,
) -> None:
    path = write_manifest(tmp_path / "manifest.json", {"global_features": []})

    with pytest.raises(ManifestValidationError):
        validate_global_features(path)


def test_validate_global_features_rejects_missing_expected_condition(
    tmp_path: Path,
) -> None:
    path = write_manifest(
        tmp_path / "manifest.json",
        {"global_features": {"A": feature_block()}},
    )

    with pytest.raises(ManifestValidationError):
        validate_global_features(path, expected_conditions=("A", "B"))


def test_validate_global_features_rejects_scalar_expected_conditions(
    tmp_path: Path,
) -> None:
    path = write_manifest(
        tmp_path / "manifest.json",
        {"global_features": {"normal": feature_block()}},
    )

    with pytest.raises(ManifestValidationError):
        validate_global_features(path, expected_conditions="normal")


def test_validate_global_features_allows_extra_condition_by_default(
    tmp_path: Path,
) -> None:
    path = write_manifest(
        tmp_path / "manifest.json",
        {"global_features": {"A": feature_block(), "B": feature_block()}},
    )

    result = validate_global_features(path, expected_conditions=("A",))

    assert result.is_valid
    assert result.extra_conditions == ("B",)


def test_validate_global_features_rejects_extra_condition_when_disallowed(
    tmp_path: Path,
) -> None:
    path = write_manifest(
        tmp_path / "manifest.json",
        {"global_features": {"A": feature_block(), "B": feature_block()}},
    )

    with pytest.raises(ManifestValidationError):
        validate_global_features(
            path,
            expected_conditions=("A",),
            allow_extra_conditions=False,
        )


def test_validate_global_features_rejects_missing_feature_key(tmp_path: Path) -> None:
    path = write_manifest(
        tmp_path / "manifest.json",
        {"global_features": {"A": {"rg_mean_A": 36.0, "n_rg_frames": 12}}},
    )

    with pytest.raises(ManifestValidationError):
        validate_global_features(path)


def test_validate_global_features_requires_feature_object_mapping(
    tmp_path: Path,
) -> None:
    path = write_manifest(
        tmp_path / "manifest.json",
        {"global_features": {"A": []}},
    )

    with pytest.raises(ManifestValidationError):
        validate_global_features(path)


def test_validate_global_features_rejects_invalid_rg_mean_type(
    tmp_path: Path,
) -> None:
    path = write_manifest(
        tmp_path / "manifest.json",
        {"global_features": {"A": feature_block(rg_mean_A="36.0")}},
    )

    with pytest.raises(ManifestValidationError):
        validate_global_features(path)


def test_validate_global_features_rejects_negative_rg_mean(tmp_path: Path) -> None:
    path = write_manifest(
        tmp_path / "manifest.json",
        {"global_features": {"A": feature_block(rg_mean_A=-1.0)}},
    )

    with pytest.raises(ManifestValidationError):
        validate_global_features(path)


def test_validate_global_features_rejects_negative_rg_std(tmp_path: Path) -> None:
    path = write_manifest(
        tmp_path / "manifest.json",
        {"global_features": {"A": feature_block(rg_std_A=-1.0)}},
    )

    with pytest.raises(ManifestValidationError):
        validate_global_features(path)


def test_validate_global_features_rejects_non_positive_frame_count(
    tmp_path: Path,
) -> None:
    path = write_manifest(
        tmp_path / "manifest.json",
        {"global_features": {"A": feature_block(n_rg_frames=0)}},
    )

    with pytest.raises(ManifestValidationError):
        validate_global_features(path)


def test_load_manifest_json_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(ManifestValidationError):
        load_manifest_json(path)


def test_load_manifest_json_rejects_non_object_json(tmp_path: Path) -> None:
    path = write_manifest(tmp_path / "manifest.json", [])

    with pytest.raises(ManifestValidationError):
        load_manifest_json(path)


def test_validate_global_features_allows_extra_feature_keys(tmp_path: Path) -> None:
    features = feature_block()
    features["extra"] = "allowed"
    path = write_manifest(
        tmp_path / "manifest.json",
        {"global_features": {"A": features}},
    )

    result = validate_global_features(path)

    assert result.is_valid


def test_validate_global_features_allows_custom_required_keys(tmp_path: Path) -> None:
    path = write_manifest(
        tmp_path / "manifest.json",
        {"global_features": {"A": {"rg_mean_A": 36.0}}},
    )

    result = validate_global_features(path, required_feature_keys=("rg_mean_A",))

    assert result.is_valid
    assert result.required_feature_keys == ("rg_mean_A",)


def test_validate_global_features_rejects_scalar_required_feature_keys(
    tmp_path: Path,
) -> None:
    path = write_manifest(
        tmp_path / "manifest.json",
        {"global_features": {"A": feature_block()}},
    )

    with pytest.raises(ManifestValidationError):
        validate_global_features(path, required_feature_keys="rg_mean_A")


def test_validate_global_features_rejects_scalar_string_conditions(
    tmp_path: Path,
) -> None:
    path = write_manifest(
        tmp_path / "manifest.json",
        {"conditions": "A", "global_features": {"A": feature_block()}},
    )

    with pytest.raises(ManifestValidationError):
        validate_global_features(path)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("rg_mean_A", True),
        ("n_rg_frames", True),
    ],
)
def test_validate_global_features_rejects_known_bool_values(
    tmp_path: Path,
    key: str,
    value: bool,
) -> None:
    features = feature_block()
    features[key] = value
    path = write_manifest(
        tmp_path / "manifest.json",
        {"global_features": {"A": features}},
    )

    with pytest.raises(ManifestValidationError):
        validate_global_features(path)
