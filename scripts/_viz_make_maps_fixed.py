"""Leaflet flood-map of the FIXED present-day verification run (outputs/_fixed).
Same UI as flood_maps.html (city / hazard / RP / opacity, OSM base, admin
boundaries) but single scenario = present (fixed): KL fillspill pluvial,
SG main-stem fluvial, continuous-coastline seawalls. Combined = per-pixel max
of the three hazards, computed here.

Out: outputs/_viz/flood_maps_fixed.html
"""
import base64
import glob
import io
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import array_bounds
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform_bounds

RPS = [100]  # RP100-only verification slice
HZ = ["coastal", "fluvial", "pluvial", "combined"]
MAXDIM = 660
CLASSES = [(0.10, (158, 202, 224)), (0.5, (107, 174, 214)), (1.0, (49, 130, 189)),
           (2.0, (8, 81, 156)), (3.5, (8, 48, 107))]
PALETTE = [255, 255, 255] + [c for _, rgb in CLASSES for c in rgb]
PALETTE += [0, 0, 0] * (256 - len(PALETTE) // 3)

CITY = {
    "bangkok":      {"label": "Bangkok", "dir": "outputs/_fixed/bangkok_present_polder", "iso": "tha",
                     "primary": ["Bangkok Metropolis"],
                     "neighbors": ["Nonthaburi", "Samut Prakan", "Samut Sakhon", "Pathum Thani"]},
    "jakarta":      {"label": "Jakarta", "dir": "outputs/_fixed/jakarta_present", "iso": "idn",
                     "primary": ["Jakarta Raya"], "neighbors": ["Banten", "Jawa Barat"]},
    "kuala_lumpur": {"label": "Kuala Lumpur", "dir": "outputs/_fixed/kuala_lumpur_present", "iso": "mys",
                     "primary": ["Kuala Lumpur"], "neighbors": ["Selangor"]},
    "singapore":    {"label": "Singapore", "dir": "outputs/_fixed/singapore_present", "iso": "sgp",
                     "primary": ["Central Singapore", "South West", "North West",
                                 "North East", "South East"], "neighbors": []},
}


def hazard_path(d, hz, rp):
    g = glob.glob(f"{d}/{hz}/rp_{rp}/{hz}_depth_*_rp{rp}.tif")
    return g[0] if g else None


def depth_array(d, hz, rp):
    """Return (depth float32, rasterio src) for a layer, or combined = per-pixel max."""
    if hz != "combined":
        p = hazard_path(d, hz, rp)
        if not p:
            return None, None
        with rasterio.open(p) as r:
            a = r.read(1).astype("float32"); a = np.where(np.isfinite(a), a, 0.0)
            return a, {"transform": r.transform, "crs": r.crs, "shape": r.shape}
    mx = None; meta = None
    for h in ["coastal", "fluvial", "pluvial"]:
        a, m = depth_array(d, h, rp)
        if a is None:
            continue
        mx = a if mx is None else np.maximum(mx, a)
        meta = m
    return mx, meta


def to_index(depth):
    idx = np.zeros(depth.shape, dtype=np.uint8)
    for ci, (lo, _) in enumerate(CLASSES, start=1):
        idx[depth >= lo] = ci
    return idx


def render(depth, meta):
    if depth is None or (depth >= CLASSES[0][0]).sum() == 0:
        return None
    src_crs = meta["crs"]; src_t = meta["transform"]; h0, w0 = meta["shape"]
    dst_crs = "EPSG:3857"
    w, s, e, n = array_bounds(h0, w0, src_t)
    _, dw, dh = calculate_default_transform(src_crs, dst_crs, w0, h0, w, s, e, n)
    sc = min(1.0, MAXDIM / max(dw, dh))
    dw, dh = max(1, int(dw * sc)), max(1, int(dh * sc))
    dt, dw, dh = calculate_default_transform(src_crs, dst_crs, w0, h0, w, s, e, n, dst_width=dw, dst_height=dh)
    out = np.zeros((dh, dw), "float32")
    reproject(depth, out, src_transform=src_t, src_crs=src_crs, dst_transform=dt,
              dst_crs=dst_crs, resampling=Resampling.max, dst_nodata=0.0)
    bw, bs, be, bn = array_bounds(dh, dw, dt)
    W, S, E, N = transform_bounds(dst_crs, "EPSG:4326", bw, bs, be, bn)
    img = Image.fromarray(to_index(out), "P"); img.putpalette(PALETTE)
    buf = io.BytesIO(); img.save(buf, format="PNG", optimize=True, transparency=0)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), [[S, W], [N, E]]


def main():
    manifest = {}
    for city, cfg in CITY.items():
        layers, bounds = {}, None
        for hz in HZ:
            for rp in RPS:
                depth, meta = depth_array(cfg["dir"], hz, rp)
                if depth is None:
                    continue
                res = render(depth, meta)
                if res is None:
                    continue
                uri, b = res
                layers[f"{hz}_{rp}"] = uri; bounds = b
                print(f"  {city:13s} {hz:9s} rp{rp:<5d} ok ({len(uri)//1024} KB)")
        if bounds is None:
            print(f"  {city}: NO LAYERS"); continue
        cx = (bounds[0][1] + bounds[1][1]) / 2; cy = (bounds[0][0] + bounds[1][0]) / 2
        manifest[city] = {"label": cfg["label"], "iso": cfg["iso"], "primary": cfg["primary"],
                          "neighbors": cfg["neighbors"], "bounds": bounds, "center": [cy, cx], "layers": layers}
    html = TEMPLATE.replace("__MANIFEST__", json.dumps(manifest))
    outp = Path("outputs/_viz/flood_maps_fixed.html"); outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(html, encoding="utf-8")
    print(f"\nwrote {outp} ({len(html)//1024} KB)")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ASEAN Flood Atlas — FIXED present-day (verification)</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"/>
<style>
  *{box-sizing:border-box} body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#1d1d1f;background:#fff}
  header{padding:14px 18px 8px} h1{font-size:18px;margin:0 0 2px} .sub{color:#6b7280;font-size:12.5px;margin:0}
  .tag{display:inline-block;background:#0f6e56;color:#fff;font-size:11px;padding:2px 8px;border-radius:6px;margin-left:6px;vertical-align:1px}
  .bar{display:flex;flex-wrap:wrap;gap:16px;align-items:center;padding:8px 18px 12px;border-bottom:1px solid #eceef2}
  .grp{display:flex;gap:6px;align-items:center;flex-wrap:wrap} .grp .lbl{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.04em;margin-right:2px}
  button{border:1px solid #e2e5ea;background:#fff;border-radius:8px;padding:6px 11px;font-size:13px;cursor:pointer;transition:.12s}
  button:hover{border-color:#b9bfca} button.on{background:#1d1d1f;color:#fff;border-color:#1d1d1f}
  #map{height:72vh;min-height:440px;width:100%}
  .legend{background:rgba(255,255,255,.94);padding:8px 10px;border-radius:8px;border:1px solid #e2e5ea;font-size:12px;line-height:1.5;box-shadow:0 1px 4px rgba(0,0,0,.08)}
  .legend i{display:inline-block;width:13px;height:13px;margin-right:6px;vertical-align:-2px;border-radius:2px}
  .legend .ttl{font-weight:500;margin-bottom:4px}
  .foot{padding:10px 18px 18px;color:#6b7280;font-size:11.5px;line-height:1.5}
</style></head><body>
<header><h1>ASEAN Open Flood Atlas — present-day <span class="tag">FIXED / verification</span></h1>
<p class="sub">Present-day (SSP5-8.5/2020) <b>RP100</b>, depth (m) on bare-earth. Fixes: KL pluvial fill-spill · Singapore main-stem fluvial (&ge;50&nbsp;km&sup2;) + handfill pluvial (rain pools near drainage) · framefixed sea-masks (W/E edge artifact removed) · citable continuous coastal defences. Combined = per-pixel max.</p>
<p class="sub" style="margin-top:4px">Coastal-defence crest (above MSL): <b>Singapore +3.0&nbsp;m</b> (PUB pre-2011 reclamation std) · <b>Bangkok +2.10&nbsp;m</b> (BMA dike, UNESCAP) · <b>Jakarta +2.0&nbsp;m</b> (existing wall ~1&ndash;2&nbsp;m; coastal is subsidence-dominated). KL is inland (no coastal).</p></header>
<div class="bar">
  <div class="grp"><span class="lbl">City</span><span id="citybtns"></span></div>
  <div class="grp"><span class="lbl">Hazard</span><span id="hzbtns"></span></div>
  <div class="grp"><span class="lbl">Return period</span><span id="rpbtns"></span></div>
  <div class="grp" style="font-size:12px;color:#6b7280"><span>Opacity</span><input type="range" id="op" min="0.2" max="1" step="0.05" value="0.85" style="width:80px"></div>
</div>
<div id="map"></div>
<p class="foot">Verification build (outputs/_fixed), RP100 present-day. Coastal vs the buggy atlas: Bangkok 648&rarr;68, Singapore 109&rarr;~1 (defended), Jakarta 137&rarr;182 (real chronic below-sea-level subsidence, not an artifact). Bangkok W/E edge flood 105/167&rarr;2/10&nbsp;km&sup2; (sea-mask frame artifact removed). KL pluvial 0&rarr;38, Singapore fluvial 181&rarr;28 (main-stem) + pluvial 15&rarr;90 (handfill: gate HR 0.13&rarr;0.71, PASS). Source: flood-v4.0 diagnostic fixes.</p>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/topojson/3.0.2/topojson.min.js"></script>
<script>
const M = __MANIFEST__;
const CITIES = Object.keys(M);
const HZ = [["combined","Combined"],["coastal","Coastal"],["fluvial","Fluvial"],["pluvial","Pluvial"]];
const RPS = [100];
const CLASS = [["≥3.5 m","#08306b"],["2–3.5 m","#08519c"],["1–2 m","#3182bd"],["0.5–1 m","#6baed6"],["0.1–0.5 m","#9ecae1"]];
let city=CITIES[0], hz="combined", rp=100, overlay=null, boundary=null, op=0.85;
const topocache={};
const map=L.map('map',{zoomControl:true}).setView(M[city].center,11);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(map);
const legend=L.control({position:'bottomright'});
legend.onAdd=()=>{const d=L.DomUtil.create('div','legend');d.innerHTML='<div class="ttl">Flood depth</div>'+CLASS.map(c=>`<div><i style="background:${c[1]}"></i>${c[0]}</div>`).join('');return d;};
legend.addTo(map);
function btns(id,items,isCur,on){const el=document.getElementById(id);el.innerHTML='';
  items.forEach(([v,l])=>{const b=document.createElement('button');b.textContent=l;if(isCur(v))b.className='on';
    b.onclick=()=>{[...el.children].forEach(c=>c.className='');b.className='on';on(v);};el.appendChild(b);});}
function setOverlay(){if(overlay){map.removeLayer(overlay);overlay=null;}
  const uri=M[city].layers[`${hz}_${rp}`]; if(uri){overlay=L.imageOverlay(uri,M[city].bounds,{opacity:op}).addTo(map);}}
async function setBoundary(){if(boundary){map.removeLayer(boundary);boundary=null;}
  const c=M[city];
  try{let t=topocache[c.iso];
    if(!t){const r=await fetch(`https://cdn.jsdelivr.net/npm/datamaps@0.5.10/src/js/data/${c.iso}.topo.json`);t=await r.json();topocache[c.iso]=t;}
    const k=Object.keys(t.objects)[0];const fc=topojson.feature(t,t.objects[k]);boundary=L.layerGroup();
    fc.features.forEach(f=>{const n=(f.properties&&f.properties.name)||f.id||'';
      if(c.primary.includes(n))L.geoJSON(f,{style:{color:'#d8431d',weight:2.5,fill:false}}).addTo(boundary);
      else if(c.neighbors.includes(n))L.geoJSON(f,{style:{color:'#888',weight:1,dashArray:'3,3',fill:false}}).addTo(boundary);});
    boundary.addTo(map);}catch(e){}}
function drawCity(){btns('citybtns',CITIES.map(k=>[k,M[k].label]),v=>v===city,goCity);}
function goCity(c){city=c;map.flyToBounds(M[c].bounds,{padding:[20,20]});setOverlay();setBoundary();drawCity();}
drawCity();
btns('hzbtns',HZ,v=>v===hz,v=>{hz=v;setOverlay();});
btns('rpbtns',RPS.map(r=>[r,'RP'+r]),v=>v===rp,v=>{rp=v;setOverlay();});
document.getElementById('op').oninput=e=>{op=+e.target.value;if(overlay)overlay.setOpacity(op);};
map.fitBounds(M[city].bounds);setOverlay();setBoundary();
</script></body></html>"""


if __name__ == "__main__":
    main()
