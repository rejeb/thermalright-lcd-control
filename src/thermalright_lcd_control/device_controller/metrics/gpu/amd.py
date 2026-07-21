# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""AMD GPU metrics (sysfs/hwmon/debugfs, rocm-smi fallback).

Mixed into :class:`GpuMetrics`; relies on the shared state initialised there
(``amd_card_path``/``amd_card_index``/``amd_pci_bdf``/``amd_hwmon_base``, the
``_temp_*``/``_usage_*``/``_freq_*`` path caches, ``gpu_temp``/``gpu_usage``/
``gpu_freq``, ``logger``) and the shared ``_read_file_float`` helper.
"""
import glob
import os
import re
import subprocess


class AmdMixin:
    def _is_amd_available(self):
        # sysfs vendor check
        for vendor_file in glob.glob("/sys/class/drm/card*/device/vendor"):
            try:
                with open(vendor_file) as f:
                    if f.read().strip().lower() == "0x1002":
                        return True
            except Exception:
                continue
        # rocm-smi availability (optional)
        try:
            r = subprocess.run(["rocm-smi", "--showid"], capture_output=True, text=True, timeout=3)
            return r.returncode == 0
        except Exception:
            return False

    # ---------- AMD card selection ----------

    def _enumerate_amd_cards(self):
        """
        Gather AMD cards with basic attributes used to prefer a discrete GPU.
        """
        cards = []
        for card_dev in glob.glob("/sys/class/drm/card*/device"):
            try:
                with open(os.path.join(card_dev, "vendor")) as f:
                    if f.read().strip().lower() != "0x1002":
                        continue
            except Exception:
                continue

            # card index X from /sys/class/drm/cardX/device
            m = re.search(r"/card(\d+)/device$", card_dev)
            card_idx = int(m.group(1)) if m else None

            real = os.path.realpath(card_dev)  # .../0000:bb:dd.f
            bdf = os.path.basename(real)
            bus = None
            if ":" in bdf:
                # 0000:bb:dd.f -> bb is PCI bus
                try:
                    bus = bdf.split(":")[1]
                except Exception:
                    bus = None

            # VRAM total (bytes). APUs typically have small visible VRAM.
            vram_total = 0
            try:
                with open(os.path.join(card_dev, "mem_info_vram_total")) as f:
                    vram_total = int(f.read().strip())
            except Exception:
                pass

            cards.append({
                "card_dev": card_dev,
                "card_idx": card_idx,
                "bdf": bdf,
                "bus": bus,
                "vram_total": vram_total
            })
        return cards

    def _score_amd_card(self, info):
        """
        Heuristic:
          +100 if PCI bus != "00" (very likely discrete on a separate bus)
          +50  if VRAM >= 1 GiB
          +10  if higher card index (common that iGPU is card0, dGPU is card1+)
          +5   if pp_dpm_sclk exists (power DPM often richer on dGPU)
        """
        score = 0
        if info.get("bus") and info["bus"] != "00":
            score += 100
        if info.get("vram_total", 0) >= (1 << 30):
            score += 50
        if isinstance(info.get("card_idx"), int):
            score += max(0, info["card_idx"]) // 1 * 10
        if os.path.exists(os.path.join(info["card_dev"], "pp_dpm_sclk")):
            score += 5
        return score

    def _get_hwmon_base_for_card(self, card_dev_dir):
        """
        Resolve the hwmon directory for a specific amdgpu card.
        """
        for h in glob.glob(os.path.join(card_dev_dir, "hwmon", "hwmon*")):
            # Sanity check the 'name' file to ensure it's amdgpu
            try:
                with open(os.path.join(h, "name")) as f:
                    if "amdgpu" in f.read().strip().lower():
                        return h
            except Exception:
                continue
        return None

    def _select_amd_card(self):
        """
        Choose the best AMD card (prefer discrete), and cache its paths.
        """
        cards = self._enumerate_amd_cards()
        if not cards:
            return

        # Allow manual override via env (e.g., "1" -> card1)
        env_idx = os.environ.get("AMD_GPU_CARD_INDEX")
        chosen = None

        if env_idx is not None:
            try:
                env_idx = int(env_idx)
                chosen = next((c for c in cards if c["card_idx"] == env_idx), None)
            except Exception:
                chosen = None

        if chosen is None:
            # Score-based selection
            scored = sorted(cards, key=lambda c: self._score_amd_card(c), reverse=True)
            chosen = scored[0]

        self.amd_card_path = chosen["card_dev"]
        self.amd_card_index = chosen["card_idx"]
        self.amd_pci_bdf = chosen["bdf"]
        self.amd_hwmon_base = self._get_hwmon_base_for_card(self.amd_card_path)

        self.logger.debug(
            f"Selected AMD card: card{self.amd_card_index} @ {self.amd_pci_bdf}, "
            f"hwmon={self.amd_hwmon_base}"
        )

    # ---------- name ----------

    def _get_amd_name(self):
        # Try rocm-smi product name
        try:
            r = subprocess.run(["rocm-smi", "--showproductname"],
                               capture_output=True, text=True, timeout=4)
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    if "Card series:" in line:
                        return line.split(":", 1)[1].strip()
        except Exception:
            pass
        # Fallback: sysfs device id of the selected card
        dev_paths = [self.amd_card_path] if self.amd_card_path else glob.glob("/sys/class/drm/card*/device")
        for dev_path in dev_paths:
            try:
                with open(os.path.join(dev_path, "vendor")) as f:
                    if f.read().strip().lower() != "0x1002":
                        continue
                with open(os.path.join(dev_path, "device")) as f:
                    devid = f.read().strip()
                return f"AMD GPU (Device {devid})"
            except Exception:
                continue
        return "AMD GPU"

    # ---------- temperature ----------

    def _amd_hwmon_temp(self):
        """
        Prefer 'junction'/'hotspot' label if present, else 'edge' for the selected card.
        temp*_input is millidegrees.
        """
        # Use cache if available
        if self._temp_method_cache == "amd_hwmon" and self._temp_path_cache:
            v = self._read_file_float(self._temp_path_cache, scale=1/1000.0)
            if v is not None:
                return v
            # Invalidate cache on failure
            self._temp_path_cache = None
            self._temp_method_cache = None

        bases = []
        if self.amd_hwmon_base:
            bases.append(self.amd_hwmon_base)
        else:
            # Fallback: search (shouldn't happen often)
            for name_file in glob.glob("/sys/class/hwmon/hwmon*/name"):
                try:
                    with open(name_file) as f:
                        if "amdgpu" in f.read().strip().lower():
                            bases.append(os.path.dirname(name_file))
                except Exception:
                    continue

        for base in bases:
            try:
                labels = {}
                for lbl in glob.glob(os.path.join(base, "temp*_label")):
                    m = re.search(r"temp(\d+)_label$", lbl)
                    if not m:
                        continue
                    idx = m.group(1)
                    try:
                        with open(lbl) as f:
                            labels[idx] = f.read().strip().lower()
                    except Exception:
                        pass

                # pick best
                pick = None
                for idx, lab in labels.items():
                    if any(k in lab for k in ("junction", "hotspot", "tjunction")):
                        pick = idx
                        break
                if not pick:
                    for idx, lab in labels.items():
                        if "edge" in lab:
                            pick = idx
                            break

                if pick:
                    p = os.path.join(base, f"temp{pick}_input")
                    if os.path.exists(p):
                        v = self._read_file_float(p, scale=1/1000.0)
                        if v is not None:
                            self._temp_path_cache = p
                            self._temp_method_cache = "amd_hwmon"
                            return v

                # fallback: first temp*_input
                inputs = sorted(glob.glob(os.path.join(base, "temp*_input")))
                if inputs:
                    v = self._read_file_float(inputs[0], scale=1/1000.0)
                    if v is not None:
                        self._temp_path_cache = inputs[0]
                        self._temp_method_cache = "amd_hwmon"
                        return v
            except Exception:
                continue
        return None

    def _get_amd_temperature(self):
        # 1) hwmon bound to the selected card
        v = self._amd_hwmon_temp()
        if v is not None:
            self.gpu_temp = v
            self.logger.debug(f"AMD GPU temperature (hwmon): {v:.1f}°C")
            return v
        # 2) rocm-smi (may not map to a specific card reliably)
        try:
            r = subprocess.run(["rocm-smi", "--showtemp"],
                               capture_output=True, text=True, timeout=4)
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    if "Temperature:" in line:
                        s = line.split(":", 1)[1].strip().lower().replace("°c", "").replace("c", "")
                        self.gpu_temp = float(s)
                        self.logger.debug(f"AMD GPU temperature (rocm-smi): {self.gpu_temp}°C")
                        return self.gpu_temp
        except Exception:
            pass
        return None

    # ---------- usage ----------

    def _get_amd_usage(self):
        """
        Use the selected AMD card's instantaneous busy percent.
        """
        # Use cache if available
        if self._usage_path_cache:
            try:
                with open(self._usage_path_cache) as f:
                    self.gpu_usage = float(f.read().strip())
                    return self.gpu_usage
            except Exception:
                self._usage_path_cache = None

        if self.amd_card_path:
            p = os.path.join(self.amd_card_path, "gpu_busy_percent")
            try:
                with open(p) as f:
                    self.gpu_usage = float(f.read().strip())
                    self._usage_path_cache = p
                    self.logger.debug(f"AMD GPU usage: {self.gpu_usage:.1f}% (from {p})")
                    return self.gpu_usage
            except Exception:
                pass

        # Fallback search (should be rare)
        for p in glob.glob("/sys/class/drm/card*/device/gpu_busy_percent"):
            try:
                with open(p) as f:
                    self.gpu_usage = float(f.read().strip())
                    self._usage_path_cache = p
                    self.logger.debug(f"AMD GPU usage: {self.gpu_usage:.1f}% (from {p})")
                    return self.gpu_usage
            except Exception:
                continue

        # rocm-smi fallback (no cache due to expensive subprocess)
        try:
            r = subprocess.run(["rocm-smi", "--showuse"],
                               capture_output=True, text=True, timeout=4)
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    if "GPU use (%)" in line:
                        s = line.split(":", 1)[1].strip().replace("%", "")
                        self.gpu_usage = float(s)
                        self.logger.debug(f"AMD GPU usage (rocm-smi): {self.gpu_usage:.1f}%")
                        return self.gpu_usage
        except Exception:
            pass
        return None

    # ---------- frequency ----------

    def _amd_freq_from_pp_dpm(self, card_dev_dir):
        # Use cache if available
        if self._freq_method_cache == "pp_dpm" and self._freq_path_cache:
            try:
                with open(self._freq_path_cache) as f:
                    for line in f:
                        if "*" in line:
                            mhz = re.search(r"(\d+)\s*MHz", line, re.IGNORECASE)
                            if mhz:
                                return float(mhz.group(1))
            except Exception:
                self._freq_path_cache = None
                self._freq_method_cache = None

        p = os.path.join(card_dev_dir, "pp_dpm_sclk")
        try:
            with open(p) as f:
                # lines like: "0: 300Mhz", "1: 500Mhz *"
                current = None
                for line in f:
                    if "*" in line:
                        current = line
                        break
                if not current:
                    return None
                mhz = re.search(r"(\d+)\s*MHz", current, re.IGNORECASE)
                if mhz:
                    self._freq_path_cache = p
                    self._freq_method_cache = "pp_dpm"
                    return float(mhz.group(1))
        except Exception:
            pass
        return None

    def _amd_freq_from_hwmon(self):
        # Use cache if available
        if self._freq_method_cache == "hwmon" and self._freq_path_cache:
            try:
                hz = self._read_file_float(self._freq_path_cache, scale=1.0)
                if hz and hz > 0:
                    return round(hz / 1_000_000.0, 2)
            except Exception:
                self._freq_path_cache = None
                self._freq_method_cache = None

        # some kernels expose freq1_input (Hz) under the selected amdgpu hwmon
        base = self.amd_hwmon_base
        if not base:
            return None
        f1 = os.path.join(base, "freq1_input")
        try:
            if os.path.exists(f1):
                hz = self._read_file_float(f1, scale=1.0)
                if hz and hz > 0:
                    self._freq_path_cache = f1
                    self._freq_method_cache = "hwmon"
                    return round(hz / 1_000_000.0, 2)  # Hz → MHz
        except Exception:
            pass
        return None

    def _amd_freq_from_debugfs(self):
        """
        Match the debugfs node by PCI BDF (in dri/*/name) to the selected card.
        """
        # Use cache if available
        if self._freq_method_cache == "debugfs" and self._freq_path_cache:
            try:
                with open(self._freq_path_cache) as f:
                    txt = f.read()
                m = re.search(r"GPU\s+clock:\s+(\d+)\s*MHz", txt, re.IGNORECASE)
                if m:
                    return float(m.group(1))
            except Exception:
                self._freq_path_cache = None
                self._freq_method_cache = None

        if not self.amd_pci_bdf:
            return None
        for d in glob.glob("/sys/kernel/debug/dri/*"):
            try:
                namef = os.path.join(d, "name")
                if not os.path.exists(namef):
                    continue
                with open(namef) as f:
                    name_txt = f.read().strip()
                # example content: "amdgpu dev=0000:65:00.0 ..."
                if self.amd_pci_bdf in name_txt and "amdgpu" in name_txt:
                    info = os.path.join(d, "amdgpu_pm_info")
                    if os.path.exists(info):
                        with open(info) as f:
                            txt = f.read()
                        m = re.search(r"GPU\s+clock:\s+(\d+)\s*MHz", txt, re.IGNORECASE)
                        if m:
                            self._freq_path_cache = info
                            self._freq_method_cache = "debugfs"
                            return float(m.group(1))
            except Exception:
                continue
        return None

    def _get_amd_frequency(self):
        # Ensure a card is chosen
        if not self.amd_card_path:
            self._select_amd_card()

        # 1) pp_dpm_sclk on selected card
        v = self._amd_freq_from_pp_dpm(self.amd_card_path) if self.amd_card_path else None
        if v:
            self.gpu_freq = round(v, 2)
            self.logger.debug(f"AMD GPU freq (pp_dpm_sclk): {self.gpu_freq} MHz")
            return self.gpu_freq

        # 2) hwmon freq1_input of selected card
        v = self._amd_freq_from_hwmon()
        if v:
            self.gpu_freq = v
            self.logger.debug(f"AMD GPU freq (hwmon): {self.gpu_freq} MHz")
            return self.gpu_freq

        # 3) debugfs amdgpu_pm_info matched by BDF
        v = self._amd_freq_from_debugfs()
        if v:
            self.gpu_freq = v
            self.logger.debug(f"AMD GPU freq (debugfs): {self.gpu_freq} MHz")
            return self.gpu_freq

        return None
