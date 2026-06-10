import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.city_manifest import load_hotspots_from_manifest
from scripts.hotspot_scoring import sample_score
RP=100; R=50.0; THR=0.10
PLUV=f"outputs/kuala_lumpur_ssp585_2020/pluvial/rp_{RP}/pluvial_depth_SSP5-8.5_2020_rp{RP}.tif"
FL=f"outputs/kl_fluvbias_mainstem/fluvial/rp_{RP}/fluvial_depth_SSP5-8.5_2020_rp{RP}.tif"
hs=load_hotspots_from_manifest("kuala_lumpur")
print(f"{'label':34s} {'cls':5s} {'pluv':>6s} {'fluv':>6s} {'comb':>6s}  hit")
for h in sorted(hs,key=lambda x:(x.cls,x.label)):
    p=sample_score(PLUV,h.lon,h.lat,radius_m=R); fl=sample_score(FL,h.lon,h.lat,radius_m=R)
    c=max(p,fl); hit="WET" if c>=THR else "dry"
    flag = " <<MISS" if (h.cls=="flood" and hit=="dry") else (" <<FP" if (h.cls=="dry" and hit=="WET") else "")
    print(f"{h.label[:34]:34s} {h.cls:5s} {p:6.2f} {fl:6.2f} {c:6.2f}  {hit}{flag}")
