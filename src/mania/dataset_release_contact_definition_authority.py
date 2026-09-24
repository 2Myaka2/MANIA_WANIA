"""Construct publication metadata from versioned authority and explicit run inputs.

No historical publication input, coordinate loading or scientific calculation.
The existing Stage 33 projection remains the strict publication model boundary.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from mania.dataset_release_csv import (
    DatasetReleaseTable,
    require_portable_publication_path,
)
from mania.dataset_release_metadata import (
    ReplicaKey,
    build_dataset_release_contact_definition,
)
from mania.preprocessing.molecular_partner_metadata_io import read_strict_json
from mania.preprocessing.trajectory_contacts import PreprocessingContactDetectionOptions
from mania.preprocessing.trajectory_preprocessing_manifests import (
    build_edge_semantics_manifest,
)

AUTHORITY_RESOURCE = "data/publication/contact_definition_authority_v1.json"
AUTHORITY_SHA256 = "6beafe903e8ca10fc8b9d749108043c3d2c366aed0d516cc4a8041054a89c597"


def _canonical(value: Any) -> str:
    # JSON equality deliberately distinguishes boolean, integer and float leaves.
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))


def _authority_bytes() -> bytes:
    content = files("mania").joinpath(AUTHORITY_RESOURCE).read_bytes()
    if hashlib.sha256(content).hexdigest() != AUTHORITY_SHA256:
        raise ValueError("Committed contact authority hash differs")
    return content


def _bound_path(workspace: Path, path: str) -> Path:
    require_portable_publication_path(path)
    result = workspace / path
    if not result.is_file():
        raise ValueError(f"Missing publication authority binding: {path}")
    return result


def materialize_contact_definition_authority(workspace: Path, path: str) -> Path:
    """Copy exact package bytes; reject an existing substituted authority."""
    require_portable_publication_path(path)
    content = _authority_bytes()
    target = workspace / path
    if target.exists():
        if target.read_bytes() != content:
            raise ValueError("Materialized contact authority differs from package")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(content)
    return target


@dataclass(frozen=True)
class PublicationContactDefinition:
    """An exact nested Stage 33 input plus its strict flattened model."""

    replica_key: ReplicaKey
    contact_definition_id: str
    contact_layer: str
    interaction_type: str
    parameters: dict[str, Any]
    source_artifact_role: str
    source_artifact_path: str
    units: dict[str, str]

    def __post_init__(self) -> None:
        self.to_table()

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(
            dict(
                replica_key=list(self.replica_key),
                contact_definition_id=self.contact_definition_id,
                contact_layer=self.contact_layer,
                interaction_type=self.interaction_type,
                parameters=self.parameters,
                source_artifact_role=self.source_artifact_role,
                source_artifact_path=self.source_artifact_path,
                units=self.units,
            )
        )

    def to_table(self) -> DatasetReleaseTable:
        payload = self.to_dict()
        payload["replica_key"] = self.replica_key
        return build_dataset_release_contact_definition(**payload)


def _run_contact_configuration(
    workspace: Path, path: str, replica_key: ReplicaKey
) -> tuple[dict[str, Any], int]:
    run = read_strict_json(_bound_path(workspace, path))
    if (
        run["kind"] != "mania_run_provenance"
        or run["status"] != "completed"
        or type(run["run_id"]) is not str
        or not run["run_id"].strip()
    ):
        raise ValueError("Completed current run identity is required")
    configuration = run["resolved_configuration"]
    bindings = configuration["dataset_context"]["bindings"]
    selected = [
        b
        for b in bindings
        if tuple(
            b["dataset_spec"]["identity"][name]
            for name in ("dataset_id", "system_id", "trajectory_id", "replica_id")
        )
        == replica_key
    ]
    if len(selected) != 1:
        raise ValueError("Run configuration must bind exactly this replica identity")
    sampling = [
        s
        for s in run["sampling_by_condition"]
        if s["condition"] == selected[0]["execution_condition"]
    ]
    if len(sampling) != 1:
        raise ValueError("Exactly one current sampling binding is required")
    count = sampling[0]["effective"]["sampled_frame_count"]
    if type(count) is not int or count < 1:
        raise ValueError("Resolved sample count must be a positive integer")
    options = configuration["contact_detection_options"]
    validated = PreprocessingContactDetectionOptions(**options).to_dict(
        include_contact_selection=True
    )
    if _canonical(options) != _canonical(validated):
        raise ValueError("Contact options must be complete without normalization")
    if options["distance_unit"] != "angstrom":
        raise ValueError("Contact unit mismatch: accepted representation is angstrom")
    if options["contact_selection"] != "protein":
        raise ValueError("Protein publication requires protein contact selection")
    return options, count


def build_dataset_release_contact_definitions(
    *,
    workspace: Path,
    replica_key: ReplicaKey,
    edge_semantics_path: str,
    run_provenance_path: str,
    pbc_correction_status: dict[str, Any],
    specialized_authority_path: str | None = None,
    partner_catalog_path: str | None = None,
) -> tuple[PublicationContactDefinition, ...]:
    """Build every implemented protein definition and optional specialized pair.

    All paths are explicit workspace-relative artifact bindings. Supplying a
    specialized authority requires its exact package bytes and a partner catalog.
    PBC approval is explicit caller evidence, never inferred from coordinates.
    Current provenance supplies run identity, contact options and resolved count.
    """
    contract = json.loads(_authority_bytes())
    semantics = read_strict_json(_bound_path(workspace, edge_semantics_path))
    if _canonical(semantics) != _canonical(build_edge_semantics_manifest()):
        raise ValueError("Edge semantics differ from implemented publication authority")
    options, count = _run_contact_configuration(
        workspace, run_provenance_path, replica_key
    )
    pbc = copy.deepcopy(pbc_correction_status)
    expected_pbc = contract["pbc_required_values"]
    if set(pbc) != set(expected_pbc) | set(contract["pbc_path_fields"]) or any(
        _canonical(pbc[name]) != _canonical(value)
        for name, value in expected_pbc.items()
    ):
        raise ValueError(
            "PBC requires approved external protocol and internal_mic=false"
        )
    for name in contract["pbc_path_fields"]:
        _bound_path(workspace, pbc[name])
    # Preserve the accepted five-sample prose, but never apply it to another run.
    sample_label = "five" if count == 5 else str(count)
    common = contract["shared_parameters"] | dict(
        occupancy_denominator_semantics=contract[
            "occupancy_denominator_template"
        ].format(resolved_samples=sample_label),
        pbc_correction_status=pbc,
    )
    protein = contract["protein"]
    models = []
    for edge in semantics["edge_types"]:
        criteria = edge["detection_criteria"]
        cutoff = (
            dict(
                value=options["cutoff_distance"],
                unit=options["distance_unit"],
                comparator="<=",
            )
            if criteria.get("threshold_source") == "runtime contact definition"
            else criteria
        )
        models.append(
            PublicationContactDefinition(
                replica_key=replica_key,
                contact_definition_id=edge["name"],
                contact_layer=protein["contact_layer"],
                interaction_type=edge["canonical_backend_spelling"],
                parameters=copy.deepcopy(
                    common
                    | dict(
                        atom_selections=options,
                        cutoff=cutoff,
                        distance_definition=edge["definition"],
                        specialized_distance_semantics=protein[
                            "specialized_distance_semantics"
                        ],
                        type_specific_parameters=edge,
                    )
                ),
                source_artifact_role=protein["source_artifact_role"],
                source_artifact_path=edge_semantics_path,
                units=copy.deepcopy(protein["units"]),
            )
        )
    if specialized_authority_path is None:
        if partner_catalog_path is not None:
            raise ValueError("Partner catalog requires specialized authority binding")
        return tuple(models)
    materialized = _bound_path(workspace, specialized_authority_path)
    if materialized.read_bytes() != _authority_bytes():
        raise ValueError("Materialized contact authority differs from package")
    if partner_catalog_path is None:
        raise ValueError("Missing partner catalog binding")
    _bound_path(workspace, partner_catalog_path)
    for definition in contract["specialized_definitions"]:
        payload = copy.deepcopy(definition)
        payload.update(
            replica_key=replica_key, source_artifact_path=specialized_authority_path
        )
        payload["parameters"].update(copy.deepcopy(common))
        payload["parameters"]["type_specific_parameters"][
            contract["specialized_partner_binding_field"]
        ] = partner_catalog_path
        models.append(PublicationContactDefinition(**payload))
    return tuple(models)
