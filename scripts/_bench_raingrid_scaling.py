"""Single-solve numba thread-scaling benchmark for run_rain_on_grid.
Run with NUMBA_NUM_THREADS env set; prints threads + wall time for a fixed solve
(same # timesteps across thread counts -> wall-time ratio = parallel efficiency)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import numba
from model.pluvial_rain_model import run_rain_on_grid

THREADS = int(os.environ.get("NUMBA_NUM_THREADS", "6"))
try: numba.set_num_threads(THREADS)
except Exception: pass

# KL-sized grid (~3.9M cells), mild slope + scattered outlets + uniform rain
rng = np.random.default_rng(0)   # seed fixed (no Math.random concerns; this is a bench)
H, W = 1924, 2045
yy = np.linspace(0, 30, H)[:, None]
z = (yy + 0.5*np.sin(np.linspace(0,40,W))[None,:]).astype(np.float64) + rng.random((H,W))*0.3
outlet = np.zeros((H,W), dtype=bool)
outlet[::120, ::120] = True       # scattered sinks
kw = dict(net_rain_depth_m=0.08, n=0.06, storm_duration_s=1800.0,
          dx=30.0, dy=30.0, verbose=False, open_boundary=False)

# warmup (JIT compile) — tiny duration
run_rain_on_grid(z, outlet, total_duration_s=60.0, **kw)
# timed solve — fixed duration => deterministic timestep count, thread-independent
t0=time.perf_counter()
res=run_rain_on_grid(z, outlet, total_duration_s=3600.0, **kw)
dt=time.perf_counter()-t0
print(f"threads={THREADS}  wall={dt:7.2f}s  peak_max={float(np.nanmax(res['peak_depth'])):.3f}m")
