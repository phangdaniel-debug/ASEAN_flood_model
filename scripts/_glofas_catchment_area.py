"""Upstream catchment area at the KL GLoFAS sample point (the scale the fluvial
GEV discharge represents) -> the physical anchor for the HAND channel threshold."""
import sys, tempfile, os; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, rasterio
from rasterio.warp import transform as rio_transform
if not hasattr(np, "in1d"):
    np.in1d = np.isin  # pysheds 0.5 / numpy 2.0 shim (limitation #7)
from pysheds.grid import Grid

GL_LAT, GL_LON = 3.074, 101.578
DEM="data/kuala_lumpur/copernicus_dem_utm47n.tif"
with rasterio.open(DEM) as ds:
    crs=ds.crs; transform=ds.transform; H,W=ds.height,ds.width; dem=ds.read(1).astype("float32"); nod=ds.nodata
    prof=ds.profile
# pysheds accumulation (same pipeline as derive_drainage_mask_from_accumulation)
tmp=tempfile.NamedTemporaryFile(suffix=".tif",delete=False); tmp.close()
p=prof.copy(); p.update(dtype="float32",count=1,nodata=-9999.0)
dw=dem.copy(); dw[~np.isfinite(dw)]=-9999.0
with rasterio.open(tmp.name,"w",**p) as dst: dst.write(dw,1)
grid=Grid.from_raster(tmp.name); raw=grid.read_raster(tmp.name)
filled=grid.fill_pits(raw); filled=grid.fill_depressions(filled); inflated=grid.resolve_flats(filled)
fdir=grid.flowdir(inflated); acc=grid.accumulation(fdir)
acc=np.asarray(acc)
os.unlink(tmp.name)
# locate GLoFAS point in raster, snap to max-accumulation cell in a window (channel)
xs,ys=rio_transform("EPSG:4326",crs,[GL_LON],[GL_LAT]); col_f,row_f=~transform*(xs[0],ys[0])
row,col=int(row_f),int(col_f)
print(f"GLoFAS pt ({GL_LAT}N {GL_LON}E) -> raster row,col=({row},{col})")
for win in [0,2,5,10]:
    r0,r1=max(0,row-win),min(H,row+win+1); c0,c1=max(0,col-win),min(W,col+win+1)
    block=acc[r0:r1,c0:c1]; mx=float(np.nanmax(block))
    print(f"  window +-{win}px: max accumulation = {mx:,.0f} px = {mx*900/1e6:,.1f} km2")
print(f"\nFull-domain max accumulation (basin outlet): {np.nanmax(acc):,.0f} px = {np.nanmax(acc)*900/1e6:,.0f} km2")
