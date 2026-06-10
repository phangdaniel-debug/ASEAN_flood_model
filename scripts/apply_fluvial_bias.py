"""Documented magnitude bias correction for the KL fluvial discharge (Plan 7).
stage_above_bankfull = mannings_stage(factor * Q_rp) - mannings_stage(bankfull_q),
where Q_rp is the GLOFAS-GEV return level. factor anchored to the rainfall bias (#19/Plan 7)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.gev_utils import gev_return_level, mannings_stage

def apply_fluvial_bias(rp, factor, gev_xi, gev_mu, gev_sigma,
                       bankfull_q, channel_w, n, slope):
    q_rp = gev_return_level(-gev_xi, gev_mu, gev_sigma, rp)
    stage = mannings_stage(factor * q_rp, channel_w, n, slope)
    bankfull_stage = mannings_stage(bankfull_q, channel_w, n, slope)
    return max(0.0, stage - bankfull_stage)
