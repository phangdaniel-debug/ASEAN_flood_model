# Drain-conveyance anchor for the capacity-limited raingrid (Plan 6 Task 3)

**Purpose:** set `--drain-conveyance-m-s` for the finite (minor-drain) outlet cells from a
**documented** drain capacity, not from the validation gate (discipline guard, limitation #19).

## Source

Representative **secondary urban monsoon drain**, per **MSMA 2nd ed. (Urban Stormwater
Management Manual for Malaysia, DID Malaysia, 2012)** typical concrete-lined secondary-drain
section. Representative geometry (secondary tier, the dominant minor-drain class in the OSM
waterway network used as KL's drainage):

- bottom width `b = 1.2 m`
- design flow depth `y = 1.0 m`
- longitudinal slope `S = 0.002` (typical urban secondary-drain grade)
- Manning's `n = 0.015` (smooth concrete)

## Manning conveyance

Rectangular section:
- Area `A = b·y = 1.2 × 1.0 = 1.20 m²`
- Wetted perimeter `P = b + 2y = 1.2 + 2.0 = 3.20 m`
- Hydraulic radius `R = A/P = 0.375 m` → `R^(2/3) = 0.521`
- `Q = (1/n)·A·R^(2/3)·S^(1/2) = (1/0.015)·1.20·0.521·0.0447 ≈ 1.86 m³/s`

## Per-cell depth-shed rate

An outlet cell is 30 × 30 = **900 m²** of surface. The drain through it can shed water from
that surface at:

`drain_conveyance_m_s = Q / cell_area = 1.86 / 900 ≈ 0.00207 m/s`  →  **use `0.002 m/s` (≈ 2 mm/s).**

## Caveats (honest)

- **Uniform across minor drains.** A ditch conveys less and a canal more than this secondary
  value; we apply one representative rate to all minor-drain cells (sea + major rivers are
  perfect sinks, handled separately via `--major-river-raster`). Per-drain-class conveyance is a
  later refinement if validation shows it's needed.
- **Sensitivity.** Q scales ~linearly with the assumed section; a half-size ditch (~0.9 m³/s →
  0.001 m/s) or a canal (~4 m³/s → 0.0044 m/s) bracket the value. 0.002 m/s is the secondary-drain
  midpoint. The selection criterion is this documented section — NOT the gate.

**Value adopted: `--drain-conveyance-m-s 0.002` (minor drains) + `--major-river-raster
data/kuala_lumpur/river_mask_utm47n.tif` (sea + major rivers stay perfect sinks).**
