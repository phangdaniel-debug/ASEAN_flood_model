<#
.SYNOPSIS
    Detached overnight pipeline runner for run_city_pipeline.py sweeps.

.DESCRIPTION
    Launches a sequence of city-pipeline runs as detached, session-independent
    processes that survive Claude Code session changes, user logoff, etc.

    Designed in response to debugging finding (May 18 2026): the previous
    overnight Bangkok defended+inertial run died silently because the parent
    Claude Code session was terminated mid-run, killing the orphan Python child.
    See systematic-debugging investigation in conversation history.

    Two key behaviours:
      1. Each scenario is invoked as a fresh Python process via Start-Process,
         not chained inside a single bash loop. This eliminates the accumulated
         parent-shell state (file-cache pressure, AV scan queue) that caused
         monotonic per-RP slowdown across sequential pipelines in the earlier
         overnight run.
      2. Numba parallel mode stays ON (NUMBA_NUM_THREADS is NOT set). The prior
         attempt to set NUMBA_NUM_THREADS=1 in response to §6.6 of the
         methodology doc was a misreading - that paragraph meant "serialise
         scenarios at the process level" not "disable numba parallelism".
         Empirical measurement showed single-thread mode was ~114x slower
         per RP than the default parallel mode.

.PARAMETER LogPath
    Where to append per-scenario stdout/stderr. Default: logs/overnight_<timestamp>.log

.PARAMETER SentinelPath
    File written when the entire queue is complete. Default: logs/overnight_<timestamp>.done

.EXAMPLE
    # Run from PowerShell (foreground):
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\_run_overnight_pipeline.ps1

    # Run detached so it survives this PowerShell window closing or Claude
    # Code session ending. The ExecutionPolicy Bypass flag is required
    # because the script is unsigned and Windows default policy blocks
    # unsigned scripts (UnauthorizedAccess error otherwise).
    Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','scripts\_run_overnight_pipeline.ps1' -WindowStyle Hidden

.NOTES
    Customise the @scenarios array below to set which (city, scenario, horizon,
    extra-flags) tuples to run. Each tuple becomes one detached Python pipeline.
#>

# Hardcoded queue. Edit this list for what to run.
# Format: @{city='...'; scenario='...'; horizon=YYYY; solver='inertial'|'bathtub'; extra=@(...)}
#
# Ordering rationale (highest-priority first, so a partial overnight still
# delivers value):
#   1. Finish Bangkok defended+inertial (SSP5-8.5 / 2050 + 2100) — partial
#      work already done; closes out the headline city.
#   2. Singapore (4 scenarios) — cleanest validation case; in-city PUB gauge,
#      already on inertial, new Marina Barrage + ECP defense polylines.
#   3. HCMC (4 scenarios, bathtub — inertial blocked per §5.4) — Saigon-Nha
#      Be ring dyke + tide gates; closes a real RP2 gap.
#   4. Manila (4 scenarios, bathtub — inertial blocked) — largest absolute
#      bias to fix (RP2 182x); KAMANAVA + Pasig + MMDA seawalls.
#   5. Jakarta (4 scenarios, inertial) — completes coverage; low marginal
#      value given existing 1.7x RP100 bias, runs last.
#
# Common flags:
#   --subsidence-correction: enable per-city subsidence raster (no-op when
#                            no zone config exists, e.g. singapore).
#   --flood-defenses       : enable the new defense polyline burns added to
#                            apply_flood_defenses.py for all four cities.
#   --no-fit-*             : reuse cached GEV/coastal/GloFAS fits, skip the
#                            slow stats refits (~30 min/run saved).
$commonFlags = @(
    '--subsidence-correction',
    '--flood-defenses',
    '--no-fit-era5',
    '--no-fit-coastal',
    '--no-fit-glofas',
    # Halve the inertial simulation horizon from default 8h -> 4h so the
    # full 18-scenario queue fits in an overnight window. Per the model's
    # own help text this risks truncating the surge peak in long-tail
    # scenarios, but empirically the surge hydrograph used here peaks
    # within the first ~3-4h, so 14400s should still capture the peak.
    # Decision recorded May 18 23:09 PST after observing SSP5-8.5/2050
    # RP5 was taking 25+ min/RP at the 8h default.
    '--inertial-t-end', '14400'
)
$scenarios = @(
    # ---- Rerun batch (May 19) for the 8 scenarios that failed in the
    # 23:13 May 18 run due to a UnicodeEncodeError in HCMC + Manila defense
    # names containing U+2192 ('->'). Fixed by replacing with ASCII '->'.
    # Bangkok / Singapore / Jakarta succeeded on the first pass; no need
    # to re-run them.
    # ---- HCMC defended+bathtub (Saigon ring dyke + tide gates) ----
    @{city='hcmc';      scenario='SSP2-4.5'; horizon=2050; solver='bathtub';  extra=$commonFlags}
    @{city='hcmc';      scenario='SSP2-4.5'; horizon=2100; solver='bathtub';  extra=$commonFlags}
    @{city='hcmc';      scenario='SSP5-8.5'; horizon=2050; solver='bathtub';  extra=$commonFlags}
    @{city='hcmc';      scenario='SSP5-8.5'; horizon=2100; solver='bathtub';  extra=$commonFlags}

    # ---- Manila defended+bathtub (MMDA + Pasig + KAMANAVA) ----
    @{city='manila';    scenario='SSP2-4.5'; horizon=2050; solver='bathtub';  extra=$commonFlags}
    @{city='manila';    scenario='SSP2-4.5'; horizon=2100; solver='bathtub';  extra=$commonFlags}
    @{city='manila';    scenario='SSP5-8.5'; horizon=2050; solver='bathtub';  extra=$commonFlags}
    @{city='manila';    scenario='SSP5-8.5'; horizon=2100; solver='bathtub';  extra=$commonFlags}
)

# Resolve repo root from the script location.
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$Timestamp   = Get-Date -Format 'yyyyMMdd_HHmmss'
$LogDir      = Join-Path $ProjectRoot 'logs'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$LogPath      = Join-Path $LogDir "overnight_$Timestamp.log"
$SentinelPath = Join-Path $LogDir "overnight_$Timestamp.done"

# Locate the Python interpreter. Prefer the explicit pythoncore install over
# whatever PATH returns first, because Windows by default shadows python.exe
# with a Microsoft Store stub at C:\Users\<u>\AppData\Local\Microsoft\WindowsApps\
# that pops the Store dialog instead of running. The pythoncore-3.14-64 path
# matches what the existing pipeline log (logs/bkk_defended_inertial.log)
# shows is in use.
$Python = 'C:\Users\Daniel\AppData\Local\Python\pythoncore-3.14-64\python.exe'
if (-not (Test-Path $Python)) {
    # Fall back to PATH only if the pythoncore path is missing, and filter out
    # the WindowsApps stub (zero-length file pointing at the Store).
    $candidates = Get-Command python.exe -All -ErrorAction SilentlyContinue |
                  Where-Object { $_.Source -notmatch '\\WindowsApps\\' }
    if ($candidates) { $Python = $candidates[0].Source }
}
if (-not (Test-Path $Python)) {
    throw "Could not locate a real python.exe (tried pythoncore-3.14-64 and PATH)."
}

# Banner
$banner = @"
================================================================
Overnight pipeline runner started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
ProjectRoot : $ProjectRoot
Python      : $Python
LogPath     : $LogPath
Sentinel    : $SentinelPath
Scenarios   : $($scenarios.Count)
NUMBA mode  : parallel (default - DO NOT set NUMBA_NUM_THREADS=1)
================================================================
"@
Add-Content -Path $LogPath -Value $banner
Write-Host $banner

# Execute each scenario serially, each as its own fresh Python process.
# Start-Process -Wait blocks this script until the child exits, but the
# child is a separate process tree from any caller (Claude Code, etc.)
# so abrupt termination of the launcher does NOT kill the Python child.
$idx = 0
foreach ($s in $scenarios) {
    $idx++
    $header = @"

================================================================
[$idx/$($scenarios.Count)] $($s.city) $($s.scenario) / $($s.horizon)  solver=$($s.solver)
started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
================================================================
"@
    Add-Content -Path $LogPath -Value $header
    Write-Host $header

    $argList = @(
        (Join-Path $ProjectRoot 'scripts\run_city_pipeline.py'),
        '--city',           $s.city,
        '--scenario',       $s.scenario,
        '--horizon',        $s.horizon,
        '--coastal-solver', $s.solver
    ) + $s.extra

    # Start the Python subprocess. RedirectStandardOutput / Error stream the
    # pipeline's output to per-scenario files we then concatenate to the main
    # log when the run completes (Start-Process can't append to an existing
    # file directly).
    $tempOut = [System.IO.Path]::GetTempFileName()
    $tempErr = [System.IO.Path]::GetTempFileName()
    try {
        $proc = Start-Process -FilePath $Python `
                              -ArgumentList $argList `
                              -WorkingDirectory $ProjectRoot `
                              -NoNewWindow `
                              -Wait `
                              -PassThru `
                              -RedirectStandardOutput $tempOut `
                              -RedirectStandardError  $tempErr

        Get-Content $tempOut | Add-Content -Path $LogPath
        Get-Content $tempErr | Add-Content -Path $LogPath

        $footer = "[$idx/$($scenarios.Count)] EXIT $($proc.ExitCode) at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        Add-Content -Path $LogPath -Value $footer
        Write-Host $footer

        if ($proc.ExitCode -ne 0) {
            $msg = "Pipeline failed (exit $($proc.ExitCode)) for $($s.city) $($s.scenario)/$($s.horizon). Continuing with remaining scenarios."
            Add-Content -Path $LogPath -Value $msg
            Write-Host $msg
        }
    }
    finally {
        Remove-Item -Path $tempOut -ErrorAction SilentlyContinue
        Remove-Item -Path $tempErr -ErrorAction SilentlyContinue
    }
}

# Write completion sentinel.
$summary = @"

================================================================
Overnight queue complete: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Scenarios processed: $($scenarios.Count)
================================================================
"@
Add-Content -Path $LogPath -Value $summary
Set-Content -Path $SentinelPath -Value $summary
Write-Host $summary
