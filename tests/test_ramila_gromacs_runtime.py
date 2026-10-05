"""Source-specific Ramila identity, native axes and accepted missing-data science."""

import copy
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
rt = importlib.import_module("ramila_gromacs_runtime")


def make_site(tmp_path):
    source, runtime, output = (tmp_path / n for n in ("source", "runtime", "output"))
    runtime.mkdir()
    authority = copy.deepcopy(rt.load_authority())
    for row in authority["trajectories"]:
        for record in rt.lightweight(row):
            path = source / record["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(record["path"])
            record.update(rt.identity(source, record["path"]).model_dump())
        (source / row["xtc_path"]).write_text(row["trajectory_id"])
    rt.dump(runtime / "authority.json", authority)
    return SimpleNamespace(
        source=source,
        runtime=runtime,
        output=output,
        authority=authority,
        rows=authority["trajectories"],
    )


def spec(variant="wt", *, end=None):
    value = copy.deepcopy(
        rt.load_authority()["trajectories"][0 if variant == "wt" else 6]["dataset_spec"]
    )
    if end is not None:
        value["temporal"]["production_end_ns"] = end
    return value


def window_plan(plan, value):
    from mania.dataset_identity import DatasetTemporalParameters
    from mania.preprocessing.physical_time_windows import plan_physical_time_windows

    return plan_physical_time_windows(
        plan,
        temporal=DatasetTemporalParameters(**value["temporal"]),
        boundary_profile="mania.window_boundaries.inclusive.v1",
    )


def test_exact_twelve_preserved_catalog_identities_and_observed_paths(tmp_path):
    site = make_site(tmp_path)
    authority = rt.load_authority(site.runtime)
    assert tuple(r["trajectory_id"] for r in authority["trajectories"]) == rt.SELECTIONS
    assert len(rt.select(authority, rt.SELECTIONS)) == 12
    rt.discover(site.source, site.rows)
    special = site.rows[4]
    assert special["tpr"]["path"].endswith("mdrep2replacement.tpr")
    assert special["additional_tprs"][0]["path"].endswith("repair_to_101ns.tpr")
    assert len(special["logs"]) == 4
    for row in site.rows:
        variant = row["dataset_spec"]["identity"]["variant_id"]
        assert Path(row["xtc_path"]).name.startswith(
            "md_rep" if variant == "WT" else "t330m_rep"
        )


@pytest.mark.parametrize("variant,end,count", [("wt", 100, 476), ("t330m", 30, 126)])
def test_complete_axis_exact_production_endpoints(variant, end, count):
    plan = rt.sampling_plan(
        tuple(float(t) for t in range(0, end * 1000 + 1, 10)), spec(variant)
    )
    assert plan.requested_sample_count == plan.sampled_frame_count == count
    assert plan.missing_sample_count == 0
    assert plan.selected_samples[0].actual_time_ps == 5000
    assert plan.selected_samples[-1].actual_time_ps == end * 1000
    rt.require_time_qc(plan)


def test_technical_inclusive_windows_share_six_samples():
    value = spec(end=8)
    plan = rt.sampling_plan(tuple(float(t) for t in range(0, 8001, 10)), value)
    windows = window_plan(plan, value).windows
    assert plan.sampled_frame_count == 16
    assert [
        (w.requested_start_ns, w.requested_end_ns, w.sampled_frame_count)
        for w in windows
    ] == [(5, 7, 11), (6, 8, 11)]
    assert (
        len(set(windows[0].source_frame_indexes) & set(windows[1].source_frame_indexes))
        == 6
    )


@pytest.mark.parametrize("kind", ["lipid", "glycan"])
def test_honest_missing_200ps_target_keeps_denominator_and_breaks_episodes(kind):
    from test_preprocessing_specialized_contact_windows import aggregate, frames

    value = spec(end=8)
    # Neighboring 10-ps frames cannot replace the absent exact 6000-ps target.
    times = tuple(float(t) for t in range(5000, 8001, 10) if t != 6000)
    plan = rt.sampling_plan(times, value)
    assert plan.requested_sample_count == 16
    assert plan.sampled_frame_count == 15 and plan.missing_sample_count == 1
    assert plan.missing_samples[0].requested_time_ps == 6000
    assert 5990 not in [s.actual_time_ps for s in plan.selected_samples]
    assert 6010 not in [s.actual_time_ps for s in plan.selected_samples]
    binding = SimpleNamespace(
        sampling_plan=plan,
        window_plan=window_plan(plan, value),
        execution_condition="NORM",
    )
    results = frames(binding, kind=kind, positive=tuple(range(16)), excluded=False)
    observed = aggregate(binding, results, kind)
    first = observed.windows[0].metrics[0]
    assert first.n_resolved_frames_in_window == first.n_contact_frames == 10
    assert first.occupancy == 1.0  # Not 10/11 and no invented zero-contact frame.
    assert first.n_contact_episodes == 2
    assert plan.sampled_frame_count / plan.requested_sample_count == 15 / 16


@pytest.mark.parametrize("times", [(5000, 5200, 5200, 5400), (5000, 5400, 5200, 5600)])
def test_competing_duplicate_and_backward_restart_block(times):
    with pytest.raises(ValueError, match="BLOCKED"):
        rt.sampling_plan(times, spec(end=8))


@pytest.mark.parametrize("missing,passes", [(6, True), (7, False)])
def test_exact_existing_95_percent_qc_with_honest_gaps(missing, passes):
    times = tuple(
        float(t)
        for t in range(0, 30001, 10)
        if t not in {5000 + i * 200 for i in range(missing)}
    )
    plan = rt.sampling_plan(times, spec("t330m"))
    assert plan.requested_sample_count == 126
    assert plan.sampled_frame_count == 126 - missing
    if passes:
        rt.require_time_qc(plan)
    else:
        with pytest.raises(ValueError, match="Production time QC FAIL"):
            rt.require_time_qc(plan)


@pytest.mark.parametrize("variant", ["wt", "t330m"])
@pytest.mark.parametrize("unexpected", [False, True])
def test_explicit_full_sequence_mapping_rejects_unexpected_mutation(
    tmp_path, monkeypatch, variant, unexpected
):
    mda = pytest.importorskip("MDAnalysis")
    import numpy as np

    from mania.preprocessing import molecular_partner_identification as partners
    from mania.preprocessing import specialized_contact_execution as execution

    row = rt.load_authority()["trajectories"][0 if variant == "wt" else 6]
    mapping = rt.read_json(rt.RUNTIME / row["canonical_mapping_path"])
    entries = sorted(mapping["mappings"], key=lambda m: m["canonical_residue_number"])
    if unexpected:
        entries[0]["source_resname"] = "VAL"
    rt.dump(tmp_path / row["canonical_mapping_path"], mapping)
    # One atom per explicitly mapped residue; no reliance on equal numeric IDs.
    u = mda.Universe.empty(
        690, n_residues=690, atom_resindex=np.arange(690), trajectory=True
    )
    u.add_TopologyAttr("resnames", [m["source_resname"] for m in entries])
    u.add_TopologyAttr("resids", [int(m["source_resid"]) for m in entries])
    u.add_TopologyAttr("segids", [entries[0]["source_chain_id"]])
    monkeypatch.setattr(
        rt, "topology_fingerprint", lambda _: row["topology_fingerprint"]
    )
    monkeypatch.setattr(
        execution,
        "adapt_molecular_partner_topology",
        lambda _: (SimpleNamespace(connectivity_status="available"), ()),
    )
    monkeypatch.setattr(
        partners,
        "identify_molecular_partners",
        lambda *a, **kw: SimpleNamespace(
            lipid_partner_count=row["lipid_partners"],
            glycan_partner_count=row["glycan_partners"],
        ),
    )
    metadata = rt.read_json(rt.RUNTIME / row["partner_metadata_path"])
    rt.dump(tmp_path / row["partner_metadata_path"], metadata)
    if unexpected:
        with pytest.raises(ValueError, match="Unexpected protein substitution"):
            rt.validate_topology(u, row, tmp_path)
    else:
        rt.validate_topology(u, row, tmp_path)
