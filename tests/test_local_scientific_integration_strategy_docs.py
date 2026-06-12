from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = REPO_ROOT / "docs" / "local_scientific_integration_tests.md"
ADR_PATH = (
    REPO_ROOT
    / "docs"
    / "adr"
    / "0001-optional-scientific-dependencies.md"
)


def read_strategy() -> str:
    return STRATEGY_PATH.read_text(encoding="utf-8")


def test_local_scientific_integration_strategy_exists() -> None:
    assert STRATEGY_PATH.is_file()


def test_strategy_defines_test_categories() -> None:
    strategy_text = read_strategy()

    for category in (
        "Default unit/contract tests",
        "Documentation/config tests",
        "Local scientific integration tests",
    ):
        assert category in strategy_text


def test_strategy_proposes_future_markers() -> None:
    strategy_text = read_strategy()

    for marker in (
        "local_scientific",
        "requires_mdanalysis",
        "requires_real_md_data",
    ):
        assert marker in strategy_text


def test_strategy_documents_local_data_policy() -> None:
    strategy_text = read_strategy().lower()

    for term in (
        "real topology files must not be committed",
        "real trajectory files must not be committed",
        "data/reference",
        "local reference package",
    ):
        assert term in strategy_text


def test_strategy_documents_optional_dependency_policy() -> None:
    strategy_text = read_strategy()

    for term in (
        ".[md]",
        ".[science]",
        "optional extras",
        "Default/core tests must not require these extras",
    ):
        assert term in strategy_text


def test_strategy_documents_stage_9_3_non_goals() -> None:
    strategy_text = read_strategy()

    for term in (
        "does not",
        "import MDAnalysis",
        "trajectory loading",
        "Rg",
        "contacts",
        "modify CI",
        "register pytest markers",
    ):
        assert term in strategy_text


def test_adr_references_stage_9_3_strategy() -> None:
    adr_text = ADR_PATH.read_text(encoding="utf-8")

    assert "Stage 9.3" in adr_text
    assert "local_scientific_integration_tests.md" in adr_text


def test_strategy_does_not_claim_implementation() -> None:
    strategy_text = read_strategy().lower()

    for forbidden_phrase in (
        "local scientific integration tests are implemented",
        "tests/local_scientific is available",
        "markers are registered",
    ):
        assert forbidden_phrase not in strategy_text
