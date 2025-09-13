# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
import subprocess
import threading
from functools import wraps


def async_background(daemon=True):
    """
    Simple decorator using threading (built-in)
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            thread = threading.Thread(target=func, args=args, kwargs=kwargs)
            thread.daemon = daemon
            thread.start()
            return thread

        return wrapper

    return decorator


def _get_default_font_path():
    return _get_detailed_font_info()["file"]


def _get_default_font_name():
    return _get_detailed_font_info()["fullname"]


def _get_detailed_font_info():
    formats = {
        "file": "%{file}",
        "fullname": "%{fullname}",
    }

    info = {}
    for key, format_str in formats.items():
        try:
            result = subprocess.check_output(
                ["fc-match", ":weight=bold", f"--format={format_str}"],
                text=True
            ).strip()
            info[key] = result
        except subprocess.CalledProcessError:
            info[key] = "Not available"

    return info
