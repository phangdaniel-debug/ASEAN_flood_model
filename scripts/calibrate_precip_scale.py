"""
DEPRECATED (2026-04-26): pluvial pipeline now uses ERA5-Land directly.

The previous purpose of this script was to derive a MERRA-2 wet-bias
correction factor (precip_scale) per city.  Since 2026-04-26 the pluvial
fit reads ERA5-Land hourly (Open-Meteo) directly -- no MERRA-2 wet-bias
correction is needed, so there is nothing to calibrate.

If you were using this for the legacy MERRA-2 path, see:
  - docs/superpowers/specs/2026-04-26-pluvial-redesign.md
  - scripts/fit_pluvial_baseline_era5.py (rewritten 2026-04-26)
  - scripts/validate_pluvial_idf_anchors.py (new IDF anchor validator)
"""
from __future__ import annotations
import sys


def main() -> int:
    sys.stderr.write(
        "calibrate_precip_scale.py is DEPRECATED.\n"
        "The pluvial pipeline now uses ERA5-Land directly; no MERRA-2 wet-bias\n"
        "correction is needed.  See docs/superpowers/specs/2026-04-26-pluvial-redesign.md\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
