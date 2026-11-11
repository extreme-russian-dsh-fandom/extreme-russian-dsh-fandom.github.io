#!/bin/sh
# Regenerate the catalog data and start the live server.
#
# `zola serve` rebuilds content/ and templates, but never runs the generator, so
# a new tag, a registry edit or a fresh plugin only shows up after this script.
#
#   scripts/dev.sh                  regenerate, then serve
#   scripts/dev.sh --build-only     regenerate only (server already running)

set -eu

cd "$(dirname "$0")/.."

# Pick an interpreter that actually runs Python 3.11+. On Windows a bare
# `python3` can be a Store stub or a launcher shim that prints a banner and
# exits, which looks exactly like a silent no-op.
pick_python() {
    for candidate in python3 python py; do
        if ! command -v "$candidate" >/dev/null 2>&1; then
            continue
        fi
        if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

PYTHON=$(pick_python) || {
    echo "dev.sh: no working Python 3.11+ found in PATH (tried python3, python, py)" >&2
    exit 1
}

echo "dev.sh: using $PYTHON"
"$PYTHON" scripts/build_index.py

if [ "${1:-}" = "--build-only" ]; then
    exit 0
fi

if ! command -v zola >/dev/null 2>&1; then
    echo "dev.sh: zola not found in PATH" >&2
    exit 1
fi

echo "dev.sh: starting zola serve"
exec zola serve
