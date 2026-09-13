"""Narrow publication inputs preserve accepted builder authority and scalar types."""

import json
from dataclasses import asdict

import pytest
from test_dataset_release_metadata import contact_parameters, replica_key
from test_dataset_release_science import metric

from mania.dataset_release_inputs_io import (
    PUBLICATION_INPUT_KIND,
    PUBLICATION_INPUT_SCHEMA_VERSION,
    read_dataset_release_publication_inputs,
    write_dataset_release_publication_inputs,
)


def payload():
    return {
        "schema_version": PUBLICATION_INPUT_SCHEMA_VERSION,
        "kind": PUBLICATION_INPUT_KIND,
        "contact_definitions": [
            dict(
                replica_key=list(replica_key()),
                contact_definition_id=layer,
                contact_layer=layer,
                interaction_type=layer,
                parameters=contact_parameters(layer),
                units={},
                source_artifact_role="accepted_contact_definition",
                source_artifact_path=f"evidence/{layer}.json",
            )
            for layer in ("protein-protein", "protein-lipid", "protein-glycan")
        ],
        "software_versions": [
            dict(
                dataset_id=replica_key()[0],
                component_role="engine",
                component_name="NAMD",
                version=None,
                run_id=None,
                source_artifact_role="supplied_engine_record",
                source_artifact_path="evidence/engine.json",
            )
        ],
        "metrics": [asdict(metric()) | {"source_value_field": "occupancy"}],
    }


def test_publication_input_roundtrip_and_values(tmp_path):
    path = tmp_path / "inputs.json"
    assert write_dataset_release_publication_inputs(payload(), path).written
    model = read_dataset_release_publication_inputs(path)
    assert model.software_versions.records()[0]["version"] is None
    assert model.metrics == (metric(),)
    assert model.metric_source_value_fields == ("occupancy",)
    assert len(model.contact_definitions) == 3
    lipid = {r["parameter_path"]: r for r in model.contact_definitions[1].records()}
    glycan = {r["parameter_path"]: r for r in model.contact_definitions[2].records()}
    assert lipid["$/cutoff/value"]["number_value"] == 6
    assert glycan["$/cutoff/value"]["number_value"] == 4.5
    assert lipid["$/cutoff/comparison"]["string_value"] == "<="
    assert (
        lipid[
            "$/pbc_correction_status/mania_internal_minimum_image_correction_applied"
        ]["boolean_value"]
        is False
    )
    assert not write_dataset_release_publication_inputs(payload(), path).written


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "contact_unknown",
        "software_unknown",
        "metric_unknown",
        "metric_bool",
        "partial_window",
        "missing_parameters",
        "wrong_version",
    ],
)
def test_strict_control_input_mutations(tmp_path, mutation):
    data = payload()
    if mutation == "unknown":
        data["extra"] = True
    elif mutation.endswith("unknown"):
        key = {
            "contact_unknown": "contact_definitions",
            "software_unknown": "software_versions",
            "metric_unknown": "metrics",
        }[mutation]
        data[key][0]["extra"] = 1
    elif mutation == "metric_bool":
        data["metrics"][0]["metric_value"] = True
    elif mutation == "partial_window":
        data["metrics"][0]["window_index"] = 1
    elif mutation == "missing_parameters":
        del data["contact_definitions"][0]["parameters"]["cutoff"]
    else:
        data["software_versions"][0]["version"] = 1
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        read_dataset_release_publication_inputs(path)
