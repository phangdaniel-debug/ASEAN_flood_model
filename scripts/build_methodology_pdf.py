"""
Generate METHODOLOGY.pdf from the methodology content.
Uses ReportLab for full control over layout, tables, and image embedding.

Usage:
    python scripts/build_methodology_pdf.py
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image as PILImage

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable, Image, KeepTogether, PageBreak,
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR   = PROJECT_ROOT / "outputs" / "singapore_ssp585_2100"

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
NAVY    = colors.HexColor("#1a3a5c")
BLUE    = colors.HexColor("#2166ac")
STEEL   = colors.HexColor("#4a90d9")
ROW_ALT = colors.HexColor("#eef3f8")
BORDER  = colors.HexColor("#b0bec5")
CODEBG  = colors.HexColor("#f5f5f5")
CODEFG  = colors.HexColor("#1a1a1a")
NOTEBLUE= colors.HexColor("#ddeeff")

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
BASE = getSampleStyleSheet()

def _ps(name, **kw):
    parent = kw.pop("parent", BASE["Normal"])
    return ParagraphStyle(name, parent=parent, **kw)

TITLE    = _ps("Title",    fontSize=20, leading=26, spaceAfter=4,  textColor=NAVY,  alignment=TA_CENTER, fontName="Helvetica-Bold")
SUBTITLE = _ps("Subtitle", fontSize=11, leading=14, spaceAfter=16, textColor=colors.HexColor("#555"), alignment=TA_CENTER)
H1       = _ps("H1",  fontSize=13, leading=17, spaceBefore=20, spaceAfter=5,  textColor=NAVY,  fontName="Helvetica-Bold")
H2       = _ps("H2",  fontSize=11, leading=14, spaceBefore=12, spaceAfter=4,  textColor=BLUE,  fontName="Helvetica-Bold")
H3       = _ps("H3",  fontSize=9.5,leading=13, spaceBefore=8,  spaceAfter=3,  textColor=colors.HexColor("#333"), fontName="Helvetica-BoldOblique")
BODY     = _ps("Body", fontSize=9.5, leading=14, spaceAfter=5, alignment=TA_JUSTIFY)
BODYS    = _ps("BodyS", fontSize=8.5, leading=12, spaceAfter=4, alignment=TA_JUSTIFY)
BULLET   = _ps("Bullet", fontSize=9.5, leading=13, leftIndent=14, firstLineIndent=-10, spaceAfter=3)
BULLETS  = _ps("BulletS", fontSize=8.5, leading=12, leftIndent=14, firstLineIndent=-10, spaceAfter=2)
CODE     = _ps("Code", fontSize=8, leading=11, fontName="Courier",
               backColor=CODEBG, borderColor=BORDER, borderWidth=0.5,
               borderPad=6, spaceBefore=4, spaceAfter=6, leftIndent=6)
CAPTION  = _ps("Caption", fontSize=7.5, leading=10.5, textColor=colors.HexColor("#555"),
               alignment=TA_CENTER, spaceAfter=10, spaceBefore=2)
NOTE     = _ps("Note", fontSize=8.5, leading=12, backColor=NOTEBLUE,
               borderColor=STEEL, borderWidth=0.5, borderPad=6,
               spaceBefore=4, spaceAfter=6, leftIndent=6)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PAGE_W = A4[0] - 4.0*cm   # usable text width

def hr():
    return HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=3, spaceBefore=3)

def sp(h=0.3):
    return Spacer(1, h*cm)

def b(t): return f"<b>{t}</b>"
def i(t): return f"<i>{t}</i>"
def code_inline(t): return f"<font face='Courier' size='8'>{t}</font>"

def P(text, style=BODY):
    return Paragraph(text, style)

def make_table(data, col_widths=None, first_col_bold=False):
    if col_widths is None:
        n = len(data[0])
        col_widths = [PAGE_W / n] * n

    TH = _ps("TH", fontSize=8.5, leading=11, fontName="Helvetica-Bold",
              textColor=colors.white)
    TD = _ps("TD", fontSize=8.5, leading=11)
    TD_BOLD = _ps("TDB", fontSize=8.5, leading=11, fontName="Helvetica-Bold")

    wrapped = []
    for ri, row in enumerate(data):
        wrow = []
        for ci, cell in enumerate(row):
            if ri == 0:
                wrow.append(Paragraph(str(cell), TH))
            elif first_col_bold and ci == 0:
                wrow.append(Paragraph(str(cell), TD_BOLD))
            else:
                wrow.append(Paragraph(str(cell), TD))
        wrapped.append(wrow)

    t = Table(wrapped, colWidths=col_widths, repeatRows=1)
    cmds = [
        ("BACKGROUND",    (0,0),  (-1,0),  NAVY),
        ("TEXTCOLOR",     (0,0),  (-1,0),  colors.white),
        ("ROWBACKGROUNDS",(0,1),  (-1,-1), [colors.white, ROW_ALT]),
        ("GRID",          (0,0),  (-1,-1), 0.35, BORDER),
        ("TOPPADDING",    (0,0),  (-1,-1), 4),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 4),
        ("LEFTPADDING",   (0,0),  (-1,-1), 5),
        ("RIGHTPADDING",  (0,0),  (-1,-1), 5),
        ("VALIGN",        (0,0),  (-1,-1), "TOP"),
    ]
    t.setStyle(TableStyle(cmds))
    return t

def img_elem(path, width_cm=15.0, caption=""):
    p = Path(path)
    if not p.exists():
        return [P(f"[Image not found: {p.name}]", CAPTION)]
    pil = PILImage.open(str(p))
    ratio = pil.size[1] / pil.size[0]
    w = width_cm * cm
    elems = [Image(str(p), width=w, height=w*ratio)]
    if caption:
        elems.append(P(caption, CAPTION))
    return elems

def section_divider(title):
    """Full-width section title with coloured background."""
    style = _ps("SecDiv", fontSize=12, leading=16, fontName="Helvetica-Bold",
                textColor=colors.white, backColor=NAVY, borderPad=6,
                spaceBefore=14, spaceAfter=2)
    return [Paragraph(title, style)]

# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------
def build():
    out = PROJECT_ROOT / "METHODOLOGY.pdf"
    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=2.0*cm, rightMargin=2.0*cm,
        topMargin=2.2*cm,  bottomMargin=2.2*cm,
        title="Singapore Flood Depth Model - Methodology",
        author="Singapore Flood Pipeline",
    )

    S = []   # story

    # ===================================================================
    # COVER
    # ===================================================================
    S += [
        sp(1.0),
        P("Singapore Flood Depth Model", TITLE),
        P("Methodology &amp; Technical Reference", SUBTITLE),
        P("Scenario: SSP5-8.5  |  Horizon: 2100  |  April 2026", SUBTITLE),
        hr(), sp(0.3),
        P("This document describes the data sources, statistical methods, physical models, "
          "and design decisions behind the Singapore multi-hazard flood screening pipeline. "
          "It covers three hazard types (coastal, fluvial, pluvial) across nine return periods "
          "(RP2 to RP1000) and provides justification for each modelling choice.", BODY),
        sp(0.5),
    ]

    # ===================================================================
    # 1. PIPELINE OVERVIEW
    # ===================================================================
    S += section_divider("1. Pipeline Overview")
    S += [
        sp(0.2),
        P("The pipeline executes the following sequential steps:", BODY),
        P("""Terrain data (DEM)
  |
Baseline flood levels (GEV / Gumbel fit to ERA5 and tide gauge)
  |
Climate scenario adjustment (AR6 sea-level delta; Clausius-Clapeyron)
  |
Sea mask (BFS flood-fill)
  |
Flood depth computation:
  - Coastal   : 2D Local Inertia solver + surge hydrograph BC
  - Fluvial   : HAND + bankfull subtraction (RP10 threshold)
  - Pluvial   : Depression-filling ponding model
  |
Severity classification (5 classes)
  |
Multi-hazard combined maps""", CODE),
        sp(0.3),
    ]

    # ===================================================================
    # 2. TERRAIN DATA
    # ===================================================================
    S += section_divider("2. Terrain Data (Copernicus DEM GLO-30)")
    S += [
        sp(0.2),
        P("The Copernicus DEM GLO-30 (TanDEM-X radar mission, ~2011-2015) provides global "
          "coverage at ~30 m nominal resolution referenced to the EGM2008 geoid "
          "(a global approximation of mean sea level). It is downloaded automatically via the "
          "Microsoft Planetary Computer STAC API for the Singapore bounding box "
          "(103.57-104.10 deg E, 1.15-1.50 deg N) and reprojected to UTM Zone 48N (EPSG:32648).", BODY),

        P("Reprojection to a projected CRS is mandatory: geographic coordinates in degrees "
          "cannot be used to compute pixel areas or distances in metres. EGM2008 vertical "
          "datum alignment with the IPCC AR6 sea-level projections requires no datum "
          "conversion, which is a key practical advantage.", BODY),
        sp(0.2),
        make_table([
            ["Parameter", "Value", "Reason"],
            ["Resolution", "30 m", "Matches native DEM; finer resampling adds no real information"],
            ["Projected CRS", "EPSG:32648 (UTM 48N)", "Required for metre-based area and distance calculations"],
            ["Resampling", "Bilinear", "Smooth interpolation for continuous elevation surface"],
            ["Vertical datum", "EGM2008", "Aligns directly with AR6 sea-level projections; no datum conversion needed"],
        ], col_widths=[3.5*cm, 4.0*cm, 9.0*cm]),
        sp(0.3),

        P(b("Singapore terrain profile"), H3),
        P("Only 3.9-4.5% of Singapore's land (44-52 km2) sits below the coastal surge levels "
          "of 2.27-2.68 m. The P10 elevation of 4.3 m means 90% of land is above 4.3 m. "
          "The thin coastal flooding fringe seen on the output maps reflects this terrain "
          "reality, not a model limitation.", BODY),
        make_table([
            ["Percentile", "Land elevation (m)", "Notes"],
            ["P1",  "0.5",  "Lowest coastal fringe"],
            ["P5",  "2.9",  "Just above RP2 surge level (2.27 m)"],
            ["P10", "4.3",  "90% of land is above this"],
            ["P25", "7.3",  "Lower quarter of terrain"],
            ["P50", "13.9", "Median -- well above all surge levels"],
            ["P75", "23.3", "Upper quarter"],
            ["P90", "34.6", "High interior hills"],
        ], col_widths=[2.5*cm, 4.5*cm, 9.5*cm]),
        sp(0.4),
    ]

    # elevation map
    S += img_elem(OUTPUT_DIR/"singapore_elevation_map.png", width_cm=15.5,
        caption="Figure 1. Singapore DEM elevation. Yellow = below 2.27 m (inundatable at RP2). "
                "Orange = 2.27-4 m (low-lying). Green onwards = above 4 m. "
                "Red contour = 2.27 m RP2 coastal surge level. "
                "Only the thin coastal fringe is below modelled surge levels.")
    S.append(PageBreak())

    # ===================================================================
    # 3. BASELINE FLOOD LEVELS
    # ===================================================================
    S += section_divider("3. Present-Day Flood Levels (Baseline)")
    S += [
        sp(0.2),
        P("3.1  Extreme Value Theory: GEV and Gumbel Distributions", H2),
        P("All three hazard baselines are derived by fitting a "
          + b("Generalised Extreme Value (GEV)") + " distribution to annual maxima series. "
          "The theoretical foundation is the "
          + b("Fisher-Tippett-Gnedenko theorem") + ": regardless of the underlying distribution "
          "of the original observations, the distribution of block maxima (one maximum per year) "
          "converges to the GEV family as the block size grows. This provides a rigorous "
          "asymptotic justification for using GEV without assuming a specific distribution "
          "for the underlying process.", BODY),

        P("GEV cumulative distribution function:", H3),
        P("F(x; mu, sigma, xi) = exp{ -[1 + xi*(x-mu)/sigma]^(-1/xi) }", CODE),
        make_table([
            ["Parameter", "Symbol", "Physical meaning"],
            ["Location", "mu",    "Roughly the median of annual maxima (m or mm)"],
            ["Scale",    "sigma", "Spread of annual maxima; sigma > 0 (same units as mu)"],
            ["Shape",    "xi",    "Tail behaviour; determines which extreme-value type applies"],
        ], col_widths=[3.0*cm, 2.5*cm, 11.0*cm]),
        sp(0.2),
        P("The shape parameter determines the tail behaviour:", H3),
        make_table([
            ["Shape xi", "Distribution type", "Tail", "Physical example"],
            ["xi = 0", "Gumbel (Type I)",   "Exponential -- no heavy tail", "Rainfall maxima, temperature extremes"],
            ["xi > 0", "Frechet (Type II)", "Power-law -- unbounded heavy tail", "Wind speeds, flood flows in some regions"],
            ["xi < 0", "Weibull (Type III)","Bounded upper tail -- finite maximum", "Sea surges in sheltered locations"],
        ], col_widths=[2.5*cm, 4.0*cm, 4.5*cm, 5.5*cm]),
        sp(0.2),
        P("Return level (the value exceeded with probability 1/T in any year):", H3),
        P("x_T = mu - (sigma/xi)*[1 - (-ln(1-1/T))^(-xi)]    for xi != 0\n"
          "x_T = mu - sigma * ln(-ln(1-1/T))                   for xi = 0 (Gumbel)", CODE),
        P(b("Fitting method:") + " Maximum Likelihood Estimation (MLE) via "
          + code_inline("scipy.stats.genextreme.fit()") +
          ". MLE maximises the probability of observing the actual data sample given the "
          "GEV parameters, and is asymptotically efficient for large samples. "
          "The annual maxima block approach is preferred over Peaks-Over-Threshold for "
          "transparency: no threshold selection or declustering decisions are required, "
          "and the asymptotic justification is exact for annual maxima.", BODY),
        sp(0.3),
    ]

    S += [
        P("3.2  Coastal Baseline -- Tide Gauge GEV", H2),
        P(b("Source:") + " UHSLC Research Quality tide gauge, Tanjong Pagar, Singapore "
          "(station 699), hourly sea levels 1984-2023 (39 years).", BODY),
        P(b("Processing steps:"), H3),
        P("1. " + b("De-tiding:") + " Remove the astronomical tidal signal using harmonic "
          "analysis (T_TIDE). What remains is the storm surge residual -- the sea level "
          "anomaly driven by atmospheric pressure (inverted barometer) and wind stress. "
          "This isolates the meteorologically-driven component, which is what climate "
          "change affects and what GEV statistics should describe.", BULLET),
        P("2. " + b("Annual maxima:") + " Extract the single highest hourly surge residual "
          "per calendar year (39 values).", BULLET),
        P("3. " + b("GEV MLE fit."), BULLET),
        sp(0.1),
        make_table([
            ["Fitted parameter", "Value", "Physical interpretation"],
            ["Shape xi",    "-0.08", "Weibull-type: bounded upper tail. Physically correct for "
                                     "Singapore, which is sheltered from typhoons in the Strait of Malacca. "
                                     "Surge events are driven by modest pressure systems with a finite upper bound."],
            ["Location mu", "1.57 m","Median annual surge level"],
            ["Scale sigma", "0.083 m","Very small spread -- Singapore has low inter-annual surge variability"],
        ], col_widths=[3.5*cm, 2.5*cm, 10.5*cm]),
        sp(0.3),
    ]

    S += [
        P("3.3  Fluvial Baseline -- ERA5 Precipitation to Channel Stage", H2),
        P("No freely available multi-decade river flow records exist for Singapore. "
          "The baseline is derived through a chain of hydrological transformations "
          "applied to ERA5 reanalysis precipitation (1950-2024, Open-Meteo API).", BODY),
        P(b("Step 1: 24h rolling accumulation"), H3),
        P("The 24-hour duration captures total rainfall volume driving flood peaks in "
          "Singapore's 10-50 km2 urban catchments (response time 3-12 hours). "
          "Annual maxima of the 24h rolling sum are extracted for GEV fitting.", BODY),
        P(b("Step 2: GEV fit to 74 annual maxima"), H3),
        make_table([
            ["Fitted parameter", "Value", "Physical interpretation"],
            ["Shape xi",     "+0.05", "Slightly Frechet-type: heavier tail than Gumbel. "
                                      "Reflects Singapore's occasional extreme 24h events "
                                      "(Sumatra squalls, slow convective clusters) that "
                                      "exceed what Gumbel would predict."],
            ["Location mu",  "129 mm","Typical annual maximum 24h accumulation"],
            ["Scale sigma",  "30 mm", "Moderate inter-annual variability"],
        ], col_widths=[3.5*cm, 2.5*cm, 10.5*cm]),
        sp(0.2),
        P(b("Step 3: SCS Curve Number runoff conversion"), H3),
        P("Q = (P - Ia)^2 / (P - Ia + S)  where  S = (25400/CN) - 254,  Ia = 0.2*S", CODE),
        P("CN = 85 (dense urban Singapore: predominantly impervious surfaces, connected drains). "
          "This gives potential retention S = 44.8 mm and initial abstraction Ia = 9.0 mm. "
          "For a 200 mm design rainfall, runoff Q = 172 mm (86% runoff ratio). "
          + b("Why SCS-CN:") + " One-parameter model requiring only land use classification; "
          "more complex infiltration models require soil hydraulic data not publicly available "
          "for Singapore.", BODY),
        P(b("Step 4: Triangular unit hydrograph -- peak discharge"), H3),
        P("Q_peak_m3s = Q_mm * A_km2 * 0.2778 / T_lag_h", CODE),
        P("The triangular unit hydrograph converts runoff depth to a peak discharge hydrograph "
          "using the catchment lag time T_lag (estimated from catchment geometry) and area A. "
          "This is a standard simplified approach in urban hydrology.", BODY),
        P(b("Step 5: Manning's equation -- stage from discharge"), H3),
        P("d = [ Q * n / (W * S^0.5) ]^(3/5)\n"
          "n = 0.04 (concrete-lined channel),  W = 10 m,  S = 0.002", CODE),
        P("Manning's equation is the fundamental equation of steady uniform open-channel flow. "
          "It converts peak discharge to flow depth for a channel of given geometry and roughness. "
          "The representative parameters (n, W, S) approximate Singapore's primary drainage "
          "network; uncertainty in these values is partially absorbed by the bankfull subtraction "
          "applied in the HAND model (Step 7.2).", BODY),
        sp(0.3),
    ]

    S += [
        P("3.4  Pluvial Baseline -- ERA5 Precipitation to Ponding Depth", H2),
        P(b("Why 6-hour duration:") + " Singapore's PUB designs primary drains using the 6-hour "
          "design storm (consistent with MSS intensity-duration-frequency guidance). "
          "Flash flooding typically develops within 1-3 hours of intense rainfall, making "
          "the 6-hour window the appropriate design duration for surface ponding. "
          "The 24-hour window used for fluvial captures different physics: "
          "catchment-scale runoff accumulation vs. local drainage overload.", BODY),
        P(b("Gumbel distribution (xi = 0):"), H3),
        P("F(x) = exp{ -exp[-(x-mu)/sigma] }\n"
          "x_T  = mu - sigma * ln(-ln(1-1/T))\n\n"
          "Fitted: mu = 66 mm,  sigma = 19.5 mm", CODE),
        P("The zero shape parameter identifies a Gumbel (Type I) distribution. "
          "This is physically plausible for Singapore's convective 6h rainfall: the generating "
          "mechanism (tropical convective cells) produces a relatively symmetric distribution "
          "of annual maxima without the heavy tail seen at 24h accumulations. "
          "The Gumbel is analytically simple, widely used for tropical rainfall frequency "
          "analysis, and is a special case of the GEV consistent with the MLE fit.", BODY),
        P(b("Drain capacity threshold:"), H3),
        P("Singapore's PUB primary drainage network is designed to convey 100 mm/6h "
          "(the RP10 design standard) without surface flooding. Only excess above this "
          "threshold causes spatially significant surface ponding:", BODY),
        P("excess_mm = max(0,  design_mm - 100)\n"
          "ponding_m = excess_mm * 0.75 / 100\n\n"
          "Runoff coefficient 0.75: 75% of excess rainfall ponds (25% infiltrates)\n"
          "/100 divisor: converts mm excess to effective ponding depth over 30m grid cell,\n"
          "reflecting concentration into depressions rather than uniform spreading", CODE),
        P(b("RP2 and RP5 correctly produce zero ponding") + " -- these events are within "
          "drain capacity. This is a physical constraint, not a model artefact.", BODY),
        make_table([
            ["Return period", "Design rainfall (mm/6h)", "Excess above 100 mm", "Ponding level (m)"],
            ["RP2, RP5",  "< 100", "0",    "0.000"],
            ["RP10",      "~113",  "~13",  "0.095"],
            ["RP25",      "~152",  "~52",  "0.272"],
            ["RP100",     "~194",  "~94",  "0.535"],
            ["RP1000",    "~253",  "~153", "0.967"],
        ], col_widths=[3.0*cm, 5.5*cm, 4.5*cm, 4.0*cm]),
        sp(0.3),
    ]
    S.append(PageBreak())

    # ===================================================================
    # 4. CLIMATE ADJUSTMENT
    # ===================================================================
    S += section_divider("4. Climate Scenario Adjustment")
    S += [
        sp(0.2),
        P("4.1  Coastal -- IPCC AR6 Sea-Level Projections", H2),
        P("Sea-level rise arises from thermal expansion of warming ocean water, "
          "mass loss from glaciers and ice sheets, and changes in terrestrial water storage. "
          "The IPCC AR6 WGI Chapter 9 sea-level projections (Rutgers University Zarr store) "
          "provide thousands of Monte Carlo samples of total sea-level change at the "
          "Singapore tide gauge for each SSP scenario.", BODY),
        P("delta_i = SLC(target_year)_i - SLC(baseline_year=2020)_i\n"
          "Reported delta = percentile_p(delta_i across all samples)", CODE),
        P(b("Why per-sample delta before aggregating:") + " Subtracting the median of the 2100 "
          "distribution from the median of the 2020 distribution independently overstates "
          "uncertainty because it ignores intra-sample correlation -- samples showing "
          "high sea level in 2100 also show higher-than-median sea level in 2020. "
          "Per-sample differencing preserves this correlation and gives a physically correct "
          "uncertainty distribution.", BODY),
        make_table([
            ["Scenario", "Horizon", "Sea-level delta (m)", "RP2 future level (m)", "RP1000 future level (m)"],
            ["SSP2-4.5", "2050", "+0.24", "1.84", "2.24"],
            ["SSP2-4.5", "2100", "+0.44", "2.04", "2.44"],
            ["SSP5-8.5", "2050", "+0.31", "1.91", "2.31"],
            ["SSP5-8.5", "2100", "+0.67", "2.27", "2.68"],
        ], col_widths=[3.0*cm, 2.5*cm, 4.0*cm, 4.5*cm, 4.5*cm]),
        sp(0.3),
        P("4.2  Fluvial and Pluvial -- Clausius-Clapeyron Scaling", H2),
        P("The Clausius-Clapeyron relation governs atmospheric moisture capacity: "
          "for every 1 deg C of warming, the atmosphere holds ~7% more water vapour. "
          "Because precipitation extremes are constrained by atmospheric moisture, "
          "rainfall intensities scale approximately at 7%/deg C -- "
          "a well-established result from observations, theory, and climate models. "
          "(Some tropical studies find 10-15%/deg C for the most intense events, "
          "making the 7% rate a conservative lower bound.)", BODY),
        P("mu_future  = mu  * (1 + 0.07 * deltaT)\n"
          "sigma_future = sigma * (1 + 0.07 * deltaT)\n"
          "xi unchanged  (tail shape not significantly altered by warming)\n\n"
          "precip_factor(T) = GEV_quantile(1-1/T; mu_fut, sigma_fut, xi)\n"
          "                 / GEV_quantile(1-1/T; mu,     sigma,     xi)\n\n"
          "Fluvial stage factor: precip_factor(T)^0.6   [Manning: d ~ Q^(3/5)]\n"
          "Pluvial ponding factor: precip_factor(T)^1.0  [linear in excess rainfall]", CODE),
        P("Scaling both mu and sigma by the same factor preserves the coefficient of "
          "variation (sigma/mu), consistent with observations that the whole distribution "
          "shifts proportionally. For xi > 0 (fluvial, Frechet tail), rarer events "
          "intensify more than common ones -- reproducing the 'super-CC' behaviour "
          "observed in tropical extreme rainfall extremes.", BODY),
        make_table([
            ["Scenario", "Horizon", "deltaT (C)", "CC factor", "Fluvial stage factor", "Pluvial factor"],
            ["SSP2-4.5", "2050", "+1.0", "1.07", "~1.04", "1.07"],
            ["SSP2-4.5", "2100", "+2.1", "1.15", "~1.09", "1.15"],
            ["SSP5-8.5", "2050", "+1.5", "1.11", "~1.06", "1.11"],
            ["SSP5-8.5", "2100", "+4.0", "1.28", "~1.16", "1.28"],
        ], col_widths=[3.0*cm, 2.5*cm, 2.5*cm, 2.5*cm, 4.5*cm, 3.0*cm]),
        sp(0.3),
    ]
    S.append(PageBreak())

    # ===================================================================
    # 5. FLOOD DEPTH MODELS
    # ===================================================================
    S += section_divider("5.  Flood Depth Computation")
    S += [sp(0.2)]

    # --- 5a COASTAL INERTIA ---
    S += [
        P("5.1  Coastal: 2D Local Inertia Solver", H2),
        P(b("Full shallow-water equations (SWE):"), H3),
        P("Continuity:   dh/dt + d(hu)/dx + d(hv)/dy = 0\n"
          "x-momentum:   d(hu)/dt + d(hu^2)/dx + d(huv)/dy\n"
          "              = -g*h*d(z+h)/dx - g*n^2*u*|v|/h^(1/3)\n"
          "(analogous for y-momentum)\n\n"
          "h = water depth, u,v = depth-averaged velocities,\n"
          "z = bed elevation, n = Manning's roughness, g = 9.806 m/s2", CODE),

        P(b("Why the Local Inertia approximation:"), H3),
        P("The nonlinear advection terms d(hu2)/dx and d(huv)/dy represent momentum "
          "carried by the flow itself. For slowly-propagating flood waves at low Froude "
          "numbers (Fr = v/sqrt(gh) << 1), these terms are an order of magnitude smaller "
          "than the pressure gradient and friction terms. Dropping them gives the "
          + b("Local Inertia (LI) model") + " (Bates, Horritt &amp; Fewtrell, 2010):", BODY),
        P("x-momentum:   d(hu)/dt = -g*h*d(eta)/dx - g*n^2*u*|v|/h^(1/3)\n\n"
          "where eta = z + h (water-surface elevation)", CODE),
        P("The LI model retains the inertial acceleration term d(hu)/dt, "
          "giving more realistic wave propagation than the purely kinematic approximation, "
          "while remaining computationally tractable. Validity condition: Fr < ~0.5, "
          "which holds throughout Singapore's low-gradient urban floodplain (typical Fr 0.01-0.3 "
          "during surge). This is the same model used in LISFLOOD-FP, "
          "the leading research-grade 2D flood model, for urban coastal applications.", BODY),

        P(b("Finite-difference discretisation (staggered Arakawa C-grid):"), H3),
        P("h, eta    defined at cell centres (i,j)\n"
          "qx = hu   defined at x-interfaces between (i,j) and (i,j+1)\n"
          "qy = hv   defined at y-interfaces between (i,j) and (i+1,j)\n\n"
          "Interface discharge update (x-direction):\n\n"
          "  q_x^{n+1} = ( q_x^n - g*h_f*(eta_{j+1}-eta_j)/dx*dt )\n"
          "              / ( 1 + g*n^2*|q_x^n|*dt / h_f^(7/3) )\n\n"
          "  h_f = max(0, max(eta_L, eta_R) - max(z_L, z_R))   [upwind free-surface depth]\n\n"
          "Continuity update:\n"
          "  h^{n+1}_{ij} = h^n_{ij}\n"
          "               - (dt/dx)*(q^{n+1}_{x,ij} - q^{n+1}_{x,i,j-1})\n"
          "               - (dt/dy)*(q^{n+1}_{y,ij} - q^{n+1}_{y,i-1,j})\n"
          "  h^{n+1}_{ij} = max(0, h^{n+1}_{ij})    [no negative depths]", CODE),
        P("The friction term in the denominator provides implicit friction stabilisation: "
          "unlike explicit friction (which requires dt < h^(4/3)/(g*n2*|q|)), this "
          "formulation is unconditionally stable with respect to friction, allowing larger "
          "timesteps in shallow water.", BODY),
        sp(0.2),

        P(b("CFL stability condition:"), H3),
        P("dt_CFL = alpha * min(dx,dy) / (c_max + v_max)\n\n"
          "c_max = max(sqrt(g*h))  over wet land cells only\n"
          "v_max = max(|q|/h)      over wet interfaces\n"
          "alpha = 0.7             (CFL safety factor)", CODE),
        P(b("Sea cells are excluded from the CFL condition.") + " Sea cells have prescribed "
          "depths equal to the full surge WSE above the seabed, giving c_max ~ 5 m/s "
          "and forcing dt < 4 s even before any land flooding begins. Since sea depths "
          "are fixed Dirichlet BCs not evolved by the solver, they do not constrain "
          "numerical stability. Exclusion allows dt = 30 s during the dry ramp-up phase, "
          "eliminating ~7,500 unnecessary timesteps per RP.", BODY),
        sp(0.2),

        P(b("Surge hydrograph boundary condition:"), H3),
        make_table([
            ["Phase", "Time window", "WSE at sea cells"],
            ["Ramp",    "0 to 3 h",  "Linear 0 to peak_wse"],
            ["Hold",    "3 to 4 h",  "Constant at peak_wse"],
            ["Recession","4 to 6 h", "Linear peak_wse to 0"],
            ["Settling", "6 to 8 h", "WSE = 0; post-surge drainage only"],
        ], col_widths=[3.0*cm, 4.0*cm, 9.5*cm]),
        sp(0.1),
        P("The synthetic hydrograph is physically representative: real storm surges in the "
          "Singapore Strait develop over 2-6 hours, hold near peak for 1-2 hours, and "
          "recede over 2-4 hours. A static surge level (bathtub) would unrealistically "
          "flood all connected low-lying land simultaneously at t=0. The time-varying "
          "hydrograph produces the physically correct behaviour: wave front advance during "
          "ramp-up, peak inundation at ~4 hours, and partial drainage during recession.", BODY),
        sp(0.2),

        P(b("Cold start and peak depth tracking:"), H3),
        P("The domain starts dry (h = 0 on all land cells). The peak depth at each cell is "
          "tracked throughout the simulation as max(h_current, h_previous_peak). "
          "This records the maximum water depth at any time during the 8-hour window, "
          "which is the physically meaningful quantity for damage assessment.", BODY),

        P(b("Convergence criterion (wet cells only):"), H3),
        P("mean_change = mean(|h_new - h_old|) over wet land cells (h > 1e-3 m)\n"
          "Stop if: mean_change < 1e-4 m over 200 consecutive steps", CODE),
        P("Evaluating convergence over all land cells (including the ~95% that remain dry) "
          "would drive the mean change to near-zero even when active flooding is still "
          "evolving. Restricting to wet cells ensures convergence is only declared when "
          "the flood front has genuinely stabilised.", BODY),
        sp(0.2),

        P(b("Why 2D Local Inertia over alternatives:"), H3),
        make_table([
            ["Model", "Adds vs LI", "Missing vs LI", "When appropriate"],
            ["Bathtub",          "Nothing",                "Connectivity, dynamics, velocity",              "Rapid screening only"],
            ["Local Inertia (used)", "Wave propagation, connectivity, velocity", "Advection (negligible at Fr<0.5)", "Urban coastal, Fr < 0.5"],
            ["Diffusion wave",   "Simpler numerics",       "Inertial effects (matters at steep slopes)",    "Gentle-slope river routing"],
            ["Full SWE",         "Advection, turbulence",  "Nothing significant for Fr<0.5 cases",         "High Fr, dam breaks, tsunamis"],
        ], col_widths=[3.0*cm, 4.0*cm, 5.0*cm, 5.5*cm]),
        sp(0.2),
        make_table([
            ["Return period", "Peak WSE (m)", "Flooded area (km2)", "Max depth (m)"],
            ["RP2",    "2.27", "28.2", "2.32"],
            ["RP10",   "2.41", "30.2", "2.47"],
            ["RP50",   "2.52", "31.7", "2.58"],
            ["RP100",  "2.56", "32.2", "2.61"],
            ["RP500",  "2.64", "33.5", "2.70"],
            ["RP1000", "2.68", "34.0", "2.74"],
        ], col_widths=[3.5*cm, 4.0*cm, 5.0*cm, 5.0*cm]),
        sp(0.4),
    ]
    S.append(PageBreak())

    # --- 5b HAND ---
    S += [
        P("5.2  Fluvial: HAND with Bankfull Subtraction", H2),
        P("The " + b("Height Above Nearest Drainage (HAND)") + " assigns to every land pixel "
          "the vertical distance to the nearest channel cell, measured along the D8 flow path. "
          "It is a topographic proxy for flood susceptibility: a pixel 0.5 m above the "
          "channel floods when the stage exceeds 0.5 m; a pixel 5 m above requires a "
          "correspondingly deeper flood. HAND was introduced by Nobre et al. (2011) and "
          "validated globally as a computationally efficient alternative to full 2D hydraulic "
          "modelling for floodplain delineation.", BODY),

        P(b("Step 1: Pit filling (Planchon-Darboux algorithm)"), H3),
        P("The raw DEM contains isolated single-pixel depressions (pits) created by DEM noise, "
          "bridges, and culverts that break D8 flow routing by trapping flow indefinitely. "
          "The Planchon-Darboux algorithm raises each pit cell to the minimum elevation "
          "allowing drainage to the domain boundary (filled_dem >= dem always). "
          "This is a standard preprocessing step implemented via the pysheds library.", BODY),

        P(b("Step 2: D8 flow direction"), H3),
        P("flow_dir[i,j] = argmax_k { (z[i,j] - z[neighbour_k]) / distance_k }", CODE),
        P("D8 assigns all flow from each cell to whichever of the 8 neighbours has the "
          "steepest downhill gradient. This produces discrete, deterministic flow paths. "
          + b("Why D8:") + " simpler and more computationally efficient than "
          "multi-flow-direction methods (D-infinity); standard in operational hydrology; "
          "sufficient for channel delineation on 30 m DEMs where the channel network "
          "is the dominant drainage feature.", BODY),

        P(b("Step 3: Flow accumulation"), H3),
        P("FAC[i,j] = 1 + sum(FAC[k] for all k where flow_dir[k] points to [i,j])", CODE),
        P("FAC counts the number of upstream cells draining through each pixel. "
          "High FAC identifies stream valleys; low FAC identifies ridges.", BODY),

        P(b("Step 4: Channel delineation"), H3),
        P("A pixel is a channel if: FAC >= 500 cells (draining >= 0.45 km2)  OR  mapped "
          "as river/canal/drain in OpenStreetMap.", BODY),
        P("The 500-cell FAC threshold corresponds to ~0.45 km2 catchment area at 30 m resolution, "
          "consistent with Singapore's engineered drainage density. The OSM overlay ensures "
          "piped/culverted channels with small FAC (secondary drains) are correctly included.", BODY),

        P(b("Step 5: HAND derivation"), H3),
        P("HAND[i,j] = dem[i,j] - dem[channel_cell at end of D8 path from (i,j)]", CODE),
        P("For each non-channel pixel, the D8 path is traced downstream until a channel "
          "cell is reached. HAND is the elevation difference along this path. "
          "Channel cells have HAND = 0.", BODY),
        sp(0.2),

        P(b("Bankfull subtraction:"), H3),
        P("overbank_m = max(0,  stage_RP - stage_RP10)\n"
          "depth[i,j] = max(0,  overbank_m - HAND[i,j])", CODE),
        P("Singapore's primary drainage network is designed to carry RP10 flows without "
          "overflow (PUB design standard). Using the raw channel stage would flood large "
          "areas at RP2-RP10 where no surface flooding physically occurs. "
          "Subtracting the RP10 bankfull stage means: "
          "RP2-RP10 produce zero overbank flooding (within design capacity); "
          "RP25 onwards produce flooding proportional to how much the stage exceeds bankfull.", BODY),
        sp(0.2),

        P(b("Why HAND over alternatives:"), H3),
        make_table([
            ["Method", "Advantage", "Limitation vs HAND"],
            ["Bathtub from sea",  "Simple",                   "Floods across ridges; ignores watershed boundaries"],
            ["HAND (used)",       "Respects D8 boundaries; no BFS seed needed", "Static; no backwater, no velocity"],
            ["1D HEC-RAS",        "Full hydraulic routing",   "Requires surveyed cross-sections; not scriptable"],
            ["2D LISFLOOD-FP",    "Full 2D dynamics",         "Computationally intensive for 9 RPs * 3 hazards"],
        ], col_widths=[3.5*cm, 6.5*cm, 7.5*cm]),
        sp(0.2),
        make_table([
            ["Return period", "Stage (m)", "Overbank above RP10 (m)", "Flooded area (km2)"],
            ["RP2-RP10",  "1.47-1.93", "0.00", "0.0"],
            ["RP25",      "2.16",      "0.23", "85.9"],
            ["RP50",      "2.33",      "0.39", "91.2"],
            ["RP100",     "2.49",      "0.56", "97.1"],
            ["RP500",     "2.87",      "0.93", "108.7"],
            ["RP1000",    "3.03",      "1.09", "113.4"],
        ], col_widths=[3.5*cm, 3.5*cm, 5.5*cm, 4.5*cm]),
        sp(0.4),
    ]

    # --- 5c PLUVIAL ---
    S += [
        P("5.3  Pluvial: Depression-Filling Ponding Model", H2),
        P("Pluvial flooding occurs when intense short-duration rainfall exceeds the local "
          "drainage capacity. Water ponds in terrain depressions -- road underpasses, "
          "low-lying carparks, basement entrances, natural hollows -- until it either "
          "drains, evaporates, or overflows at the depression's pour point "
          "(the lowest point on the depression rim).", BODY),

        P(b("Depression-filling algorithm (Planchon-Darboux via pysheds):"), H3),
        P("filled_dem[i,j] = minimum elevation allowing a continuous downhill path\n"
          "                   to the domain boundary\n\n"
          "max_ponding[i,j] = max(0, filled_dem[i,j] - dem[i,j])\n\n"
          "Example: a 2m pixel in a bowl with a 3m pour point:\n"
          "  max_ponding = 3 - 2 = 1 m  (can hold up to 1 m before overflowing)", CODE),
        P("max_ponding gives the maximum depth each pixel can hold before overflow. "
          "Pixels at ridges and hilltops have max_ponding = 0 "
          "(filled_dem = dem -- no depression to fill).", BODY),

        P(b("Ponding depth calculation:"), H3),
        P("depth[i,j] = min(water_level_m,  max_ponding[i,j])", CODE),
        P("At low return periods (small water_level_m), only the shallowest depressions "
          "fill. At high return periods, progressively deeper depressions fill. "
          "The constant 330 km2 flooded area from RP10 to RP1000 reflects "
          "that all depressions resolvable at 30 m are already filling by RP10; "
          "additional water at higher RPs increases depth in existing ponds but "
          "does not activate new ones.", BODY),

        P(b("Sea mask exclusion:"), H3),
        P("Sea pixels are set to NaN before depression-filling. Without this, the entire "
          "ocean would form a single enormous depression that absorbs all available water, "
          "producing unrealistic flooding concentrated at the coastline. "
          "NaN sea pixels are ignored by the fill algorithm, isolating the land surface.", BODY),
        sp(0.2),

        P(b("Why depression-filling over alternatives:"), H3),
        make_table([
            ["Method", "Physical interpretation", "Limitation vs depression-filling"],
            ["Bathtub", "Flat water to water level", "Floods all land below threshold; physically wrong for rainfall (not connected to sea)"],
            ["Bathtub + BFS", "Connected low areas only", "Treats entire watershed as one pool; doesn't represent isolated depressions"],
            ["Depression-filling (used)", "Each depression fills to pour point", "Static; no drainage rate; overestimates at 30m (sub-30m depressions missed)"],
            ["1D/2D drainage network", "Explicit pipe flow and surcharging", "Requires complete drainage network geometry (not publicly available)"],
        ], col_widths=[3.5*cm, 5.5*cm, 7.5*cm]),
        sp(0.2),
        make_table([
            ["Return period", "Ponding level (m)", "Flooded area (km2)", "Notes"],
            ["RP2, RP5",  "0.000", "0.0",   "Within drain capacity -- no surface ponding"],
            ["RP10",      "0.095", "330.1", "Onset of surface ponding"],
            ["RP25",      "0.272", "330.1", "Depth increases; extent saturated at 30m resolution"],
            ["RP100",     "0.535", "330.1", "--"],
            ["RP1000",    "0.967", "330.1", "--"],
        ], col_widths=[3.0*cm, 4.0*cm, 4.5*cm, 6.0*cm]),
        sp(0.4),
    ]
    S.append(PageBreak())

    # ===================================================================
    # MAPS
    # ===================================================================
    S += section_divider("6. Results: Multi-Hazard Flood Maps")
    S += [
        sp(0.2),
        P("The combined map at each return period colours every pixel by the dominant hazard "
          "(greatest depth): " + b("Blue = Coastal") + ", " + b("Orange = Fluvial") +
          ", " + b("Green = Pluvial") +
          ". Colour intensity is proportional to depth (0-1.5 m shared scale).", BODY),
        sp(0.3),
    ]
    S += img_elem(OUTPUT_DIR/"map_combined_SSP5-8.5_2100_rp_comparison.png", width_cm=16.5,
        caption="Figure 2. Return-period comparison panel (SSP5-8.5, 2100). "
                "Blue = Coastal (inertial solver), Orange = Fluvial (HAND), Green = Pluvial (ponding). "
                "Numbers in subplot titles are flooded area (km2).")
    S.append(PageBreak())

    for rp, label in [(2,  "RP2 -- 1-in-2 year. Coastal surge only; RP2 fluvial and pluvial within drain/channel capacity."),
                      (25, "RP25 -- 1-in-25 year. All three hazards active for the first time."),
                      (100,"RP100 -- 1-in-100 year. Fluvial and pluvial flooding extends inland."),
                      (1000,"RP1000 -- 1-in-1000 year. Near-maximum flood extents for all three hazards.")]:
        mp = OUTPUT_DIR / f"map_combined_SSP5-8.5_2100_rp{rp}.png"
        S += img_elem(mp, width_cm=15.0,
            caption=f"Figure. {label}")
        S.append(sp(0.2))

    S.append(PageBreak())

    # ===================================================================
    # LIMITATIONS & ENHANCEMENTS
    # ===================================================================
    S += section_divider("7. Limitations and Potential Enhancements")
    S += [
        sp(0.2),
        make_table([
            ["Limitation", "Practical implication", "Severity"],
            ["30 m DEM resolution", "Sea walls, embankments, culverts invisible; extents may penetrate protected areas", "High"],
            ["No flood defences", "Coastal sea walls, PUB tidal gates, Marina Barrage not represented as barriers", "High"],
            ["ERA5 underestimates tropical rainfall", "Fluvial/pluvial baselines likely understate true extremes by 10-30% at high RPs", "Medium"],
            ["Inertial solver 8h window", "Coastal area ~3 km2 smaller than static bathtub equilibrium", "Low"],
            ["HAND ignores channel routing", "No backwater or attenuation; RP10 bankfull subtraction partially mitigates", "Medium"],
            ["Pluvial extent saturates at RP10", "RP10-RP1000 variation is in depth only; 30 m DEM cannot resolve sub-30 m depressions", "Medium"],
            ["Hazards independent", "Joint events not modelled; worst Singapore floods involve all three simultaneously", "High"],
            ["No observational validation", "Quantitative accuracy unknown without comparison to satellite flood maps", "High"],
        ], col_widths=[4.0*cm, 9.5*cm, 2.5*cm]),
        sp(0.3),
        P(b("High-priority enhancements:"), H3),
        P("1. SLA LiDAR DEM (1 m) -- resolves sea walls, embankments, drainage channel geometry.", BULLET),
        P("2. Validation against Sentinel-1 SAR flood imagery from past events.", BULLET),
        P("3. Explicit flood defence layer -- burn sea wall and bund crest elevations into DEM.", BULLET),
        P("4. PUB drainage network geometry replacing representative Manning's parameters.", BULLET),
        P(b("Medium-priority enhancements:"), H3),
        P("5. Uncertainty quantification across AR6 17th/50th/83rd percentile sea-level deltas.", BULLET),
        P("6. Compound flooding framework -- joint exceedance probability for all three hazards.", BULLET),
        P("7. MSS/NEA radar-gauge merged precipitation replacing ERA5.", BULLET),
        sp(0.3),
    ]

    # ===================================================================
    # DATA SOURCES
    # ===================================================================
    S += section_divider("8. Data Sources and Reproducibility")
    S += [
        sp(0.2),
        make_table([
            ["Data", "Source", "Pipeline script"],
            ["Copernicus DEM GLO-30",     "Microsoft Planetary Computer STAC", "fetch_copernicus_dem.py"],
            ["GEBCO 2025 bathymetry",      "download.gebco.net (manual one-off)", "merge_gebco_dem.py"],
            ["ERA5 precipitation 1950-2024","Open-Meteo Historical Weather API", "fit_pluvial_baseline_era5.py\nfit_fluvial_baseline_era5.py"],
            ["Tide gauge 1984-2023",        "UHSLC Research Quality archive",    "fetch_gesla_singapore.py"],
            ["AR6 sea-level projections",   "Rutgers/IPCC public Zarr store",    "build_singapore_hazard_levels.py"],
            ["OSM river network",           "Overpass API via OSMnx",            "build_river_raster_from_osm.py"],
        ], col_widths=[4.5*cm, 6.5*cm, 6.5*cm]),
        sp(0.2),
        P("Run " + code_inline("python scripts/run_singapore_pipeline.py") +
          " to reproduce all outputs from scratch. GEBCO requires a one-off manual download.", BODYS),
    ]

    doc.build(S)
    print(f"Wrote: {out}")


if __name__ == "__main__":
    build()
