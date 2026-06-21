from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "preprocessing_graph_workflow_contract.md"


def doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def normalized(text: str) -> str:
    return " ".join(text.split())


def test_workflow_contract_doc_mentions_protein_run_future_api_scope() -> None:
    text = normalized(doc_text())

    for phrase in (
        "generic preprocessing manifests",
        "should not assume NaPi2b",
        "generic protein run metadata",
        "future API scope",
        "condition_names",
        "Conditions are not protein identity",
    ):
        assert phrase in text


def test_workflow_contract_doc_mentions_stage_15_not_napi2b_specific() -> None:
    text = normalized(doc_text())

    for phrase in (
        "Stage 15 backend workflow",
        "NaPi2b is only the current local sample/test dataset",
        "run/output-root based",
        "not hardcoded to a protein",
    ):
        assert phrase in text
