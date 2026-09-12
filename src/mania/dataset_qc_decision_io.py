"""Authoritative decision JSON uses accepted 32.A models without new fields."""

from pathlib import Path

from mania._dataset_qc_json import model_bytes, read_model, write_model
from mania.dataset_qc_contract import DatasetQCDecisionSet
from mania.preprocessing.molecular_partner_metadata_io import (
    SpecializedArtifactWriteResult,
)

DATASET_QC_DECISION_SET_FILENAME = "dataset_qc_decision_set.json"


def read_dataset_qc_decision_set(path: str | Path) -> DatasetQCDecisionSet:
    return read_model(path, DatasetQCDecisionSet)


def dataset_qc_decision_set_bytes(decisions: DatasetQCDecisionSet) -> bytes:
    return model_bytes(decisions, DatasetQCDecisionSet)


def write_dataset_qc_decision_set(
    decisions: DatasetQCDecisionSet,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> SpecializedArtifactWriteResult:
    return write_model(decisions, DatasetQCDecisionSet, path, overwrite=overwrite)
