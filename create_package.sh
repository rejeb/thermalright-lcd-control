#!/bin/bash
# Kept for backwards compatibility. The packaging pipeline now lives in
# packaging/: build-venv.sh (container build) then build-tarball.sh (assembly).
# See docs/superpowers/specs/2026-07-26-linux-packaging-design.md
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$REPO_ROOT/packaging/build-venv.sh"
"$REPO_ROOT/packaging/build-tarball.sh"
