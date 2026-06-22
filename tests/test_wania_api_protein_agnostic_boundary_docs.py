from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "wania_api_protein_agnostic_boundary.md"


def doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def normalized_lower(text: str) -> str:
    return " ".join(text.lower().split())


def test_wania_api_protein_agnostic_boundary_doc_exists() -> None:
    assert DOC_PATH.is_file()


def test_doc_contains_protein_agnostic_boundary_language() -> None:
    text = normalized_lower(doc_text())

    assert "protein-agnostic" in text
    assert "napi2b" in text
    assert "sample" in text
    assert "not hardcode" in text or "not hardcoded" in text
    assert "stage 16" in text


def test_doc_contains_future_metadata_fields() -> None:
    text = doc_text()

    for phrase in (
        "protein_id",
        "protein_name",
        "run_name",
        "condition_names",
    ):
        assert phrase in text


def test_doc_links_wania_object_json_payload_contract() -> None:
    text = doc_text()

    for phrase in (
        "Stage 16.0",
        "docs/wania_object_json_payload_contract.md",
        "object JSON",
        "protein-agnostic",
        "graph/graph.json",
    ):
        assert phrase in text


def test_doc_distinguishes_conditions_from_protein_identity() -> None:
    text = normalized_lower(doc_text())

    for phrase in (
        "conditions are not protein identity",
        "conditions are states/groups within a protein run",
        "normal",
        "tumor",
        "wild_type",
        "mutant",
    ):
        assert phrase in text


def test_doc_states_one_package_or_job_equals_one_protein_run() -> None:
    text = normalized_lower(doc_text())

    for phrase in (
        "one uploaded package",
        "one job",
        "one protein run",
    ):
        assert phrase in text


def test_doc_marks_multi_protein_comparison_as_future_scope() -> None:
    text = normalized_lower(doc_text())

    for phrase in (
        "multi-protein dashboard or catalog",
        "cross-protein comparison",
        "future scope",
        "residue/sequence/structure mapping or alignment",
    ):
        assert phrase in text
