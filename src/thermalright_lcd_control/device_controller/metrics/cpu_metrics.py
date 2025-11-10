# SPDX-License-Identifier: Apache-2.0
import glob, os, re
import psutil
from thermalright_lcd_control.device_controller.metrics import Metrics
from thermalright_lcd_control.common.logging_config import LoggerConfig

class CpuMetrics(Metrics):
    """
    AMD-friendly CPU metrics with robust k10temp/zenpower scanning.
    Prefers Tdie > Tctl; falls back to first available temp*_input,
    else psutil, else thermal zones.
    """
    def __init__(self):
        super().__init__()
        self.logger = LoggerConfig.setup_service_logger()
        self.cpu_usage = 0.0
        self.cpu_temp = None
        self.cpu_freq = None

        # Cache to optimize performance
        self._temp_path_cache = None
        self._temp_method_cache = None
        self._freq_path_cache = None
        self._hwmon_roots_cache = None

    # ---------- helpers ----------
    def _read_float(self, path, scale=1.0):
        try:
            with open(path) as f:
                return float(f.read().strip()) * scale
        except Exception:
            return None

    def _list_hwmon_roots(self):
        # Cache hwmon roots to avoid repeated scans
        if self._hwmon_roots_cache is not None:
            return self._hwmon_roots_cache

        roots = set()
        # Generic hwmon
        roots.update(os.path.dirname(p) for p in glob.glob("/sys/class/hwmon/hwmon*/name"))
        # Common AMD device paths
        roots.update(glob.glob("/sys/devices/platform/k10temp.*/hwmon/hwmon*"))
        roots.update(glob.glob("/sys/devices/platform/k10temp/hwmon/hwmon*"))
        roots.update(glob.glob("/sys/devices/platform/zenpower.*/hwmon/hwmon*"))
        # If /device/name exists under hwmon, include those too
        for devname in glob.glob("/sys/class/hwmon/hwmon*/device/name"):
            roots.add(os.path.dirname(os.path.dirname(devname)))

        self._hwmon_roots_cache = sorted(roots)
        return self._hwmon_roots_cache

    def _amd_hwmon_candidates(self):
        """Return list of (root, driver_name_lower) for k10temp/zenpower only."""
        out = []
        for root in self._list_hwmon_roots():
            for namefile in (os.path.join(root, "name"),
                             os.path.join(root, "device", "name")):
                if os.path.exists(namefile):
                    try:
                        nm = open(namefile).read().strip().lower()
                    except Exception:
                        continue
                    if nm in ("k10temp", "zenpower"):
                        out.append((root, nm))
                        break
        return out

    def _pick_best_amd_temp(self, root):
        """
        From an AMD hwmon root, choose Tdie > Tctl > otherwise first reasonable temp*_input.
        """
        # Map labels
        labels = {}
        for lbl in glob.glob(os.path.join(root, "temp*_label")):
            m = re.search(r"temp(\d+)_label$", lbl)
            if not m: 
                continue
            idx = m.group(1)
            try:
                labels[idx] = open(lbl).read().strip().lower()
            except Exception:
                pass

        def read_idx(idx):
            p = os.path.join(root, f"temp{idx}_input")
            return self._read_float(p, 1/1000.0)

        # 1) Prefer Tdie
        for idx, lab in labels.items():
            if "tdie" in lab:
                v = read_idx(idx)
                if v is not None:
                    return v, f"{root}:temp{idx}_input (Tdie)"

        # 2) Then Tctl
        for idx, lab in labels.items():
            if "tctl" in lab:
                v = read_idx(idx)
                if v is not None:
                    return v, f"{root}:temp{idx}_input (Tctl)"

        # 3) Otherwise pick a reasonable sensor:
        #    prefer non-ccd sensors; if none, take max CCD (some systems only expose CCDs).
        inputs = sorted(glob.glob(os.path.join(root, "temp*_input")))
        non_ccd = []
        ccd = []
        for p in inputs:
            idx = re.search(r"temp(\d+)_input$", p).group(1)
            lab = labels.get(idx, "")
            v = self._read_float(p, 1/1000.0)
            if v is None:
                continue
            if "ccd" in lab:
                ccd.append((v, p))
            else:
                non_ccd.append((v, p))
        pick = (max(non_ccd) if non_ccd else (max(ccd) if ccd else (None, None)))
        if pick[0] is not None:
            tag = "non-CCD" if non_ccd else "CCD"
            return pick[0], f"{pick[1]} ({tag})"

        return None, None

    # ---------- temperature ----------
    def get_temperature(self):
        # Use cache if available
        if self._temp_path_cache and self._temp_method_cache:
            try:
                if self._temp_method_cache == "hwmon":
                    v = self._read_float(self._temp_path_cache, 1/1000.0)
                    if v is not None:
                        self.cpu_temp = v
                        return v
                elif self._temp_method_cache == "psutil":
                    temps = psutil.sensors_temperatures()
                    key, idx = self._temp_path_cache
                    if key in temps and len(temps[key]) > idx:
                        cur = getattr(temps[key][idx], "current", None)
                        if cur is not None:
                            self.cpu_temp = float(cur)
                            return self.cpu_temp
                elif self._temp_method_cache == "thermal":
                    v = self._read_float(self._temp_path_cache, 1/1000.0)
                    if v is not None:
                        self.cpu_temp = v
                        return v
            except Exception:
                # Invalidate cache on error
                self._temp_path_cache = None
                self._temp_method_cache = None

        # 1) AMD hwmon direct
        try:
            for root, drv in self._amd_hwmon_candidates():
                v, src = self._pick_best_amd_temp(root)
                if v is not None:
                    # Cache the found path
                    m = re.search(r"(.*temp\d+_input)", src)
                    if m:
                        self._temp_path_cache = m.group(1)
                        self._temp_method_cache = "hwmon"
                    self.cpu_temp = v
                    self.logger.debug(f"CPU temp via {drv}: {v:.1f}°C from {src}")
                    return v
        except Exception as e:
            self.logger.debug(f"AMD hwmon read failed: {e}")

        # 2) psutil (may already expose k10temp)
        try:
            temps = psutil.sensors_temperatures()
            # Try explicit k10temp/zenpower keys first
            for key in ("k10temp", "zenpower", "coretemp", "cpu-thermal", "acpitz"):
                if key in temps and temps[key]:
                    for idx, e in enumerate(temps[key]):
                        cur = getattr(e, "current", None)
                        if cur is not None:
                            self.cpu_temp = float(cur)
                            self._temp_path_cache = (key, idx)
                            self._temp_method_cache = "psutil"
                            self.logger.debug(f"CPU temp via psutil[{key}]: {self.cpu_temp:.1f}°C")
                            return self.cpu_temp
            # Otherwise, heuristically pick the first with a plausible current
            for name, entries in temps.items():
                for idx, e in enumerate(entries):
                    cur = getattr(e, "current", None)
                    if cur is not None and 0.0 < cur < 120.0:
                        self.cpu_temp = float(cur)
                        self._temp_path_cache = (name, idx)
                        self._temp_method_cache = "psutil"
                        self.logger.debug(f"CPU temp via psutil[{name}]: {self.cpu_temp:.1f}°C")
                        return self.cpu_temp
        except Exception as e:
            self.logger.debug(f"psutil sensors_temperatures failed: {e}")

        # 3) thermal zones (types include k10temp/zenpower/x86_pkg_temp/cpu)
        try:
            for type_file in glob.glob("/sys/class/thermal/thermal_zone*/type"):
                try:
                    tname = open(type_file).read().strip().lower()
                except Exception:
                    continue
                if not any(k in tname for k in ("k10temp", "zenpower", "x86_pkg_temp", "cpu")):
                    continue
                tfile = os.path.join(os.path.dirname(type_file), "temp")
                v = self._read_float(tfile, 1/1000.0)
                if v is not None and 0.0 < v < 120.0:
                    self.cpu_temp = v
                    self._temp_path_cache = tfile
                    self._temp_method_cache = "thermal"
                    self.logger.debug(f"CPU temp via thermal zone '{tname}': {v:.1f}°C")
                    return v
        except Exception as e:
            self.logger.debug(f"thermal zones failed: {e}")

        self.logger.warning("CPU temperature unavailable")
        return None

    # ---------- usage ----------
    def get_usage_percentage(self):
        try:
            # Use interval=None to avoid blocking; relies on previous call for accurate reading
            self.cpu_usage = psutil.cpu_percent(interval=0)
            return self.cpu_usage
        except Exception as e:
            self.logger.error(f"Error reading CPU usage: {e}")
            return 0.0

    # ---------- frequency ----------
    def _cpufreq_sysfs(self):
        # Use cache if available
        if self._freq_path_cache:
            v = self._read_float(self._freq_path_cache, 1/1000.0)
            if v:
                return round(v, 2)
            # Invalidate cache on failure
            self._freq_path_cache = None

        for p in ("/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq",
                  "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"):
            if os.path.exists(p):
                v = self._read_float(p, 1/1000.0)  # kHz -> MHz
                if v:
                    self._freq_path_cache = p
                    return round(v, 2)
        return None

    def get_frequency(self):
        try:
            fi = psutil.cpu_freq()
            if fi and fi.current:
                self.cpu_freq = round(float(fi.current), 2)
                return self.cpu_freq
            v = self._cpufreq_sysfs()
            if v:
                self.cpu_freq = v
                return v
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("cpu MHz"):
                        self.cpu_freq = round(float(line.split(":")[1]), 2)
                        return self.cpu_freq
        except Exception as e:
            self.logger.error(f"Error reading CPU frequency: {e}")
        return None

    # ---------- bundles ----------
    def get_all_metrics(self):
        return {
            "temperature": self.get_temperature(),
            "usage_percentage": self.get_usage_percentage(),
            "frequency": self.get_frequency(),
        }

    def get_metric_value(self, metric_name) -> str:
        if metric_name == "cpu_temperature":
            v = self.get_temperature(); return f"{v}" if v is not None else "N/A"
        if metric_name == "cpu_usage":
            v = self.get_usage_percentage(); return f"{v}" if v is not None else "N/A"
        if metric_name == "cpu_frequency":
            v = self.get_frequency(); return f"{v}" if v is not None else "N/A"
        return "N/A"

    def __str__(self):
        t = self.get_temperature()
        u = self.get_usage_percentage()
        f = self.get_frequency()
        t_s = f"{t:.1f}°C" if t is not None else "N/A"
        u_s = f"{u:.1f}%" if u is not None else "N/A"
        f_s = f"{f:.0f} MHz" if f is not None else "N/A"
        return f"CPU - Usage: {u_s}, Temperature: {t_s}, Frequency: {f_s}"
