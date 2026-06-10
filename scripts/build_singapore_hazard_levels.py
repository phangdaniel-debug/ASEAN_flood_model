"""
Backward-compat shim.  Canonical implementation: build_hazard_levels.py.
"""
from __future__ import annotations

import runpy
import sys
import warnings
from pathlib import Path

warnings.warn(
    "build_singapore_hazard_levels.py is deprecated; use build_hazard_levels.py.",
    DeprecationWarning,
    stacklevel=2,
)

_TARGET = Path(__file__).with_name("build_hazard_levels.py")
sys.argv[0] = str(_TARGET)
runpy.run_path(str(_TARGET), run_name="__main__")
