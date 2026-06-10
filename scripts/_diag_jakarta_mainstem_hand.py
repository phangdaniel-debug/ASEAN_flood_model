"""Jakarta J2 main-stem HAND viability sweep (mirrors KL Plan 8 _diag_hand_extent_tradeoff).

The J1 CRR crash = the DENSE single-stage Ciliwung HAND (hand_utm48s.tif) floods a uniform
4.30 m RP100 overbank across flat Jakarta, drowning the central-levee dry controls (Menteng,
Gambir, Cipete). Fix = reference HAND to flow-accumulation channels at the Ciliwung GloFAS-reach
catchment scale (Depok ~370 km²), NOT the dense network. This sweep picks the threshold:
it must (a) REACH the Ciliwung-corridor positives, (b) SPARE the levee dry controls, (c) give a
credible bounded extent (not whole-domain — the KL 875 km² guard). Anchored to the ~370 km²
reach, gate as consistency check.
"""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, rasterio, csv
from pyproj import Transformer
from model.hand_model import compute_hand, derive_drainage_mask_from_accumulation

DEM = "data/jakarta/copernicus_dem_utm48s_subsidence_corrected.tif"
STAGE = 4.30   # RP100 fluvial overbank (m) the HAND is thresholded against
THRESHOLDS = [20000, 50000, 100000, 200000, 411000]   # px; ×900 m² = 18/45/90/180/370 km²

with rasterio.open(DEM) as ds:
    z = ds.read(1).astype(np.float32); prof = ds.profile; nod = ds.nodata; T = ds.transform; crs = ds.crs
zf = np.where(z == nod, np.nan, z) if nod is not None else z
fin = np.isfinite(zf); dom_km2 = fin.sum() * 900 / 1e6

rows = list(csv.DictReader(open("data/jakarta/manifest/hotspots.csv", encoding="utf-8")))
tf = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
# Spots that decide the threshold:
CILIWUNG_POS = {"Kampung Melayu", "Bukit Duri", "Kampung Pulo", "Cawang", "Bidara Cina"}
LEVEE_DRY    = {"Menteng", "Gambir", "Cipete", "Pasar Minggu"}
def rc(lon, lat):
    x, y = tf.transform(lon, lat); c, r = ~T * (x, y); return int(r), int(c)
pts = {row["name"]: rc(float(row["lon"]), float(row["lat"])) for row in rows}

def hand_at(hand, name, win=2):
    r, c = pts[name]
    sub = hand[max(0, r-win):r+win+1, max(0, c-win):c+win+1]
    sub = sub[np.isfinite(sub)]
    return float(sub.min()) if sub.size else np.nan

print(f"domain {dom_km2:.0f} km2 | stage {STAGE} m | RP100 reached = HAND<{STAGE}")
print(f"{'thr(px)':>8}{'catch_km2':>10}{'cells':>8}{'ext_km2':>9}{'ext%':>6} | "
      f"{'Ciliwung+ (min HAND)':>22} | {'levee-dry (min HAND)':>22}")
for thr in THRESHOLDS:
    src = derive_drainage_mask_from_accumulation(zf.astype(np.float32), prof, acc_threshold=thr)
    src = src & fin
    if src.sum() == 0:
        print(f"{thr:>8}{thr*900/1e6:>10.0f}{0:>8}  (no channels)"); continue
    hand = compute_hand(zf.astype(np.float32), src, prof)
    wet = np.isfinite(hand) & (hand < STAGE)
    pos_h = {n: hand_at(hand, n) for n in CILIWUNG_POS}
    dry_h = {n: hand_at(hand, n) for n in LEVEE_DRY}
    pos_reached = sum(1 for v in pos_h.values() if np.isfinite(v) and v < STAGE)
    dry_spared  = sum(1 for v in dry_h.values() if not (np.isfinite(v) and v < STAGE))
    print(f"{thr:>8}{thr*900/1e6:>10.0f}{int(src.sum()):>8}{wet.sum()*900/1e6:>9.0f}"
          f"{100*wet.sum()/fin.sum():>5.0f}% | reached {pos_reached}/{len(CILIWUNG_POS)}"
          f"  spared {dry_spared}/{len(LEVEE_DRY)}")
    # detail
    print("           positives:", {n: round(v,1) for n,v in pos_h.items()})
    print("           levee-dry:", {n: round(v,1) for n,v in dry_h.items()})
