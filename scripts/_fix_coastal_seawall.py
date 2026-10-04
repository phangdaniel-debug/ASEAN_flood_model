"""Fix coastal over-prediction: burn a continuous coastline seawall crest into
each coastal city's DEM. Coastline = land pixels (sea_mask==1) within 2 cells of
sea (sea_mask==0); raised to max(DEM, crest_egm2008). Represents "the coast is
defended to crest X" at screening grade (documented protection levels).

Crests are metres above local MSL, converted to EGM2008 with the per-city MDT
offset (same as apply_flood_defenses.py).

Out: dem/_diag/<city>_seawall.tif
"""
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import binary_dilation

CITY = {
    # city: (base_dem, sea_mask, msl_egm2008, crest_msl_m)
    # crest_msl = CONTEMPORANEOUS (present-day) coastal-defence crest, above local MSL.
    # These block the RP100 still-water level (~1-2 m above MSL) but matter at higher
    # RPs / future SLR, where the post-2011 (+4 m SG) and NCICD (+4.8 m LWS JKT) upgrades apply.
    #   Bangkok  +2.10 m  (existing BMA flood-protection dike crest; UNESCAP/BMA)
    #   Jakarta  +2.0 m   (existing coastal wall ~1-2 m, Muara Baru concrete wall = 2 m,
    #                      actively overtopped by subsidence; NCICD design +4.8 m LWS is future.
    #                      Note: Jakarta coastal is subsidence-dominated, so crest barely matters.)
    #   Singapore +3.0 m  (pre-2011 reclamation/platform standard, e.g. East Coast;
    #                      +4 m applies only to post-2011 reclamation)
    "bangkok":   ("dem/_hand/bangkok_v3_debiased_defended.tif",
                  "data/bangkok/sea_mask_utm47n_framefix.tif", 1.1785, 2.10),
    "jakarta":   ("dem/jakarta/dem_bareearth_jakarta_present_conditioned.tif",
                  "data/jakarta/sea_mask_utm48s_framefix.tif", 0.9976, 2.0),
    "singapore": ("dem/singapore/dem_bareearth_singapore_present_conditioned.tif",
                  "data/singapore/sea_mask_utm48n_framefix.tif", 1.1588, 3.0),
}


def main():
    Path("dem/_diag").mkdir(parents=True, exist_ok=True)
    for city, (demp, seap, msl, crest_msl) in CITY.items():
        with rasterio.open(demp) as r:
            z = r.read(1); prof = r.profile; nd = r.nodata
        with rasterio.open(seap) as s:
            sm = s.read(1)
        land = (sm == 1); sea = (sm == 0)
        coast = land & binary_dilation(sea, iterations=2)
        crest = msl + crest_msl
        m = coast & np.isfinite(z) & (z != nd)
        znew = z.astype("float32").copy()
        znew[m] = np.maximum(z[m], crest)
        prof.update(dtype="float32")
        out = Path(f"dem/_diag/{city}_seawall.tif")
        with rasterio.open(out, "w", **prof) as d:
            d.write(znew, 1)
        print(f"{city:10s} coastline raised {int(m.sum()):,} px to {crest:.2f}m EGM2008 "
              f"(={crest_msl}m MSL) -> {out}")


if __name__ == "__main__":
    main()
