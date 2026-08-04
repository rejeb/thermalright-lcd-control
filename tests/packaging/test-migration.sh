#!/bin/bash
# Simulate an OLD tarball install (launcher in /usr/local/bin, udev rules in
# /etc), then install the package over it. The package's pre-install must clean
# the stray files and must NOT touch ~/.config.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENGINE="${CONTAINER_ENGINE:-docker}"

"$ENGINE" run --rm -v "$REPO_ROOT:/src:ro" fedora:latest bash -euo pipefail -c '
    dnf install -y -q rpm-build >/dev/null 2>&1

    # --- simulate the OLD install ---
    mkdir -p /opt/thermalright-lcd-control/venv /usr/local/bin /etc/udev/rules.d
    echo "old" > /opt/thermalright-lcd-control/venv/STALE
    echo "#!/bin/sh" > /usr/local/bin/thermalright-lcd-control-app
    chmod +x /usr/local/bin/thermalright-lcd-control-app
    echo "# old rules" > /etc/udev/rules.d/99-thermalright.rules
    mkdir -p /root/.config/thermalright-lcd-control/themes/backgrounds/320240
    echo USERDATA > /root/.config/thermalright-lcd-control/themes/backgrounds/320240/mine.png

    # --- install the package over it ---
    mkdir -p /rpm/SOURCES /rpm/SPECS
    cp /src/releases/*.tar.gz /rpm/SOURCES/
    cp /src/packaging/obs/*.spec /rpm/SPECS/
    rpmbuild --define "_topdir /rpm" -bb /rpm/SPECS/thermalright-lcd-control.spec >/dev/null 2>&1
    dnf install -y -q /rpm/RPMS/*/*.rpm >/dev/null 2>&1

    # --- assertions ---
    rc=0
    [ -e /usr/local/bin/thermalright-lcd-control-app ] \
        && { echo "FAIL: stale /usr/local launcher survived"; rc=1; }
    [ -e /etc/udev/rules.d/99-thermalright.rules ] \
        && { echo "FAIL: stale /etc udev rules survived"; rc=1; }
    [ -e /opt/thermalright-lcd-control/venv/STALE ] \
        && { echo "FAIL: stale venv payload survived"; rc=1; }
    grep -q USERDATA /root/.config/thermalright-lcd-control/themes/backgrounds/320240/mine.png \
        || { echo "FAIL: migration destroyed user data"; rc=1; }
    [ -x /usr/bin/thermalright-lcd-control-app ] \
        || { echo "FAIL: new launcher missing"; rc=1; }
    # The -data package installs first; its payload must survive the pre-install
    # cleanup (this is the regression that recursive deletion of /opt caused).
    [ -d /opt/thermalright-lcd-control/resources ] \
        || { echo "FAIL: -data resources destroyed by pre-install cleanup"; rc=1; }

    [ $rc -eq 0 ] && echo "OK: migration cleaned stale files and preserved user data"
    exit $rc
'
