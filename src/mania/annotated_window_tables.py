"""Pure enrichment of accepted canonical tables by exact Dataset system key."""

from dataclasses import dataclass, field, fields
from typing import Any, ClassVar, TypeVar

from mania.biological_annotations import (
    BiologicalAnnotationError,
    CanonicalResidueBiologicalAnnotation,
    DatasetSystemBiologicalAnnotations,
    _text,
)
from mania.canonical_window_tables import (
    CanonicalProteinEdgeWindowRow,
    CanonicalProteinEdgeWindowTable,
    CanonicalProteinGlycanWindowRow,
    CanonicalProteinGlycanWindowTable,
    CanonicalProteinLipidWindowRow,
    CanonicalProteinLipidWindowTable,
)


@dataclass(frozen=True)
class DatasetBiologicalAnnotationBinding:
    dataset_id: str
    system_id: str
    annotations: DatasetSystemBiologicalAnnotations

    def __post_init__(self) -> None:
        _text(self.dataset_id, "dataset_id")
        _text(self.system_id, "system_id")
        if type(self.annotations) is not DatasetSystemBiologicalAnnotations:
            raise BiologicalAnnotationError("annotations must be exact system metadata")
        self.annotations.__post_init__()
        if self.system_key != (self.annotations.dataset_id, self.annotations.system_id):
            raise BiologicalAnnotationError(
                "Annotation Dataset system identity must match"
            )

    @property
    def system_key(self) -> tuple[str, str]:
        return self.dataset_id, self.system_id


@dataclass(frozen=True)
class DatasetBiologicalAnnotationBindings:
    bindings: tuple[DatasetBiologicalAnnotationBinding, ...]

    def __post_init__(self) -> None:
        if type(self.bindings) is not tuple or any(
            type(binding) is not DatasetBiologicalAnnotationBinding
            for binding in self.bindings
        ):
            raise BiologicalAnnotationError(
                "bindings must be a tuple of exact bindings"
            )
        for binding in self.bindings:
            binding.__post_init__()
        keys = [binding.system_key for binding in self.bindings]
        if len(set(keys)) != len(keys):
            raise BiologicalAnnotationError("Dataset system keys must be unique")
        if keys != sorted(keys):
            raise BiologicalAnnotationError("bindings must follow Dataset system order")

    def lookup(self, system_key: tuple[str, str]) -> DatasetSystemBiologicalAnnotations:
        if type(system_key) is not tuple or len(system_key) != 2:
            raise BiologicalAnnotationError(
                "system_key must be an exact two-field tuple"
            )
        for value in system_key:
            _text(value, "system key identifier")
        for binding in self.bindings:
            if binding.system_key == system_key:
                return binding.annotations
        raise BiologicalAnnotationError(
            "No complete annotation binding for Dataset system"
        )


BIOLOGICAL_ANNOTATION_COLUMNS = (
    "is_ecd",
    "is_mx35_region",
    "is_glycosylation_site",
    "glycosylation_present_in_topology",
    "glycan_name",
    "glycosylation_source",
    "glycosylation_verifier",
    "is_disulfide_variant_site",
    "is_cysteine_variant_site",
)


def _validate_annotations(row: Any, prefixes: tuple[str, ...]) -> None:
    for prefix in prefixes:
        CanonicalResidueBiologicalAnnotation(
            getattr(row, f"{prefix}canonical_residue_number"),
            getattr(row, f"{prefix}canonical_resname"),
            **{
                name: getattr(row, f"{prefix}{name}")
                for name in BIOLOGICAL_ANNOTATION_COLUMNS
            },
        )


ANNOTATED_CANONICAL_PROTEIN_EDGE_WINDOW_CSV_FILENAME = (
    "protein_edges_by_window_canonical_annotated.csv"
)


@dataclass(frozen=True)
class AnnotatedCanonicalProteinEdgeWindowRow(CanonicalProteinEdgeWindowRow):
    source_is_ecd: bool
    source_is_mx35_region: bool
    source_is_glycosylation_site: bool
    source_glycosylation_present_in_topology: bool | None
    source_glycan_name: str | None
    source_glycosylation_source: str | None
    source_glycosylation_verifier: str | None
    source_is_disulfide_variant_site: bool
    source_is_cysteine_variant_site: bool
    target_is_ecd: bool
    target_is_mx35_region: bool
    target_is_glycosylation_site: bool
    target_glycosylation_present_in_topology: bool | None
    target_glycan_name: str | None
    target_glycosylation_source: str | None
    target_glycosylation_verifier: str | None
    target_is_disulfide_variant_site: bool
    target_is_cysteine_variant_site: bool

    def __post_init__(self) -> None:
        super().__post_init__()
        _validate_annotations(self, ("source_", "target_"))


@dataclass(frozen=True)
class AnnotatedCanonicalProteinEdgeWindowTable(CanonicalProteinEdgeWindowTable):
    rows: tuple[AnnotatedCanonicalProteinEdgeWindowRow, ...]
    schema_version: str = field(
        init=False, default="mania.canonical_annotated_protein_edges_by_window.v0.1"
    )
    kind: str = field(
        init=False, default="mania_canonical_annotated_protein_edges_by_window"
    )
    _row_type: ClassVar[type[CanonicalProteinEdgeWindowRow]] = (
        AnnotatedCanonicalProteinEdgeWindowRow
    )


ANNOTATED_CANONICAL_PROTEIN_LIPID_WINDOW_CSV_FILENAME = (
    "protein_lipid_contacts_by_window_canonical_annotated.csv"
)


@dataclass(frozen=True)
class AnnotatedCanonicalProteinLipidWindowRow(CanonicalProteinLipidWindowRow):
    is_ecd: bool
    is_mx35_region: bool
    is_glycosylation_site: bool
    glycosylation_present_in_topology: bool | None
    glycan_name: str | None
    glycosylation_source: str | None
    glycosylation_verifier: str | None
    is_disulfide_variant_site: bool
    is_cysteine_variant_site: bool

    def __post_init__(self) -> None:
        super().__post_init__()
        _validate_annotations(self, ("",))


@dataclass(frozen=True)
class AnnotatedCanonicalProteinLipidWindowTable(CanonicalProteinLipidWindowTable):
    rows: tuple[AnnotatedCanonicalProteinLipidWindowRow, ...]
    schema_version: str = field(
        init=False,
        default="mania.canonical_annotated_protein_lipid_contacts_by_window.v0.1",
    )
    kind: str = field(
        init=False, default="mania_canonical_annotated_protein_lipid_contacts_by_window"
    )
    _row_type: ClassVar[type[CanonicalProteinLipidWindowRow]] = (
        AnnotatedCanonicalProteinLipidWindowRow
    )


ANNOTATED_CANONICAL_PROTEIN_GLYCAN_WINDOW_CSV_FILENAME = (
    "protein_glycan_contacts_by_window_canonical_annotated.csv"
)


@dataclass(frozen=True)
class AnnotatedCanonicalProteinGlycanWindowRow(CanonicalProteinGlycanWindowRow):
    is_ecd: bool
    is_mx35_region: bool
    is_glycosylation_site: bool
    glycosylation_present_in_topology: bool | None
    glycan_name: str | None
    glycosylation_source: str | None
    glycosylation_verifier: str | None
    is_disulfide_variant_site: bool
    is_cysteine_variant_site: bool

    def __post_init__(self) -> None:
        super().__post_init__()
        _validate_annotations(self, ("",))


@dataclass(frozen=True)
class AnnotatedCanonicalProteinGlycanWindowTable(CanonicalProteinGlycanWindowTable):
    rows: tuple[AnnotatedCanonicalProteinGlycanWindowRow, ...]
    schema_version: str = field(
        init=False,
        default="mania.canonical_annotated_protein_glycan_contacts_by_window.v0.1",
    )
    kind: str = field(
        init=False,
        default="mania_canonical_annotated_protein_glycan_contacts_by_window",
    )
    _row_type: ClassVar[type[CanonicalProteinGlycanWindowRow]] = (
        AnnotatedCanonicalProteinGlycanWindowRow
    )


_Row = TypeVar(
    "_Row",
    AnnotatedCanonicalProteinEdgeWindowRow,
    AnnotatedCanonicalProteinLipidWindowRow,
    AnnotatedCanonicalProteinGlycanWindowRow,
)


def _build_rows(
    canonical_table: Any,
    table_type: type[Any],
    row_type: type[_Row],
    annotation_bindings: DatasetBiologicalAnnotationBindings,
) -> tuple[_Row, ...]:
    if type(canonical_table) is not table_type:
        raise BiologicalAnnotationError(
            "canonical_table must be exact canonical table type"
        )
    if type(annotation_bindings) is not DatasetBiologicalAnnotationBindings:
        raise BiologicalAnnotationError(
            "annotation_bindings must be exact binding collection"
        )
    canonical_table.__post_init__()
    annotation_bindings.__post_init__()
    rows = []
    for row in canonical_table.rows:
        metadata = annotation_bindings.lookup((row.dataset_id, row.system_id))
        values = {item.name: getattr(row, item.name) for item in fields(row)}
        prefixes = (
            ("source_", "target_")
            if table_type is CanonicalProteinEdgeWindowTable
            else ("",)
        )
        for prefix in prefixes:
            annotation = metadata.annotation_for_residue(
                getattr(row, f"{prefix}canonical_residue_number")
            )
            values.update(
                {
                    f"{prefix}{name}": getattr(annotation, name)
                    for name in BIOLOGICAL_ANNOTATION_COLUMNS
                }
            )
        rows.append(row_type(**values))
    return tuple(rows)


def build_annotated_canonical_protein_edge_window_table(
    canonical_table: CanonicalProteinEdgeWindowTable,
    *,
    annotation_bindings: DatasetBiologicalAnnotationBindings,
) -> AnnotatedCanonicalProteinEdgeWindowTable:
    return AnnotatedCanonicalProteinEdgeWindowTable(
        _build_rows(
            canonical_table,
            CanonicalProteinEdgeWindowTable,
            AnnotatedCanonicalProteinEdgeWindowRow,
            annotation_bindings,
        )
    )


def build_annotated_canonical_protein_lipid_window_table(
    canonical_table: CanonicalProteinLipidWindowTable,
    *,
    annotation_bindings: DatasetBiologicalAnnotationBindings,
) -> AnnotatedCanonicalProteinLipidWindowTable:
    return AnnotatedCanonicalProteinLipidWindowTable(
        _build_rows(
            canonical_table,
            CanonicalProteinLipidWindowTable,
            AnnotatedCanonicalProteinLipidWindowRow,
            annotation_bindings,
        )
    )


def build_annotated_canonical_protein_glycan_window_table(
    canonical_table: CanonicalProteinGlycanWindowTable,
    *,
    annotation_bindings: DatasetBiologicalAnnotationBindings,
) -> AnnotatedCanonicalProteinGlycanWindowTable:
    return AnnotatedCanonicalProteinGlycanWindowTable(
        _build_rows(
            canonical_table,
            CanonicalProteinGlycanWindowTable,
            AnnotatedCanonicalProteinGlycanWindowRow,
            annotation_bindings,
        )
    )
