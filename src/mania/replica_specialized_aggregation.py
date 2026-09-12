"""Pure Stage 31.C occupancy statistics with explicit partner correspondence.

Only canonical protein identity is shared. Topology-local molecular partners
require supplied correspondence across every available member before sparse
absence can contribute zero. Correspondence is aggregation evidence only.
"""

from dataclasses import asdict, dataclass, field, fields, replace
from decimal import Context, Decimal, localcontext
from math import isfinite
from typing import ClassVar, Generic, TypeVar

from mania.canonical_reference import CanonicalProteinReference
from mania.canonical_residue_mapping import (
    CanonicalResidueMappingRecord,
    canonical_residue_for_mapping,
)
from mania.canonical_window_tables import (
    CanonicalProteinGlycanWindowRow,
    CanonicalProteinGlycanWindowTable,
    CanonicalProteinLipidWindowRow,
    CanonicalProteinLipidWindowTable,
)
from mania.preprocessing.molecular_partner_entities import MolecularPartnerKind
from mania.preprocessing.specialized_contact_window_tables import (
    ProteinGlycanWindowRow,
    ProteinLipidWindowRow,
)
from mania.replica_aggregation_contract import (
    REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID,
    REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256,
    CompatibleReplicaAggregationGroup,
    ReplicaAggregationGroupSpec,
    ReplicaAggregationMember,
)

CANONICAL_PROTEIN_LIPID_REPLICA_AGGREGATION_SCHEMA_VERSION = (
    "mania.canonical_protein_lipid_replica_aggregation.v0.1"
)
CANONICAL_PROTEIN_LIPID_REPLICA_AGGREGATION_KIND = (
    "mania_canonical_protein_lipid_replica_aggregation"
)
CANONICAL_PROTEIN_GLYCAN_REPLICA_AGGREGATION_SCHEMA_VERSION = (
    "mania.canonical_protein_glycan_replica_aggregation.v0.1"
)
CANONICAL_PROTEIN_GLYCAN_REPLICA_AGGREGATION_KIND = (
    "mania_canonical_protein_glycan_replica_aggregation"
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

_ReplicaKey = tuple[str, str, str, str]
_CanonicalRow = CanonicalProteinLipidWindowRow | CanonicalProteinGlycanWindowRow
_CanonicalTable = CanonicalProteinLipidWindowTable | CanonicalProteinGlycanWindowTable


class ReplicaSpecializedAggregationError(ValueError):
    """Invalid canonical input, explicit correspondence or replica statistics."""


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
            raise ReplicaSpecializedAggregationError(
                f"{name} must match the pinned Stage 30 reference"
            )


def _require_group(group: CompatibleReplicaAggregationGroup) -> None:
    if type(group) is not CompatibleReplicaAggregationGroup:
        raise ReplicaSpecializedAggregationError(
            "group must be an exact CompatibleReplicaAggregationGroup"
        )
    if type(group.spec) is not ReplicaAggregationGroupSpec:
        raise ReplicaSpecializedAggregationError("group spec must have exact type")
    _require_reference(group.spec)
    if type(group.members) is not tuple or any(
        type(member) is not ReplicaAggregationMember for member in group.members
    ):
        raise ReplicaSpecializedAggregationError("group members must have exact types")
    for member in group.members:
        _require_reference(member)


def _canonical_endpoint(number: int, resname: str) -> None:
    try:
        residue = _REFERENCE.residue_at(number)
    except ValueError as exc:
        raise ReplicaSpecializedAggregationError(str(exc)) from None
    if type(resname) is not str or resname != residue.canonical_resname:
        raise ReplicaSpecializedAggregationError(
            "canonical resname must match the pinned reference"
        )


def _number(value: object, name: str) -> float:
    if not isinstance(value, bool) and isinstance(value, (int, float)):
        try:
            if isfinite(value) and value >= 0:
                return float(value)
        except OverflowError:
            pass
    raise ReplicaSpecializedAggregationError(f"{name} must be finite and non-negative")


def _text(value: object, name: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ReplicaSpecializedAggregationError(
            f"{name} must be a non-empty stripped string"
        )


@dataclass(frozen=True)
class ReplicaSpecializedPartnerCorrespondenceMember:
    """One explicitly supplied topology-local partner in one Dataset replica."""

    dataset_id: str
    system_id: str
    trajectory_id: str
    replica_id: str
    local_partner_id: str
    partner_name: str

    def __post_init__(self) -> None:
        for name in ("dataset_id", "system_id", "trajectory_id", "replica_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ReplicaSpecializedAggregationError(
                    f"{name} must be a non-empty string"
                )
            object.__setattr__(self, name, value.strip())
        for name in ("local_partner_id", "partner_name"):
            _text(getattr(self, name), name)

    @property
    def replica_key(self) -> _ReplicaKey:
        return self.dataset_id, self.system_id, self.trajectory_id, self.replica_id

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SpecializedPartnerCorrespondence:
    """Aggregation permission, never canonical or global molecular identity."""

    partner_correspondence_id: str
    partner_kind: MolecularPartnerKind
    partner_name: str
    members: tuple[ReplicaSpecializedPartnerCorrespondenceMember, ...]

    def __post_init__(self) -> None:
        _text(self.partner_correspondence_id, "partner_correspondence_id")
        _text(self.partner_name, "partner_name")
        if type(self.partner_kind) is not str or self.partner_kind not in (
            "lipid",
            "glycan",
        ):
            raise ReplicaSpecializedAggregationError(
                "partner_kind must be exactly lipid or glycan"
            )
        if type(self.members) is not tuple or any(
            type(member) is not ReplicaSpecializedPartnerCorrespondenceMember
            for member in self.members
        ):
            raise ReplicaSpecializedAggregationError(
                "members must be a tuple of exact correspondence members"
            )
        for member in self.members:
            if replace(member) != member:
                raise ReplicaSpecializedAggregationError(
                    "member Dataset identifiers must be stripped"
                )
            if member.partner_name != self.partner_name:
                raise ReplicaSpecializedAggregationError(
                    "member partner_name must exactly match correspondence"
                )
        keys = [member.replica_key for member in self.members]
        if len(set(keys)) != len(keys):
            raise ReplicaSpecializedAggregationError(
                "correspondence member replica keys must be unique"
            )
        if keys != sorted(keys):
            raise ReplicaSpecializedAggregationError(
                "members must follow deterministic replica order"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "partner_correspondence_id": self.partner_correspondence_id,
            "partner_kind": self.partner_kind,
            "partner_name": self.partner_name,
            "members": [member.to_dict() for member in self.members],
        }


@dataclass(frozen=True)
class SpecializedPartnerCorrespondences:
    """Explicit collection with exact ID lookup; names provide no lookup key."""

    correspondences: tuple[SpecializedPartnerCorrespondence, ...]

    def __post_init__(self) -> None:
        if type(self.correspondences) is not tuple or any(
            type(item) is not SpecializedPartnerCorrespondence
            for item in self.correspondences
        ):
            raise ReplicaSpecializedAggregationError(
                "correspondences must be a tuple of exact correspondences"
            )
        bindings = set()
        for item in self.correspondences:
            replace(item)
            for member in item.members:
                key = (item.partner_kind, member.replica_key, member.local_partner_id)
                if key in bindings:
                    raise ReplicaSpecializedAggregationError(
                        "local partner must belong to only one correspondence per kind"
                    )
                bindings.add(key)
        ids = [item.partner_correspondence_id for item in self.correspondences]
        if len(set(ids)) != len(ids):
            raise ReplicaSpecializedAggregationError(
                "correspondence IDs must be unique"
            )
        if ids != sorted(ids):
            raise ReplicaSpecializedAggregationError(
                "correspondences must follow deterministic ID order"
            )

    def lookup(
        self, partner_correspondence_id: str
    ) -> SpecializedPartnerCorrespondence:
        _text(partner_correspondence_id, "partner_correspondence_id")
        for item in self.correspondences:
            if item.partner_correspondence_id == partner_correspondence_id:
                return item
        raise ReplicaSpecializedAggregationError(
            "no explicit partner correspondence ID"
        )

    def to_dict(self) -> dict[str, object]:
        return {"correspondences": [item.to_dict() for item in self.correspondences]}


def _require_correspondences(
    group: CompatibleReplicaAggregationGroup,
    correspondences: SpecializedPartnerCorrespondences,
    partner_kind: MolecularPartnerKind,
) -> None:
    if type(correspondences) is not SpecializedPartnerCorrespondences:
        raise ReplicaSpecializedAggregationError(
            "correspondences must be an exact SpecializedPartnerCorrespondences"
        )
    replace(correspondences)
    available = {member.replica_key for member in group.available_members}
    if not available and correspondences.correspondences:
        raise ReplicaSpecializedAggregationError(
            "zero available replicas require empty correspondences"
        )
    for item in correspondences.correspondences:
        if item.partner_kind != partner_kind:
            raise ReplicaSpecializedAggregationError(
                "correspondence kind must match aggregation kind"
            )
        if {member.replica_key for member in item.members} != available:
            raise ReplicaSpecializedAggregationError(
                "correspondence members must cover exactly all available replica keys"
            )


@dataclass(frozen=True)
class _CanonicalSpecializedReplicaAggregate:
    canonical_residue_number: int
    canonical_resname: str
    partner_correspondence_id: str
    partner_name: str
    mean_occupancy: float
    std_occupancy: float | None
    median_occupancy: float
    n_replicates_available: int
    n_replicates_supporting: int
    support_fraction: float

    def __post_init__(self) -> None:
        _canonical_endpoint(self.canonical_residue_number, self.canonical_resname)
        _text(self.partner_correspondence_id, "partner_correspondence_id")
        _text(self.partner_name, "partner_name")
        n, supporting = self.n_replicates_available, self.n_replicates_supporting
        if type(n) is not int or n <= 0:
            raise ReplicaSpecializedAggregationError(
                "n_replicates_available must be positive"
            )
        if type(supporting) is not int or not 1 <= supporting <= n:
            raise ReplicaSpecializedAggregationError(
                "n_replicates_supporting must be in 1..n_replicates_available"
            )
        for name in ("mean_occupancy", "median_occupancy", "support_fraction"):
            value = _number(getattr(self, name), name)
            if value > 1:
                raise ReplicaSpecializedAggregationError(f"{name} must be in [0, 1]")
            object.__setattr__(self, name, value)
        with localcontext(Context(prec=50)):
            fraction = float(Decimal(supporting) / Decimal(n))
        if self.support_fraction != fraction:
            raise ReplicaSpecializedAggregationError(
                "support_fraction must equal supporting/available"
            )
        if n == 1:
            if self.std_occupancy is not None:
                raise ReplicaSpecializedAggregationError(
                    "std_occupancy must be None for n=1"
                )
            if self.mean_occupancy != self.median_occupancy:
                raise ReplicaSpecializedAggregationError(
                    "mean must equal median for n=1"
                )
        else:
            object.__setattr__(
                self, "std_occupancy", _number(self.std_occupancy, "std_occupancy")
            )
        if self.mean_occupancy > self.support_fraction:
            raise ReplicaSpecializedAggregationError(
                "mean_occupancy cannot exceed support_fraction"
            )
        if n - supporting > n // 2 and self.median_occupancy != 0:
            raise ReplicaSpecializedAggregationError(
                "a majority of absent pairs requires median zero"
            )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CanonicalProteinLipidReplicaAggregate(_CanonicalSpecializedReplicaAggregate):
    """One canonical protein/lipid correspondence with occupancy/support only."""


@dataclass(frozen=True)
class CanonicalProteinGlycanReplicaAggregate(_CanonicalSpecializedReplicaAggregate):
    """One canonical protein/glycan correspondence with occupancy/support only."""


_Aggregate = TypeVar(
    "_Aggregate",
    CanonicalProteinLipidReplicaAggregate,
    CanonicalProteinGlycanReplicaAggregate,
)


@dataclass(frozen=True)
class _SpecializedReplicaAggregation(Generic[_Aggregate]):
    group: CompatibleReplicaAggregationGroup
    correspondences: SpecializedPartnerCorrespondences
    row_count: int
    rows: tuple[_Aggregate, ...]
    schema_version: str = field(init=False)
    kind: str = field(init=False)
    canonical_reference_id: str = field(
        init=False, default=REPLICA_AGGREGATION_CANONICAL_REFERENCE_ID
    )
    canonical_reference_sequence_sha256: str = field(
        init=False, default=REPLICA_AGGREGATION_CANONICAL_REFERENCE_SHA256
    )
    _row_type: ClassVar[type[_CanonicalSpecializedReplicaAggregate]]
    _partner_kind: ClassVar[MolecularPartnerKind]

    def __post_init__(self) -> None:
        _require_group(self.group)
        _require_reference(self)
        _require_correspondences(self.group, self.correspondences, self._partner_kind)
        if type(self.rows) is not tuple or any(
            type(row) is not self._row_type for row in self.rows
        ):
            raise ReplicaSpecializedAggregationError(
                "rows must be a tuple of exact aggregate rows"
            )
        if type(self.row_count) is not int or self.row_count != len(self.rows):
            raise ReplicaSpecializedAggregationError("row_count must equal len(rows)")
        order = [
            (row.partner_correspondence_id, row.canonical_residue_number)
            for row in self.rows
        ]
        if len(set(order)) != len(order):
            raise ReplicaSpecializedAggregationError(
                "aggregate row identities must be unique"
            )
        if order != sorted(order):
            raise ReplicaSpecializedAggregationError(
                "rows must follow deterministic correspondence/residue order"
            )
        for row in self.rows:
            replace(row)
            item = self.correspondences.lookup(row.partner_correspondence_id)
            if row.partner_name != item.partner_name:
                raise ReplicaSpecializedAggregationError(
                    "aggregate partner_name must match correspondence"
                )
            if row.n_replicates_available != self.group.available_replica_count:
                raise ReplicaSpecializedAggregationError(
                    "row available count must match group"
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
            "correspondences": self.correspondences.to_dict(),
            "row_count": self.row_count,
            "rows": [row.to_dict() for row in self.rows],
        }


@dataclass(frozen=True)
class CanonicalProteinLipidReplicaAggregation(
    _SpecializedReplicaAggregation[CanonicalProteinLipidReplicaAggregate]
):
    """One compatible group/window and its explicit lipid correspondences."""

    schema_version: str = field(
        init=False, default=CANONICAL_PROTEIN_LIPID_REPLICA_AGGREGATION_SCHEMA_VERSION
    )
    kind: str = field(
        init=False, default=CANONICAL_PROTEIN_LIPID_REPLICA_AGGREGATION_KIND
    )
    _row_type = CanonicalProteinLipidReplicaAggregate
    _partner_kind = "lipid"


@dataclass(frozen=True)
class CanonicalProteinGlycanReplicaAggregation(
    _SpecializedReplicaAggregation[CanonicalProteinGlycanReplicaAggregate]
):
    """One compatible group/window and its explicit glycan correspondences."""

    schema_version: str = field(
        init=False, default=CANONICAL_PROTEIN_GLYCAN_REPLICA_AGGREGATION_SCHEMA_VERSION
    )
    kind: str = field(
        init=False, default=CANONICAL_PROTEIN_GLYCAN_REPLICA_AGGREGATION_KIND
    )
    _row_type = CanonicalProteinGlycanReplicaAggregate
    _partner_kind = "glycan"


def _validate_row(row: _CanonicalRow, partner_kind: MolecularPartnerKind) -> None:
    # Delegate retained metric/source evidence to the accepted pure validator on
    # a private copy. Canonical row reconstruction would read a reference file.
    source_type = (
        ProteinLipidWindowRow if partner_kind == "lipid" else ProteinGlycanWindowRow
    )
    source = {item.name: getattr(row, item.name) for item in fields(source_type)}
    try:
        source_type(**source)
        record = CanonicalResidueMappingRecord(
            row.engine,
            row.protein_chain_id,
            row.protein_resid,
            row.protein_resname,
            row.canonical_residue_number,
            row.canonical_resname,
            "mapped",
        )
        canonical_residue_for_mapping(record, _REFERENCE)
    except (ValueError, TypeError, OverflowError):
        raise ReplicaSpecializedAggregationError(
            "invalid canonical specialized row"
        ) from None


def _aggregate_pair(
    number: int,
    correspondence: SpecializedPartnerCorrespondence,
    values: list[Decimal],
    row_type: type[_Aggregate],
) -> _Aggregate:
    # Exact accepted 31.B formula; no public statistical helper exists there.
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
        return row_type(
            number,
            _REFERENCE.residue_at(number).canonical_resname,
            correspondence.partner_correspondence_id,
            correspondence.partner_name,
            float(mean),
            float(variance.sqrt()) if variance is not None else None,
            float(median),
            n,
            supporting,
            float(Decimal(supporting) / Decimal(n)),
        )


def _aggregate_rows(
    group: CompatibleReplicaAggregationGroup,
    table: _CanonicalTable,
    correspondences: SpecializedPartnerCorrespondences,
    partner_kind: MolecularPartnerKind,
    row_type: type[_Aggregate],
) -> tuple[_Aggregate, ...]:
    _require_group(group)
    # Fail incomplete correspondence before looking at sparse observations.
    _require_correspondences(group, correspondences, partner_kind)
    table_type = (
        CanonicalProteinLipidWindowTable
        if partner_kind == "lipid"
        else CanonicalProteinGlycanWindowTable
    )
    canonical_row_type = (
        CanonicalProteinLipidWindowRow
        if partner_kind == "lipid"
        else CanonicalProteinGlycanWindowRow
    )
    if type(table) is not table_type:
        raise ReplicaSpecializedAggregationError(
            f"table must be an exact {table_type.__name__}"
        )
    _require_reference(table)
    for item in fields(table):
        if not item.init and getattr(table, item.name) != item.default:
            raise ReplicaSpecializedAggregationError(
                "fixed canonical table metadata must match"
            )
    if type(table.rows) is not tuple or any(
        type(row) is not canonical_row_type for row in table.rows
    ):
        raise ReplicaSpecializedAggregationError(
            "rows must be a tuple of exact canonical specialized rows"
        )
    order = [row.row_order for row in table.rows]
    if order != sorted(order):
        raise ReplicaSpecializedAggregationError(
            "input rows must follow deterministic canonical order"
        )
    members = {member.replica_key: member for member in group.members}
    bindings = {
        (member.replica_key, member.local_partner_id): item
        for item in correspondences.correspondences
        for member in item.members
    }
    window = group.spec.window
    observed: dict[tuple[str, int], dict[_ReplicaKey, Decimal]] = {}
    seen = set()
    for row in table.rows:
        member = members.get(row.replica_key)
        if member is None or (row.window_id, row.window_index) != (
            window.window_id,
            window.window_index,
        ):
            continue
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
                raise ReplicaSpecializedAggregationError(
                    f"row {name} must match group member"
                )
        for name in ("requested_window_start_ns", "requested_window_end_ns"):
            if Decimal(str(getattr(row, name))) != Decimal(str(getattr(window, name))):
                raise ReplicaSpecializedAggregationError(
                    f"row {name} must match group window"
                )
        if row.right_endpoint_inclusive != window.right_endpoint_inclusive:
            raise ReplicaSpecializedAggregationError(
                "row right_endpoint_inclusive must match group window"
            )
        correspondence = bindings.get(
            (row.replica_key, getattr(row, f"{partner_kind}_partner_id"))
        )
        if correspondence is None:
            # Unbound partners and unavailable/excluded replicas add no evidence.
            continue
        _validate_row(row, partner_kind)
        if getattr(row, f"{partner_kind}_partner_name") != correspondence.partner_name:
            raise ReplicaSpecializedAggregationError(
                "row partner_name must exactly match correspondence"
            )
        identity = (
            row.replica_key,
            row.canonical_residue_number,
            getattr(row, f"{partner_kind}_partner_id"),
        )
        if identity in seen:
            raise ReplicaSpecializedAggregationError("duplicate relevant canonical row")
        seen.add(identity)
        key = (correspondence.partner_correspondence_id, row.canonical_residue_number)
        observed.setdefault(key, {})[row.replica_key] = Decimal(str(row.occupancy))
    available_keys = tuple(member.replica_key for member in group.available_members)
    return tuple(
        _aggregate_pair(
            number,
            correspondences.lookup(correspondence_id),
            [
                observed[(correspondence_id, number)].get(key, Decimal(0))
                for key in available_keys
            ],
            row_type,
        )
        for correspondence_id, number in sorted(observed)
    )


def aggregate_canonical_protein_lipid_across_replicas(
    group: CompatibleReplicaAggregationGroup,
    table: CanonicalProteinLipidWindowTable,
    *,
    correspondences: SpecializedPartnerCorrespondences,
) -> CanonicalProteinLipidReplicaAggregation:
    """Aggregate only explicit lipid correspondences for one group/window."""
    rows = _aggregate_rows(
        group, table, correspondences, "lipid", CanonicalProteinLipidReplicaAggregate
    )
    return CanonicalProteinLipidReplicaAggregation(
        group, correspondences, len(rows), rows
    )


def aggregate_canonical_protein_glycan_across_replicas(
    group: CompatibleReplicaAggregationGroup,
    table: CanonicalProteinGlycanWindowTable,
    *,
    correspondences: SpecializedPartnerCorrespondences,
) -> CanonicalProteinGlycanReplicaAggregation:
    """Aggregate only explicit glycan correspondences for one group/window."""
    rows = _aggregate_rows(
        group, table, correspondences, "glycan", CanonicalProteinGlycanReplicaAggregate
    )
    return CanonicalProteinGlycanReplicaAggregation(
        group, correspondences, len(rows), rows
    )


__all__ = [
    "CANONICAL_PROTEIN_LIPID_REPLICA_AGGREGATION_SCHEMA_VERSION",
    "CANONICAL_PROTEIN_LIPID_REPLICA_AGGREGATION_KIND",
    "CANONICAL_PROTEIN_GLYCAN_REPLICA_AGGREGATION_SCHEMA_VERSION",
    "CANONICAL_PROTEIN_GLYCAN_REPLICA_AGGREGATION_KIND",
    "ReplicaSpecializedPartnerCorrespondenceMember",
    "SpecializedPartnerCorrespondence",
    "SpecializedPartnerCorrespondences",
    "CanonicalProteinLipidReplicaAggregate",
    "CanonicalProteinGlycanReplicaAggregate",
    "CanonicalProteinLipidReplicaAggregation",
    "CanonicalProteinGlycanReplicaAggregation",
    "ReplicaSpecializedAggregationError",
    "aggregate_canonical_protein_lipid_across_replicas",
    "aggregate_canonical_protein_glycan_across_replicas",
]
