"""Production-only, explicitly mapped C-alpha RMSD; no drift classification."""

from __future__ import annotations

import hashlib
import importlib
import json
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mania.canonical_residue_mapping import (
    CANONICAL_RESIDUE_MAPPING_REFERENCE_ID,
    CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256,
    CanonicalResidueMappingTable,
)
from mania.dataset_identity import DatasetTrajectoryIdentity
from mania.preprocessing.physical_time_execution import (
    PreprocessingConditionTemporalExecution,
)

CONTRACT_ID = "mania.production_ca_rmsd.v1"
ALGORITHM_ID = "kabsch_equal_weight_proper_rotation_float64_v1"
METHOD = {
    "algorithm_id": ALGORITHM_ID,
    "weights": "equal",
    "center": "arithmetic_centroid",
    "rotation": "proper_only",
    "reflection": "forbidden",
    "dtype": "float64",
    "coordinate_unit": "angstrom",
    "time_unit": "ps",
    "formula": "sqrt(sum_i(||X_centered_i @ R - reference_centered_i||^2)/N)",
    "convention": "row_vectors",
    "rank_policy": "at_least_3_atoms; rank_at_least_2; tolerance=eps*max(shape)*smax",
    "serializer_precision": ".17g",
    "nonfinite_policy": "fail",
    "automatic_drift_classification": False,
}
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Index = Annotated[int, Field(ge=0)]
Text = Annotated[str, Field(min_length=1)]


def identity_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, allow_inf_nan=False
    )


class SelectedAtom(StrictModel):
    canonical_residue_number: Annotated[int, Field(ge=1, le=690)]
    canonical_resname: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    source_engine: Literal["gromacs", "namd"]
    source_chain_id: str | None
    source_resid: Text
    source_resname: Text
    topology_residue_index: Index
    topology_atom_index: Index
    topology_atom_id: int | None
    atom_name: Literal["CA"] = "CA"
    element: Literal["C"] = "C"
    source_segid: str | None
    source_chainID: str | None


class AtomSelection(StrictModel):
    selection_id: Digest
    ordering: Literal["canonical_residue_number"] = "canonical_residue_number"
    atom_count: Annotated[int, Field(ge=3)]
    canonical_reference_id: str
    canonical_reference_sequence_sha256: Digest
    selected_identity_sha256: Digest
    not_represented_canonical_positions: list[int]
    atoms: list[SelectedAtom]

    @model_validator(mode="after")
    def validate_roster(self) -> AtomSelection:
        if self.canonical_reference_id != CANONICAL_RESIDUE_MAPPING_REFERENCE_ID or (
            self.canonical_reference_sequence_sha256
            != CANONICAL_RESIDUE_MAPPING_REFERENCE_SHA256
        ):
            raise ValueError("Canonical reference mismatch")
        positions = [a.canonical_residue_number for a in self.atoms]
        if positions != sorted(set(positions)) or len(positions) != self.atom_count:
            raise ValueError("Duplicate, reordered or incomplete canonical atom roster")
        if len({a.topology_atom_index for a in self.atoms}) != self.atom_count or (
            len({a.topology_residue_index for a in self.atoms}) != self.atom_count
        ):
            raise ValueError("Duplicate topology atom/residue identity")
        digest = identity_digest([a.model_dump(mode="json") for a in self.atoms])
        if digest != self.selection_id or digest != self.selected_identity_sha256:
            raise ValueError("Changed selection identity")
        if self.not_represented_canonical_positions != [
            i for i in range(1, 691) if i not in positions
        ]:
            raise ValueError("Absent canonical positions disagree with present roster")
        return self


def optional_attribute(obj: Any, name: str) -> Any:
    try:
        return getattr(obj, name)
    except (AttributeError, LookupError):
        return None


def validate_selection_mapping(
    selection: AtomSelection, mapping: CanonicalResidueMappingTable
) -> None:
    """Check every retained atom against its exact explicit source mapping."""
    from mania.canonical_reference_io import load_default_napi2b_canonical_reference
    from mania.canonical_residue_mapping import validate_canonical_residue_mapping_table

    validate_canonical_residue_mapping_table(
        mapping, reference=load_default_napi2b_canonical_reference()
    )
    records = {r.source_key: r for r in mapping.mappings}
    for atom in selection.atoms:
        mapped = records.get(
            (
                atom.source_engine,
                atom.source_chain_id,
                atom.source_resid,
                atom.source_resname,
            )
        )
        if (
            mapped is None
            or mapped.mapping_status != "mapped"
            or (
                mapped.canonical_residue_number != atom.canonical_residue_number
                or mapped.canonical_resname != atom.canonical_resname
                or atom.source_segid != atom.source_chain_id
            )
        ):
            raise ValueError(
                "RMSD atom roster disagrees with explicit canonical mapping"
            )


def atom_identity(atom: Any, mapped: Any, engine: str) -> SelectedAtom:
    residue = atom.residue
    segid = optional_attribute(residue, "segid") or None
    chain = optional_attribute(atom, "chainID") or None
    atom_id = optional_attribute(atom, "id")
    return SelectedAtom(
        canonical_residue_number=mapped.canonical_residue_number,
        canonical_resname=mapped.canonical_resname,
        source_engine=mapped.source_engine,
        source_chain_id=segid,
        source_resid=str(residue.resid),
        source_resname=str(residue.resname),
        topology_residue_index=int(residue.ix),
        topology_atom_index=int(atom.index),
        topology_atom_id=int(atom_id) if atom_id is not None else None,
        source_segid=segid,
        source_chainID=chain,
    )


def select_mapped_ca_atoms(
    universe: Any,
    mapping: CanonicalResidueMappingTable,
    engine: str,
) -> tuple[AtomSelection, tuple[Any, ...]]:
    """Bind every present protein residue by its complete source namespace."""
    records = {r.source_key: r for r in mapping.mappings}
    selected = []
    for residue in universe.select_atoms("protein").residues:
        key = (
            engine,
            optional_attribute(residue, "segid") or None,
            str(residue.resid),
            str(residue.resname),
        )
        mapped = records.get(key)
        if mapped is None or mapped.mapping_status != "mapped":
            raise ValueError(f"Incomplete explicit protein mapping: {key}")
        candidates = [a for a in residue.atoms if a.name == "CA"]
        if (
            len(candidates) != 1
            or str(optional_attribute(candidates[0], "element")).upper() != "C"
        ):
            raise ValueError("Every mapped present residue requires one CA carbon")
        atom = candidates[0]
        selected.append((atom_identity(atom, mapped, engine), atom))
    selected.sort(key=lambda pair: pair[0].canonical_residue_number)
    atoms = [pair[0] for pair in selected]
    digest = identity_digest([a.model_dump(mode="json") for a in atoms])
    positions = {a.canonical_residue_number for a in atoms}
    selection = AtomSelection(
        selection_id=digest,
        selected_identity_sha256=digest,
        atom_count=len(atoms),
        canonical_reference_id=mapping.canonical_reference_id,
        canonical_reference_sequence_sha256=mapping.canonical_reference_sequence_sha256,
        not_represented_canonical_positions=[
            i for i in range(1, 691) if i not in positions
        ],
        atoms=atoms,
    )
    validate_selection_mapping(selection, mapping)
    return selection, tuple(pair[1] for pair in selected)


def coordinates_float64(value: Any, atom_count: int) -> Any:
    np = importlib.import_module("numpy")
    try:
        xyz = np.array(value, dtype=np.float64, copy=True)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Malformed RMSD coordinates") from exc
    if xyz.shape != (atom_count, 3) or atom_count < 3 or not np.isfinite(xyz).all():
        raise ValueError("RMSD needs finite N x 3 coordinates and at least 3 atoms")
    centered = xyz - xyz.mean(axis=0)
    if not np.isfinite(centered).all() or np.linalg.matrix_rank(centered) < 2:
        raise ValueError("Rigid alignment requires at least two independent axes")
    return xyz


def fitted_rmsd(coordinates: Any, reference: Any) -> float:
    """SVD Kabsch with a determinant +1 row-vector rotation, in angstrom."""
    np = importlib.import_module("numpy")
    try:
        count = len(reference)
    except TypeError as exc:
        raise ValueError("Malformed RMSD reference") from exc
    x = coordinates_float64(coordinates, count)
    y = coordinates_float64(reference, count)
    x -= x.mean(axis=0)
    y -= y.mean(axis=0)
    u, _, vt = np.linalg.svd(x.T @ y)
    correction = np.eye(3, dtype=np.float64)
    correction[2, 2] = 1.0 if np.linalg.det(u @ vt) >= 0 else -1.0
    rotation = u @ correction @ vt
    delta = x @ rotation - y
    result = float(np.sqrt(np.sum(delta * delta, dtype=np.float64) / count))
    if not np.isfinite(result) or result < 0:
        raise ValueError("Nonfinite fitted RMSD")
    return result


class RMSDSample(StrictModel):
    requested_sample_index: Index
    requested_time_ps: Annotated[float, Field(ge=0)]
    state: Literal["missing", "resolved"]
    runtime_frame_index: Index | None
    source_frame_index: Index | None
    prepared_frame_index: Index | None
    actual_time_ps: Annotated[float, Field(ge=0)] | None
    time_delta_ps: float | None
    rmsd_A: Annotated[float, Field(ge=0)] | None

    @model_validator(mode="after")
    def state_partition(self) -> RMSDSample:
        fields = (
            self.runtime_frame_index,
            self.source_frame_index,
            self.prepared_frame_index,
            self.actual_time_ps,
            self.time_delta_ps,
            self.rmsd_A,
        )
        if self.state == "missing" and any(v is not None for v in fields):
            raise ValueError("Missing requested sample cannot contain a measurement")
        if self.state == "resolved" and any(v is None for v in fields):
            raise ValueError("Resolved sample requires complete measurement identity")
        if self.actual_time_ps is not None and (
            self.time_delta_ps != self.actual_time_ps - self.requested_time_ps
        ):
            raise ValueError("Actual/requested time delta mismatch")
        return self


@dataclass(frozen=True)
class SelectedFrameObservation:
    execution_condition: str
    sample: Any
    coordinates: Any
    atom_selection: AtomSelection


class RMSDAccumulator:
    """One fixed reference plus compact rows; never stores a coordinate trajectory."""

    def __init__(
        self,
        binding: PreprocessingConditionTemporalExecution,
        selection: AtomSelection,
        *,
        source_frame_map: tuple[int, ...],
    ) -> None:
        self.binding = binding
        self.selection = selection.model_copy(deep=True)
        self._fixed_selection = selection.model_copy(deep=True)
        plan = binding.sampling_plan
        if not plan.selected_samples:
            raise ValueError("RMSD requires at least one resolved production sample")
        if (
            len(source_frame_map) != plan.source_frame_count
            or any(type(i) is not int or i < 0 for i in source_frame_map)
            or list(source_frame_map) != sorted(set(source_frame_map))
        ):
            raise ValueError("Prepared-to-source frame map mismatch")
        self.source_frame_map = source_frame_map
        # The reference identity is fixed before traversal, never the first arrival.
        self.reference_sample = plan.selected_samples[0]
        self.reference: Any = None
        self.reference_coordinate_sha256: str | None = None
        self.rows: list[RMSDSample] = []
        self.resolved_count = 0

    def observe(self, observation: SelectedFrameObservation) -> None:
        if observation.execution_condition != self.binding.execution_condition or (
            observation.atom_selection != self._fixed_selection
            or self.selection != self._fixed_selection
        ):
            raise ValueError("Changed RMSD execution/atom roster identity")
        expected = self.binding.sampling_plan.selected_samples
        if self.resolved_count >= len(expected) or (
            observation.sample != expected[self.resolved_count]
        ):
            raise ValueError("Changed/reordered/duplicate RMSD sample roster")
        xyz = coordinates_float64(observation.coordinates, self.selection.atom_count)
        if self.reference is None:
            self.reference = xyz.copy()
            self.reference.setflags(write=False)
            self.reference_coordinate_sha256 = hashlib.sha256(
                xyz.astype("<f8", copy=False).tobytes(order="C")
            ).hexdigest()
        sample = observation.sample
        frame = sample.source_frame_index
        self.rows.append(
            RMSDSample(
                requested_sample_index=sample.requested_sample_index,
                requested_time_ps=sample.requested_time_ps,
                state="resolved",
                runtime_frame_index=frame,
                source_frame_index=self.source_frame_map[frame],
                prepared_frame_index=frame,
                actual_time_ps=sample.actual_time_ps,
                time_delta_ps=sample.time_delta_ps,
                rmsd_A=fitted_rmsd(xyz, self.reference),
            )
        )
        self.resolved_count += 1

    def finalize(self) -> list[RMSDSample]:
        if self.resolved_count != len(self.binding.sampling_plan.selected_samples):
            raise ValueError("Incomplete resolved RMSD observation roster")
        missing = [
            RMSDSample(
                requested_sample_index=s.requested_sample_index,
                requested_time_ps=s.requested_time_ps,
                state="missing",
                runtime_frame_index=None,
                source_frame_index=None,
                prepared_frame_index=None,
                actual_time_ps=None,
                time_delta_ps=None,
                rmsd_A=None,
            )
            for s in self.binding.sampling_plan.missing_samples
        ]
        return sorted([*self.rows, *missing], key=lambda s: s.requested_sample_index)

    def selected_frame_observer(
        self,
        atoms: tuple[Any, ...],
        universe: Any = None,
    ) -> Any:
        """Copy only the selected coordinates from the already loaded contact frame."""
        np = importlib.import_module("numpy")
        by_frame = {
            s.source_frame_index: s for s in self.binding.sampling_plan.selected_samples
        }

        topology_counts = (
            (len(universe.atoms), len(universe.residues))
            if universe is not None
            else None
        )

        def observer(condition: str, frame: int, actual_time: float | None) -> None:
            if topology_counts is not None and topology_counts != (
                len(universe.atoms),
                len(universe.residues),
            ):
                raise ValueError("Changed live topology atom/residue roster")
            sample = by_frame[frame]
            if actual_time != sample.actual_time_ps:
                raise ValueError("Loaded contact time differs from resolved sample")
            if any(
                a.name != "CA" or str(optional_attribute(a, "element")).upper() != "C"
                for a in atoms
            ):
                raise ValueError("Changed live CA carbon selection")
            if any(
                len(
                    [
                        candidate
                        for candidate in a.residue.atoms
                        if candidate.name == "CA"
                    ]
                )
                != 1
                for a in atoms
            ):
                raise ValueError("Changed live C-alpha candidate roster")
            current = [
                atom_identity(a, record, record.source_engine)
                for a, record in zip(atoms, self.selection.atoms, strict=True)
            ]
            if current != self.selection.atoms:
                raise ValueError("Changed live topology/atom identity")
            self.observe(
                SelectedFrameObservation(
                    condition,
                    sample,
                    [np.array(a.position, dtype=np.float64, copy=True) for a in atoms],
                    self.selection,
                )
            )

        return observer

    @property
    def identity(self) -> DatasetTrajectoryIdentity:
        return self.binding.dataset_spec.identity
