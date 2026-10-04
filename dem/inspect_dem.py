"""Quick metadata inspection of a DEM (CRS, res, bounds, nodata, stats)."""
import sys
import numpy as np
import rasterio
from pyproj import CRS

path = sys.argv[1]
with rasterio.open(path) as src:
    crs = CRS.from_user_input(src.crs)
    print("path        :", path)
    print("driver      :", src.driver)
    print("size        :", src.width, "x", src.height)
    print("res (m)     :", src.res)
    print("crs         :", src.crs)
    print("crs name    :", crs.name)
    print("is_projected:", crs.is_projected)
    print("axis units  :", [ax.unit_name for ax in crs.axis_info])
    print("bounds      :", src.bounds)
    print("nodata      :", src.nodata)
    a = src.read(1, masked=True)
    print("elev min/med/max (m):",
          float(a.min()), float(np.ma.median(a)), float(a.max()))
    print("valid cells :", int(a.count()), "/", a.size)
