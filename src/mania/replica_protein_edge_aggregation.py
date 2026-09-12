"""Pure Stage 31.B statistics over sparse, canonical protein-edge tables.

Availability belongs to the accepted Stage 31.A group. Only an absent edge in
an available member contributes zero, privately in the statistical vector.
"""

from dataclasses import asdict, dataclass, field, fields
from decimal import Context, Decimal, localcontext
from math import isfinite

from mania.canonical_reference import CanonicalProteinReference
from mania.canonical_residue_mapping import (
    CanonicalResidueMappingRecord,
    canonical_residue_for_mapping,
)
from mania.canonical_window_tables import (
    CanonicalProteinEdgeWindowRow,
    CanonicalProteinEdgeWindowTable,
)
from mania.preprocessing.protein_edge_window_table import DatasetProteinEdgeWindowRow
from mania.replica_aggregation_contract import (
    REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID,
    REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256,
    CompatibleReplicaAggregationGroup,
    ReplicaAggregationGroupSpec,
    ReplicaAggregationMember,
)

CANONICAL_PROTEIN_EDGE_REPLICA_AGGREGATION_SCHEMA_VERSION = (
    "mania.canonical_protein_edge_replica_aggregation.v0.1"
)
CANONICAL_PROTEIN_EDGE_REPLICA_AGGREGATION_KIND = (
    "mania_canonical_protein_edge_replica_aggregation"
)

# An in-memory copy of the accepted packaged Stage 30.A reference keeps even
# direct aggregate-row construction free of resource I/O. The accepted model
# verifies the pinned digest and metadata; tests compare the entire payload to
# that packaged reference. This is not another mapping or reference authority.
_REFERENCE = CanonicalProteinReference(
    uniprot_accession="O95436",
    canonical_isoform_id="O95436-1",
    uniprot_entry_name="NPT2B_HUMAN",
    gene_symbol="SLC34A2",
    protein_name="Sodium-dependent phosphate transport protein 2B",
    organism_name="Homo sapiens",
    source_system="UniProtKB/Swiss-Prot",
    source_record_url="https://www.uniprot.org/uniprotkb/O95436-1/entry",
    uniprot_sequence_version=3,
    uniprot_sequence_last_updated="2010-11-30",
    uniprot_sequence_md5="16C21D07D36DC8B416EA72769F0B0280",
    sequence_sha256=REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256,
    sequence_length=690,
    sequence=(
        "MAPWPELGDAQPNPDKYLEGAAGQQPTAPDKSKETNKTDNTEAPVTKIELLPSYSTATLIDEPTEVDDPW"
        "NLPTLQDSGIKWSERDTKGKILCFFQGIGRLILLLGFLYFFVCSLDILSSAFQLVGGKMAGQFFSNSSI"
        "MSNPLLGLVIGVLVTVLVQSSSTSTSIVVSMVSSSLLTVRAAIPIIMGANIGTSITNTIVALMQVGDRSE"
        "FRRAFAGATVHDFFNWLSVLVLLPVEVATHYLEIITQLIVESFHFKNGEDAPDLLKVITKPFTKLIVQLDK"
        "KVISQIAMNDEKAKNKSLVKIWCKTFTNKTQINVTVPSTANCTSPSLCWTDGIQNWTMKNVTYKENIAKC"
        "QHIFVNFHLPDLAVGTILLILSLLVLCGCLIMIVKILGSVLKGQVATVIKKTINTDFPFPFAWLTGYLAIL"
        "VGAGMTFIVQSSSVFTSALTPLIGIGVITIERAYPLTLGSNIGTTTTAILAALASPGNALRSSLQIALCHFF"
        "FNISGILLWYPIPFTRLPIRMAKGLGNISAKYRWFAVFYLIIFFFLIPLTVFGLSLAGWRVLVGVGVPVVF"
        "IIILVLCLRLLQSRCPRVLPKKLQNWNFLPLWMRSLKPWDAVVSKFTGCFQMRCCCCCRVCCRACCLLCDCP"
        "KCCRCSKCCEDLEEAQEGQDVPVKAPETFDNITISREAQGEVPASDSKTECTAL"
    ),
)

_EdgeKey = tuple[int, int, str]
_ReplicaKey = tuple[str, str, str, str]


class ReplicaProteinEdgeAggregationError(ValueError):
    """Invalid canonical input, group binding or replica statistics."""


def _require_reference(value: object) -> None:
    for name, expected in (
        ("canonical_reference_id", REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID),
        (
            "canonical_reference_sequence_sha256",
            REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256,
        ),
    ):
        actual = getattr(value, name, None)
        if type(actual) is not str or actual != expected:
            raise ReplicaProteinEdgeAggregationError(
                f"{name} must match the pinned Stage 30 reference"
            )


def _require_group(group: CompatibleReplicaAggregationGroup) -> None:
    if type(group) is not CompatibleReplicaAggregationGroup:
        raise ReplicaProteinEdgeAggregationError(
            "group must be an exact CompatibleReplicaAggregationGroup"
        )
    if type(group.spec) is not ReplicaAggregationGroupSpec:
        raise ReplicaProteinEdgeAggregationError("group spec must have exact type")
    _require_reference(group.spec)
    if type(group.members) is not tuple or any(
        type(member) is not ReplicaAggregationMember for member in group.members
    ):
        raise ReplicaProteinEdgeAggregationError("group members must have exact types")
    for member in group.members:
        _require_reference(member)


def _canonical_endpoint(number: int, resname: str) -> None:
    try:
        residue = _REFERENCE.residue_at(number)
    except ValueError as exc:
        raise ReplicaProteinEdgeAggregationError(str(exc)) from None
    if type(resname) is not str or resname != residue.canonical_resname:
        raise ReplicaProteinEdgeAggregationError(
            "canonical resname must match the pinned reference"
        )


def _number(value: object, name: str) -> float:
    if not isinstance(value, bool) and isinstance(value, (int, float)):
        try:
            if isfinite(value) and value >= 0:
                return float(value)
        except OverflowError:
            pass
    raise ReplicaProteinEdgeAggregationError(f"{name} must be finite and non-negative")


@dataclass(frozen=True)
class CanonicalProteinEdgeReplicaAggregate:
    """One canonical edge with statistics over all available group members."""

    source_canonical_residue_number: int
    source_canonical_resname: str
    target_canonical_residue_number: int
    target_canonical_resname: str
    edge_type: str
    mean_occupancy: float
    std_occupancy: float | None
    median_occupancy: float
    n_replicates_available: int
    n_replicates_supporting: int
    support_fraction: float

    def __post_init__(self) -> None:
        _canonical_endpoint(
            self.source_canonical_residue_number, self.source_canonical_resname
        )
        _canonical_endpoint(
            self.target_canonical_residue_number, self.target_canonical_resname
        )
        if self.source_canonical_residue_number >= self.target_canonical_residue_number:
            raise ReplicaProteinEdgeAggregationError(
                "canonical edge requires source < target"
            )
        if (
            type(self.edge_type) is not str
            or not self.edge_type
            or self.edge_type != self.edge_type.strip()
        ):
            raise ReplicaProteinEdgeAggregationError(
                "edge_type must be a non-empty stripped string"
            )
        n, supporting = self.n_replicates_available, self.n_replicates_supporting
        if type(n) is not int or n <= 0:
            raise ReplicaProteinEdgeAggregationError(
                "n_replicates_available must be positive"
            )
        if type(supporting) is not int or not 1 <= supporting <= n:
            raise ReplicaProteinEdgeAggregationError(
                "n_replicates_supporting must be in 1..n_replicates_available"
            )
        for name in ("mean_occupancy", "median_occupancy", "support_fraction"):
            value = _number(getattr(self, name), name)
            if value > 1:
                raise ReplicaProteinEdgeAggregationError(f"{name} must be in [0, 1]")
            object.__setattr__(self, name, value)
        with localcontext(Context(prec=50)):
            fraction = float(Decimal(supporting) / Decimal(n))
        if self.support_fraction != fraction:
            raise ReplicaProteinEdgeAggregationError(
                "support_fraction must equal supporting/available"
            )
        if n == 1:
            if self.std_occupancy is not None:
                raise ReplicaProteinEdgeAggregationError(
                    "std_occupancy must be None for n=1"
                )
            if self.mean_occupancy != self.median_occupancy:
                raise ReplicaProteinEdgeAggregationError(
                    "mean must equal median for n=1"
                )
        else:
            object.__setattr__(
                self, "std_occupancy", _number(self.std_occupancy, "std_occupancy")
            )
        if self.mean_occupancy > self.support_fraction:
            raise ReplicaProteinEdgeAggregationError(
                "mean_occupancy cannot exceed support_fraction"
            )
        if n - supporting > n // 2 and self.median_occupancy != 0:
            raise ReplicaProteinEdgeAggregationError(
                "a majority of absent edges requires median zero"
            )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _edge_order(edge: CanonicalProteinEdgeReplicaAggregate) -> tuple[str, int, int]:
    return (
        edge.edge_type,
        edge.source_canonical_residue_number,
        edge.target_canonical_residue_number,
    )


@dataclass(frozen=True)
class CanonicalProteinEdgeReplicaAggregation:
    """Sparse aggregate for exactly one accepted group and requested window."""

    group: CompatibleReplicaAggregationGroup
    edge_count: int
    edges: tuple[CanonicalProteinEdgeReplicaAggregate, ...]
    schema_version: str = field(
        init=False, default=CANONICAL_PROTEIN_EDGE_REPLICA_AGGREGATION_SCHEMA_VERSION
    )
    kind: str = field(
        init=False, default=CANONICAL_PROTEIN_EDGE_REPLICA_AGGREGATION_KIND
    )
    canonical_reference_id: str = field(
        init=False, default=REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID
    )
    canonical_reference_sequence_sha256: str = field(
        init=False, default=REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256
    )

    def __post_init__(self) -> None:
        _require_group(self.group)
        _require_reference(self)
        if type(self.edges) is not tuple or any(
            type(edge) is not CanonicalProteinEdgeReplicaAggregate
            for edge in self.edges
        ):
            raise ReplicaProteinEdgeAggregationError(
                "edges must be a tuple of exact aggregate rows"
            )
        if type(self.edge_count) is not int or self.edge_count != len(self.edges):
            raise ReplicaProteinEdgeAggregationError("edge_count must equal len(edges)")
        order = [_edge_order(edge) for edge in self.edges]
        if len(set(order)) != len(order):
            raise ReplicaProteinEdgeAggregationError(
                "aggregate edge identities must be unique"
            )
        if order != sorted(order):
            raise ReplicaProteinEdgeAggregationError(
                "edges must follow deterministic canonical order"
            )
        for edge in self.edges:
            # Validate a private copy without changing a supplied frozen row.
            CanonicalProteinEdgeReplicaAggregate(**asdict(edge))
            if edge.n_replicates_available != self.group.available_replica_count:
                raise ReplicaProteinEdgeAggregationError(
                    "edge available count must match group"
                )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "canonical_reference_id": self.canonical_reference_id,
            "canonical_reference_sequence_sha256": (
                self.canonical_reference_sequence_sha256
            ),
            "group": self.group.to_dict(),
            "edge_count": self.edge_count,
            "edges": [edge.to_dict() for edge in self.edges],
        }


def _validate_row(row: CanonicalProteinEdgeWindowRow) -> None:
    # Stage 30.C's row validator reads its reference resource. Delegate the same
    # source evidence/metric checks to the accepted pure model on a private copy,
    # then use Stage 30.B's pure mapping validation with the pinned memory object.
    source = {
        item.name: getattr(row, item.name)
        for item in fields(DatasetProteinEdgeWindowRow)
    }
    if row.source_residue_index > row.target_residue_index:
        for suffix in ("residue_index", "chain_id", "resid", "resname"):
            left, right = f"source_{suffix}", f"target_{suffix}"
            source[left], source[right] = source[right], source[left]
    try:
        DatasetProteinEdgeWindowRow(**source)
        for prefix in ("source", "target"):
            record = CanonicalResidueMappingRecord(
                row.engine,
                getattr(row, f"{prefix}_chain_id"),
                getattr(row, f"{prefix}_resid"),
                getattr(row, f"{prefix}_resname"),
                getattr(row, f"{prefix}_canonical_residue_number"),
                getattr(row, f"{prefix}_canonical_resname"),
                "mapped",
            )
            canonical_residue_for_mapping(record, _REFERENCE)
    except (ValueError, TypeError, OverflowError):
        raise ReplicaProteinEdgeAggregationError(
            "invalid canonical protein-edge row"
        ) from None
    if row.source_canonical_residue_number >= row.target_canonical_residue_number:
        raise ReplicaProteinEdgeAggregationError(
            "canonical edge requires source < target"
        )


def _aggregate_edge(
    row: CanonicalProteinEdgeWindowRow, values: list[Decimal]
) -> CanonicalProteinEdgeReplicaAggregate:
    # Fixed context (including rounding/traps), sorted summation, no global state.
    with localcontext(Context(prec=50)):
        values = sorted(values)
        n = len(values)
        mean = sum(values, Decimal(0)) / Decimal(n)
        middle = n // 2
        median = (
            values[middle]
            if n % 2
            else (values[middle - 1] + values[middle]) / Decimal(2)
        )
        supporting = sum(value > 0 for value in values)
        variance = (
            sum(((value - mean) ** 2 for value in values), Decimal(0)) / Decimal(n - 1)
            if n >= 2
            else None
        )
        return CanonicalProteinEdgeReplicaAggregate(
            row.source_canonical_residue_number,
            row.source_canonical_resname,
            row.target_canonical_residue_number,
            row.target_canonical_resname,
            row.edge_type,
            float(mean),
            float(variance.sqrt()) if variance is not None else None,
            float(median),
            n,
            supporting,
            float(Decimal(supporting) / Decimal(n)),
        )


def aggregate_canonical_protein_edges_across_replicas(
    group: CompatibleReplicaAggregationGroup,
    table: CanonicalProteinEdgeWindowTable,
) -> CanonicalProteinEdgeReplicaAggregation:
    """Aggregate one group/window, ignoring other replica keys and window labels.

    Matching rows must agree with all member identity and requested-bound fields,
    including rows belonging to explicitly unavailable/excluded members.
    """
    _require_group(group)
    if type(table) is not CanonicalProteinEdgeWindowTable:
        raise ReplicaProteinEdgeAggregationError(
            "table must be an exact CanonicalProteinEdgeWindowTable"
        )
    _require_reference(table)
    for item in fields(table):
        if not item.init and getattr(table, item.name) != item.default:
            raise ReplicaProteinEdgeAggregationError(
                "fixed canonical table metadata must match"
            )
    if type(table.rows) is not tuple or any(
        type(row) is not CanonicalProteinEdgeWindowRow for row in table.rows
    ):
        raise ReplicaProteinEdgeAggregationError(
            "rows must be a tuple of exact canonical protein-edge rows"
        )
    identities = [row.row_identity for row in table.rows]
    if len(set(identities)) != len(identities):
        raise ReplicaProteinEdgeAggregationError("duplicate canonical row identity")
    order = [row.row_order for row in table.rows]
    if order != sorted(order):
        raise ReplicaProteinEdgeAggregationError(
            "input rows must follow deterministic canonical order"
        )
    members = {member.replica_key: member for member in group.members}
    window = group.spec.window
    observed: dict[_EdgeKey, dict[_ReplicaKey, Decimal]] = {}
    evidence: dict[_EdgeKey, CanonicalProteinEdgeWindowRow] = {}
    for row in table.rows:
        member = members.get(row.replica_key)
        if member is None or (row.window_id, row.window_index) != (
            window.window_id,
            window.window_index,
        ):
            continue
        _validate_row(row)
        for name in (
            "dataset_id",
            "system_id",
            "trajectory_id",
            "replica_id",
            "engine",
            "variant_id",
            "condition",
            "disulfide_state",
        ):
            if getattr(row, name) != getattr(member, name):
                raise ReplicaProteinEdgeAggregationError(
                    f"row {name} must match group member"
                )
        for name in ("requested_window_start_ns", "requested_window_end_ns"):
            if Decimal(str(getattr(row, name))) != Decimal(str(getattr(window, name))):
                raise ReplicaProteinEdgeAggregationError(
                    f"row {name} must match group window"
                )
        if row.right_endpoint_inclusive != window.right_endpoint_inclusive:
            raise ReplicaProteinEdgeAggregationError(
                "row right_endpoint_inclusive must match group window"
            )
        if member.availability_status != "available":
            continue
        key = (
            row.source_canonical_residue_number,
            row.target_canonical_residue_number,
            row.edge_type,
        )
        observed.setdefault(key, {})[row.replica_key] = Decimal(str(row.occupancy))
        evidence[key] = row
    available_keys = tuple(member.replica_key for member in group.available_members)
    edges = tuple(
        sorted(
            (
                _aggregate_edge(
                    evidence[key],
                    [
                        values.get(replica_key, Decimal(0))
                        for replica_key in available_keys
                    ],
                )
                for key, values in observed.items()
            ),
            key=_edge_order,
        )
    )
    return CanonicalProteinEdgeReplicaAggregation(group, len(edges), edges)


__all__ = [
    "CANONICAL_PROTEIN_EDGE_REPLICA_AGGREGATION_KIND",
    "CANONICAL_PROTEIN_EDGE_REPLICA_AGGREGATION_SCHEMA_VERSION",
    "CanonicalProteinEdgeReplicaAggregate",
    "CanonicalProteinEdgeReplicaAggregation",
    "ReplicaProteinEdgeAggregationError",
    "aggregate_canonical_protein_edges_across_replicas",
]
