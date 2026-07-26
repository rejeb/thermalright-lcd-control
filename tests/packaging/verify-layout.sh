#!/bin/bash
# Verify an installed filesystem matches packaging/layout.manifest.
# Usage: verify-layout.sh <root>        (<root> is "/" for a real install)
set -uo pipefail

ROOT="${1:-/}"
MANIFEST="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/packaging/layout.manifest"
FAILED=0

fail() { echo "FAIL: $1"; FAILED=1; }

while IFS=$'\t' read -r kind mode path; do
    case "$kind" in ""|\#*) continue ;; esac
    full="${ROOT%/}$path"
    case "$kind" in
        d|t)
            [ -d "$full" ] || { fail "missing directory: $path"; continue; }
            ;;
        f)
            [ -f "$full" ] || { fail "missing file: $path"; continue; }
            ;;
        *)
            fail "unknown type '$kind' for $path"; continue ;;
    esac
    actual=$(stat -c '%a' "$full")
    [ "$actual" = "$mode" ] || fail "mode mismatch on $path: expected $mode, got $actual"
done < <(grep -v '^[[:space:]]*#' "$MANIFEST" | grep -v '^[[:space:]]*$')

# Nothing may be installed under /usr/local.
if [ -e "${ROOT%/}/usr/local/bin/thermalright-lcd-control-app" ]; then
    fail "/usr/local/bin/thermalright-lcd-control-app must not exist"
fi

if [ "$FAILED" -eq 0 ]; then
    echo "OK: layout matches manifest"
fi
exit "$FAILED"
