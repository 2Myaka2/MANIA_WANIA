#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if (( $# < 3 )); then
    echo "Usage: $0 EGOR_DATA_DIR OUTPUT_DIR TRAJECTORY_ID [--TEST-0ss-r1-5-8ns]" >&2
    exit 2
fi
SOURCE_DIR="$1"
RESULTS_DIR="$2"
TRAJECTORY_ID="$3"
shift 3
exec python "$SCRIPT_DIR/tools/run_egor_all.py" "$SOURCE_DIR" "$RESULTS_DIR" --trajectory-id "$TRAJECTORY_ID" "$@"
