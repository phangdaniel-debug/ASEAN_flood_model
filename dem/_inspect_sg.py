import rasterio, numpy as np
paths = {
  "ETH_canopy_singapore_0p01": r"D:\GPTs\Projects\flood-v3.0\dem\singapore\auxdata\ETH_GlobalCanopyHeight_0p01deg_2020_singapore.tif",
  "ETH_canopy_global_0p01": r"D:\GPTs\Projects\flood-v3.0\dem\singapore\auxdata\_eth_canopy_0p01deg_global.tif",
  "worldcover_sg": r"D:\GPTs\Projects\flood-v3.0\dem\singapore\auxdata\worldcover_2021_N00E102.tif",
  "v2_glo30_sg": r"D:\GPTs\Projects\flood-v2.0\data\singapore\copernicus_dem_utm48n.tif",
  "v2_bcov_sg": r"D:\GPTs\Projects\flood-v2.0\data\singapore\building_coverage_utm48n.tif",
}
for name, p in paths.items():
    try:
        with rasterio.open(p) as s:
            print(f"=== {name} ===")
            print("  shape", s.shape, "crs", s.crs, "res", s.res, "nodata", s.nodata, "dtype", s.dtypes[0])
            b = s.bounds
            from rasterio.warp import transform_bounds
            ll = transform_bounds(s.crs, "EPSG:4326", b.left, b.bottom, b.right, b.top)
            print("  bounds_lonlat", tuple(round(x,4) for x in ll))
            if s.width*s.height < 5_000_000:
                a = s.read(1).astype("float64")
                nod = s.nodata
                v = a[np.isfinite(a)]
                if nod is not None:
                    v = v[v != nod]
                if v.size:
                    print("  vals min/med/mean/max", round(float(v.min()),2), round(float(np.median(v)),2), round(float(v.mean()),2), round(float(v.max()),2), "n", v.size)
    except Exception as e:
        print(f"=== {name} === ERR {e}")
