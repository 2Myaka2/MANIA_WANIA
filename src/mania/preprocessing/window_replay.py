"""Offline window replay from strict per-frame evidence and saved temporal plans."""

from dataclasses import dataclass
from pathlib import Path

from mania.canonical_window_tables import (
    CanonicalProteinEdgeWindowTable,
    CanonicalProteinGlycanWindowTable,
    CanonicalProteinLipidWindowTable,
    DatasetCanonicalResidueMappingBindings,
    build_canonical_protein_edge_window_table,
    build_canonical_protein_glycan_window_table,
    build_canonical_protein_lipid_window_table,
)
from mania.preprocessing.perframe_observations import read_perframe_observations
from mania.preprocessing.physical_time_execution import PreprocessingTemporalExecution
from mania.preprocessing.physical_time_execution_io import (
    read_preprocessing_temporal_execution,
)
from mania.preprocessing.protein_edge_window_execution import (
    build_preprocessing_protein_edge_window_source_table,
)
from mania.preprocessing.protein_edge_window_table import DatasetProteinEdgeWindowTable
from mania.preprocessing.specialized_contact_execution import (
    build_specialized_contact_source_tables,
)
from mania.preprocessing.specialized_contact_window_tables import (
    ProteinGlycanWindowTable,
    ProteinLipidWindowTable,
)


@dataclass(frozen=True)
class ReplayedWindowTables:
    protein: DatasetProteinEdgeWindowTable
    lipid: ProteinLipidWindowTable
    glycan: ProteinGlycanWindowTable
    canonical_protein: CanonicalProteinEdgeWindowTable | None = None
    canonical_lipid: CanonicalProteinLipidWindowTable | None = None
    canonical_glycan: CanonicalProteinGlycanWindowTable | None = None


def replay_window_tables(
    observation_dir: str | Path,
    temporal: PreprocessingTemporalExecution | str | Path,
    *,
    mapping_bindings: DatasetCanonicalResidueMappingBindings | None = None,
) -> ReplayedWindowTables:
    """Load once, aggregate all windows, optionally apply authoritative mapping.

    ``temporal`` is a retained execution or its JSON path, never a trajectory.
    Missing specialized metadata remains unavailable in the completion index;
    its empty source table must not be interpreted as negative observations.
    """
    execution = (
        read_preprocessing_temporal_execution(temporal)
        if isinstance(temporal, (str, Path))
        else temporal
    )
    saved = read_perframe_observations(observation_dir, execution)
    protein = build_preprocessing_protein_edge_window_source_table(
        execution, saved.protein
    )
    lipid, glycan = build_specialized_contact_source_tables(
        saved.specialized, execution
    )
    if mapping_bindings is None:
        return ReplayedWindowTables(protein, lipid, glycan)
    profiles = {
        b.dataset_spec.identity.replica_key: b.window_plan.boundary_profile
        for b in execution.bindings
    }
    return ReplayedWindowTables(
        protein,
        lipid,
        glycan,
        build_canonical_protein_edge_window_table(
            protein, mapping_bindings=mapping_bindings, boundary_profiles=profiles
        ),
        build_canonical_protein_lipid_window_table(
            lipid, mapping_bindings=mapping_bindings, boundary_profiles=profiles
        ),
        build_canonical_protein_glycan_window_table(
            glycan, mapping_bindings=mapping_bindings, boundary_profiles=profiles
        ),
    )
