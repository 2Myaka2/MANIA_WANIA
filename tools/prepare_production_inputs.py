"""Prepare one Egor input or explicitly confirm its completed preparation report."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    operations = parser.add_subparsers(dest="operation", required=True)
    for operation in ("prepare", "confirm"):
        p = operations.add_parser(operation)
        for name in ("data-root", "result-root", "authority-package"):
            p.add_argument("--" + name, required=True, type=Path)
        p.add_argument("--trajectory-id", required=True)
        p.add_argument("--min-free-bytes", required=True, type=int)
        if operation == "prepare":
            p.add_argument("--workers", required=True, type=int, choices=(1,))
            p.add_argument("--threads", required=True, type=int, choices=(1,))
        else:
            p.add_argument("--report-sha256", required=True)
            p.add_argument("--reviewer")
            p.add_argument("--review-note")
            mode = p.add_mutually_exclusive_group(required=True)
            mode.add_argument("--approve", action="store_true")
            mode.add_argument("--source-attestation", type=Path)
            p.add_argument("--production-output-root", required=True, type=Path)
    args = vars(parser.parse_args(argv))
    operation = args.pop("operation")
    if operation == "confirm":
        if args["source_attestation"] is not None:
            if args["reviewer"] is not None or args["review_note"] is not None:
                parser.error("--source-attestation uses only the saved reviewer/note")
        elif args["reviewer"] is None or args["review_note"] is None:
            parser.error("--approve requires --reviewer and --review-note")
    # Pin library threads before the optional scientific modules are imported.
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[name] = "1"
    # Import numpy/optional science only after pinning library resources.
    if __package__:
        from . import production_input_preparation as preparation
    else:
        import production_input_preparation as preparation
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        *(sys.argv[1:] if argv is None else argv),
    ]
    try:
        result = getattr(preparation, operation)(**args, command=command)
    except Exception as exc:
        print(
            json.dumps(
                dict(
                    status="failed",
                    error=str(exc),
                    result_root=str(args["result_root"]),
                )
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
