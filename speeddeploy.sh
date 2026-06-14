#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if [ -x "$SCRIPT_DIR/venv/bin/python" ]; then
    exec "$SCRIPT_DIR/venv/bin/python" -m speeddeploy "$@"
fi

if command -v python3 >/dev/null 2>&1; then
    exec python3 -m speeddeploy "$@"
fi

echo "Python introuvable. Active un virtualenv ou installe Python." >&2
exit 1
