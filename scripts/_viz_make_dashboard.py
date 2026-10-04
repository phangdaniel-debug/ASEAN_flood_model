"""Build a self-contained HTML dashboard of flood extent (km2) by
city x scenario x RP x hazard layer, from outputs/_viz/extents.json.

2x2 small multiples (one panel per city); each panel groups bars by RP
(10/100/1000) with four layers (coastal, fluvial, pluvial, combined).
A scenario selector across the top switches all panels at once. Vanilla
JS + inline SVG, data embedded -- no external dependencies.

Out: outputs/_viz/flood_extent_dashboard.html
"""
import json
from pathlib import Path

DATA = json.loads(Path("outputs/_viz/extents.json").read_text())

CITY_LABEL = {"bangkok": "Bangkok", "jakarta": "Jakarta",
              "kuala_lumpur": "Kuala Lumpur", "singapore": "Singapore"}
SCEN_LABEL = {"present": "Present-day", "ssp245_2050": "SSP2-4.5 / 2050",
              "ssp245_2100": "SSP2-4.5 / 2100", "ssp585_2050": "SSP5-8.5 / 2050",
              "ssp585_2100": "SSP5-8.5 / 2100"}

HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ASEAN Multi-Hazard Flood Atlas — Extent Explorer</title>
<style>
  :root{ --coastal:#2b8cbe; --fluvial:#2ca25f; --pluvial:#8856a7; --combined:#cf3a2e; --bg:#fbfbfd; --ink:#1d1d1f; --mut:#6b7280; --line:#e7e9ee; }
  *{box-sizing:border-box}
  body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--ink);padding:24px}
  h1{font-size:20px;margin:0 0 2px} .sub{color:var(--mut);font-size:13px;margin:0 0 16px}
  .controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:18px}
  .controls .lbl{font-size:12px;color:var(--mut);margin-right:4px;text-transform:uppercase;letter-spacing:.04em}
  button.sc{border:1px solid var(--line);background:#fff;border-radius:8px;padding:7px 12px;font-size:13px;cursor:pointer;transition:.12s}
  button.sc:hover{border-color:#b9bfca}
  button.sc.active{background:var(--ink);color:#fff;border-color:var(--ink)}
  .legend{display:flex;gap:16px;flex-wrap:wrap;margin:0 0 14px;font-size:12.5px;color:#333}
  .legend span{display:inline-flex;align-items:center;gap:6px}
  .sw{width:12px;height:12px;border-radius:3px;display:inline-block}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  @media(max-width:760px){.grid{grid-template-columns:1fr}}
  .panel{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 14px 6px}
  .panel h3{margin:0 0 1px;font-size:15px} .panel .pmax{color:var(--mut);font-size:11.5px;margin:0 0 4px}
  svg{display:block;width:100%;height:auto;overflow:visible}
  .bar{transition:height .25s ease, y .25s ease}
  .axis{stroke:var(--line);stroke-width:1} .gtxt{fill:var(--mut);font-size:10px}
  .vlab{fill:#444;font-size:9px;text-anchor:middle}
  .tip{position:fixed;pointer-events:none;background:#1d1d1f;color:#fff;font-size:12px;padding:6px 9px;border-radius:6px;opacity:0;transition:.08s;white-space:nowrap;z-index:9}
  .foot{color:var(--mut);font-size:11.5px;margin-top:16px;line-height:1.5}
</style></head><body>
<h1>ASEAN Multi-Hazard Flood Atlas — Extent Explorer</h1>
<p class="sub">Flooded land area (km², depth ≥ 0.10 m) on the calibrated bare-earth terrain, local-inertia coastal solver, model-blind corrected forcing. Combined = per-pixel maximum of the three layers.</p>
<div class="controls"><span class="lbl">Scenario</span><span id="scbar"></span></div>
<div class="legend">
  <span><i class="sw" style="background:var(--coastal)"></i>Coastal</span>
  <span><i class="sw" style="background:var(--fluvial)"></i>Fluvial</span>
  <span><i class="sw" style="background:var(--pluvial)"></i>Pluvial</span>
  <span><i class="sw" style="background:var(--combined)"></i>Combined</span>
  <span style="color:var(--mut)">· grouped by return period (RP10 / RP100 / RP1000) · each panel auto-scaled to its own maximum</span>
</div>
<div class="grid" id="grid"></div>
<div class="tip" id="tip"></div>
<p class="foot">Source: flood-v4.0 clean-run atlas. Per-panel y-axis is independent so within-city hazard composition and return-period scaling stay legible — note the km² scale differs between cities (Bangkok ≫ Kuala Lumpur). KL’s coastal layer is ~0 (inland); its pluvial design-excess largely drains on the steep Klang Valley under the corrected forcing (fluvial-dominant).</p>
<script>
const DATA = __DATA__;
const CITY_LABEL = __CITY_LABEL__;
const SCEN_LABEL = __SCEN_LABEL__;
const SCENS = __SCENS__;
const CITIES = __CITIES__;
const RPS = [10,100,1000];
const LAYERS = [["coastal","#2b8cbe"],["fluvial","#2ca25f"],["pluvial","#8856a7"],["combined","#cf3a2e"]];
let scen = SCENS[0];
const tip = document.getElementById('tip');

function scbar(){
  const b=document.getElementById('scbar');
  b.innerHTML='';
  SCENS.forEach(s=>{
    const btn=document.createElement('button');
    btn.className='sc'+(s===scen?' active':''); btn.textContent=SCEN_LABEL[s];
    btn.onclick=()=>{scen=s; render(); [...b.children].forEach(c=>c.classList.remove('active')); btn.classList.add('active');};
    b.appendChild(btn);
  });
}

function panel(city){
  const W=440,H=230, padL=42,padR=10,padT=10,padB=34;
  const recs=RPS.map(rp=>DATA[city][scen][rp]);
  let max=0; recs.forEach(r=>LAYERS.forEach(([k])=>max=Math.max(max,r[k])));
  max=max<=0?1:max; const nice=niceMax(max);
  const plotW=W-padL-padR, plotH=H-padT-padB;
  const groups=RPS.length, gW=plotW/groups, bw=Math.min(20,(gW-14)/LAYERS.length);
  let svg=`<svg viewBox="0 0 ${W} ${H}" role="img">`;
  // y gridlines
  for(let i=0;i<=4;i++){const v=nice*i/4, y=padT+plotH-(v/nice)*plotH;
    svg+=`<line class="axis" x1="${padL}" y1="${y}" x2="${W-padR}" y2="${y}"/>`;
    svg+=`<text class="gtxt" x="${padL-5}" y="${y+3}" text-anchor="end">${fmt(v)}</text>`;}
  RPS.forEach((rp,gi)=>{
    const r=DATA[city][scen][rp]; const gx=padL+gi*gW;
    const innerW=bw*LAYERS.length+ (LAYERS.length-1)*3;
    const start=gx+(gW-innerW)/2;
    LAYERS.forEach(([k,col],li)=>{
      const v=r[k], h=(v/nice)*plotH, x=start+li*(bw+3), y=padT+plotH-h;
      svg+=`<rect class="bar" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0,h).toFixed(1)}" fill="${col}" rx="1.5" `
         +`data-t="${CITY_LABEL[city]} · RP${rp} · ${k}: ${v.toFixed(1)} km²"></rect>`;
      if(v>0 && h>10) svg+=`<text class="vlab" x="${(x+bw/2).toFixed(1)}" y="${(y-2).toFixed(1)}">${fmt(v)}</text>`;
    });
    svg+=`<text class="gtxt" x="${(gx+gW/2).toFixed(1)}" y="${H-padB+16}" text-anchor="middle">RP${rp}</text>`;
  });
  svg+=`<text class="gtxt" transform="translate(11,${padT+plotH/2}) rotate(-90)" text-anchor="middle">km²</text>`;
  svg+='</svg>';
  return `<div class="panel"><h3>${CITY_LABEL[city]}</h3><div class="pmax">peak ${fmt(nice)} km² · ${SCEN_LABEL[scen]}</div>${svg}</div>`;
}
function niceMax(m){const p=Math.pow(10,Math.floor(Math.log10(m)));const n=m/p;
  const s=n<=1?1:n<=2?2:n<=2.5?2.5:n<=5?5:10;return s*p;}
function fmt(v){return v>=100?Math.round(v).toLocaleString():v>=10?v.toFixed(0):v.toFixed(1);}
function render(){
  document.getElementById('grid').innerHTML=CITIES.map(panel).join('');
  document.querySelectorAll('rect.bar').forEach(r=>{
    r.onmousemove=e=>{tip.style.opacity=1;tip.textContent=r.dataset.t;tip.style.left=(e.clientX+12)+'px';tip.style.top=(e.clientY+12)+'px';};
    r.onmouseleave=()=>tip.style.opacity=0;
  });
}
scbar(); render();
</script></body></html>"""


def main():
    html = (HTML
            .replace("__DATA__", json.dumps(DATA))
            .replace("__CITY_LABEL__", json.dumps(CITY_LABEL))
            .replace("__SCEN_LABEL__", json.dumps(SCEN_LABEL))
            .replace("__SCENS__", json.dumps(list(SCEN_LABEL.keys())))
            .replace("__CITIES__", json.dumps(list(CITY_LABEL.keys()))))
    outp = Path("outputs/_viz/flood_extent_dashboard.html")
    outp.write_text(html, encoding="utf-8")
    print(f"wrote {outp}  ({len(html)//1024} KB)")

    # wrapper-free fragment for inline widget rendering (style + body inner + script)
    style = html[html.index("<style>"): html.index("</style>") + len("</style>")]
    body_inner = html[html.index("</style></head><body>") + len("</style></head><body>"): html.index("</body>")]
    frag = style + body_inner
    fragp = Path("outputs/_viz/flood_extent_widget.html")
    fragp.write_text(frag, encoding="utf-8")
    print(f"wrote {fragp}  ({len(frag)//1024} KB)")


if __name__ == "__main__":
    main()
