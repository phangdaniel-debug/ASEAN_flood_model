# Bangkok main-stem HAND viability — NEGATIVE (Plan B2 Task 1)

**Finding: the KL accumulation main-stem-HAND does NOT transfer to Bangkok.** DEM flow-
accumulation counts only WITHIN-domain contributing area, but the Chao Phraya's 160,000 km²
catchment is almost entirely OUTSIDE the 5,444 km² Bangkok domain (it enters as boundary
inflow; D8 accumulation starts at 0 at the edge). So accumulation cannot identify the trunk.

Sweep (RP100 mainstem stage 7.11 m; `scripts/_diag_bangkok_mainstem_hand.py`):

| acc thr (px) | channels | extent<7.11 m | extent % | note |
|---|---|---|---|---|
| 20,000 | 18,259 | 3,507 km² | 64% | catastrophic over-flood (flat delta + dense channels) |
| 200,000 | 43 | 216 km² | 4% | only the immediate Chao Phraya trunk; misses outer 2011 districts (Sai Mai/Pak Kret/Mueang Non = NaN HAND); CBD clears |
| 1,000,000+ | 0 | — | no in-domain channel reaches that accumulation |

**Conclusion:** single-stage HAND worked for KL's *incised valley* but is structurally
unsuited to a **flat-delta megaflood fed by an out-of-domain mega-river**. The 7.11 m mainstem
stage via any dense HAND floods most of the delta; via trunk-only HAND it can't reach the
districts the 2011 basin flood actually inundated. **Decision (user): hydrodynamic mainstem
fluvial** — route the Chao Phraya overbank via the inertial solver (a riverine boundary-inflow
hydrograph, like the coastal surge), NOT HAND. This is the physically-correct flat-delta
treatment and a new sub-project (Plan B2 revised).

**Transferability lesson:** main-stem HAND (#20) transfers to incised-valley cities (KL); flat
deltas with out-of-domain mega-rivers (Bangkok, likely Jakarta/HCMC) need hydrodynamic fluvial
routing — the inertial solver, already used for coastal.

## Hydrodynamic riverine-fluvial design (B2-revised, chosen)

**Key enabler:** `model/inertial_wave_model.py::run_inertial(z, sea_mask, wl_boundary, …)`
holds cells in a boundary mask at a Dirichlet water-surface elevation (static or a
`wl_fn(t)` hydrograph) and propagates shallow-water flow. It is hazard-agnostic — "coastal"
= sea_mask + surge hydrograph. **Riverine fluvial = river-channel mask + a riverine stage.**
This propagates the Chao Phraya overbank onto the floodplain *dynamically* (connectivity +
friction), fixing BOTH HAND failures: disconnected low cells (the CBD) don't flood unless
water reaches them (CRR), and water spreads across the connected flat delta to the outer
2011 districts (HR).

**Design decisions to settle in the B2-revised spec/plan:**
1. **River boundary mask** = the Chao Phraya mainstem channel cells (from the OSM river mask,
   filtered to the mainstem/major reaches — NOT all klongs). These are the Dirichlet source.
2. **Sloping water surface (the crux):** unlike the flat sea, a river surface slopes downstream.
   The boundary water-surface elevation per river cell = `bed_elevation(cell) + flood_depth`,
   where `flood_depth` = bankfull + the RP overbank (BCP RP100 ≈ 7.11 m relative). So the
   source follows the bed slope + a near-uniform overbank depth, and the solver routes the
   spill physically. (A single uniform absolute `wl` would be wrong for a sloping river.)
3. **Hydrograph:** the 2011 flood was sustained (weeks) → a long ramp-hold (or static) BC gives
   the equilibrium floodplain extent (the design-RP maximum inundation). Reuse the coastal
   hydrograph machinery with a long hold.
4. **Build/anchor:** the river mask + bed profile from the committed `river_mask` + DEM; the
   overbank depth from the documented BCP mainstem stage (7.11 m RP100). Anchored to data, not
   the gate.
5. **Validate:** run riverine-inertial → fluvial inundation; union into the composite; re-run
   the Bangkok hotspot gate. Expect HR up (outer districts reached) + CRR up (CBD only floods
   if hydrodynamically connected — the honest King's-Dyke test). Inertial compute ~50 min/run.

**Scope:** this is a new solver MODE + spec/plan/TDD/compute — a dedicated B2-revised effort.
