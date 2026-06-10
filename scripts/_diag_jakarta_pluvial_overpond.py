"""Why does fill-spill pluvial flood the elevated-south dry controls? (Jakarta J2 residual)

Decides the pluvial-homogeneity-migration question: is the over-ponding a (a) RADIUS ARTEFACT
(the 50 m validator window catches a genuine lower depression downslope of an elevated pin —
KL Mont-Kiara pattern, a measurement-window issue, NOT model over-extent), (b) DEM-PIT ARTEFACT
(a spurious sharp local minimum the fill-spill fills — a DEM-conditioning issue), or (c) GENUINE
FILL-SPILL OVER-FILL / MISSING-DRAINAGE (a real depression over-filled by routed runoff with no
modelled outlet — the only case the KL raingrid + OSM-drainage migration would fix).
"""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, rasterio, csv
from pyproj import Transformer

DEM = "data/jakarta/copernicus_dem_utm48s_subsidence_corrected.tif"
PLU = "outputs/jakarta_ssp585_2020/pluvial/rp_100/pluvial_depth_SSP5-8.5_2020_rp100.tif"
EXCESS = 0.1495  # RP100 pluvial excess depth (m), uniform forcing
TARGETS = {"Jagakarsa", "Pondok Pinang", "Pasar Minggu"}  # the elevated-south FPs

with rasterio.open(DEM) as d:
    Z = d.read(1).astype(float); znod = d.nodata; T = d.transform; crs = d.crs
Z = np.where(Z == znod, np.nan, Z) if znod is not None else Z
with rasterio.open(PLU) as d:
    P = d.read(1).astype(float); pnod = d.nodata
P = np.where(np.isfinite(P), P, np.nan)
px = abs(T.a)  # 30 m
tf = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
rows = [r for r in csv.DictReader(open("data/jakarta/manifest/hotspots.csv", encoding="utf-8"))
        if r["name"] in TARGETS]

def window(A, r, c, rad_px):
    return A[max(0, r-rad_px):r+rad_px+1, max(0, c-rad_px):c+rad_px+1]

for row in rows:
    x, y = tf.transform(float(row["lon"]), float(row["lat"]))
    col, r = ~T * (x, y); r, col = int(r), int(col)
    pin_z = Z[r, col]
    # cells within the 50 m validator radius (distance from pin center)
    rad = 2  # 2 px = 60 m window; mask to <=50 m
    zwin = window(Z, r, col, rad); pwin = window(P, r, col, rad)
    rr, cc = np.mgrid[-min(r,rad):zwin.shape[0]-min(r,rad), -min(col,rad):zwin.shape[1]-min(col,rad)]
    dist = np.hypot(rr*px, cc*px)
    in50 = dist <= 50.0
    wet = in50 & np.isfinite(pwin) & (pwin > 0.10)
    # wider context (330 m) to judge pit-ness
    ctx = window(Z, r, col, 11); ctx = ctx[np.isfinite(ctx)]
    print(f"\n=== {row['name']}  (pin elev {pin_z:.1f} m) ===")
    if not wet.any():
        print("  no wet cell within 50 m (dry at validator radius)"); continue
    wd = pwin[wet]; wz = zwin[wet]; wdist = dist[wet]
    imax = np.argmax(wd)
    wet_z = wz[imax]; wet_depth = wd[imax]; wet_dist = wdist[imax]
    drop = pin_z - wet_z                       # how far downslope the wet cell is
    relief = float(np.nanmin(ctx)) ; ctx_med = float(np.nanmedian(ctx))
    pit_depth = ctx_med - wet_z                # how far below the 330 m median the wet cell sits
    print(f"  wettest cell in 50 m: depth={wet_depth:.2f} m  elev={wet_z:.1f} m  dist_from_pin={wet_dist:.0f} m")
    print(f"  downslope drop pin->wetcell: {drop:.1f} m   (large => 50m window caught a lower cell = RADIUS artefact)")
    print(f"  330 m context: median={ctx_med:.1f} m  min={relief:.1f} m   wetcell below-median={pit_depth:.1f} m")
    print(f"  fill depth {wet_depth:.2f} m vs RP100 excess {EXCESS:.3f} m  => {wet_depth/EXCESS:.0f}x concentration")
    # heuristic read
    if wet_dist > 30 and drop > 5:
        verdict = "RADIUS ARTEFACT (wet cell is a lower depression downslope; pin itself elevated/dry)"
    elif pit_depth > wet_depth and wet_dist <= 30:
        verdict = "DEM-PIT / over-fill at the pin (sharp local low filled)"
    else:
        verdict = "depression fill (check vs local relief / outlet)"
    print(f"  => likely: {verdict}")
