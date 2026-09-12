"""Accepted pure API equivalence and the canonical-only transaction boundary."""

from dataclasses import replace

import pytest
from test_replica_aggregation_manifest import make_manifest
from test_replica_specialized_aggregation import collection

from mania import canonical_window_tables_io as canonical_io
from mania.replica_aggregation_contract import (
    build_compatible_replica_aggregation_group,
)
from mania.replica_aggregation_tables_io import replica_aggregation_csv_bytes
from mania.replica_aggregation_workflow import (
    FAMILIES,
    ReplicaAggregationInputError,
    build_replica_aggregation_tables,
    execute_replica_aggregation_manifest,
    load_replica_aggregation_inputs,
)


def test_complete_pure_workflow_equivalence(tmp_path):
    manifest, _ = make_manifest(tmp_path, complete=True)
    inputs = load_replica_aggregation_inputs(manifest)
    actual = execute_replica_aggregation_manifest(manifest)
    for family in FAMILIES:
        results = []
        for control in manifest.groups:
            group = build_compatible_replica_aggregation_group(
                control.spec,
                control.members,
            )
            if family.name == "protein":
                results.append(family.aggregate(group, inputs[family.name]))
            else:
                correspondences = getattr(control, f"{family.name}_correspondences")
                if correspondences.correspondences:
                    results.append(
                        family.aggregate(
                            group,
                            inputs[family.name],
                            correspondences=correspondences,
                        )
                    )
        expected = family.build_table(tuple(results))
        assert actual[family.name] == expected
        written = family.writer(expected, tmp_path / "expected")
        assert written.written
        assert written.output_path.read_bytes() == replica_aggregation_csv_bytes(
            actual[family.name],
        )
    by_system = {r.system_id: r for r in actual["protein"].rows}
    r = by_system["wt-norm"]
    assert (
        r.mean_occupancy,
        r.std_occupancy,
        r.median_occupancy,
        r.n_replicates_available,
        r.n_replicates_supporting,
        r.support_fraction,
    ) == (
        0.3,
        0.36055512754639896,
        0.2,
        3,
        2,
        2 / 3,
    )
    for system in ("single", "namd-none"):
        r = by_system[system]
        assert (
            r.mean_occupancy,
            r.median_occupancy,
            r.std_occupancy,
            r.n_replicates_available,
            r.n_replicates_supporting,
            r.support_fraction,
        ) == (0.6, 0.6, None, 1, 1, 1.0)
    for system in ("unavailable", "excluded"):
        r = by_system[system]
        assert (
            r.mean_occupancy,
            r.std_occupancy,
            r.n_replicates_available,
            r.support_fraction,
        ) == (0.35, 0.4949747468305833, 2, 0.5)
    assert by_system["namd-none"].condition is None
    assert len([r for r in by_system.values() if r.condition == "NORM"]) == 4
    assert actual["lipid"].rows[0].mean_occupancy == 0.3
    assert actual["glycan"].rows[0].std_occupancy == 0.28867513459481287


@pytest.mark.parametrize("kind", ["lipid", "glycan"])
def test_same_name_unbound_partner_never_participates(tmp_path, kind):
    manifest, _ = make_manifest(tmp_path)
    family = next(f for f in FAMILIES if f.name == kind)
    path = getattr(manifest, f"{kind}_canonical_table_paths")[0]
    original = family.canonical_reader(path)
    unbound = replace(original.rows[0], **{f"{kind}_partner_id": f"{kind}_unbound"})
    table = family.canonical_table(
        tuple(
            sorted(
                (*original.rows, unbound),
                key=lambda r: r.row_order,
            )
        )
    )
    before = execute_replica_aggregation_manifest(manifest)[kind]
    assert getattr(canonical_io, f"write_canonical_protein_{kind}_window_csv")(
        table,
        path.parent,
        overwrite=True,
    ).written
    assert execute_replica_aggregation_manifest(manifest)[kind] == before


def test_empty_and_no_correspondence_families(tmp_path):
    manifest, _ = make_manifest(tmp_path, empty=True)
    assert all(
        t.row_count == 0
        for t in execute_replica_aggregation_manifest(
            manifest,
        ).values()
    )
    g = replace(
        manifest.groups[0],
        lipid_correspondences=collection(),
        glycan_correspondences=collection(),
    )
    manifest = replace(manifest, groups=(g,))
    assert set(execute_replica_aggregation_manifest(manifest)) == {
        "protein",
        "lipid",
        "glycan",
    }


def test_duplicate_across_files_and_source_schema_rejected(tmp_path):
    manifest, _ = make_manifest(tmp_path, specialized=False)
    path = manifest.protein_canonical_table_paths[0]
    other = tmp_path / "distinct-file.csv"
    other.write_bytes(path.read_bytes())
    with pytest.raises(ReplicaAggregationInputError):
        execute_replica_aggregation_manifest(
            replace(
                manifest,
                protein_canonical_table_paths=(path, other),
            )
        )
    path.write_text(
        path.read_text().replace("source_canonical_residue_number", "source_id")
    )
    with pytest.raises(ReplicaAggregationInputError):
        execute_replica_aggregation_manifest(manifest)


def test_no_family_no_invocation_and_no_discovery(tmp_path, monkeypatch):
    manifest, _ = make_manifest(tmp_path, specialized=False)
    (tmp_path / "protein_lipid_contacts_by_window_canonical.csv").write_text("garbage")

    def forbidden(*args, **kwargs):
        raise AssertionError("No directory scan")

    monkeypatch.setattr(type(tmp_path), "glob", forbidden)
    monkeypatch.setattr(type(tmp_path), "iterdir", forbidden)
    inputs = load_replica_aggregation_inputs(manifest)
    assert set(build_replica_aggregation_tables(manifest, inputs)) == {"protein"}


def test_exact_canonical_model_required_even_without_correspondences(tmp_path):
    from mania.preprocessing.specialized_contact_window_tables import (
        ProteinLipidWindowTable,
    )
    from mania.replica_aggregation_workflow import ReplicaAggregationExecutionError

    manifest, _ = make_manifest(tmp_path)
    control = replace(manifest.groups[0], lipid_correspondences=collection())
    manifest = replace(manifest, groups=(control,))
    inputs = load_replica_aggregation_inputs(manifest)
    inputs["lipid"] = ProteinLipidWindowTable(())
    with pytest.raises(ReplicaAggregationExecutionError):
        build_replica_aggregation_tables(manifest, inputs)
