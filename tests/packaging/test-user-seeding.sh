#!/bin/bash
# The launcher seeds the per-user themes tree from /opt on every launch. Seeding
# used to be gated on ~/.config/<app>/themes merely EXISTING, which silently
# skipped the copy whenever the directory was present but not populated — most
# visibly after install.sh's layout wipe (it keeps themes/user_backgrounds, so
# the directory survives) and on upgrades that ship new assets.
#
# No container and no built tarball needed: the launcher is driven against a
# fake APP_ROOT and a fake HOME.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LAUNCHER="$REPO_ROOT/scripts/usr/bin/thermalright-lcd-control-app"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

rc=0
fail() { echo "FAIL: $1"; rc=1; }

# --- a stand-in for /opt/thermalright-lcd-control -------------------------
APP_ROOT="$WORK/opt"
mkdir -p "$APP_ROOT/resources/themes"/{backgrounds/320240,foregrounds/320240,presets/320240,user_backgrounds}
mkdir -p "$APP_ROOT/resources/config" "$APP_ROOT/resources/32x32"
echo bg      > "$APP_ROOT/resources/themes/backgrounds/320240/a001.png"
echo fg      > "$APP_ROOT/resources/themes/foregrounds/320240/f001.png"
echo preset  > "$APP_ROOT/resources/themes/presets/320240/p001.json"
cp "$REPO_ROOT/resources/gui_config.yaml" "$APP_ROOT/resources/"
# Never launch the real GUI: a stub interpreter stands in for the venv python.
mkdir -p "$APP_ROOT/venv/bin"
printf '#!/bin/sh\nexit 0\n' > "$APP_ROOT/venv/bin/python"
chmod +x "$APP_ROOT/venv/bin/python"

launch() { env HOME="$1" TRLCD_APP_ROOT="$APP_ROOT" "$LAUNCHER" >/dev/null 2>&1; }
seeded() { find "$1/.config/thermalright-lcd-control/themes/$2" -type f 2>/dev/null | wc -l; }

# --- case 1: fresh machine, no ~/.config at all ---------------------------
H="$WORK/fresh"; mkdir -p "$H"
launch "$H"
for sub in backgrounds foregrounds presets; do
    [ "$(seeded "$H" "$sub")" -ge 1 ] || fail "fresh install did not seed themes/$sub"
done

# --- case 2: the state install.sh's layout wipe leaves behind --------------
# Everything under themes/ removed except user_backgrounds, so themes/ exists
# but holds no bundled asset. This is the 1.3.1 -> 2.x upgrade path.
H="$WORK/wiped"; mkdir -p "$H/.config/thermalright-lcd-control/themes/user_backgrounds"
echo mine > "$H/.config/thermalright-lcd-control/themes/user_backgrounds/mine.png"
launch "$H"
for sub in backgrounds foregrounds presets; do
    [ "$(seeded "$H" "$sub")" -ge 1 ] || fail "post-wipe upgrade did not re-seed themes/$sub"
done
grep -q mine "$H/.config/thermalright-lcd-control/themes/user_backgrounds/mine.png" \
    || fail "re-seeding destroyed themes/user_backgrounds"

# --- case 3: upgrade shipping a new resolution ----------------------------
# An already-populated tree must gain the new assets without losing or
# overwriting anything the user owns.
H="$WORK/upgrade"; T="$H/.config/thermalright-lcd-control/themes"
mkdir -p "$T/backgrounds/320240" "$T/presets/320240"
echo EDITED > "$T/backgrounds/320240/a001.png"
echo USERPRESET > "$T/presets/320240/mine.json"
mkdir -p "$APP_ROOT/resources/themes/backgrounds/480480"
echo newbg > "$APP_ROOT/resources/themes/backgrounds/480480/b001.png"
launch "$H"
[ -f "$T/backgrounds/480480/b001.png" ] || fail "upgrade did not seed the new resolution folder"
grep -q EDITED "$T/backgrounds/320240/a001.png" || fail "seeding overwrote a user-modified asset"
grep -q USERPRESET "$T/presets/320240/mine.json" || fail "seeding destroyed a user preset"

# --- case 4: seeding is idempotent ----------------------------------------
before=$(find "$T" -type f | sort | md5sum)
launch "$H"
[ "$before" = "$(find "$T" -type f | sort | md5sum)" ] || fail "second launch changed the themes tree"

[ $rc -eq 0 ] && echo "OK: per-user themes seeding covers fresh, post-wipe and upgrade installs"
exit $rc
