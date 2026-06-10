import csv
import json
from pathlib import Path

import pytest

from mania.analysis.graph_diagnostics import (
    ConditionGraphDiagnostics,
    GraphDiagnosticsError,
    MultiConditionGraphDiagnostics,
    run_condition_graph_diagnostics,
    run_multi_condition_graph_diagnostics,
    write_condition_graph_diagnostics,
    write_condition_graph_diagnostics_bundle,
    write_multi_condition_graph_diagnostics,
    write_multi_condition_graph_diagnostics_bundle,
)
from mania.constants import EDGE_COLUMNS, NODE_COLUMNS

FIXTURE_ROOT = Path("tests/fixtures/expected_contract_subset_tiny")


def write_csv(
    path: Path,
    fieldnames: tuple[str, ...],
    rows: list[dict[str, str]],
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def node_row(
    resid: str,
    *,
    condition: str = "normal",
    degree: str = "1",
    strength: str = "0.5",
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    row = {column: "" for column in NODE_COLUMNS}
    row.update(
        {
            "resid": resid,
            "resname": "ALA",
            "region": "TM1",
            "condition": condition,
            "degree": degree,
            "strength": strength,
        }
    )
    if extra is not None:
        row.update(extra)
    return row


def edge_row(
    source: str,
    target: str,
    *,
    edge_type: str = "contact",
    condition: str = "normal",
    contact_freq: str = "0.5",
    mean_dist_a: str = "7.25",
) -> dict[str, str]:
    row = {column: "" for column in EDGE_COLUMNS}
    row.update(
        {
            "resid_i": source,
            "resid_j": target,
            "edge_type": edge_type,
            "condition": condition,
            "contact_freq": contact_freq,
            "mean_dist_A": mean_dist_a,
        }
    )
    return row


def write_condition_dir(
    tmp_path: Path,
    *,
    condition: str = "normal",
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]],
    node_columns: tuple[str, ...] = NODE_COLUMNS,
) -> Path:
    condition_dir = tmp_path / condition
    condition_dir.mkdir()
    write_csv(condition_dir / "nodes.csv", node_columns, nodes)
    write_csv(condition_dir / "edges.csv", EDGE_COLUMNS, edges)
    return condition_dir


def test_normal_fixture_diagnostics_document_strength_mismatch() -> None:
    diagnostics = run_condition_graph_diagnostics(
        FIXTURE_ROOT / "normal",
        condition="normal",
    )

    assert isinstance(diagnostics, ConditionGraphDiagnostics)
    assert diagnostics.condition == "normal"
    assert diagnostics.graph.n_nodes == 2
    assert diagnostics.graph.n_edges == 1
    assert diagnostics.qc_report.passed_basic_qc is True
    assert diagnostics.topology_metrics.condition == "normal"
    assert diagnostics.topology_consistency.condition == "normal"
    assert diagnostics.passed_basic_qc is True
    assert diagnostics.passed_topology_consistency is False
    assert diagnostics.passed is False


def test_tumor_fixture_diagnostics_document_strength_mismatch() -> None:
    diagnostics = run_condition_graph_diagnostics(
        FIXTURE_ROOT / "tumor",
        condition="tumor",
    )

    assert diagnostics.condition == "tumor"
    assert diagnostics.qc_report.passed_basic_qc is True
    assert diagnostics.passed_basic_qc is True
    assert diagnostics.passed_topology_consistency is False
    assert diagnostics.passed is False


def test_synthetic_matching_graph_passes_diagnostics(tmp_path: Path) -> None:
    condition_dir = write_condition_dir(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )

    diagnostics = run_condition_graph_diagnostics(
        condition_dir,
        condition="normal",
    )

    assert diagnostics.passed_basic_qc is True
    assert diagnostics.passed_topology_consistency is True
    assert diagnostics.passed is True


def test_isolated_node_fails_basic_qc_without_raising(tmp_path: Path) -> None:
    condition_dir = write_condition_dir(
        tmp_path,
        nodes=[
            node_row("1"),
            node_row("2"),
            node_row("3", degree="0", strength="0.0"),
        ],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )

    diagnostics = run_condition_graph_diagnostics(
        condition_dir,
        condition="normal",
    )

    assert diagnostics.passed_basic_qc is False
    assert diagnostics.passed is False


def test_degree_mismatch_fails_consistency_without_raising(
    tmp_path: Path,
) -> None:
    condition_dir = write_condition_dir(
        tmp_path,
        nodes=[node_row("1", degree="0"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )

    diagnostics = run_condition_graph_diagnostics(
        condition_dir,
        condition="normal",
    )

    assert diagnostics.passed_topology_consistency is False
    assert diagnostics.passed is False
    assert "degree" in {
        mismatch.metric for mismatch in diagnostics.topology_consistency.mismatches
    }


def test_missing_condition_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(GraphDiagnosticsError, match="Missing condition directory"):
        run_condition_graph_diagnostics(
            tmp_path / "missing",
            condition="normal",
        )


def test_condition_path_that_is_not_directory_raises(tmp_path: Path) -> None:
    path = tmp_path / "normal"
    path.write_text("not a directory", encoding="utf-8")

    with pytest.raises(GraphDiagnosticsError, match="not a directory"):
        run_condition_graph_diagnostics(path, condition="normal")


@pytest.mark.parametrize("condition", ("", " "))
def test_empty_condition_name_raises(tmp_path: Path, condition: str) -> None:
    condition_dir = tmp_path / "condition"
    condition_dir.mkdir()

    with pytest.raises(GraphDiagnosticsError, match="Condition must be non-empty"):
        run_condition_graph_diagnostics(condition_dir, condition=condition)


def test_graph_loading_error_is_translated(tmp_path: Path) -> None:
    condition_dir = tmp_path / "normal"
    condition_dir.mkdir()

    with pytest.raises(GraphDiagnosticsError, match="Could not load contract graph"):
        run_condition_graph_diagnostics(condition_dir, condition="normal")


def test_invalid_edge_weight_is_translated(tmp_path: Path) -> None:
    condition_dir = write_condition_dir(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="abc")],
    )

    with pytest.raises(
        GraphDiagnosticsError,
        match="Could not compute graph topology metrics",
    ):
        run_condition_graph_diagnostics(condition_dir, condition="normal")


def test_invalid_tolerance_is_translated(tmp_path: Path) -> None:
    condition_dir = write_condition_dir(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )

    with pytest.raises(
        GraphDiagnosticsError,
        match="Could not check graph topology consistency",
    ):
        run_condition_graph_diagnostics(
            condition_dir,
            condition="normal",
            abs_tol=-1,
        )


def test_custom_weight_column_works(tmp_path: Path) -> None:
    condition_dir = write_condition_dir(
        tmp_path,
        nodes=[node_row("1", strength="7.25"), node_row("2", strength="7.25")],
        edges=[edge_row("1", "2", contact_freq="0.5", mean_dist_a="7.25")],
    )

    diagnostics = run_condition_graph_diagnostics(
        condition_dir,
        condition="normal",
        weight_column="mean_dist_A",
    )

    assert diagnostics.passed_topology_consistency is True
    assert diagnostics.passed is True


def test_custom_node_metric_columns_work(tmp_path: Path) -> None:
    node_columns = (*NODE_COLUMNS, "exported_degree", "exported_strength")
    condition_dir = write_condition_dir(
        tmp_path,
        node_columns=node_columns,
        nodes=[
            node_row(
                "1",
                degree="99",
                strength="99",
                extra={"exported_degree": "1", "exported_strength": "0.5"},
            ),
            node_row(
                "2",
                degree="99",
                strength="99",
                extra={"exported_degree": "1", "exported_strength": "0.5"},
            ),
        ],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )

    diagnostics = run_condition_graph_diagnostics(
        condition_dir,
        condition="normal",
        degree_column="exported_degree",
        strength_column="exported_strength",
    )

    assert diagnostics.passed_topology_consistency is True
    assert diagnostics.passed is True


def test_to_dict_is_json_serializable(tmp_path: Path) -> None:
    condition_dir = write_condition_dir(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )
    diagnostics = run_condition_graph_diagnostics(
        condition_dir,
        condition="normal",
    )

    payload = diagnostics.to_dict()

    assert {
        "condition",
        "n_nodes",
        "n_edges",
        "passed",
        "passed_basic_qc",
        "passed_topology_consistency",
        "qc_report",
        "topology_metrics",
        "topology_consistency",
    }.issubset(payload)
    assert json.loads(json.dumps(payload))["condition"] == "normal"


def test_write_condition_graph_diagnostics_creates_json_file(
    tmp_path: Path,
) -> None:
    condition_dir = write_condition_dir(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )
    diagnostics = run_condition_graph_diagnostics(
        condition_dir,
        condition="normal",
    )

    path = write_condition_graph_diagnostics(
        diagnostics,
        tmp_path / "diagnostics",
    )

    assert path == tmp_path / "diagnostics" / "graph_diagnostics.json"
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["condition"] == diagnostics.condition
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_write_condition_graph_diagnostics_bundle_creates_json_files(
    tmp_path: Path,
) -> None:
    condition_dir = write_condition_dir(
        tmp_path,
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="0.5")],
    )
    diagnostics = run_condition_graph_diagnostics(
        condition_dir,
        condition="normal",
    )

    paths = write_condition_graph_diagnostics_bundle(
        diagnostics,
        tmp_path / "bundle",
    )

    assert tuple(path.name for path in paths) == (
        "graph_diagnostics.json",
        "graph_qc.json",
        "graph_topology_metrics.json",
        "graph_topology_consistency.json",
    )
    assert all(path.exists() for path in paths)
    for path in paths:
        json.loads(path.read_text(encoding="utf-8"))


def test_multi_condition_fixture_diagnostics_document_strength_mismatches() -> None:
    diagnostics = run_multi_condition_graph_diagnostics(
        FIXTURE_ROOT,
        conditions=("normal", "tumor"),
    )

    assert isinstance(diagnostics, MultiConditionGraphDiagnostics)
    assert diagnostics.conditions == ("normal", "tumor")
    assert set(diagnostics.condition_diagnostics) == {"normal", "tumor"}
    assert diagnostics.passed is False
    assert diagnostics.failed_conditions == ("normal", "tumor")
    assert diagnostics.passed_conditions == ()


def test_multi_condition_order_is_preserved() -> None:
    diagnostics = run_multi_condition_graph_diagnostics(
        FIXTURE_ROOT,
        conditions=("tumor", "normal"),
    )

    assert diagnostics.conditions == ("tumor", "normal")
    assert diagnostics.failed_conditions == ("tumor", "normal")


def test_multi_condition_whitespace_is_stripped() -> None:
    diagnostics = run_multi_condition_graph_diagnostics(
        FIXTURE_ROOT,
        conditions=(" normal ", " tumor "),
    )

    assert diagnostics.conditions == ("normal", "tumor")


@pytest.mark.parametrize("conditions", (("normal", ""), ("normal", " ")))
def test_multi_condition_empty_condition_fails(
    tmp_path: Path,
    conditions: tuple[str, str],
) -> None:
    with pytest.raises(GraphDiagnosticsError, match="Condition must be non-empty"):
        run_multi_condition_graph_diagnostics(tmp_path, conditions=conditions)


def test_multi_condition_duplicate_condition_fails() -> None:
    with pytest.raises(GraphDiagnosticsError, match="Duplicate condition"):
        run_multi_condition_graph_diagnostics(
            FIXTURE_ROOT,
            conditions=("normal", " normal "),
        )


def test_multi_condition_string_conditions_input_fails() -> None:
    with pytest.raises(GraphDiagnosticsError, match="iterable of names"):
        run_multi_condition_graph_diagnostics(FIXTURE_ROOT, conditions="normal")


def test_multi_condition_missing_output_root_fails(tmp_path: Path) -> None:
    with pytest.raises(GraphDiagnosticsError, match="Missing output root"):
        run_multi_condition_graph_diagnostics(
            tmp_path / "missing",
            conditions=("normal",),
        )


def test_multi_condition_output_root_file_fails(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    output_root.write_text("not a directory", encoding="utf-8")

    with pytest.raises(GraphDiagnosticsError, match="not a directory"):
        run_multi_condition_graph_diagnostics(
            output_root,
            conditions=("normal",),
        )


def test_multi_condition_missing_condition_directory_fails(tmp_path: Path) -> None:
    write_condition_dir(
        tmp_path,
        condition="normal",
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2")],
    )

    with pytest.raises(GraphDiagnosticsError, match="Missing condition directory"):
        run_multi_condition_graph_diagnostics(
            tmp_path,
            conditions=("normal", "missing"),
        )


def test_multi_condition_synthetic_matching_output_passes(tmp_path: Path) -> None:
    write_condition_dir(
        tmp_path,
        condition="normal",
        nodes=[
            node_row("1", condition="normal"),
            node_row("2", condition="normal"),
        ],
        edges=[edge_row("1", "2", condition="normal")],
    )
    write_condition_dir(
        tmp_path,
        condition="tumor",
        nodes=[
            node_row("1", condition="tumor"),
            node_row("2", condition="tumor"),
        ],
        edges=[edge_row("1", "2", condition="tumor")],
    )

    diagnostics = run_multi_condition_graph_diagnostics(
        tmp_path,
        conditions=("normal", "tumor"),
    )

    assert diagnostics.passed is True
    assert diagnostics.passed_conditions == ("normal", "tumor")
    assert diagnostics.failed_conditions == ()


def test_multi_condition_mixed_pass_fail_is_represented(tmp_path: Path) -> None:
    write_condition_dir(
        tmp_path,
        condition="normal",
        nodes=[
            node_row("1", condition="normal"),
            node_row("2", condition="normal"),
        ],
        edges=[edge_row("1", "2", condition="normal")],
    )
    write_condition_dir(
        tmp_path,
        condition="tumor",
        nodes=[
            node_row("1", condition="tumor", degree="0"),
            node_row("2", condition="tumor"),
        ],
        edges=[edge_row("1", "2", condition="tumor")],
    )

    diagnostics = run_multi_condition_graph_diagnostics(
        tmp_path,
        conditions=("normal", "tumor"),
    )

    assert diagnostics.passed is False
    assert diagnostics.passed_conditions == ("normal",)
    assert diagnostics.failed_conditions == ("tumor",)


def test_multi_condition_invalid_edge_weight_raises(tmp_path: Path) -> None:
    write_condition_dir(
        tmp_path,
        condition="normal",
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2", contact_freq="abc")],
    )

    with pytest.raises(GraphDiagnosticsError, match="topology metrics"):
        run_multi_condition_graph_diagnostics(tmp_path, conditions=("normal",))


def test_multi_condition_custom_weight_column_is_applied_to_all_conditions(
    tmp_path: Path,
) -> None:
    for condition in ("normal", "tumor"):
        write_condition_dir(
            tmp_path,
            condition=condition,
            nodes=[
                node_row("1", condition=condition, strength="7.25"),
                node_row("2", condition=condition, strength="7.25"),
            ],
            edges=[
                edge_row(
                    "1",
                    "2",
                    condition=condition,
                    contact_freq="0.5",
                    mean_dist_a="7.25",
                )
            ],
        )

    default_diagnostics = run_multi_condition_graph_diagnostics(
        tmp_path,
        conditions=("normal", "tumor"),
    )
    custom_diagnostics = run_multi_condition_graph_diagnostics(
        tmp_path,
        conditions=("normal", "tumor"),
        weight_column="mean_dist_A",
    )

    assert default_diagnostics.passed is False
    assert custom_diagnostics.passed is True


def test_multi_condition_custom_node_metric_columns_apply_to_all_conditions(
    tmp_path: Path,
) -> None:
    node_columns = (*NODE_COLUMNS, "exported_degree", "exported_strength")
    for condition in ("normal", "tumor"):
        write_condition_dir(
            tmp_path,
            condition=condition,
            node_columns=node_columns,
            nodes=[
                node_row(
                    "1",
                    condition=condition,
                    degree="99",
                    strength="99",
                    extra={"exported_degree": "1", "exported_strength": "0.5"},
                ),
                node_row(
                    "2",
                    condition=condition,
                    degree="99",
                    strength="99",
                    extra={"exported_degree": "1", "exported_strength": "0.5"},
                ),
            ],
            edges=[edge_row("1", "2", condition=condition)],
        )

    diagnostics = run_multi_condition_graph_diagnostics(
        tmp_path,
        conditions=("normal", "tumor"),
        degree_column="exported_degree",
        strength_column="exported_strength",
    )

    assert diagnostics.passed is True


def test_multi_condition_to_dict_is_json_serializable(tmp_path: Path) -> None:
    write_condition_dir(
        tmp_path,
        condition="normal",
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2")],
    )
    diagnostics = run_multi_condition_graph_diagnostics(
        tmp_path,
        conditions=("normal",),
    )

    payload = diagnostics.to_dict()

    assert {
        "conditions",
        "passed",
        "passed_conditions",
        "failed_conditions",
        "condition_diagnostics",
    }.issubset(payload)
    assert json.loads(json.dumps(payload))["conditions"] == ["normal"]


def test_write_multi_condition_graph_diagnostics_creates_json_file(
    tmp_path: Path,
) -> None:
    write_condition_dir(
        tmp_path,
        condition="normal",
        nodes=[node_row("1"), node_row("2")],
        edges=[edge_row("1", "2")],
    )
    diagnostics = run_multi_condition_graph_diagnostics(
        tmp_path,
        conditions=("normal",),
    )

    path = write_multi_condition_graph_diagnostics(
        diagnostics,
        tmp_path / "diagnostics",
    )

    assert path == (
        tmp_path / "diagnostics" / "multi_condition_graph_diagnostics.json"
    )
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["conditions"] == list(diagnostics.conditions)
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_write_multi_condition_graph_diagnostics_bundle_creates_json_files(
    tmp_path: Path,
) -> None:
    for condition in ("normal", "tumor"):
        write_condition_dir(
            tmp_path,
            condition=condition,
            nodes=[
                node_row("1", condition=condition),
                node_row("2", condition=condition),
            ],
            edges=[edge_row("1", "2", condition=condition)],
        )
    diagnostics = run_multi_condition_graph_diagnostics(
        tmp_path,
        conditions=("normal", "tumor"),
    )

    paths = write_multi_condition_graph_diagnostics_bundle(
        diagnostics,
        tmp_path / "bundle",
    )

    assert paths[0].name == "multi_condition_graph_diagnostics.json"
    assert (tmp_path / "bundle" / "normal").is_dir()
    assert (tmp_path / "bundle" / "tumor").is_dir()
    assert (
        tmp_path / "bundle" / "normal" / "graph_diagnostics.json"
    ) in paths
    assert (
        tmp_path / "bundle" / "tumor" / "graph_topology_consistency.json"
    ) in paths
    assert all(path.exists() for path in paths)
    for path in paths:
        json.loads(path.read_text(encoding="utf-8"))
