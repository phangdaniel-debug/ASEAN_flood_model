import rasterio
paths = {
    "v3 glo30":        r"D:\GPTs\Projects\flood-v3.0\dem\kl\glo30_dsm_utm47n.tif",
    "v2 copernicus":   r"D:\GPTs\Projects\flood-v2.0\data\kuala_lumpur\copernicus_dem_utm47n.tif",
    "bcov (v3)":       r"D:\GPTs\Projects\flood-v3.0\dem\kl\auxdata\building_coverage_utm47n.tif",
    "canopy meta (v3)":r"D:\GPTs\Projects\flood-v3.0\dem\kl\auxdata\canopy_meta_chm_kl.tif",
    "worldcover (v3)": r"D:\GPTs\Projects\flood-v3.0\dem\kl\auxdata\worldcover_2021_N00E099.tif",
    "deltadtm (v3)":   r"D:\GPTs\Projects\flood-v3.0\dem\kl\auxdata\deltadtm_kl.tif",
    "v2 hand_mainstem":r"D:\GPTs\Projects\flood-v2.0\data\kuala_lumpur\hand_mainstem_utm47n.tif",
}
for tag, p in paths.items():
    try:
        with rasterio.open(p) as r:
            print(f"{tag:18} crs={r.crs} size={r.width}x{r.height} res={tuple(round(x,4) for x in r.res)} "
                  f"bounds={tuple(round(x,1) for x in r.bounds)}")
    except Exception as e:
        print(f"{tag:18} ERROR {e}")
