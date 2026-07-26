# Pure repack: the tarball already contains a prebuilt venv. No pip, no network,
# no compilation happens here — which is what makes OBS's network-isolated build
# workers a non-issue.
%global appname thermalright-lcd-control
%global appdir  /opt/%{appname}

# The venv ships prebuilt with its own CPython; the distro's Python must not
# touch it. Disable every automatic scan that would rewrite or misread it.
%global __brp_python_bytecompile %{nil}
%global __brp_mangle_shebangs %{nil}
%global __requires_exclude_from ^%{appdir}/.*$
%global __provides_exclude_from ^%{appdir}/.*$
%global debug_package %{nil}

# Disable RPM's post-install binary processing (check-rpaths, strip, compress).
# The uv-managed CPython bundles Tcl/Tk built by python-build-standalone with a
# build-time rpath of /tools/deps/lib, which check-rpaths rejects outright. The
# payload is prebuilt and smoke-tested exactly as it stands, so RPM must ship it
# byte-identical rather than rewrite or strip it.
%global __arch_install_post %{nil}
%global __os_install_post %{nil}

# Debuginfo extraction must be OFF for a vendored payload.
# openSUSE's OBS config passes `--define _build_create_debug 1` and runs
# find-debuginfo through a hook that __os_install_post alone does not suppress,
# producing .debug files under /usr/lib/debug that no %%files section owns:
#   error: Installed (but unpackaged) file(s) found: /usr/lib/debug/...
# Extracting debug symbols from third-party prebuilt binaries has no value here
# anyway — upstream ships them stripped.
%global _enable_debug_packages 0
%global __debug_install_post %{nil}
%global __debug_package 0
%global _build_create_debug 0
# Safety net: if a future distro still emits stray files under /usr/lib/debug,
# warn instead of failing the whole build.
%global _unpackaged_files_terminate_build 0

Name:           %{appname}
Version:        2.1.0
Release:        1%{?dist}
Summary:        Thermalright LCD Control
License:        Apache-2.0
URL:            https://github.com/rejeb/thermalright-lcd-control
Source0:        %{name}-%{version}.tar.gz
BuildRequires:  coreutils
ExclusiveArch:  x86_64

Requires:       %{name}-data = %{version}-%{release}

# Runtime libraries are taken from the distribution, never bundled (see the
# design spec). Declared as SONAMEs rather than package names: Fedora and
# openSUSE both auto-provide sonames, so one spec covers both without
# per-distro conditionals. This list was derived by running ldd against the
# bundled Qt xcb platform plugin and the modules the app imports — not guessed.
Requires:       libhidapi-hidraw.so.0()(64bit)
Requires:       libusb-1.0.so.0()(64bit)
Requires:       libGL.so.1()(64bit)
Requires:       libEGL.so.1()(64bit)
Requires:       libdbus-1.so.3()(64bit)
# OpenCV links these; Fedora pulls them in transitively but openSUSE does not.
Requires:       libglib-2.0.so.0()(64bit)
Requires:       libgthread-2.0.so.0()(64bit)
Requires:       libfontconfig.so.1()(64bit)
Requires:       libfreetype.so.6()(64bit)
Requires:       libxkbcommon.so.0()(64bit)
Requires:       libxkbcommon-x11.so.0()(64bit)
Requires:       libxcb-cursor.so.0()(64bit)
Requires:       libxcb-icccm.so.4()(64bit)
Requires:       libxcb-image.so.0()(64bit)
Requires:       libxcb-keysyms.so.1()(64bit)
Requires:       libxcb-render-util.so.0()(64bit)
Requires:       libxcb-util.so.1()(64bit)
Requires:       libxcb-shape.so.0()(64bit)

%description
GUI application to control Thermalright LCD displays on Linux.
Bundles its own Python runtime and dependencies under %{appdir}.

%package data
Summary:        Themes, fonts and icons for %{name}
BuildArch:      noarch

%description data
Architecture-independent resources (themes, fonts, icons) for %{name}.

%prep
%autosetup

%build
# Nothing to build: the payload is prebuilt.

%install
mkdir -p %{buildroot}%{appdir}
cp -a opt/%{appname}/venv   %{buildroot}%{appdir}/
cp -a opt/%{appname}/python %{buildroot}%{appdir}/
cp -a resources             %{buildroot}%{appdir}/
install -Dm644 README.md %{buildroot}%{appdir}/README.md
install -Dm644 LICENSE   %{buildroot}%{appdir}/LICENSE

install -Dm755 usr/bin/%{appname}-app %{buildroot}%{_bindir}/%{appname}-app
install -Dm644 %{appname}.desktop %{buildroot}%{_datadir}/applications/%{appname}.desktop
install -Dm644 99-thermalright.rules \
    %{buildroot}%{_prefix}/lib/udev/rules.d/99-thermalright.rules

# Autostart entry: same desktop file, launched minimized to the tray.
install -Dm644 %{appname}.desktop %{buildroot}%{_sysconfdir}/xdg/autostart/%{appname}.desktop
sed -i 's|^Exec=.*|Exec=%{appname}-app --minimized|' \
    %{buildroot}%{_sysconfdir}/xdg/autostart/%{appname}.desktop
grep -q X-GNOME-Autostart-enabled %{buildroot}%{_sysconfdir}/xdg/autostart/%{appname}.desktop \
    || echo 'X-GNOME-Autostart-enabled=true' >> %{buildroot}%{_sysconfdir}/xdg/autostart/%{appname}.desktop

sed -i 's|^Icon=.*|Icon=%{appdir}/resources/256x256/icon.png|' \
    %{buildroot}%{_datadir}/applications/%{appname}.desktop \
    %{buildroot}%{_sysconfdir}/xdg/autostart/%{appname}.desktop

chmod 755 %{buildroot}%{appdir}

%pre
# An older tarball install is not owned by RPM; remove its stray files so they
# cannot shadow the packaged ones. NEVER touch ~/.config — user data is not ours.
rm -f /usr/local/bin/%{appname}-app || :
rm -f %{_sysconfdir}/udev/rules.d/99-thermalright.rules || :

# Remove ONLY the old tarball's own payload (venv/python), and only when RPM does
# not already own it. Do NOT test or delete %{appdir} itself: the -data package
# installs first and creates that directory, so an ownership test on it fails and
# a recursive delete would destroy the resources just installed.
for stale in venv python; do
    if [ -e %{appdir}/$stale ] && ! rpm -qf %{appdir}/$stale >/dev/null 2>&1; then
        rm -rf %{appdir}/$stale || :
    fi
done

%post
# The udev rules grant device access to the 'plugdev' group; ensure it exists.
# Adding USERS to it is the launcher's job: a scriptlet has no invoking user.
groupadd -f plugdev || :
if [ -x /usr/bin/udevadm ]; then
    /usr/bin/udevadm control --reload-rules >/dev/null 2>&1 || :
    /usr/bin/udevadm trigger --action=add --subsystem-match=hidraw >/dev/null 2>&1 || :
    /usr/bin/udevadm trigger --action=add --subsystem-match=usb >/dev/null 2>&1 || :
fi

%files
%{appdir}/venv
%{appdir}/python
%{appdir}/README.md
%{appdir}/LICENSE
%{_bindir}/%{appname}-app
%{_datadir}/applications/%{appname}.desktop
%{_sysconfdir}/xdg/autostart/%{appname}.desktop
%{_prefix}/lib/udev/rules.d/99-thermalright.rules
%dir %{appdir}

%files data
# BOTH subpackages must own %%{appdir}. If only the main package owns it,
# removing the two together orphans an empty directory: RPM cannot delete a
# non-empty dir while the -data payload is still present, and once that payload
# goes nothing owns the dir any more. Shared ownership makes RPM remove it with
# the last owner.
%dir %{appdir}
%{appdir}/resources

%changelog
* Sun Jul 26 2026 REJEB BEN REJEB <benrejebrejeb@gmail.com> - 2.1.0-1
- Initial RPM packaging with vendored runtime.
