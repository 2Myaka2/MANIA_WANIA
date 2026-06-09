import csv
import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from mania.adapters import (
    ConditionExportResult,
    MultiConditionExportResult,
    NotebookContractSubsetExportResult,
    NotebookExportAdapterError,
    export_centrality,
    export_communities,
    export_condition,
    export_conditions,
    export_edges,
    export_graph,
    export_nodes,
    export_notebook_contract_subset,
    export_rg_timeseries,
    export_run_meta,
)
from mania.constants import (
    CENTRALITY_COLUMNS,
    COMMUNITIES_COLUMNS,
    EDGE_COLUMNS,
    NODE_COLUMNS,
    RG_TIMESERIES_COLUMNS,
    SCHEMA_VERSION,
)
from mania.validation.artifacts import (
    validate_condition_column,
    validate_csv_artifact_schema,
)
from mania.validation.graph import validate_graph_json

FIXTURE_DIR = Path("tests/fixtures/notebook_export_v1_1_tiny")
RESIDUE_TABLE_COLUMNS = NODE_COLUMNS[:11]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def read_header(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        return next(csv.reader(csv_file))


def read_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as json_file:
        payload = json.load(json_file)
    assert isinstance(payload, dict)
    return payload


def write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def manifest_payload(
    *,
    rg_mean_A: object = 36.0,
    rg_std_A: object = 1.0,
    n_rg_frames: object = 2,
) -> dict[str, object]:
    return {
        "conditions": ["normal"],
        "global_features": {
            "normal": {
                "rg_mean_A": rg_mean_A,
                "rg_std_A": rg_std_A,
                "n_rg_frames": n_rg_frames,
            }
        },
    }


def write_csv(
    path: Path,
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def assert_conditions(rows: list[dict[str, str]], expected: str) -> None:
    assert [row["condition"] for row in rows] == [expected] * len(rows)


def residue_row(
    resid: str = "1",
    *,
    condition: str = "normal",
    resname: str = "ALA",
) -> tuple[str, ...]:
    return (
        resid,
        resname,
        "TM1",
        condition,
        "1.0",
        "2.0",
        "3.0",
        "-0.5",
        "0.8",
        "120.0",
        "H",
    )


def centrality_row(resid: str = "1", *, condition: str = "normal") -> tuple[str, ...]:
    return (resid, condition, "1", "0.7", "0.0", "0.5", "0.6", "0.55", "1")


def community_row(resid: str = "1", *, condition: str = "normal") -> tuple[str, ...]:
    return (resid, condition, "1", "2", "fixture_louvain")


def node_row(resid: str = "1", *, condition: str = "normal") -> tuple[str, ...]:
    return (
        resid,
        "ALA",
        "TM1",
        condition,
        "1.0",
        "2.0",
        "3.0",
        "-0.5",
        "0.8",
        "120.0",
        "H",
        "1",
        "0.7",
        "0.0",
        "0.5",
        "0.6",
        "0.55",
        "1",
        "1",
    )


DEFAULT_RESIDUE_ROWS = (residue_row(),)
DEFAULT_CENTRALITY_ROWS = (centrality_row(),)
DEFAULT_COMMUNITY_ROWS = (community_row(),)


def edge_row(
    resid_i: str = "1",
    resid_j: str = "2",
    *,
    edge_type: str = "contact",
    condition: str = "normal",
    contact_freq: str = "0.75",
) -> tuple[str, ...]:
    return (
        resid_i,
        resid_j,
        edge_type,
        condition,
        contact_freq,
        "4.2",
        "0.3",
        "2",
        "3.0",
        "4",
        "0.30",
        "0.40",
        "2",
        "1",
        "0",
        "1",
        "0.10",
    )


DEFAULT_EDGE_ROWS = (edge_row(),)


def write_residue_table(
    source_dir: Path,
    condition: str = "normal",
    rows: Sequence[Sequence[str]] = DEFAULT_RESIDUE_ROWS,
    header: Sequence[str] = RESIDUE_TABLE_COLUMNS,
) -> Path:
    return write_csv(source_dir / f"residue_table_{condition}.csv", header, rows)


def write_centrality_table(
    source_dir: Path,
    condition: str = "normal",
    rows: Sequence[Sequence[str]] = DEFAULT_CENTRALITY_ROWS,
    header: Sequence[str] = CENTRALITY_COLUMNS,
) -> Path:
    return write_csv(source_dir / f"centrality_{condition}.csv", header, rows)


def write_communities_table(
    source_dir: Path,
    condition: str = "normal",
    rows: Sequence[Sequence[str]] = DEFAULT_COMMUNITY_ROWS,
    header: Sequence[str] = COMMUNITIES_COLUMNS,
) -> Path:
    return write_csv(source_dir / f"communities_{condition}.csv", header, rows)


def write_edges_table(
    source_dir: Path,
    condition: str = "normal",
    rows: Sequence[Sequence[str]] = DEFAULT_EDGE_ROWS,
    header: Sequence[str] = EDGE_COLUMNS,
) -> Path:
    return write_csv(
        source_dir / f"protein_contact_edges_undirected_{condition}.csv",
        header,
        rows,
    )


def write_nodes_csv(
    path: Path,
    rows: Sequence[Sequence[str]],
    header: Sequence[str] = NODE_COLUMNS,
) -> Path:
    return write_csv(path, header, rows)


def write_edges_csv(
    path: Path,
    rows: Sequence[Sequence[str]],
    header: Sequence[str] = EDGE_COLUMNS,
) -> Path:
    return write_csv(path, header, rows)


def write_minimal_node_sources(
    source_dir: Path,
    *,
    residue_rows: Sequence[Sequence[str]] = DEFAULT_RESIDUE_ROWS,
    centrality_rows: Sequence[Sequence[str]] = DEFAULT_CENTRALITY_ROWS,
    community_rows: Sequence[Sequence[str]] = DEFAULT_COMMUNITY_ROWS,
) -> None:
    write_residue_table(source_dir, rows=residue_rows)
    write_centrality_table(source_dir, rows=centrality_rows)
    write_communities_table(source_dir, rows=community_rows)


def assert_export_nodes_fails(source_dir: Path, tmp_path: Path) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_nodes(
            source_dir=source_dir,
            output_dir=tmp_path / "out",
            condition="normal",
        )


def assert_export_edges_fails(source_dir: Path, tmp_path: Path) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_edges(
            source_dir=source_dir,
            output_dir=tmp_path / "out",
            condition="normal",
        )


def assert_export_graph_fails(output_dir: Path, condition: str = "normal") -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_graph(output_dir, condition)


def validate_condition_export_result(
    result: ConditionExportResult,
    condition: str,
) -> None:
    validate_csv_artifact_schema(result.rg_timeseries_path, "rg_timeseries.csv")
    validate_condition_column(result.rg_timeseries_path, condition)
    validate_csv_artifact_schema(result.centrality_path, "centrality.csv")
    validate_condition_column(result.centrality_path, condition)
    validate_csv_artifact_schema(result.communities_path, "communities.csv")
    validate_condition_column(result.communities_path, condition)
    validate_csv_artifact_schema(result.nodes_path, "nodes.csv")
    validate_condition_column(result.nodes_path, condition)
    validate_csv_artifact_schema(result.edges_path, "edges.csv")
    validate_condition_column(result.edges_path, condition)
    validate_graph_json(result.graph_path, expected_condition=condition)


def unsupported_artifact_paths(output_dir: Path) -> tuple[Path, ...]:
    unsupported_per_condition = (
        "temporal_rin.csv",
        "conformational_states.csv",
        "contacts_perframe.parquet",
    )
    condition_artifacts = tuple(
        output_dir / condition / name
        for condition in ("normal", "tumor")
        for name in unsupported_per_condition
    )
    return (
        *condition_artifacts,
        output_dir / "comparison.csv",
        output_dir / "stats.csv",
    )


def test_exports_normal_rg_timeseries(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    path = export_rg_timeseries(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="normal",
        frame_time_ps=100.0,
    )

    assert path == output_dir / "normal" / "rg_timeseries.csv"
    assert path.is_file()
    assert read_header(path) == list(RG_TIMESERIES_COLUMNS)

    rows = read_rows(path)
    assert len(rows) == 2
    assert_conditions(rows, "normal")
    assert [row["frame"] for row in rows] == ["0", "1"]
    assert [row["time_ps"] for row in rows] == ["0", "100"]
    assert [row["rg_A"] for row in rows] == ["35.0", "37.0"]


def test_exports_tumor_rg_timeseries(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    path = export_rg_timeseries(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="tumor",
        frame_time_ps=100.0,
    )

    assert path == output_dir / "tumor" / "rg_timeseries.csv"
    assert path.is_file()

    rows = read_rows(path)
    assert len(rows) == 2
    assert_conditions(rows, "tumor")


def test_exported_rg_timeseries_passes_existing_validators(tmp_path: Path) -> None:
    path = export_rg_timeseries(
        source_dir=FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        condition="normal",
        frame_time_ps=100.0,
    )

    validate_csv_artifact_schema(path, "rg_timeseries.csv")
    validate_condition_column(path, "normal")


def test_missing_source_file_fails(tmp_path: Path) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_rg_timeseries(
            source_dir=FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            condition="missing",
            frame_time_ps=100.0,
        )


@pytest.mark.parametrize(
    "frame_time_ps",
    [0, -1, float("nan"), float("inf")],
)
def test_invalid_frame_time_ps_fails(
    tmp_path: Path,
    frame_time_ps: float,
) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_rg_timeseries(
            source_dir=FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            condition="normal",
            frame_time_ps=frame_time_ps,
        )


def test_missing_notebook_column_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "rg_timeseries_normal.csv",
        ("frame", "condition"),
        (("0", "normal"),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_rg_timeseries(
            source_dir=source_dir,
            output_dir=tmp_path / "mania_output",
            condition="normal",
            frame_time_ps=100.0,
        )


def test_condition_mismatch_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "rg_timeseries_normal.csv",
        ("frame", "rg_A", "condition"),
        (("0", "35.0", "tumor"),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_rg_timeseries(
            source_dir=source_dir,
            output_dir=tmp_path / "mania_output",
            condition="normal",
            frame_time_ps=100.0,
        )


def test_empty_condition_value_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "rg_timeseries_normal.csv",
        ("frame", "rg_A", "condition"),
        (("0", "35.0", ""),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_rg_timeseries(
            source_dir=source_dir,
            output_dir=tmp_path / "mania_output",
            condition="normal",
            frame_time_ps=100.0,
        )


def test_invalid_frame_value_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "rg_timeseries_normal.csv",
        ("frame", "rg_A", "condition"),
        (("not-an-int", "35.0", "normal"),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_rg_timeseries(
            source_dir=source_dir,
            output_dir=tmp_path / "mania_output",
            condition="normal",
            frame_time_ps=100.0,
        )


def test_invalid_rg_value_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "rg_timeseries_normal.csv",
        ("frame", "rg_A", "condition"),
        (("0", "not-a-number", "normal"),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_rg_timeseries(
            source_dir=source_dir,
            output_dir=tmp_path / "mania_output",
            condition="normal",
            frame_time_ps=100.0,
        )


@pytest.mark.parametrize("rg_value", ["nan", "inf"])
def test_non_finite_rg_value_fails(tmp_path: Path, rg_value: str) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "rg_timeseries_normal.csv",
        ("frame", "rg_A", "condition"),
        (("0", rg_value, "normal"),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_rg_timeseries(
            source_dir=source_dir,
            output_dir=tmp_path / "mania_output",
            condition="normal",
            frame_time_ps=100.0,
        )


def test_decimal_frame_time_ps_works(tmp_path: Path) -> None:
    path = export_rg_timeseries(
        source_dir=FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        condition="normal",
        frame_time_ps=0.5,
    )

    rows = read_rows(path)
    assert [row["time_ps"] for row in rows] == ["0", "0.5"]


def test_output_directory_is_created(tmp_path: Path) -> None:
    output_dir = tmp_path / "nested" / "mania_output"

    path = export_rg_timeseries(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="normal",
        frame_time_ps=100.0,
    )

    assert path == output_dir / "normal" / "rg_timeseries.csv"
    assert path.is_file()


def test_exports_normal_centrality(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    path = export_centrality(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="normal",
    )

    assert path == output_dir / "normal" / "centrality.csv"
    assert path.is_file()
    assert read_header(path) == list(CENTRALITY_COLUMNS)

    rows = read_rows(path)
    assert len(rows) == 2
    assert_conditions(rows, "normal")
    validate_csv_artifact_schema(path, "centrality.csv")
    validate_condition_column(path, "normal")


def test_exports_tumor_centrality(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    path = export_centrality(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="tumor",
    )

    assert path == output_dir / "tumor" / "centrality.csv"
    rows = read_rows(path)
    assert len(rows) == 2
    assert_conditions(rows, "tumor")


def test_exports_normal_communities(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    path = export_communities(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="normal",
    )

    assert path == output_dir / "normal" / "communities.csv"
    assert path.is_file()
    assert read_header(path) == list(COMMUNITIES_COLUMNS)

    rows = read_rows(path)
    assert len(rows) == 2
    assert_conditions(rows, "normal")
    validate_csv_artifact_schema(path, "communities.csv")
    validate_condition_column(path, "normal")


def test_exports_tumor_communities(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    path = export_communities(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="tumor",
    )

    assert path == output_dir / "tumor" / "communities.csv"
    rows = read_rows(path)
    assert len(rows) == 2
    assert_conditions(rows, "tumor")


def test_missing_centrality_source_file_fails(tmp_path: Path) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_centrality(
            source_dir=FIXTURE_DIR,
            output_dir=tmp_path / "out",
            condition="missing",
        )


def test_missing_communities_source_file_fails(tmp_path: Path) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_communities(
            source_dir=FIXTURE_DIR,
            output_dir=tmp_path / "out",
            condition="missing",
        )


def test_centrality_missing_required_column_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    header = tuple(column for column in CENTRALITY_COLUMNS if column != "pagerank")
    write_csv(
        source_dir / "centrality_normal.csv",
        header,
        (("1", "normal", "1", "0.7", "0.0", "0.5", "0.6", "1"),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_centrality(
            source_dir=source_dir,
            output_dir=tmp_path / "out",
            condition="normal",
        )


def test_communities_missing_required_column_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    header = tuple(column for column in COMMUNITIES_COLUMNS if column != "algorithm")
    write_csv(
        source_dir / "communities_normal.csv",
        header,
        (("1", "normal", "1", "2"),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_communities(
            source_dir=source_dir,
            output_dir=tmp_path / "out",
            condition="normal",
        )


def test_centrality_condition_mismatch_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "centrality_normal.csv",
        CENTRALITY_COLUMNS,
        (("1", "tumor", "1", "0.7", "0.0", "0.5", "0.6", "0.55", "1"),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_centrality(
            source_dir=source_dir,
            output_dir=tmp_path / "out",
            condition="normal",
        )


def test_communities_condition_mismatch_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "communities_normal.csv",
        COMMUNITIES_COLUMNS,
        (("1", "tumor", "1", "2", "fixture_louvain"),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_communities(
            source_dir=source_dir,
            output_dir=tmp_path / "out",
            condition="normal",
        )


def test_centrality_empty_condition_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "centrality_normal.csv",
        CENTRALITY_COLUMNS,
        (("1", "", "1", "0.7", "0.0", "0.5", "0.6", "0.55", "1"),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_centrality(
            source_dir=source_dir,
            output_dir=tmp_path / "out",
            condition="normal",
        )


def test_communities_empty_condition_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "communities_normal.csv",
        COMMUNITIES_COLUMNS,
        (("1", "", "1", "2", "fixture_louvain"),),
    )

    with pytest.raises(NotebookExportAdapterError):
        export_communities(
            source_dir=source_dir,
            output_dir=tmp_path / "out",
            condition="normal",
        )


def test_centrality_extra_input_columns_are_dropped(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "centrality_normal.csv",
        (*CENTRALITY_COLUMNS, "extra_debug"),
        (("1", "normal", "1", "0.7", "0.0", "0.5", "0.6", "0.55", "1", "x"),),
    )

    path = export_centrality(
        source_dir=source_dir,
        output_dir=tmp_path / "out",
        condition="normal",
    )

    header = read_header(path)
    assert header == list(CENTRALITY_COLUMNS)
    assert "extra_debug" not in header


def test_communities_extra_input_columns_are_dropped(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(
        source_dir / "communities_normal.csv",
        (*COMMUNITIES_COLUMNS, "extra_debug"),
        (("1", "normal", "1", "2", "fixture_louvain", "x"),),
    )

    path = export_communities(
        source_dir=source_dir,
        output_dir=tmp_path / "out",
        condition="normal",
    )

    header = read_header(path)
    assert header == list(COMMUNITIES_COLUMNS)
    assert "extra_debug" not in header


def test_table_export_output_directory_is_created(tmp_path: Path) -> None:
    output_dir = tmp_path / "nested" / "mania_output"

    path = export_centrality(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="normal",
    )

    assert path.exists()
    assert path.parent.is_dir()


def test_empty_centrality_data_file_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(source_dir / "centrality_normal.csv", CENTRALITY_COLUMNS, ())

    with pytest.raises(NotebookExportAdapterError):
        export_centrality(
            source_dir=source_dir,
            output_dir=tmp_path / "out",
            condition="normal",
        )


def test_empty_communities_data_file_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_csv(source_dir / "communities_normal.csv", COMMUNITIES_COLUMNS, ())

    with pytest.raises(NotebookExportAdapterError):
        export_communities(
            source_dir=source_dir,
            output_dir=tmp_path / "out",
            condition="normal",
        )


def test_exports_normal_nodes(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    path = export_nodes(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="normal",
    )

    assert path == output_dir / "normal" / "nodes.csv"
    assert path.is_file()
    assert read_header(path) == list(NODE_COLUMNS)

    rows = read_rows(path)
    assert len(rows) == 2
    assert_conditions(rows, "normal")
    assert [row["resid"] for row in rows] == ["1", "2"]
    assert {"degree", "strength", "pagerank", "kcore"}.issubset(rows[0])
    assert "community_id" in rows[0]
    assert "community_size" not in rows[0]
    assert "algorithm" not in rows[0]
    validate_csv_artifact_schema(path, "nodes.csv")
    validate_condition_column(path, "normal")


def test_exports_tumor_nodes(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    path = export_nodes(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="tumor",
    )

    assert path == output_dir / "tumor" / "nodes.csv"
    rows = read_rows(path)
    assert len(rows) == 2
    assert_conditions(rows, "tumor")
    assert [row["resid"] for row in rows] == ["1", "2"]


def test_missing_residue_table_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_centrality_table(source_dir)
    write_communities_table(source_dir)

    assert_export_nodes_fails(source_dir, tmp_path)


def test_missing_node_centrality_table_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_residue_table(source_dir)
    write_communities_table(source_dir)

    assert_export_nodes_fails(source_dir, tmp_path)


def test_missing_node_communities_table_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_residue_table(source_dir)
    write_centrality_table(source_dir)

    assert_export_nodes_fails(source_dir, tmp_path)


def test_node_residue_table_missing_required_column_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    header = tuple(column for column in RESIDUE_TABLE_COLUMNS if column != "resname")
    write_residue_table(
        source_dir,
        header=header,
        rows=(
            ("1", "TM1", "normal", "1.0", "2.0", "3.0", "-0.5", "0.8", "120.0", "H"),
        ),
    )
    write_centrality_table(source_dir)
    write_communities_table(source_dir)

    assert_export_nodes_fails(source_dir, tmp_path)


def test_node_centrality_missing_required_column_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_residue_table(source_dir)
    header = tuple(column for column in CENTRALITY_COLUMNS if column != "pagerank")
    write_centrality_table(
        source_dir,
        header=header,
        rows=(("1", "normal", "1", "0.7", "0.0", "0.5", "0.6", "1"),),
    )
    write_communities_table(source_dir)

    assert_export_nodes_fails(source_dir, tmp_path)


def test_node_communities_missing_required_column_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_residue_table(source_dir)
    write_centrality_table(source_dir)
    header = tuple(column for column in COMMUNITIES_COLUMNS if column != "community_id")
    write_communities_table(
        source_dir,
        header=header,
        rows=(("1", "normal", "2", "fixture_louvain"),),
    )

    assert_export_nodes_fails(source_dir, tmp_path)


def test_node_residue_condition_mismatch_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_residue_table(source_dir, rows=(residue_row(condition="tumor"),))
    write_centrality_table(source_dir)
    write_communities_table(source_dir)

    assert_export_nodes_fails(source_dir, tmp_path)


def test_node_centrality_condition_mismatch_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_residue_table(source_dir)
    write_centrality_table(source_dir, rows=(centrality_row(condition="tumor"),))
    write_communities_table(source_dir)

    assert_export_nodes_fails(source_dir, tmp_path)


def test_node_communities_condition_mismatch_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_residue_table(source_dir)
    write_centrality_table(source_dir)
    write_communities_table(source_dir, rows=(community_row(condition="tumor"),))

    assert_export_nodes_fails(source_dir, tmp_path)


def test_duplicate_resid_in_residue_table_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_minimal_node_sources(
        source_dir,
        residue_rows=(residue_row("1"), residue_row("1", resname="POPC")),
    )

    assert_export_nodes_fails(source_dir, tmp_path)


def test_duplicate_resid_in_centrality_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_minimal_node_sources(
        source_dir,
        centrality_rows=(centrality_row("1"), centrality_row("1")),
    )

    assert_export_nodes_fails(source_dir, tmp_path)


def test_duplicate_resid_in_communities_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_minimal_node_sources(
        source_dir,
        community_rows=(community_row("1"), community_row("1")),
    )

    assert_export_nodes_fails(source_dir, tmp_path)


def test_missing_centrality_row_for_nodes_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_minimal_node_sources(
        source_dir,
        residue_rows=(residue_row("1"), residue_row("2", resname="POPC")),
        centrality_rows=(centrality_row("1"),),
        community_rows=(community_row("1"), community_row("2")),
    )

    assert_export_nodes_fails(source_dir, tmp_path)


def test_missing_communities_row_for_nodes_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_minimal_node_sources(
        source_dir,
        residue_rows=(residue_row("1"), residue_row("2", resname="POPC")),
        centrality_rows=(centrality_row("1"), centrality_row("2")),
        community_rows=(community_row("1"),),
    )

    assert_export_nodes_fails(source_dir, tmp_path)


def test_extra_centrality_row_without_residue_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_minimal_node_sources(
        source_dir,
        centrality_rows=(centrality_row("1"), centrality_row("3")),
    )

    assert_export_nodes_fails(source_dir, tmp_path)


def test_extra_communities_row_without_residue_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_minimal_node_sources(
        source_dir,
        community_rows=(community_row("1"), community_row("3")),
    )

    assert_export_nodes_fails(source_dir, tmp_path)


def test_node_extra_input_columns_are_dropped(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_residue_table(
        source_dir,
        header=(*RESIDUE_TABLE_COLUMNS, "extra_debug"),
        rows=((*residue_row(), "x"),),
    )
    write_centrality_table(
        source_dir,
        header=(*CENTRALITY_COLUMNS, "extra_debug"),
        rows=((*centrality_row(), "x"),),
    )
    write_communities_table(
        source_dir,
        header=(*COMMUNITIES_COLUMNS, "extra_debug"),
        rows=((*community_row(), "x"),),
    )

    path = export_nodes(
        source_dir=source_dir,
        output_dir=tmp_path / "out",
        condition="normal",
    )

    header = read_header(path)
    assert header == list(NODE_COLUMNS)
    assert "extra_debug" not in header
    assert "community_size" not in header
    assert "algorithm" not in header


def test_empty_required_node_value_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_minimal_node_sources(source_dir, residue_rows=(residue_row(resname=""),))

    assert_export_nodes_fails(source_dir, tmp_path)


def test_empty_residue_data_file_for_nodes_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_residue_table(source_dir, rows=())
    write_centrality_table(source_dir)
    write_communities_table(source_dir)

    assert_export_nodes_fails(source_dir, tmp_path)


def test_exports_normal_edges(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    path = export_edges(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="normal",
    )

    assert path == output_dir / "normal" / "edges.csv"
    assert path.is_file()
    assert read_header(path) == list(EDGE_COLUMNS)

    rows = read_rows(path)
    assert len(rows) == 1
    assert_conditions(rows, "normal")
    assert [(row["resid_i"], row["resid_j"]) for row in rows] == [("1", "2")]
    validate_csv_artifact_schema(path, "edges.csv")
    validate_condition_column(path, "normal")


def test_exports_tumor_edges(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    path = export_edges(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="tumor",
    )

    assert path == output_dir / "tumor" / "edges.csv"
    rows = read_rows(path)
    assert len(rows) == 1
    assert_conditions(rows, "tumor")


def test_missing_edge_source_file_fails(tmp_path: Path) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_edges(
            source_dir=FIXTURE_DIR,
            output_dir=tmp_path / "out",
            condition="missing",
        )


def test_edge_file_missing_required_column_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    header = tuple(column for column in EDGE_COLUMNS if column != "contact_freq")
    row = tuple(value for index, value in enumerate(edge_row()) if index != 4)
    write_edges_table(source_dir, header=header, rows=(row,))

    assert_export_edges_fails(source_dir, tmp_path)


def test_edge_condition_mismatch_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_edges_table(source_dir, rows=(edge_row(condition="tumor"),))

    assert_export_edges_fails(source_dir, tmp_path)


def test_edge_empty_condition_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_edges_table(source_dir, rows=(edge_row(condition=""),))

    assert_export_edges_fails(source_dir, tmp_path)


def test_edge_empty_resid_i_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_edges_table(source_dir, rows=(edge_row(resid_i=""),))

    assert_export_edges_fails(source_dir, tmp_path)


def test_edge_empty_resid_j_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_edges_table(source_dir, rows=(edge_row(resid_j=""),))

    assert_export_edges_fails(source_dir, tmp_path)


def test_edge_empty_edge_type_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_edges_table(source_dir, rows=(edge_row(edge_type=""),))

    assert_export_edges_fails(source_dir, tmp_path)


def test_edge_empty_required_metric_value_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_edges_table(source_dir, rows=(edge_row(contact_freq=""),))

    assert_export_edges_fails(source_dir, tmp_path)


def test_duplicate_undirected_edge_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_edges_table(
        source_dir,
        rows=(
            edge_row("1", "2", edge_type="contact"),
            edge_row("2", "1", edge_type="contact"),
        ),
    )

    assert_export_edges_fails(source_dir, tmp_path)


def test_same_pair_with_different_edge_type_is_allowed(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_edges_table(
        source_dir,
        rows=(
            edge_row("1", "2", edge_type="contact"),
            edge_row("2", "1", edge_type="hydrogen_bond"),
        ),
    )

    path = export_edges(
        source_dir=source_dir,
        output_dir=tmp_path / "out",
        condition="normal",
    )

    rows = read_rows(path)
    assert len(rows) == 2
    assert [row["edge_type"] for row in rows] == ["contact", "hydrogen_bond"]


def test_edge_extra_input_columns_are_dropped(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_edges_table(
        source_dir,
        header=(*EDGE_COLUMNS, "extra_debug"),
        rows=((*edge_row(), "x"),),
    )

    path = export_edges(
        source_dir=source_dir,
        output_dir=tmp_path / "out",
        condition="normal",
    )

    header = read_header(path)
    assert header == list(EDGE_COLUMNS)
    assert "extra_debug" not in header


def test_empty_edge_data_file_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_edges_table(source_dir, rows=())

    assert_export_edges_fails(source_dir, tmp_path)


def test_edge_output_directory_is_created(tmp_path: Path) -> None:
    output_dir = tmp_path / "nested" / "mania_output"

    path = export_edges(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="normal",
    )

    assert path.exists()
    assert path.parent.is_dir()


def test_exports_normal_graph(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"
    export_nodes(FIXTURE_DIR, output_dir, "normal")
    export_edges(FIXTURE_DIR, output_dir, "normal")

    path = export_graph(output_dir, "normal")

    assert path == output_dir / "normal" / "graph.json"
    assert path.is_file()

    graph = read_json(path)
    assert graph["condition"] == "normal"
    assert graph["schema_version"] == SCHEMA_VERSION
    assert graph["directed"] is False
    assert graph["n_nodes"] == 2
    assert graph["n_edges"] == 1

    nodes = graph["nodes"]
    edges = graph["edges"]
    assert isinstance(nodes, list)
    assert isinstance(edges, list)
    assert len(nodes) == 2
    assert len(edges) == 1
    assert {node["id"] for node in nodes if isinstance(node, dict)} == {"1", "2"}

    edge = edges[0]
    assert isinstance(edge, dict)
    assert edge["source"] == "1"
    assert edge["target"] == "2"
    validate_graph_json(path, expected_condition="normal")


def test_exports_tumor_graph(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"
    export_nodes(FIXTURE_DIR, output_dir, "tumor")
    export_edges(FIXTURE_DIR, output_dir, "tumor")

    path = export_graph(output_dir, "tumor")

    graph = read_json(path)
    assert graph["condition"] == "tumor"
    assert graph["n_nodes"] == 2
    assert graph["n_edges"] == 1

    nodes = graph["nodes"]
    assert isinstance(nodes, list)
    assert {node["id"] for node in nodes if isinstance(node, dict)} == {"1", "2"}


def test_graph_missing_nodes_csv_fails(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"
    export_edges(FIXTURE_DIR, output_dir, "normal")

    assert_export_graph_fails(output_dir)


def test_graph_missing_edges_csv_fails(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"
    export_nodes(FIXTURE_DIR, output_dir, "normal")

    assert_export_graph_fails(output_dir)


def test_graph_invalid_nodes_schema_fails(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"
    condition_dir = output_dir / "normal"
    header = tuple(column for column in NODE_COLUMNS if column != "resname")
    row = tuple(value for index, value in enumerate(residue_row()) if index != 1)
    write_nodes_csv(condition_dir / "nodes.csv", (row,), header=header)
    write_edges_csv(condition_dir / "edges.csv", (edge_row(),))

    assert_export_graph_fails(output_dir)


def test_graph_invalid_edges_schema_fails(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"
    condition_dir = output_dir / "normal"
    write_nodes_csv(condition_dir / "nodes.csv", (node_row(),))
    header = tuple(column for column in EDGE_COLUMNS if column != "contact_freq")
    row = tuple(value for index, value in enumerate(edge_row()) if index != 4)
    write_edges_csv(condition_dir / "edges.csv", (row,), header=header)

    assert_export_graph_fails(output_dir)


def test_graph_nodes_condition_mismatch_fails(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"
    condition_dir = output_dir / "normal"
    write_nodes_csv(condition_dir / "nodes.csv", (node_row(condition="tumor"),))
    write_edges_csv(condition_dir / "edges.csv", (edge_row(),))

    assert_export_graph_fails(output_dir)


def test_graph_edges_condition_mismatch_fails(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"
    condition_dir = output_dir / "normal"
    write_nodes_csv(condition_dir / "nodes.csv", (node_row(),))
    write_edges_csv(condition_dir / "edges.csv", (edge_row(condition="tumor"),))

    assert_export_graph_fails(output_dir)


def test_graph_duplicate_node_ids_fail(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"
    condition_dir = output_dir / "normal"
    write_nodes_csv(condition_dir / "nodes.csv", (node_row("1"), node_row("1")))
    write_edges_csv(condition_dir / "edges.csv", (edge_row(),))

    assert_export_graph_fails(output_dir)


def test_graph_empty_node_resid_fails(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"
    condition_dir = output_dir / "normal"
    write_nodes_csv(condition_dir / "nodes.csv", (node_row(""),))
    write_edges_csv(condition_dir / "edges.csv", (edge_row(),))

    assert_export_graph_fails(output_dir)


def test_graph_edge_missing_source_node_fails(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"
    condition_dir = output_dir / "normal"
    write_nodes_csv(condition_dir / "nodes.csv", (node_row("1"),))
    write_edges_csv(condition_dir / "edges.csv", (edge_row("3", "1"),))

    assert_export_graph_fails(output_dir)


def test_graph_edge_missing_target_node_fails(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"
    condition_dir = output_dir / "normal"
    write_nodes_csv(condition_dir / "nodes.csv", (node_row("1"),))
    write_edges_csv(condition_dir / "edges.csv", (edge_row("1", "3"),))

    assert_export_graph_fails(output_dir)


def test_graph_empty_edge_resid_i_fails(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"
    condition_dir = output_dir / "normal"
    write_nodes_csv(condition_dir / "nodes.csv", (node_row("1"),))
    write_edges_csv(condition_dir / "edges.csv", (edge_row("", "1"),))

    assert_export_graph_fails(output_dir)


def test_graph_empty_edge_resid_j_fails(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"
    condition_dir = output_dir / "normal"
    write_nodes_csv(condition_dir / "nodes.csv", (node_row("1"),))
    write_edges_csv(condition_dir / "edges.csv", (edge_row("1", ""),))

    assert_export_graph_fails(output_dir)


def test_per_condition_graph_does_not_condition_scope_node_ids(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "mania_output"
    export_nodes(FIXTURE_DIR, output_dir, "normal")
    export_edges(FIXTURE_DIR, output_dir, "normal")

    path = export_graph(output_dir, "normal")

    graph = read_json(path)
    nodes = graph["nodes"]
    assert isinstance(nodes, list)
    node_ids = [node["id"] for node in nodes if isinstance(node, dict)]
    assert node_ids == ["1", "2"]
    assert all(":" not in node_id for node_id in node_ids)


def test_export_condition_exports_all_normal_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    result = export_condition(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="normal",
        frame_time_ps=100.0,
    )

    assert isinstance(result, ConditionExportResult)
    assert result.condition == "normal"
    assert all(path.exists() for path in result.paths)
    assert (output_dir / "normal").is_dir()
    assert result.paths == (
        output_dir / "normal" / "rg_timeseries.csv",
        output_dir / "normal" / "centrality.csv",
        output_dir / "normal" / "communities.csv",
        output_dir / "normal" / "nodes.csv",
        output_dir / "normal" / "edges.csv",
        output_dir / "normal" / "graph.json",
    )
    validate_condition_export_result(result, "normal")


def test_export_condition_exports_all_tumor_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    result = export_condition(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        condition="tumor",
        frame_time_ps=100.0,
    )

    assert isinstance(result, ConditionExportResult)
    assert result.condition == "tumor"
    assert all(path.exists() for path in result.paths)

    validate_condition_export_result(result, "tumor")
    graph = read_json(result.graph_path)
    assert graph["condition"] == "tumor"


def test_condition_export_result_paths_property_works(tmp_path: Path) -> None:
    result = export_condition(
        source_dir=FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        condition="normal",
        frame_time_ps=100.0,
    )

    assert len(result.paths) == 6
    assert result.paths == (
        result.rg_timeseries_path,
        result.centrality_path,
        result.communities_path,
        result.nodes_path,
        result.edges_path,
        result.graph_path,
    )
    assert all(path.exists() for path in result.paths)


def test_export_condition_failure_propagates_for_missing_source(
    tmp_path: Path,
) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_condition(
            source_dir=tmp_path / "empty_source",
            output_dir=tmp_path / "mania_output",
            condition="normal",
            frame_time_ps=100.0,
        )


def test_export_condition_invalid_frame_time_ps_propagates(tmp_path: Path) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_condition(
            source_dir=FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            condition="normal",
            frame_time_ps=0,
        )


def test_export_condition_creates_graph_after_nodes_and_edges(
    tmp_path: Path,
) -> None:
    result = export_condition(
        source_dir=FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        condition="normal",
        frame_time_ps=100.0,
    )

    graph = read_json(result.graph_path)
    nodes_rows = read_rows(result.nodes_path)
    edges_rows = read_rows(result.edges_path)

    assert result.nodes_path.exists()
    assert result.edges_path.exists()
    assert result.graph_path.exists()
    assert graph["n_nodes"] == len(nodes_rows)
    assert graph["n_edges"] == len(edges_rows)


def test_export_conditions_exports_normal_and_tumor(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    result = export_conditions(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        conditions=("normal", "tumor"),
        frame_time_ps=100.0,
    )

    assert isinstance(result, MultiConditionExportResult)
    assert result.conditions == ("normal", "tumor")
    assert set(result.condition_results) == {"normal", "tumor"}
    assert result.condition_results["normal"].condition == "normal"
    assert result.condition_results["tumor"].condition == "tumor"
    assert all(path.exists() for path in result.paths)
    assert (output_dir / "normal").is_dir()
    assert (output_dir / "tumor").is_dir()

    for condition in result.conditions:
        condition_dir = output_dir / condition
        assert (condition_dir / "rg_timeseries.csv").is_file()
        assert (condition_dir / "centrality.csv").is_file()
        assert (condition_dir / "communities.csv").is_file()
        assert (condition_dir / "nodes.csv").is_file()
        assert (condition_dir / "edges.csv").is_file()
        assert (condition_dir / "graph.json").is_file()


def test_export_conditions_outputs_pass_validators(tmp_path: Path) -> None:
    result = export_conditions(
        source_dir=FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        conditions=("normal", "tumor"),
        frame_time_ps=100.0,
    )

    for condition in result.conditions:
        validate_condition_export_result(
            result.condition_results[condition],
            condition,
        )


def test_export_conditions_preserves_condition_order(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    result = export_conditions(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        conditions=("tumor", "normal"),
        frame_time_ps=100.0,
    )

    assert result.conditions == ("tumor", "normal")
    assert result.paths[:6] == result.condition_results["tumor"].paths
    assert result.paths[6:] == result.condition_results["normal"].paths
    assert result.paths[0] == output_dir / "tumor" / "rg_timeseries.csv"
    assert result.paths[6] == output_dir / "normal" / "rg_timeseries.csv"


def test_export_conditions_strips_condition_whitespace(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    result = export_conditions(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        conditions=(" normal ", " tumor "),
        frame_time_ps=100.0,
    )

    assert result.conditions == ("normal", "tumor")
    assert (output_dir / "normal").is_dir()
    assert (output_dir / "tumor").is_dir()
    assert not (output_dir / " normal ").exists()
    assert not (output_dir / " tumor ").exists()


@pytest.mark.parametrize("conditions", [("normal", ""), ("normal", "   ")])
def test_export_conditions_empty_condition_fails(
    tmp_path: Path,
    conditions: tuple[str, str],
) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_conditions(
            source_dir=FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            conditions=conditions,
            frame_time_ps=100.0,
        )


def test_export_conditions_duplicate_condition_fails(tmp_path: Path) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_conditions(
            source_dir=FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            conditions=("normal", "normal"),
            frame_time_ps=100.0,
        )


def test_export_conditions_duplicate_after_stripping_fails(tmp_path: Path) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_conditions(
            source_dir=FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            conditions=("normal", " normal "),
            frame_time_ps=100.0,
        )


def test_export_conditions_missing_source_for_one_condition_fails(
    tmp_path: Path,
) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_conditions(
            source_dir=FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            conditions=("normal", "missing"),
            frame_time_ps=100.0,
        )


def test_export_conditions_invalid_frame_time_ps_propagates(tmp_path: Path) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_conditions(
            source_dir=FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            conditions=("normal", "tumor"),
            frame_time_ps=0,
        )


def test_multi_condition_export_result_paths_property_works(tmp_path: Path) -> None:
    result = export_conditions(
        source_dir=FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        conditions=("normal", "tumor"),
        frame_time_ps=100.0,
    )

    assert len(result.paths) == 12
    assert all(path.exists() for path in result.paths)
    assert result.paths[:6] == result.condition_results["normal"].paths
    assert result.paths[6:] == result.condition_results["tumor"].paths


def test_exports_run_meta_for_all_manifest_conditions(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    path = export_run_meta(source_dir=FIXTURE_DIR, output_dir=output_dir)

    assert path == output_dir / "run_meta.json"
    assert path.is_file()

    payload = read_json(path)
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["conditions"] == ["normal", "tumor"]
    assert payload["source_manifest"] == "mania_manifest.json"

    global_features = payload["global_features"]
    assert isinstance(global_features, dict)
    assert list(global_features) == ["normal", "tumor"]
    for condition in ("normal", "tumor"):
        features = global_features[condition]
        assert isinstance(features, dict)
        assert "rg_mean_A" in features
        assert "rg_std_A" in features
        assert "n_rg_frames" in features


def test_exports_run_meta_for_explicit_conditions(tmp_path: Path) -> None:
    path = export_run_meta(
        source_dir=FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        conditions=("normal",),
    )

    payload = read_json(path)
    assert payload["conditions"] == ["normal"]

    global_features = payload["global_features"]
    assert isinstance(global_features, dict)
    assert set(global_features) == {"normal"}
    assert "tumor" not in global_features


def test_run_meta_explicit_condition_order_is_preserved(tmp_path: Path) -> None:
    path = export_run_meta(
        source_dir=FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        conditions=("tumor", "normal"),
    )

    payload = read_json(path)
    assert payload["conditions"] == ["tumor", "normal"]

    global_features = payload["global_features"]
    assert isinstance(global_features, dict)
    assert list(global_features) == ["tumor", "normal"]


def test_run_meta_condition_whitespace_is_stripped(tmp_path: Path) -> None:
    path = export_run_meta(
        source_dir=FIXTURE_DIR,
        output_dir=tmp_path / "mania_output",
        conditions=(" normal ", " tumor "),
    )

    payload = read_json(path)
    assert payload["conditions"] == ["normal", "tumor"]


@pytest.mark.parametrize("conditions", [("normal", ""), ("normal", "   ")])
def test_run_meta_empty_condition_fails(
    tmp_path: Path,
    conditions: tuple[str, str],
) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_run_meta(
            source_dir=FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            conditions=conditions,
        )


def test_run_meta_duplicate_condition_fails(tmp_path: Path) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_run_meta(
            source_dir=FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            conditions=("normal", " normal "),
        )


def test_run_meta_missing_requested_condition_fails(tmp_path: Path) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_run_meta(
            source_dir=FIXTURE_DIR,
            output_dir=tmp_path / "mania_output",
            conditions=("normal", "missing"),
        )


def test_run_meta_missing_source_manifest_fails(tmp_path: Path) -> None:
    with pytest.raises(NotebookExportAdapterError):
        export_run_meta(
            source_dir=tmp_path / "source",
            output_dir=tmp_path / "mania_output",
        )


def test_run_meta_invalid_manifest_json_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "mania_manifest.json").write_text("{", encoding="utf-8")

    with pytest.raises(NotebookExportAdapterError):
        export_run_meta(source_dir=source_dir, output_dir=tmp_path / "mania_output")


def test_run_meta_missing_global_features_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_json(source_dir / "mania_manifest.json", {"conditions": ["normal"]})

    with pytest.raises(NotebookExportAdapterError):
        export_run_meta(source_dir=source_dir, output_dir=tmp_path / "mania_output")


def test_run_meta_invalid_global_feature_value_fails(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    write_json(source_dir / "mania_manifest.json", manifest_payload(rg_mean_A=-1.0))

    with pytest.raises(NotebookExportAdapterError):
        export_run_meta(source_dir=source_dir, output_dir=tmp_path / "mania_output")


def test_run_meta_output_directory_is_created(tmp_path: Path) -> None:
    output_dir = tmp_path / "nested" / "mania_output"

    path = export_run_meta(source_dir=FIXTURE_DIR, output_dir=output_dir)

    assert output_dir.is_dir()
    assert path.is_file()


def test_export_conditions_does_not_create_run_meta(tmp_path: Path) -> None:
    output_dir = tmp_path / "mania_output"

    export_conditions(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        conditions=("normal", "tumor"),
        frame_time_ps=100.0,
    )

    assert not (output_dir / "run_meta.json").exists()


def test_export_notebook_contract_subset_exports_supported_outputs(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "mania_output"

    result = export_notebook_contract_subset(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        conditions=("normal", "tumor"),
        frame_time_ps=100.0,
    )

    assert isinstance(result, NotebookContractSubsetExportResult)
    assert result.run_meta_path == output_dir / "run_meta.json"
    assert result.conditions_result.conditions == ("normal", "tumor")
    assert result.paths == (
        output_dir / "run_meta.json",
        output_dir / "normal" / "rg_timeseries.csv",
        output_dir / "normal" / "centrality.csv",
        output_dir / "normal" / "communities.csv",
        output_dir / "normal" / "nodes.csv",
        output_dir / "normal" / "edges.csv",
        output_dir / "normal" / "graph.json",
        output_dir / "tumor" / "rg_timeseries.csv",
        output_dir / "tumor" / "centrality.csv",
        output_dir / "tumor" / "communities.csv",
        output_dir / "tumor" / "nodes.csv",
        output_dir / "tumor" / "edges.csv",
        output_dir / "tumor" / "graph.json",
    )
    assert all(path.exists() for path in result.paths)

    payload = read_json(result.run_meta_path)
    assert payload["conditions"] == ["normal", "tumor"]
    for condition in result.conditions_result.conditions:
        validate_condition_export_result(
            result.conditions_result.condition_results[condition],
            condition,
        )
    assert all(not path.exists() for path in unsupported_artifact_paths(output_dir))


def test_export_notebook_contract_subset_infers_conditions_from_run_meta(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "mania_output"

    result = export_notebook_contract_subset(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        frame_time_ps=100.0,
    )

    assert result.conditions_result.conditions == ("normal", "tumor")
    assert result.paths[0] == output_dir / "run_meta.json"
    assert result.paths[1:7] == result.conditions_result.condition_results[
        "normal"
    ].paths
    assert result.paths[7:] == result.conditions_result.condition_results[
        "tumor"
    ].paths


def test_export_notebook_contract_subset_uses_explicit_conditions_for_both_steps(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "mania_output"

    result = export_notebook_contract_subset(
        source_dir=FIXTURE_DIR,
        output_dir=output_dir,
        conditions=iter(("tumor", "normal")),
        frame_time_ps=100.0,
    )

    payload = read_json(result.run_meta_path)
    assert payload["conditions"] == ["tumor", "normal"]
    assert result.conditions_result.conditions == ("tumor", "normal")
    assert result.paths[1] == output_dir / "tumor" / "rg_timeseries.csv"
    assert result.paths[7] == output_dir / "normal" / "rg_timeseries.csv"


def test_export_notebook_contract_subset_fails_before_conditions_for_bad_manifest(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    write_json(source_dir / "mania_manifest.json", {"conditions": ["normal"]})
    output_dir = tmp_path / "mania_output"

    with pytest.raises(NotebookExportAdapterError):
        export_notebook_contract_subset(
            source_dir=source_dir,
            output_dir=output_dir,
            frame_time_ps=100.0,
        )

    assert not (output_dir / "run_meta.json").exists()
    assert not (output_dir / "normal").exists()


def test_export_notebook_contract_subset_propagates_condition_step_failure(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "mania_output"

    with pytest.raises(NotebookExportAdapterError):
        export_notebook_contract_subset(
            source_dir=FIXTURE_DIR,
            output_dir=output_dir,
            conditions=("normal", "tumor"),
            frame_time_ps=0,
        )

    assert (output_dir / "run_meta.json").is_file()
