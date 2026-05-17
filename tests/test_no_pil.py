# SPDX-License-Identifier: Apache-2.0
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_pil_imports_anywhere():
    res = subprocess.run(
        ["grep", "-rn", r"from PIL\|import PIL", "src", "tests"],
        cwd=ROOT, capture_output=True, text=True)
    hits = [line for line in res.stdout.splitlines()
            if "test_no_pil.py" not in line]
    assert not hits, "PIL still imported:\n" + "\n".join(hits)
