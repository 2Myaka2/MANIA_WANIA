from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "wania_mvp_contract_v0_1.md"
REFERENCE_PATHS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "wania_object_json_payload_contract.md",
    REPO_ROOT / "docs" / "notebook_parity_audit_v1_3.md",
)


def normalized(text: str) -> str:
    return " ".join(text.split())


def doc_text() -> str:
    return normalized(DOC_PATH.read_text(encoding="utf-8"))


def test_wania_mvp_contract_v0_1_doc_exists() -> None:
    assert DOC_PATH.is_file()


def test_wania_mvp_contract_records_required_profile_concepts() -> None:
    text = doc_text()

    for phrase in (
        "WANIA MVP",
        "stable frontend-facing subset",
        "required",
        "optional",
        "backend-only",
        "future",
        "schema_version",
        "run",
        "capabilities",
        "graph.nodes",
        "graph.edges",
        "x/y/z",
        "x_ca/y_ca/z_ca",
        "edge_type",
        "interaction.primary_type",
        "artifacts",
        "diagnostics",
    ):
        assert phrase in text


def test_wania_mvp_contract_keeps_science_optional_or_backend_only() -> None:
    text = doc_text()

    for phrase in (
        "backbone",
        "aromatic_pi",
        "cation_pi",
        "analysis metrics",
        "communities",
        "temporal RIN",
        "InteractionAccumulator",
        "atom cache",
        "progressive enhancement",
        "rich illustrative payload",
        "not the minimal required MVP payload",
    ):
        assert phrase in text


def test_wania_mvp_contract_records_stage_boundaries_and_roadmap() -> None:
    text = doc_text()

    for phrase in (
        "not schema redesign",
        "not a FastAPI",
        "not a FastAPI/upload/job API contract",
        "not upload/job API",
        "Stage 17.2",
        "minimal valid payload fixture",
        "Stage 17.3",
        (
            "a true capability does not make its corresponding optional "
            "block required"
        ),
    ):
        assert phrase in text


def test_wania_mvp_contract_is_linked_from_required_docs() -> None:
    for path in REFERENCE_PATHS:
        assert "wania_mvp_contract_v0_1.md" in path.read_text(encoding="utf-8")
