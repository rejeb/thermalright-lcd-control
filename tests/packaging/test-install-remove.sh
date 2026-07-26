#!/bin/bash
# Install the package, verify the layout, remove it, verify nothing is left and
# that ~/.config survived. Run from the repo root.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENGINE="${CONTAINER_ENGINE:-docker}"
FAILED=0

# Paths every package must own, and must fully relinquish on removal.
OWNED_PATHS='/opt/thermalright-lcd-control /usr/bin/thermalright-lcd-control-app
/usr/share/applications/thermalright-lcd-control.desktop
/etc/xdg/autostart/thermalright-lcd-control.desktop
/usr/lib/udev/rules.d/99-thermalright.rules'

run_rpm_test() {
    local image="$1" installer="$2"
    echo "=== install/remove: $image ==="
    "$ENGINE" run --rm -v "$REPO_ROOT:/src:ro" -e OWNED_PATHS="$OWNED_PATHS" "$image" \
      bash -euo pipefail -c '
        if [ "'"$installer"'" = dnf ]; then
            dnf install -y -q rpm-build >/dev/null 2>&1
        else
            zypper -n --gpg-auto-import-keys refresh >/dev/null 2>&1
            zypper -n install rpm-build >/dev/null 2>&1
        fi
        mkdir -p /rpm/SOURCES /rpm/SPECS
        cp /src/releases/*.tar.gz /rpm/SOURCES/
        cp /src/packaging/obs/*.spec /rpm/SPECS/
        rpmbuild --define "_topdir /rpm" -bb /rpm/SPECS/thermalright-lcd-control.spec >/dev/null 2>&1

        if [ "'"$installer"'" = dnf ]; then
            dnf install -y -q /rpm/RPMS/*/*.rpm >/dev/null 2>&1
        else
            zypper -n install --allow-unsigned-rpm /rpm/RPMS/*/*.rpm >/dev/null 2>&1
        fi

        mkdir -p /root/.config/thermalright-lcd-control
        echo SENTINEL > /root/.config/thermalright-lcd-control/keepme

        cp -r /src/tests /tmp/tests && cp -r /src/packaging /tmp/packaging
        cd /tmp && bash tests/packaging/verify-layout.sh /

        # PYTHONDONTWRITEBYTECODE: this test runs as root, which (unlike a real
        # user) can write into /opt. Without it the import leaves __pycache__
        # files the package does not own, so removal correctly refuses to delete
        # the directory and the leftover check fails on a test artifact.
        QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
          /opt/thermalright-lcd-control/venv/bin/python -c "
import thermalright_lcd_control, PySide6.QtWidgets
app = PySide6.QtWidgets.QApplication([])
print(\"runtime OK\")"

        if [ "'"$installer"'" = dnf ]; then
            dnf remove -y -q thermalright-lcd-control thermalright-lcd-control-data >/dev/null 2>&1
        else
            zypper -n remove thermalright-lcd-control thermalright-lcd-control-data >/dev/null 2>&1
        fi

        rc=0
        for p in $OWNED_PATHS; do
            if [ -e "$p" ]; then echo "FAIL: leftover after removal: $p"; rc=1; fi
        done
        grep -q SENTINEL /root/.config/thermalright-lcd-control/keepme \
            || { echo "FAIL: package removal destroyed user config"; rc=1; }
        [ $rc -eq 0 ] && echo "OK: clean install/remove, user config preserved"
        exit $rc
    ' || FAILED=1
}

run_deb_test() {
    local image="$1"
    echo "=== install/remove: $image ==="
    "$ENGINE" run --rm -v "$REPO_ROOT:/src:ro" -e OWNED_PATHS="$OWNED_PATHS" "$image" \
      bash -euo pipefail -c '
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq >/dev/null
        apt-get install -y -qq --no-install-recommends build-essential debhelper fakeroot >/dev/null 2>&1
        mkdir /b && tar -xzf /src/releases/thermalright-lcd-control-*.tar.gz -C /b --strip-components=1
        # The packaging is stored flattened as debian.<file> (the layout OBS
        # wants). dpkg-buildpackage needs a real debian/ tree, so rebuild one —
        # this is the same transformation OBS debtransform performs.
        mkdir -p /b/debian/source
        for f in /src/packaging/obs/debian.*; do
            base=$(basename "$f")
            case "$base" in
                debian.source.format) cp "$f" /b/debian/source/format ;;
                *) cp "$f" "/b/debian/${base#debian.}" ;;
            esac
        done
        chmod +x /b/debian/rules /b/debian/preinst /b/debian/postinst
        cd /b && dpkg-buildpackage -us -uc -b >/dev/null 2>&1
        apt-get install -y -qq /*.deb >/dev/null 2>&1

        mkdir -p /root/.config/thermalright-lcd-control
        echo SENTINEL > /root/.config/thermalright-lcd-control/keepme

        cp -r /src/tests /tmp/tests && cp -r /src/packaging /tmp/packaging
        cd /tmp && bash tests/packaging/verify-layout.sh /

        # PYTHONDONTWRITEBYTECODE: this test runs as root, which (unlike a real
        # user) can write into /opt. Without it the import leaves __pycache__
        # files the package does not own, so removal correctly refuses to delete
        # the directory and the leftover check fails on a test artifact.
        QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
          /opt/thermalright-lcd-control/venv/bin/python -c "
import thermalright_lcd_control, PySide6.QtWidgets
app = PySide6.QtWidgets.QApplication([])
print(\"runtime OK\")"

        # purge, not remove: files under /etc are conffiles, which dpkg keeps on
        # `remove` by design and only deletes on `purge`. Testing `remove` here
        # would flag correct Debian behaviour as a leak.
        apt-get purge -y -qq thermalright-lcd-control thermalright-lcd-control-data >/dev/null 2>&1

        rc=0
        for p in $OWNED_PATHS; do
            if [ -e "$p" ]; then echo "FAIL: leftover after removal: $p"; rc=1; fi
        done
        grep -q SENTINEL /root/.config/thermalright-lcd-control/keepme \
            || { echo "FAIL: package removal destroyed user config"; rc=1; }
        [ $rc -eq 0 ] && echo "OK: clean install/remove, user config preserved"
        exit $rc
    ' || FAILED=1
}

run_rpm_test fedora:latest dnf
run_rpm_test opensuse/tumbleweed zypper
run_deb_test debian:bookworm
run_deb_test ubuntu:24.04

if [ "$FAILED" -ne 0 ]; then
    echo "install/remove tests FAILED"
else
    echo "install/remove tests passed on all distros"
fi
exit "$FAILED"
