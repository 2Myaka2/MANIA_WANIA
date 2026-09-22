"""Source authority failures and shared reader behavior, without real contacts."""

import importlib.util
import json
from dataclasses import replace
from decimal import localcontext
from pathlib import Path

import numpy as np
import pytest

from mania.preprocessing.namd_authority import (
    DCDIdentity,
    ElementControl,
    RawFrameTime,
    ReviewedAssignment,
    SourceRecord,
    TimeControl,
    derive_time,
    read_control,
    read_reviewed_assignments,
    source_identity,
    validate_elements,
    validate_time,
    write_control,
)
from mania.preprocessing.namd_runtime import (
    NAMDControlPaths,
    apply_namd_authority,
    observe_dcd,
)
from mania.preprocessing.physical_time_execution import (
    collect_runtime_physical_time_source_frames,
)
from mania.preprocessing.trajectory_loader import load_single_condition_runtime
from mania.preprocessing.trajectory_runtime import PreprocessingConditionRuntimeInput

spec = importlib.util.spec_from_file_location(
    "stage34b_authority_helper",
    Path(__file__).parents[1] / "tools/stage34b_namd_authority.py",
)
assert spec and spec.loader
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


@pytest.fixture
def element_bundle(tmp_path):
    psf = tmp_path / "input.psf"
    # Names intentionally disagree with types; masses intentionally uninformative.
    atoms = [("H", "CL"), ("C", "CLA"), ("Cl", "SOD"), ("Na", "Q")]
    text = "PSF EXT\n\n         1 !NTITLE\n REMARKS synthetic authority test\n\n"
    text += "         4 !NATOM\n"
    for i, (name, atom_type) in enumerate(atoms, 1):
        text += (
            f"{i:10d} {'PROA':<8} {1:<8} {'ALA':<8} {name:<8} "
            f"{atom_type:<8} {0.0:14.6f} {99.0:14.4f} {0:8d}\n"
        )
    text += "\n         1 !NBOND: bonds\n         1         4\n"
    psf.write_text(text)
    directory = tmp_path / "toppar"
    directory.mkdir()
    rtf = directory / "source.rtf"
    rtf.write_text(
        "MASS -1 CL 12 C ! explicitly carbon\n"
        "MASS -1 CLA 35 CL ! explicitly chlorine\n"
        "MASS -1 SOD 23 NA ! explicitly sodium\n"
        "MASS -1 Q 99 ! polar hydrogen\n"
        "RESI TEST 0\nATOM X Q 0 ! chemical hydrogen site\n"
    )
    source = source_identity(rtf)
    review = ReviewedAssignment(
        atom_type="Q",
        element="H",
        status="accepted",
        rationale="Original definition explicitly states polar hydrogen.",
        evidence=(
            SourceRecord(source=source, line=4, text=rtf.read_text().splitlines()[3]),
        ),
    )
    control = helper.build_elements(psf, directory, (review,))
    return psf, directory, review, control


def config_log(tmp_path, count=1000):
    config, log = tmp_path / "input.conf", tmp_path / "production.out"
    config.write_text(
        "structure input.psf\ndcdfile original.dcd\ntimestep 2.0\n"
        f"dcdfreq 50000\nfirsttimestep 0\nnumsteps {50000 * count}\n"
    )
    log.write_text(
        "Info: TIMESTEP 2\nInfo: DCD FREQUENCY 50000\n"
        f"Info: NUMBER OF STEPS {50000 * count}\n"
        "Info: DCD FIRST STEP 50000\nInfo: STRUCTURE FILE input.psf\n"
        "Info: DCD FILENAME original.dcd\n"
        + "".join(
            f"WRITING COORDINATES TO DCD FILE original.dcd AT STEP {step}\n"
            for step in range(50000, 50000 * count + 1, 50000)
        )
    )
    return config, log


def time_control(config, log, raw):
    return TimeControl(
        schema_version="mania.namd_time_authority.v1",
        engine="NAMD",
        config=source_identity(config),
        log=source_identity(log),
        dcd=raw,
        derivation="config_log_step_times_timestep_fs_divided_by_1000",
        status="validated",
        **derive_time(config, log, raw.frame_count),
    )


@pytest.fixture
def time_bundle(tmp_path):
    config, log = config_log(tmp_path)
    dcd = tmp_path / "input.dcd"
    dcd.write_bytes(b"header identity only; runtime tests use an actual DCD")
    raw = DCDIdentity(
        path=str(dcd),
        size_bytes=dcd.stat().st_size,
        atom_count=4,
        frame_count=1000,
        istart=50000,
        nsavc=50000,
        delta=0.04090965911746025,
        dt_ps=100.00000029814058,
        unit_cell=True,
        remarks="FILENAME=original.dcd CREATED BY NAMD",
        observed_times=(
            RawFrameTime(frame=0, time_ps=100.00000029814058),
            RawFrameTime(frame=999, time_ps=100000.00029814057),
        ),
    )
    return dcd, time_control(config, log, raw)


def test_exact_lookup_and_provenance(element_bundle, tmp_path):
    psf, _, _, control = element_bundle
    assert validate_elements(control, psf) == {
        "CL": "C",
        "CLA": "Cl",
        "Q": "H",
        "SOD": "Na",
    }
    path = tmp_path / "elements.json"
    write_control(path, control)
    reread = read_control(path, ElementControl)
    assert reread == control
    assert reread.entries[0].authority_kind == "direct_definition"
    assert next(e for e in reread.entries if e.atom_type == "Q").review.rationale
    assert {e.element for e in control.entries} == {"C", "Cl", "H", "Na"}


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "case",
        "population",
        "duplicate",
        "wrong_psf",
        "stale_source",
        "missing_definition",
        "wrong_element",
        "unresolved",
        "rejected",
        "stale_line",
        "no_type_evidence",
        "extra_source",
    ],
)
def test_element_fail_closed(element_bundle, tmp_path, mutation):
    psf, directory, review, control = element_bundle
    payload = control.model_dump(mode="json")
    if mutation in ("unknown", "case"):
        payload["entries"][0]["atom_type"] = (
            "UNKNOWN" if mutation == "unknown" else "cl"
        )
    elif mutation == "population":
        payload["used_type_counts"]["CL"] += 1
    elif mutation == "duplicate":
        payload["entries"].append(payload["entries"][0])
    elif mutation == "wrong_psf":
        other = tmp_path / "other.psf"
        other.write_text(psf.read_text())
        psf = other
    elif mutation == "stale_source":
        path = directory / "source.rtf"
        path.write_text(path.read_text() + "! changed\n")
    elif mutation == "extra_source":
        (directory / "extra.str").write_text("MASS -1 CL 35 CL\n")
    elif mutation == "missing_definition":
        payload["entries"][0]["definitions"] = []
    elif mutation == "wrong_element":
        payload["entries"][0]["element"] = "Cl"
    else:
        target = next(e for e in payload["entries"] if e["atom_type"] == "Q")
        if mutation in ("unresolved", "rejected"):
            target["review"]["status"] = mutation
        elif mutation == "stale_line":
            target["review"]["evidence"][0]["text"] = "invented evidence"
        elif mutation == "no_type_evidence":
            target["review"]["evidence"][0]["line"] = 1
            target["review"]["evidence"][0]["text"] = (
                (directory / "source.rtf").read_text().splitlines()[0]
            )
    with pytest.raises(ValueError):
        altered = ElementControl.model_validate_json(json.dumps(payload))
        validate_elements(altered, psf)


def test_all_definitions_conflict_and_compatible_mass_difference(element_bundle):
    psf, directory, review, _ = element_bundle
    path = directory / "duplicate.prm"
    path.write_text(
        "MASS -1 CL 12.011 C ! compatible; differing mass is evidence only\n"
    )
    control = helper.build_elements(psf, directory, (review,))
    assert len(control.entries[0].definitions) == 2
    path.write_text("MASS -1 CL 12.011 CL ! conflicting explicit element\n")
    with pytest.raises(ValueError, match="Conflicting"):
        helper.build_elements(psf, directory, (review,))


def test_no_review_no_guess_even_with_names_masses_or_pdb(element_bundle, tmp_path):
    psf, directory, _, _ = element_bundle
    (tmp_path / "initial.pdb").write_text("ATOM      1  H   ALA A   1\n")
    with pytest.raises(ValueError, match="Unresolved used type: Q"):
        helper.build_elements(psf, directory, ())


@pytest.mark.parametrize(
    "field,value",
    [("engine", "GROMACS"), ("schema_version", "future"), ("unknown", True)],
)
def test_strict_control_fields(element_bundle, field, value):
    payload = element_bundle[3].model_dump(mode="json")
    payload[field] = value
    with pytest.raises(ValueError):
        ElementControl.model_validate_json(json.dumps(payload))


def test_duplicate_json_rejected(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"engine":"NAMD","engine":"NAMD"}')
    with pytest.raises(ValueError, match="Duplicate"):
        read_control(path, ElementControl)


def test_duplicate_review_status_rejected(tmp_path):
    path = tmp_path / "review.json"
    path.write_text('[{"status":"unresolved","status":"accepted"}]')
    with pytest.raises(ValueError, match="Duplicate"):
        read_reviewed_assignments(path)


def test_exact_time_axis_and_stage27_proof(time_bundle):
    dcd, control = time_bundle
    times = validate_time(control, dcd)
    assert len(times) == 1000 and times[0] == 100 and times[999] == 100000
    assert control.dcd.dt_ps == 100.00000029814058
    assert control.dcd.observed_times[0].time_ps != times[0]
    with localcontext() as context:
        context.prec = 2
        assert (
            derive_time(Path(control.config.path), Path(control.log.path), 1000)[
                "scientific_times_ps"
            ]
            == control.scientific_times_ps
        )
    proof = helper.sampling_proof(control)
    assert proof["full_grid"]["sampled_frame_count"] == 1000
    assert proof["future_pilot"]["sampled_frame_count"] == 5
    assert proof["full_grid"]["missing_sample_count"] == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "missing",
        "irregular",
        "reset",
        "count",
        "config",
        "start",
        "other_dcd",
        "log_dt",
        "extra_run",
        "dynamic",
        "rounding",
        "stale_log",
        "wrong_dcd",
        "bad_header",
    ],
)
def test_time_fail_closed(time_bundle, mutation, tmp_path):
    dcd, control = time_bundle
    config, log = Path(control.config.path), Path(control.log.path)
    text = log.read_text()
    line = "WRITING COORDINATES TO DCD FILE original.dcd AT STEP 100000\n"
    if mutation == "duplicate":
        log.write_text(text.replace(line, line + line))
    elif mutation == "missing":
        log.write_text(text.replace(line, ""))
    elif mutation in ("irregular", "reset"):
        log.write_text(
            text.replace(
                line,
                line.replace("100000", "100001" if mutation == "irregular" else "0"),
            )
        )
    elif mutation == "config":
        config.write_text(config.read_text().replace("timestep 2.0", "timestep 4.0"))
    elif mutation == "start":
        config.write_text(
            config.read_text().replace("firsttimestep 0", "firsttimestep 50000")
        )
    elif mutation == "other_dcd":
        log.write_text(text.replace(line, line.replace("original.dcd", "other.dcd")))
    elif mutation == "log_dt":
        log.write_text(text.replace("TIMESTEP 2", "TIMESTEP 3"))
    elif mutation in ("extra_run", "dynamic"):
        config.write_text(
            config.read_text()
            + ("run 50000\n" if mutation == "extra_run" else "timestep $dt\n")
        )
    elif mutation == "stale_log":
        log.write_text(text + "new content\n")
        with pytest.raises(ValueError, match="Stale"):
            validate_time(control, dcd)
        return
    elif mutation == "wrong_dcd":
        dcd = tmp_path / "another.dcd"
        dcd.write_bytes(b"wrong")
    elif mutation == "rounding":
        control = control.model_copy(
            update={
                "scientific_times_ps": tuple(
                    str(round((i + 1) * control.dcd.dt_ps, 6)) for i in range(1000)
                )
            }
        )
    elif mutation == "bad_header":
        control = control.model_copy(
            update={"dcd": control.dcd.model_copy(update={"istart": 0})}
        )
    with pytest.raises(ValueError):
        if mutation in ("rounding", "wrong_dcd", "bad_header"):
            validate_time(control, dcd)
        else:
            derive_time(config, log, 999 if mutation == "count" else 1000)


@pytest.fixture
def actual_reader_bundle(element_bundle, tmp_path, request):
    mda = pytest.importorskip("MDAnalysis")
    psf, _, _, elements = element_bundle
    dcd = tmp_path / "input.dcd"
    writer_u = mda.Universe(str(psf), to_guess=())
    frame_count = getattr(request, "param", 5)
    writer_u.load_new(np.zeros((frame_count, 4, 3), dtype=np.float32), order="fac")
    with mda.Writer(
        str(dcd),
        4,
        dt=100,
        nsavc=50000,
        istart=50000,
        remarks="FILENAME=original.dcd CREATED BY NAMD",
    ) as writer:
        for i, ts in enumerate(writer_u.trajectory):
            ts.positions[:] = np.arange(12).reshape(4, 3) + i
            ts.dimensions = [20 + i, 21 + i, 22 + i, 90, 90, 90]
            writer.write(writer_u)
    config, log = config_log(tmp_path, frame_count)
    u = mda.Universe(str(psf), str(dcd), to_guess=())
    time = time_control(config, log, observe_dcd(u.trajectory, dcd))
    paths = NAMDControlPaths(tmp_path / "elements.json", tmp_path / "time.json")
    write_control(paths.elements, elements)
    write_control(paths.time, time)
    yield u, paths, PreprocessingConditionRuntimeInput("test", psf, (dcd,)), time
    u.trajectory.close()


def test_reader_repeated_random_reopened_and_all_later_consumers(actual_reader_bundle):
    u, paths, runtime_input, time = actual_reader_bundle
    before = helper.topology_snapshot(u)
    frames = [
        (ts.positions.copy(), ts.dimensions.copy(), ts.time) for ts in u.trajectory
    ]
    loaded = load_single_condition_runtime(runtime_input, namd_authority=paths)
    assert loaded.passed, loaded.issues
    adapted = loaded.runtime.runtime_object
    try:
        assert helper.topology_snapshot(adapted) == before
        assert list(adapted.atoms.elements) == ["C", "Cl", "Na", "H"]
        for _ in range(2):
            source = collect_runtime_physical_time_source_frames(loaded)
            assert [s.time_ps for s in source] == [100, 200, 300, 400, 500]
        for i in [4, 0, 2, 2, 1, 3, 0]:
            ts = adapted.trajectory[i]
            assert ts.time == (i + 1) * 100
            np.testing.assert_array_equal(ts.positions, frames[i][0])
            np.testing.assert_array_equal(ts.dimensions, frames[i][1])
        adapted.trajectory.close()
        adapted.trajectory._reopen()
        assert [ts.time for ts in adapted.trajectory] == [100, 200, 300, 400, 500]
        # The accepted Stage 28 engine consumes the same Stage 27 actual timestamps.
        from mania.dataset_identity import DatasetTemporalParameters
        from mania.preprocessing.contact_episodes import compute_window_contact_episodes
        from mania.preprocessing.physical_time_sampling import (
            resolve_physical_time_sampling,
        )
        from mania.preprocessing.physical_time_windows import plan_physical_time_windows

        temporal = DatasetTemporalParameters(
            production_start_ns=0.1,
            production_end_ns=0.5,
            frame_stride_ps=100,
            window_length_ns=0.4,
            window_step_ns=0.4,
            overlap_percent=0,
        )
        sampling = resolve_physical_time_sampling(source, temporal=temporal)
        windows = plan_physical_time_windows(sampling, temporal=temporal)
        episode = compute_window_contact_episodes(
            sampling,
            windows.windows[0],
            contact_source_frame_indexes=tuple(range(5)),
        )
        assert episode.episodes[0].start_actual_time_ps == 100
        assert episode.episodes[0].end_actual_time_ps == 500
        assert episode.episodes[0].episode_length_ns == 0.4
        from mania.preprocessing.trajectory_contacts import _frame_time as contact_time
        from mania.preprocessing.trajectory_rg import _frame_time as rg_time

        ts = adapted.trajectory[4]
        assert contact_time(ts, 4, None) == 500
        assert rg_time("test", 4, ts, None)[0] == 500
    finally:
        adapted.trajectory.close()
    reopened = load_single_condition_runtime(runtime_input, namd_authority=paths)
    assert reopened.passed
    assert reopened.runtime.runtime_object.trajectory[0].time == 100
    reopened.runtime.runtime_object.trajectory.close()
    assert time.dcd.observed_times[0].time_ps == frames[0][2]


def test_existing_elements_conflict_and_no_mutation(actual_reader_bundle):
    u, paths, runtime_input, _ = actual_reader_bundle
    u.add_TopologyAttr("elements", ["H"] * 4)
    before = helper.topology_snapshot(u)
    with pytest.raises(ValueError, match="Existing explicit"):
        apply_namd_authority(
            u, runtime_input.topology_path, runtime_input.trajectory_paths[0], paths
        )
    assert list(u.atoms.elements) == ["H"] * 4
    assert helper.topology_snapshot(u) == before
    assert u.trajectory.transformations == [] or u.trajectory.transformations == ()


def test_legacy_no_control_and_conflicting_frame_override(actual_reader_bundle):
    u, paths, runtime_input, _ = actual_reader_bundle
    raw = u.trajectory[0].time
    legacy = load_single_condition_runtime(runtime_input)
    assert legacy.passed
    assert legacy.runtime.runtime_object.trajectory[0].time == raw != 100
    assert getattr(legacy.runtime.runtime_object.atoms, "elements", None) is None
    legacy.runtime.runtime_object.trajectory.close()
    assert not load_single_condition_runtime(
        replace(runtime_input, frame_time_ps=100), namd_authority=paths
    ).passed


def test_gromacs_extension_cannot_apply_control(actual_reader_bundle):
    u, paths, runtime_input, _ = actual_reader_bundle
    with pytest.raises(ValueError, match="PSF/DCD"):
        apply_namd_authority(
            u,
            runtime_input.topology_path.with_suffix(".tpr"),
            runtime_input.trajectory_paths[0],
            paths,
        )


@pytest.mark.parametrize("actual_reader_bundle", [1000], indirect=True)
def test_full_reader_axis_through_stage27(actual_reader_bundle):
    _, paths, runtime_input, _ = actual_reader_bundle
    loaded = load_single_condition_runtime(runtime_input, namd_authority=paths)
    assert loaded.passed
    try:
        source = collect_runtime_physical_time_source_frames(loaded)
        assert len(source) == 1000
        assert source[0].time_ps == 100 and source[999].time_ps == 100000
        from mania.dataset_identity import DatasetTemporalParameters
        from mania.preprocessing.physical_time_sampling import (
            resolve_physical_time_sampling,
        )

        temporal = DatasetTemporalParameters(
            production_start_ns=0.1,
            production_end_ns=100,
            frame_stride_ps=100,
            window_length_ns=0.4,
            window_step_ns=0.4,
            overlap_percent=0,
        )
        plan = resolve_physical_time_sampling(source, temporal=temporal)
        assert plan.sampled_frame_count == plan.requested_sample_count == 1000
        assert plan.missing_sample_count == 0
        assert all(sample.time_delta_ps == 0 for sample in plan.selected_samples)
    finally:
        loaded.runtime.runtime_object.trajectory.close()


def test_existing_matching_elements_and_double_application(actual_reader_bundle):
    u, paths, runtime_input, _ = actual_reader_bundle
    u.add_TopologyAttr("elements", ["C", "Cl", "Na", "H"])
    apply_namd_authority(
        u, runtime_input.topology_path, runtime_input.trajectory_paths[0], paths
    )
    assert u.trajectory[0].time == 100
    with pytest.raises(ValueError, match="before trajectory transformations"):
        apply_namd_authority(
            u, runtime_input.topology_path, runtime_input.trajectory_paths[0], paths
        )
    assert u.trajectory[0].time == 100


def test_runtime_header_tampering_rejected(actual_reader_bundle):
    u, paths, runtime_input, time = actual_reader_bundle
    payload = time.model_dump(mode="json")
    payload["dcd"]["dt_ps"] = 100.0
    paths.time.write_text(json.dumps(payload))
    before = helper.topology_snapshot(u)
    with pytest.raises(ValueError, match="Stale DCD"):
        apply_namd_authority(
            u, runtime_input.topology_path, runtime_input.trajectory_paths[0], paths
        )
    assert helper.topology_snapshot(u) == before
    assert getattr(u.atoms, "elements", None) is None


def test_mapping_readiness_never_infers_numeric_identity(element_bundle):
    psf = element_bundle[0]
    assert helper.mapping_readiness(None, psf, None, None)["status"] == "BLOCKED"
    with pytest.raises(ValueError, match="Wrong mapping PSF"):
        helper.mapping_readiness(None, psf, Path("unread.json"), "0" * 64)


@pytest.mark.parametrize(
    "statement",
    [
        "eval {timestep 4}",
        "foreach x {1 2} {}",
        "proc another_run {} {}",
        "source extra.conf",
    ],
)
def test_dynamic_tcl_time_authority_rejected(time_bundle, statement):
    _, time = time_bundle
    config = Path(time.config.path)
    config.write_text(config.read_text() + statement + "\n")
    with pytest.raises(ValueError, match="Nonliteral"):
        derive_time(config, Path(time.log.path), 1000)
