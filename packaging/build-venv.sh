#!/bin/bash
# Build the vendored virtualenv inside a pinned Debian bookworm container.
#
# WHY A CONTAINER: the venv's glibc floor is set by the machine that builds it.
# A venv built on a modern host does NOT run on older targets. See
# packaging/Dockerfile.builder for why the base image is pinned to bookworm.
#
# WHY /opt/thermalright-lcd-control: the venv symlinks to the uv-managed
# interpreter under /opt/thermalright-lcd-control/python by ABSOLUTE path.
# Building elsewhere and moving the tree breaks those symlinks.
#
# SPEED: the build environment is baked into a cached image (no apt-get per run)
# and uv's download cache is mounted from the host (wheels + CPython downloaded
# once, not every run). A warm run is dominated by copying the ~570 MB payload
# out of the container.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$REPO_ROOT/build"
CACHE_DIR="${UV_BUILD_CACHE:-$REPO_ROOT/.cache/uv}"
PREFIX="/opt/thermalright-lcd-control"
IMAGE="thermalright-lcd-control-builder:bookworm"
DOCKERFILE="$REPO_ROOT/packaging/Dockerfile.builder"
# Highest glibc symbol version any shipped binary may require.
MAX_GLIBC="2.36"
ENGINE="${CONTAINER_ENGINE:-docker}"

command -v "$ENGINE" >/dev/null || { echo "ERROR: $ENGINE not found"; exit 1; }

# Bake the builder image. Docker's layer cache makes this a no-op unless
# Dockerfile.builder changed.
echo "Preparing builder image..."
"$ENGINE" build -q -t "$IMAGE" -f "$DOCKERFILE" "$REPO_ROOT/packaging" >/dev/null

mkdir -p "$OUT_DIR" "$CACHE_DIR"
# The container runs as root, so a previous run's output is root-owned and the
# host user cannot remove it. Clear it from inside a container instead.
if [ -e "$OUT_DIR/opt" ] || [ -e "$OUT_DIR/requirements.txt" ]; then
    "$ENGINE" run --rm -v "$OUT_DIR:/out" "$IMAGE" \
        rm -rf /out/opt /out/requirements.txt
fi

"$ENGINE" run --rm \
    -v "$REPO_ROOT:/src:ro" \
    -v "$OUT_DIR:/out" \
    -v "$CACHE_DIR:/uvcache" \
    -e PREFIX="$PREFIX" \
    -e UV_CACHE_DIR=/uvcache \
    -e HOST_UID="$(id -u)" \
    -e HOST_GID="$(id -g)" \
    "$IMAGE" bash -euo pipefail -c '
    cd /src

    export UV_PYTHON_INSTALL_DIR="$PREFIX/python"
    mkdir -p "$UV_PYTHON_INSTALL_DIR" "$PREFIX"

    uv python install --python-preference only-managed 3.14
    uv venv --python 3.14 --python-preference only-managed --relocatable "$PREFIX/venv"

    uv export --frozen --no-hashes > /out/requirements.txt
    # No --no-build: pure-Python sdists (pyvips is one — its binary half lives
    # in pyvips-binary) are harmless and must still install. What must NOT
    # happen is compiling a C extension here, since that would tie the payload
    # to this container glibc; the absence of a compiler in the image enforces
    # that, and the glibc-floor assertion below is the backstop.
    uv pip install --python "$PREFIX/venv" -r /out/requirements.txt

    # Build the wheel into a writable dir (/src is read-only).
    uv build --out-dir /tmp/dist
    uv pip install --python "$PREFIX/venv" --no-deps /tmp/dist/*.whl

    # SMOKE TEST: a broken venv must fail the build, not ship.
    echo "--- smoke test ---"
    QT_QPA_PLATFORM=offscreen "$PREFIX/venv/bin/python" -c "
import PySide6.QtWidgets, cv2, pyvips, usb.core, hid, yaml, psutil
import thermalright_lcd_control
app = PySide6.QtWidgets.QApplication([])
print(\"smoke ok:\", thermalright_lcd_control.__name__)
"
    echo "--- smoke test passed ---"

    mkdir -p /out/opt
    cp -a "$PREFIX" /out/opt/
    chmod -R a+rX /out/opt
    # Hand the output back to the invoking host user; otherwise the next run
    # cannot clean it and the tarball step cannot read it.
    chown -R "$HOST_UID:$HOST_GID" /out /uvcache
'

# GLIBC FLOOR ASSERTION. Every downstream artifact inherits this floor, and a
# regression here is invisible until a user on an older distro reports a crash.
# objdump is required: without it the check would silently pass.
command -v objdump >/dev/null || { echo "ERROR: objdump not found (install binutils) — cannot verify the glibc floor"; exit 1; }

echo "Checking glibc floor (max allowed: $MAX_GLIBC)..."
TOO_NEW=$(
    # `|| true` on each stage: objdump exits non-zero on files it cannot parse
    # (scripts, data), and grep exits 1 when a chunk has no matches. Under
    # `set -euo pipefail` either would abort the script with no message, making
    # a skipped check look identical to a passing one.
    find "$OUT_DIR/opt" \( -name '*.so' -o -name '*.so.*' -o -perm -u+x -type f \) -print0 \
      | { xargs -0 -r objdump -T 2>/dev/null || true; } \
      | { grep -o 'GLIBC_[0-9][0-9.]*' || true; } | sort -u \
      | while read -r sym; do
            ver="${sym#GLIBC_}"
            if [ "$(printf '%s\n%s\n' "$ver" "$MAX_GLIBC" | sort -V | tail -1)" != "$MAX_GLIBC" ]; then
                echo "$sym"
            fi
        done
)
if [ -n "$TOO_NEW" ]; then
    echo "ERROR: binaries require glibc newer than $MAX_GLIBC:"
    echo "$TOO_NEW" | sed 's/^/  /'
    echo "The build container is too new. Check the base image in $DOCKERFILE."
    exit 1
fi
echo "OK: glibc floor is <= $MAX_GLIBC"

echo "Venv built: $OUT_DIR/opt/thermalright-lcd-control/{venv,python}"
echo "Locked deps: $OUT_DIR/requirements.txt"
