# Build environment for the vendored virtualenv.
#
# Baked once and reused so every build does not re-run apt-get and re-download
# uv. Rebuilt automatically only when this file changes.
#
# WHY bookworm AND NOT debian:stable: `stable` is a moving tag (it became Debian
# 13 / glibc 2.41). The venv's glibc floor is set by the machine that builds it,
# and bookworm's 2.36 is the floor that covers every target we ship to. Do not
# change this to a floating tag.
FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive

# Qt/hidapi/X11 libraries are needed by the SMOKE TEST only; they are runtime
# dependencies declared by the packages, never bundled into the payload.
# binutils provides objdump for the glibc-floor assertion.
RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends \
        curl ca-certificates binutils \
        libgl1 libegl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 \
        libfreetype6 libdbus-1-3 libglib2.0-0 libhidapi-hidraw0 libusb-1.0-0 \
        libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
        libxcb-shape0 libxcb-render-util0 libxcb-util1 libxcb-xinerama0 \
        libxcb-randr0 libxkbfile1 && \
    rm -rf /var/lib/apt/lists/*

# No compiler is installed on purpose: every dependency must resolve to a
# prebuilt manylinux wheel. If a build ever fails asking for a compiler, the fix
# is to pin a dependency version that publishes wheels — not to add gcc here,
# which would silently make the payload depend on this container's glibc.
RUN curl -LsSf https://astral.sh/uv/install.sh \
    | env UV_INSTALL_DIR=/usr/local/bin INSTALLER_NO_MODIFY_PATH=1 sh
