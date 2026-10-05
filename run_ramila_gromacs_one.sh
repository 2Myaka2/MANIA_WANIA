#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 3 ]] || { echo "Usage: $0 SOURCE_ROOT OUTPUT_ROOT TRAJECTORY_ID" >&2; exit 2; }
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
python_bin=${MANIA_PYTHON:-python3}
[[ ! -x "$repo/.venv/bin/python" ]] || python_bin="$repo/.venv/bin/python"
exec "$python_bin" "$repo/tools/run_ramila_gromacs.py" run "$1" "$2" "$3"
