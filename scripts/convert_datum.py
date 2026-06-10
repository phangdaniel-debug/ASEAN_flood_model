"""
Vertical datum conversion utilities for the Singapore flood pipeline.

Background
----------
The Copernicus GLO-30 DEM uses **EGM2008** as its vertical reference surface.
All water levels ingested into the flood depth model must be expressed in the
same datum.  A mismatch silently shifts every depth estimate by a constant
offset — typically 0.5–1.5 m for Singapore — which is larger than the depth
threshold separating Minor from Major flood severity.

Datum hierarchy used in this pipeline
--------------------------------------
EGM2008
    The Earth Gravitational Model 2008 geoid.  Approximately equal to global
    mean sea level.  This is the DEM's zero elevation surface.

Local MSL (Mean Sea Level)
    The time-averaged ocean surface at a specific tide gauge station.  Differs
    from EGM2008 by the **Mean Dynamic Topography** (MDT) — the permanent,
    non-tidal tilt of the sea surface due to ocean circulation.  MDT is small
    (~0–0.1 m) in most of Southeast Asia but non-negligible for high-accuracy
    work.

Chart Datum (CD) / Lowest Astronomical Tide (LAT)
    The reference for nautical charts and tidal predictions.  At Tanjong Pagar,
    Singapore, CD is approximately 1.573 m below local MSL.

Singapore Height Datum (SHD)
    The official Singapore vertical datum, defined so that SHD = 0 m ≈ MSL at
    Tanjong Pagar.  SHD is used in PUB drainage drawings and survey products.

Conversion chain used in this pipeline
---------------------------------------
UHSLC gauge datum (mm)
    → divide by 1000, subtract long-term mean
    → MSL anomaly (m)
    → add  ``msl_to_egm2008_offset``
    → EGM2008 (m)   ← what the DEM expects

For **fluvial** and **pluvial** hazards the water levels are purely relative
(stage above channel bed; equivalent ponding depth).  They are consumed by the
HAND and depression-filling models respectively, which are also self-relative.
No absolute datum conversion is required for those hazards.

Known offsets (derived from CNES-CLS18 MDT)
--------------------------------------------
Values represent the height of local MSL above the EGM2008 geoid (Mean Dynamic
Topography) at each tide gauge location.  Run
``python scripts/derive_msl_egm2008_offsets.py`` to re-derive.

All values are positive in SE Asia (0.04–0.30 m), reflecting the broad positive
MDT of the western Pacific and Indian Ocean margins.  GLO-30 DEM has ~1–2 m RMSE,
so these offsets matter primarily as systematic bias corrections.

``CHART_DATUM_TO_MSL_SINGAPORE``
    Singapore Chart Datum ≈ −1.573 m relative to local MSL at Tanjong Pagar.
    (Source: PUB Singapore and maritime authority documentation.)
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Known offsets — extend this table for new sites
# ---------------------------------------------------------------------------

#: MSL elevation above EGM2008 (m) at each active tide gauge.
#: Source: CNES-CLS18 MDT, interpolated via scripts/derive_msl_egm2008_offsets.py.
#: Values below are interim literature estimates (CNES-CLS18/DTU15 consensus, +-0.04 m).
#: Run ``python scripts/derive_msl_egm2008_offsets.py --write`` to apply exact values.
#: Positive = local MSL is above the EGM2008 geoid surface.
MSL_TO_EGM2008_SINGAPORE: float = 0.04     # UHSLC 699, Tanjong Pagar; interim estimate
MSL_TO_EGM2008_PORT_KLANG: float = 0.12    # UHSLC 140, Port Klang; interim estimate
MSL_TO_EGM2008_KO_LAK: float = 0.28        # UHSLC 328, Ko Lak (Bangkok proxy); interim estimate
MSL_TO_EGM2008_TANJUNG_PRIOK: float = 0.30 # UHSLC 161, Tanjung Priok (Jakarta); interim estimate
MSL_TO_EGM2008_MANILA: float = 0.25        # UHSLC 304, Manila (Fort Santiago); interim estimate — South China Sea ~14.6°N
MSL_TO_EGM2008_VUNG_TAU: float = 0.35      # UHSLC 257, Vung Tau (HCMC proxy); interim estimate — South China Sea ~10.3°N

#: Chart Datum elevation relative to local MSL at Tanjong Pagar (m).
#: Negative = CD is below MSL.
CHART_DATUM_TO_MSL_SINGAPORE: float = -1.573


# ---------------------------------------------------------------------------
# Conversion functions
# ---------------------------------------------------------------------------

def msl_anomaly_to_egm2008(level_msl_m: float, msl_to_egm2008_offset: float) -> float:
    """
    Convert a water level expressed as an anomaly above local MSL to EGM2008.

    Parameters
    ----------
    level_msl_m :
        Water level in metres above local MSL (e.g. de-meaned tide gauge).
    msl_to_egm2008_offset :
        Height of local MSL above the EGM2008 surface, in metres.
        Positive when local MSL sits above EGM2008 (typical in the tropics).
        Use ``MSL_TO_EGM2008_SINGAPORE`` for the Singapore tide gauge.

    Returns
    -------
    float
        Water level in metres above EGM2008.
    """
    return float(level_msl_m + msl_to_egm2008_offset)


def chart_datum_to_egm2008(
    level_cd_m: float,
    cd_to_msl_offset: float,
    msl_to_egm2008_offset: float,
) -> float:
    """
    Convert a water level above Chart Datum to EGM2008.

    Parameters
    ----------
    level_cd_m :
        Water level in metres above Chart Datum.
    cd_to_msl_offset :
        Chart Datum height relative to local MSL (metres; typically negative,
        i.e. CD is below MSL).  Use ``CHART_DATUM_TO_MSL_SINGAPORE`` for
        Tanjong Pagar.
    msl_to_egm2008_offset :
        As for :func:`msl_anomaly_to_egm2008`.

    Returns
    -------
    float
        Water level in metres above EGM2008.

    Examples
    --------
    >>> # 2.0 m above Singapore Chart Datum → EGM2008
    >>> chart_datum_to_egm2008(2.0, CHART_DATUM_TO_MSL_SINGAPORE, MSL_TO_EGM2008_SINGAPORE)
    0.467
    """
    level_msl = level_cd_m + cd_to_msl_offset   # CD → MSL (cd_to_msl is negative)
    return msl_anomaly_to_egm2008(level_msl, msl_to_egm2008_offset)


def make_datum_note(
    source_datum: str,
    msl_to_egm2008_offset: float,
    target_datum: str = "EGM2008",
    extra: str = "",
) -> str:
    """
    Generate a provenance string for the ``datum_note`` column in baseline CSVs.

    Parameters
    ----------
    source_datum :
        Description of the input datum (e.g. ``"UHSLC_gauge_de-meaned_to_MSL"``).
    msl_to_egm2008_offset :
        The MSL→EGM2008 offset applied (metres).
    target_datum :
        The output datum (always ``"EGM2008"`` in this pipeline).
    extra :
        Any additional provenance detail appended after a semicolon.
    """
    note = (
        f"source={source_datum}; "
        f"msl_to_egm2008_offset={msl_to_egm2008_offset:+.4f}m; "
        f"target_datum={target_datum}"
    )
    if extra:
        note += f"; {extra}"
    return note


def validate_datum_notes(baseline_df) -> list[str]:
    """
    Check that all coastal rows in a baseline DataFrame carry an EGM2008-referenced
    ``datum_note``.  Returns a list of warning strings (empty if all is well).

    Parameters
    ----------
    baseline_df : pd.DataFrame
        Baseline hazard CSV loaded as a DataFrame.  Expected columns:
        ``hazard_type``, optionally ``datum_note``.
    """
    warnings: list[str] = []
    if "datum_note" not in baseline_df.columns:
        warnings.append(
            "Baseline CSV has no 'datum_note' column.  Cannot verify that "
            "coastal water levels are referenced to EGM2008.  Re-run the "
            "fit scripts (fetch_uhslc_gauge.py) to regenerate the baseline "
            "with datum provenance, or add the column manually."
        )
        return warnings

    coastal = baseline_df[baseline_df["hazard_type"].str.lower() == "coastal"]
    for _, row in coastal.iterrows():
        note = str(row.get("datum_note", ""))
        if "EGM2008" not in note:
            warnings.append(
                f"Coastal RP={row['return_period']}: datum_note does not confirm "
                f"EGM2008 referencing — found: {note!r}.  "
                "Ensure coastal levels are in metres above EGM2008 before use."
            )
        if "msl_to_egm2008_offset" not in note:
            warnings.append(
                f"Coastal RP={row['return_period']}: datum_note does not record "
                "the MSL→EGM2008 offset that was applied.  "
                "Re-run fetch_uhslc_gauge.py with --msl-to-egm2008-offset, "
                "or apply the MDT correction via scripts/derive_msl_egm2008_offsets.py."
            )
    return warnings
