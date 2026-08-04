# Makefile
# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

PACKAGE := thermalright-lcd-control
VERSION := $(shell python3 -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
DIST_DIR := releases

.PHONY: clean clean-cache build-venv build-tarball test-packaging test-packaging-all build-all

# Builds the vendored venv inside a pinned debian:bookworm container
# (glibc 2.36 floor). ~20s warm; the first run bakes the builder image and
# fills .cache/uv, so it takes a few minutes.
build-venv:
	./packaging/build-venv.sh

# Assembles the single artifact used by BOTH GitHub Releases and OBS. ~13s.
build-tarball:
	./packaging/build-tarball.sh

# Routine check. Requires a built tarball. The equivalence test is the one thing
# OBS cannot do for us: it proves `install.sh` and the package produce the same
# on-disk layout. ~8 min.
test-packaging:
	./tests/packaging/test-layout-equivalence.sh
	./tests/packaging/test-migration.sh

# Full matrix across Fedora, openSUSE, Debian and Ubuntu. Slow (~20 min) and
# largely duplicates what OBS does on its own build farm — run before a release,
# not on every change.
test-packaging-all: test-packaging
	./tests/packaging/test-install-remove.sh

build-all: clean build-venv build-tarball

clean:
	rm -rf $(DIST_DIR) build dist rpmbuild

# Also drops the uv download cache, forcing wheels and CPython to be re-fetched.
clean-cache: clean
	rm -rf .cache
