"""Dataset v1.0 tabular publication models and deterministic, strict CSV I/O."""

import csv
import io
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import TypeAlias

from mania.dataset_release_contract import (
    CONTACT_DEFINITION_REQUIRED_PARAMETERS,
    DATASET_RELEASE_CONTRACT_SCHEMA_VERSION,
    PUBLICATION_TABLE_SPECS,
    REPLICA_KEY,
    PublicationColumnSpec,
    PublicationTableSpec,
)
from mania.preprocessing.molecular_partner_metadata_io import write_atomic_text

PublicationScalar: TypeAlias = str | int | Decimal | bool | None
PublicationRow: TypeAlias = tuple[PublicationScalar, ...]
METADATA_TABLE_IDS = (
    "systems",
    "simulations",
    "time_windows",
    "contact_definitions",
    "software_versions",
    "quality_control",
    "quality_control_findings",
    "quality_control_evidence",
    "nodes",
    "residue_annotations",
)


class DatasetReleaseCSVError(ValueError):
    """Invalid publication schema, logical row, or CSV operation."""


def publication_table_spec(table_id: str) -> PublicationTableSpec:
    """Return only an exact frozen Stage 33.A tabular publication descriptor."""
    for spec in PUBLICATION_TABLE_SPECS:
        if spec.table_id == table_id:
            return spec
    raise DatasetReleaseCSVError("Unsupported publication table ID")


def require_portable_publication_path(value: str) -> None:
    """Validate supplied evidence lexically, without resolving or rewriting it."""
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or any(p in ("", ".", "..") for p in value.split("/"))
        or any(c in value for c in "\\:~$%")
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise DatasetReleaseCSVError("Evidence must use a portable relative path")


def publication_number(value: object) -> Decimal:
    """Exact numeric value, independent of the caller's Decimal context.

    Binary floats become their exact decimal expansion (not rounded display
    strings). Reading that expansion restores the same logical value and float.
    Removing insignificant trailing zeros does not use Decimal arithmetic.
    """
    if type(value) is float:
        number = Decimal.from_float(value)
    elif type(value) is int:
        number = Decimal(value)
    elif isinstance(value, Decimal):
        number = value
    else:
        raise DatasetReleaseCSVError("Expected an integer, float or Decimal number")
    if not number.is_finite():
        raise DatasetReleaseCSVError("Publication numbers must be finite")
    sign, digits, exponent = number.as_tuple()
    if not isinstance(exponent, int):  # Nonfinite exponents were rejected above.
        raise DatasetReleaseCSVError("Invalid numeric exponent")
    if not number:
        return Decimal((sign, (0,), 0))
    while len(digits) > 1 and digits[-1] == 0:
        digits, exponent = digits[:-1], exponent + 1
    return Decimal((sign, digits, exponent))


def _scalar(
    value: object, column: PublicationColumnSpec, *, empty: bool
) -> PublicationScalar:
    if value is None:
        if not column.nullable:
            raise DatasetReleaseCSVError(f"{column.name} is not nullable")
        return None
    if column.logical_type == "number":
        return publication_number(value)
    expected = {"string": str, "integer": int, "boolean": bool}[column.logical_type]
    if type(value) is not expected:
        raise DatasetReleaseCSVError(f"Invalid logical type for {column.name}")
    if isinstance(value, str):
        if not value and not empty:
            raise DatasetReleaseCSVError(f"Empty text is ambiguous for {column.name}")
        if column.name.endswith("artifact_path"):
            require_portable_publication_path(value)
        return value
    if isinstance(value, (int, bool)):
        return value
    raise DatasetReleaseCSVError("Invalid scalar")


def _contact_scalar(record: Mapping[str, PublicationScalar]) -> None:
    kind = record["parameter_kind"]
    if kind not in (
        "string",
        "integer",
        "number",
        "boolean",
        "null",
        "object",
        "array",
    ):
        raise DatasetReleaseCSVError("Invalid contact parameter kind")
    if record["contact_layer"] not in (
        "protein-protein",
        "protein-lipid",
        "protein-glycan",
    ):
        raise DatasetReleaseCSVError("Invalid contact layer")
    for name in ("string", "integer", "number", "boolean"):
        if (record[f"{name}_value"] is not None) != (name == kind):
            raise DatasetReleaseCSVError("Contact scalar must match parameter_kind")


def _contact_trees(records: tuple[dict[str, PublicationScalar], ...]) -> None:
    """Validate the frozen parameter-tree encoding without evaluating definitions."""
    groups: dict[
        tuple[PublicationScalar, ...], dict[str, dict[str, PublicationScalar]]
    ] = {}
    for record in records:
        key = tuple(record[n] for n in (*REPLICA_KEY, "contact_definition_id"))
        path = record["parameter_path"]
        assert isinstance(path, str)
        if (path != "$" and not path.startswith("$/")) or re.search(r"~(?![01])", path):
            raise DatasetReleaseCSVError("Invalid escaped contact parameter path")
        groups.setdefault(key, {})[path] = record
    for tree in groups.values():
        root = tree.get("$")
        if (
            root is None
            or root["parameter_kind"] != "object"
            or any(
                f"$/{name}" not in tree
                for name in CONTACT_DEFINITION_REQUIRED_PARAMETERS
            )
        ):
            raise DatasetReleaseCSVError(
                "Contact tree lacks its required parameter roots"
            )
        children: dict[str, list[str]] = {}
        for path, record in tree.items():
            if any(
                record[n] != root[n]
                for n in (
                    "contact_layer",
                    "interaction_type",
                    "source_artifact_role",
                    "source_artifact_path",
                )
            ):
                raise DatasetReleaseCSVError(
                    "Contact definition identity/evidence disagrees"
                )
            if path == "$":
                continue
            parent, child = path.rsplit("/", 1)
            if parent not in tree or tree[parent]["parameter_kind"] not in (
                "object",
                "array",
            ):
                raise DatasetReleaseCSVError(
                    "Contact parameter must have a container parent"
                )
            children.setdefault(parent, []).append(child)
        for parent, names in children.items():
            if tree[parent]["parameter_kind"] == "array" and set(names) != {
                str(i) for i in range(len(names))
            }:
                raise DatasetReleaseCSVError("Contact array indexes must be contiguous")


@dataclass(frozen=True)
class DatasetReleaseTable:
    """Immutable scalar rows, normalized and sorted under the frozen descriptor.

    Empty tables are valid at this low level. Release builders enforce their
    stronger populations separately. No filesystem access occurs here.
    """

    spec: PublicationTableSpec
    rows: tuple[PublicationRow, ...]

    def __post_init__(self) -> None:
        if type(self.spec) is not PublicationTableSpec or (
            self.spec != publication_table_spec(self.spec.table_id)
        ):
            raise DatasetReleaseCSVError("Table must use the frozen Stage 33.A schema")
        if type(self.rows) is not tuple:
            raise DatasetReleaseCSVError("Rows must be an immutable tuple")
        names = tuple(c.name for c in self.spec.columns)
        normalized = []
        keys = set()
        for row in self.rows:
            if type(row) is not tuple or len(row) != len(names):
                raise DatasetReleaseCSVError("Row must have the exact column count")
            raw = dict(zip(names, row, strict=True))
            values = tuple(
                _scalar(
                    value,
                    column,
                    empty=(
                        self.table_id == "contact_definitions"
                        and column.name == "string_value"
                        and raw["parameter_kind"] == "string"
                    ),
                )
                for column, value in zip(self.spec.columns, row, strict=True)
            )
            record = dict(zip(names, values, strict=True))
            if self.table_id == "contact_definitions":
                _contact_scalar(record)
            key = tuple(record[n] for n in self.spec.primary_key)
            if key in keys:
                raise DatasetReleaseCSVError(f"Duplicate {self.table_id} primary key")
            keys.add(key)
            normalized.append(values)
        order = (
            (*REPLICA_KEY, "window_index", "window_id")
            if self.table_id == "time_windows"
            else self.spec.primary_key
        )
        indexes = tuple(names.index(n) for n in order)
        object.__setattr__(
            self,
            "rows",
            tuple(
                sorted(
                    normalized,
                    key=lambda r: tuple(r[i] for i in indexes),
                )
            ),
        )
        if self.table_id == "contact_definitions":
            _contact_trees(self.records())

    @property
    def table_id(self) -> str:
        return self.spec.table_id

    @property
    def relative_path(self) -> str:
        return self.spec.relative_path

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def schema_identity(self) -> str:
        return DATASET_RELEASE_CONTRACT_SCHEMA_VERSION

    def records(self) -> tuple[dict[str, PublicationScalar], ...]:
        """Independent dictionaries for audit/projection; stored rows stay immutable."""
        names = tuple(c.name for c in self.spec.columns)
        return tuple(dict(zip(names, r, strict=True)) for r in self.rows)

    def to_dict(self) -> dict[str, object]:
        """Deterministic audit view; numeric values remain exact Decimal scalars."""
        return dict(
            table_id=self.table_id,
            relative_path=self.relative_path,
            schema_identity=self.schema_identity,
            row_count=self.row_count,
            schema=self.spec.to_dict(),
            rows=list(self.records()),
        )


def build_publication_table(
    table_id: str,
    records: Iterable[Mapping[str, object]],
) -> DatasetReleaseTable:
    spec = publication_table_spec(table_id)
    names = tuple(c.name for c in spec.columns)
    rows = []
    for record in records:
        if set(record) != set(names):
            raise DatasetReleaseCSVError("Record fields must equal the frozen schema")
        rows.append(tuple(record[n] for n in names))
    # The constructor validates and narrows all supplied scalar values.
    return DatasetReleaseTable(spec, tuple(rows))  # type: ignore[arg-type]


def publication_csv_bytes(table: DatasetReleaseTable) -> bytes:
    if type(table) is not DatasetReleaseTable:
        raise DatasetReleaseCSVError("Expected a publication table")
    validated = DatasetReleaseTable(table.spec, table.rows)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=",", lineterminator="\n")
    writer.writerow(c.name for c in validated.spec.columns)
    for row in validated.rows:
        writer.writerow(
            ""
            if v is None
            else ("true" if v else "false")
            if type(v) is bool
            else str(v)
            for v in row
        )
    return stream.getvalue().encode("utf-8")


def _bound_path(table_id: str, path: str | Path) -> Path:
    expected = PurePosixPath(publication_table_spec(table_id).relative_path).parts
    target = Path(path)
    if ".." in target.parts or target.parts[-len(expected) :] != expected:
        raise DatasetReleaseCSVError("Path must end with the exact publication path")
    return target


def write_publication_csv(
    table: DatasetReleaseTable,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Atomically write just the requested artifact using repository conventions."""
    target = _bound_path(table.table_id, path)
    result = write_atomic_text(
        publication_csv_bytes(table).decode("utf-8"),
        target,
        overwrite=overwrite,
    )
    if not result.passed:
        raise DatasetReleaseCSVError(result.error)
    return target


def _decode(cell: str, column: PublicationColumnSpec, *, empty: bool) -> object:
    if cell == "" and column.nullable and not empty:
        return None
    if column.logical_type == "string":
        return cell
    if column.logical_type == "boolean" and cell in ("true", "false"):
        return cell == "true"
    if column.logical_type == "integer" and re.fullmatch(r"0|-?[1-9][0-9]*", cell):
        return int(cell)
    if column.logical_type == "number" and re.fullmatch(
        r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?",
        cell,
    ):
        return Decimal(cell)
    raise DatasetReleaseCSVError(f"Invalid CSV logical type for {column.name}")


def read_publication_csv(table_id: str, path: str | Path) -> DatasetReleaseTable:
    """Reconstruct a normalized model with exact headers, types, and unique PKs."""
    spec = publication_table_spec(table_id)
    try:
        with _bound_path(table_id, path).open(encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream, delimiter=",", strict=True)
            names = tuple(c.name for c in spec.columns)
            if tuple(next(reader, ())) != names:
                raise DatasetReleaseCSVError("CSV header must equal the frozen schema")
            records = []
            for cells in reader:
                if len(cells) != len(names):
                    raise DatasetReleaseCSVError("CSV row has the wrong column count")
                raw = dict(zip(names, cells, strict=True))
                records.append(
                    {
                        c.name: _decode(
                            v,
                            c,
                            empty=(
                                table_id == "contact_definitions"
                                and c.name == "string_value"
                                and raw["parameter_kind"] == "string"
                            ),
                        )
                        for c, v in zip(spec.columns, cells, strict=True)
                    }
                )
        return build_publication_table(table_id, records)
    except (OSError, UnicodeError, csv.Error, ArithmeticError) as exc:
        raise DatasetReleaseCSVError("Invalid or unreadable publication CSV") from exc
