"""
Consolidated visualisation suite for ASEAN flood-model outputs.

Replaces the old per-scenario PNG explosion (9 per-RP PNGs + 1 comparison
+ 9 street overlays + 1 comparison = 20 files per scenario per variant)
with a smaller, cleaner cross-cutting set of figures organised under
``outputs/_viz/``::

    outputs/_viz/
        01_rp_comparison/         # 3x3 RP panel per (city, scen, yr, variant)
        02_defended_vs_undefended/ # 2x2 (RP2/RP100 x undef/def) per scenario
        03_suite_overview/        # 5-city panel per (RP, scen, yr)
        04_scenario_progression/  # 2x2 climate grid per (city, RP, variant)
        INDEX.md                  # auto-generated table of contents

User defaults (selected May 19 2026):
  --headline-rps:  2,100   (RP2 = annual; RP100 = design event)
  --scenarios:     ssp245_2050, ssp245_2100, ssp585_2050, ssp585_2100  (full 2x2)

All figures are derived from the existing per-scenario depth TIFs and
summary CSVs — no model rerun required. Pluvial cells with depth below
``--pluvial-floor`` (default 0.05 m) are suppressed for rendering, hiding
the 0.005 m drain-capacity floor noise.

Usage::

    # Regenerate everything (~5-10 min):
    python scripts/build_viz_suite.py all

    # Or one panel type at a time:
    python scripts/build_viz_suite.py rp-comparison
    python scripts/build_viz_suite.py defended-vs-undefended
    python scripts/build_viz_suite.py suite-overview
    python scripts/build_viz_suite.py scenario-progression
    python scripts/build_viz_suite.py index
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import click
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import rasterio


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HAZARD_CMAPS = {
    "coastal": "Blues",
    "fluvial": "Oranges",
    "pluvial": "Greens",
}
HAZARD_COLOURS = {
    "coastal": "#2166AC",
    "fluvial": "#D94801",
    "pluvial": "#1A9850",
}
RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]

# Scenarios in the 2x2 grid, ordered for figure layouts.
SCENARIOS = [
    ("SSP2-4.5", 2050, "ssp245_2050"),
    ("SSP5-8.5", 2050, "ssp585_2050"),
    ("SSP2-4.5", 2100, "ssp245_2100"),
    ("SSP5-8.5", 2100, "ssp585_2100"),
]

# Coastal-relevant cities (KL is inland; supplementary slugs skipped by
# default — they are sub-region cuts of the parent metros).
SUITE_CITIES = ["singapore", "bangkok", "jakarta", "manila", "hcmc"]

# Pretty display names.
CITY_DISPLAY = {
    "singapore": "Singapore",
    "bangkok":   "Bangkok",
    "jakarta":   "Jakarta",
    "manila":    "Manila",
    "hcmc":      "Ho Chi Minh City",
    "kuala_lumpur": "Kuala Lumpur",
    "bangkok_chao_phraya": "Bangkok (Chao Phraya)",
    "klang_shah_alam": "Klang–Shah Alam",
    "subang_langat": "Subang–Langat",
    "tangerang": "Tangerang",
    "bekasi_depok": "Bekasi–Depok",
}

# ---------------------------------------------------------------------------
# Output layout
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScenarioDir:
    """Discovered scenario output directory."""
    city: str
    scenario: str             # e.g. "SSP2-4.5"
    horizon: int              # e.g. 2050
    variant: str              # "undefended" | "defended" | "defended_polygons" | "defended_bathtub"
    path: Path

    @property
    def slug(self) -> str:
        """e.g. bangkok_ssp245_2050_defended"""
        return self.path.name

    @property
    def scen_slug(self) -> str:
        """ssp245_2050"""
        return f"{self.scenario.lower().replace('-', '').replace('.', '')}_{self.horizon}"


_SLUG_RE = re.compile(r"^(?P<city>[a-z_]+?)_ssp(?P<sc>\d{3})_(?P<yr>\d{4})(?P<rest>.*)$")


def discover_scenarios(out_root: Path) -> list[ScenarioDir]:
    """Walk outputs/ and outputs/Archive/, return one ScenarioDir per directory.

    The user archived the pre-May-2026 scenario tree into ``outputs/Archive/``
    when the PNG clutter became unmanageable. Future pipeline runs land
    back under ``outputs/<scenario>/``. We walk both to keep both visible
    to the viz suite.
    """
    found: list[ScenarioDir] = []
    seen: set[str] = set()
    # Walk outputs/ as one group, then Archive/ as a second group. Each
    # group is sorted internally, but the groups are processed in order so
    # a fresh outputs/<scenario> always shadows an Archive/<scenario> of
    # the same name. (A single sorted() over both lists would not: the
    # "Archive" path component sorts before the lowercase city dirs, so
    # Archive copies would wrongly win the dedup.)
    groups: list[list[Path]] = []
    if out_root.exists():
        groups.append(sorted(p for p in out_root.iterdir()))
    archive = out_root / "Archive"
    if archive.exists():
        groups.append(sorted(p for p in archive.iterdir()))
    for d in (d for group in groups for d in group):
        if not d.is_dir() or d.name.startswith("_") or d.name == "Archive":
            continue
        if d.name in seen:
            continue   # prefer the first hit (outputs/ over Archive/)
        m = _SLUG_RE.match(d.name)
        if not m:
            continue
        sc = m["sc"]   # e.g. "245"
        scenario = f"SSP{sc[0]}-{sc[1]}.{sc[2]}"
        horizon = int(m["yr"])
        rest = m["rest"].lstrip("_")
        variant = rest if rest else "undefended"
        found.append(ScenarioDir(m["city"], scenario, horizon, variant, d))
        seen.add(d.name)
    return found


# ---------------------------------------------------------------------------
# Depth loading + RGBA assembly
# ---------------------------------------------------------------------------

def _load_depth(
    root: Path, hazard: str, scenario: str, horizon: int, rp: int,
    pluvial_floor: float = 0.05,
) -> np.ndarray | None:
    p = root / hazard / f"rp_{rp}" / f"{hazard}_depth_{scenario}_{horizon}_rp{rp}.tif"
    if not p.exists():
        return None
    with rasterio.open(p) as src:
        arr = src.read(1).astype(np.float32)
    arr[~np.isfinite(arr)] = 0.0
    arr[arr < 0] = 0.0
    if hazard == "pluvial" and pluvial_floor > 0:
        arr[arr < pluvial_floor] = 0.0
    return arr


def _load_land_mask(root: Path, scenario: str, horizon: int, rp: int) -> np.ndarray | None:
    p = root / "coastal" / f"rp_{rp}" / f"coastal_depth_{scenario}_{horizon}_rp{rp}.tif"
    if not p.exists():
        return None
    with rasterio.open(p) as src:
        return np.isfinite(src.read(1).astype(np.float32))


def _combined_rgba(depths: dict[str, np.ndarray], vmax: float) -> np.ndarray:
    rows, cols = next(iter(depths.values())).shape
    rgba = np.zeros((rows, cols, 4), dtype=np.float32)
    stacked = np.stack([depths[h] for h in HAZARD_CMAPS], axis=0)
    dominant = np.argmax(stacked, axis=0)
    max_depth = stacked.max(axis=0)
    for i, hazard in enumerate(HAZARD_CMAPS):
        cmap = plt.get_cmap(HAZARD_CMAPS[hazard])
        mask = (dominant == i) & (max_depth > 0)
        if not mask.any():
            continue
        nd = np.clip(max_depth[mask] / vmax, 0.0, 1.0)
        rgba[mask] = cmap(0.4 + 0.6 * nd)
    rgba[max_depth <= 0, 3] = 0.0
    return rgba, max_depth


def _render_panel(
    ax, root: Path, scenario: str, horizon: int, rp: int,
    vmax: float, pluvial_floor: float, title: str | None = None,
) -> tuple[bool, float]:
    """Render one (scenario, rp) panel onto ax. Returns (ok, wet_km2)."""
    depths = {}
    for h in HAZARD_CMAPS:
        d = _load_depth(root, h, scenario, horizon, rp, pluvial_floor)
        if d is None:
            ax.set_title((title or "") + "  (missing)", fontsize=8)
            ax.axis("off")
            return False, 0.0
        depths[h] = d
    rgba, max_depth = _combined_rgba(depths, vmax)
    land_mask = _load_land_mask(root, scenario, horizon, rp)
    if land_mask is not None:
        bg = np.zeros((*land_mask.shape, 4), dtype=np.float32)
        bg[land_mask] = [0.88, 0.88, 0.88, 1.0]
        ax.imshow(bg, interpolation="nearest")
    ax.imshow(rgba, interpolation="nearest")
    wet_km2 = float((max_depth > 0).sum()) * 30 * 30 / 1e6
    if title is not None:
        ax.set_title(f"{title}\n{wet_km2:.0f} km²", fontsize=9)
    ax.axis("off")
    return True, wet_km2


# ---------------------------------------------------------------------------
# Panel 1: 3x3 RP comparison (replaces per-RP individual PNGs)
# ---------------------------------------------------------------------------

def _panel_rp_comparison(scen: ScenarioDir, vmax: float, pluvial_floor: float,
                          out_dir: Path) -> Path | None:
    fig, axes = plt.subplots(3, 3, figsize=(13, 11), dpi=140)
    city = CITY_DISPLAY.get(scen.city, scen.city)
    variant_label = "Undefended" if scen.variant == "undefended" else scen.variant.replace("_", " ").title()
    fig.suptitle(
        f"{city} — {scen.scenario} / {scen.horizon} ({variant_label})\n"
        f"Multi-hazard flood depth; colour = dominant hazard; vmax = {vmax:.1f} m",
        fontsize=12, y=1.00,
    )
    rendered_any = False
    for idx, rp in enumerate(RETURN_PERIODS):
        ax = axes[idx // 3, idx % 3]
        ok, _ = _render_panel(ax, scen.path, scen.scenario, scen.horizon, rp,
                              vmax, pluvial_floor, title=f"RP {rp}")
        rendered_any = rendered_any or ok
    if not rendered_any:
        plt.close(fig)
        return None
    patches = [mpatches.Patch(color=HAZARD_COLOURS[h], label=h.title())
               for h in HAZARD_CMAPS]
    fig.legend(handles=patches, loc="lower center", ncol=3, fontsize=10,
               framealpha=0.9, bbox_to_anchor=(0.5, -0.01))
    out = out_dir / f"{scen.slug}.png"
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Panel 2: defended vs undefended (2x2: RP2/RP100 x undef/def)
# ---------------------------------------------------------------------------

def _panel_defended_vs_undefended(
    city: str, scenario: str, horizon: int, scen_dirs: list[ScenarioDir],
    headline_rps: list[int], vmax: float, pluvial_floor: float, out_dir: Path,
) -> Path | None:
    undef = next((s for s in scen_dirs
                  if s.city == city and s.scenario == scenario
                  and s.horizon == horizon and s.variant == "undefended"), None)
    defended = next((s for s in scen_dirs
                     if s.city == city and s.scenario == scenario
                     and s.horizon == horizon and s.variant == "defended"), None)
    if undef is None or defended is None:
        return None
    ncols = len(headline_rps)
    fig, axes = plt.subplots(2, ncols, figsize=(5.5 * ncols, 9), dpi=140)
    if ncols == 1:
        axes = axes.reshape(2, 1)
    city_disp = CITY_DISPLAY.get(city, city)
    fig.suptitle(
        f"{city_disp} — {scenario} / {horizon}: defended vs undefended\n"
        f"vmax = {vmax:.1f} m; colour = dominant hazard",
        fontsize=13, y=1.00,
    )
    rows = [("Undefended", undef), ("Defended", defended)]
    for ri, (label, sd) in enumerate(rows):
        for ci, rp in enumerate(headline_rps):
            ax = axes[ri, ci]
            _render_panel(ax, sd.path, scenario, horizon, rp,
                          vmax, pluvial_floor,
                          title=f"{label} — RP {rp}")
    patches = [mpatches.Patch(color=HAZARD_COLOURS[h], label=h.title())
               for h in HAZARD_CMAPS]
    fig.legend(handles=patches, loc="lower center", ncol=3, fontsize=10,
               framealpha=0.9, bbox_to_anchor=(0.5, -0.01))
    out = out_dir / f"{city}_{undef.scen_slug}.png"
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Panel 3: suite overview (5 cities x N RPs at one scenario)
# ---------------------------------------------------------------------------

def _panel_suite_overview(
    scenario: str, horizon: int, rp: int,
    scen_dirs: list[ScenarioDir], variant: str,
    vmax: float, pluvial_floor: float, out_dir: Path,
) -> Path | None:
    cities_found = []
    for c in SUITE_CITIES:
        sd = next((s for s in scen_dirs
                   if s.city == c and s.scenario == scenario
                   and s.horizon == horizon and s.variant == variant), None)
        if sd is not None:
            cities_found.append((c, sd))
    if not cities_found:
        return None
    n = len(cities_found)
    fig, axes = plt.subplots(1, n, figsize=(4.5 * n, 5.2), dpi=140)
    if n == 1:
        axes = [axes]
    fig.suptitle(
        f"Coastal city suite — {scenario} / {horizon}, RP {rp}, {variant} DEM\n"
        f"vmax = {vmax:.1f} m; colour = dominant hazard",
        fontsize=13, y=1.02,
    )
    for ax, (city, sd) in zip(axes, cities_found):
        _render_panel(ax, sd.path, scenario, horizon, rp,
                      vmax, pluvial_floor, title=CITY_DISPLAY.get(city, city))
    patches = [mpatches.Patch(color=HAZARD_COLOURS[h], label=h.title())
               for h in HAZARD_CMAPS]
    fig.legend(handles=patches, loc="lower center", ncol=3, fontsize=10,
               framealpha=0.9, bbox_to_anchor=(0.5, -0.04))
    sc_slug = scenario.lower().replace("-", "").replace(".", "")
    out = out_dir / f"suite_{variant}_{sc_slug}_{horizon}_rp{rp}.png"
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Panel 4: scenario progression (2x2 climate grid per city x RP x variant)
# ---------------------------------------------------------------------------

def _panel_scenario_progression(
    city: str, rp: int, variant: str,
    scen_dirs: list[ScenarioDir],
    vmax: float, pluvial_floor: float, out_dir: Path,
) -> Path | None:
    matches = {}
    for sce, hor, _ in SCENARIOS:
        sd = next((s for s in scen_dirs
                   if s.city == city and s.scenario == sce
                   and s.horizon == hor and s.variant == variant), None)
        if sd is not None:
            matches[(sce, hor)] = sd
    if not matches:
        return None
    fig, axes = plt.subplots(2, 2, figsize=(11, 10), dpi=140)
    city_disp = CITY_DISPLAY.get(city, city)
    fig.suptitle(
        f"{city_disp} — RP {rp} climate progression ({variant} DEM)\n"
        f"vmax = {vmax:.1f} m; colour = dominant hazard",
        fontsize=13, y=1.00,
    )
    layout = [("SSP2-4.5", 2050, (0, 0)), ("SSP5-8.5", 2050, (0, 1)),
              ("SSP2-4.5", 2100, (1, 0)), ("SSP5-8.5", 2100, (1, 1))]
    for sce, hor, (r, c) in layout:
        ax = axes[r, c]
        sd = matches.get((sce, hor))
        if sd is None:
            ax.set_title(f"{sce} / {hor}  (missing)", fontsize=9)
            ax.axis("off")
            continue
        _render_panel(ax, sd.path, sce, hor, rp,
                      vmax, pluvial_floor, title=f"{sce} / {hor}")
    patches = [mpatches.Patch(color=HAZARD_COLOURS[h], label=h.title())
               for h in HAZARD_CMAPS]
    fig.legend(handles=patches, loc="lower center", ncol=3, fontsize=10,
               framealpha=0.9, bbox_to_anchor=(0.5, -0.01))
    out = out_dir / f"{city}_rp{rp}_{variant}.png"
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# INDEX.md
# ---------------------------------------------------------------------------

def _write_index(out_root: Path, viz_root: Path) -> None:
    md = ["# Visualisation Suite Index",
          "",
          f"Generated by `scripts/build_viz_suite.py` from outputs under `{out_root}`.",
          "",
          "## Layout",
          "",
          "- **01_rp_comparison/** — single 3×3 panel per (city, scenario, horizon, variant) showing all 9 return periods.",
          "- **02_defended_vs_undefended/** — 2-row × N-RP-column comparison per scenario (top: undefended; bottom: defended).",
          "- **03_suite_overview/** — five coastal cities side by side per (RP, scenario, horizon, variant).",
          "- **04_scenario_progression/** — 2×2 climate grid per (city, RP, variant): SSP2-4.5 ↔ SSP5-8.5 across 2050 ↔ 2100.",
          "",
          "Pluvial cells with depth below 0.05 m are suppressed (hides the 0.005 m drain-capacity floor that paints every spurious DEM micro-depression).",
          ""]
    for sub in ("01_rp_comparison", "02_defended_vs_undefended",
                "03_suite_overview", "04_scenario_progression"):
        d = viz_root / sub
        if not d.exists():
            continue
        files = sorted(p.name for p in d.glob("*.png"))
        if not files:
            continue
        md.append(f"## {sub}")
        md.append("")
        for f in files:
            md.append(f"- [{f}]({sub}/{f})")
        md.append("")
    (viz_root / "INDEX.md").write_text("\n".join(md), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _discover(ctx) -> list[ScenarioDir]:
    """discover_scenarios(), restricted to ctx.obj['cities'] when set.

    The ``--cities`` filter lets a single city be rebuilt in isolation —
    e.g. after a sea-mask fix re-run for Manila — without regenerating
    (or pulling stale Archive data into) every other city's panels.
    """
    scen_dirs = discover_scenarios(ctx.obj["out_root"])
    cities = ctx.obj.get("cities")
    if cities:
        scen_dirs = [sd for sd in scen_dirs if sd.city in cities]
    return scen_dirs


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.option("--out-root", type=click.Path(path_type=Path),
              default=Path("outputs"), show_default=True)
@click.option("--vmax", type=float, default=1.5, show_default=True,
              help="Depth scale maximum (m) shared across panels.")
@click.option("--pluvial-floor", type=float, default=0.05, show_default=True,
              help="Suppress pluvial cells with depth below this value (m).")
@click.option("--headline-rps", default="2,100", show_default=True,
              help="Comma-separated RPs for defended-vs-undefended panels.")
@click.option("--cities", default="", show_default=False,
              help="Comma-separated city slugs to restrict the build to "
                   "(e.g. 'manila' or 'manila,hcmc'). Empty = all "
                   "discovered cities.")
@click.pass_context
def cli(ctx, out_root: Path, vmax: float, pluvial_floor: float,
        headline_rps: str, cities: str):
    ctx.ensure_object(dict)
    ctx.obj["out_root"] = out_root
    ctx.obj["vmax"] = vmax
    ctx.obj["pluvial_floor"] = pluvial_floor
    ctx.obj["headline_rps"] = [int(x) for x in headline_rps.split(",")]
    ctx.obj["cities"] = {c.strip() for c in cities.split(",") if c.strip()}
    ctx.obj["viz_root"] = out_root / "_viz"


@cli.command("rp-comparison")
@click.pass_context
def rp_comparison_cmd(ctx):
    """Generate 3x3 RP-comparison panels for every (city, scenario, variant)."""
    out_dir = ctx.obj["viz_root"] / "01_rp_comparison"
    scen_dirs = _discover(ctx)
    n = 0
    for sd in scen_dirs:
        p = _panel_rp_comparison(sd, ctx.obj["vmax"], ctx.obj["pluvial_floor"], out_dir)
        if p is not None:
            click.echo(f"  wrote {p.relative_to(ctx.obj['out_root'])}")
            n += 1
    click.echo(f"[rp-comparison] {n} panels written to {out_dir}")


@cli.command("defended-vs-undefended")
@click.pass_context
def defended_vs_undefended_cmd(ctx):
    """Generate defended-vs-undefended side-by-side panels per scenario."""
    out_dir = ctx.obj["viz_root"] / "02_defended_vs_undefended"
    scen_dirs = _discover(ctx)
    cities = sorted({sd.city for sd in scen_dirs if sd.variant == "defended"})
    headline_rps = ctx.obj["headline_rps"]
    n = 0
    for city in cities:
        for sce, hor, _ in SCENARIOS:
            p = _panel_defended_vs_undefended(
                city, sce, hor, scen_dirs, headline_rps,
                ctx.obj["vmax"], ctx.obj["pluvial_floor"], out_dir,
            )
            if p is not None:
                click.echo(f"  wrote {p.relative_to(ctx.obj['out_root'])}")
                n += 1
    click.echo(f"[defended-vs-undefended] {n} panels written to {out_dir}")


@cli.command("suite-overview")
@click.pass_context
def suite_overview_cmd(ctx):
    """Generate 5-city suite-overview panels per (RP, scenario, variant)."""
    out_dir = ctx.obj["viz_root"] / "03_suite_overview"
    scen_dirs = _discover(ctx)
    n = 0
    for variant in ("undefended", "defended"):
        for rp in ctx.obj["headline_rps"]:
            for sce, hor, _ in SCENARIOS:
                p = _panel_suite_overview(
                    sce, hor, rp, scen_dirs, variant,
                    ctx.obj["vmax"], ctx.obj["pluvial_floor"], out_dir,
                )
                if p is not None:
                    click.echo(f"  wrote {p.relative_to(ctx.obj['out_root'])}")
                    n += 1
    click.echo(f"[suite-overview] {n} panels written to {out_dir}")


@cli.command("scenario-progression")
@click.pass_context
def scenario_progression_cmd(ctx):
    """Generate 2x2 climate-grid panels per (city, RP, variant)."""
    out_dir = ctx.obj["viz_root"] / "04_scenario_progression"
    scen_dirs = _discover(ctx)
    cities = sorted({sd.city for sd in scen_dirs})
    n = 0
    for city in cities:
        for variant in ("undefended", "defended"):
            for rp in ctx.obj["headline_rps"]:
                p = _panel_scenario_progression(
                    city, rp, variant, scen_dirs,
                    ctx.obj["vmax"], ctx.obj["pluvial_floor"], out_dir,
                )
                if p is not None:
                    click.echo(f"  wrote {p.relative_to(ctx.obj['out_root'])}")
                    n += 1
    click.echo(f"[scenario-progression] {n} panels written to {out_dir}")


@cli.command("index")
@click.pass_context
def index_cmd(ctx):
    """Regenerate INDEX.md inside outputs/_viz/."""
    _write_index(ctx.obj["out_root"], ctx.obj["viz_root"])
    click.echo(f"[index] wrote {ctx.obj['viz_root'] / 'INDEX.md'}")


@cli.command("all")
@click.pass_context
def all_cmd(ctx):
    """Regenerate every panel type + index."""
    ctx.invoke(rp_comparison_cmd)
    ctx.invoke(defended_vs_undefended_cmd)
    ctx.invoke(suite_overview_cmd)
    ctx.invoke(scenario_progression_cmd)
    ctx.invoke(index_cmd)


if __name__ == "__main__":
    cli(obj={})
