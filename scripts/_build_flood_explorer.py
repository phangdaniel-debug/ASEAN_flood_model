"""Build a single self-contained interactive HTML flood explorer.

Renders every (hazard x scenario x return-period) depth field to a small indexed
PNG, plus a Combined (all-hazard) view and a coastline overlay, and embeds them
base64 into one HTML with hazard/scenario/RP selectors and a hotspot toggle.
No external dependencies at view time.

    python scripts/_build_flood_explorer.py
"""
from __future__ import annotations

import base64
import glob
import io
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import transform as rio_transform

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.hotspot_scoring import load_hotspots  # noqa: E402

OUT = ROOT / "docs/paper/figures/flood_explorer.html"
DS = 3
THR = 0.05
LAND = (228, 228, 228)

SCENARIOS = [
    ("singapore_ssp585_2020", "Baseline 2020"),
    ("singapore_ssp245_2050", "SSP2-4.5 / 2050"),
    ("singapore_ssp585_2050", "SSP5-8.5 / 2050"),
    ("singapore_ssp245_2100", "SSP2-4.5 / 2100"),
    ("singapore_ssp585_2100", "SSP5-8.5 / 2100"),
]
HAZARDS = ["pluvial", "coastal", "fluvial"]
RPS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]

# --- single-hazard: 6 discrete depth bands (lower edges), shallow->deep ---
BANDS = [0.05, 0.15, 0.30, 0.50, 1.0, 2.0]
BAND_LABELS = ["0.05–0.15", "0.15–0.30", "0.30–0.50", "0.50–1.0", "1.0–2.0", "≥2.0"]
BAND_COLORS = [(208, 231, 245), (148, 196, 223), (74, 152, 201),
               (31, 108, 176), (8, 69, 148), (106, 27, 154)]
# --- combined: 3 hazard hues x 3 depth bands (light/med/dark) ---
CBANDS = [0.05, 0.30, 1.0]
HAZ_HUE = {
    "pluvial": [(198, 219, 239), (66, 146, 198), (8, 48, 107)],     # blue
    "coastal": [(178, 226, 226), (44, 162, 162), (0, 77, 77)],      # teal
    "fluvial": [(253, 208, 162), (241, 105, 19), (127, 39, 4)],     # orange
}
HAZ_LEGEND = [("pluvial", "#4292c6", "Pluvial"),
              ("coastal", "#2ca2a2", "Coastal"),
              ("fluvial", "#f16913", "Fluvial")]

_SINGLE_PAL = [0, 0, 0] + list(LAND)
for _c in BAND_COLORS:
    _SINGLE_PAL += list(_c)
_COMB_PAL = [0, 0, 0] + list(LAND)
for _h in ("pluvial", "coastal", "fluvial"):
    for _c in HAZ_HUE[_h]:
        _COMB_PAL += list(_c)


def _ds_max(a, f=DS):
    h, w = a.shape
    hp, wp = (-h) % f, (-w) % f
    a = np.pad(a, ((0, hp), (0, wp)), constant_values=np.nan)
    H, W = a.shape
    return np.nanmax(a.reshape(H // f, f, W // f, f), axis=(1, 3))


def _read(scen, haz, rp):
    g = glob.glob(str(ROOT / f"outputs/{scen}/{haz}/rp_{rp}/{haz}_depth_*.tif"))
    if not g:
        return None
    with rasterio.open(g[0]) as ds:
        d = ds.read(1).astype("float32")
        if ds.nodata is not None:
            d = np.where(d == ds.nodata, np.nan, d)
    return _ds_max(d)


def _datauri(idx, palette):
    im = Image.fromarray(idx.astype(np.uint8), mode="P")
    im.putpalette(palette)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True, transparency=0)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _single(d):
    finite = np.isfinite(d)
    idx = np.zeros(d.shape, np.uint8)
    idx[finite] = 1
    wet = finite & (d >= THR)
    band = np.clip(np.digitize(d, BANDS) - 1, 0, len(BANDS) - 1)
    idx[wet] = 2 + band[wet]
    return _datauri(idx, _SINGLE_PAL)


def _combined(p, c, f):
    arrs = [p, c, f]
    finite = np.any([np.isfinite(a) for a in arrs], axis=0)
    stack = np.stack([np.where(np.isfinite(a), a, -1.0) for a in arrs])  # 3,H,W
    dom = np.argmax(stack, axis=0)
    domd = np.max(stack, axis=0)
    idx = np.zeros(p.shape, np.uint8)
    idx[finite] = 1
    wet = finite & (domd >= THR)
    band = np.clip(np.digitize(domd, CBANDS) - 1, 0, len(CBANDS) - 1)
    idx[wet] = (2 + dom * len(CBANDS) + band)[wet]
    return _datauri(idx, _COMB_PAL)


def _coastline(landmask):
    L = landmask
    nb = np.zeros_like(L)
    nb[1:, :] |= ~L[:-1, :]; nb[:-1, :] |= ~L[1:, :]
    nb[:, 1:] |= ~L[:, :-1]; nb[:, :-1] |= ~L[:, 1:]
    edge = L & nb
    de = edge.copy()                      # dilate 1 px for a crisp ~2 px outline
    de[1:, :] |= edge[:-1, :]; de[:-1, :] |= edge[1:, :]
    de[:, 1:] |= edge[:, :-1]; de[:, :-1] |= edge[:, 1:]
    rgba = np.zeros((*L.shape, 4), np.uint8)
    rgba[de] = (40, 40, 40, 255)
    im = Image.fromarray(rgba, "RGBA")
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    ref = glob.glob(str(ROOT / "outputs/singapore_ssp585_2100/pluvial/rp_100/*depth*.tif"))[0]
    with rasterio.open(ref) as ds:
        W, H = ds.width, ds.height
        inv = ~ds.transform
        crs = ds.crs
        land = np.isfinite(_ds_max(np.where(ds.read(1) == ds.nodata, np.nan,
                                            ds.read(1).astype("float32"))))
    coast = _coastline(land)

    hotspots = []
    for h in load_hotspots(ROOT / "data/singapore/flood_obs/hotspots/sg_pluvial_hotspots.csv"):
        xs, ys = rio_transform("EPSG:4326", crs, [h.lon], [h.lat])
        col, row = inv * (xs[0], ys[0])
        hotspots.append({"x": round(100 * col / W, 3), "y": round(100 * row / H, 3),
                         "cls": h.cls, "label": h.label})
    n_flood = sum(1 for h in hotspots if h["cls"] == "flood")

    images = {h: {s[0]: {} for s in SCENARIOS} for h in HAZARDS + ["combined"]}
    n = 0
    for scen, _ in SCENARIOS:
        for rp in RPS:
            fields = {haz: _read(scen, haz, rp) for haz in HAZARDS}
            for haz in HAZARDS:
                if fields[haz] is not None:
                    images[haz][scen][str(rp)] = _single(fields[haz]); n += 1
            if all(fields[h] is not None for h in HAZARDS):
                images["combined"][scen][str(rp)] = _combined(
                    fields["pluvial"], fields["coastal"], fields["fluvial"]); n += 1
        print(f"  {scen}: {n} maps so far")

    html = (_HTML.replace("/*IMAGES*/", json.dumps(images))
                 .replace("/*COAST*/", json.dumps(coast))
                 .replace("/*HOTSPOTS*/", json.dumps(hotspots))
                 .replace("/*SCEN*/", json.dumps(SCENARIOS))
                 .replace("/*RPS*/", json.dumps(RPS))
                 .replace("/*BANDS*/", json.dumps(list(zip(BAND_LABELS,
                          ["#%02x%02x%02x" % c for c in BAND_COLORS]))))
                 .replace("/*HAZLEG*/", json.dumps([[l, col] for _, col, l in HAZ_LEGEND]))
                 .replace("/*NF*/", str(n_flood))
                 .replace("/*ND*/", str(len(hotspots) - n_flood)))
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}  ({OUT.stat().st_size/1e6:.1f} MB, {n} maps, {len(hotspots)} hotspots)")


_HTML = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Singapore flood explorer</title>
<style>
 body{font-family:system-ui,Arial,sans-serif;margin:0;background:#fafafa;color:#222}
 header{padding:10px 14px;background:#1f3a5f;color:#fff}
 header h1{margin:0;font-size:17px} header p{margin:3px 0 0;font-size:12px;opacity:.85}
 .wrap{max-width:980px;margin:0 auto;padding:10px 12px 30px}
 .ctrls{display:flex;flex-wrap:wrap;gap:14px;margin:10px 0}
 .grp{display:flex;flex-direction:column;gap:4px}
 .grp label{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:#555}
 .btns{display:flex;flex-wrap:wrap;gap:5px}
 button.opt{border:1px solid #bbb;background:#fff;border-radius:6px;padding:5px 9px;font-size:13px;cursor:pointer}
 button.opt.on{background:#1f3a5f;color:#fff;border-color:#1f3a5f}
 .toggle{display:flex;align-items:center;gap:6px;font-size:14px}
 .stage{position:relative;width:100%;background:#cfe8f5;border:1px solid #ccc;border-radius:8px;overflow:hidden}
 .stage img{display:block;width:100%;position:relative} .stage img.lyr{position:absolute;inset:0}
 .ov{position:absolute;inset:0;pointer-events:none}
 .hs{position:absolute;width:9px;height:9px;border-radius:50%;transform:translate(-50%,-50%);
     border:1.4px solid #fff;box-shadow:0 0 2px rgba(0,0,0,.6)}
 .hs.flood{background:#e23} .hs.dry{background:#2a8}
 .cap{font-size:13px;margin:8px 2px;font-weight:600}
 .legend{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;font-size:12px;margin-top:8px;color:#444}
 .lz{display:flex;align-items:center;gap:5px}
 .ch{display:inline-block;width:14px;height:12px;border:1px solid #aaa}
 .sw{display:inline-block;width:11px;height:11px;border-radius:50%;border:1.4px solid #fff;
   box-shadow:0 0 2px rgba(0,0,0,.5);vertical-align:middle;margin-right:4px}
</style></head><body>
<header><h1>Singapore multi-hazard flood explorer</h1>
<p>Screening-grade open model — depth by hazard, climate scenario and return period. Coastline overlaid; toggle the documented hotspot register.</p></header>
<div class="wrap">
 <div class="ctrls">
  <div class="grp"><label>Hazard</label><div class="btns" id="haz"></div></div>
  <div class="grp"><label>Scenario</label><div class="btns" id="scen"></div></div>
  <div class="grp"><label>Return period (years)</label><div class="btns" id="rp"></div></div>
  <div class="grp"><label>Overlay</label>
    <div class="toggle"><input type="checkbox" id="tog" checked><label for="tog" style="text-transform:none;font-weight:400">Hotspots (/*NF*/ flood, /*ND*/ dry)</label></div></div>
 </div>
 <div class="cap" id="cap"></div>
 <div class="stage"><img id="map" alt="flood depth">
   <img id="coast" class="lyr" alt="coastline"><div class="ov" id="ov"></div></div>
 <div class="legend" id="legend"></div>
 <p style="font-size:11px;color:#888;margin-top:14px">Pluvial = rain-on-grid; coastal = bathtub (no-defence upper bound); fluvial = HAND canal overflow (channels masked). Combined colours each cell by the deepest hazard. Light grey = land, grey line = coastline. Hotspots are pluvial-register points; most meaningful on the pluvial layer.</p>
</div>
<script>
const IMAGES=/*IMAGES*/, COAST=/*COAST*/, HOTSPOTS=/*HOTSPOTS*/, SCEN=/*SCEN*/, RPS=/*RPS*/;
const BANDS=/*BANDS*/, HAZLEG=/*HAZLEG*/;
const HAZ=[["pluvial","Pluvial"],["coastal","Coastal"],["fluvial","Fluvial"],["combined","Combined"]];
let st={haz:"pluvial",scen:"singapore_ssp585_2100",rp:"100",hs:true};
document.getElementById("coast").src=COAST;
function mk(host,items,key){const h=document.getElementById(host);h.innerHTML="";
 items.forEach(it=>{const[v,l]=it;const b=document.createElement("button");b.className="opt";b.textContent=l;
  b.onclick=()=>{st[key]=v;render();};b.dataset.v=v;h.appendChild(b);});}
mk("haz",HAZ,"haz"); mk("scen",SCEN,"scen"); mk("rp",RPS.map(r=>[String(r),String(r)]),"rp");
document.getElementById("tog").onchange=e=>{st.hs=e.target.checked;render();};
function legend(){
 const L=document.getElementById("legend");
 if(st.haz==="combined"){
   L.innerHTML='<span style="color:#666">deepest hazard (darker = deeper):</span>'+
     HAZLEG.map(([l,c])=>`<span class="lz"><span class="ch" style="background:${c}"></span>${l}</span>`).join("");
 }else{
   L.innerHTML='<span style="color:#666">depth (m):</span>'+
     BANDS.map(([l,c])=>`<span class="lz"><span class="ch" style="background:${c}"></span>${l}</span>`).join("");
 }
 L.innerHTML+='<span class="lz"><span class="sw" style="background:#e23"></span>flood-prone</span>'+
   '<span class="lz"><span class="sw" style="background:#2a8"></span>dry control</span>';
}
function render(){
 document.querySelectorAll("#haz .opt").forEach(b=>b.classList.toggle("on",b.dataset.v===st.haz));
 document.querySelectorAll("#scen .opt").forEach(b=>b.classList.toggle("on",b.dataset.v===st.scen));
 document.querySelectorAll("#rp .opt").forEach(b=>b.classList.toggle("on",b.dataset.v===st.rp));
 const uri=((IMAGES[st.haz]||{})[st.scen]||{})[st.rp];
 const map=document.getElementById("map");
 const sl=SCEN.find(s=>s[0]===st.scen)[1], hl=HAZ.find(h=>h[0]===st.haz)[1];
 document.getElementById("cap").textContent=hl+" — "+sl+" — RP"+st.rp+(uri?"":"  (not available)");
 map.style.visibility=uri?"visible":"hidden"; if(uri)map.src=uri;
 const ov=document.getElementById("ov"); ov.innerHTML="";
 if(st.hs){HOTSPOTS.forEach(p=>{const d=document.createElement("div");
   d.className="hs "+p.cls; d.style.left=p.x+"%"; d.style.top=p.y+"%"; d.title=p.label+" ("+p.cls+")";
   ov.appendChild(d);});}
 legend();
}
render();
</script></body></html>"""


if __name__ == "__main__":
    main()
