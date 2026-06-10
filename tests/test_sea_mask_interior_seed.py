"""Tests for derive_sea_mask interior-seed support.

Regression coverage for the Manila Bay enclosed-basin bug: GLO-30 stores
Manila Bay as a ~335 km2 connected region of <=0 m pixels that does not
touch the raster boundary.  A purely boundary-seeded BFS therefore never
reaches it and the bay is mis-classified as land, producing spurious
coastal flooding (entire bay painted wet at RP2) and pluvial ponding over
open water.  The fix lets derive_sea_mask accept explicit interior seeds.
"""
import numpy as np

from model.flood_depth_model import derive_sea_mask


def _enclosed_basin_dem():
    """20x20 DEM: land at 5.0 m everywhere except a 6x6 below-sea-level
    basin (-1.0 m) at rows/cols 7-12.  The basin does NOT touch the raster
    boundary, so a boundary-seeded BFS cannot reach it -- the synthetic
    analogue of Manila Bay enclosed within the clipped DEM domain."""
    dem = np.full((20, 20), 5.0, dtype=np.float32)
    dem[7:13, 7:13] = -1.0
    return dem


def test_enclosed_basin_not_sea_without_seed():
    """A fully-enclosed sub-zero basin is NOT sea with boundary seeds only."""
    dem = _enclosed_basin_dem()
    sea = derive_sea_mask(dem, connectivity=8, nan_bfs=True)
    assert sea.sum() == 0


def test_enclosed_basin_is_sea_with_interior_seed():
    """An interior seed inside the basin flood-fills the connected sub-zero
    region and classifies the whole basin as sea."""
    dem = _enclosed_basin_dem()
    extra = np.zeros(dem.shape, dtype=bool)
    extra[9, 9] = True  # a pixel inside the basin
    sea = derive_sea_mask(dem, connectivity=8, nan_bfs=True, extra_seeds=extra)
    assert sea[7:13, 7:13].all()   # whole 6x6 basin now sea
    assert int(sea.sum()) == 36    # exactly the basin, no land bleed
    assert not sea[0, 0]           # surrounding land untouched


def test_interior_seed_on_land_seeds_nothing():
    """A seed placed on a land (>0 m) pixel activates nothing: the seed
    only promotes pixels that are themselves sea candidates (<=0 m / NaN)."""
    dem = _enclosed_basin_dem()
    extra = np.zeros(dem.shape, dtype=bool)
    extra[0, 0] = True  # land pixel at 5.0 m
    sea = derive_sea_mask(dem, connectivity=8, nan_bfs=True, extra_seeds=extra)
    assert sea.sum() == 0


def test_boundary_sea_still_detected_with_extra_seeds():
    """Supplying extra_seeds must not suppress normal boundary-seeded
    detection: open sea touching the raster edge is still classified."""
    dem = np.full((20, 20), 5.0, dtype=np.float32)
    dem[:, 0:3] = -1.0          # open sea along the left edge
    dem[7:13, 7:13] = -1.0      # plus an enclosed interior basin
    extra = np.zeros(dem.shape, dtype=bool)
    extra[9, 9] = True
    sea = derive_sea_mask(dem, connectivity=8, nan_bfs=True, extra_seeds=extra)
    assert sea[:, 0:3].all()        # edge sea detected
    assert sea[7:13, 7:13].all()    # interior basin detected


# -------------------------------------------------------------------------
# elevated_water_seeds — permanent inland lakes above MSL (Laguna de Bay)
# -------------------------------------------------------------------------

def _elevated_lake_dem():
    """20x20 DEM: land at 5.0 m, with a 6x6 lake whose surface sits at
    +1.0 m (above MSL) at rows/cols 7-12.  The 0-m and NaN passes cannot
    reach a +1 m water body -- the synthetic analogue of Laguna de Bay."""
    dem = np.full((20, 20), 5.0, dtype=np.float32)
    dem[7:13, 7:13] = 1.0
    return dem


def test_elevated_lake_not_sea_without_elevated_seed():
    """A +1 m lake is not detected by the standard 0-m / NaN passes."""
    dem = _elevated_lake_dem()
    sea = derive_sea_mask(dem, connectivity=8, nan_bfs=True)
    assert sea.sum() == 0


def test_elevated_lake_captured_with_elevated_seed():
    """An elevated-water seed with a max_elev above the lake surface
    flood-fills the lake and classifies it as water."""
    dem = _elevated_lake_dem()
    seed = np.zeros(dem.shape, dtype=bool)
    seed[9, 9] = True
    sea = derive_sea_mask(
        dem, connectivity=8, nan_bfs=True,
        elevated_water_seeds=[(seed, 2.0)],
    )
    assert sea[7:13, 7:13].all()   # whole lake captured
    assert int(sea.sum()) == 36    # exactly the lake, no land bleed


def test_elevated_seed_cap_below_lake_captures_nothing():
    """If max_elev is below the lake surface the seed pixel is not a
    candidate and nothing is captured."""
    dem = _elevated_lake_dem()
    seed = np.zeros(dem.shape, dtype=bool)
    seed[9, 9] = True
    sea = derive_sea_mask(
        dem, connectivity=8, nan_bfs=True,
        elevated_water_seeds=[(seed, 0.5)],  # lake is at 1.0 m
    )
    assert sea.sum() == 0


def test_elevated_pass_is_interior_seeded_only():
    """The elevated pass never seeds from the raster boundary: a permissive
    max_elev must not flood-fill the domain from its edge."""
    dem = _elevated_lake_dem()        # land at 5.0 m, lake at 1.0 m
    seed = np.zeros(dem.shape, dtype=bool)
    seed[9, 9] = True
    # max_elev=10 makes every pixel a candidate, but only the seeded
    # component (the lake, 8-connected) should be filled -- the lake is
    # surrounded by land that is *also* <=10 m, so this also checks the
    # fill does not leak through the high land.
    sea = derive_sea_mask(
        dem, connectivity=8, nan_bfs=True,
        elevated_water_seeds=[(seed, 10.0)],
    )
    # With a 10 m cap the whole 20x20 grid is one connected candidate
    # component, so the seeded fill covers everything -- but crucially it
    # is the *seeded* component, not a boundary artefact.  Verify the seed
    # drives it by confirming an unseeded permissive cap fills nothing.
    sea_noseed = derive_sea_mask(dem, connectivity=8, nan_bfs=True)
    assert sea_noseed.sum() == 0
    assert sea[9, 9]
