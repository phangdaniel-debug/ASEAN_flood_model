# Environment notes & known issues

## ✅ RESOLVED — the "BLAS/rasterio crashes" were an ACTIVATION problem
**Root cause:** running the conda env's `python.exe` **directly, unactivated**, leaves
`env\Library\bin` off the DLL search path → a wrong BLAS DLL loads → delay-load
"procedure not found" crash (Windows `0xC06D007F`, shows as exit 127 / "no output").
It was NOT a pip-vs-conda conflict or an OpenBLAS kernel bug. The same cause produced
the `np.linalg.lstsq`/`matmul` crash AND the `rasterio.rowcol`/`sample` crash.

**Canonical way to run (USE THIS):**
```
mamba run -n sfincs python <script.py> [args]
```
`mamba run` activates the env (sets PATH + GDAL_DATA + PROJ_DATA). Alternatively, in
PowerShell prepend `env\Library\bin;env;env\Scripts` to `$env:PATH` and set GDAL_DATA/
PROJ_DATA, then call python.exe directly (gives live streaming; `mamba run` buffers).

**Working env = `sfincs`** (conda-first, `repro/environment_sfincs.yml`): numpy 2.4.6,
hydromt 1.4.0, hydromt_sfincs 2.0.0rc3, component API verified. The old `hydromt-sfincs`
env also works *if activated* (kept as fallback). The affine-inverse sampler + closed-form
OLS in `dem/*.py` were unnecessary workarounds (harmless; left in place).

---

## (Historical) BLAS/LAPACK crash investigation — superseded by the activation finding above

**Symptom:** any BLAS/LAPACK call in the env crashes the process with a native
access violation (`0xC0000005`, exit `-1066598273`) — including `numpy @` matmul,
`np.linalg.lstsq`, `inv`, `solve`, `svd`. Element-wise numpy, pandas, rasterio
reads, and h5py are unaffected.

**Cause:** the env was built as `conda (python/cartopy/matplotlib/jupyter) + pip
install hydromt-sfincs==2.0.0rc3`, and pip pulled the **entire compiled stack**
(numpy 2.4.6, rasterio 1.4.4, geopandas, …) as PyPI wheels. The pip numpy wheel
bundles its own OpenBLAS while conda also provides one → two OpenBLAS DLLs on the
Windows search path → wrong/incompatible kernel loads → segfault. (The same
mismatch is why `rasterio.transform.rowcol()` / `src.sample()` with array inputs
also crash.)

**Current workarounds in code:**
- `dem/calibrate_dem.py::_sample` — manual affine inverse instead of `rowcol`/`sample`.
- `dem/calibrate_dem.py` f-fit — closed-form OLS instead of `np.linalg.lstsq`.

These keep Phase-1 calibration working, but BLAS will bite elsewhere (scipy, any
solver, possibly hydromt/SFINCS-subgrid internals).

**Proper fix (do after the background data jobs finish — they share this env and
only use element-wise numpy, so don't disturb them mid-run):** rebuild the env
**conda-first** so the compiled stack is conda-forge-consistent:

```
mamba create -n hydromt-sfincs -c conda-forge python=3.11 \
    numpy scipy gdal rasterio geopandas pyproj xarray dask numba pyflwdir \
    h5py netcdf4 pyarrow shapely click requests matplotlib cartopy earthaccess \
    rioxarray xugrid pandas
mamba activate hydromt-sfincs
pip install --no-deps hydromt==1.4.0 hydromt-sfincs==2.0.0rc3
# then re-add any pure-python deps pip reports missing (universal_pathlib,
# pydantic, tomli-w, etc.) with: pip install --no-deps <pkg>
```

Then re-run `repro/verify_env.py` AND a BLAS check (`python -c "import numpy as np;
print((np.random.rand(50,50)@np.random.rand(50,50)).sum())"`) before continuing.

## Working facts
- conda/mamba at `D:\GPTs\Python`; env python `D:\GPTs\Python\envs\hydromt-sfincs\python.exe`.
- Run scripts via the env python directly; `mamba run` buffers output oddly.
- Native crashes print nothing through the Bash tool — re-run via PowerShell and
  check `$LASTEXITCODE` to see the real failure.
