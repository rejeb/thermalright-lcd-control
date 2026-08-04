# OBS project setup (one-time, manual)

Create the project `home:<user>:thermalright-lcd-control` at https://build.opensuse.org
and enable these build targets — **x86_64 only**:

- Fedora (current release)
- Fedora (previous release)
- openSUSE Tumbleweed
- openSUSE Leap (current)
- Debian (stable)
- Ubuntu (current LTS)
- Ubuntu (current release)

Notes:

- Do NOT enable aarch64. The venv is x86-64 only; an aarch64 build would
  produce a package that installs and then fails at launch.
- Home projects have no formal disk quota, but uploads are capped at ~4 GB.
  The current tarball is ~650 MB.
- `_constraints` requests 30 GB of worker disk. Keep it modest — oversized
  requests find no compliant worker and never schedule.
- Home-project builds have lower scheduling priority; queuing is normal.
- Publish the repo, then users add it with the standard
  `dnf config-manager` / `zypper ar` / `apt` instructions OBS generates.

## Files OBS needs

| File | Role |
|---|---|
| `thermalright-lcd-control-<version>.tar.gz` | the source artifact |
| `thermalright-lcd-control.spec` | **build recipe for RPM targets** (Fedora, openSUSE) |
| `thermalright-lcd-control.dsc` | **build recipe for DEB targets** (Debian, Ubuntu) |
| `debian.control`, `debian.rules`, `debian.changelog`, `debian.preinst`, `debian.postinst`, `debian.source.format` | Debian packaging, stored flattened with a `debian.` prefix — the layout OBS expects, uploaded verbatim |
| `_constraints` | build-worker disk request |

The `.dsc` is not optional. Without it OBS has no recipe for Debian targets and
falls back to treating `debian.control` as one, which fails with:

```
dpkg-buildpackage: error: cannot open file debian/changelog: No such file or directory
```

`Debtransform-Tar:` in the `.dsc` points at the tarball; OBS's `debtransform`
then builds the Debian source package from it plus the `debian.*` files.
`publish.sh` keeps the version in both the `.spec` and the `.dsc` in sync with
`pyproject.toml`.

## Publishing

```bash
make build-all                                    # venv + tarball + tests
packaging/obs/publish.sh home:<user>:thermalright-lcd-control
```

`publish.sh` injects the version from `pyproject.toml` into both the RPM spec and
the Debian changelog, so neither can drift from the tarball being uploaded. There
is intentionally no `_service` file.

## Why builds work on OBS despite no network

Every OBS build is a pure repack: the tarball already contains a prebuilt,
smoke-tested virtualenv. Nothing is downloaded, compiled or resolved at build
time, so OBS's network-isolated workers are a non-issue.

## Verified locally

The packaging in this directory has been built and installed in containers for:

| Distro | Build | Install | Layout | Runtime import | X11 plugin |
|---|---|---|---|---|---|
| Fedora (latest) | yes | yes | matches manifest | OK | 0 unresolved |
| openSUSE Tumbleweed | yes | yes | matches manifest | OK | 0 unresolved |
| Debian bookworm | yes | yes | matches manifest | OK | 0 unresolved |

Runtime library dependencies were derived by running `ldd` against the bundled Qt
xcb platform plugin and the modules the application imports — they are not
guesses. The RPM declares them as SONAMEs (`libEGL.so.1()(64bit)` and friends)
so one spec covers Fedora and openSUSE without per-distro conditionals; Debian
uses package names, which is the norm there.
