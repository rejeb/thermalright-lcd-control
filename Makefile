# Makefile
# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

# Package name
PACKAGE := thermalright-lcd-control

# Get version from pyproject.toml
VERSION := $(shell python3 -c 'import toml; print(toml.load("pyproject.toml")["project"]["version"])')

# Sources to package
SOURCES := src resources pyproject.toml

# Output directory
DIST_DIR := releases

# Signing key
GPG_KEY=/home/rbenrejeb/.ssh/rbr_gpg.key

.PHONY: clean prepare-dist build-tar-gz


# Prepare dist directory
prepare-dist:
	mkdir -p $(DIST_DIR)

build-tar-gz: prepare-dist
	@echo "Creating TAR.GZ package using create_package.sh..."
	bash create_package.sh
	@echo "TAR.GZ package created successfully!"

clean:
	rm -rf $(DIST_DIR)
	rm -rf rpmbuild
	rm -rf build

# Build both packages
build-all: clean build-tar-gz