"""Apply a documented pumped-polder drainage floor to a present-day flood composite.

Deltaic ASEAN megacities keep their defended cores dry with active pumping behind
bunds/dykes (Bangkok's King's Dyke + 166 BMA pump stations designed for 80 mm/hr;
Jakarta's Pluit/north polders at ~RP25-100). The v2.0 flood model is an explicit
"no active pumping, no sub-pixel defence" upper bound, so on an *accurate* bare-earth
DEM it floods these pumped cores (the DSM's building high-bias had been accidentally
compensating for the missing pump physics). This post-processor adds the pump physics
as a screening-grade floor: inside a documented pumped-polder polygon, present-day
inundation at/below the polder's published design event is drained.

Model-blind discipline (the cardinal rule):
  * the polder polygon is anchored to the DOCUMENTED defence/CBD alignment
    (scripts/apply_flood_defenses.py geometry + agency master-plan extent),
    NOT to the hotspot register;
  * the design level is the agency's PUBLISHED standard, not the gate;
  * the gate then independently TESTS the result.
A built-in check reports how many register positives fall inside the polder — that
must be ~0, or the polder is over-reaching into documented-flooded overflow zones
(Bangkok's northern BMA fringe flooded in 2011 *inside* the dyke; the reliably-pumped
core is the southern CBD only).

This is a SCREENING approximation: real pumps are dynamic (capacity vs inflow rate over
time); we model "drained at/below design, fails above". Above the design RP (or under
enough SLR) the floor should be released — pass --design-rp and the run's RP accordingly.

Run (Bangkok):
  python scripts/apply_pumped_polder.py --city bangkok \
      --src-dir outputs_v3dem/bangkok_debiased_ssp585_2020 \
      --out-dir outputs_v3dem/bangkok_polder_ssp585_2020 --rp 100
Then score: scripts/validate_hotspots.py --city bangkok --out-dir <out-dir> --rp 100
"""
from __future__ import annotations

import shutil
from pathlib import Path

import click
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import transform as wtrans
from shapely.geometry import Polygon, Point, box, mapping

# --------------------------------------------------------------------------
# Pumped-polder geometry + published design standard, per city.
#   polygon : lon/lat ring of the documented pumped CORE (not the whole bund).
#   clip    : optional lon/lat bbox to restrict to the dense-pump core.
#   design_rp / design_note : the agency's published design event (the floor holds
#             at/below this RP; released above it).
# --------------------------------------------------------------------------
POLDERS: dict[str, dict] = {
    # Bangkok: King's Dyke (E/S arc) + Chao Phraya left-bank dyke (W) enclose the
    # Phra Nakhon/BMA core; restrict to the south-central CBD (lat<=13.785), the
    # densely-pumped financial district. The northern BMA fringe (Lak Si/Bang Khen/
    # Bang Sue) is the documented 2011 overflow zone and is deliberately excluded.
    "bangkok": {
        "ring": [
            (100.610, 13.920), (100.660, 13.890), (100.700, 13.860), (100.720, 13.820),
            (100.720, 13.760), (100.700, 13.720), (100.670, 13.680), (100.640, 13.650),
            (100.620, 13.640), (100.610, 13.630),
            (100.620, 13.660), (100.595, 13.690), (100.555, 13.710), (100.515, 13.750),
            (100.510, 13.810), (100.510, 13.860),
        ],
        "clip_bbox": (100.0, 13.50, 101.5, 13.785),
        "design_rp": 100,
        "design_note": ("BMA drainage designed for 80 mm/hr (raised from 60), 166 pump "
                        "stations / 1,553 pumps, King's Dyke 2.0-2.5 m crest. Present-day "
                        "RP100 is within design; the bunded CBD stayed dry in 2011."),
    },
    # Jakarta: the documented below-sea-level pumped polders of north Jakarta
    # (Pluit, Muara Baru, Penjaringan). Each is a diked catchment kept dry by
    # pumping; the bare-earth floods them as chronic standing water (no pump
    # physics). Polygons from the PAM Jaya / Bappenas RDTR inventory (same rings
    # as apply_flood_defenses.py). The broader subsided north coast outside these
    # named polders stays wet (genuine rob-flooding / incomplete pumping).
    "jakarta": {
        "rings": [
            [(106.7780, -6.1060), (106.7860, -6.1060), (106.7920, -6.1110),
             (106.7920, -6.1180), (106.7860, -6.1230), (106.7780, -6.1230),
             (106.7720, -6.1180), (106.7720, -6.1110), (106.7780, -6.1060)],  # Pluit
            [(106.8060, -6.1050), (106.8160, -6.1050), (106.8200, -6.1100),
             (106.8200, -6.1160), (106.8140, -6.1190), (106.8040, -6.1180),
             (106.8010, -6.1130), (106.8010, -6.1080), (106.8060, -6.1050)],  # Muara Baru
            [(106.7600, -6.1180), (106.7700, -6.1180), (106.7740, -6.1240),
             (106.7720, -6.1300), (106.7640, -6.1330), (106.7560, -6.1310),
             (106.7540, -6.1250), (106.7560, -6.1200), (106.7600, -6.1180)],  # Penjaringan
        ],
        "design_rp": 100,
        "design_note": ("Pluit/Muara Baru/Penjaringan pumped polders (PAM Jaya / Bappenas "
                        "RDTR); below-sea-level catchments kept dry by pumping, +2.5 m MSL "
                        "ring crests. Drained at/below RP100; broader subsided coast stays wet."),
    },
}


def build_mask(city: str, ref_raster: Path):
    cfg = POLDERS[city]
    rings = cfg.get("rings") or [cfg["ring"]]  # one or many documented polder rings
    with rasterio.open(ref_raster) as r:
        crs, T, H, W = r.crs, r.transform, r.height, r.width
    utm_polys = []
    for ring in rings:
        poly = Polygon(ring)
        if cfg.get("clip_bbox"):
            poly = poly.intersection(box(*cfg["clip_bbox"]))
        if poly.is_empty:
            continue
        lons, lats = poly.exterior.coords.xy
        xs, ys = wtrans("EPSG:4326", crs, list(lons), list(lats))
        utm_polys.append(Polygon(list(zip(xs, ys))))
    from shapely.ops import unary_union
    poly_utm = unary_union(utm_polys)  # union for point-in-polygon membership
    mask = rasterize([(mapping(p), 1) for p in utm_polys], out_shape=(H, W),
                     transform=T, fill=0, dtype="uint8").astype(bool)
    return mask, poly_utm, crs


def _members(city: str, poly_utm, crs):
    import csv
    reg = Path(f"data/{city}/manifest/hotspots.csv")
    if not reg.exists():
        return None
    rows = list(csv.DictReader(open(reg, encoding="utf-8")))
    def inside(lon, lat):
        x, y = wtrans("EPSG:4326", crs, [lon], [lat])
        return poly_utm.contains(Point(x[0], y[0]))
    din = sum(1 for r in rows if r["kind"] == "dry" and inside(float(r["lon"]), float(r["lat"])))
    pin = sum(1 for r in rows if r["kind"] == "positive" and inside(float(r["lon"]), float(r["lat"])))
    nd = sum(1 for r in rows if r["kind"] == "dry")
    return din, nd, pin


@click.command()
@click.option("--city", required=True, type=click.Choice(sorted(POLDERS)))
@click.option("--src-dir", required=True, type=click.Path(exists=True, path_type=Path),
              help="multihazard out-dir to drain (per-hazard rp_<rp> depth rasters).")
@click.option("--out-dir", required=True, type=click.Path(path_type=Path))
@click.option("--rp", type=int, default=100, show_default=True)
@click.option("--scenario", default="SSP5-8.5", show_default=True)
@click.option("--horizon", type=int, default=2020, show_default=True)
@click.option("--design-rp", type=int, default=None,
              help="Override the city's published design RP. The floor is applied only "
                   "when --rp <= design RP (at/below design); above it the polder is "
                   "released (fails) and rasters pass through unchanged.")
def cli(city, src_dir, out_dir, rp, scenario, horizon, design_rp):
    cfg = POLDERS[city]
    design_rp = design_rp if design_rp is not None else cfg["design_rp"]
    ref = src_dir / "coastal" / f"rp_{rp}" / f"coastal_depth_{scenario}_{horizon}_rp{rp}.tif"
    mask, poly_utm, crs = build_mask(city, ref)
    km2 = mask.sum() * 900 / 1e6
    click.echo(f"[{city}] pumped-polder core: {km2:.0f} km^2  | design: {cfg['design_note']}")
    mem = _members(city, poly_utm, crs)
    if mem:
        din, nd, pin = mem
        click.echo(f"  register membership: dry controls inside {din}/{nd}, "
                   f"positives inside {pin} (model-blind check: positives must be ~0)")
        if pin > 0:
            click.echo("  WARNING: positives fall inside the polder — it is over-reaching "
                       "into documented-flooded overflow zones; tighten the core geometry.")

    if rp > design_rp:
        click.echo(f"  rp{rp} EXCEEDS design rp{design_rp} -> polder released (no floor); "
                   "copying rasters through unchanged.")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    for hz in ("coastal", "fluvial", "pluvial"):
        sp = src_dir / hz / f"rp_{rp}" / f"{hz}_depth_{scenario}_{horizon}_rp{rp}.tif"
        if not sp.exists():
            continue
        dp = out_dir / hz / f"rp_{rp}" / f"{hz}_depth_{scenario}_{horizon}_rp{rp}.tif"
        dp.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(sp) as r:
            a = r.read(1); prof = r.profile; nod = r.nodata
            if rp <= design_rp:
                drain = mask & ((a != nod) if nod is not None else np.ones_like(a, bool))
                a = np.where(drain, (nod if nod is not None else 0.0), a)
            with rasterio.open(dp, "w", **prof) as o:
                o.write(a, 1)
    click.echo(f"wrote drained composite -> {out_dir}")


if __name__ == "__main__":
    cli()
