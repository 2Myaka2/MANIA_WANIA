"""Stage 30.B explicit namespaces, canonical authority, and no-inference proofs."""

import json
from dataclasses import FrozenInstanceError, fields, replace
from typing import get_args

import pytest

from mania import canonical_residue_mapping as model
from mania.canonical_reference import CanonicalProteinReference
from mania.canonical_reference_io import load_default_napi2b_canonical_reference
from mania.canonical_residue_mapping import (
    CanonicalResidueMappingError,
    CanonicalResidueMappingRecord,
    CanonicalResidueMappingTable,
    canonical_residue_for_mapping,
    find_source_residue_mapping,
    require_mapped_source_residue,
    require_source_residue_mapping,
    validate_canonical_residue_mapping_table,
)

ROW_FIELDS = (
    "source_engine",
    "source_chain_id",
    "source_resid",
    "source_resname",
    "canonical_residue_number",
    "canonical_resname",
    "mapping_status",
)


@pytest.fixture
def reference():
    return load_default_napi2b_canonical_reference()


@pytest.fixture
def mapped():
    return CanonicalResidueMappingRecord(
        "gromacs", "A", "330", "MET", 330, "THR", "mapped"
    )


@pytest.fixture
def unmapped():
    return CanonicalResidueMappingRecord(
        "namd", None, "X42", "SER", None, None, "unmapped"
    )


def key_arguments(record):
    return {name: getattr(record, name) for name in ROW_FIELDS[:4]}


def test_constants_and_public_api(reference):
    expected = {
        "CANONICAL_RESIDUE_MAPPING_KIND": "mania_canonical_residue_mapping",
        "CANONICAL_RESIDUE_MAPPING_SCHEMA_VERSION": (
            "mania.canonical_residue_mapping.v0.1"
        ),
        "CANONICAL_RESIDUE_MAPPING_REFERENCE_ID": "uniprotkb:O95436-1:sequence-v3",
        "CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256": (
            "33ce6c59e28a7373fce51debe32cec8d891ef691c2e77a0655a74040da25eef9"
        ),
    }
    assert {name: getattr(model, name) for name in expected} == expected
    assert model.CANONICAL_RESIDUE_MAPPING_REFERENCE_ID == reference.reference_id
    assert model.CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256 == reference.sequence_sha256
    assert get_args(model.CanonicalResidueMappingStatus) == ("mapped", "unmapped")
    assert set(model.__all__) == set(expected) | {
        "CanonicalResidueMappingError",
        "CanonicalResidueMappingRecord",
        "CanonicalResidueMappingStatus",
        "CanonicalResidueMappingTable",
        "canonical_residue_for_mapping",
        "find_source_residue_mapping",
        "require_mapped_source_residue",
        "require_source_residue_mapping",
        "validate_canonical_residue_mapping_table",
    }
    assert issubclass(CanonicalResidueMappingError, ValueError)


def test_frozen_fields_source_key_and_deterministic_dictionary(mapped, unmapped):
    table = CanonicalResidueMappingTable((mapped, unmapped))
    assert tuple(f.name for f in fields(mapped)) == ROW_FIELDS
    assert tuple(f.name for f in fields(table) if f.init) == ("mappings",)
    assert tuple(f.name for f in fields(table) if not f.init) == (
        "schema_version",
        "kind",
        "canonical_reference_id",
        "canonical_reference_sequence_sha256",
    )
    for instance in (mapped, unmapped, table):
        for item in fields(instance):
            with pytest.raises(FrozenInstanceError):
                setattr(instance, item.name, None)
    for item in fields(table):
        if not item.init:
            with pytest.raises(TypeError):
                CanonicalResidueMappingTable((), **{item.name: item.default})
    assert mapped.source_key == ("gromacs", "A", "330", "MET")
    assert unmapped.source_key == ("namd", None, "X42", "SER")
    assert mapped.to_dict() == dict(
        zip(
            ROW_FIELDS,
            ("gromacs", "A", "330", "MET", 330, "THR", "mapped"),
            strict=True,
        )
    )
    assert tuple(mapped.to_dict()) == ROW_FIELDS
    assert unmapped.to_dict()["canonical_residue_number"] is None
    assert unmapped.to_dict()["canonical_resname"] is None
    def serialize(value):
        return json.dumps(value.to_dict(), allow_nan=False, separators=(",", ":"))

    before = serialize(table)
    external = table.to_dict()
    external["mappings"][0]["source_resid"] = "changed"
    external["mappings"].clear()
    assert serialize(table) == before == serialize(replace(table))


@pytest.mark.parametrize(
    "engine", ["GROMACS", "NAMD", "namdd", " gromacs", "", 1, None]
)
def test_strict_engine(mapped, engine):
    with pytest.raises(CanonicalResidueMappingError, match="source_engine"):
        replace(mapped, source_engine=engine)


@pytest.mark.parametrize("field", ["source_chain_id", "source_resid", "source_resname"])
@pytest.mark.parametrize("value", ["", " ", " A", "A ", 330, True, 1.5, [], {}])
def test_strict_source_text(mapped, field, value):
    with pytest.raises(CanonicalResidueMappingError, match=field):
        replace(mapped, **{field: value})


@pytest.mark.parametrize("field", ["source_resid", "source_resname"])
def test_required_source_text(mapped, field):
    with pytest.raises(CanonicalResidueMappingError, match=field):
        replace(mapped, **{field: None})


@pytest.mark.parametrize("resid", ["311", "330", "330A", "15:CA", "00330", "Ω42"])
def test_source_evidence_is_preserved(mapped, reference, resid):
    record = replace(
        mapped, source_chain_id=None, source_resid=resid, source_resname="mEt*"
    )
    table = CanonicalResidueMappingTable((record,))
    assert validate_canonical_residue_mapping_table(table, reference=reference) is table
    assert type(record.source_resid) is str
    assert record.source_resid == resid
    assert record.source_resname == "mEt*"
    assert record.source_chain_id is None
    assert replace(record, source_chain_id="a").source_chain_id == "a"


@pytest.mark.parametrize(
    "status", [None, 1, True, [], "Mapped", "inferred", "aligned", "auto"]
)
def test_mapping_status_is_explicit(mapped, status):
    with pytest.raises(CanonicalResidueMappingError, match="mapping_status"):
        replace(mapped, mapping_status=status)


@pytest.mark.parametrize("number", [None, True, False, 0, -1, 691, 330.0, "330", []])
def test_mapped_position_requirements(mapped, number):
    with pytest.raises(CanonicalResidueMappingError, match="integer in 1..690"):
        replace(mapped, canonical_residue_number=number)


@pytest.mark.parametrize(
    "name", [None, "", "Thr", "thr", "THR ", "T", "THRR", "ÅLA", 1]
)
def test_mapped_name_syntax(mapped, name):
    with pytest.raises(CanonicalResidueMappingError, match="canonical_resname"):
        replace(mapped, canonical_resname=name)


@pytest.mark.parametrize(
    "number,name",
    [
        (0, None),
        (-1, None),
        (False, None),
        (330, None),
        (None, "UNK"),
        (None, "NA"),
        (None, ""),
        (330, "THR"),
    ],
)
def test_unmapped_requires_both_null_fields(unmapped, number, name):
    with pytest.raises(CanonicalResidueMappingError, match="both be None"):
        replace(unmapped, canonical_residue_number=number, canonical_resname=name)


@pytest.mark.parametrize("number", [1, 690])
def test_valid_boundary_positions(mapped, reference, number):
    residue = reference.residue_at(number)
    record = replace(
        mapped,
        canonical_residue_number=number,
        canonical_resname=residue.canonical_resname,
    )
    table = CanonicalResidueMappingTable((record,))
    assert validate_canonical_residue_mapping_table(table, reference=reference) is table
    assert canonical_residue_for_mapping(record, reference) == residue


def test_exact_table_and_record_types(mapped, reference):
    class RecordSubclass(CanonicalResidueMappingRecord):
        pass

    class TableSubclass(CanonicalResidueMappingTable):
        pass

    for records in (
        [mapped],
        (mapped.to_dict(),),
        (RecordSubclass(**mapped.to_dict()),),
    ):
        with pytest.raises(CanonicalResidueMappingError, match="tuple of exact"):
            CanonicalResidueMappingTable(records)
    for table in (None, (), TableSubclass(())):
        with pytest.raises(CanonicalResidueMappingError, match="table must be exact"):
            validate_canonical_residue_mapping_table(table, reference=reference)
        with pytest.raises(CanonicalResidueMappingError, match="table must be exact"):
            find_source_residue_mapping(table, **key_arguments(mapped))
    with pytest.raises(CanonicalResidueMappingError, match="record must be exact"):
        canonical_residue_for_mapping(RecordSubclass(**mapped.to_dict()), reference)


def test_duplicate_source_keys_even_with_different_canonical_states(mapped):
    alternate = replace(
        mapped,
        canonical_residue_number=None,
        canonical_resname=None,
        mapping_status="unmapped",
    )
    for duplicate in (mapped, alternate):
        with pytest.raises(CanonicalResidueMappingError, match="Duplicate source key"):
            CanonicalResidueMappingTable((mapped, duplicate))


def test_exact_source_sort_with_none_lexical_resid_and_case(mapped):
    keys = (
        ("gromacs", None, "2", "MET"),
        ("gromacs", "A", "100", "MET"),
        ("gromacs", "A", "20", "MET"),
        ("gromacs", "A", "20", "met"),
        ("gromacs", "B", "1", "MET"),
        ("gromacs", "a", "1", "MET"),
        ("namd", None, "1", "MET"),
    )
    records = tuple(
        replace(mapped, **dict(zip(ROW_FIELDS[:4], key, strict=True))) for key in keys
    )
    assert (
        tuple(r.source_key for r in CanonicalResidueMappingTable(records).mappings)
        == keys
    )
    for index in range(len(records) - 1):
        swapped = list(records)
        swapped[index], swapped[index + 1] = swapped[index + 1], swapped[index]
        with pytest.raises(CanonicalResidueMappingError, match="ordered by exact"):
            CanonicalResidueMappingTable(tuple(swapped))


def test_duplicate_targets_across_engines_chains_and_resnames(mapped, reference):
    records = (
        mapped,
        replace(mapped, source_resname="THR"),
        replace(mapped, source_chain_id="B"),
        replace(mapped, source_engine="namd", source_resname="THR"),
    )
    table = CanonicalResidueMappingTable(records)
    assert validate_canonical_residue_mapping_table(table, reference=reference) is table
    for record in records:
        assert find_source_residue_mapping(table, **key_arguments(record)) is record
    # Identical resid/resname in different source chains stay distinct as well.
    chains = tuple(
        replace(mapped, source_chain_id=chain, source_resid="100", source_resname="ALA")
        for chain in ("A", "B")
    )
    assert len(CanonicalResidueMappingTable(chains).mappings) == 2


def test_sparse_and_empty_mapping_are_not_coverage_checks(mapped, reference):
    records = tuple(
        replace(
            mapped,
            source_resid=resid,
            canonical_residue_number=number,
            canonical_resname=reference.residue_at(number).canonical_resname,
        )
        for resid, number in (("1", 1), ("400A", 330), ("900", 690))
    )
    for table in (
        CanonicalResidueMappingTable(records),
        CanonicalResidueMappingTable(()),
    ):
        assert (
            validate_canonical_residue_mapping_table(table, reference=reference)
            is table
        )


def test_t330m_variant_preserves_source_and_validates_wt_canonical(mapped, reference):
    assert reference.residue_at(330).canonical_resname == "THR"
    table = CanonicalResidueMappingTable((mapped,))
    assert validate_canonical_residue_mapping_table(table, reference=reference) is table
    assert (mapped.source_resname, mapped.canonical_resname) == ("MET", "THR")
    wrong = replace(mapped, canonical_resname="MET")
    with pytest.raises(CanonicalResidueMappingError, match="position 330"):
        validate_canonical_residue_mapping_table(
            CanonicalResidueMappingTable((wrong,)), reference=reference
        )
    with pytest.raises(CanonicalResidueMappingError, match="position 330"):
        canonical_residue_for_mapping(wrong, reference)


@pytest.mark.parametrize("name", ["ALA", "UNK", "XYZ"])
def test_reference_checks_actual_name_beyond_model_syntax(mapped, reference, name):
    record = replace(mapped, canonical_resname=name)
    with pytest.raises(CanonicalResidueMappingError, match="canonical_resname"):
        validate_canonical_residue_mapping_table(
            CanonicalResidueMappingTable((record,)), reference=reference
        )


def test_numeric_namespace_counterexample_and_missing_lookup(mapped, reference):
    # Synthetic namespace proof only; this is not a biological NaPi2b mapping claim.
    record = replace(
        mapped,
        source_resid="311",
        source_resname="GLN",
        canonical_residue_number=312,
        canonical_resname=reference.residue_at(312).canonical_resname,
    )
    table = CanonicalResidueMappingTable((record, mapped))
    assert validate_canonical_residue_mapping_table(table, reference=reference) is table
    assert require_mapped_source_residue(table, **key_arguments(record)) is record
    assert (
        canonical_residue_for_mapping(record, reference).canonical_residue_number == 312
    )
    assert reference.residue_at(311).canonical_resname == "GLN"
    for remaining in (
        CanonicalResidueMappingTable((mapped,)),
        CanonicalResidueMappingTable(()),
    ):
        assert find_source_residue_mapping(remaining, **key_arguments(record)) is None
        with pytest.raises(CanonicalResidueMappingError, match="No explicit"):
            require_source_residue_mapping(remaining, **key_arguments(record))
        with pytest.raises(CanonicalResidueMappingError, match="No explicit"):
            require_mapped_source_residue(remaining, **key_arguments(record))


@pytest.mark.parametrize(
    "change",
    [
        {"source_engine": "namd"},
        {"source_chain_id": None},
        {"source_chain_id": "a"},
        {"source_chain_id": "B"},
        {"source_resid": "0330"},
        {"source_resid": "330A"},
        {"source_resname": "THR"},
        {"source_resname": "met"},
    ],
)
def test_lookup_requires_all_four_exact_fields(mapped, change):
    table = CanonicalResidueMappingTable((mapped,))
    assert (
        find_source_residue_mapping(table, **(key_arguments(mapped) | change)) is None
    )


@pytest.mark.parametrize(
    "change",
    [
        {"source_engine": "GROMACS"},
        {"source_chain_id": " A"},
        {"source_resid": 330},
        {"source_resname": ""},
    ],
)
def test_lookup_rejects_invalid_key_instead_of_normalizing(mapped, change):
    with pytest.raises(CanonicalResidueMappingError):
        find_source_residue_mapping(
            CanonicalResidueMappingTable((mapped,)), **(key_arguments(mapped) | change)
        )


def test_require_helpers_distinguish_explicit_unmapped(mapped, unmapped, reference):
    table = CanonicalResidueMappingTable((mapped, unmapped))
    assert require_source_residue_mapping(table, **key_arguments(mapped)) is mapped
    assert require_mapped_source_residue(table, **key_arguments(mapped)) is mapped
    assert find_source_residue_mapping(table, **key_arguments(unmapped)) is unmapped
    assert require_source_residue_mapping(table, **key_arguments(unmapped)) is unmapped
    with pytest.raises(CanonicalResidueMappingError, match="explicitly unmapped"):
        require_mapped_source_residue(table, **key_arguments(unmapped))
    with pytest.raises(CanonicalResidueMappingError, match="explicitly unmapped"):
        canonical_residue_for_mapping(unmapped, reference)


def test_reference_requires_exact_type_even_for_empty_table(reference, mapped):
    class ReferenceSubclass(CanonicalProteinReference):
        pass

    arguments = {
        f.name: getattr(reference, f.name) for f in fields(reference) if f.init
    }
    for invalid in (None, reference.to_dict(), ReferenceSubclass(**arguments)):
        with pytest.raises(
            CanonicalResidueMappingError, match="exact CanonicalProteinReference"
        ):
            validate_canonical_residue_mapping_table(
                CanonicalResidueMappingTable(()), reference=invalid
            )
        with pytest.raises(
            CanonicalResidueMappingError, match="exact CanonicalProteinReference"
        ):
            canonical_residue_for_mapping(mapped, invalid)


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("canonical_isoform_id", "O95436-2", "reference_id"),
        ("sequence_sha256", "0" * 64, "sequence_sha256"),
    ],
)
def test_reference_identity_guards(reference, mapped, field, value, message):
    # Corruption injection bypasses 30.A's already strict construction on purpose.
    altered = replace(reference)
    object.__setattr__(altered, field, value)
    with pytest.raises(CanonicalResidueMappingError, match=message):
        validate_canonical_residue_mapping_table(
            CanonicalResidueMappingTable(()), reference=altered
        )
    with pytest.raises(CanonicalResidueMappingError, match=message):
        canonical_residue_for_mapping(mapped, altered)
