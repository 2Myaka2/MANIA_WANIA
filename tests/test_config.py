from pathlib import Path

import pytest
from pydantic import ValidationError

from mania.config import MANIAConfig, load_config

EXAMPLE_CONFIG = Path("configs/mania.example.yaml")


def test_example_yaml_loads_successfully() -> None:
    config = load_config(EXAMPLE_CONFIG)

    assert config.project.name == "NaPi2b_NORM_TUMOR"
    assert len(config.systems) == 2
    assert config.runtime.run_mode == "full"
    assert config.features.energy_rerun is False


def test_load_config_accepts_path() -> None:
    config = load_config(Path(EXAMPLE_CONFIG))

    assert isinstance(config, MANIAConfig)


def test_invalid_run_mode_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        MANIAConfig.model_validate(
            {
                "project": {"name": "example", "run_id": "run_001"},
                "systems": {
                    "normal": {
                        "topology": "data/normal/system.tpr",
                        "trajectory": "data/normal/traj.xtc",
                        "condition": "normal",
                        "label": 0,
                    }
                },
                "runtime": {
                    "output_dir": "mania_output",
                    "cache_dir": "mania_output/cache",
                    "temp_dir": "mania_output/tmp",
                    "run_mode": "preprocess",
                },
            }
        )


def test_single_condition_config_is_valid() -> None:
    config = MANIAConfig.model_validate(
        {
            "project": {"name": "single_condition", "run_id": "run_001"},
            "systems": {
                "normal": {
                    "topology": "data/normal/system.tpr",
                    "trajectory": "data/normal/traj.xtc",
                    "condition": "normal",
                    "label": 0,
                }
            },
            "runtime": {
                "output_dir": "mania_output",
                "cache_dir": "mania_output/cache",
                "temp_dir": "mania_output/tmp",
                "run_mode": "analysis",
            },
        }
    )

    assert len(config.systems) == 1
    assert config.features.rg is True
    assert config.features.energy_rerun is False
    assert config.features.energy_groups == []
    assert config.features.esm2 is False


@pytest.mark.parametrize(
    "config_data",
    [
        {
            "systems": {
                "normal": {
                    "topology": "data/normal/system.tpr",
                    "trajectory": "data/normal/traj.xtc",
                    "condition": "normal",
                    "label": 0,
                }
            },
            "runtime": {
                "output_dir": "mania_output",
                "cache_dir": "mania_output/cache",
                "temp_dir": "mania_output/tmp",
            },
        },
        {
            "project": {"name": "example", "run_id": "run_001"},
            "runtime": {
                "output_dir": "mania_output",
                "cache_dir": "mania_output/cache",
                "temp_dir": "mania_output/tmp",
            },
        },
    ],
)
def test_missing_required_project_or_systems_block_raises_error(
    config_data: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        MANIAConfig.model_validate(config_data)
