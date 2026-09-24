"""Publication construction guards needing only packaged and synthetic authority."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from mania.dataset_release_contact_definition_authority import (
    AUTHORITY_RESOURCE,
    AUTHORITY_SHA256,
    build_dataset_release_contact_definitions,
    materialize_contact_definition_authority,
)
from mania.preprocessing.trajectory_contacts import PreprocessingContactDetectionOptions
from mania.preprocessing.trajectory_preprocessing_manifests import (
    build_edge_semantics_manifest,
)

KEY = ("synthetic-dataset", "synthetic-system", "current-trajectory", "1")
AUTHORITY = "authority/contract.json"


def write(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def provenance(key=KEY, count=5, cutoff=4.5):
    return dict(
        kind="mania_run_provenance",
        status="completed",
        run_id="current-synthetic-run",
        software_identity=dict(version="0.1.0"),
        resolved_configuration=dict(
            contact_detection_options=PreprocessingContactDetectionOptions(
                contact_selection="protein", cutoff_distance=cutoff
            ).to_dict(include_contact_selection=True),
            dataset_context=dict(
                bindings=[
                    dict(
                        dataset_spec=dict(
                            identity=dict(
                                zip(
                                    (
                                        "dataset_id",
                                        "system_id",
                                        "trajectory_id",
                                        "replica_id",
                                    ),
                                    key,
                                    strict=True,
                                )
                            )
                        ),
                        execution_condition="synthetic",
                    )
                ]
            ),
        ),
        sampling_by_condition=[
            dict(condition="synthetic", effective=dict(sampled_frame_count=count))
        ],
    )


def bindings(tmp_path):
    write(tmp_path, "run/edge_semantics.json", build_edge_semantics_manifest())
    write(tmp_path, "run/run_provenance.json", provenance())
    write(
        tmp_path,
        "evidence/protocol.json",
        dict(protocol_scientifically_approved=True, internal_mic=False),
    )
    write(tmp_path, "evidence/trajectory.json", dict(status="PASS"))
    write(tmp_path, "evidence/catalog.json", dict(partners=[]))
    materialize_contact_definition_authority(tmp_path, AUTHORITY)
    return dict(
        workspace=tmp_path,
        replica_key=KEY,
        edge_semantics_path="run/edge_semantics.json",
        run_provenance_path="run/run_provenance.json",
        specialized_authority_path=AUTHORITY,
        partner_catalog_path="evidence/catalog.json",
        pbc_correction_status=dict(
            internal_mic=False,
            external_protocol_approved=True,
            historical_scientific_pbc_status="unresolved",
            protocol_authority="evidence/protocol.json",
            trajectory_preparation_and_diagnostics="evidence/trajectory.json",
        ),
    )


def test_reproducible_without_history(tmp_path, monkeypatch):
    args = bindings(tmp_path)
    original = Path.open

    def guarded(path, *a, **kw):
        assert "local_md" not in path.parts
        assert path.name != "publication_inputs.json"
        return original(path, *a, **kw)

    monkeypatch.setattr(Path, "open", guarded)
    models = build_dataset_release_contact_definitions(**args)
    assert models == build_dataset_release_contact_definitions(**args)
    assert [m.contact_definition_id for m in models] == [
        *build_edge_semantics_manifest()["edge_priority"],
        "protein_lipid",
        "protein_glycan",
    ]
    assert sum(m.to_table().row_count for m in models) == 426
    edges = build_edge_semantics_manifest()["edge_types"]
    for model, edge in zip(models[: len(edges)], edges, strict=True):
        assert model.parameters["type_specific_parameters"] == edge
        assert model.source_artifact_role == "accepted_edge_semantics"
        assert model.units == {}
    for model in models[-2:]:
        assert model.source_artifact_role == "accepted_specialized_window_contract"
        assert model.units == {"$/cutoff/value": "angstrom"}
        assert "edge_weight" not in model.parameters
    assert hashlib.sha256((tmp_path / AUTHORITY).read_bytes()).hexdigest() == (
        AUTHORITY_SHA256
    )
    assert all(m.replica_key == KEY for m in models)


@pytest.mark.parametrize(
    "defect",
    [
        "missing",
        "duplicate",
        "collapsed",
        "alias",
        "criteria",
        "priority",
        "overlap",
        "flag",
    ],
)
def test_reject_edge_semantics_inconsistency(tmp_path, defect):
    args = bindings(tmp_path)
    edges = build_edge_semantics_manifest()
    if defect == "missing":
        edges["edge_types"].pop(1)
    elif defect == "duplicate":
        edges["edge_types"].append(copy.deepcopy(edges["edge_types"][0]))
    elif defect == "collapsed":
        edges["edge_types"] = edges["edge_types"][-1:]
    else:
        field, value = {
            "alias": ("canonical_backend_spelling", "saltbridge"),
            "criteria": ("detection_criteria", {"max_ca_distance_A": 5.0}),
            "priority": ("priority_rank", 99),
            "overlap": ("can_overlap_other_edge_types", False),
            "flag": ("implemented", 1),
        }[defect]
        edges["edge_types"][0][field] = value
    write(tmp_path, args["edge_semantics_path"], edges)
    with pytest.raises(ValueError, match="Edge semantics differ"):
        build_dataset_release_contact_definitions(**args)


@pytest.mark.parametrize(
    "defect",
    [
        "id",
        "role",
        "cutoff",
        "anchor",
        "unit",
        "lipid_contact",
        "glycan_contact",
        "version",
        "extra_parameter",
    ],
)
def test_reject_changed_specialized_authority(tmp_path, defect):
    args = bindings(tmp_path)
    data = json.loads((tmp_path / AUTHORITY).read_text())
    lipid, glycan = data["specialized_definitions"]
    if defect in ("id", "lipid_contact"):
        lipid["contact_definition_id"] = "protein_lipid_contact"
    elif defect == "glycan_contact":
        glycan["contact_definition_id"] = "protein_glycan_contact"
    elif defect == "role":
        lipid["source_artifact_role"] = "incorrect_d2_wrapper_role"
    elif defect == "cutoff":
        lipid["parameters"]["cutoff"]["value"] = 6.1
    elif defect == "anchor":
        glycan["parameters"]["type_specific_parameters"]["anchor_exclusion"] = None
    elif defect == "unit":
        lipid["units"]["$/cutoff/value"] = "A"
    elif defect == "version":
        data["contract_version"] = 2
    else:
        lipid["parameters"]["edge_weight"] = "occupancy"
    write(tmp_path, AUTHORITY, data)
    with pytest.raises(ValueError, match="authority differs"):
        build_dataset_release_contact_definitions(**args)
    with pytest.raises(ValueError, match="authority differs"):
        materialize_contact_definition_authority(tmp_path, AUTHORITY)


@pytest.mark.parametrize(
    "defect",
    [
        "internal_mic",
        "approval",
        "missing_protocol",
        "missing_diagnostic",
        "missing_catalog",
        "absent_catalog",
        "unit",
        "identity",
        "run_id",
        "options",
        "absolute_path",
        "parent_path",
    ],
)
def test_reject_invalid_runtime_binding(tmp_path, defect):
    args = bindings(tmp_path)
    if defect == "internal_mic":
        args["pbc_correction_status"]["internal_mic"] = True
    elif defect == "approval":
        args["pbc_correction_status"]["external_protocol_approved"] = False
    elif defect == "missing_protocol":
        del args["pbc_correction_status"]["protocol_authority"]
    elif defect == "missing_diagnostic":
        (tmp_path / "evidence/trajectory.json").unlink()
    elif defect == "missing_catalog":
        args["partner_catalog_path"] = None
    elif defect == "absent_catalog":
        (tmp_path / "evidence/catalog.json").unlink()
    elif defect in ("absolute_path", "parent_path"):
        args["edge_semantics_path"] = (
            str(tmp_path / "run/edge_semantics.json")
            if defect == "absolute_path"
            else "../edge_semantics.json"
        )
    else:
        run = provenance()
        if defect == "unit":
            run["resolved_configuration"]["contact_detection_options"][
                "distance_unit"
            ] = "A"
        elif defect == "identity":
            args["replica_key"] = (*KEY[:3], "2")
        elif defect == "run_id":
            run["run_id"] = ""
        else:
            del run["resolved_configuration"]["contact_detection_options"][
                "exclude_same_residue"
            ]
        write(tmp_path, "run/run_provenance.json", run)
    with pytest.raises(ValueError):
        build_dataset_release_contact_definitions(**args)


def test_runtime_contact_cutoff_and_sampling_are_not_global(tmp_path):
    args = bindings(tmp_path)
    write(tmp_path, "run/run_provenance.json", provenance(count=7, cutoff=5.25))
    models = {
        m.contact_definition_id: m
        for m in build_dataset_release_contact_definitions(**args)
    }
    assert models["residue_contact"].parameters["cutoff"]["value"] == 5.25
    assert models["backbone"].parameters["cutoff"]["max_ca_distance_A"] == 4.5
    assert models["protein_lipid"].parameters["cutoff"]["value"] == 6.0
    for m in models.values():
        assert "7 resolved samples" in m.parameters["occupancy_denominator_semantics"]


def test_protein_only_and_materialization_idempotency(tmp_path):
    args = bindings(tmp_path)
    assert materialize_contact_definition_authority(tmp_path, AUTHORITY).read_bytes()
    args.update(specialized_authority_path=None, partner_catalog_path=None)
    assert len(build_dataset_release_contact_definitions(**args)) == len(
        build_edge_semantics_manifest()["edge_types"]
    )


def helper(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).parents[1] / "tools" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("stage", ["b5", "c2", "c4"])
def test_stage34_helpers_need_no_publication_seed(tmp_path, stage):
    b5 = helper("stage34b5_publication_resume")
    c2 = helper("stage34c_three_replica_downstream")
    c4 = helper("stage34c_publication_resume")
    prefix = "history/c2/" if stage == "c4" else ""
    for replica in ("1",) if stage == "b5" else c2.REPLICAS:
        key = b5.KEY if stage == "b5" else c2.key(replica)
        directory = (
            "b3/output"
            if stage == "b5"
            else prefix
            + (
                "history/b3/output"
                if replica == "1"
                else f"history/c1/replica{replica}/output"
            )
        )
        write(
            tmp_path,
            directory + "/edge_semantics.json",
            build_edge_semantics_manifest(),
        )
        write(tmp_path, directory + "/run_provenance.json", provenance(key))
        diagnostic = (
            "prior/frozen/b3_pbc.json"
            if stage == "b5"
            else prefix
            + (
                "history/r1/frozen/b3_pbc.json"
                if replica == "1"
                else f"history/c1/replica{replica}/persisted_pbc_validation.json"
            )
        )
        write(tmp_path, diagnostic, dict(status="PASS"))
    for directory in ("qc", "aggregation"):
        write(
            tmp_path,
            ("prior/" if stage == "b5" else prefix)
            + directory
            + "/run_provenance.json",
            provenance(),
        )
    authority_prefix = "prior/" if stage == "b5" else prefix + "history/r1/"
    write(
        tmp_path,
        authority_prefix + "pbc_protocol_approval.json",
        dict(protocol_scientifically_approved=True, internal_mic=False),
    )
    write(tmp_path, authority_prefix + "frozen/partner_catalog.json", dict(partners=[]))
    if stage == "c4":
        for r in ("2", "3"):
            write(
                tmp_path,
                f"history/c3/replica{r}/molecular_partner_catalog.json",
                dict(partners=[]),
            )
    assert not list(tmp_path.rglob("publication_inputs.json"))
    model = (
        b5.prepare_publication_inputs
        if stage == "b5"
        else c2.publication_inputs
        if stage == "c2"
        else c4.prepare_publication_inputs
    )(tmp_path)
    assert len(model.contact_definitions) == {"b5": 12, "c2": 32, "c4": 36}[stage]
    assert (
        sum(t.row_count for t in model.contact_definitions)
        == {
            "b5": 426,
            "c2": 1194,
            "c4": 1278,
        }[stage]
    )
    assert not model.metrics


def test_resource_has_no_historical_identity():
    from importlib.resources import files

    text = files("mania").joinpath(AUTHORITY_RESOURCE).read_text()
    for forbidden in ("local_md", "/home/", "stage34", "run_id", "timestamp"):
        assert forbidden not in text
