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

.PHONY: build-fpm-deb build-fpm-rpm clean prepare-dist build-tar-gz


# Prepare dist directory
prepare-dist:
	mkdir -p $(DIST_DIR)


# FPM - Package DEB
build-fpm-deb: prepare-dist
	fpm -s dir -t deb \
		-n $(PACKAGE) \
		-v $(VERSION) \
		-p $(DIST_DIR)/$(PACKAGE)_$(VERSION)_all.deb \
		--description "Linux Thermal Right LCD display control" \
		--license "Apache-2.0" \
		--maintainer "REJEB BEN REJEB <benrejebrejeb@gmail.com>" \
  		--vendor "REJEB BEN REJEB" \
		--category "utils" \
		--url "https://www.github.com/rejeb/thermalright-lcd-control" \
		--depends python3 \
		--depends python3-venv \
		--depends "libhidapi-hidraw0 | libhidapi-libusb0" \
		--after-install scripts/postinst \
		--before-install scripts/preinst \
		--force \
		--deb-no-default-config-files \
		./resources/config/=/etc/$(PACKAGE)/config/ \
		./resources/themes/=/etc/$(PACKAGE)/ \
		./src/=/usr/lib/$(PACKAGE)/ \
		./pyproject.toml=/usr/lib/$(PACKAGE)/pyproject.toml \
		./README.md=/usr/lib/$(PACKAGE)/README.md \
		./LICENSE=/usr/share/doc/$(PACKAGE)/copyright/LICENSE \
		./scripts/thermalright-lcd-control.service=/lib/systemd/system/thermalright-lcd-control.service \
		./resources/gui_config.yaml=/etc/$(PACKAGE)/gui_config.yaml \
		./resources/themes/=/usr/share/$(PACKAGE)/themes/ \
		./scripts/usr/bin/$(PACKAGE)=/usr/bin/$(PACKAGE) \
		./scripts/thermalright-lcd-control.desktop=/usr/share/applications/thermalright-lcd-control.desktop \
		./resources/32x32/icon.png=/usr/share/icons/hicolor/32x32/apps/thermalright-lcd-control.png \
		./resources/48x48/icon.png=/usr/share/icons/hicolor/48x48/apps/thermalright-lcd-control.png \
		./resources/64x64/icon.png=/usr/share/icons/hicolor/64x64/apps/thermalright-lcd-control.png \
		./resources/128x128/icon.png=/usr/share/icons/hicolor/128x128/apps/thermalright-lcd-control.png \
		./resources/256x256/icon.png=/usr/share/icons/hicolor/256x256/apps/thermalright-lcd-control.png

# FPM - Package RPM
build-fpm-rpm: prepare-dist
	fpm -s dir -t rpm \
		-n $(PACKAGE) \
		-v $(VERSION) \
		-p $(DIST_DIR)/$(PACKAGE)-$(VERSION)-1.noarch.rpm \
		--description "Linux Thermal Right LCD display control" \
		--license Apache-2.0 \
		--maintainer "Rejeb <benrejebrejeb@gmail.com>" \
		--url "https://www.github.com/rejeb/thermalright-lcd-control" \
  		--vendor "REJEB BEN REJEB" \
		--category "utils" \
		--depends python3 \
		--depends python3-virtualenv \
		--depends hidapi-devel \
		--before-install scripts/preinst \
		--after-install scripts/postinst \
		--force \
		./src/=/usr/lib/$(PACKAGE)/ \
		./pyproject.toml=/usr/lib/$(PACKAGE)/pyproject.toml \
		./README.md=/usr/lib/$(PACKAGE)/README.md \
		./LICENSE=/usr/share/doc/$(PACKAGE)/copyright/LICENSE \
		./scripts/thermalright-lcd-control.service=/usr/lib/systemd/system/thermalright-lcd-control.service \
		./resources/config/=/etc/$(PACKAGE)/config/ \
		./resources/gui_config.yaml=/etc/$(PACKAGE)/gui_config.yaml \
		./resources/themes/=/usr/share/$(PACKAGE)/themes/ \
		./scripts/usr/bin/thermalright-lcd-control=/usr/bin/thermalright-lcd-control \
		./scripts/thermalright-lcd-control.desktop=/usr/share/applications/thermalright-lcd-control.desktop \
		./resources/32x32/icon.png=/usr/share/icons/hicolor/32x32/apps/thermalright-lcd-control.png \
		./resources/48x48/icon.png=/usr/share/icons/hicolor/48x48/apps/thermalright-lcd-control.png \
		./resources/64x64/icon.png=/usr/share/icons/hicolor/64x64/apps/thermalright-lcd-control.png \
		./resources/128x128/icon.png=/usr/share/icons/hicolor/128x128/apps/thermalright-lcd-control.png \
		./resources/256x256/icon.png=/usr/share/icons/hicolor/256x256/apps/thermalright-lcd-control.png

build-tar-gz: prepare-dist
	@echo "Creating TAR.GZ package using create_package.sh..."
	bash create_package.sh
	@echo "TAR.GZ package created successfully!"

clean:
	rm -rf $(DIST_DIR)
	rm -rf rpmbuild
	rm -rf build

# Build both packages
build-all: clean build-fpm-deb build-fpm-rpm build-tar-gz