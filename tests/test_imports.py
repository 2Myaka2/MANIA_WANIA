import mania


def test_import_mania() -> None:
    assert mania is not None


def test_version_exists() -> None:
    assert isinstance(mania.__version__, str)
    assert mania.__version__
