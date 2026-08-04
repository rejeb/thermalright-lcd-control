#!/bin/bash
# RULE 1: "Installation through a package manager should result in the same
# output as the tarball." This is the mechanical check of that rule. It installs
# both ways in identical containers and diffs the resulting file lists.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENGINE="${CONTAINER_ENGINE:-docker}"
OUT=$(mktemp -d)
trap 'rm -rf "$OUT"' EXIT

# Paths owned by the install. resources/, venv/ and python/ are compared as trees
# by file count only: enumerating ~9,700 PNGs and thousands of venv files line by
# line makes failures unreadable and adds nothing.
SNAPSHOT='
  find /opt/thermalright-lcd-control -maxdepth 1 -printf "%y %m %f\n" | sort
  echo "venv-files: $(find /opt/thermalright-lcd-control/venv -type f | wc -l)"
  echo "python-files: $(find /opt/thermalright-lcd-control/python -type f | wc -l)"
  echo "resource-files: $(find /opt/thermalright-lcd-control/resources -type f | wc -l)"
  for p in /usr/bin/thermalright-lcd-control-app \
           /usr/share/applications/thermalright-lcd-control.desktop \
           /etc/xdg/autostart/thermalright-lcd-control.desktop \
           /usr/lib/udev/rules.d/99-thermalright.rules; do
      if [ -e "$p" ]; then stat -c "%a %n" "$p"; else echo "MISSING $p"; fi
  done
  echo "usr-local: $(ls /usr/local/bin/thermalright-lcd-control-app 2>/dev/null || echo none)"
  echo "autostart-exec: $(grep -h ^Exec= /etc/xdg/autostart/thermalright-lcd-control.desktop 2>/dev/null || echo none)"
  echo "desktop-icon: $(grep -h ^Icon= /usr/share/applications/thermalright-lcd-control.desktop 2>/dev/null || echo none)"
'

echo "=== snapshot: tarball install ==="
"$ENGINE" run --rm -v "$REPO_ROOT:/src:ro" fedora:latest bash -euo pipefail -c "
    dnf install -y -q hidapi libusb1 findutils >/dev/null 2>&1
    mkdir /t && tar -xzf /src/releases/thermalright-lcd-control-*.tar.gz -C /t --strip-components=1
    cd /t && ./install.sh >/dev/null 2>&1
    $SNAPSHOT
" > "$OUT/tarball.txt"

echo "=== snapshot: rpm install ==="
"$ENGINE" run --rm -v "$REPO_ROOT:/src:ro" fedora:latest bash -euo pipefail -c "
    dnf install -y -q rpm-build >/dev/null 2>&1
    mkdir -p /rpm/SOURCES /rpm/SPECS
    cp /src/releases/*.tar.gz /rpm/SOURCES/
    cp /src/packaging/obs/*.spec /rpm/SPECS/
    rpmbuild --define '_topdir /rpm' -bb /rpm/SPECS/thermalright-lcd-control.spec >/dev/null 2>&1
    dnf install -y -q /rpm/RPMS/*/*.rpm >/dev/null 2>&1
    $SNAPSHOT
" > "$OUT/rpm.txt"

echo "=== diff ==="
if diff -u "$OUT/tarball.txt" "$OUT/rpm.txt"; then
    echo "OK: tarball and package installs are equivalent"
else
    echo "FAIL: tarball and package installs diverge (see diff above)"
    exit 1
fi
