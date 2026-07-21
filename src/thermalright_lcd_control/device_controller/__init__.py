# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

# NOTE: deliberately empty. An eager import of controller/device_loader here
# would re-enter this package mid-import when a display.* submodule is imported
# (circular). Callers import from the concrete modules directly.
