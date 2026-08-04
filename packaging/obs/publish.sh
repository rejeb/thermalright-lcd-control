#!/bin/bash
# Upload the single source artifact + packaging metadata to OBS.
# OBS then builds every distro package as a pure repack.
#
# There is deliberately no _service file: the version is injected into the spec
# and the Debian changelog here, from pyproject.toml, so the two can never drift
# from the tarball actually being uploaded.
#
# Requires: osc, and ~/.config/osc/oscrc (or OBS_USERNAME/OBS_PASSWORD).
# Usage: packaging/obs/publish.sh home:<user>:thermalright-lcd-control
set -euo pipefail

PROJECT="${1:?usage: publish.sh <obs-project>}"
PKGNAME="thermalright-lcd-control"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

command -v osc >/dev/null || { echo "ERROR: osc not found"; exit 1; }

VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$REPO_ROOT/pyproject.toml','rb'))['project']['version'])")
TARBALL="$REPO_ROOT/releases/$PKGNAME-$VERSION.tar.gz"
[ -f "$TARBALL" ] || { echo "ERROR: $TARBALL not found — run packaging/build-tarball.sh"; exit 1; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

cd "$WORK"
osc checkout "$PROJECT" "$PKGNAME" 2>/dev/null || osc mkpac "$PROJECT" "$PKGNAME"
cd "$PROJECT/$PKGNAME"

# Replace the previous revision's sources wholesale.
osc rm --force ./* 2>/dev/null || true
rm -f ./*

cp "$TARBALL" .
cp "$REPO_ROOT/packaging/obs/$PKGNAME.spec" .
# The .dsc is the BUILD RECIPE for Debian/Ubuntu targets. Without it OBS has no
# valid recipe and falls back to treating debian.control as one, which fails
# with "cannot open file debian/changelog". OBS's debtransform uses the .dsc
# plus Debtransform-Tar to assemble the Debian source package from the
# flattened debian.* files below.
cp "$REPO_ROOT/packaging/obs/$PKGNAME.dsc" .
cp "$REPO_ROOT/packaging/obs/_constraints" .

# Keep the packaging metadata's version in lockstep with pyproject.toml.
sed -i "s|^Version:.*|Version:        $VERSION|" "$PKGNAME.spec"
sed -i -e "s|^Version:.*|Version: $VERSION-1|" \
       -e "s|^Debtransform-Tar:.*|Debtransform-Tar: $PKGNAME-$VERSION.tar.gz|" \
       -e "s|^ 00000000000000000000000000000000 0 .*| 00000000000000000000000000000000 0 $PKGNAME-$VERSION.tar.gz|" \
       "$PKGNAME.dsc"

# The Debian packaging is already stored flattened as debian.<file>, which is
# exactly the layout OBS expects, so these copy across verbatim.
cp "$REPO_ROOT"/packaging/obs/debian.* .

# Rewrite the changelog's version+date so dpkg builds the right version.
if [ -f debian.changelog ]; then
    printf '%s (%s-1) unstable; urgency=medium\n\n  * Release %s.\n\n -- REJEB BEN REJEB <benrejebrejeb@gmail.com>  %s\n' \
        "$PKGNAME" "$VERSION" "$VERSION" "$(date -R)" > debian.changelog
fi

osc addremove
osc commit -m "Release $VERSION"
echo "Published $PKGNAME $VERSION to $PROJECT"
