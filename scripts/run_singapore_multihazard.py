"""
Backward-compat shim.  The canonical implementation now lives in
`scripts/run_multihazard.py` (generic across all ASEAN city configs).
This stub re-executes the new module so existing commands and notes
continue to work unchanged.
"""
from __future__ import annotations

import runpy
import sys
import warnings
from pathlib import Path

warnings.warn(
    "run_singapore_multihazard.py is deprecated; use run_multihazard.py instead.",
    DeprecationWarning,
    stacklevel=2,
)

_TARGET = Path(__file__).with_name("run_multihazard.py")
sys.argv[0] = str(_TARGET)
runpy.run_path(str(_TARGET), run_name="__main__")
