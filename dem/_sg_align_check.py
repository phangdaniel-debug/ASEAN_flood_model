import rasterio
paths = {
    "glo30 (v2 copernicus)": r"D:\GPTs\Projects\flood-v2.0\data\singapore\copernicus_dem_utm48n.tif",
    "bcov (v2)":             r"D:\GPTs\Projects\flood-v2.0\data\singapore\building_coverage_utm48n.tif",
    "canopy clip (v3)":      r"D:\GPTs\Projects\flood-v3.0\dem\singapore\auxdata\canopy_eth_2020_singapore.tif",
    "worldcover (v3)":       r"D:\GPTs\Projects\flood-v3.0\dem\singapore\auxdata\worldcover_2021_N00E102.tif",
    "deltadtm (v3)":         r"D:\GPTs\Projects\flood-v3.0\dem\singapore\auxdata\deltadtm_singapore.tif",
}
for tag, p in paths.items():
    try:
        with rasterio.open(p) as r:
            b = tuple(round(x, 3) for x in r.bounds)
            print(f"{tag:22} crs={r.crs} size={r.width}x{r.height} res={tuple(round(x,4) for x in r.res)}")
            print(f"   bounds={b} nod={r.nodata}")
    except Exception as e:
        print(f"{tag:22} ERROR {e}")
