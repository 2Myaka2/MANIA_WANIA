import json
from pathlib import Path

from mania.constants import SCHEMA_VERSION
from mania.validation.graph import (
    GraphValidationError,
    load_graph_json,
    validate_graph_json,
)


def write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def valid_graph_payload() -> dict[str, object]:
    return {
        "condition": "normal",
        "n_nodes": 2,
        "n_edges": 1,
        "directed": False,
        "schema_version": SCHEMA_VERSION,
        "nodes": [{"id": "1"}, {"id": "2"}],
        "edges": [{"source": "1", "target": "2"}],
    }


def assert_graph_validation_error(path: Path) -> None:
    try:
        validate_graph_json(path, expected_condition="normal")
    except GraphValidationError:
        return
    raise AssertionError("Expected GraphValidationError")


def test_valid_per_condition_graph_passes(tmp_path: Path) -> None:
    path = write_json(tmp_path / "graph.json", valid_graph_payload())

    result = validate_graph_json(path, expected_condition="normal")

    assert result.is_valid
    assert result.condition == "normal"
    assert result.node_ids == ("1", "2")
    assert result.edge_count == 1
    assert result.n_nodes_declared == 2
    assert result.n_edges_declared == 1
    assert result.missing_keys == ()
    assert result.duplicate_node_ids == ()


def test_missing_required_key_fails(tmp_path: Path) -> None:
    payload = valid_graph_payload()
    del payload["schema_version"]
    path = write_json(tmp_path / "graph.json", payload)

    assert_graph_validation_error(path)


def test_wrong_condition_fails(tmp_path: Path) -> None:
    payload = valid_graph_payload()
    payload["condition"] = "tumor"
    path = write_json(tmp_path / "graph.json", payload)

    assert_graph_validation_error(path)


def test_duplicate_node_ids_fail(tmp_path: Path) -> None:
    payload = valid_graph_payload()
    payload["nodes"] = [{"id": "1"}, {"id": "1"}]
    path = write_json(tmp_path / "graph.json", payload)

    assert_graph_validation_error(path)


def test_declared_n_nodes_mismatch_fails(tmp_path: Path) -> None:
    payload = valid_graph_payload()
    payload["n_nodes"] = 3
    path = write_json(tmp_path / "graph.json", payload)

    assert_graph_validation_error(path)


def test_declared_n_edges_mismatch_fails(tmp_path: Path) -> None:
    payload = valid_graph_payload()
    payload["n_edges"] = 2
    path = write_json(tmp_path / "graph.json", payload)

    assert_graph_validation_error(path)


def test_non_list_nodes_fail(tmp_path: Path) -> None:
    payload = valid_graph_payload()
    payload["nodes"] = {}
    path = write_json(tmp_path / "graph.json", payload)

    assert_graph_validation_error(path)


def test_node_without_id_fails(tmp_path: Path) -> None:
    payload = valid_graph_payload()
    payload["nodes"] = [{}]
    payload["n_nodes"] = 1
    path = write_json(tmp_path / "graph.json", payload)

    assert_graph_validation_error(path)


def test_non_list_edges_fail(tmp_path: Path) -> None:
    payload = valid_graph_payload()
    payload["edges"] = {}
    path = write_json(tmp_path / "graph.json", payload)

    assert_graph_validation_error(path)


def test_non_object_edge_fails(tmp_path: Path) -> None:
    payload = valid_graph_payload()
    payload["edges"] = ["not-an-edge"]
    path = write_json(tmp_path / "graph.json", payload)

    assert_graph_validation_error(path)


def test_combined_graph_with_condition_scoped_ids_passes(tmp_path: Path) -> None:
    payload = {
        "condition": "combined",
        "n_nodes": 2,
        "n_edges": 1,
        "directed": False,
        "schema_version": SCHEMA_VERSION,
        "nodes": [{"id": "normal:1"}, {"id": "tumor:1"}],
        "edges": [{"source": "normal:1", "target": "tumor:1"}],
    }
    path = write_json(tmp_path / "graph.json", payload)

    result = validate_graph_json(path, combined_graph=True)

    assert result.is_valid
    assert result.node_ids == ("normal:1", "tumor:1")


def test_combined_graph_without_condition_scoped_ids_fails(tmp_path: Path) -> None:
    path = write_json(tmp_path / "graph.json", valid_graph_payload())

    try:
        validate_graph_json(path, combined_graph=True)
    except GraphValidationError:
        return
    raise AssertionError("Expected GraphValidationError")


def test_explicit_condition_scoped_id_requirement_fails(tmp_path: Path) -> None:
    path = write_json(tmp_path / "graph.json", valid_graph_payload())

    try:
        validate_graph_json(path, require_condition_scoped_ids=True)
    except GraphValidationError:
        return
    raise AssertionError("Expected GraphValidationError")


def test_invalid_json_fails(tmp_path: Path) -> None:
    path = tmp_path / "graph.json"
    path.write_text("{", encoding="utf-8")

    try:
        load_graph_json(path)
    except GraphValidationError:
        return
    raise AssertionError("Expected GraphValidationError")


def test_non_object_json_fails(tmp_path: Path) -> None:
    path = write_json(tmp_path / "graph.json", [])

    try:
        validate_graph_json(path)
    except GraphValidationError:
        return
    raise AssertionError("Expected GraphValidationError")


def test_n_nodes_type_validation_fails(tmp_path: Path) -> None:
    payload = valid_graph_payload()
    payload["n_nodes"] = "2"
    path = write_json(tmp_path / "graph.json", payload)

    assert_graph_validation_error(path)


def test_n_edges_type_validation_fails(tmp_path: Path) -> None:
    payload = valid_graph_payload()
    payload["n_edges"] = "1"
    path = write_json(tmp_path / "graph.json", payload)

    assert_graph_validation_error(path)


def test_integer_node_ids_are_converted_to_strings(tmp_path: Path) -> None:
    payload = valid_graph_payload()
    payload["nodes"] = [{"id": 1}, {"id": 2}]
    payload["edges"] = [{"source": 1, "target": 2}]
    path = write_json(tmp_path / "graph.json", payload)

    result = validate_graph_json(path, expected_condition="normal")

    assert result.is_valid
    assert result.node_ids == ("1", "2")
