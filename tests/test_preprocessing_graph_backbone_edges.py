from __future__ import annotations

from mania.constants import EDGE_TYPE_PRIORITY
from mania.preprocessing import (
    BACKBONE_MAX_CA_DIST_A,
    PreprocessingCaCoordinate,
    PreprocessingConditionContactsResult,
    PreprocessingContactDetectionOptions,
    PreprocessingContactFrameResult,
    PreprocessingContactPairResult,
    PreprocessingGraphEdgeMappingRecord,
    PreprocessingManifestContactsResult,
    build_preprocessing_graph_export_mapping,
)


def ca_coordinate(
    residue_index: int,
    x_ca: float,
    *,
    segid: str | None = "A",
) -> PreprocessingCaCoordinate:
    return PreprocessingCaCoordinate(
        residue_index=residue_index,
        residue_id=residue_index + 1,
        resname="ALA",
        segid=segid,
        x_ca=x_ca,
        y_ca=0.0,
        z_ca=0.0,
    )


def contact_pair(
    source_index: int = 0,
    target_index: int = 1,
    *,
    edge_type: str = "residue_contact",
) -> PreprocessingContactPairResult:
    return PreprocessingContactPairResult(
        source_residue_index=source_index,
        target_residue_index=target_index,
        source_residue_id=source_index + 1,
        target_residue_id=target_index + 1,
        source_resname="ALA",
        target_resname="ALA",
        source_segid="A",
        target_segid="A",
        minimum_distance=3.0,
        edge_type=edge_type,
    )


def condition_result(
    coordinates: tuple[PreprocessingCaCoordinate, ...],
    *,
    condition_name: str = "normal",
    contacts: tuple[PreprocessingContactPairResult, ...] = (),
) -> PreprocessingConditionContactsResult:
    return PreprocessingConditionContactsResult(
        condition_name=condition_name,
        options=PreprocessingContactDetectionOptions(
            contact_selection="protein"
        ),
        representative_ca_coordinates=coordinates,
        frame_results=(
            PreprocessingContactFrameResult(
                condition_name=condition_name,
                frame_index=0,
                contacts=contacts,
            ),
        ),
        status="computed",
    )


def test_five_sequential_residues_create_four_backbone_edges() -> None:
    result = build_preprocessing_graph_export_mapping(
        condition_result(
            tuple(ca_coordinate(index, index * 3.8) for index in range(5))
        )
    )

    assert result.passed is True
    assert result.node_count == 5
    assert result.edge_count == 4
    assert all(edge.edge_kind == "backbone" for edge in result.edges)
    assert all(edge.all_edge_types == ("backbone",) for edge in result.edges)
    assert all(edge.n_edge_types == 1 for edge in result.edges)
    assert all(edge.contact_frequency is None for edge in result.edges)


def test_backbone_pair_over_cutoff_is_not_created() -> None:
    result = build_preprocessing_graph_export_mapping(
        condition_result(
            (
                ca_coordinate(0, 0.0),
                ca_coordinate(1, BACKBONE_MAX_CA_DIST_A + 0.1),
            )
        )
    )

    assert result.edges == ()


def test_backbone_pair_at_cutoff_is_created() -> None:
    result = build_preprocessing_graph_export_mapping(
        condition_result(
            (
                ca_coordinate(0, 0.0),
                ca_coordinate(1, BACKBONE_MAX_CA_DIST_A),
            )
        )
    )

    assert result.passed is True
    assert result.edge_count == 1
    assert result.edges[0].edge_kind == "backbone"


def test_close_non_sequential_residues_do_not_create_backbone_edge() -> None:
    result = build_preprocessing_graph_export_mapping(
        condition_result((ca_coordinate(0, 0.0), ca_coordinate(2, 3.8)))
    )

    assert result.edges == ()


def test_sequential_residues_in_different_chains_do_not_create_edge() -> None:
    result = build_preprocessing_graph_export_mapping(
        condition_result(
            (
                ca_coordinate(0, 0.0, segid="A"),
                ca_coordinate(1, 3.8, segid="B"),
            )
        )
    )

    assert result.edges == ()


def test_backbone_edges_remain_condition_specific() -> None:
    result = build_preprocessing_graph_export_mapping(
        PreprocessingManifestContactsResult(
            condition_results=(
                condition_result(
                    (ca_coordinate(0, 0.0), ca_coordinate(1, 3.8)),
                    condition_name="normal",
                ),
                condition_result(
                    (ca_coordinate(0, 10.0), ca_coordinate(1, 13.8)),
                    condition_name="tumor",
                ),
            )
        )
    )

    assert result.passed is True
    assert result.edge_count == 2
    assert {edge.condition_name for edge in result.edges} == {"normal", "tumor"}
    assert result.backbone_edge_counts == {"normal": 1, "tumor": 1}
    assert result.to_dict()["backbone_edge_counts"] == {
        "normal": 1,
        "tumor": 1,
    }
    assert all(
        edge.source_node_id.startswith(f"{edge.condition_name}|")
        and edge.target_node_id.startswith(f"{edge.condition_name}|")
        for edge in result.edges
    )


def test_backbone_overlap_preserves_contact_metrics() -> None:
    result = build_preprocessing_graph_export_mapping(
        condition_result(
            (ca_coordinate(0, 0.0), ca_coordinate(1, 3.8)),
            contacts=(contact_pair(),),
        )
    )

    assert result.passed is True
    assert result.edge_count == 1
    edge = result.edges[0]
    assert edge.edge_kind == "backbone"
    assert edge.all_edge_types == ("backbone", "residue_contact")
    assert edge.n_edge_types == 2
    assert edge.contact_frame_count == 1
    assert edge.total_frame_count == 1
    assert edge.contact_frequency == 1.0
    assert edge.minimum_distance == 3.0
    assert edge.mean_minimum_distance == 3.0


def test_backbone_has_highest_edge_type_priority() -> None:
    assert EDGE_TYPE_PRIORITY == (
        "backbone",
        "hbond",
        "disulfide",
        "salt_bridge",
        "ionic",
        "cation_pi",
        "aromatic_pi",
        "hydrophobic",
        "vdw",
    )

    for lower_priority_type in ("vdw", "hydrophobic"):
        edge = PreprocessingGraphEdgeMappingRecord(
            edge_id=f"backbone-{lower_priority_type}",
            source_node_id="n1",
            target_node_id="n2",
            condition_name="normal",
            edge_kind=lower_priority_type,
            all_edge_types=(lower_priority_type, "backbone"),
        )
        assert edge.edge_kind == "backbone"
        assert edge.all_edge_types == ("backbone", lower_priority_type)
        assert edge.n_edge_types == 2


def test_pi_edge_types_follow_existing_graph_priority() -> None:
    aromatic = PreprocessingGraphEdgeMappingRecord(
        edge_id="aromatic-vdw",
        source_node_id="n1",
        target_node_id="n2",
        condition_name="normal",
        edge_kind="vdw",
        all_edge_types=("vdw", "aromatic_pi"),
    )
    cation = PreprocessingGraphEdgeMappingRecord(
        edge_id="cation-hydrophobic",
        source_node_id="n1",
        target_node_id="n2",
        condition_name="normal",
        edge_kind="hydrophobic",
        all_edge_types=("hydrophobic", "cation_pi"),
    )

    assert aromatic.edge_kind == "aromatic_pi"
    assert aromatic.all_edge_types == ("aromatic_pi", "vdw")
    assert aromatic.n_edge_types == 2
    assert cation.edge_kind == "cation_pi"
    assert cation.all_edge_types == ("cation_pi", "hydrophobic")
    assert cation.n_edge_types == 2


def test_graph_mapping_merges_typed_contacts_and_preserves_backbone_priority() -> None:
    result = build_preprocessing_graph_export_mapping(
        condition_result(
            (ca_coordinate(0, 0.0), ca_coordinate(1, 3.8)),
            contacts=(
                contact_pair(edge_type="aromatic_pi"),
                contact_pair(edge_type="cation_pi"),
            ),
        )
    )

    assert result.passed
    assert result.edge_count == 1
    edge = result.edges[0]
    assert edge.edge_kind == "backbone"
    assert edge.all_edge_types == (
        "backbone",
        "cation_pi",
        "aromatic_pi",
    )
    assert edge.n_edge_types == 3


def test_notebook_compact_edge_type_aliases_normalize_to_backend_names() -> None:
    edge = PreprocessingGraphEdgeMappingRecord(
        edge_id="aliases",
        source_node_id="n1",
        target_node_id="n2",
        condition_name="normal",
        edge_kind="saltbridge",
        all_edge_types=("aromaticpi", "cationpi", "saltbridge"),
    )

    assert edge.edge_kind == "salt_bridge"
    assert edge.all_edge_types == (
        "salt_bridge",
        "cation_pi",
        "aromatic_pi",
    )
    assert edge.n_edge_types == 3
