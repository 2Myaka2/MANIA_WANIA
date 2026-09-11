"""Controlled metadata only: canonical regions never imply supplied site flags."""

import ast
import inspect
from dataclasses import FrozenInstanceError, replace

import pytest

from mania import biological_annotations as m
from mania.canonical_reference_io import load_default_napi2b_canonical_reference


def metadata(**changes):
    return m.DatasetSystemBiologicalAnnotations(
        **{
            "dataset_id": "synthetic",
            "system_id": "variant",
            "annotation_scope": "complete_for_system",
            "glycosylation_sites": (),
            "disulfide_variant_sites": (),
            "cysteine_variant_sites": (),
            **changes,
        }
    )


def glyco(number=330, **changes):
    return m.GlycosylationSiteAnnotation(
        **{
            "canonical_residue_number": number,
            "canonical_resname": load_default_napi2b_canonical_reference()
            .residue_at(number)
            .canonical_resname,
            "present_in_topology": True,
            "glycan_name": "synthetic-glycan",
            "source": "controlled-fixture",
            "verifier": "fixture-review",
            **changes,
        }
    )


def variant(number=330, **changes):
    return m.CanonicalVariantSiteAnnotation(
        **{
            "canonical_residue_number": number,
            "canonical_resname": load_default_napi2b_canonical_reference()
            .residue_at(number)
            .canonical_resname,
            "source": "controlled-fixture",
            "verifier": "fixture-review",
            **changes,
        }
    )


@pytest.mark.parametrize(
    "number,ecd,mx35",
    [
        (233, False, False),
        (234, True, False),
        (310, True, False),
        (311, True, True),
        (330, True, True),
        (341, True, True),
        (342, True, False),
        (361, True, False),
        (362, False, False),
    ],
)
def test_exact_regions_and_complete_negative_semantics(number, ecd, mx35):
    assert (m.NAPI2B_ECD_START, m.NAPI2B_ECD_END) == (234, 361)
    assert (m.NAPI2B_MX35_START, m.NAPI2B_MX35_END) == (311, 341)
    annotation = metadata().annotation_for_residue(number)
    assert annotation.is_ecd is ecd
    assert annotation.is_mx35_region is mx35
    assert annotation.is_glycosylation_site is False
    assert annotation.glycosylation_present_in_topology is None
    assert annotation.glycan_name is None
    assert annotation.glycosylation_source is None
    assert annotation.glycosylation_verifier is None
    assert not annotation.is_disulfide_variant_site
    assert not annotation.is_cysteine_variant_site


def test_mx35_inside_ecd_and_explicit_sites_with_topology_absence():
    for number in range(311, 342):
        assert m.is_napi2b_ecd_residue(number)
        assert m.is_napi2b_mx35_residue(number)
    data = metadata(
        glycosylation_sites=(glyco(present_in_topology=False),),
        disulfide_variant_sites=(variant(),),
        cysteine_variant_sites=(variant(),),
    )
    annotation = data.annotation_for_residue(330)
    assert annotation.canonical_resname == "THR"
    assert annotation.is_glycosylation_site
    assert annotation.glycosylation_present_in_topology is False
    assert annotation.glycan_name == "synthetic-glycan"
    assert annotation.glycosylation_source == "controlled-fixture"
    assert annotation.glycosylation_verifier == "fixture-review"
    assert annotation.is_disulfide_variant_site
    assert annotation.is_cysteine_variant_site
    for obj, field in (
        (data, "system_id"),
        (glyco(), "glycan_name"),
        (variant(), "source"),
        (annotation, "is_ecd"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, field, None)


@pytest.mark.parametrize("number", [0, 691, True, False, 330.0, "330", None])
def test_bad_canonical_position(number):
    for helper in (
        m.is_napi2b_ecd_residue,
        m.is_napi2b_mx35_residue,
        metadata().annotation_for_residue,
    ):
        with pytest.raises(m.BiologicalAnnotationError):
            helper(number)


@pytest.mark.parametrize(
    "factory,changes",
    [
        (glyco, {"canonical_resname": "MET"}),
        (variant, {"canonical_resname": None}),
        (glyco, {"present_in_topology": 1}),
        (glyco, {"glycan_name": ""}),
        (glyco, {"source": ""}),
        (variant, {"verifier": ""}),
        (metadata, {"annotation_scope": "unknown"}),
        (metadata, {"annotation_scope": "partial"}),
        (metadata, {"dataset_id": ""}),
        (metadata, {"system_id": 1}),
    ],
)
def test_invalid_metadata(factory, changes):
    with pytest.raises(m.BiologicalAnnotationError):
        factory(**changes)


@pytest.mark.parametrize(
    "name,factory",
    [
        ("glycosylation_sites", glyco),
        ("disulfide_variant_sites", variant),
        ("cysteine_variant_sites", variant),
    ],
)
def test_duplicate_unsorted_and_non_tuple_sites(name, factory):
    for sites in (
        (factory(), factory()),
        (factory(330), factory(311)),
        [factory()],
        (object(),),
    ):
        with pytest.raises(m.BiologicalAnnotationError):
            metadata(**{name: sites})


@pytest.mark.parametrize(
    "changes",
    [
        {"canonical_resname": "MET"},
        {"is_ecd": False},
        {"is_mx35_region": False},
        {"is_ecd": 1},
        {"is_glycosylation_site": 0},
        {"is_cysteine_variant_site": None},
        {"is_disulfide_variant_site": "false"},
        {"glycan_name": "invented"},
        {"is_glycosylation_site": True},
    ],
)
def test_residue_flags_revalidate(changes):
    with pytest.raises(m.BiologicalAnnotationError):
        replace(metadata().annotation_for_residue(330), **changes)


def test_no_network_or_scientific_runtime_imports(monkeypatch):
    import socket
    import subprocess
    import urllib.request

    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected network/process access")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    assert metadata(glycosylation_sites=(glyco(),)).annotation_for_residue(330).is_ecd
    tree = ast.parse(inspect.getsource(m))
    imports = [
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    assert not any(
        name and name.startswith(("requests", "http", "urllib", "MDAnalysis"))
        for name in imports
    )
