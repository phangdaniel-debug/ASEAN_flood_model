"""Hydrodynamic riverine fluvial inundation via the inertial solver (Bangkok B2).
Holds the river-channel source cells at bed + overbank, routes the spill onto the
floodplain dynamically (connectivity-aware, unlike single-stage HAND)."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, rasterio, click
from model.inertial_wave_model import run_inertial
from model.hand_model import derive_drainage_mask_from_accumulation

@click.command()
@click.option("--dem", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--out", required=True, type=click.Path(path_type=Path))
@click.option("--overbank-m", type=float, required=True, help="Flood stage above bed held at the river source (m).")
@click.option("--acc-threshold", type=int, default=100000, show_default=True,
              help="Accumulation threshold (px) defining the mainstem source channels.")
@click.option("--n", type=float, default=0.06, show_default=True)
@click.option("--t-end", type=float, default=28800.0, show_default=True)
@click.option("--clamp-lo", type=float, default=-3.0, show_default=True,
              help="DEM floor (m). Bangkok's genuine subsidence-corrected delta minimum is "
                   "~-2 to -3 m; cells below are GLO-30 voids/water-body artifacts that "
                   "otherwise create absurd depths (CFL collapse + spurious deep flooding).")
def cli(dem, out, overbank_m, acc_threshold, n, t_end, clamp_lo):
    with rasterio.open(dem) as ds:
        z=ds.read(1).astype(np.float64); prof=ds.profile; nod=ds.nodata
    if nod is not None: z=np.where(z==nod,np.nan,z)
    n_art=int(np.nansum(z<clamp_lo))
    z=np.where(np.isfinite(z) & (z<clamp_lo), clamp_lo, z)   # clamp artifact pits to delta floor
    click.echo(f"DEM artifact clamp: {n_art:,} cells < {clamp_lo} m raised to floor")
    # Mainstem source = high-accumulation channels (the Chao Phraya + major branches).
    src=derive_drainage_mask_from_accumulation(z.astype(np.float32), prof, acc_threshold=acc_threshold)
    src=src & np.isfinite(z)
    click.echo(f"Riverine source: {int(src.sum()):,} channel cells (acc>={acc_threshold}); overbank={overbank_m} m")
    wse=np.where(src, z + overbank_m, 0.0)   # per-cell WSE at source = bed + overbank
    res=run_inertial(z, src, wl_boundary=wse, n=n, dx=abs(prof['transform'].a),
                     dy=abs(prof['transform'].e), t_end=t_end, dt_max=30.0,
                     convergence_tol=1e-3, crop_bbox=True)
    depth=res["peak_depth"].astype(np.float32)
    # Mask the source channel itself (conveyance, not inundation) + nodata
    depth=np.where(src, 0.0, depth); depth=np.where(np.isfinite(z), depth, np.nan)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    op=prof.copy(); op.update(dtype="float32", count=1, nodata=np.nan)
    with rasterio.open(out,"w",**op) as d: d.write(depth,1)
    w=depth[np.isfinite(depth)&(depth>0.1)]
    click.echo(f"Wrote {out}: extent>0.1m={w.size*900/1e6:.0f} km2, mean={w.mean() if w.size else 0:.2f}m, max={np.nanmax(depth):.2f}m, steps={res['n_steps']}, converged={res['converged']}")

if __name__=="__main__": cli()
