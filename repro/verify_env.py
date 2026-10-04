"""Verify the hydromt-sfincs env: key deps + the v2.0 component API."""
import importlib.metadata as m

mods = ["hydromt", "hydromt_sfincs", "rasterio", "geopandas", "xarray",
        "numba", "pyflwdir", "pyproj", "numpy", "xugrid"]
for x in mods:
    try:
        print(f"{x:14s} {m.version(x)}")
    except Exception as e:
        print(f"{x:14s} ERR {e}")

print("---- component API check ----")
from hydromt_sfincs import SfincsModel
sf = SfincsModel(root="_tmp_envcheck", mode="w+")
# New hydromt v1 / hydromt_sfincs v2 expose a component registry dict.
comps = sorted(getattr(sf, "components", {}).keys())
print("SfincsModel components:", comps)
print("RESULT:", "component-API OK" if comps else "NOT component API")
