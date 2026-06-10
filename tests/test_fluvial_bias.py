import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.apply_fluvial_bias import apply_fluvial_bias

GEV = dict(gev_xi=0.2835, gev_mu=149.5, gev_sigma=44.7,
           bankfull_q=98.0, channel_w=30.0, n=0.035, slope=0.002)

def test_factor_one_reproduces_baseline_rp100():
    s = apply_fluvial_bias(rp=100, factor=1.0, **GEV)
    assert abs(s - 3.31) < 0.10   # committed baseline stage-above-bankfull

def test_factor_206_clears_old_klang_road_hand():
    s = apply_fluvial_bias(rp=100, factor=2.06, **GEV)
    assert s > 5.45               # > Old Klang Road HAND -> it will flood

def test_monotone_in_rp():
    ss = [apply_fluvial_bias(rp=rp, factor=2.06, **GEV) for rp in (2,10,100,1000)]
    assert all(b >= a for a, b in zip(ss, ss[1:]))
