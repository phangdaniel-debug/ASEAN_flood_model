# Bangkok dry-control expansion — testing the C13 degenerate-stratum concern (2026-07-18)

Addresses ranked follow-up **item 3** from the outstanding-review triage: Bangkok's
"significant skill" rested on a **degenerate 7/7 control stratum** (zero resampling
variance) with a marginal Fisher exact p ≈ 0.077. The review noted this "isn't fixable by
disclosure — only expanding the Bangkok dry-control register would firm it up." This run
does that expansion and reports what it shows.

## Discipline (declared before scoring)

- **Model not consulted before freezing.** Controls were selected on documented 2011
  dry status, geocoded (Nominatim), and frozen *before* any scoring.
- **Supplementary, not a re-pre-registration.** The paper's frozen register
  (`hotspots_expanded.csv`, 32 pos / 7 dry) is **untouched**. The expansion is a separate
  file `data/bangkok/manifest/hotspots_c13supp.csv` (32 pos / 10 dry) scored as a
  post-hoc robustness check.
- **What counts as a documented-dry control here.** In a defence-determined flat delta the
  documented-dry universe is narrow: research confirmed the 2011 flood inundated the north
  (Don Mueang, Sai Mai, Laksi, Bang Khen, Chatuchak), the east (Bang Kapi, Ramkhamhaeng,
  Srinakharin — these are register *positives*), Thonburi (west bank), and the southern
  riverside (Sathon/Bang Kho Laem/Khlong Toei). The documented-dry set is the defended
  inner core (the existing 7) **plus** three spatially-distinct sites this run adds:

  | New control | Basis (2011) | Distance from nearest existing pt |
  |---|---|---|
  | Suvarnabhumi Airport | stayed dry & operational behind its 23.5 km / 3.0–3.5 m embankment while Don Mueang flooded | 3.9 km (far east) |
  | Grand Palace / Rattanakosin | riverside old city held dry by sandbag+pump defence, stayed open | 3.8 km (NW, riverside) |
  | Yaowarat / Chinatown | "largely dry" behind the central Chao Phraya floodwall | 2.1 km (NW) |

  All three are >2 km from any existing register point and in-domain; Suvarnabhumi is
  ~29 km from the old-city pair. Sources in the register `source` column.
- **One scoring run at gate protocol** (present-day RP100 polder composite, ≥0.10 m, 50 m).

## Result

| Register | pos/dry | HR | CRR | TSS [95% CI] | Fisher p (1-sided) |
|---|---|---|---|---|---|
| paper frozen (7 dry) | 32/7 | 0.34 | 1.00 | 0.34 [0.19, 0.50] | 0.077 |
| **supplementary (10 dry)** | 32/10 | 0.34 | 0.90 | **0.24 [−0.02, 0.47]** | **0.137** |

**Expanding the control stratum does not confirm Bangkok's significance — it removes it.**
The TSS CI now **crosses zero** and Fisher p rises 0.077 → 0.137. The single false alarm is
**Grand Palace** (model floods it at 0.17 m, pluvial); Suvarnabhumi and Yaowarat are both
correctly rejected.

**The flip is driven entirely by one genuinely borderline control.** Grand Palace is the one
new site that *did* take transient ankle-deep water in 2011 (documented "ringed by
ankle-deep water… pumped… remained open") — held dry only by active pumping the model does
not encode, and its 50 m window legitimately includes the perimeter streets that wetted.
A post-hoc sensitivity dropping it (9 dry, 0 FA) gives Fisher p = **0.041** — i.e. the two
*unambiguous* new controls the model gets right would have firmed the significance below
0.05. **This sensitivity is reported, not claimed:** the pre-registered result is the
10-control p = 0.137.

## Interpretation

C13 is **confirmed, not closed**: Bangkok's location skill is **not robustly significant**.
Whether it clears p < 0.05 depends entirely on how one borderline riverside control is
classified — exactly the fragility the degenerate 7/7 stratum concealed. Two things worth
recording:

1. **Consistent with the paper as written.** The SAFE abstract already reports significance
   "in three of the four cities (positive but marginal in the fourth)" — Bangkok is that
   fourth city. This run *corroborates* that framing; **no paper claim needs weakening.**
2. **The model doc overstated it.** §7.4 listed Bangkok as "significant (bootstrap)"; that
   bootstrap significance is an artifact of the degenerate stratum and is now corrected to
   "not robustly significant — flips to p = 0.137 under a documented 10-control expansion."

No re-tuning was performed. The expansion register is retained as a robustness artifact;
the paper's frozen register remains the pre-registered one.
