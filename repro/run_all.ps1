<#
  run_all.ps1 — flood-v4.0 bare-earth multi-hazard atlas driver
  ----------------------------------------------------------------------------
  Regenerates the atlas from clean inputs. Per-city flags are transcribed from
  the handoff §9 run matrix; the coastal MSL offset is resolved at runtime from
  scripts/cities.py so it can never go stale.

  Two interpreters (handoff §2) — this driver uses ONLY the flood interpreter
  (the adopted DEMs are pre-built and vendored). DEM rebuilds use the `sfincs`
  conda env separately.

  STAGES
    -Stage validate  (default) : present-day RP100 documented-hotspot gate,
                                  all 4 cities — the step-2 trust gate.
    -Stage atlas               : full 3-RP × 2×2 scenario grid — SLOW
                                  (inertial coastal ≈30 min/run; KL raingrid
                                  slow at high RP). Gated on purpose.

  PREREQUISITES finalised in later steps (NOT done here):
    • step 3: per-scenario 3-RP (10/100/1000) forcing slices (handoff §4)
    • step 4: model-blind register expansion, frozen before scoring (handoff §7)

  USAGE
    pwsh repro/run_all.ps1                         # validate, all cities, present-day
    pwsh repro/run_all.ps1 -City jakarta           # one city
    pwsh repro/run_all.ps1 -Stage atlas -DryRun    # print the full matrix, run nothing
#>
[CmdletBinding()]
param(
  [ValidateSet('all','bangkok','jakarta','kuala_lumpur','singapore')]
  [string]$City = 'all',
  [ValidateSet('validate','atlas')]
  [string]$Stage = 'validate',
  [string]$Scenario = 'present',
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$PY = 'C:\Users\Daniel\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$ROOT = Split-Path -Parent $PSScriptRoot          # repo root (repro/..)
Set-Location $ROOT

# ── scenario-horizon grid ─────────────────────────────────────────────────────
#   key -> @(hazard_levels CSV stem, scenario label, horizon year)
$SCENARIOS = [ordered]@{
  'present'      = @('ssp585_2020', 'SSP5-8.5', 2020)   # present-day validation baseline
  'ssp245_2050'  = @('ssp245_2050', 'SSP2-4.5', 2050)
  'ssp245_2100'  = @('ssp245_2100', 'SSP2-4.5', 2100)
  'ssp585_2050'  = @('ssp585_2050', 'SSP5-8.5', 2050)
  'ssp585_2100'  = @('ssp585_2100', 'SSP5-8.5', 2100)
}

# ── per-city static config (handoff §3 terrain, §9 flags) ─────────────────────
#   utm    : mask suffix          dem/hand: relative to repo root
#   runoff : §9 uniform fallback   clamp   : $false => pass --no-clamp-negative-land
$CITYCFG = @{
  bangkok = @{
    utm='utm47n'; runoff=0.75; clamp=$false; coastal=$true; pluvial='fillspill'
    dem ='dem/_hand/bangkok_v3_debiased_defended.tif'
    hand='dem/_hand/hand_trunk_v3_debiased.tif'
    polder=$true        # apply_pumped_polder.py post-step
  }
  jakarta = @{
    utm='utm48s'; runoff=0.80; clamp=$false; coastal=$true; pluvial='fillspill'
    dem ='dem/jakarta/dem_bareearth_jakarta_present_conditioned.tif'
    hand='dem/_hand/jakarta_hand_v3.tif'
    polder=$false
  }
  kuala_lumpur = @{
    utm='utm47n'; runoff=0.75; clamp=$true; coastal=$false; pluvial='raingrid'
    dem ='dem/kl/dem_bareearth_kl_eth_present_conditioned.tif'
    hand='dem/_hand/kl_hand_mainstem_v3eth.tif'
    pluvial_dem='dem/_hand/kl_raingrid_v3eth.tif'
    tidal_channel='data/kuala_lumpur/drainage_waterways_utm47n.tif'
    polder=$false
  }
  singapore = @{
    utm='utm48n'; runoff=0.75; clamp=$true; coastal=$true; pluvial='fillspill'
    dem ='dem/singapore/dem_bareearth_singapore_present_conditioned.tif'
    hand='dem/_hand/singapore_hand_v3_hybrid.tif'
    polder=$false
  }
}

function Resolve-Msl([string]$slug) {
  & $PY -c "import sys; sys.path.insert(0,'scripts'); from cities import CITIES; print(CITIES['$slug'].msl_to_egm2008_offset)"
}

function Build-RunArgs([string]$slug, [string]$csvStem, [string]$scLabel, [int]$horizon, [string]$outDir) {
  $c = $CITYCFG[$slug]; $u = $c.utm
  $a = @(
    'scripts/run_multihazard.py',
    '--dem', $c.dem,
    '--fluvial-hand-raster', $c.hand,
    '--hazard-levels', "data/$slug/hazard_levels_$csvStem.csv",
    '--scenario', $scLabel, '--horizon', $horizon,
    '--out-dir', $outDir,
    '--fluvial-bankfull-rp', '0',
    '--runoff-coeff-raster', "data/$slug/runoff_coeff_$u.tif",
    '--runoff-coeff', $c.runoff,
    '--pluvial-model', $c.pluvial, '--pluvial-depth-cap', '3.0'
  )
  if ($c.pluvial -eq 'raingrid') { $a += @('--pluvial-dem-raster', $c.pluvial_dem) }
  if ($c.coastal) {
    $msl = Resolve-Msl $slug
    $a += @('--coastal-solver','inertial','--coastal-msl-egm2008', $msl,
            '--sea-mask-raster', "data/$slug/sea_mask_$u.tif",
            '--tidal-channel-raster', "data/$slug/river_mask_$u.tif",
            '--tidal-burn-elevation','2.0')
  } else {
    $a += @('--only-hazard-types','fluvial,pluvial')
    if ($c.tidal_channel) { $a += @('--tidal-channel-raster', $c.tidal_channel) }
  }
  if (-not $c.clamp) { $a += '--no-clamp-negative-land' }
  return ,$a
}

function Invoke-CityScenario([string]$slug, [string]$scKey) {
  $s = $SCENARIOS[$scKey]; $csvStem=$s[0]; $scLabel=$s[1]; $horizon=$s[2]
  $outDir = "outputs/${slug}_${scKey}"
  $runArgs = Build-RunArgs $slug $csvStem $scLabel $horizon $outDir
  Write-Host "`n>>> $slug / $scKey" -ForegroundColor Cyan
  Write-Host "    $PY $($runArgs -join ' ')"
  if (-not $DryRun) { & $PY @runArgs | Out-Host }
  if ($CITYCFG[$slug].polder) {
    $polderDir = "${outDir}_polder"
    Write-Host "    + apply_pumped_polder.py ($slug) -> $polderDir" -ForegroundColor Yellow
    if (-not $DryRun) {
      & $PY scripts/apply_pumped_polder.py --city $slug --src-dir $outDir --out-dir $polderDir `
          --rp 100 --scenario $scLabel --horizon $horizon | Out-Host
    }
    return $polderDir
  }
  return $outDir
}

# ── dispatch ──────────────────────────────────────────────────────────────────
$cities = if ($City -eq 'all') { 'bangkok','jakarta','kuala_lumpur','singapore' } else { ,$City }

if ($Stage -eq 'validate') {
  foreach ($cc in $cities) {
    $scored = Invoke-CityScenario $cc 'present'
    if (-not $DryRun) {
      Write-Host "    scoring present-day RP100 gate ($cc) in $scored" -ForegroundColor Green
      # Singapore uses its own scorer (register under flood_obs/hotspots/); the
      # other 3 use the generic validate_hotspots.py (manifest registers).
      if ($cc -eq 'singapore') {
        & $PY scripts/_score_singapore_hotspot_v2.py --out-dir $scored --rp 100 --label 'DeltaDTM'
      } else {
        & $PY scripts/validate_hotspots.py --city $cc --out-dir $scored --rp 100 --scenario SSP5-8.5 --horizon 2020
      }
    }
  }
}
elseif ($Stage -eq 'atlas') {
  Write-Host "ATLAS: 3-RP × 2×2 grid. Ensure step-3 RP slices + step-4 frozen registers exist first." -ForegroundColor Magenta
  $scKeys = if ($Scenario -eq 'present') { $SCENARIOS.Keys } else { ,$Scenario }
  foreach ($cc in $cities) { foreach ($sk in $scKeys) { Invoke-CityScenario $cc $sk } }
}
