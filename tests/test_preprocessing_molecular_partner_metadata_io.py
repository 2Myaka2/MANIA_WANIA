"""Explicit control JSON, accepted model reconstruction, atomic persistence."""

import json
from dataclasses import FrozenInstanceError, replace
from unittest.mock import Mock

import pytest

from mania.preprocessing.molecular_partner_entities import (
    ExplicitMolecularPartnerDefinition as Definition,
)
from mania.preprocessing.molecular_partner_entities import (
    MolecularPartnerComponentClassification as Classification,
)
from mania.preprocessing.molecular_partner_metadata_io import (
    MolecularPartnerMetadata,
    MolecularPartnerMetadataReadError,
    read_molecular_partner_metadata,
    validate_molecular_partner_metadata,
    write_molecular_partner_metadata,
)


def metadata(*, lipid=True, glycan=True, external=False):
    classifications, partners = [], []
    if lipid:
        classifications.append(Classification(2, "lipid", "LIPID-X"))
        partners.append(Definition("lipid-one", "lipid", "LIPID-X", (2,)))
    if glycan:
        classifications.append(Classification(3, "glycan", "GLYCAN-X"))
        partners.append(
            Definition(
                "glycan-one",
                "glycan",
                "GLYCAN-X",
                (3,),
                0,
                3,
                "external_metadata" if external else "topology_connectivity",
            )
        )
    return MolecularPartnerMetadata(tuple(classifications), tuple(partners))


@pytest.mark.parametrize("empty", [False, True])
def test_metadata_roundtrip_determinism_order_and_atomic_no_clobber(tmp_path, empty):
    value = metadata(lipid=not empty, glycan=not empty)
    shuffled = MolecularPartnerMetadata(
        tuple(reversed(value.classifications)), tuple(reversed(value.explicit_partners))
    )
    assert shuffled == value
    path = tmp_path / "user-chosen-control.json"
    assert write_molecular_partner_metadata(value, path).passed
    content = path.read_bytes()
    assert content.endswith(b"\n") and not content.endswith(b"\n\n")
    assert read_molecular_partner_metadata(path) == value
    assert validate_molecular_partner_metadata(path).passed
    assert not write_molecular_partner_metadata(value, path).passed
    assert path.read_bytes() == content
    assert write_molecular_partner_metadata(shuffled, path, overwrite=True).passed
    assert path.read_bytes() == content
    assert list(tmp_path.iterdir()) == [path]
    with pytest.raises(FrozenInstanceError):
        value.kind = "other"


@pytest.mark.parametrize(
    "damage",
    [
        "schema",
        "kind",
        "extra",
        "missing",
        "duplicate_key",
        "nan",
        "classification_extra",
        "classification_bool",
        "classification_duplicate",
        "partner_duplicate",
        "component_overlap",
        "component_unordered",
        "array",
        "linkage",
    ],
)
def test_strict_metadata_rejects_malformed_contract(tmp_path, damage):
    payload = metadata().to_dict()
    if damage in ("schema", "kind"):
        payload["schema_version" if damage == "schema" else "kind"] = "unknown"
    elif damage == "extra":
        payload["guess"] = True
    elif damage == "missing":
        del payload["explicit_partners"]
    elif damage == "classification_extra":
        payload["classifications"][0]["guess"] = True
    elif damage == "classification_bool":
        payload["classifications"][0]["residue_index"] = True
    elif damage == "classification_duplicate":
        payload["classifications"].append(payload["classifications"][0])
    elif damage == "partner_duplicate":
        payload["explicit_partners"].append(payload["explicit_partners"][0])
    elif damage == "component_overlap":
        partner = dict(payload["explicit_partners"][0], partner_id="second")
        payload["explicit_partners"].append(partner)
    elif damage == "component_unordered":
        payload["explicit_partners"][0]["component_residue_indexes"] = [3, 2]
    elif damage == "array":
        payload["classifications"] = {}
    elif damage == "linkage":
        payload["explicit_partners"][1]["first_sugar_residue_index"] = None
    text = json.dumps(payload)
    if damage == "duplicate_key":
        text = text.replace('"kind":', '"kind": "duplicate", "kind":', 1)
    if damage == "nan":
        text = text.replace('"residue_index": 2', '"residue_index": NaN', 1)
    path = tmp_path / "metadata.json"
    path.write_text(text)
    with pytest.raises(MolecularPartnerMetadataReadError):
        read_molecular_partner_metadata(path)
    assert not validate_molecular_partner_metadata(path).passed


def test_no_scan_or_name_inference_and_writer_failure(monkeypatch, tmp_path):
    import mania.preprocessing.molecular_partner_metadata_io as module

    value = metadata()
    with pytest.raises(ValueError):
        replace(value, classifications=list(value.classifications))
    monkeypatch.setattr(module.os, "link", Mock(side_effect=OSError("controlled")))
    path = tmp_path / "metadata.json"
    assert not write_molecular_partner_metadata(value, path).passed
    assert not path.exists() and list(tmp_path.iterdir()) == []
