"""
Backward-compat shim.  Canonical implementation: fetch_uhslc_gauge.py.
"""
from __future__ import annotations

import runpy
import sys
import warnings
from pathlib import Path

warnings.warn(
    "fetch_gesla_singapore.py is deprecated; use fetch_uhslc_gauge.py.",
    DeprecationWarning,
    stacklevel=2,
)

_TARGET = Path(__file__).with_name("fetch_uhslc_gauge.py")
sys.argv[0] = str(_TARGET)
runpy.run_path(str(_TARGET), run_name="__main__")
