"""Stage 30.C synthetic explicit identities and accepted evidence preservation."""

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, asdict, fields, replace

import pytest

from mania import canonical_window_tables as model
from mania.canonical_reference_io import load_default_napi2b_canonical_reference
from mania.canonical_residue_mapping import (
    CanonicalResidueMappingRecord,
    CanonicalResidueMappingTable,
)
from mania.preprocessing.protein_edge_window_table import (
    DatasetProteinEdgeWindowRow,
    DatasetProteinEdgeWindowTable,
)
from mania.preprocessing.specialized_contact_window_tables import (
    ProteinGlycanWindowRow,
    ProteinGlycanWindowTable,
    ProteinLipidWindowRow,
    ProteinLipidWindowTable,
)

KINDS = ("edge", "lipid", "glycan")
COMMON = dict(
    dataset_id="synthetic",
    system_id="variant",
    trajectory_id="trajectory",
    variant_id="T330M",
    engine="gromacs",
    condition="NORM",
    replica_id="1",
    disulfide_state=None,
    window_id="window_0001",
    window_index=0,
    requested_window_start_ns=5.0,
    requested_window_end_ns=5.25,
    right_endpoint_inclusive=False,
    effective_window_start_ns=5.0,
    effective_window_end_ns=5.2,
    requested_sample_count=5,
    resolved_frame_count=4,
    missing_sample_count=1,
    coverage_fraction=0.8,
)
METRICS = dict(
    n_contact_frames=2,
    occupancy=0.5,
    n_contact_episodes=1,
    mean_episode_length_ns=0.05,
    max_episode_length_ns=0.05,
)
SOURCE_TYPES = {
    "edge": DatasetProteinEdgeWindowTable,
    "lipid": ProteinLipidWindowTable,
    "glycan": ProteinGlycanWindowTable,
}


def source_row(kind, **changes):
    values = {**COMMON, **METRICS}
    if kind == "edge":
        values.update(
            source_residue_index=10,
            source_chain_id="A",
            source_resid="330",
            source_resname="MET",
            target_residue_index=20,
            target_chain_id="A",
            target_resid="311",
            target_resname="GLN",
            edge_type="contact",
            edge_weight=0.5,
        )
        row_type = DatasetProteinEdgeWindowRow
    else:
        values.update(
            protein_residue_index=10,
            protein_chain_id="A",
            protein_resid="330",
            protein_resname="MET",
            distance_mean_A=3.5,
            distance_min_A=3.0,
        )
        values.update(
            {
                f"{kind}_partner_id": f"{kind}:source:40",
                f"{kind}_partner_name": "synthetic-partner",
                f"{kind}_component_residue_indexes": (40, 41),
            }
        )
        row_type = ProteinLipidWindowRow if kind == "lipid" else ProteinGlycanWindowRow
        if kind == "glycan":
            values.update(
                carrier_residue_index=9,
                first_sugar_residue_index=40,
                linkage_evidence="external_metadata",
                carrier_link_atom_index=None,
                first_sugar_link_atom_index=None,
            )
    return row_type(**{**values, **changes})


def mapped(resid="330", resname="MET", number=330, *, engine="gromacs", chain="A"):
    ref = load_default_napi2b_canonical_reference()
    return CanonicalResidueMappingRecord(
        engine,
        chain,
        resid,
        resname,
        number,
        ref.residue_at(number).canonical_resname,
        "mapped",
    )


def mapping_table(records=None):
    if records is None:
        records = (mapped(), mapped("311", "GLN", 312))
    return CanonicalResidueMappingTable(
        tuple(
            sorted(
                records,
                key=lambda r: (
                    r.source_engine,
                    r.source_chain_id or "",
                    r.source_resid,
                    r.source_resname,
                ),
            )
        )
    )


def binding(table=None, **changes):
    values = {
        name: COMMON[name]
        for name in (
            "dataset_id",
            "system_id",
            "trajectory_id",
            "replica_id",
        )
    }
    return model.DatasetCanonicalResidueMappingBinding(
        **{**values, **changes},
        mapping_table=mapping_table() if table is None else table,
    )


def bindings(table=None, **changes):
    return model.DatasetCanonicalResidueMappingBindings((binding(table, **changes),))


def build(kind, rows=None, assigned=None):
    if rows is None:
        rows = (source_row(kind),)
    return getattr(model, f"build_canonical_protein_{kind}_window_table")(
        SOURCE_TYPES[kind](rows),
        mapping_bindings=bindings() if assigned is None else assigned,
    )


def test_binding_contract_exact_types_keys_order_and_lookup():
    first = binding()
    second = binding(replica_id="2")
    collection = model.DatasetCanonicalResidueMappingBindings((first, second))
    assert tuple(f.name for f in fields(first)) == (
        "dataset_id",
        "system_id",
        "trajectory_id",
        "replica_id",
        "mapping_table",
    )
    assert tuple(f.name for f in fields(collection)) == ("bindings",)
    assert collection.lookup(first.replica_key) is first.mapping_table
    assert collection.lookup(second.replica_key) is second.mapping_table
    for bad_key in (
        "NORM",
        ("NORM",),
        (*first.replica_key[:3], "absent"),
        (*first.replica_key[:3], ""),
        list(first.replica_key),
    ):
        with pytest.raises(model.CanonicalWindowTableError):
            collection.lookup(bad_key)
    for bad in ((first, first), (second, first), [first], (object(),)):
        with pytest.raises(model.CanonicalWindowTableError):
            model.DatasetCanonicalResidueMappingBindings(bad)
    for name in ("dataset_id", "system_id", "trajectory_id", "replica_id"):
        for bad in ("", " ", 1, None):
            with pytest.raises(model.CanonicalWindowTableError):
                replace(first, **{name: bad})
    with pytest.raises(model.CanonicalWindowTableError):
        replace(first, mapping_table=object())
    with pytest.raises(FrozenInstanceError):
        first.replica_id = "other"
    with pytest.raises(FrozenInstanceError):
        collection.bindings = ()


def test_bindings_validate_reference_and_reject_mutated_mapping():
    wrong = mapping_table((replace(mapped(), canonical_resname="MET"),))
    with pytest.raises(model.CanonicalWindowTableError, match="pinned reference"):
        bindings(wrong)
    for field, value in (
        ("canonical_reference_id", "wrong"),
        ("canonical_reference_sequence_sha256", "0" * 64),
        ("mappings", [mapped()]),
    ):
        table = mapping_table()
        object.__setattr__(table, field, value)
        with pytest.raises(model.CanonicalWindowTableError):
            bindings(table)
    for field, value in (
        ("canonical_resname", "MET"),
        ("mapping_status", "bogus"),
        ("canonical_residue_number", True),
    ):
        assigned = bindings()
        object.__setattr__(
            assigned.bindings[0].mapping_table.mappings[-1], field, value
        )
        with pytest.raises(model.CanonicalWindowTableError):
            build("lipid", assigned=assigned)


@pytest.mark.parametrize("kind", KINDS)
def test_models_preserve_all_evidence_without_input_mutation(kind):
    source = SOURCE_TYPES[kind]((source_row(kind),))
    assigned = bindings()
    before = json.dumps([source.to_dict(), asdict(assigned)], sort_keys=True)
    result = getattr(model, f"build_canonical_protein_{kind}_window_table")(
        source,
        mapping_bindings=assigned,
    )
    row = result.rows[0]
    for name in (*COMMON, *METRICS):
        assert getattr(row, name) == getattr(source.rows[0], name)
    if kind == "edge":
        assert row.edge_weight == source.rows[0].edge_weight
        assert row.row_identity == (
            *row.replica_key,
            "window_0001",
            312,
            330,
            "contact",
        )
        for name in ("residue_index", "chain_id", "resid", "resname"):
            assert getattr(row, f"source_{name}") == getattr(
                source.rows[0], f"target_{name}"
            )
            assert getattr(row, f"target_{name}") == getattr(
                source.rows[0], f"source_{name}"
            )
        assert (
            row.target_resid,
            row.target_resname,
            row.target_canonical_residue_number,
            row.target_canonical_resname,
        ) == ("330", "MET", 330, "THR")
        assert (row.source_resid, row.source_canonical_residue_number) == ("311", 312)
    else:
        for name, value in source.rows[0].to_dict().items():
            assert row.to_dict()[name] == value
        assert (
            row.protein_resid,
            row.protein_resname,
            row.canonical_residue_number,
            row.canonical_resname,
        ) == ("330", "MET", 330, "THR")
        assert row.row_identity == (
            *row.replica_key,
            "window_0001",
            330,
            getattr(row, f"{kind}_partner_id"),
        )
        assert "edge_weight" not in row.to_dict()
    assert before == json.dumps([source.to_dict(), asdict(assigned)], sort_keys=True)
    assert result.row_count == 1
    assert result.canonical_reference_id == "uniprotkb:O95436-1:sequence-v3"
    assert result.canonical_reference_sequence_sha256 == (
        "33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9"
    )
    assert result.schema_version == getattr(
        model, f"CANONICAL_PROTEIN_{kind.upper()}_WINDOW_TABLE_SCHEMA_VERSION"
    )
    assert result.kind == getattr(
        model, f"CANONICAL_PROTEIN_{kind.upper()}_WINDOW_TABLE_KIND"
    )
    assert tuple(result.to_dict()) == (
        "schema_version",
        "kind",
        "canonical_reference_id",
        "canonical_reference_sequence_sha256",
        "row_count",
        "rows",
    )
    assert json.dumps(result.to_dict(), allow_nan=False) == json.dumps(
        build(kind).to_dict(), allow_nan=False
    )
    for value, field in ((row, "condition"), (result, "rows")):
        with pytest.raises(FrozenInstanceError):
            setattr(value, field, None)
    assert (
        not {
            "mapping_status",
            "is_ecd",
            "is_mx35_region",
            "glycosylation_site",
            "variant_site",
            "disulfide_site",
            "mutation_flags",
            "canonical_partner_id",
        }
        & row.to_dict().keys()
    )
    if kind != "edge":
        independent = row.to_dict()
        independent[f"{kind}_component_residue_indexes"].append(99)
        assert getattr(row, f"{kind}_component_residue_indexes") == (40, 41)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "change", ["missing", "unmapped", "resname", "engine", "chain", "none_chain"]
)
def test_exact_source_mapping_failures(kind, change):
    records = list(mapping_table().mappings)
    if change == "missing":
        records.pop()
    elif change == "unmapped":
        records[-1] = replace(
            records[-1],
            mapping_status="unmapped",
            canonical_residue_number=None,
            canonical_resname=None,
        )
    else:
        field, value = {
            "resname": ("source_resname", "THR"),
            "engine": ("source_engine", "namd"),
            "chain": ("source_chain_id", "B"),
            "none_chain": ("source_chain_id", None),
        }[change]
        records[-1] = replace(records[-1], **{field: value})
    with pytest.raises(model.CanonicalWindowTableError, match="explicit"):
        build(kind, assigned=bindings(mapping_table(records)))


@pytest.mark.parametrize("kind", KINDS)
def test_missing_resid_and_binding_fail_no_index_fallback(kind):
    for field in (
        ("source_resid", "target_resid") if kind == "edge" else ("protein_resid",)
    ):
        with pytest.raises(model.CanonicalWindowTableError, match="resid"):
            build(kind, (source_row(kind, **{field: None}),))
    with pytest.raises(model.CanonicalWindowTableError, match="binding"):
        build(kind, assigned=model.DatasetCanonicalResidueMappingBindings(()))
    with pytest.raises(model.CanonicalWindowTableError, match="binding"):
        build(kind, assigned=bindings(trajectory_id="another"))


@pytest.mark.parametrize("kind", KINDS)
def test_same_condition_replica_bindings_and_canonical_sort(kind):
    first, second = source_row(kind), source_row(kind, replica_id="2")
    alternate = mapping_table((mapped(number=400), mapped("311", "GLN", 300)))
    assigned = model.DatasetCanonicalResidueMappingBindings(
        (
            binding(),
            binding(alternate, replica_id="2"),
            binding(replica_id="extra"),
        )
    )
    result = build(kind, (first, second), assigned)
    assert [row.condition for row in result.rows] == ["NORM", "NORM"]
    field = (
        "target_canonical_residue_number"
        if kind == "edge"
        else "canonical_residue_number"
    )
    assert [getattr(row, field) for row in result.rows] == [330, 400]
    if kind == "edge":
        assert result.rows[1].source_canonical_residue_number == 300
        assert result.rows[1].source_residue_index == 20
        assert result.rows[1].target_residue_index == 10


@pytest.mark.parametrize("kind", KINDS)
def test_none_condition_engine_and_chain_match_exactly(kind):
    changes = dict(engine="namd", condition=None)
    for prefix in ("source_", "target_") if kind == "edge" else ("protein_",):
        changes[f"{prefix}chain_id"] = None
    records = tuple(
        replace(r, source_engine="namd", source_chain_id=None)
        for r in mapping_table().mappings
    )
    row = build(
        kind, (source_row(kind, **changes),), bindings(mapping_table(records))
    ).rows[0]
    assert row.condition is None and row.engine == "namd"


def test_self_loop_fails_and_unequal_canonical_orientation_succeeds():
    assigned = bindings(mapping_table((mapped(), mapped("311", "GLN", 330))))
    with pytest.raises(model.CanonicalWindowTableError, match="self-loops"):
        build("edge", assigned=assigned)
    assigned = bindings(mapping_table((mapped(number=300), mapped("311", "GLN", 400))))
    row = build("edge", assigned=assigned).rows[0]
    assert (row.source_residue_index, row.target_residue_index) == (10, 20)
    assert (
        row.source_canonical_residue_number,
        row.target_canonical_residue_number,
    ) == (300, 400)


@pytest.mark.parametrize("kind", KINDS)
def test_canonical_collision_never_merges(kind):
    first = source_row(kind)
    changes = (
        dict(source_residue_index=11, source_resid="different")
        if kind == "edge"
        else dict(protein_residue_index=11, protein_resid="different")
    )
    second = replace(first, **changes)
    assigned = bindings(mapping_table((*mapping_table().mappings, mapped("different"))))
    with pytest.raises(model.CanonicalWindowTableError, match="collision"):
        build(kind, (first, second), assigned)
    # Condition is evidence, never part of canonical uniqueness.
    canonical = build(kind)
    with pytest.raises(model.CanonicalWindowTableError, match="collision"):
        type(canonical)(
            (canonical.rows[0], replace(canonical.rows[0], condition="other"))
        )


@pytest.mark.parametrize("kind", KINDS)
def test_empty_tables_extra_bindings_and_exact_type_boundaries(kind):
    empty = build(kind, (), model.DatasetCanonicalResidueMappingBindings(()))
    assert empty.row_count == 0 and empty.to_dict()["rows"] == []
    assert build(kind, (), bindings()).to_dict() == empty.to_dict()
    function = getattr(model, f"build_canonical_protein_{kind}_window_table")
    with pytest.raises(model.CanonicalWindowTableError):
        function(object(), mapping_bindings=bindings())
    with pytest.raises(model.CanonicalWindowTableError):
        function(SOURCE_TYPES[kind](()), mapping_bindings=())
    for bad in ([], (object(),)):
        with pytest.raises(model.CanonicalWindowTableError):
            type(empty)(bad)


@pytest.mark.parametrize("kind", KINDS)
def test_direct_models_revalidate_canonical_reference_metrics_order_and_mutations(kind):
    table = build(kind)
    row = table.rows[0]
    prefix = "target_" if kind == "edge" else ""
    for name, bad in (
        (f"{prefix}canonical_resname", "MET"),
        (f"{prefix}canonical_residue_number", True),
        (f"{prefix}canonical_residue_number", 691),
        ("occupancy", 0.7),
        ("coverage_fraction", 0.7),
        ("n_contact_frames", True),
        ("mean_episode_length_ns", float("nan")),
    ):
        with pytest.raises(model.CanonicalWindowTableError):
            replace(row, **{name: bad})
    with pytest.raises(model.CanonicalWindowTableError, match="order"):
        type(table)((replace(row, replica_id="2"), row))
    object.__setattr__(row, f"{prefix}canonical_resname", "MET")
    with pytest.raises(model.CanonicalWindowTableError, match="pinned reference"):
        type(table)((row,))


def test_exact_lookup_return_invariant(monkeypatch):
    monkeypatch.setattr(
        model, "require_mapped_source_residue", lambda *a, **k: mapped("wrong")
    )
    with pytest.raises(
        model.CanonicalWindowTableError, match="source key must be exact"
    ):
        build("lipid")


def test_numeric_equality_has_no_authority_for_specialized_source():
    row = source_row("lipid", protein_resid="311", protein_resname="GLN")
    result = build("lipid", (row,)).rows[0]
    assert (result.protein_resid, result.canonical_residue_number) == ("311", 312)
    with pytest.raises(model.CanonicalWindowTableError, match="No explicit"):
        build("lipid", (row,), bindings(mapping_table((mapped(),))))


def test_new_production_modules_have_no_network_imports():
    from mania import canonical_window_tables_io

    for module in (model, canonical_window_tables_io):
        tree = ast.parse(inspect.getsource(module))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        assert not any(
            name.startswith(
                ("requests", "urllib", "http.client", "socket", "subprocess")
            )
            for name in imports
        )


@pytest.mark.parametrize("kind", KINDS)
def test_builder_sorts_by_canonical_position_after_mapping(kind):
    first = source_row(kind)
    changes = (
        dict(source_residue_index=11, source_resid="other")
        if kind == "edge"
        else dict(protein_residue_index=11, protein_resid="other")
    )
    second = replace(first, **changes)
    assigned = bindings(
        mapping_table((*mapping_table().mappings, mapped("other", number=234)))
    )
    result = build(kind, (first, second), assigned)
    assert (
        result.rows[0].source_resid == "other"
        if kind == "edge"
        else (result.rows[0].protein_resid == "other")
    )
    if kind == "edge":
        assert result.rows[0].row_order == (
            *result.rows[0].replica_key,
            0,
            "contact",
            234,
            312,
        )
    else:
        assert result.rows[0].row_order == (
            *result.rows[0].replica_key,
            0,
            234,
            getattr(first, f"{kind}_partner_id"),
        )


@pytest.mark.parametrize("kind", ("lipid", "glycan"))
def test_same_canonical_residue_distinct_partners_remain_separate(kind):
    first = source_row(kind)
    second = replace(first, **{f"{kind}_partner_id": "other-partner"})
    result = build(kind, (first, second))
    assert result.row_count == 2
    assert {row.canonical_residue_number for row in result.rows} == {330}
    assert {getattr(row, f"{kind}_partner_id") for row in result.rows} == {
        getattr(first, f"{kind}_partner_id"),
        "other-partner",
    }
