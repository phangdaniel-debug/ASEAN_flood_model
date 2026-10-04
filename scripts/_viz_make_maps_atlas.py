"""Leaflet visualiser of the FULL fixed atlas (outputs/_fixed_atlas).

City x scenario x return-period x hazard, with a per-pixel-max "combined" layer,
on an OSM base with admin boundaries. Extends scripts/_viz_make_maps_fixed.py
(which covered only present-day RP100) to all 5 scenarios x 3 RPs.

Out: outputs/_viz/flood_maps_atlas.html
"""
import base64
import csv
import glob
import io
import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from PIL import Image
from rasterio.transform import array_bounds
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform_bounds

SCEN = [("ssp585_2020", "Present (2020)"), ("ssp245_2050", "SSP2-4.5 / 2050"),
        ("ssp245_2100", "SSP2-4.5 / 2100"), ("ssp585_2050", "SSP5-8.5 / 2050"),
        ("ssp585_2100", "SSP5-8.5 / 2100")]
RPS = [10, 100, 1000]
HZ = ["combined", "coastal", "fluvial", "pluvial", "duration"]
# duration persistence classes 1..5 (<6h, 6-24h, 1-3d, 3-7d, >7d) — YlOrRd
DUR_COLORS = [(255, 255, 178), (254, 204, 92), (253, 141, 60), (240, 59, 32), (189, 0, 38)]
MAXDIM = 520
CLASSES = [(0.10, (158, 202, 224)), (0.5, (107, 174, 214)), (1.0, (49, 130, 189)),
           (2.0, (8, 81, 156)), (3.5, (8, 48, 107))]
PALETTE = [255, 255, 255] + [c for _, rgb in CLASSES for c in rgb]
PALETTE += [0, 0, 0] * (256 - len(PALETTE) // 3)

CITY = {
    "bangkok":      {"label": "Bangkok", "iso": "tha", "primary": ["Bangkok Metropolis"],
                     "neighbors": ["Nonthaburi", "Samut Prakan", "Samut Sakhon", "Pathum Thani"]},
    "jakarta":      {"label": "Jakarta", "iso": "idn", "primary": ["Jakarta Raya"],
                     "neighbors": ["Banten", "Jawa Barat"]},
    "kuala_lumpur": {"label": "Kuala Lumpur", "iso": "mys", "primary": ["Kuala Lumpur"],
                     "neighbors": ["Selangor"]},
    "singapore":    {"label": "Singapore", "iso": "sgp",
                     "primary": ["Central Singapore", "South West", "North West",
                                 "North East", "South East"], "neighbors": []},
}


def cell_dir(city, stem, rp):
    d = f"outputs/_fixed_atlas/{city}_{stem}_rp{rp}"
    return d + "_polder" if city == "bangkok" and Path(d + "_polder").is_dir() else d


def _display_declutter(a, min_cells=11, wet_thr=0.05):
    """RENDER-ONLY: drop pluvial wet clusters < ~1 ha (11 cells at 30 m).

    Sub-hectare ponds are validated point-scale signal (they carry documented-hotspot
    hits: removing them from the DATA drops the gate HR in all three cities), but at
    atlas display resolution they alias into misleading confetti.  So the data rasters
    and the gate are untouched; only the rendered layer omits sub-resolution clusters.
    """
    wet = a > wet_thr
    lab, n = ndimage.label(wet, structure=np.ones((3, 3)))
    if n == 0:
        return a
    keep = np.bincount(lab.ravel()) >= min_cells
    keep[0] = True
    out = a.copy()
    out[wet & ~keep[lab]] = 0.0
    return out


def _read(city, stem, rp, hz):
    g = glob.glob(f"{cell_dir(city, stem, rp)}/{hz}/rp_{rp}/{hz}_depth_*_rp{rp}.tif")
    if not g:
        return None, None
    try:
        with rasterio.open(g[0]) as r:
            a = r.read(1).astype("float32")
            a = np.where(np.isfinite(a), a, 0.0)
            return a, {"transform": r.transform, "crs": r.crs, "shape": r.shape}
    except Exception as e:                       # e.g. a raster mid-rewrite
        print(f"    [warn] {city} {stem} rp{rp} {hz}: {e}")
        return None, None


def depth_array(city, stem, rp, hz):
    if hz == "duration":
        p = f"{cell_dir(city, stem, rp)}/duration/duration_combined_rp{rp}.tif"
        if not Path(p).exists():
            return None, None
        with rasterio.open(p) as r:
            a = r.read(1).astype("float32")
            return a, {"transform": r.transform, "crs": r.crs, "shape": r.shape}
    if hz != "combined":
        return _read(city, stem, rp, hz)
    mx = None; meta = None
    for h in ("coastal", "fluvial", "pluvial"):
        a, m = _read(city, stem, rp, h)
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


def render(depth, meta, mode="depth"):
    """Coverage-weighted RGBA render: colour = depth class (max-pooled so severity survives
    the downsample); ALPHA = the fraction of the display pixel's footprint actually wet
    (average-pooled 0/1 indicator). mode='duration': the array is a persistence-class
    raster (1..5), coloured with DUR_COLORS. Returns (rgba_image, leaflet_bounds)."""
    wet_thr = 0.5 if mode == "duration" else CLASSES[0][0]
    if depth is None or (depth >= wet_thr).sum() == 0:
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
    frac = np.zeros((dh, dw), "float32")
    reproject((depth >= wet_thr).astype("float32"), frac,
              src_transform=src_t, src_crs=src_crs, dst_transform=dt,
              dst_crs=dst_crs, resampling=Resampling.average, dst_nodata=0.0)
    bw, bs, be, bn = array_bounds(dh, dw, dt)
    W, S, E, N = transform_bounds(dst_crs, "EPSG:4326", bw, bs, be, bn)
    rgba = np.zeros((dh, dw, 4), dtype=np.uint8)
    if mode == "duration":
        idx = np.clip(np.nan_to_num(out, nan=0.0), 0, 5).astype(np.uint8)
        for ci, rgb in enumerate(DUR_COLORS, start=1):
            m = idx == ci
            rgba[m, 0], rgba[m, 1], rgba[m, 2] = rgb
    else:
        idx = to_index(out)
        for ci, (_, rgb) in enumerate(CLASSES, start=1):
            m = idx == ci
            rgba[m, 0], rgba[m, 1], rgba[m, 2] = rgb
    alpha = (55.0 + 200.0 * np.clip(frac, 0.0, 1.0)).astype(np.uint8)
    rgba[..., 3] = np.where(idx > 0, alpha, 0)
    img = Image.fromarray(rgba, "RGBA")
    return img, [[S, W], [N, E]]


def load_register(city):
    """Documented-hotspot register points for the map: positives (documented flooding) +
    dry controls, from the validation register (hotspots_expanded.csv — the set the current
    gate scores; Singapore's is the imported PUB Flood-Prone list)."""
    f = Path(f"data/{city}/manifest/hotspots_expanded.csv")
    if not f.exists():
        return []
    pts = []
    with open(f, encoding="utf-8", errors="replace", newline="") as fh:
        for r in csv.DictReader(fh):
            lon, lat = str(r.get("lon", "")).strip(), str(r.get("lat", "")).strip()
            if not lon or not lat:
                continue
            kind = str(r.get("kind", "")).strip()
            cls = {"positive": "pos", "dry": "dry"}.get(kind)   # dry_diagnostic excluded (matches gate)
            if cls is None:
                continue
            try:
                pts.append({"lat": float(lat), "lon": float(lon), "cls": cls,
                            "name": str(r.get("name") or r.get("label") or "").strip()})
            except ValueError:
                continue
    return pts


def main():
    # EXTERNAL layer files (relative to the HTML), not inline base64: inlining ~300
    # layers would produce a browser-choking single file (the flood-v5.0 40 MB lesson).
    outdir = Path("outputs/_viz/atlas_layers")
    outdir.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for city, cfg in CITY.items():
        layers, bounds = {}, None
        for stem, _ in SCEN:
            for rp in RPS:
                for hz in HZ:
                    depth, meta = depth_array(city, stem, rp, hz)
                    if depth is None:
                        continue
                    res = render(depth, meta, mode="duration" if hz == "duration" else "depth")
                    if res is None:
                        continue
                    img, b = res
                    fname = f"{city}_{stem}_{rp}_{hz}.png"
                    img.save(outdir / fname, optimize=True)
                    layers[f"{stem}_{rp}_{hz}"] = f"atlas_layers/{fname}"
                    bounds = b
            print(f"  {city:13s} {stem:12s} layers so far: {len(layers)}")
        if bounds is None:
            print(f"  {city}: NO LAYERS"); continue
        cx = (bounds[0][1] + bounds[1][1]) / 2; cy = (bounds[0][0] + bounds[1][0]) / 2
        reg = load_register(city)
        manifest[city] = {"label": cfg["label"], "iso": cfg["iso"], "primary": cfg["primary"],
                          "neighbors": cfg["neighbors"], "bounds": bounds, "center": [cy, cx],
                          "layers": layers, "register": reg}
        npos = sum(1 for p in reg if p["cls"] == "pos")
        print(f"  {city:13s} register: {npos} positives + {len(reg)-npos} dry controls")
    html = (TEMPLATE.replace("__MANIFEST__", json.dumps(manifest))
                    .replace("__SCEN__", json.dumps(SCEN)).replace("__RPS__", json.dumps(RPS)))
    outp = Path("outputs/_viz/flood_maps_atlas.html"); outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(html, encoding="utf-8")
    print(f"\nwrote {outp} ({len(html)//1024} KB)")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ASEAN Flood Atlas — full (fixed-atlas)</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"/>
<style>
  *{box-sizing:border-box} body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#1d1d1f;background:#fff}
  header{padding:14px 18px 8px} h1{font-size:18px;margin:0 0 2px} .sub{color:#6b7280;font-size:12.5px;margin:0}
  .tag{display:inline-block;background:#0f6e56;color:#fff;font-size:11px;padding:2px 8px;border-radius:6px;margin-left:6px;vertical-align:1px}
  .bar{display:flex;flex-wrap:wrap;gap:16px;align-items:center;padding:8px 18px 12px;border-bottom:1px solid #eceef2}
  .grp{display:flex;gap:6px;align-items:center;flex-wrap:wrap} .grp .lbl{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.04em;margin-right:2px}
  button{border:1px solid #e2e5ea;background:#fff;border-radius:8px;padding:6px 11px;font-size:13px;cursor:pointer;transition:.12s}
  button:hover{border-color:#b9bfca} button.on{background:#1d1d1f;color:#fff;border-color:#1d1d1f}
  #map{height:74vh;min-height:460px;width:100%}
  .legend{background:rgba(255,255,255,.94);padding:8px 10px;border-radius:8px;border:1px solid #e2e5ea;font-size:12px;line-height:1.5;box-shadow:0 1px 4px rgba(0,0,0,.08)}
  .legend i{display:inline-block;width:13px;height:13px;margin-right:6px;vertical-align:-2px;border-radius:2px}
  .legend .ttl{font-weight:500;margin-bottom:4px}
  .foot{padding:10px 18px 18px;color:#6b7280;font-size:11.5px;line-height:1.5}
</style></head><body>
<header><h1>ASEAN Open Flood Atlas <span class="tag">full fixed-atlas</span></h1>
<p class="sub">30 m coastal + fluvial + pluvial flood depth (m), bare-earth terrain, inertial coastal + main-stem-HAND fluvial + regime-matched pluvial (handfill scenario-scaled). Combined = per-pixel max. Pick city / scenario / return period / hazard.</p></header>
<div class="bar">
  <div class="grp"><span class="lbl">City</span><span id="citybtns"></span></div>
  <div class="grp"><span class="lbl">Scenario</span><span id="scbtns"></span></div>
  <div class="grp"><span class="lbl">RP</span><span id="rpbtns"></span></div>
  <div class="grp"><span class="lbl">Hazard</span><span id="hzbtns"></span></div>
  <div class="grp"><span class="lbl">Register</span><span id="regbtns"></span></div>
  <div class="grp" style="font-size:12px;color:#6b7280"><span>Opacity</span><input type="range" id="op" min="0.2" max="1" step="0.05" value="0.85" style="width:80px"></div>
</div>
<div id="map"></div>
<p class="foot">Full fixed-atlas (outputs/_fixed_atlas), 4 cities x 5 scenarios x 3 RPs. Empty layers (e.g. KL coastal) are omitted.
Display note: opacity is coverage-weighted — solid colour = contiguous inundation at display scale; faint tint/stipple = zones of scattered sub-pixel ponding (real, validated point-scale hazard that cannot be drawn as discrete features at this zoom). Source: flood-v4.0.</p>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/topojson/3.0.2/topojson.min.js"></script>
<script>
const M = __MANIFEST__;
const SCEN = __SCEN__, RPS = __RPS__;
const CITIES = Object.keys(M);
const HZ = [["combined","Combined"],["coastal","Coastal"],["fluvial","Fluvial"],["pluvial","Pluvial"],["duration","Duration"]];
const CLASS = [["≥3.5 m","#08306b"],["2–3.5 m","#08519c"],["1–2 m","#3182bd"],["0.5–1 m","#6baed6"],["0.1–0.5 m","#9ecae1"]];
const DURCLASS = [["&gt; 7 days","#bd0026"],["3–7 days","#f03b20"],["1–3 days","#fd8d3c"],["6–24 h","#fecc5c"],["&lt; 6 h","#ffffb2"]];
// legendDiv declared with map state (TDZ-safe: legend swap runs from setOverlay during init)
let city=CITIES[0], scen=SCEN[0][0], rp=100, hz="combined", overlay=null, boundary=null, op=0.85, legendDiv=null;
let regLayer=null, regOn=true;
const topocache={};
const map=L.map('map',{zoomControl:true}).setView(M[city].center,11);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(map);
// dedicated high-z pane so register markers stay above the flood image overlay (z 400)
map.createPane('reg'); map.getPane('reg').style.zIndex=650;
const regRenderer=L.svg({pane:'reg'});
function legendHTML(){
  const top = (hz==='duration')
    ? '<div class="ttl">Flood persistence</div>'+DURCLASS.map(c=>`<div><i style="background:${c[1]}"></i>${c[0]}</div>`).join('')
    : '<div class="ttl">Flood depth</div>'+CLASS.map(c=>`<div><i style="background:${c[1]}"></i>${c[0]}</div>`).join('');
  return top
    +'<div class="ttl" style="margin-top:6px">Register</div>'
    +'<div><i style="background:#e02424;border-radius:50%"></i>documented flood</div>'
    +'<div><i style="background:#2563eb;border-radius:50%"></i>dry control</div>';
}
const legend=L.control({position:'bottomright'});
legend.onAdd=()=>{legendDiv=L.DomUtil.create('div','legend');
  legendDiv.innerHTML=legendHTML();
  return legendDiv;};
legend.addTo(map);
function setRegister(){
  if(regLayer){map.removeLayer(regLayer);regLayer=null;}
  if(!regOn)return;
  const pts=M[city].register||[];
  regLayer=L.layerGroup();
  pts.forEach(p=>{const isPos=p.cls==='pos';
    L.circleMarker([p.lat,p.lon],{pane:'reg',renderer:regRenderer,radius:5,weight:1.5,color:'#fff',
      fillColor:isPos?'#e02424':'#2563eb',fillOpacity:.95})
     .bindTooltip((isPos?'⚑ ':'○ ')+(p.name||'(unnamed)')+(isPos?' — documented flood':' — dry control'),
                  {direction:'top',opacity:.95})
     .addTo(regLayer);});
  regLayer.addTo(map);
}
function btns(id,items,isCur,on){const el=document.getElementById(id);el.innerHTML='';
  items.forEach(([v,l])=>{const b=document.createElement('button');b.textContent=l;if(isCur(v))b.className='on';
    b.onclick=()=>{[...el.children].forEach(c=>c.className='');b.className='on';on(v);};el.appendChild(b);});}
function key(){return `${scen}_${rp}_${hz}`;}
function setOverlay(){if(overlay){map.removeLayer(overlay);overlay=null;}
  if(legendDiv) legendDiv.innerHTML=legendHTML();
  const uri=M[city].layers[key()]; if(uri){overlay=L.imageOverlay(uri,M[city].bounds,{opacity:op}).addTo(map);}}
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
function goCity(c){city=c;map.flyToBounds(M[c].bounds,{padding:[20,20]});setOverlay();setBoundary();setRegister();drawCity();}
drawCity();
btns('scbtns',SCEN,v=>v===scen,v=>{scen=v;setOverlay();});
btns('rpbtns',RPS.map(r=>[r,'RP'+r]),v=>v===rp,v=>{rp=v;setOverlay();});
btns('hzbtns',HZ,v=>v===hz,v=>{hz=v;setOverlay();});
btns('regbtns',[["on","Show"],["off","Hide"]],v=>((v==='on')===regOn),v=>{regOn=(v==='on');setRegister();});
document.getElementById('op').oninput=e=>{op=+e.target.value;if(overlay)overlay.setOpacity(op);};
map.fitBounds(M[city].bounds);setOverlay();setBoundary();setRegister();
</script></body></html>"""


if __name__ == "__main__":
    main()
