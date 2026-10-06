"""Deterministic, strict, atomic persistence of the two RMSD authorities."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import io
import json
import platform
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from mania.dataset_identity import DatasetTrajectoryIdentity
from mania.preprocessing.molecular_partner_metadata_io import (
    read_strict_json,
    write_atomic_text,
)
from mania.preprocessing.physical_time_execution import (
    PreprocessingConditionTemporalExecution,
)
from mania.preprocessing.physical_time_execution_io import (
    read_preprocessing_temporal_execution,
)
from mania.preprocessing.trajectory_rmsd import (
    CONTRACT_ID,
    METHOD,
    AtomSelection,
    Digest,
    RMSDAccumulator,
    RMSDSample,
    StrictModel,
    identity_digest,
)
from mania.software_identity import get_software_identity

TIMESERIES_FILENAME = "protein_rmsd_timeseries.csv"
MEASUREMENT_FILENAME = "protein_rmsd_measurement.json"
RMSD_ROLES = ("protein_rmsd_timeseries", "protein_rmsd_measurement")
COLUMNS = (
    "dataset_id",
    "system_id",
    "trajectory_id",
    "replica_id",
    "engine",
    "variant_id",
    "condition",
    "scope_id",
    "requested_sample_index",
    "requested_time_ps",
    "state",
    "runtime_frame_index",
    "source_frame_index",
    "prepared_frame_index",
    "actual_time_ps",
    "time_delta_ps",
    "rmsd_A",
    "reference_requested_sample_index",
    "selection_id",
    "measurement_contract_id",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def portable_member(root: Path, path: str) -> Path:
    from mania.artifact_inventory import _require_portable_path

    _require_portable_path(path, "member")
    target = root / path
    if any(p.is_symlink() for p in (target, *target.parents)) or (
        not target.resolve().is_relative_to(root.resolve())
    ):
        raise ValueError("Handoff member must be a contained physical regular file")
    return target


class FileBinding(StrictModel):
    artifact_id: str
    path: str | None
    byte_size: Annotated[int, Field(ge=0)]
    sha256: Digest
    format: str

    @model_validator(mode="after")
    def portable(self) -> FileBinding:
        if self.path is not None:
            from mania.artifact_inventory import _require_portable_path

            _require_portable_path(self.path, "binding path")
        if not self.artifact_id or not self.format:
            raise ValueError("Binding needs artifact ID and format")
        return self


def bind_file(path: Path, artifact_id: str, portable: str | None = None) -> FileBinding:
    return FileBinding(
        artifact_id=artifact_id,
        path=portable,
        byte_size=path.stat().st_size,
        sha256=file_sha256(path),
        format=path.suffix.removeprefix(".").lower(),
    )


class RMSDScope(StrictModel):
    scope_id: Literal["production"] = "production"
    stabilization_included: Literal[False] = False
    temporal_execution: FileBinding
    execution_binding: dict[str, Any]


class RMSDReference(StrictModel):
    policy: Literal["first_resolved_requested_production_sample"]
    sample: RMSDSample
    prepared_trajectory_sha256: Digest
    selected_coordinate_sha256: Digest


class RMSDTable(StrictModel):
    artifact_id: Literal["output:protein_rmsd_timeseries"]
    path: Literal["protein_rmsd_timeseries.csv"]
    byte_size: Annotated[int, Field(gt=0)]
    sha256: Digest
    row_count: Annotated[int, Field(gt=0)]


class RMSDCompleteness(StrictModel):
    evidence_state: Literal["complete"]
    temporal_coverage_state: Literal["complete", "partial"]
    requested_count: Annotated[int, Field(gt=0)]
    resolved_count: Annotated[int, Field(gt=0)]
    missing_count: Annotated[int, Field(ge=0)]
    measured_count: Annotated[int, Field(gt=0)]
    resolved_measurement_count_matches: Literal[True]
    missing_requested_sample_indexes: list[int]
    reference_first_request_missing: bool

    @field_validator("resolved_measurement_count_matches", mode="before")
    @classmethod
    def exact_completion_bool(cls, value: Any) -> bool:
        if value is not True:
            raise ValueError("RMSD completion requires an exact true JSON bool")
        return True


class RMSDSoftwareIdentity(StrictModel):
    software_name: Literal["MANIA"]
    distribution_name: Literal["mania-wania"]
    version: Annotated[str, Field(min_length=1)]
    commit_sha: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")] | None
    commit_source: Literal["git_checkout", "unavailable"]
    working_tree_status: Literal["clean", "dirty", "unavailable"]

    @model_validator(mode="after")
    def checkout_identity(self) -> RMSDSoftwareIdentity:
        if (self.commit_sha is None) != (self.commit_source == "unavailable"):
            raise ValueError("RMSD software checkout identity mismatch")
        return self


class RMSDImplementation(StrictModel):
    software_identity: dict[str, Any]
    python: str
    numpy: str
    mdanalysis: str | None
    algorithm_source_sha256: Digest
    persistence_source_sha256: Digest
    producer_build_sha256: Digest
    source_module: Literal["mania.preprocessing.trajectory_rmsd.fitted_rmsd"]

    @model_validator(mode="after")
    def build_identity(self) -> RMSDImplementation:
        RMSDSoftwareIdentity.model_validate(self.software_identity)
        if set(self.software_identity) != {
            "software_name",
            "distribution_name",
            "version",
            "commit_sha",
            "commit_source",
            "working_tree_status",
        }:
            raise ValueError("Software identity requires exact MANIA fields")
        if self.producer_build_sha256 != identity_digest(
            {
                "algorithm": self.algorithm_source_sha256,
                "persistence": self.persistence_source_sha256,
            }
        ):
            raise ValueError("Software source/build identity mismatch")
        return self


class RMSDMeasurement(StrictModel):
    schema_version: Literal["mania.protein_rmsd_measurement.v0.1"]
    kind: Literal["mania_protein_rmsd_measurement"]
    measurement_contract_id: Literal["mania.production_ca_rmsd.v1"]
    dataset_identity: DatasetTrajectoryIdentity
    execution_condition: str
    scope: RMSDScope
    reference: RMSDReference
    atom_selection: AtomSelection
    method: dict[str, Any]
    source_bindings: dict[str, FileBinding]
    implementation: RMSDImplementation
    table: RMSDTable
    completeness: RMSDCompleteness
    limitations: list[str]

    @model_validator(mode="after")
    def contract(self) -> RMSDMeasurement:
        expected = {
            **METHOD,
            "alignment_selection_id": self.atom_selection.selection_id,
            "measurement_selection_id": self.atom_selection.selection_id,
        }
        if (
            self.method != expected
            or type(self.method.get("automatic_drift_classification")) is not bool
        ):
            raise ValueError("RMSD method mismatch")
        if set(self.source_bindings) != {
            "topology",
            "mapping",
            "prepared_trajectory",
            "raw_trajectory",
            "preparation_report",
        }:
            raise ValueError(
                "RMSD requires exact topology/mapping/preparation bindings"
            )
        if self.reference.prepared_trajectory_sha256 != (
            self.source_bindings["prepared_trajectory"].sha256
        ):
            raise ValueError("Reference prepared trajectory lineage mismatch")
        if self.dataset_identity.condition not in (None, self.execution_condition):
            raise ValueError("RMSD replica/execution condition mismatch")
        if any(
            a.source_engine != self.dataset_identity.engine
            for a in self.atom_selection.atoms
        ):
            raise ValueError("Atom roster engine differs from Dataset replica")
        return self


def implementation_identity() -> RMSDImplementation:
    np = importlib.import_module("numpy")

    from mania.preprocessing import trajectory_rmsd
    from mania.preprocessing.scientific_runtime import get_mdanalysis_status

    algorithm = file_sha256(Path(trajectory_rmsd.__file__))
    persistence = file_sha256(Path(__file__))
    mda = get_mdanalysis_status().version
    return RMSDImplementation(
        software_identity=get_software_identity().to_dict(),
        python=platform.python_version(),
        numpy=np.__version__,
        mdanalysis=mda,
        algorithm_source_sha256=algorithm,
        persistence_source_sha256=persistence,
        producer_build_sha256=identity_digest(
            {"algorithm": algorithm, "persistence": persistence}
        ),
        source_module="mania.preprocessing.trajectory_rmsd.fitted_rmsd",
    )


def completeness(rows: list[RMSDSample]) -> RMSDCompleteness:
    missing = [s.requested_sample_index for s in rows if s.state == "missing"]
    resolved = len(rows) - len(missing)
    return RMSDCompleteness(
        evidence_state="complete",
        temporal_coverage_state="partial" if missing else "complete",
        requested_count=len(rows),
        resolved_count=resolved,
        missing_count=len(missing),
        measured_count=resolved,
        resolved_measurement_count_matches=True,
        missing_requested_sample_indexes=missing,
        reference_first_request_missing=rows[0].state == "missing",
    )


def timeseries_text(
    rows: list[RMSDSample],
    identity: DatasetTrajectoryIdentity,
    selection_id: str,
    reference_index: int,
) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(COLUMNS)
    for row in rows:
        values = {
            **identity.model_dump(mode="json"),
            **row.model_dump(mode="json"),
            "scope_id": "production",
            "selection_id": selection_id,
            "reference_requested_sample_index": reference_index,
            "measurement_contract_id": CONTRACT_ID,
        }
        writer.writerow(
            [
                ""
                if values[key] is None
                else format(values[key], ".17g")
                if type(values[key]) is float
                else values[key]
                for key in COLUMNS
            ]
        )
    return output.getvalue()


def atomic_json(path: Path, value: Any) -> None:
    result = write_atomic_text(
        json.dumps(
            value,
            sort_keys=True,
            indent=2,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n",
        path,
        overwrite=False,
    )
    if not result.passed:
        raise ValueError(f"Protected atomic artifact write failed: {path}")


def write_rmsd_evidence(
    accumulator: RMSDAccumulator,
    output_root: Path,
    *,
    source_bindings: dict[str, FileBinding],
    implementation: RMSDImplementation | None = None,
) -> RMSDMeasurement:
    rows = accumulator.finalize()
    csv_path = output_root / TIMESERIES_FILENAME
    json_path = output_root / MEASUREMENT_FILENAME
    if csv_path.exists() or json_path.exists():
        raise ValueError("Existing RMSD evidence is immutable")
    result = write_atomic_text(
        timeseries_text(
            rows,
            accumulator.identity,
            accumulator.selection.selection_id,
            accumulator.reference_sample.requested_sample_index,
        ),
        csv_path,
        overwrite=False,
    )
    if not result.passed:
        raise ValueError("Atomic RMSD CSV write failed")
    reference = next(s for s in rows if s.state == "resolved")
    assert accumulator.reference_coordinate_sha256 is not None
    metadata = RMSDMeasurement(
        schema_version="mania.protein_rmsd_measurement.v0.1",
        kind="mania_protein_rmsd_measurement",
        measurement_contract_id="mania.production_ca_rmsd.v1",
        dataset_identity=accumulator.identity,
        execution_condition=accumulator.binding.execution_condition,
        scope=RMSDScope(
            temporal_execution=bind_file(
                output_root / "temporal_execution.json",
                "output:temporal_execution",
                "temporal_execution.json",
            ),
            execution_binding=accumulator.binding.to_dict(),
        ),
        reference=RMSDReference(
            policy="first_resolved_requested_production_sample",
            sample=reference,
            prepared_trajectory_sha256=source_bindings["prepared_trajectory"].sha256,
            selected_coordinate_sha256=accumulator.reference_coordinate_sha256,
        ),
        atom_selection=accumulator.selection,
        method={
            **METHOD,
            "alignment_selection_id": accumulator.selection.selection_id,
            "measurement_selection_id": accumulator.selection.selection_id,
        },
        source_bindings=source_bindings,
        implementation=implementation or implementation_identity(),
        table=RMSDTable(
            artifact_id="output:protein_rmsd_timeseries",
            path="protein_rmsd_timeseries.csv",
            byte_size=csv_path.stat().st_size,
            sha256=file_sha256(csv_path),
            row_count=len(rows),
        ),
        completeness=completeness(rows),
        limitations=[
            "production_only; stabilization_excluded",
            "same_trajectory_fixed_reference",
            "scientific_pbc_status=unresolved",
            "source_coordinate_precision_retained_in_preparation_report",
            "no_automatic_drift_classification",
            "coordinates_required_for_recomputation",
        ],
    )
    atomic_json(json_path, metadata.model_dump(mode="json"))
    read_rmsd_evidence(output_root)
    return metadata


def validate_sample_roster(
    metadata: RMSDMeasurement,
    rows: list[RMSDSample],
    binding: PreprocessingConditionTemporalExecution,
) -> None:
    if metadata.scope.execution_binding != binding.to_dict() or (
        metadata.dataset_identity != binding.dataset_spec.identity
        or metadata.execution_condition != binding.execution_condition
    ):
        raise ValueError("RMSD temporal/replica lineage mismatch")
    samples: list[Any] = sorted(
        [
            *binding.sampling_plan.selected_samples,
            *binding.sampling_plan.missing_samples,
        ],
        key=lambda s: s.requested_sample_index,
    )
    if len(rows) != len(samples) or len(rows) != metadata.table.row_count:
        raise ValueError("Missing/duplicate RMSD rows")
    selected = {
        s.requested_sample_index: s for s in binding.sampling_plan.selected_samples
    }
    for row, sample in zip(rows, samples, strict=True):
        if (row.requested_sample_index, row.requested_time_ps) != (
            sample.requested_sample_index,
            sample.requested_time_ps,
        ):
            raise ValueError("Reordered/changed RMSD requested sample roster")
        resolved = selected.get(row.requested_sample_index)
        if (row.state == "resolved") != (resolved is not None):
            raise ValueError("RMSD missing/resolved partition mismatch")
        if resolved is not None and (
            row.runtime_frame_index != resolved.source_frame_index
            or row.prepared_frame_index != resolved.source_frame_index
            or row.actual_time_ps != resolved.actual_time_ps
            or row.time_delta_ps != resolved.time_delta_ps
        ):
            raise ValueError("Resolved RMSD frame/time lineage mismatch")
    if metadata.reference.sample != next(s for s in rows if s.state == "resolved"):
        raise ValueError("RMSD reference must be first resolved requested sample")
    if metadata.completeness != completeness(rows):
        raise ValueError("RMSD completion mismatch")


def read_rmsd_evidence(
    output_root: Path,
    *,
    expected_bindings: dict[str, FileBinding] | None = None,
    expected_implementation: RMSDImplementation | None = None,
) -> tuple[RMSDMeasurement, list[RMSDSample]]:
    raw_metadata = read_strict_json(output_root / MEASUREMENT_FILENAME)
    metadata = RMSDMeasurement.model_validate(raw_metadata)
    if metadata.model_dump(mode="json") != raw_metadata:
        raise ValueError("RMSD schema requires all exact fields without normalization")
    if expected_bindings is not None and metadata.source_bindings != expected_bindings:
        raise ValueError("Changed RMSD topology/mapping/prepared/source lineage")
    if expected_implementation is not None and (
        metadata.implementation != expected_implementation
    ):
        raise ValueError("Changed RMSD implementation/software identity")
    csv_path = portable_member(output_root, metadata.table.path)
    if csv_path.stat().st_size != metadata.table.byte_size or (
        file_sha256(csv_path) != metadata.table.sha256
    ):
        raise ValueError("RMSD CSV binding mismatch")
    rows = []
    with csv_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        if tuple(next(reader, ())) != COLUMNS:
            raise ValueError("RMSD CSV requires exact ordered columns")
        for fields in reader:
            if len(fields) != len(COLUMNS):
                raise ValueError("Malformed RMSD CSV row")
            data = dict(zip(COLUMNS, fields, strict=True))
            row: dict[str, Any] = {}
            for name in RMSDSample.model_fields:
                raw = data[name]
                if name == "state":
                    row[name] = raw
                elif not raw:
                    row[name] = None
                elif name.endswith("index"):
                    if not raw.isascii() or not raw.isdecimal() or str(int(raw)) != raw:
                        raise ValueError(
                            "RMSD indexes require canonical nonnegative ints"
                        )
                    row[name] = int(raw)
                else:
                    row[name] = float(raw)
            rows.append(RMSDSample.model_validate(row))
    expected_text = timeseries_text(
        rows,
        metadata.dataset_identity,
        metadata.atom_selection.selection_id,
        metadata.reference.sample.requested_sample_index,
    )
    if csv_path.read_bytes() != expected_text.encode("utf-8"):
        raise ValueError("RMSD CSV identity/contract/representation mismatch")
    temporal_binding = metadata.scope.temporal_execution
    temporal_path = portable_member(output_root, temporal_binding.path or "")
    if (
        bind_file(temporal_path, temporal_binding.artifact_id, temporal_binding.path)
        != temporal_binding
    ):
        raise ValueError("Changed RMSD temporal artifact binding")
    temporal = read_preprocessing_temporal_execution(temporal_path)
    matches = [
        b
        for b in temporal.bindings
        if b.execution_condition == metadata.execution_condition
    ]
    if len(matches) != 1:
        raise ValueError("RMSD requires exact unique temporal binding")
    validate_sample_roster(metadata, rows, matches[0])
    return metadata, rows


def build_production_rmsd_accumulators(
    runtime_loading: Any,
    temporal_execution: Any,
    *,
    mapping_path: Path,
    frame_map: tuple[int, ...],
) -> tuple[dict[str, RMSDAccumulator], dict[str, Any]]:
    from mania.canonical_residue_mapping_io import read_canonical_residue_mapping
    from mania.preprocessing.trajectory_rmsd import select_mapped_ca_atoms

    if temporal_execution is None or len(temporal_execution.bindings) != 1:
        raise ValueError("Production RMSD requires one authoritative Dataset binding")
    binding = temporal_execution.bindings[0]
    runtime = runtime_loading.runtime_load_result.condition_results[0]
    if runtime.condition_name != binding.execution_condition:
        raise ValueError("Production RMSD runtime/temporal identity mismatch")
    selection, atoms = select_mapped_ca_atoms(
        runtime.runtime.runtime_object,
        read_canonical_residue_mapping(mapping_path),
        binding.dataset_spec.identity.engine,
    )
    accumulator = RMSDAccumulator(binding, selection, source_frame_map=frame_map)
    return {binding.execution_condition: accumulator}, {
        binding.execution_condition: accumulator.selected_frame_observer(
            atoms, runtime.runtime.runtime_object
        ),
    }
