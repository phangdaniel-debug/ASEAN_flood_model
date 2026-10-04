"""Fix spurious coastal edge-flooding: the build_sea_mask NaN-BFS sweeps the
DEM's nodata BORDER FRAME (W/E/N domain edges) into 'sea', so the coastal
solver seeds from the lateral domain edges and floods inland up both sides.

Fix: a sea-mask pixel is only real ocean if it is within DIST_M of genuine
water (original Copernicus DEM <= 0 m). Sea pixels far from any real water are
the nodata frame -> reclassify to nodata (255) so they cannot seed coastal BFS.

Writes <sea_mask>_framefix.tif next to each input. Verifies edge columns.
"""
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import binary_opening, generate_binary_structure

OPEN_PX = 10  # opening radius: removes the thin (~5-15px) nodata border frame

CITY = {
    "bangkok":   ("data/bangkok/copernicus_dem_utm47n.tif",   "data/bangkok/sea_mask_utm47n.tif"),
    "jakarta":   ("data/jakarta/copernicus_dem_utm48s.tif",   "data/jakarta/sea_mask_utm48s.tif"),
    "singapore": ("data/singapore/copernicus_dem_utm48n.tif", "data/singapore/sea_mask_utm48n.tif"),
}


def main():
    st = generate_binary_structure(2, 1)
    for city, (demp, seap) in CITY.items():
        with rasterio.open(demp) as r:
            z = r.read(1).astype("float64"); znd = r.nodata
        with rasterio.open(seap) as s:
            sm = s.read(1); prof = s.profile
        sea = (sm == 0)
        realwater = np.isfinite(z) & (z != znd) & (z <= 0.0)
        # Opening strips the thin nodata border frame; union real water back so no
        # genuine ocean/channel is lost. The frame is nodata (not water) -> stays removed.
        new_sea = binary_opening(sea, structure=st, iterations=OPEN_PX) | (sea & realwater)
        removed = sea & ~new_sea
        new = sm.copy()
        new[removed] = 255  # nodata: not a coastal seed (was spurious frame-sea)
        out = Path(seap).with_name(Path(seap).stem + "_framefix.tif")
        prof.update(dtype="uint8")
        with rasterio.open(out, "w", **prof) as d:
            d.write(new.astype("uint8"), 1)
        px = abs(prof["transform"].a * prof["transform"].e) / 1e6
        before = int(sea[:, 0].sum() + sea[:, -1].sum())
        after = int(new_sea[:, 0].sum() + new_sea[:, -1].sum())
        wret = 100 * (new_sea & realwater).sum() / max(1, realwater.sum())
        print(f"{city:10s}: removed {removed.sum()*px:6.0f} km2 frame-sea | "
              f"L+R edge-col sea {before} -> {after} | water retained {wret:.0f}% | "
              f"sea {(sm==0).sum()*px:.0f}->{new_sea.sum()*px:.0f} km2 -> {out.name}")


if __name__ == "__main__":
    main()
