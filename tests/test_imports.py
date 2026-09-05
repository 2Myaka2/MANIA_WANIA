import tomllib
from importlib.metadata import version
from pathlib import Path

import mania


def test_import_mania() -> None:
    assert mania is not None


def test_version_exists() -> None:
    assert isinstance(mania.__version__, str)
    assert mania.__version__
    assert mania.__version__ == version("mania-wania")


def test_package_version_uses_single_source() -> None:
    project_root = Path(__file__).resolve().parents[1]
    with (project_root / "pyproject.toml").open("rb") as stream:
        metadata = tomllib.load(stream)

    assert "version" not in metadata["project"]
    assert "version" in metadata["project"]["dynamic"]
    assert metadata["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "mania._version.__version__"
    }
