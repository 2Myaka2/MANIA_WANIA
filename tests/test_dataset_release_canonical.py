"""Full pinned reference and complete-system annotation publication."""

import copy
from dataclasses import replace

import pytest
from test_dataset_release_metadata import complete_annotations

from mania.canonical_reference_io import load_default_napi2b_canonical_reference
from mania.dataset_release_canonical import (
    build_dataset_release_nodes,
    build_dataset_release_residue_annotations,
)
from mania.dataset_release_csv import read_publication_csv, write_publication_csv


def test_all_nodes_match_pinned_reference_and_t330m_cannot_change_them():
    table = build_dataset_release_nodes()
    reference = load_default_napi2b_canonical_reference()
    assert table.row_count == 690
    for row, residue in zip(table.records(), reference.residues(), strict=True):
        assert row["canonical_residue_number"] == residue.canonical_residue_number
        assert row["canonical_resname"] == residue.canonical_resname
        assert row["canonical_reference_id"] == reference.reference_id
        assert row["canonical_reference_sequence_sha256"] == reference.sequence_sha256
    assert table.records()[329]["canonical_resname"] == "THR"
    assert all("source" not in c.name for c in table.spec.columns)


def test_complete_annotations_match_accepted_builder_and_preserve_variant_evidence(
    tmp_path,
):
    metadata = complete_annotations()
    table = build_dataset_release_residue_annotations(
        (metadata,),
        annotation_publication_system_keys=((metadata.dataset_id, metadata.system_id),),
    )
    assert table.row_count == 690
    for row in table.records():
        accepted = metadata.annotation_for_residue(row["canonical_residue_number"])
        for name in accepted.__dataclass_fields__:
            assert row[name] == getattr(accepted, name)
        assert row["annotation_scope"] == "complete_for_system"
    by_number = {r["canonical_residue_number"]: r for r in table.records()}
    for number in (233, 234, 361, 362):
        assert by_number[number]["is_ecd"] == (number in (234, 361))
    for number in (310, 311, 341, 342):
        assert by_number[number]["is_mx35_region"] == (number in (311, 341))
    assert by_number[330]["canonical_resname"] == "THR"
    assert by_number[330]["is_ecd"] and by_number[330]["is_mx35_region"]
    for kind in ("disulfide", "cysteine"):
        assert by_number[330][f"is_{kind}_variant_site"]
        assert by_number[330][f"{kind}_variant_source"] == f"{kind} source"
        assert by_number[330][f"{kind}_variant_verifier"] == f"{kind} verifier"
        assert by_number[329][f"{kind}_variant_source"] is None
    assert by_number[300]["glycan_name"] == "synthetic glycan"
    assert by_number[300]["glycosylation_present_in_topology"] is True
    assert by_number[301]["glycosylation_present_in_topology"] is None
    path = write_publication_csv(table, tmp_path / table.relative_path)
    assert read_publication_csv(table.table_id, path) == table


def test_variant_flags_never_inferred_from_t330m_name_or_topology():
    metadata = replace(
        complete_annotations(), disulfide_variant_sites=(), cysteine_variant_sites=()
    )
    table = build_dataset_release_residue_annotations(
        (metadata,),
        annotation_publication_system_keys=((metadata.dataset_id, "T330M"),),
    )
    row = table.records()[329]
    assert row["canonical_resname"] == "THR"
    assert not row["is_disulfide_variant_site"]
    assert not row["is_cysteine_variant_site"]
    assert row["disulfide_variant_source"] is row["cysteine_variant_source"] is None


def test_selection_is_explicit_and_exactly_690_per_selected_system():
    first = complete_annotations()
    second = replace(first, system_id="another")
    assert (
        build_dataset_release_residue_annotations(
            (first, second),
            annotation_publication_system_keys=(),
        ).row_count
        == 0
    )
    table = build_dataset_release_residue_annotations(
        (second, first),
        annotation_publication_system_keys=(
            (first.dataset_id, "another"),
            (first.dataset_id, "T330M"),
        ),
    )
    assert table.row_count == 1380
    assert {r["system_id"] for r in table.records()} == {"another", "T330M"}


@pytest.mark.parametrize(
    "selected",
    [
        (("synthetic-33b", "missing"),),
        (("synthetic-33b", "T330M"),) * 2,
        (("T330M",),),
        (("synthetic-33b", None),),
    ],
)
def test_missing_or_malformed_annotation_selection_fails(selected):
    with pytest.raises(ValueError):
        build_dataset_release_residue_annotations(
            (complete_annotations(),), annotation_publication_system_keys=selected
        )


def test_absent_incomplete_or_duplicate_annotation_authority_fails():
    metadata = complete_annotations()
    selected = ((metadata.dataset_id, metadata.system_id),)
    with pytest.raises(ValueError, match="complete_for_system"):
        build_dataset_release_residue_annotations(
            (), annotation_publication_system_keys=selected
        )
    with pytest.raises(ValueError, match="Duplicate"):
        build_dataset_release_residue_annotations(
            (metadata, metadata), annotation_publication_system_keys=selected
        )
    incomplete = copy.deepcopy(metadata)
    object.__setattr__(incomplete, "annotation_scope", "partial")
    with pytest.raises(ValueError, match="complete_for_system"):
        build_dataset_release_residue_annotations(
            (incomplete,), annotation_publication_system_keys=selected
        )
