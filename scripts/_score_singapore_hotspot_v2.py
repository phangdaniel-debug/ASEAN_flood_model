"""Score Singapore against its documented-hotspot register on the v2.0 operating point.

#4: bring Singapore into the IEEE paper's hotspot gate (Table III) on a basis
*consistent with KL/Bangkok/Jakarta* — RP100, 0.10 m depth threshold, combined
(coastal OR fluvial OR pluvial) wet-mask, present-day forcing — rather than the
flood-atlas-era SG operating point (RP50 / 150 m radius / pluvial-only / 2100).

The SG model itself is UNCHANGED between flood-atlas and v2.0; only the scoring
convention is re-aligned here. Rasters are read in place from flood-atlas; the
v2.0 `hotspot_scoring` engine does the sampling and bootstrap so the skill numbers
are produced by the identical code path as the other three cities.

Combined hit = ANY of the three RP100 depth rasters has a cell >= 0.10 m within the
hit-radius of the hotspot (equivalent to a per-pixel-max wet-mask, but robust to the
three rasters being on slightly different grids).
"""
from __future__ import annotations

import sys
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V2_ROOT / "scripts"))
from hotspot_scoring import load_hotspots, sample_hit, skill_scores, bootstrap_tss_ci  # noqa: E402

ATLAS = Path("D:/GPTs/Projects/flood-atlas")
REGISTER = ATLAS / "data/singapore/flood_obs/hotspots/sg_pluvial_hotspots.csv"
RASTERS = [
    ATLAS / "outputs/singapore_ssp585_2020/coastal/rp_100/coastal_depth_SSP5-8.5_2020_rp100.tif",
    ATLAS / "outputs/singapore_ssp585_2020/fluvial/rp_100/fluvial_depth_SSP5-8.5_2020_rp100.tif",
    ATLAS / "outputs/singapore_ssp585_2020/pluvial/rp_100/pluvial_depth_SSP5-8.5_2020_rp100.tif",
]
THRESH = 0.10


def combined_hit(h, radius_m: float) -> bool:
    return any(
        sample_hit(r, h.lon, h.lat, radius_m=radius_m, depth_threshold_m=THRESH)
        for r in RASTERS
    )


def main() -> None:
    hotspots = load_hotspots(REGISTER)
    n_flood = sum(1 for h in hotspots if h.cls == "flood")
    n_dry = sum(1 for h in hotspots if h.cls == "dry")
    for r in RASTERS:
        if not r.exists():
            raise SystemExit(f"missing raster: {r}")
    print(f"Singapore register: {n_flood} flood / {n_dry} dry  (combined coastal|fluvial|pluvial RP100, >= {THRESH} m)")
    print(f"{'radius':>8} | {'HR':>5} {'CRR':>5} {'TSS':>6} | 95% CI")
    print("-" * 52)
    for radius_m in (50.0, 150.0):
        flood_hits = [combined_hit(h, radius_m) for h in hotspots if h.cls == "flood"]
        dry_hits = [combined_hit(h, radius_m) for h in hotspots if h.cls == "dry"]
        sc = skill_scores(flood_hits, dry_hits)
        point, lo, hi = bootstrap_tss_ci(flood_hits, dry_hits)
        print(f"{radius_m:>6.0f} m | {sc.hit_rate:>5.2f} {sc.correct_reject_rate:>5.2f} "
              f"{sc.tss:>6.2f} | [{lo:+.2f}, {hi:+.2f}]")


if __name__ == "__main__":
    main()
