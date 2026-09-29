#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${MANIA_PYTHON:-python3}"
"$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "Python >= 3.11 required before installation")'
exec "$PYTHON" "$SCRIPT_DIR/tools/run_gromacs_wt_all.py" "$@"
