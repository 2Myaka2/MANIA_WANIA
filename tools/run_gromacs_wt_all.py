"""Source-only WT launcher. Exit 3 means coordinates/production remain pending."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Support both direct CLI execution and repository test imports.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import gromacs_wt_source_attestation as attestation  # noqa: E402
from gromacs_wt_runtime import (  # noqa: E402
    PENDING,
    REPRESENTATIVE,
    RUNTIME,
    SELECTIONS,
    discover,
    inventory,
    load_authority,
    require,
)

REPO = Path(__file__).resolve().parents[1]
CHECKPOINT_BYTES = 1024 * 1024  # Metadata-only reserve; never a preparation estimate.


def overlap(a: Path, b: Path) -> bool:
    return a.is_relative_to(b) or b.is_relative_to(a)


def roots(source: Path, output: Path, runtime: Path) -> tuple[Path, Path]:
    source, output = source.absolute(), output.absolute()
    require(
        source.resolve() == source and output.resolve() == output,
        "Source/output roots must not contain symlinks or traversal",
    )
    require(source.is_dir(), f"Missing source directory: {source}")
    require(not overlap(source, output), "Source and output roots must be disjoint")
    require(not overlap(output, runtime), "Output overlaps runtime authority")
    require(not REPO.is_relative_to(output), "Output must not contain the repository")
    for name in (".git", "src", "tools", "tests", "production", "docs", "configs"):
        require(not overlap(output, REPO / name), f"Protected repository path: {name}")
    require(not overlap(source, runtime), "Source overlaps runtime authority")
    require(
        os.access(source, os.R_OK | os.W_OK | os.X_OK),
        f"Source directory must be readable/writable: {source}",
    )
    # Source remains untouched: access check only, no offset/cache/write probes.
    ancestor = output
    while not ancestor.exists():
        ancestor = ancestor.parent
    require(
        ancestor.is_dir() and os.access(ancestor, os.W_OK | os.X_OK),
        f"Output parent not writable: {ancestor}",
    )
    return source, output


def environment(source: Path, output: Path, minimum: int) -> dict[str, Any]:
    require(sys.version_info >= (3, 11), "Python >= 3.11 required before installation")
    require(minimum >= CHECKPOINT_BYTES, "Metadata reserve must be at least 1 MiB")
    ancestor = output
    while not ancestor.exists():
        ancestor = ancestor.parent
    free = shutil.disk_usage(ancestor).free
    require(
        free >= minimum,
        f"Insufficient output filesystem storage: {free} < {minimum} bytes",
    )
    return dict(
        python=sys.version.split()[0],
        source_free_bytes=shutil.disk_usage(source).free,
        output_free_bytes=free,
        required_checkpoint_free_bytes=minimum,
        storage_budget_scope="source_attestation_metadata_only",
        prepared_storage_format="OPEN",
        production_storage_sufficiency="NOT_MEASURED",
        warnings=[
            "Google Drive mounted storage is not automatically "
            "a local high-I/O filesystem.",
            "Use local Colab runtime storage; "
            "measure raw + prepared + temporary peak use.",
            "No hard links, trajectory copies or coordinate conversion are performed.",
        ],
    )


def batch(
    source: Path,
    output: Path,
    *,
    runtime: Path = RUNTIME,
    representative: bool = False,
    preflight_only: bool = False,
    minimum: int = CHECKPOINT_BYTES,
    prompt: Callable[[str], str] = input,
) -> int:
    """Continuation boundary: source evidence only, never a production dispatcher."""
    try:
        source, output = roots(source, output, runtime)
        env = environment(source, output, minimum)
        for warning in env["warnings"]:
            print(f"Storage note: {warning}", file=sys.stderr)
        authority = load_authority(runtime)
        authority_inventory = inventory(runtime)
        selections = (REPRESENTATIVE,) if representative else SELECTIONS
        # Representative mode is always discovery only: no approval or XTC hashes.
        rows = discover(source, authority, selections)
        for row in rows:
            print(
                json.dumps(
                    dict(
                        trajectory_id=row.trajectory_id,
                        xtc=row.expected_xtc_path,
                        tpr=row.tpr.path,
                        mdp=row.mdp.path,
                        logs=[i.path for i in row.logs],
                        unresolved_discrepancies=row.unresolved_discrepancies,
                    ),
                    sort_keys=True,
                )
            )
        if representative or preflight_only:
            print(
                json.dumps(
                    dict(
                        source_status="discovery_only",
                        selections=list(selections),
                        coordinate_backend_status=PENDING,
                        production_launched=False,
                        environment=env,
                    ),
                    sort_keys=True,
                )
            )
            print(
                "Source discovery only; no approval or coordinate validation. "
                "Production pending."
            )
            return 3
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO,
            text=True,
        ).strip()
        approval = output / "gromacs_source_attestation.json"
        if approval.exists() or approval.is_symlink():
            attestation.verify(
                approval,
                source=source,
                rows=rows,
                authority_inventory=authority_inventory,
                repository_head=head,
            )
            print("Existing source approval verified; no prompt.")
        else:
            require(
                not output.exists() or not any(output.iterdir()),
                "Unrecognized/nonempty output directory; "
                "choose a fresh output directory",
            )
            print(attestation.STATEMENT)
            print(
                "Scope: source_run_correspondence_only. "
                "Hashes are computed automatically."
            )
            print(
                "All XTC transfers must be complete before approving; "
                "hashing reads every byte."
            )
            reviewer = prompt("Reviewer name: ").strip()
            note = prompt("Review note: ").strip()
            answer = (
                prompt("Confirm source/run correspondence only? [y/N]: ")
                .strip()
                .lower()
            )
            require(answer == "y", "Source approval declined; no attestation written")
            require(bool(reviewer) and bool(note), "Named reviewer/note required")
            # Recheck small authority after prompting, before XTC hashing.
            require(
                inventory(runtime) == authority_inventory, "Runtime authority changed"
            )
            discover(source, authority, selections)
            output.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=output) as stream:
                stream.write(b"writable output probe")
            attestation.save(
                approval,
                source=source,
                rows=rows,
                reviewer=reviewer,
                review_note=note,
                repository_head=head,
                authority_inventory=authority_inventory,
            )
        require(inventory(runtime) == authority_inventory, "Runtime authority changed")
        print(
            json.dumps(
                dict(
                    source_status="attested",
                    coordinate_backend_status=PENDING,
                    production_launched=False,
                    attestation_path=str(approval),
                    environment=env,
                ),
                sort_keys=True,
            )
        )
        print(
            "Source-attestation checkpoint only. "
            "Coordinate preparation and contact production "
            "are pending real XTC validation. Exit status 3; no production success."
        )
        return 3
    except (ValueError, OSError, EOFError, subprocess.SubprocessError) as exc:
        print(
            json.dumps(
                dict(
                    source_status="failed",
                    error=str(exc),
                    coordinate_backend_status=PENDING,
                    production_launched=False,
                ),
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", type=Path, help="WT root with literal NORM/TUMOR replica folders"
    )
    parser.add_argument(
        "output", type=Path, help="Separate source-approval output directory"
    )
    parser.add_argument(
        "--representative-preflight",
        action="store_true",
        help="Developer only: TUMOR/r2 discovery; never approve or hash XTC",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Six-source discovery only; no prompt or XTC hashes",
    )
    parser.add_argument(
        "--minimum-free-bytes",
        type=int,
        default=CHECKPOINT_BYTES,
        help="Output metadata reserve only; NOT a production storage estimate",
    )
    args = parser.parse_args()
    return batch(
        args.source,
        args.output,
        representative=args.representative_preflight,
        preflight_only=args.preflight_only,
        minimum=args.minimum_free_bytes,
    )


if __name__ == "__main__":
    raise SystemExit(main())
