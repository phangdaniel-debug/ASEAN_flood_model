"""Standalone Leaflet flood-map for the four cities. Reprojects each flood
depth layer (coastal / fluvial / pluvial / combined) to web-mercator,
colorizes by depth class, embeds as base64 (palette-PNG) image overlays,
and writes a self-contained HTML with an OSM base map, admin boundaries
(datamaps topojson via jsdelivr), and city / scenario / hazard / RP controls.

Combined = per-pixel-max marginal from the compound layer.

Out: outputs/_viz/flood_maps.html
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

SCENARIOS = ["present", "ssp245_2050", "ssp245_2100", "ssp585_2050", "ssp585_2100"]
SCEN_LABEL = {"present": "Present-day", "ssp245_2050": "SSP2-4.5 / 2050",
              "ssp245_2100": "SSP2-4.5 / 2100", "ssp585_2050": "SSP5-8.5 / 2050",
              "ssp585_2100": "SSP5-8.5 / 2100"}
RPS = [10, 100, 1000]
HZ = ["coastal", "fluvial", "pluvial", "combined"]
MAXDIM = 660

CITY = {
    "bangkok":      {"label": "Bangkok",      "iso": "tha",
                     "primary": ["Bangkok Metropolis"],
                     "neighbors": ["Nonthaburi", "Samut Prakan", "Samut Sakhon", "Pathum Thani"]},
    "jakarta":      {"label": "Jakarta",      "iso": "idn",
                     "primary": ["Jakarta Raya"], "neighbors": ["Banten", "Jawa Barat"]},
    "kuala_lumpur": {"label": "Kuala Lumpur", "iso": "mys",
                     "primary": ["Kuala Lumpur"], "neighbors": ["Selangor"]},
    "singapore":    {"label": "Singapore",    "iso": "sgp",
                     "primary": ["Central Singapore", "South West", "North West",
                                 "North East", "South East"], "neighbors": []},
}

# depth classes (m) -> RGB (ascending; deeper overwrites). index 0 = transparent.
CLASSES = [(0.10, (158, 202, 224)), (0.5, (107, 174, 214)), (1.0, (49, 130, 189)),
           (2.0, (8, 81, 156)), (3.5, (8, 48, 107))]
PALETTE = [255, 255, 255] + [c for _, rgb in CLASSES for c in rgb]
PALETTE += [0, 0, 0] * (256 - len(PALETTE) // 3)


def resolve(city, scen, rp, hz):
    if hz == "combined":
        p = f"outputs/_compound/{city}_{scen}/marginal_rp{rp}.tif"
        return p if Path(p).exists() else None
    if scen == "present":
        stem = f"{city}_present" if rp == 100 else f"{city}_ssp585_2020_rp{rp}"
    else:
        stem = f"{city}_{scen}" if rp == 100 else f"{city}_{scen}_rp{rp}"
    for suff in (("_polder", "") if city == "bangkok" else ("",)):
        g = glob.glob(f"outputs/{stem}{suff}/{hz}/rp_{rp}/{hz}_depth_*_rp{rp}.tif")
        if g:
            return g[0]
    return None


def to_index(depth):
    idx = np.zeros(depth.shape, dtype=np.uint8)
    for ci, (lo, _) in enumerate(CLASSES, start=1):
        idx[depth >= lo] = ci
    return idx


def render_layer(src):
    """Reproject src to EPSG:3857, downsample, palette-PNG -> (dataURI, [[S,W],[N,E]]) or None."""
    with rasterio.open(src) as r:
        a = r.read(1).astype("float32")
        if r.nodata is not None:
            a[a == r.nodata] = 0.0
        a = np.nan_to_num(a, nan=0.0)
        if (a >= CLASSES[0][0]).sum() == 0:
            return None
        dst_crs = "EPSG:3857"
        _, dw, dh = calculate_default_transform(r.crs, dst_crs, r.width, r.height, *r.bounds)
        sc = min(1.0, MAXDIM / max(dw, dh))
        dw, dh = max(1, int(dw * sc)), max(1, int(dh * sc))
        dt, dw, dh = calculate_default_transform(r.crs, dst_crs, r.width, r.height,
                                                 *r.bounds, dst_width=dw, dst_height=dh)
        out = np.zeros((dh, dw), "float32")
        reproject(a, out, src_transform=r.transform, src_crs=r.crs,
                  dst_transform=dt, dst_crs=dst_crs, resampling=Resampling.max, dst_nodata=0.0)
    w, s, e, n = array_bounds(dh, dw, dt)
    W, S, E, N = transform_bounds(dst_crs, "EPSG:4326", w, s, e, n)
    img = Image.fromarray(to_index(out), "P")
    img.putpalette(PALETTE)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True, transparency=0)
    uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return uri, [[S, W], [N, E]]


def main():
    manifest = {}
    for city, cfg in CITY.items():
        layers, bounds = {}, None
        for scen in SCENARIOS:
            for hz in HZ:
                for rp in RPS:
                    src = resolve(city, scen, rp, hz)
                    if not src:
                        continue
                    res = render_layer(src)
                    if res is None:
                        continue
                    uri, b = res
                    layers[f"{scen}_{hz}_{rp}"] = uri
                    bounds = b
            print(f"  {city:13s} {scen:12s} done ({len(layers)} layers, running)")
        cx = (bounds[0][1] + bounds[1][1]) / 2
        cy = (bounds[0][0] + bounds[1][0]) / 2
        manifest[city] = {"label": cfg["label"], "iso": cfg["iso"], "primary": cfg["primary"],
                          "neighbors": cfg["neighbors"], "bounds": bounds,
                          "center": [cy, cx], "layers": layers}
    html = (TEMPLATE.replace("__MANIFEST__", json.dumps(manifest))
                    .replace("__SCEN_LABEL__", json.dumps(SCEN_LABEL)))
    outp = Path("outputs/_viz/flood_maps.html")
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(html, encoding="utf-8")
    print(f"\nwrote {outp}  ({len(html)//1024} KB)")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ASEAN Flood Atlas — Map Explorer</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"/>
<style>
  *{box-sizing:border-box} body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#1d1d1f;background:#fff}
  header{padding:14px 18px 10px} h1{font-size:18px;margin:0 0 2px} .sub{color:#6b7280;font-size:12.5px;margin:0}
  .bar{display:flex;flex-wrap:wrap;gap:16px;align-items:center;padding:8px 18px 12px;border-bottom:1px solid #eceef2}
  .grp{display:flex;gap:6px;align-items:center;flex-wrap:wrap} .grp .lbl{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.04em;margin-right:2px}
  button{border:1px solid #e2e5ea;background:#fff;border-radius:8px;padding:6px 11px;font-size:13px;cursor:pointer;transition:.12s}
  button:hover{border-color:#b9bfca} button.on{background:#1d1d1f;color:#fff;border-color:#1d1d1f}
  #map{height:72vh;min-height:440px;width:100%}
  .legend{background:rgba(255,255,255,.94);padding:8px 10px;border-radius:8px;border:1px solid #e2e5ea;font-size:12px;line-height:1.5;box-shadow:0 1px 4px rgba(0,0,0,.08)}
  .legend i{display:inline-block;width:13px;height:13px;margin-right:6px;vertical-align:-2px;border-radius:2px}
  .legend .ttl{font-weight:500;margin-bottom:4px} .opwrap{display:flex;align-items:center;gap:8px;font-size:12px;color:#6b7280}
  .foot{padding:10px 18px 18px;color:#6b7280;font-size:11.5px;line-height:1.5}
</style></head><body>
<header><h1>ASEAN Open Flood Atlas — Map Explorer</h1>
<p class="sub">Flood depth (m) on the calibrated bare-earth terrain · local-inertia coastal · model-blind corrected forcing · admin boundaries from datamaps.</p></header>
<div class="bar">
  <div class="grp"><span class="lbl">City</span><span id="citybtns"></span></div>
  <div class="grp"><span class="lbl">Scenario</span><span id="scbtns"></span></div>
  <div class="grp"><span class="lbl">Hazard</span><span id="hzbtns"></span></div>
  <div class="grp"><span class="lbl">Return period</span><span id="rpbtns"></span></div>
  <div class="grp opwrap"><span>Opacity</span><input type="range" id="op" min="0.2" max="1" step="0.05" value="0.85" style="width:80px"></div>
</div>
<div id="map"></div>
<p class="foot">Each flood layer is a 30 m model output reprojected to web-mercator; depth is classed (legend). KL’s coastal and pluvial layers are ~0 km² (inland; pluvial design-excess drains on the steep Klang Valley under the corrected forcing) so only its fluvial layer renders. Combined = per-pixel maximum of the three hazards. Source: flood-v4.0 clean-run atlas.</p>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/topojson/3.0.2/topojson.min.js"></script>
<script>
const M = __MANIFEST__;
const SCEN_LABEL = __SCEN_LABEL__;
const CITIES = Object.keys(M);
const SCENS = Object.keys(SCEN_LABEL);
const HZ = [["combined","Combined"],["coastal","Coastal"],["fluvial","Fluvial"],["pluvial","Pluvial"]];
const RPS = [10,100,1000];
const CLASS = [["≥3.5 m","#08306b"],["2–3.5 m","#08519c"],["1–2 m","#3182bd"],["0.5–1 m","#6baed6"],["0.1–0.5 m","#9ecae1"]];
let city=CITIES[0], scen="ssp585_2100", hz="combined", rp=100, overlay=null, boundary=null, op=0.85;
const topocache={};

const map=L.map('map',{zoomControl:true}).setView(M[city].center,11);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  {maxZoom:19,attribution:'© OpenStreetMap'}).addTo(map);

const legend=L.control({position:'bottomright'});
legend.onAdd=()=>{const d=L.DomUtil.create('div','legend');
  d.innerHTML='<div class="ttl">Flood depth</div>'+CLASS.map(c=>`<div><i style="background:${c[1]}"></i>${c[0]}</div>`).join('');return d;};
legend.addTo(map);

function btns(elId, items, isCur, on){
  const el=document.getElementById(elId); el.innerHTML='';
  items.forEach(([v,label])=>{const b=document.createElement('button');
    b.textContent=label; if(isCur(v))b.className='on';
    b.onclick=()=>{[...el.children].forEach(c=>c.className=''); b.className='on'; on(v);};
    el.appendChild(b);});
}
function setOverlay(){
  if(overlay){map.removeLayer(overlay);overlay=null;}
  const uri=M[city].layers[`${scen}_${hz}_${rp}`];
  if(uri){overlay=L.imageOverlay(uri,M[city].bounds,{opacity:op}).addTo(map);}
}
async function setBoundary(){
  if(boundary){map.removeLayer(boundary);boundary=null;}
  const c=M[city];
  try{
    let topo=topocache[c.iso];
    if(!topo){const r=await fetch(`https://cdn.jsdelivr.net/npm/datamaps@0.5.10/src/js/data/${c.iso}.topo.json`);topo=await r.json();topocache[c.iso]=topo;}
    const key=Object.keys(topo.objects)[0];
    const fc=topojson.feature(topo,topo.objects[key]);
    boundary=L.layerGroup();
    fc.features.forEach(f=>{
      const n=(f.properties&&f.properties.name)||f.id||'';
      if(c.primary.includes(n)) L.geoJSON(f,{style:{color:'#d8431d',weight:2.5,fill:false}}).addTo(boundary);
      else if(c.neighbors.includes(n)) L.geoJSON(f,{style:{color:'#888',weight:1,dashArray:'3,3',fill:false}}).addTo(boundary);
    });
    boundary.addTo(map);
  }catch(e){/* offline: base map still shows context */}
}
function drawCity(){btns('citybtns',CITIES.map(k=>[k,M[k].label]),v=>v===city,goCity);}
function goCity(c){city=c; map.flyToBounds(M[c].bounds,{padding:[20,20]}); setOverlay(); setBoundary(); drawCity();}
drawCity();
btns('scbtns',SCENS.map(s=>[s,SCEN_LABEL[s]]),v=>v===scen,v=>{scen=v;setOverlay();});
btns('hzbtns',HZ,v=>v===hz,v=>{hz=v;setOverlay();});
btns('rpbtns',RPS.map(r=>[r,'RP'+r]),v=>v===rp,v=>{rp=v;setOverlay();});
document.getElementById('op').oninput=e=>{op=+e.target.value; if(overlay)overlay.setOpacity(op);};
map.fitBounds(M[city].bounds); setOverlay(); setBoundary();
</script></body></html>"""


if __name__ == "__main__":
    main()
