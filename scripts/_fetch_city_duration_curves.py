"""City duration curves (flood-v5.0 duration methodology, Addendum 2).
Fluvial: GloFAS daily -> median days above max(f*Qpk, Q2) around annual-max events
(bankfull floor — the v5 G2 fix). Coastal: UHSLC hourly annual-max event shapes ->
duration(depth below peak). -> data/city_duration_curves.json
SG fluvial intentionally ABSENT (PUB canal overflow -> urban drawdown convention).
Port Klang (140) event shape is reused from flood-v5.0 peninsula curves.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, "D:/GPTs/Projects/flood-v5.0/engine/scripts")
from fetch_uhslc_gauge import fetch_year_uhslc  # noqa: E402

FRACS = [0.0, 0.10, 0.25, 0.50, 0.70, 0.90, 0.95]
DZ = [0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0]
ANCHORS = {"kuala_lumpur": (3.074, 101.578), "bangkok": (14.45, 100.45),
           "jakarta": (-6.35, 106.84)}
GAUGES = {"singapore": 699, "bangkok": 328, "jakarta": 161}


def recession(lat, lon):
    u = (f"https://flood-api.open-meteo.com/v1/flood?latitude={lat:.4f}&longitude={lon:.4f}"
         f"&daily=river_discharge&start_date=1992-01-01&end_date=2024-12-31")
    p = requests.get(u, timeout=90).json()
    s = pd.Series(pd.to_numeric(pd.Series(p["daily"]["river_discharge"]), errors="coerce").values,
                  index=pd.to_datetime(p["daily"]["time"])).dropna()
    am = s.groupby(s.index.year).max()
    q2 = float(am.median())
    per = {f: [] for f in FRACS}
    for yr, gy in s.groupby(s.index.year):
        if len(gy) < 300:
            continue
        pk = gy.idxmax()
        qpk = float(gy.max())
        if qpk <= q2:
            continue
        win = s[pk - pd.Timedelta(days=45): pk + pd.Timedelta(days=45)]
        for f in FRACS:
            per[f].append(int((win > max(f * qpk, q2)).sum()))
    curve = {str(f): {"median_days": float(np.median(per[f])),
                      "q25": float(np.percentile(per[f], 25)),
                      "q75": float(np.percentile(per[f], 75)),
                      "n_events": len(per[f])} for f in FRACS}
    return q2, curve


def gauge_shape(uid):
    ses = requests.Session()
    years = {}
    for yr in range(1995, 2025):
        try:
            s = fetch_year_uhslc(ses, yr, uhslc_id=uid)
            if s is not None and len(s):
                years[yr] = s
        except Exception:
            pass
    if len(years) < 10:
        return None
    allv = pd.concat(years.values()).sort_index()
    shapes = []
    for yr, gy in allv.groupby(allv.index.year):
        if gy.notna().sum() < 4000:
            continue
        pk = gy.idxmax()
        win = allv[pk - pd.Timedelta(hours=36): pk + pd.Timedelta(hours=36)]
        if win.notna().sum() < 48:
            continue
        shapes.append((win - gy.max()).reset_index(drop=True))
    if len(shapes) < 10:
        return None
    return {str(dz): {"median_h": float(np.median([int((sh > -dz).sum()) for sh in shapes])),
                      "n_events": len(shapes)} for dz in DZ}


out = {"fluvial_recession": {}, "coastal_event_shapes": {}}
for city, (lat, lon) in ANCHORS.items():
    q2, c = recession(lat, lon)
    out["fluvial_recession"][city] = {"lat": lat, "lon": lon, "q2": q2, "recession": c}
    print(f"  {city}: Q2={q2:.0f}, days-above-bankfull={c['0.0']['median_days']:.1f} "
          f"n={c['0.0']['n_events']}", flush=True)
for city, uid in GAUGES.items():
    d = gauge_shape(uid)
    if d is None:
        print(f"  {city} gauge {uid}: INSUFFICIENT (C1 fail -> coastal duration omitted)", flush=True)
        continue
    out["coastal_event_shapes"][city] = {"uhslc_id": uid, "duration_below_peak_h": d}
    print(f"  {city} gauge {uid}: n={d['0.2']['n_events']} | h within 0.2m={d['0.2']['median_h']:.0f} "
          f"0.5m={d['0.5']['median_h']:.0f}", flush=True)
# Port Klang reuse for KL
v5 = json.load(open("D:/GPTs/Projects/flood-v5.0/data/peninsula_duration_curves.json"))
pk = next(g for g in v5["coastal_event_shapes"] if g["uhslc_id"] == 140)
out["coastal_event_shapes"]["kuala_lumpur"] = {"uhslc_id": 140,
    "duration_below_peak_h": {k: {"median_h": v["median_h"], "n_events": v["n_events"]}
                              for k, v in pk["duration_below_peak_h"].items()}}
print("  kuala_lumpur gauge 140: reused from v5 peninsula curves", flush=True)
json.dump(out, open("data/city_duration_curves.json", "w"), indent=1)
print("DONE -> data/city_duration_curves.json", flush=True)
