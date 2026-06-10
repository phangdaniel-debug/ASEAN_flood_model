"""Tests for the catchment-routed pluvial model."""
import subprocess
import sys

import numpy as np
import pytest


def test_worldcover_class_to_runoff_coeff():
    """Each ESA WorldCover class maps to its documented runoff coefficient."""
    from scripts.fetch_esa_worldcover import WORLDCOVER_RUNOFF_COEFF, class_to_runoff_coeff

    classes = np.array([[10, 50], [80, 40]], dtype=np.uint8)
    coeff = class_to_runoff_coeff(classes)
    assert coeff[0, 0] == pytest.approx(WORLDCOVER_RUNOFF_COEFF[10])   # tree cover
    assert coeff[0, 1] == pytest.approx(WORLDCOVER_RUNOFF_COEFF[50])   # built-up
    assert coeff[1, 0] == pytest.approx(WORLDCOVER_RUNOFF_COEFF[80])   # water
    assert coeff[1, 1] == pytest.approx(WORLDCOVER_RUNOFF_COEFF[40])   # cropland


def test_worldcover_unknown_class_falls_back():
    """An unmapped class code uses the fallback coefficient, not a crash."""
    from scripts.fetch_esa_worldcover import class_to_runoff_coeff, FALLBACK_RUNOFF_COEFF

    coeff = class_to_runoff_coeff(np.array([[0]], dtype=np.uint8))   # 0 = unmapped
    assert coeff[0, 0] == pytest.approx(FALLBACK_RUNOFF_COEFF)


def test_d8_flow_direction_points_downhill():
    """Each cell's D8 direction points at its steepest-descent neighbour;
    a local minimum has direction -1 (a sink)."""
    from model.pluvial_model import d8_flow_direction

    z = np.array([[3.0, 2.0, 1.0],
                  [3.0, 2.0, 1.0],
                  [3.0, 2.0, 1.0]], dtype=np.float64)
    fdir = d8_flow_direction(z)
    # Direction code 4 == (row 0, col +1) == due east (see _D8_DR/_D8_DC).
    assert fdir[1, 0] == 4
    assert fdir[1, 1] == 4
    assert fdir[1, 2] == -1   # rightmost column: no lower neighbour -> sink


def test_d8_flow_direction_pit_is_sink():
    """A one-cell pit surrounded by higher ground has direction -1."""
    from model.pluvial_model import d8_flow_direction

    z = np.array([[5.0, 5.0, 5.0],
                  [5.0, 1.0, 5.0],
                  [5.0, 5.0, 5.0]], dtype=np.float64)
    fdir = d8_flow_direction(z)
    assert fdir[1, 1] == -1


def test_depression_inventory_finds_deep_depressions_only():
    """Depressions shallower than min_depression_depth_m are filtered out."""
    from model.pluvial_model import build_depression_inventory

    dem = np.full((5, 5), 10.0, dtype=np.float64)
    dem[1, 1] = 6.0    # deep pit (depth 4 m) -> depression
    dem[3, 3] = 9.8    # shallow pit (depth 0.2 m) -> filtered out
    filled = dem.copy()
    filled[1, 1] = 10.0
    filled[3, 3] = 10.0

    inv = build_depression_inventory(dem, filled, cell_area_m2=900.0,
                                     min_depression_depth_m=0.5,
                                     max_depression_depth_m=100.0,
                                     min_depression_area_cells=1)
    assert inv.n == 1
    assert inv.pour_elev[0] == pytest.approx(10.0)
    assert inv.capacity_m3[0] == pytest.approx(4.0 * 900.0)


def test_depression_inventory_labels_cover_depression_cells():
    """inv.labels marks exactly the cells inside kept depressions (1-based)."""
    from model.pluvial_model import build_depression_inventory

    dem = np.full((5, 5), 10.0, dtype=np.float64)
    dem[2, 2] = 5.0
    filled = dem.copy()
    filled[2, 2] = 10.0
    inv = build_depression_inventory(dem, filled, cell_area_m2=900.0,
                                     min_depression_depth_m=0.5,
                                     max_depression_depth_m=100.0,
                                     min_depression_area_cells=1)
    assert inv.labels[2, 2] == 1
    assert inv.labels[0, 0] == 0


def test_catchment_supply_sums_runoff_draining_into_depression():
    """Every cell's runoff is credited to the depression its D8 path ends in."""
    from model.pluvial_model import (build_depression_inventory,
                                     d8_flow_direction, compute_catchment_supply)

    dem = np.array([[5.0, 4.0, 3.0],
                    [5.0, 4.0, 3.0],
                    [5.0, 4.0, 3.0]], dtype=np.float64)
    dem[:, 2] = 0.0                       # right column is a deep pit trough
    filled = dem.copy()
    filled[:, 2] = 3.0
    inv = build_depression_inventory(dem, filled, cell_area_m2=1.0,
                                     min_depression_depth_m=0.5,
                                     max_depression_depth_m=100.0,
                                     min_depression_area_cells=1)
    fdir = d8_flow_direction(dem)
    runoff_volume = np.full(dem.shape, 2.0, dtype=np.float64)
    supply = compute_catchment_supply(dem, fdir, inv, runoff_volume)
    # All 9 cells drain into the single depression -> 9 * 2.0.
    assert supply[0] == pytest.approx(18.0)


def test_depression_inventory_excludes_too_deep_features():
    """Depressions deeper than max_depression_depth_m — quarries, valleys,
    reservoir basins, DEM artifacts — are excluded; they are not urban
    surface-ponding basins."""
    from model.pluvial_model import build_depression_inventory

    dem = np.full((7, 7), 10.0, dtype=np.float64)
    dem[1, 1] = 8.0       # 2 m deep -> a real ponding basin, kept
    dem[5, 5] = -40.0     # 50 m deep -> quarry / artifact, excluded
    filled = dem.copy()
    filled[1, 1] = 10.0
    filled[5, 5] = 10.0
    inv = build_depression_inventory(dem, filled, cell_area_m2=900.0,
                                     min_depression_depth_m=0.5,
                                     max_depression_depth_m=3.0,
                                     min_depression_area_cells=1)
    assert inv.n == 1                  # only the 2 m depression survives
    assert inv.labels[1, 1] == 1
    assert inv.labels[5, 5] == 0       # the 50 m feature is excluded


def test_depression_inventory_excludes_subpixel_dsm_artefacts():
    """Depressions smaller than min_depression_area_cells are dropped as
    sub-pixel DSM artefacts (inter-building voids); larger basins are kept."""
    from model.pluvial_model import build_depression_inventory

    dem = np.full((12, 12), 10.0, dtype=np.float64)
    # Tiny 1-cell pit (artefact) and a broad 4x4 basin (real, 16 cells).
    dem[2, 2] = 8.0                    # 1 cell, 2 m deep
    dem[6:10, 6:10] = 8.5             # 16 cells, 1.5 m deep
    filled = dem.copy()
    filled[2, 2] = 10.0
    filled[6:10, 6:10] = 10.0

    # Default area filter (9 cells): the 1-cell artefact is removed.
    inv = build_depression_inventory(dem, filled, cell_area_m2=900.0,
                                     min_depression_depth_m=0.5,
                                     max_depression_depth_m=3.0)
    assert inv.n == 1
    assert inv.labels[2, 2] == 0       # artefact dropped
    assert inv.labels[6, 6] == 1       # real basin kept

    # Lowering the threshold to 1 re-admits the artefact.
    inv2 = build_depression_inventory(dem, filled, cell_area_m2=900.0,
                                      min_depression_depth_m=0.5,
                                      max_depression_depth_m=3.0,
                                      min_depression_area_cells=1)
    assert inv2.n == 2


def test_build_spill_graph_walks_to_downstream_depression():
    """Walking the conditioned flow field from a depression reaches the
    downstream depression its overflow drains into."""
    from model.pluvial_model import build_spill_graph, DepressionInventory

    rows, cols = 3, 8
    dem = np.full((rows, cols), 10.0)
    labels = np.zeros((rows, cols), dtype=np.int32)
    labels[1, 1] = 1   # depression 0
    labels[1, 5] = 2   # depression 1
    inv = DepressionInventory(
        n=2, labels=labels,
        pour_elev=np.array([10.0, 10.0]),
        capacity_m3=np.array([1.0, 1.0]),
        sorted_beds=[np.array([0.0]), np.array([0.0])],
        cell_area_m2=900.0,
    )
    fdir_filled = np.full((rows, cols), -1, dtype=np.int8)
    fdir_filled[1, 1:7] = 4   # cells (1,1)..(1,6) all flow east
    sea = np.zeros((rows, cols), dtype=bool)
    river = np.zeros((rows, cols), dtype=bool)
    dest = build_spill_graph(dem, inv, fdir_filled, sea, river)
    assert dest[0] == 1     # depression 0 spills into depression 1
    assert dest[1] == -1    # depression 1 walk runs off the domain edge


def test_build_spill_graph_river_is_sink():
    """A depression whose overflow path hits a river cell spills to -1."""
    from model.pluvial_model import build_spill_graph, DepressionInventory

    rows, cols = 3, 6
    dem = np.full((rows, cols), 10.0)
    labels = np.zeros((rows, cols), dtype=np.int32)
    labels[1, 1] = 1
    inv = DepressionInventory(
        n=1, labels=labels, pour_elev=np.array([10.0]),
        capacity_m3=np.array([1.0]), sorted_beds=[np.array([0.0])],
        cell_area_m2=900.0,
    )
    fdir_filled = np.full((rows, cols), -1, dtype=np.int8)
    fdir_filled[1, 1:4] = 4
    sea = np.zeros((rows, cols), dtype=bool)
    river = np.zeros((rows, cols), dtype=bool)
    river[1, 3] = True
    dest = build_spill_graph(dem, inv, fdir_filled, sea, river)
    assert dest[0] == -1


def test_fill_level_partial_fill_below_capacity():
    """A depression supplied with less than its capacity fills part-way; the
    water level solves V(level) = supply via the hypsometric curve."""
    from model.pluvial_model import _fill_level

    beds = np.array([0.0, 1.0, 2.0, 3.0])   # 4 cells, area 1 m2
    pour_elev = 4.0
    # Supply 1.0 m3: only the deepest cell fills; h - 0 = 1 -> h = 1.
    assert _fill_level(beds, pour_elev, 1.0, 1.0) == pytest.approx(1.0)
    # Supply 6.0 m3: cells 0,1,2 below h; 3h - 3 = 6 -> h = 3.
    assert _fill_level(beds, pour_elev, 1.0, 6.0) == pytest.approx(3.0)


def test_cascade_spills_excess_downstream():
    """An over-supplied depression fills to its pour level and routes the
    surplus into its downstream depression."""
    from model.pluvial_model import run_cascade

    # Two single-cell depressions (bed 0, area 1).  dep 0 pours at 5 m
    # (capacity = 5 m3); dep 1 pours at 100 m (capacity = 100 m3).
    # dep 0 spills into dep 1; dep 1 spills off-domain.
    pour_elev = np.array([5.0, 100.0])
    capacity = np.array([5.0, 100.0])
    sorted_beds = [np.array([0.0]), np.array([0.0])]
    spill_dest = np.array([1, -1])
    supply = np.array([30.0, 0.0])   # dep 0 over-supplied by 25 m3
    levels = run_cascade(pour_elev, capacity, sorted_beds, spill_dest,
                         supply, cell_area_m2=1.0)
    assert levels[0] == pytest.approx(5.0)     # dep 0 filled to its pour level
    assert levels[1] == pytest.approx(25.0)    # dep 1 holds the 25 m3 surplus


def _profile(dem, cell_m=30.0):
    """A complete rasterio profile for a synthetic DEM — pysheds needs a real
    GeoTIFF behind its Grid, so width/height/crs/transform must all be set."""
    import rasterio
    from affine import Affine
    return {
        "driver": "GTiff", "width": dem.shape[1], "height": dem.shape[0],
        "count": 1, "dtype": "float32",
        "crs": rasterio.crs.CRS.from_epsg(32647),
        "transform": Affine(cell_m, 0.0, 0.0, 0.0, -cell_m, 0.0),
        "nodata": -9999.0,
    }


def _bowl_dem():
    """13x13 gently west-high sloping plateau (~10 m) with one central
    6 m-deep conical bowl.  The slope guarantees the conditioned DEM is not
    perfectly flat so pysheds flat-resolution always has an outlet."""
    z = np.full((13, 13), 10.0, dtype=np.float64)
    for i in range(13):
        for j in range(13):
            z[i, j] = 10.0 + (12 - j) * 0.05          # gentle west-high slope
            r = ((i - 6) ** 2 + (j - 6) ** 2) ** 0.5
            if r < 4:
                z[i, j] = z[i, j] - (4 - r) * 1.5     # carve the bowl
    return z


def test_fillspill_extent_grows_with_rainfall():
    """Pluvial extent must grow as the return-period rain depth increases —
    the whole point of the redesign."""
    from model.pluvial_model import flood_depth_pluvial_fillspill

    dem = _bowl_dem()
    profile = _profile(dem)
    sea = np.zeros(dem.shape, dtype=bool)
    river = np.zeros(dem.shape, dtype=bool)

    def wet_area(excess_depth_m):
        depth = flood_depth_pluvial_fillspill(
            dem, excess_depth_m, runoff_coeff=0.75,
            sea_mask=sea, river_mask=river, profile=profile,
            max_depression_depth_m=100.0,
        )
        return int(np.sum(np.isfinite(depth) & (depth > 0)))

    small = wet_area(0.002)    # ~RP2 — little runoff
    large = wet_area(0.200)    # ~RP1000 — much runoff
    assert large > small, "extent must grow with rainfall"


def test_fillspill_dry_when_no_rain():
    """Zero excess rain -> zero pluvial flooding."""
    from model.pluvial_model import flood_depth_pluvial_fillspill

    dem = _bowl_dem()
    profile = _profile(dem)
    sea = np.zeros(dem.shape, dtype=bool)
    river = np.zeros(dem.shape, dtype=bool)
    depth = flood_depth_pluvial_fillspill(
        dem, 0.0, runoff_coeff=0.75, sea_mask=sea, river_mask=river,
        profile=profile, max_depression_depth_m=100.0,
    )
    assert np.nansum(depth) == pytest.approx(0.0)


def test_run_multihazard_exposes_pluvial_model_flag():
    """run_multihazard.py advertises the --pluvial-model option."""
    out = subprocess.run(
        [sys.executable, "scripts/run_multihazard.py", "--help"],
        capture_output=True, text=True,
    )
    assert out.returncode == 0
    assert "--pluvial-model" in out.stdout
    assert "--runoff-coeff-raster" in out.stdout


def test_run_city_pipeline_exposes_pluvial_model_flag():
    """run_city_pipeline.py advertises the --pluvial-model option."""
    out = subprocess.run(
        [sys.executable, "scripts/run_city_pipeline.py", "--help"],
        capture_output=True, text=True,
    )
    assert out.returncode == 0
    assert "--pluvial-model" in out.stdout


def test_prebuilt_topography_matches_per_call_result():
    """Routing an RP through a prebuilt PluvialTopography gives the identical
    depth raster as the all-in-one entry point."""
    from model.pluvial_model import (build_pluvial_topography,
                                     flood_depth_pluvial_fillspill,
                                     route_pluvial_rp)

    dem = _bowl_dem()
    profile = _profile(dem)
    sea = np.zeros(dem.shape, dtype=bool)
    river = np.zeros(dem.shape, dtype=bool)

    topo = build_pluvial_topography(dem, sea, river, profile,
                                    max_depression_depth_m=100.0)
    routed = route_pluvial_rp(topo, excess_depth_m=0.05, runoff_coeff=0.75)
    direct = flood_depth_pluvial_fillspill(
        dem, 0.05, runoff_coeff=0.75, sea_mask=sea, river_mask=river,
        profile=profile, max_depression_depth_m=100.0,
    )
    assert np.array_equal(np.nan_to_num(routed), np.nan_to_num(direct))


def test_fillspill_accepts_per_cell_runoff_coeff_array():
    """The entry point accepts a 2-D runoff-coefficient array, and a NaN
    coefficient cell is treated as zero runoff, not propagated as NaN."""
    from model.pluvial_model import flood_depth_pluvial_fillspill

    dem = _bowl_dem()
    profile = _profile(dem)
    sea = np.zeros(dem.shape, dtype=bool)
    river = np.zeros(dem.shape, dtype=bool)
    rc = np.full(dem.shape, 0.75, dtype=np.float64)
    rc[0, 0] = np.nan                       # a bad coefficient cell
    depth = flood_depth_pluvial_fillspill(
        dem, 0.05, runoff_coeff=rc, sea_mask=sea, river_mask=river,
        profile=profile, max_depression_depth_m=100.0,
    )
    assert depth.dtype == np.float32
    assert depth.shape == dem.shape
    assert np.isfinite(depth).any()         # NaN coeff must not poison all cells
    assert float(np.nansum(depth)) > 0.0    # the bowl still ponds


def test_fillspill_no_depressions_returns_dry():
    """A DEM with no closed depression deeper than the noise threshold
    yields an all-dry result even under heavy rain (inv.n == 0 path)."""
    from model.pluvial_model import flood_depth_pluvial_fillspill

    # Monotonic east-sloping plane — no closed depressions at all.
    dem = np.zeros((13, 13), dtype=np.float64)
    for j in range(13):
        dem[:, j] = 10.0 + j * 2.0
    profile = _profile(dem)
    sea = np.zeros(dem.shape, dtype=bool)
    river = np.zeros(dem.shape, dtype=bool)
    depth = flood_depth_pluvial_fillspill(
        dem, 0.2, runoff_coeff=0.75, sea_mask=sea, river_mask=river,
        profile=profile,
    )
    assert float(np.nansum(depth)) == pytest.approx(0.0)
