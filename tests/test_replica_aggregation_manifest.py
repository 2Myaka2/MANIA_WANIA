"""Explicit Stage 31.D controls and reusable small synthetic acceptance inputs."""

from dataclasses import replace

import pytest
from test_replica_protein_edge_aggregation import group, row, table
from test_replica_specialized_aggregation import collection, correspondence
from test_replica_specialized_aggregation import row as specialized_row
from test_replica_specialized_aggregation import table as specialized_table

from mania import canonical_window_tables_io as canonical_io
from mania.replica_aggregation_manifest import (
    ReplicaAggregationManifest,
    ReplicaAggregationWorkflowGroup,
)
from mania.replica_aggregation_manifest_io import write_replica_aggregation_manifest


def control(request=None, specialized=True):
    request = group() if request is None else request
    return ReplicaAggregationWorkflowGroup(
        request.spec,
        request.members,
        collection(correspondence("lipid", request, local_ids=("0003", "0007", "0011")))
        if specialized
        else collection(),
        collection(correspondence("glycan", request)) if specialized else collection(),
    )


def make_manifest(tmp_path, *, specialized=True, complete=False, empty=False):
    controls = [control(specialized=specialized)]
    protein_rows = [] if empty else [row(), row("3", 0.2)]
    if complete:
        for system, statuses, engine, condition in (
            ("single", ("available",), "gromacs", "NORM"),
            (
                "unavailable",
                ("available", "available", "unavailable"),
                "gromacs",
                "NORM",
            ),
            ("excluded", ("available", "available", "excluded"), "gromacs", "NORM"),
            ("namd-none", ("available",), "namd", None),
        ):
            controls.append(
                control(
                    group(
                        statuses,
                        system_id=system,
                        engine=engine,
                        condition=condition,
                    ),
                    specialized=False,
                )
            )
            protein_rows.append(
                row(
                    occupancy=0.6 if len(statuses) == 1 else 0.7,
                    system_id=system,
                    engine=engine,
                    condition=condition,
                )
            )
    protein_paths = []
    for replica in ("1", "2", "3"):
        result = canonical_io.write_canonical_protein_edge_window_csv(
            table(*(r for r in protein_rows if r.replica_id == replica)),
            tmp_path / f"replica-{replica}",
        )
        assert result.written
        protein_paths.append(result.output_path)
    specialized_paths = {}
    for kind in ("lipid", "glycan"):
        if specialized:
            values = (0.7, 0, 0.2) if kind == "lipid" else (0.5, 0.5, 0)
            rows = (
                []
                if empty
                else [
                    specialized_row(
                        kind,
                        str(i + 1),
                        value,
                        **(
                            {"lipid_partner_id": "lipid_0011"}
                            if kind == "lipid" and i == 2
                            else {}
                        ),
                    )
                    for i, value in enumerate(values)
                    if value
                ]
            )
            result = getattr(
                canonical_io, f"write_canonical_protein_{kind}_window_csv"
            )(
                specialized_table(kind, *rows),
                tmp_path,
            )
            assert result.written
            specialized_paths[kind] = (result.output_path,)
        else:
            specialized_paths[kind] = ()
    manifest = ReplicaAggregationManifest(
        tuple(protein_paths),
        specialized_paths["lipid"],
        specialized_paths["glycan"],
        tuple(reversed(controls)),
    )
    path = tmp_path / "replica_aggregation_manifest.json"
    assert write_replica_aggregation_manifest(manifest, path).written
    return manifest, path


def test_complete_controls_and_order(tmp_path):
    manifest, _ = make_manifest(tmp_path, complete=True)
    assert [g.spec.system_id for g in manifest.groups] == [
        "excluded",
        "namd-none",
        "single",
        "unavailable",
        "wt-norm",
    ]
    assert manifest.groups[0].members[-1].availability_status == "excluded"
    with pytest.raises(ValueError, match="Duplicate"):
        replace(manifest, groups=manifest.groups * 2)
    with pytest.raises(ValueError):
        replace(manifest, groups=())
    with pytest.raises(ValueError):
        replace(
            manifest,
            protein_canonical_table_paths=(),
            lipid_canonical_table_paths=(),
            glycan_canonical_table_paths=(),
        )


@pytest.mark.parametrize("kind", ["lipid", "glycan"])
def test_incomplete_correspondence_fails_even_without_rows(tmp_path, kind):
    manifest, _ = make_manifest(tmp_path, empty=True)
    g = manifest.groups[0]
    item = getattr(g, f"{kind}_correspondences").correspondences[0]
    with pytest.raises(ValueError, match="cover exactly"):
        replace(
            g,
            **{
                f"{kind}_correspondences": collection(
                    replace(item, members=item.members[:-1]),
                )
            },
        )
    with pytest.raises(ValueError, match="requires canonical"):
        replace(manifest, **{f"{kind}_canonical_table_paths": ()})
    with pytest.raises(ValueError, match="kind"):
        replace(
            g,
            **{
                f"{kind}_correspondences": collection(
                    correspondence(
                        "glycan" if kind == "lipid" else "lipid",
                    )
                )
            },
        )


@pytest.mark.parametrize("mutation", ["engine", "window", "member"])
def test_member_compatibility_before_statistics(mutation):
    request = group()
    members = request.members
    if mutation == "engine":
        members = (replace(members[0], engine="namd"), *members[1:])
    elif mutation == "window":
        window = replace(
            members[0].window,
            requested_window_start_ns=22.5,
            requested_window_end_ns=27.5,
        )
        members = (replace(members[0], window=window), *members[1:])
    else:
        members = members[:-1]
    with pytest.raises(ValueError):
        ReplicaAggregationWorkflowGroup(
            request.spec, members, collection(), collection()
        )


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_physical_input_aliases_rejected(tmp_path, alias):
    manifest, _ = make_manifest(tmp_path, specialized=False)
    original = manifest.protein_canonical_table_paths[0]
    other = tmp_path / "alias.csv"
    if alias == "same":
        other = original
    elif alias == "symlink":
        other.symlink_to(original)
    else:
        other.hardlink_to(original)
    with pytest.raises(ValueError, match="unique physical"):
        replace(manifest, protein_canonical_table_paths=(original, other))
