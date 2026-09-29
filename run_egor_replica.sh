#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if (( $# != 3 )); then
    echo "Usage: $0 EGOR_DATA_DIR OUTPUT_DIR r1|r2|r3" >&2
    exit 2
fi
exec python "$SCRIPT_DIR/tools/run_egor_all.py" "$1" "$2" --replica "$3"
