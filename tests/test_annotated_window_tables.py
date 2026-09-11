"""All canonical evidence survives system-bound enrichment unchanged."""

from dataclasses import fields, replace

import pytest
from test_biological_annotations import glyco, metadata, variant
from test_canonical_window_tables import KINDS, build

from mania import annotated_window_tables as m
from mania.biological_annotations import BiologicalAnnotationError


def assigned(data=None):
    data = metadata() if data is None else data
    return m.DatasetBiologicalAnnotationBindings(
        (m.DatasetBiologicalAnnotationBinding(data.dataset_id, data.system_id, data),)
    )


def annotate(kind, canonical=None, bindings=None):
    return getattr(m, f"build_annotated_canonical_protein_{kind}_window_table")(
        build(kind) if canonical is None else canonical,
        annotation_bindings=assigned() if bindings is None else bindings,
    )


@pytest.mark.parametrize("kind", KINDS)
def test_exact_fields_preservation_and_explicit_flags(kind):
    canonical = build(kind)
    data = metadata(glycosylation_sites=(glyco(),), cysteine_variant_sites=(variant(),))
    table = annotate(kind, canonical, assigned(data))
    row, original = table.rows[0], canonical.rows[0]
    original_fields = tuple(f.name for f in fields(original))
    prefixes = ("source_", "target_") if kind == "edge" else ("",)
    assert tuple(f.name for f in fields(row)) == original_fields + tuple(
        prefix + name for prefix in prefixes for name in m.BIOLOGICAL_ANNOTATION_COLUMNS
    )
    for name in original_fields:
        assert getattr(row, name) == getattr(original, name)
    assert row.row_identity == original.row_identity
    assert row.row_order == original.row_order
    prefix = "target_" if kind == "edge" else ""
    assert getattr(row, prefix + "canonical_resname") == "THR"
    assert (
        getattr(row, "target_resname" if kind == "edge" else "protein_resname") == "MET"
    )
    for name in (
        "is_ecd",
        "is_mx35_region",
        "is_glycosylation_site",
        "is_cysteine_variant_site",
    ):
        assert getattr(row, prefix + name) is True
    assert getattr(row, prefix + "is_disulfide_variant_site") is False
    if kind == "edge":
        assert row.source_canonical_residue_number == 312  # explicit source 311 -> 312
        assert row.source_is_ecd and row.source_is_mx35_region
        assert not row.source_is_glycosylation_site


@pytest.mark.parametrize("kind", KINDS)
def test_no_automatic_t330m_variant_or_glycan_partner_inference(kind):
    row = annotate(kind).rows[0]
    prefixes = ("source_", "target_") if kind == "edge" else ("",)
    for prefix in prefixes:
        assert getattr(row, prefix + "is_ecd")
        assert getattr(row, prefix + "is_mx35_region")
        assert not getattr(row, prefix + "is_glycosylation_site")
        assert not getattr(row, prefix + "is_cysteine_variant_site")
        assert not getattr(row, prefix + "is_disulfide_variant_site")
        for name in (
            "glycan_name",
            "glycosylation_source",
            "glycosylation_verifier",
            "glycosylation_present_in_topology",
        ):
            assert getattr(row, prefix + name) is None


@pytest.mark.parametrize("kind", KINDS)
def test_missing_binding_empty_tables_and_identity_collision(kind):
    empty = m.DatasetBiologicalAnnotationBindings(())
    with pytest.raises(BiologicalAnnotationError, match="No complete"):
        annotate(kind, bindings=empty)
    canonical = build(kind)
    assert annotate(kind, replace(canonical, rows=()), empty).row_count == 0
    row = annotate(kind).rows[0]
    with pytest.raises(ValueError, match="collision"):
        replace(annotate(kind), rows=(row, row))
    prefix = "source_" if kind == "edge" else ""
    with pytest.raises(BiologicalAnnotationError):
        replace(row, **{prefix + "is_ecd": False})
    with pytest.raises(ValueError):
        replace(row, occupancy=2.0)


@pytest.mark.parametrize("kind", KINDS)
def test_same_condition_different_systems_replica_consistency_and_none(kind):
    canonical = build(kind)
    row = canonical.rows[0]
    rows = (
        row,
        replace(row, replica_id="2"),
        replace(row, system_id="zzz", condition=None, engine="namd"),
    )
    canonical = replace(canonical, rows=rows)
    first = metadata(glycosylation_sites=(glyco(),))
    second = metadata(system_id="zzz")
    collection = m.DatasetBiologicalAnnotationBindings(
        (
            m.DatasetBiologicalAnnotationBinding(
                first.dataset_id, first.system_id, first
            ),
            m.DatasetBiologicalAnnotationBinding(
                second.dataset_id, second.system_id, second
            ),
        )
    )
    enriched = annotate(kind, canonical, collection)
    prefix = "target_" if kind == "edge" else ""
    assert getattr(enriched.rows[0], prefix + "is_glycosylation_site")
    assert getattr(enriched.rows[1], prefix + "is_glycosylation_site")
    assert not getattr(enriched.rows[2], prefix + "is_glycosylation_site")
    assert enriched.rows[2].condition is None
    # Equal scientific condition labels still never collapse systems.
    canonical = replace(canonical, rows=(row, replace(row, system_id="zzz")))
    enriched = annotate(kind, canonical, collection)
    assert enriched.rows[0].condition == enriched.rows[1].condition == "NORM"
    assert getattr(enriched.rows[0], prefix + "is_glycosylation_site")
    assert not getattr(enriched.rows[1], prefix + "is_glycosylation_site")


def test_binding_corruption_and_exact_system_key():
    binding = assigned().bindings[0]
    for changes in ({"dataset_id": "other"}, {"annotations": None}, {"system_id": ""}):
        with pytest.raises(BiologicalAnnotationError):
            replace(binding, **changes)
    for bindings in ((binding, binding), [binding], (object(),)):
        with pytest.raises(BiologicalAnnotationError):
            m.DatasetBiologicalAnnotationBindings(bindings)
    for key in ("NORM", ("NORM",), ("synthetic", "other"), (True, "variant")):
        with pytest.raises(BiologicalAnnotationError):
            assigned().lookup(key)


@pytest.mark.parametrize("kind", KINDS)
def test_region_flags_use_canonical_number_when_source_is_outside_regions(kind):
    from test_canonical_window_tables import bindings, mapped, mapping_table, source_row

    changes = {"source_resid" if kind == "edge" else "protein_resid": "1"}
    source = source_row(kind, **changes)
    mapping = mapping_table((mapped("1", "MET", 330), mapped("311", "GLN", 312)))
    canonical = build(kind, rows=(source,), assigned=bindings(mapping))
    annotated = annotate(kind, canonical).rows[0]
    prefix = "target_" if kind == "edge" else ""
    assert (
        getattr(annotated, "target_resid" if kind == "edge" else "protein_resid") == "1"
    )
    assert getattr(annotated, prefix + "canonical_residue_number") == 330
    assert getattr(annotated, prefix + "is_ecd")
    assert getattr(annotated, prefix + "is_mx35_region")


def test_annotation_column_order_is_frozen():
    assert m.BIOLOGICAL_ANNOTATION_COLUMNS == (
        "is_ecd",
        "is_mx35_region",
        "is_glycosylation_site",
        "glycosylation_present_in_topology",
        "glycan_name",
        "glycosylation_source",
        "glycosylation_verifier",
        "is_disulfide_variant_site",
        "is_cysteine_variant_site",
    )
