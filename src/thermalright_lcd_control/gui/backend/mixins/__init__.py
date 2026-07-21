# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Domain mixins that compose :class:`AppBackend`.

Each mixin groups the slots/helpers for one domain (thumbnails, window chrome,
media helpers, backgrounds, foregrounds, overlay style, themes, device config).
The mixins carry no state of their own; ``AppBackend.__init__`` owns the shared
state they read (``self.preview``, ``self.config``, ``self.controller``, …).
"""
