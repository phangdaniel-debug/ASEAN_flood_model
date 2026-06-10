"""
Documented-HWM point cross-check.

For a small set of well-documented historical high-water marks in published
literature, sample the modelled flood-depth raster at the matching grid
cell (with a small radius around the point for context) and report whether
the modelled value falls within a plausible band relative to the reported
HWM.

This is a *plausibility* check, not a contingency-table validation: the
HWMs are spatially sparse (a few points per city) and reported with
uncertainty (±0.5 m typical), so we report mean/min/max depth within a
small neighbourhood and a verdict band rather than a CSI metric.

The HWM registry is intentionally hard-coded with literature attribution.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform as rio_transform


@dataclass
class HWM:
    city: str
    label: str
    lon: float
    lat: float
    reported_m: float          # representative reported depth (m)
    reported_band: tuple[float, float]  # plausible band
    source: str
    out_dir: Path
    hazard: str                # "fluvial" | "pluvial" | "coastal" | "combined"
    rp: int


REGISTRY: list[HWM] = [
    HWM("bangkok",  "Don Mueang Airport (THA2011 megaflood)",
        100.605, 13.913, 2.3, (1.5, 3.0),
        "Promchote et al. (2016); RID post-event survey",
        Path("outputs/bangkok_chao_phraya_ssp585_2020"),
        "fluvial", 100),
    HWM("bangkok",  "Rangsit / Pathum Thani (THA2011)",
        100.620, 13.990, 1.8, (1.0, 2.5),
        "Komori et al. (2012) Hydrol. Res. Lett. 6:41",
        Path("outputs/bangkok_chao_phraya_ssp585_2020"),
        "fluvial", 100),
    HWM("jakarta",  "Cipinang Melayu (JKT 2020 floods)",
        106.892, -6.247, 1.7, (1.0, 2.5),
        "BNPB Sitrep; Sagala et al. (2021)",
        Path("outputs/jakarta_ssp585_2020"),
        "pluvial", 100),
    HWM("jakarta",  "Pluit polder (chronic, North Jakarta)",
        106.794, -6.115, 0.7, (0.3, 1.5),
        "Abidin et al. (2011) Nat. Hazards 59:1753",
        Path("outputs/jakarta_ssp585_2020"),
        "coastal", 10),
    HWM("manila",   "Marikina Valley (Ketsana 2009)",
        121.100, 14.650, 3.0, (2.0, 4.0),
        "Lagmay et al. (2017); Abon et al. (2011) HESS",
        Path("outputs/manila_ssp585_2020"),
        "fluvial", 100),
    HWM("hcmc",     "Phu My Hung / District 7 (subsidence-driven)",
        106.706, 10.722, 0.8, (0.3, 1.5),
        "Storch & Downes (2011); Trinh et al. (2017)",
        Path("outputs/hcmc_ssp585_2020"),   # 2020 baseline; falls back to 2100 if absent
        "coastal", 10),
    HWM("singapore","Stamford Canal / Orchard Rd (2010-11 floods)",
        103.832, 1.305, 0.4, (0.2, 0.7),
        "PUB (2011) Stamford Canal flood report",
        Path("outputs/singapore_ssp585_2020"),   # 2020 baseline; no SLR inflation
        "pluvial", 100),
    # Depth-bearing Singapore hotspots from the documented hotspot table
    # (data/singapore/flood_obs/hotspots/sg_pluvial_hotspots.csv). Scored at the
    # pluvial anchor RP50 against the SSP5-8.5/2100 pluvial run.
    HWM("singapore","Liat Towers / Orchard Rd (2010-11 floods)",
        103.8336, 1.3048, 0.3, (0.1, 0.6),
        "Floods in Singapore; Liat Towers 2011-12-23 & 2010-06 (~0.3 m)",
        Path("outputs/singapore_ssp585_2100"),
        "pluvial", 50),
    HWM("singapore","Bukit Timah Rd / Dunearn (2012/2017 floods)",
        103.792, 1.331, 0.25, (0.05, 0.55),
        "Floods in Singapore; Bukit Timah Rd 2012-05-05 ~0.25 m; ST 2017-06-13",
        Path("outputs/singapore_ssp585_2100"),
        "pluvial", 50),
]


def _find_depth_raster(out_dir: Path, hazard: str, rp: int) -> Path | None:
    cand = out_dir / hazard / f"rp_{rp}"
    if not cand.is_dir():
        return None
    # Look for a depth raster — common names: depth_*.tif, *_depth_*.tif
    tifs = list(cand.glob("*depth*.tif")) + list(cand.glob("*_max_*.tif"))
    if not tifs:
        tifs = list(cand.glob("*.tif"))
    return tifs[0] if tifs else None


def _sample(raster_path: Path, lon: float, lat: float, radius_px: int = 12):
    with rasterio.open(raster_path) as ds:
        xs, ys = rio_transform("EPSG:4326", ds.crs, [lon], [lat])
        col, row = ~ds.transform * (xs[0], ys[0])
        col, row = int(round(col)), int(round(row))
        h, w = ds.height, ds.width
        if not (0 <= row < h and 0 <= col < w):
            return None
        r0, r1 = max(0, row - radius_px), min(h, row + radius_px + 1)
        c0, c1 = max(0, col - radius_px), min(w, col + radius_px + 1)
        block = ds.read(1, window=((r0, r1), (c0, c1))).astype(np.float64)
        nodata = ds.nodata
        if nodata is not None:
            block = np.where(block == nodata, np.nan, block)
        block = np.where(np.isfinite(block), block, np.nan)
        if not np.isfinite(block).any():
            return {"center": np.nan, "max": np.nan, "mean": np.nan,
                    "n_wet": 0, "n_cells": int(block.size)}
        center = block[row - r0, col - c0]
        wet = block[np.isfinite(block) & (block > 0.01)]
        return {
            "center": float(center) if np.isfinite(center) else np.nan,
            "max":    float(np.nanmax(block)),
            "mean":   float(np.nanmean(wet)) if wet.size else 0.0,
            "n_wet":  int(wet.size),
            "n_cells": int(block.size),
        }


def main() -> None:
    R = 12  # radius in pixels; 25x25 block = ~750 m radius at 30 m
    print(f"{'City':<10} {'Label':<48} {'RP':>4} {'Hazard':<8} "
          f"{'Center':>7} {f'Max{2*R+1}x{2*R+1}':>8} {'Mean_wet':>8} {'Reported':>9}  Verdict")
    print("-" * 135)
    for h in REGISTRY:
        rast = _find_depth_raster(h.out_dir, h.hazard, h.rp)
        if rast is None:
            print(f"{h.city:<10} {h.label[:48]:<48} {h.rp:>4} {h.hazard:<8}  "
                  f"(no raster at {h.out_dir / h.hazard / f'rp_{h.rp}'})")
            continue
        s = _sample(rast, h.lon, h.lat, radius_px=R)
        if s is None:
            print(f"{h.city:<10} {h.label[:48]:<48} {h.rp:>4} {h.hazard:<8}  (point outside raster)")
            continue
        lo, hi = h.reported_band
        # Compare max within the neighbourhood (more robust than the exact pixel
        # because HWM coordinates are approximate neighbourhood-level references)
        import math
        if math.isnan(s["max"]):
            verdict = "OUTSIDE-DOMAIN"
        elif lo <= s["max"] <= hi:
            verdict = "IN-BAND"
        elif s["max"] < lo:
            verdict = "UNDER"
        else:
            verdict = "OVER"
        print(f"{h.city:<10} {h.label[:48]:<48} {h.rp:>4} {h.hazard:<8} "
              f"{s['center']:>7.2f} {s['max']:>8.2f} {s['mean']:>8.2f} "
              f"{h.reported_m:>5.1f} ({lo:.1f}-{hi:.1f})  {verdict}")


if __name__ == "__main__":
    main()
