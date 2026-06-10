# Historical Event Validation (R4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `scripts/validate_historical_events.py` — a self-contained validator that downloads observed flood polygons for two historical events, rasterizes them to the pipeline DEM grid, sweeps all configured (hazard_type, RP) combinations, and reports CSI/H/FAR metrics with WARN/FAIL gates.

**Architecture:** Single new script following the same pattern as `scripts/validate_fluvial_idf_anchors.py`: an `EVENTS` registry list with per-event config, auto-download on first run (cached to `data/<city>/flood_obs/<event_id>/`), then rasterize-compare-report. Jakarta 2020 uses a confirmed Sentinel-Asia flood proxy shapefile; Malaysia 2021 requires one URL-discovery step first.

**Tech Stack:** `fiona` (shapefile read + CRS), `shapely` (geometry + transform), `rasterio` (rasterize, read depth rasters), `pyproj` (CRS reprojection), `numpy`, `click` — all already in the pipeline environment.

---

## File structure

| Path | Action | Responsibility |
|---|---|---|
| `scripts/validate_historical_events.py` | **Create** | All validation logic + CLI |
| `tests/test_validate_historical_events.py` | **Create** | Unit tests for every function |
| `docs/hazard_methodology_comparison.md` | **Modify** | Correct EMSR numbers; update Issue #11 status |

No changes to `run_city_pipeline.py`, `run_multihazard.py`, or `cities.py`.

---

## Task 1: Malaysia 2021 URL discovery and EVENTS registry

**Files:**
- Create: `scripts/validate_historical_events.py` (skeleton with EVENTS dict only)

### Context
The design spec listed EMSR432 (Jakarta 2020) and EMSR530 (KL 2021) as data sources. Both are wrong:
- Copernicus EMS was never activated for Jakarta Jan 2020 (no EMSR in that date range).
- EMSR530 is a Greece wildfire (August 2021, Fokida).

**Jakarta Jan 2020** uses a confirmed Sentinel-Asia / EOS-ARIA flood proxy shapefile:
- URL: `https://sentinel-asia.org/EO/2020/article20200101ID/EOS_ARIA-SG_20200102_FPM_Indonesia_Floods_v1.5_SHP.zip`
- All polygons = detected water (no class filter needed).
- Confirmed reachable: 778 KB ZIP, HTTP 200.

**Malaysia Dec 2021** source is unconfirmed. Follow these steps to find it.

- [ ] **Step 1: Search UNOSAT HDX for Malaysia 2021 flood polygon**

  Visit `https://data.humdata.org/organization/unosat` in a browser (or use WebFetch/WebSearch). Search for "Malaysia flood 2021". Look for a dataset titled "Satellite detected water extent … Malaysia … December 2021" — UNOSAT often publishes these within days of major floods.

  If found: note the direct shapefile ZIP download URL (typically `https://unosat.org/products/<ID>` with a `.zip` link). Note the attribute name for flood class (often `class` with value `"Flooded"`).

  If **not found** on UNOSAT: check the Copernicus GFM flood archive at `https://global-flood.emergency.copernicus.eu/react/` — filter by Malaysia, December 2021, download GeoTIFF or vector.

  Record the URL and attribute schema before proceeding.

- [ ] **Step 2: Write the skeleton script with EventConfig and EVENTS list**

  Create `scripts/validate_historical_events.py` with this exact content (fill in `MY2021_URL` from Step 1; if URL unknown, use `""` as a placeholder and note it):

  ```python
  """
  Validate the multi-hazard flood pipeline against documented historical flood events.

  Downloads observed flood polygons, rasterizes to the pipeline DEM grid, sweeps all
  configured (hazard_type, RP) combinations, and reports CSI / H / FAR metrics with
  WARN / FAIL gates.

  Events configured:
      JKT2020  - Jakarta Jan 2020 (Sentinel-Asia EOS-ARIA flood proxy, Sentinel-1 SAR)
      MYS2021  - Malaysia Dec 2021 (UNOSAT or Copernicus GFM — confirm URL before use)

  Usage
  -----
      python scripts/validate_historical_events.py                     # all events
      python scripts/validate_historical_events.py --event JKT2020     # single event
      python scripts/validate_historical_events.py --event MYS2021 \\
          --out-dir outputs/kuala_lumpur_ssp585_2100

  Exit codes
  ----------
      0 : all events PASS or WARN
      1 : at least one event FAIL
      2 : output directory or cached flood data not found
  """
  from __future__ import annotations

  import sys
  import urllib.request
  import zipfile
  from dataclasses import dataclass
  from pathlib import Path
  from typing import Optional

  import click
  import numpy as np

  PROJECT_ROOT = Path(__file__).resolve().parents[1]

  # ---------------------------------------------------------------------------
  # Event registry
  # ---------------------------------------------------------------------------

  @dataclass(frozen=True)
  class EventConfig:
      event_id: str          # short ID, e.g. "JKT2020"
      description: str       # human-readable, e.g. "Jakarta floods Jan 2020"
      city_slug: str         # e.g. "jakarta"
      source_url: str        # direct ZIP download (no auth required)
      flood_attr: Optional[str]   # shapefile attribute to filter on; None = use all polygons
      flood_value: Optional[str]  # value to match (case-insensitive); None = use all polygons
      hazard_types: tuple[str, ...]
      rp_range: tuple[int, ...]
      default_out_dir: str   # relative to PROJECT_ROOT


  # Jakarta Jan 2020 — Sentinel-Asia / EOS-ARIA Flood Proxy Map v1.5
  # Source: https://sentinel-asia.org/EO/2020/article20200101ID.html
  # All polygons represent Sentinel-1 detected water; no class filter needed.
  _JKT2020_URL = (
      "https://sentinel-asia.org/EO/2020/article20200101ID/"
      "EOS_ARIA-SG_20200102_FPM_Indonesia_Floods_v1.5_SHP.zip"
  )

  # Malaysia Dec 2021 — UNOSAT or Copernicus GFM (confirm URL in Task 1)
  # Replace "" with the actual ZIP URL before running.
  _MYS2021_URL = ""  # TODO: fill in from Task 1 Step 1


  EVENTS: list[EventConfig] = [
      EventConfig(
          event_id="JKT2020",
          description="Jakarta floods Jan 2020",
          city_slug="jakarta",
          source_url=_JKT2020_URL,
          flood_attr=None,   # all polygons = detected water
          flood_value=None,
          hazard_types=("pluvial", "fluvial"),
          rp_range=(10, 25, 50, 100, 200),
          default_out_dir="outputs/jakarta_ssp585_2100",
      ),
      EventConfig(
          event_id="MYS2021",
          description="Malaysia floods Dec 2021",
          city_slug="kuala_lumpur",
          source_url=_MYS2021_URL,
          flood_attr="class",    # UNOSAT standard; update if source differs
          flood_value="Flooded",
          hazard_types=("fluvial", "pluvial"),
          rp_range=(10, 25, 50, 100, 200),
          default_out_dir="outputs/kuala_lumpur_ssp585_2100",
      ),
  ]

  # ---------------------------------------------------------------------------
  # Gate thresholds
  # ---------------------------------------------------------------------------
  CSI_PASS = 0.30
  CSI_WARN = 0.15

  _SEP  = "=" * 72
  _DASH = "-" * 72
  ```

- [ ] **Step 3: Verify the script is importable**

  ```bash
  cd D:\Downloads\Claude-Cursor
  python -c "from scripts.validate_historical_events import EVENTS; print(len(EVENTS), 'events configured')"
  ```

  Expected: `2 events configured`

- [ ] **Step 4: Commit**

  ```bash
  git add scripts/validate_historical_events.py
  git commit -m "feat: add validate_historical_events skeleton with EventConfig registry"
  ```

---

## Task 2: Core metrics function (TDD)

**Files:**
- Modify: `scripts/validate_historical_events.py` — add `compute_metrics()`
- Create: `tests/test_validate_historical_events.py`

- [ ] **Step 1: Create test file and write failing tests**

  Create `tests/__init__.py` (empty) and `tests/test_validate_historical_events.py`:

  ```python
  """Unit tests for validate_historical_events.py"""
  from __future__ import annotations

  import numpy as np
  import pytest

  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

  from scripts.validate_historical_events import compute_metrics


  def test_compute_metrics_perfect():
      obs  = np.array([[True,  True,  False, False]])
      pred = np.array([[True,  True,  False, False]])
      m = compute_metrics(pred, obs)
      assert m["csi"]  == pytest.approx(1.0)
      assert m["h"]    == pytest.approx(1.0)
      assert m["far"]  == pytest.approx(0.0)
      assert m["bias"] == pytest.approx(1.0)
      assert m["tp"] == 2
      assert m["fp"] == 0
      assert m["fn"] == 0


  def test_compute_metrics_no_overlap():
      obs  = np.array([[True,  True,  False, False]])
      pred = np.array([[False, False, True,  True]])
      m = compute_metrics(pred, obs)
      assert m["csi"] == pytest.approx(0.0)
      assert m["h"]   == pytest.approx(0.0)
      assert m["tp"]  == 0
      assert m["fp"]  == 2
      assert m["fn"]  == 2


  def test_compute_metrics_partial_overlap():
      # obs flooded: cols 0-3; pred flooded: cols 0-1 only
      # TP=2, FP=0, FN=2
      obs  = np.array([[True, True, True, True]])
      pred = np.array([[True, True, False, False]])
      m = compute_metrics(pred, obs)
      assert m["tp"]   == 2
      assert m["fp"]   == 0
      assert m["fn"]   == 2
      assert m["csi"]  == pytest.approx(2 / 4)   # 0.50
      assert m["h"]    == pytest.approx(2 / 4)   # 0.50
      assert m["far"]  == pytest.approx(0.0)
      assert m["bias"] == pytest.approx(2 / 4)   # 0.50 (under-predict)


  def test_compute_metrics_all_false_predicted():
      obs  = np.array([[True, True]])
      pred = np.array([[False, False]])
      m = compute_metrics(pred, obs)
      assert m["csi"] == pytest.approx(0.0)
      assert m["h"]   == pytest.approx(0.0)
      # FAR = FP/(TP+FP) = 0/0 → 0.0 by convention
      assert m["far"] == pytest.approx(0.0)


  def test_compute_metrics_all_false_observed():
      obs  = np.array([[False, False]])
      pred = np.array([[True, True]])
      m = compute_metrics(pred, obs)
      # TP=0, FP=2, FN=0
      assert m["csi"]  == pytest.approx(0.0)
      assert m["far"]  == pytest.approx(1.0)
      assert m["bias"] == pytest.approx(0.0)  # (TP+FP)/(TP+FN) = 2/0 → 0 by convention


  def test_compute_metrics_2d_array():
      obs  = np.array([[True, False], [False, True]])
      pred = np.array([[True, True],  [False, False]])
      # TP=1, FP=1, FN=1
      m = compute_metrics(pred, obs)
      assert m["tp"]  == 1
      assert m["fp"]  == 1
      assert m["fn"]  == 1
      assert m["csi"] == pytest.approx(1 / 3)
  ```

- [ ] **Step 2: Run to verify tests fail**

  ```bash
  cd D:\Downloads\Claude-Cursor
  python -m pytest tests/test_validate_historical_events.py::test_compute_metrics_perfect -v
  ```

  Expected: `ImportError` or `AttributeError: module has no attribute 'compute_metrics'`

- [ ] **Step 3: Implement `compute_metrics` in the script**

  Add after the gate thresholds block in `scripts/validate_historical_events.py`:

  ```python
  # ---------------------------------------------------------------------------
  # Metrics
  # ---------------------------------------------------------------------------

  def compute_metrics(
      predicted: np.ndarray,
      observed: np.ndarray,
  ) -> dict[str, float | int]:
      """Compute flood validation contingency metrics.

      Parameters
      ----------
      predicted : bool ndarray — model-predicted flooded pixels (depth >= threshold)
      observed  : bool ndarray — observed flooded pixels (rasterized polygon)

      Returns
      -------
      dict with keys: tp, fp, fn, csi, h, far, bias
      """
      pred = predicted.astype(bool)
      obs  = observed.astype(bool)

      tp = int(np.sum( pred &  obs))
      fp = int(np.sum( pred & ~obs))
      fn = int(np.sum(~pred &  obs))

      csi  = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0
      h    = tp / (tp + fn)      if (tp + fn)      > 0 else 0.0
      far  = fp / (tp + fp)      if (tp + fp)      > 0 else 0.0
      bias = (tp + fp) / (tp + fn) if (tp + fn)    > 0 else 0.0

      return {"tp": tp, "fp": fp, "fn": fn,
              "csi": csi, "h": h, "far": far, "bias": bias}
  ```

- [ ] **Step 4: Run all metrics tests**

  ```bash
  python -m pytest tests/test_validate_historical_events.py -k "metrics" -v
  ```

  Expected: 6 tests PASS

- [ ] **Step 5: Commit**

  ```bash
  git add scripts/validate_historical_events.py tests/__init__.py tests/test_validate_historical_events.py
  git commit -m "feat: add compute_metrics with full unit test coverage"
  ```

---

## Task 3: Rasterization and depth mask functions (TDD)

**Files:**
- Modify: `scripts/validate_historical_events.py` — add `rasterize_footprint()`, `load_depth_mask()`, `find_depth_raster()`
- Modify: `tests/test_validate_historical_events.py` — add raster tests

- [ ] **Step 1: Add failing tests**

  Append to `tests/test_validate_historical_events.py`:

  ```python
  import rasterio
  from rasterio.transform import from_origin
  from shapely.geometry import box

  from scripts.validate_historical_events import (
      rasterize_footprint,
      load_depth_mask,
      find_depth_raster,
  )


  # ── rasterize_footprint ────────────────────────────────────────────────────

  def test_rasterize_footprint_full_coverage():
      """A polygon covering the entire grid → all pixels True."""
      transform = from_origin(0, 300, 30, 30)   # 10×10 grid, 30 m pixels
      geom = box(0, 0, 300, 300)
      mask = rasterize_footprint([geom], height=10, width=10, transform=transform)
      assert mask.shape == (10, 10)
      assert mask.all()


  def test_rasterize_footprint_half_coverage():
      """A polygon covering the bottom half → ~50 pixels True."""
      transform = from_origin(0, 300, 30, 30)
      geom = box(0, 0, 300, 150)   # y 0–150 = rows 5–9 (bottom half)
      mask = rasterize_footprint([geom], height=10, width=10, transform=transform)
      # rasterio burns centre-of-pixel; bottom 5 rows should be covered
      assert mask.sum() == 50


  def test_rasterize_footprint_empty():
      """Empty geometry list → all False."""
      transform = from_origin(0, 300, 30, 30)
      mask = rasterize_footprint([], height=10, width=10, transform=transform)
      assert mask.shape == (10, 10)
      assert not mask.any()


  # ── load_depth_mask ────────────────────────────────────────────────────────

  def _write_depth_tif(path, data):
      h, w = data.shape
      with rasterio.open(
          str(path), "w", driver="GTiff",
          height=h, width=w, count=1, dtype="float32",
          transform=from_origin(0, h * 30, 30, 30), crs="EPSG:32748",
      ) as dst:
          dst.write(data.astype("float32"), 1)


  def test_load_depth_mask_threshold(tmp_path):
      data = np.array([[0.05, 0.10, 0.15, 0.0]])
      path = tmp_path / "depth.tif"
      _write_depth_tif(path, data)
      mask = load_depth_mask(path, threshold=0.10)
      # 0.05 < 0.10 → False; 0.10 >= 0.10 → True; 0.15 → True; 0.0 → False
      expected = np.array([[False, True, True, False]])
      np.testing.assert_array_equal(mask, expected)


  def test_load_depth_mask_nodata(tmp_path):
      """NoData pixels should be treated as dry (False)."""
      data = np.array([[0.5, -9999.0]])
      path = tmp_path / "depth_nd.tif"
      h, w = data.shape
      with rasterio.open(
          str(path), "w", driver="GTiff",
          height=h, width=w, count=1, dtype="float32",
          transform=from_origin(0, 30, 30, 30), crs="EPSG:32748",
          nodata=-9999.0,
      ) as dst:
          dst.write(data.astype("float32"), 1)
      mask = load_depth_mask(path, threshold=0.10)
      expected = np.array([[True, False]])
      np.testing.assert_array_equal(mask, expected)


  # ── find_depth_raster ──────────────────────────────────────────────────────

  def test_find_depth_raster_found(tmp_path):
      rp_dir = tmp_path / "pluvial" / "rp_50"
      rp_dir.mkdir(parents=True)
      tif = rp_dir / "pluvial_depth_SSP5-8.5_2100_rp50.tif"
      _write_depth_tif(tif, np.full((3, 3), 0.2))
      from scripts.validate_historical_events import find_depth_raster
      assert find_depth_raster(tmp_path, "pluvial", 50) == tif


  def test_find_depth_raster_missing(tmp_path):
      from scripts.validate_historical_events import find_depth_raster
      assert find_depth_raster(tmp_path, "pluvial", 50) is None
  ```

- [ ] **Step 2: Run to verify tests fail**

  ```bash
  python -m pytest tests/test_validate_historical_events.py -k "rasterize or depth" -v
  ```

  Expected: `ImportError` for the three new names.

- [ ] **Step 3: Implement the three functions**

  Add after `compute_metrics` in `scripts/validate_historical_events.py`:

  ```python
  # ---------------------------------------------------------------------------
  # Rasterization
  # ---------------------------------------------------------------------------

  def rasterize_footprint(
      geometries: list,
      height: int,
      width: int,
      transform,
  ) -> np.ndarray:
      """Burn flood polygons into a boolean raster on the DEM grid.

      Parameters
      ----------
      geometries : list of shapely geometries (already in the target CRS)
      height, width : grid dimensions (pixels)
      transform : rasterio Affine transform for the grid

      Returns
      -------
      bool ndarray of shape (height, width); True = inside a flood polygon
      """
      from rasterio.features import rasterize as _rasterize
      from shapely.geometry import mapping

      if not geometries:
          return np.zeros((height, width), dtype=bool)

      shapes = [(mapping(g), 1) for g in geometries]
      arr = _rasterize(
          shapes,
          out_shape=(height, width),
          transform=transform,
          fill=0,
          dtype="uint8",
          all_touched=False,
      )
      return arr.astype(bool)


  # ---------------------------------------------------------------------------
  # Depth raster utilities
  # ---------------------------------------------------------------------------

  def find_depth_raster(out_dir: Path, hazard_type: str, rp: int) -> "Path | None":
      """Locate the depth TIF for a given hazard type and return period.

      Looks for: <out_dir>/<hazard_type>/rp_<rp>/<hazard_type>_depth_*.tif
      Returns None if not found.
      """
      rp_dir = out_dir / hazard_type / f"rp_{rp}"
      if not rp_dir.exists():
          return None
      matches = list(rp_dir.glob(f"{hazard_type}_depth_*.tif"))
      return matches[0] if matches else None


  def load_depth_mask(tif_path: Path, threshold: float) -> np.ndarray:
      """Read a depth raster and return a boolean flooded mask.

      Pixels with depth >= threshold are True (flooded).
      NoData / masked pixels are treated as dry (False).
      """
      import rasterio

      with rasterio.open(tif_path) as ds:
          arr = ds.read(1, masked=True)

      # Fill masked/nodata pixels with 0 (dry)
      filled = arr.filled(0.0) if hasattr(arr, "filled") else np.where(np.isfinite(arr), arr, 0.0)
      return filled >= threshold
  ```

- [ ] **Step 4: Run raster tests**

  ```bash
  python -m pytest tests/test_validate_historical_events.py -k "rasterize or depth" -v
  ```

  Expected: 7 tests PASS

- [ ] **Step 5: Commit**

  ```bash
  git add scripts/validate_historical_events.py tests/test_validate_historical_events.py
  git commit -m "feat: add rasterize_footprint, load_depth_mask, find_depth_raster"
  ```

---

## Task 4: Flood polygon download, extraction, and loading (TDD)

**Files:**
- Modify: `scripts/validate_historical_events.py` — add `download_zip()`, `extract_zip()`, `find_shapefile()`, `load_flood_footprint()`
- Modify: `tests/test_validate_historical_events.py` — add polygon loading tests

- [ ] **Step 1: Add failing tests**

  Append to `tests/test_validate_historical_events.py`:

  ```python
  import fiona
  import zipfile
  from fiona.crs import from_epsg

  from scripts.validate_historical_events import (
      extract_zip,
      find_shapefile,
      load_flood_footprint,
  )


  def _make_shapefile(directory: Path, polygons: list[dict]) -> Path:
      """Write a minimal shapefile with class attribute into directory."""
      directory.mkdir(parents=True, exist_ok=True)
      shp_path = directory / "flood.shp"
      schema = {"geometry": "Polygon", "properties": {"class": "str"}}
      with fiona.open(
          str(shp_path), "w",
          driver="ESRI Shapefile",
          crs=from_epsg(4326),
          schema=schema,
      ) as dst:
          for poly in polygons:
              dst.write(poly)
      return shp_path


  def _make_zip(shp_path: Path, zip_path: Path) -> Path:
      """Zip the shapefile (and sidecar files) into zip_path."""
      with zipfile.ZipFile(str(zip_path), "w") as zf:
          for f in shp_path.parent.glob(shp_path.stem + ".*"):
              zf.write(str(f), f.name)
      return zip_path


  # ── extract_zip ─────────────────────────────────────────────────────────────

  def test_extract_zip_creates_directory(tmp_path):
      shp_path = _make_shapefile(tmp_path / "src", [
          {"geometry": {"type": "Polygon", "coordinates": [[(0,0),(1,0),(1,1),(0,1),(0,0)]]},
           "properties": {"class": "Flooded"}}
      ])
      zip_path = tmp_path / "test.zip"
      _make_zip(shp_path, zip_path)

      extract_dir = extract_zip(zip_path)
      assert extract_dir.exists()
      assert extract_dir.is_dir()
      assert any(extract_dir.glob("*.shp"))


  def test_extract_zip_idempotent(tmp_path):
      """Calling extract_zip twice does not raise."""
      shp_path = _make_shapefile(tmp_path / "src2", [
          {"geometry": {"type": "Polygon", "coordinates": [[(0,0),(1,0),(1,1),(0,1),(0,0)]]},
           "properties": {"class": "Flooded"}}
      ])
      zip_path = tmp_path / "test2.zip"
      _make_zip(shp_path, zip_path)
      extract_zip(zip_path)
      extract_zip(zip_path)  # second call — should not error


  # ── find_shapefile ───────────────────────────────────────────────────────────

  def test_find_shapefile_finds_shp(tmp_path):
      shp = tmp_path / "flood.shp"
      shp.touch()
      result = find_shapefile(tmp_path)
      assert result == shp


  def test_find_shapefile_raises_if_missing(tmp_path):
      import pytest
      with pytest.raises(FileNotFoundError):
          find_shapefile(tmp_path)


  # ── load_flood_footprint ─────────────────────────────────────────────────────

  def test_load_flood_footprint_filters_by_class(tmp_path):
      from shapely.geometry import mapping, box
      shp_path = _make_shapefile(tmp_path / "filt", [
          {"geometry": mapping(box(0, 0, 1, 1)), "properties": {"class": "Flooded"}},
          {"geometry": mapping(box(1, 0, 2, 1)), "properties": {"class": "Possibly flooded"}},
      ])
      geoms = load_flood_footprint(shp_path, "EPSG:4326",
                                   flood_attr="class", flood_value="Flooded")
      assert len(geoms) == 1


  def test_load_flood_footprint_no_filter(tmp_path):
      from shapely.geometry import mapping, box
      schema = {"geometry": "Polygon", "properties": {"id": "int"}}
      shp_path = tmp_path / "nofilt" / "water.shp"
      (tmp_path / "nofilt").mkdir()
      with fiona.open(str(shp_path), "w", driver="ESRI Shapefile",
                      crs=from_epsg(4326), schema=schema) as dst:
          for i in range(3):
              dst.write({"geometry": mapping(box(i, 0, i+1, 1)),
                         "properties": {"id": i}})
      geoms = load_flood_footprint(shp_path, "EPSG:4326",
                                   flood_attr=None, flood_value=None)
      assert len(geoms) == 3


  def test_load_flood_footprint_reprojects(tmp_path):
      """Verify reprojection: a box in WGS84 arrives in a metric CRS."""
      from shapely.geometry import mapping, box
      shp_path = _make_shapefile(tmp_path / "reproj", [
          {"geometry": mapping(box(100.0, 0.0, 100.01, 0.01)),
           "properties": {"class": "Flooded"}},
      ])
      geoms = load_flood_footprint(shp_path, "EPSG:32648",   # UTM 48N
                                   flood_attr="class", flood_value="Flooded")
      assert len(geoms) == 1
      # Reprojected centroid x should be ~hundreds of thousands (easting UTM)
      assert geoms[0].centroid.x > 100_000
  ```

- [ ] **Step 2: Run to verify tests fail**

  ```bash
  python -m pytest tests/test_validate_historical_events.py -k "zip or shapefile or footprint" -v
  ```

  Expected: `ImportError` for the new names.

- [ ] **Step 3: Implement the four functions**

  Add after `load_depth_mask` in `scripts/validate_historical_events.py`:

  ```python
  # ---------------------------------------------------------------------------
  # Flood polygon download, extraction, loading
  # ---------------------------------------------------------------------------

  def download_zip(url: str, cache_dir: Path, no_download: bool = False) -> Path:
      """Download a ZIP to cache_dir, or return cached path if already present.

      Parameters
      ----------
      url         : direct HTTPS download URL
      cache_dir   : directory to store the ZIP (created if needed)
      no_download : if True, skip network fetch and fail if cache missing

      Returns
      -------
      Path to the downloaded (or cached) ZIP file.
      """
      cache_dir.mkdir(parents=True, exist_ok=True)
      filename = url.rstrip("/").split("/")[-1]
      zip_path = cache_dir / filename

      if zip_path.exists():
          click.echo(f"  Using cached {zip_path.name}")
          return zip_path

      if no_download:
          raise FileNotFoundError(
              f"Cache miss and --no-download set: {zip_path}\n"
              f"Run without --no-download to fetch from {url}"
          )

      click.echo(f"  Downloading {url} ...")
      urllib.request.urlretrieve(url, zip_path)
      click.echo(f"  Saved → {zip_path} ({zip_path.stat().st_size / 1024:.0f} KB)")
      return zip_path


  def extract_zip(zip_path: Path) -> Path:
      """Extract a ZIP archive next to the ZIP file; return the extract directory.

      Extraction is skipped if the directory already exists.
      """
      extract_dir = zip_path.parent / zip_path.stem
      if not extract_dir.exists():
          with zipfile.ZipFile(zip_path) as zf:
              zf.extractall(extract_dir)
      return extract_dir


  def find_shapefile(extract_dir: Path) -> Path:
      """Find the first .shp file under extract_dir (recursive).

      Raises FileNotFoundError if none found.
      """
      matches = list(extract_dir.rglob("*.shp"))
      if not matches:
          raise FileNotFoundError(f"No .shp file found under {extract_dir}")
      return matches[0]


  def load_flood_footprint(
      shp_path: Path,
      target_crs: str,
      flood_attr: "str | None",
      flood_value: "str | None",
  ) -> list:
      """Read flood polygons from a shapefile, reproject, and optionally filter by class.

      Parameters
      ----------
      shp_path    : path to the .shp file
      target_crs  : EPSG string or WKT for the output CRS (e.g. "EPSG:32748")
      flood_attr  : attribute name to filter on; None = include all features
      flood_value : attribute value to match (case-insensitive); None = include all

      Returns
      -------
      list of shapely geometries in target_crs
      """
      import fiona
      from pyproj import CRS, Transformer
      from shapely.geometry import shape
      from shapely.ops import transform as shapely_transform

      geometries: list = []

      with fiona.open(str(shp_path)) as src:
          src_crs = CRS.from_user_input(dict(src.crs))
          tgt_crs = CRS.from_user_input(target_crs)
          transformer = Transformer.from_crs(src_crs, tgt_crs, always_xy=True)

          for feat in src:
              # Optionally filter by flood class attribute
              if flood_attr is not None and flood_value is not None:
                  raw = (feat["properties"].get(flood_attr) or "").strip()
                  if raw.lower() != flood_value.lower():
                      continue

              geom = shape(feat["geometry"])
              geom_proj = shapely_transform(transformer.transform, geom)
              geometries.append(geom_proj)

      return geometries
  ```

- [ ] **Step 4: Run polygon loading tests**

  ```bash
  python -m pytest tests/test_validate_historical_events.py -k "zip or shapefile or footprint" -v
  ```

  Expected: 8 tests PASS

- [ ] **Step 5: Commit**

  ```bash
  git add scripts/validate_historical_events.py tests/test_validate_historical_events.py
  git commit -m "feat: add download_zip, extract_zip, find_shapefile, load_flood_footprint"
  ```

---

## Task 5: Event validation orchestration (TDD)

**Files:**
- Modify: `scripts/validate_historical_events.py` — add `validate_event()`
- Modify: `tests/test_validate_historical_events.py` — add orchestration tests

- [ ] **Step 1: Add failing test**

  Append to `tests/test_validate_historical_events.py`:

  ```python
  from unittest.mock import patch, MagicMock

  from scripts.validate_historical_events import validate_event, EventConfig, CSI_PASS, CSI_WARN


  def _make_event_config(city_slug="jakarta", out_dir_str="outputs/jakarta_ssp585_2100"):
      return EventConfig(
          event_id="TEST",
          description="Test event",
          city_slug=city_slug,
          source_url="https://example.com/test.zip",
          flood_attr=None,
          flood_value=None,
          hazard_types=("pluvial",),
          rp_range=(50,),
          default_out_dir=out_dir_str,
      )


  def test_validate_event_pass(tmp_path):
      """validate_event returns PASS when model perfectly matches observed."""
      # Create a depth raster: 5×5, all 0.5 m (flooded above 0.1 m threshold)
      rp_dir = tmp_path / "pluvial" / "rp_50"
      rp_dir.mkdir(parents=True)
      tif = rp_dir / "pluvial_depth_SSP5-8.5_2100_rp50.tif"
      depth_data = np.full((5, 5), 0.5, dtype=np.float32)
      _write_depth_tif(tif, depth_data)

      # Observed footprint: full 5×5 grid (150 m × 150 m in UTM)
      observed_geom = box(0, 0, 150, 150)

      event = _make_event_config(out_dir_str=str(tmp_path))

      with patch("scripts.validate_historical_events.download_zip") as mock_dl, \
           patch("scripts.validate_historical_events.extract_zip") as mock_ex, \
           patch("scripts.validate_historical_events.find_shapefile") as mock_fs, \
           patch("scripts.validate_historical_events.load_flood_footprint") as mock_lf:

          mock_dl.return_value = MagicMock()
          mock_ex.return_value = MagicMock()
          mock_fs.return_value = MagicMock()
          mock_lf.return_value = [observed_geom]   # 1 polygon = full grid

          result = validate_event(event, out_dir=tmp_path, depth_threshold=0.10, no_download=False)

      assert result["verdict"] == "PASS"
      assert result["best_hazard"] == "pluvial"
      assert result["best_rp"] == 50
      assert result["best_csi"] == pytest.approx(1.0)


  def test_validate_event_fail(tmp_path):
      """validate_event returns FAIL when model predicts nothing."""
      rp_dir = tmp_path / "pluvial" / "rp_50"
      rp_dir.mkdir(parents=True)
      tif = rp_dir / "pluvial_depth_SSP5-8.5_2100_rp50.tif"
      # All depths = 0 → no predicted flood
      _write_depth_tif(tif, np.zeros((5, 5), dtype=np.float32))

      observed_geom = box(0, 0, 150, 150)
      event = _make_event_config(out_dir_str=str(tmp_path))

      with patch("scripts.validate_historical_events.download_zip"), \
           patch("scripts.validate_historical_events.extract_zip"), \
           patch("scripts.validate_historical_events.find_shapefile"), \
           patch("scripts.validate_historical_events.load_flood_footprint") as mock_lf:
          mock_lf.return_value = [observed_geom]
          result = validate_event(event, out_dir=tmp_path, depth_threshold=0.10, no_download=False)

      assert result["verdict"] == "FAIL"
      assert result["best_csi"] == pytest.approx(0.0)


  def test_validate_event_missing_out_dir():
      """validate_event raises SystemExit(2) if out_dir does not exist."""
      event = _make_event_config(out_dir_str="outputs/nonexistent_city")
      with pytest.raises(SystemExit) as exc_info:
          validate_event(event, out_dir=Path("outputs/nonexistent_city"),
                         depth_threshold=0.10, no_download=False)
      assert exc_info.value.code == 2
  ```

- [ ] **Step 2: Run to verify test fails**

  ```bash
  python -m pytest tests/test_validate_historical_events.py -k "validate_event" -v
  ```

  Expected: `ImportError` for `validate_event`.

- [ ] **Step 3: Implement `validate_event`**

  Add after `load_flood_footprint` in `scripts/validate_historical_events.py`:

  ```python
  # ---------------------------------------------------------------------------
  # Orchestration
  # ---------------------------------------------------------------------------

  def validate_event(
      event: EventConfig,
      out_dir: "Path | None",
      depth_threshold: float,
      no_download: bool,
  ) -> dict:
      """Download, rasterize, and validate one historical event.

      Returns a dict with keys:
          verdict, best_hazard, best_rp, best_csi, best_h, best_far, best_bias,
          obs_area_km2, all_rows
      Exits with code 2 if out_dir does not exist or no depth rasters found.
      """
      import rasterio

      resolved_out = out_dir if out_dir is not None else PROJECT_ROOT / event.default_out_dir
      if not resolved_out.exists():
          click.echo(f"[error] Output directory not found: {resolved_out}\n"
                     f"        Run the pipeline for '{event.city_slug}' first.", err=True)
          sys.exit(2)

      # ── Download and load flood polygon ─────────────────────────────────────
      cache_dir = PROJECT_ROOT / "data" / event.city_slug / "flood_obs" / event.event_id

      if not event.source_url:
          click.echo(f"[error] No source_url configured for {event.event_id}. "
                     f"Fill in _MYS2021_URL in the script.", err=True)
          sys.exit(2)

      zip_path = download_zip(event.source_url, cache_dir, no_download)
      extract_dir = extract_zip(zip_path)
      shp_path = find_shapefile(extract_dir)

      # ── Discover a reference depth raster for grid metadata ─────────────────
      ref_raster: "Path | None" = None
      for ht in event.hazard_types:
          for rp in event.rp_range:
              ref_raster = find_depth_raster(resolved_out, ht, rp)
              if ref_raster:
                  break
          if ref_raster:
              break

      if ref_raster is None:
          click.echo(f"[error] No depth rasters found under {resolved_out} for "
                     f"hazard types {event.hazard_types}.", err=True)
          sys.exit(2)

      with rasterio.open(ref_raster) as ds:
          height    = ds.height
          width     = ds.width
          transform = ds.transform
          crs_wkt   = ds.crs.to_wkt()
          pixel_area_m2 = abs(ds.res[0] * ds.res[1])

      # ── Load and rasterize observed footprint ───────────────────────────────
      geoms = load_flood_footprint(shp_path, crs_wkt,
                                   event.flood_attr, event.flood_value)
      if not geoms:
          click.echo(f"[warn] No matching polygons found in {shp_path.name} "
                     f"(flood_attr={event.flood_attr!r}, flood_value={event.flood_value!r}).")

      obs_mask = rasterize_footprint(geoms, height, width, transform)
      obs_area_km2 = float(obs_mask.sum()) * pixel_area_m2 / 1e6

      # ── Sweep all (hazard_type, rp) combos ──────────────────────────────────
      all_rows: list[dict] = []
      best: dict = {"csi": -1.0}

      for hazard_type in event.hazard_types:
          for rp in event.rp_range:
              depth_path = find_depth_raster(resolved_out, hazard_type, rp)
              if depth_path is None:
                  all_rows.append({
                      "hazard": hazard_type, "rp": rp,
                      "csi": None, "h": None, "far": None, "bias": None,
                  })
                  continue
              pred_mask = load_depth_mask(depth_path, depth_threshold)
              m = compute_metrics(pred_mask, obs_mask)
              all_rows.append({"hazard": hazard_type, "rp": rp, **m})
              if m["csi"] > best.get("csi", -1.0):
                  best = {"hazard": hazard_type, "rp": rp, **m}

      # ── Determine verdict ────────────────────────────────────────────────────
      best_csi = best.get("csi", 0.0) or 0.0
      if best_csi >= CSI_PASS:
          verdict = "PASS"
      elif best_csi >= CSI_WARN:
          verdict = "WARN"
      else:
          verdict = "FAIL"

      return {
          "verdict":     verdict,
          "best_hazard": best.get("hazard", ""),
          "best_rp":     best.get("rp", 0),
          "best_csi":    best_csi,
          "best_h":      best.get("h", 0.0),
          "best_far":    best.get("far", 0.0),
          "best_bias":   best.get("bias", 0.0),
          "obs_area_km2": obs_area_km2,
          "all_rows":    all_rows,
      }
  ```

- [ ] **Step 4: Run orchestration tests**

  ```bash
  python -m pytest tests/test_validate_historical_events.py -k "validate_event" -v
  ```

  Expected: 3 tests PASS

- [ ] **Step 5: Commit**

  ```bash
  git add scripts/validate_historical_events.py tests/test_validate_historical_events.py
  git commit -m "feat: add validate_event orchestration with RP sweep and PASS/WARN/FAIL gate"
  ```

---

## Task 6: CLI (TDD)

**Files:**
- Modify: `scripts/validate_historical_events.py` — add `cli()`, `_print_event_report()`
- Modify: `tests/test_validate_historical_events.py` — add CLI tests

- [ ] **Step 1: Add failing CLI tests**

  Append to `tests/test_validate_historical_events.py`:

  ```python
  from click.testing import CliRunner
  from scripts.validate_historical_events import cli


  def test_cli_unknown_event():
      runner = CliRunner()
      result = runner.invoke(cli, ["--event", "XXXXXXX"])
      assert result.exit_code != 0
      assert "Unknown event" in result.output


  def test_cli_missing_out_dir():
      runner = CliRunner()
      result = runner.invoke(cli, ["--event", "JKT2020",
                                   "--out-dir", "outputs/nonexistent_99"])
      assert result.exit_code == 2


  def test_cli_all_events_no_download(tmp_path):
      """--no-download with empty cache → exit 2 (cache miss)."""
      runner = CliRunner()
      result = runner.invoke(cli, ["--event", "JKT2020",
                                   "--out-dir", str(tmp_path),
                                   "--no-download"])
      # Either exit 2 (out_dir exists but no rasters) or 2 (cache miss)
      assert result.exit_code == 2
  ```

- [ ] **Step 2: Run to verify tests fail**

  ```bash
  python -m pytest tests/test_validate_historical_events.py -k "cli" -v
  ```

  Expected: `ImportError` for `cli`.

- [ ] **Step 3: Implement `_print_event_report` and `cli()`**

  Add at the end of `scripts/validate_historical_events.py`:

  ```python
  # ---------------------------------------------------------------------------
  # Reporting
  # ---------------------------------------------------------------------------

  def _print_event_report(event: EventConfig, result: dict) -> None:
      """Print the per-event metrics table and verdict to stdout."""
      click.echo(_SEP)
      click.echo(f"Historical event validation: {event.event_id} — {event.description}")
      click.echo(f"  City       : {event.city_slug}")
      click.echo(f"  Source     : {event.source_url}")
      click.echo(f"  Obs. area  : {result['obs_area_km2']:.1f} km²  "
                 f"(flood polygons rasterized to 30 m grid)")
      click.echo(f"  Flood thr  : 0.10 m")
      rp_label = ", ".join(
          f"{ht} RP{min(event.rp_range)}–RP{max(event.rp_range)}"
          for ht in event.hazard_types
      )
      click.echo(f"  RP range   : {rp_label}")
      click.echo(_SEP)

      click.echo(f"  {'Hazard':<10}{'RP':>6}  {'CSI':>6}  {'H':>6}  "
                 f"{'FAR':>6}  {'Bias':>6}  Verdict")
      click.echo(_DASH)

      for row in result["all_rows"]:
          if row.get("csi") is None:
              click.echo(f"  {row['hazard']:<10}{row['rp']:>6}  {'N/A':>6}  "
                         f"{'N/A':>6}  {'N/A':>6}  {'N/A':>6}  SKIP")
              continue
          is_best = (row["hazard"] == result["best_hazard"]
                     and row["rp"] == result["best_rp"])
          marker = "  ← best CSI" if is_best else ""
          click.echo(
              f"  {row['hazard']:<10}{row['rp']:>6}  "
              f"{row['csi']:>6.2f}  {row['h']:>6.2f}  "
              f"{row['far']:>6.2f}  {row['bias']:>6.2f}  INFO{marker}"
          )

      click.echo(_DASH)
      click.echo(
          f"Best match : {result['best_hazard']} RP{result['best_rp']}  "
          f"(CSI={result['best_csi']:.2f}, H={result['best_h']:.2f}, "
          f"FAR={result['best_far']:.2f}, Bias={result['best_bias']:.2f})"
      )
      click.echo(f"  → Verdict: {result['verdict']}")
      click.echo(_SEP)


  # ---------------------------------------------------------------------------
  # CLI entry point
  # ---------------------------------------------------------------------------

  @click.command()
  @click.option("--event", "event_id", default=None,
                help="Filter to one event ID (e.g. JKT2020). Default: run all.")
  @click.option("--out-dir", "out_dir", type=click.Path(path_type=Path), default=None,
                help="Override output directory (only used when --event is also set).")
  @click.option("--depth-threshold", "depth_threshold", type=float, default=0.10,
                show_default=True, help="Flooded depth threshold in metres.")
  @click.option("--no-download", "no_download", is_flag=True, default=False,
                help="Skip network fetch; fail if cache missing.")
  def cli(
      event_id: "str | None",
      out_dir: "Path | None",
      depth_threshold: float,
      no_download: bool,
  ) -> None:
      """Validate flood pipeline against historical observed flood extents."""

      # Select events to run
      if event_id is not None:
          matching = [e for e in EVENTS if e.event_id == event_id]
          if not matching:
              valid = ", ".join(e.event_id for e in EVENTS)
              click.echo(f"Unknown event '{event_id}'. Valid IDs: {valid}")
              sys.exit(1)
          events_to_run = matching
      else:
          events_to_run = EVENTS
          if out_dir is not None:
              click.echo("[warn] --out-dir is ignored when running all events "
                         "(each event uses its configured default_out_dir).")

      fails: list[str] = []

      for event in events_to_run:
          # Use per-event default unless overridden (only honoured for single-event runs)
          effective_out = out_dir if (event_id is not None and out_dir is not None) \
              else PROJECT_ROOT / event.default_out_dir

          click.echo(f"\nRunning: {event.event_id} — {event.description}")
          result = validate_event(event, effective_out, depth_threshold, no_download)
          _print_event_report(event, result)

          if result["verdict"] == "FAIL":
              fails.append(event.event_id)

      click.echo("")
      if fails:
          click.echo(f"OVERALL: FAIL — {len(fails)} event(s) below CSI threshold: "
                     f"{', '.join(fails)}")
          sys.exit(1)
      else:
          click.echo("OVERALL: PASS (all events PASS or WARN)")
          sys.exit(0)


  if __name__ == "__main__":
      cli()
  ```

- [ ] **Step 4: Run CLI tests**

  ```bash
  python -m pytest tests/test_validate_historical_events.py -k "cli" -v
  ```

  Expected: 3 tests PASS

- [ ] **Step 5: Run full test suite**

  ```bash
  python -m pytest tests/test_validate_historical_events.py -v
  ```

  Expected: all tests PASS (approximately 22 tests total)

- [ ] **Step 6: Commit**

  ```bash
  git add scripts/validate_historical_events.py tests/test_validate_historical_events.py
  git commit -m "feat: add CLI, report printer — validate_historical_events complete"
  ```

---

## Task 7: Methodology doc update

**Files:**
- Modify: `docs/hazard_methodology_comparison.md`

- [ ] **Step 1: Correct EMSR references in Issue #11 and the at-a-glance status**

  In `docs/hazard_methodology_comparison.md`, find the Issue #11 row (line ~652):

  ```markdown
  | 11 | All cities | All hazards | **No validation against historical events.** Pipeline produces design-RP maps but never compares to documented events (Jakarta 2007/2013/2020, Bangkok 2011, KL 2021, **Manila Ondoy 2009 — EMSR available**, **HCMC 2008 typhoon**). The HCMC pluvial RP1000 of 0.32 m is suspiciously low and would benefit from R4 priority validation. | **Open — Critical**; Ondoy 2009 EMSR + Jakarta 2020 EMSR432 + KL 2021 EMSR530 are the recommended first three runs |
  ```

  Replace the Status cell with:

  ```markdown
  **Partial — In progress (2026-05-08)**: `scripts/validate_historical_events.py` added. Copernicus EMS was NOT activated for either Jakarta Jan 2020 or Malaysia Dec 2021 — the EMSR432/EMSR530 references in earlier versions of this doc were incorrect. Data sources corrected: Jakarta uses Sentinel-Asia EOS-ARIA flood proxy (Sentinel-1, Jan 2, 2020; URL confirmed); Malaysia Dec 2021 source pending (check UNOSAT HDX or Copernicus GFM). Manila Ondoy 2009 excluded — EMS started 2012, no EMSR product exists. Script implements CSI/H/FAR metrics with WARN (CSI<0.30) / FAIL (CSI<0.15) gates, auto-download, RP sweep.
  ```

- [ ] **Step 2: Update at-a-glance status paragraph (line ~9)**

  Find the sentence: `**Remaining gaps:** (a) absence of historical-event validation (R4 — Issue #11);`

  Update to: `**Remaining gaps:** (a) historical-event validation (R4 — Issue #11) in progress — validator script written, Jakarta 2020 source confirmed (Sentinel-Asia), Malaysia 2021 source pending;`

- [ ] **Step 3: Commit**

  ```bash
  git add docs/hazard_methodology_comparison.md
  git commit -m "docs: correct EMSR numbers for Issue #11, update R4 validation status"
  ```

---

## Task 8: Smoke test against real Jakarta outputs

**Context:** This task verifies the end-to-end pipeline with real Jakarta data. It requires `outputs/jakarta_ssp585_2100/` to exist (run `python scripts/run_city_pipeline.py --city jakarta` first if it doesn't).

- [ ] **Step 1: Check Jakarta outputs exist**

  ```bash
  ls D:\Downloads\Claude-Cursor\outputs\jakarta_ssp585_2100\pluvial\rp_50\
  ```

  Expected: `pluvial_depth_SSP5-8.5_2100_rp50.tif` visible.

  If the directory is missing, run:
  ```bash
  python scripts/run_city_pipeline.py --city jakarta --scenario SSP5-8.5 --horizon 2100
  ```
  (this takes ~10–30 minutes)

- [ ] **Step 2: Run the validator for JKT2020 only**

  ```bash
  cd D:\Downloads\Claude-Cursor
  python scripts/validate_historical_events.py --event JKT2020
  ```

  Expected output: downloads ~778 KB ZIP (first run), prints metrics table, exits 0 (PASS or WARN) or 1 (FAIL — if CSI < 0.15 the model has a significant problem to investigate).

  The first run will take ~30 seconds (download + shapefile processing). Subsequent runs are instant (cached).

- [ ] **Step 3: Record the best-match CSI in the methodology doc**

  In `docs/hazard_methodology_comparison.md`, find Issue #11 and append the actual CSI result from Step 2, e.g.:
  ```
  Jakarta JKT2020 smoke test: best CSI=0.XX at pluvial/fluvial RP_XX (run 2026-05-08).
  ```

- [ ] **Step 4: Commit**

  ```bash
  git add docs/hazard_methodology_comparison.md
  git commit -m "docs: record JKT2020 validation smoke-test result (Issue #11)"
  ```
