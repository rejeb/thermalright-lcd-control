#!/bin/bash
# Assemble the single source artifact consumed by BOTH GitHub Releases and OBS.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
NAME="thermalright-lcd-control"
PKG="$NAME-$VERSION"
STAGE="build/$PKG"
BUILT_VENV="build/opt/$NAME"

[ -d "$BUILT_VENV/venv" ] || { echo "ERROR: $BUILT_VENV/venv missing — run packaging/build-venv.sh first"; exit 1; }
[ -f "build/requirements.txt" ] || { echo "ERROR: build/requirements.txt missing — run packaging/build-venv.sh first"; exit 1; }

rm -rf "$STAGE"
mkdir -p "$STAGE/opt" "$STAGE/usr/bin" "$STAGE/packaging"

# Prebuilt venv + managed interpreter (the whole point: no network at install time)
cp -a "$BUILT_VENV" "$STAGE/opt/"

# Resources. resources/config is intentionally emptied: the device is configured
# from the GUI, so shipping bundled device configs would seed stale devices.
cp -a resources "$STAGE/"
rm -rf "$STAGE/resources/config"
mkdir -p "$STAGE/resources/config"

cp scripts/usr/bin/$NAME-app "$STAGE/usr/bin/"
cp scripts/$NAME.desktop "$STAGE/"
cp scripts/99-thermalright.rules "$STAGE/"
cp packaging/layout.manifest "$STAGE/packaging/"
cp install.sh uninstall.sh README.md LICENSE pyproject.toml "$STAGE/"
cp build/requirements.txt "$STAGE/"

chmod +x "$STAGE/install.sh" "$STAGE/uninstall.sh" "$STAGE/usr/bin/$NAME-app"

mkdir -p releases
rm -f "releases/$PKG.tar.gz"

# gzip -1: the payload is ~1 GB and already-compressed (PNG assets, wheels), so
# higher levels cost minutes to save a few percent. Level 1 cuts compression
# from ~60s to ~15s. Keep .tar.gz — OBS and every distro tool expect it.
tar -c -C build "$PKG" | gzip -1 > "releases/$PKG.tar.gz"
echo "Tarball: releases/$PKG.tar.gz ($(du -h "releases/$PKG.tar.gz" | cut -f1))"
