# Bangkok 2011-flood hotspot research (model-blind) — Plan B1 Task 2

**Goal:** a model-blind documented-hotspot register for Bangkok — positives = localities
**documented flooded** in the 2011 Thailand megaflood; dry controls = the inner core
**documented defended / stayed dry**. The dry label comes from 2011 flood records, NEVER
from the model's output. Selection is frozen before the model rasters are consulted.

## Key fact — the 2011 "tale of two cities"

The 2011 flood inundated the **northern, eastern and western outer districts** of the
Bangkok Metropolitan Region (and the upstream Pathum Thani / Nonthaburi industrial belt),
while the **bunded inner core** (Sukhumvit, Silom, Sathorn, the CBD) was held dry behind
hundreds of thousands of sandbags + the King's-Dyke floodwall line — water was deliberately
diverted around the centre to protect the economic core. This gives an unusually clean,
well-documented **defended/undefended boundary** → natural low-lying dry controls (unlike
KL, where low-lying negatives were unsourceable, limitation #21).

**Sources:** 2011 Thailand floods (Wikipedia); CNN "Bangkok's floods: a tale of two
cities" (2011-11-09); France24 / CSMonitor "Bangkok flood defences hold" (2011-10-29);
Thai HII flood-2011 report (tiwrmdev.hii.or.th); World Bank "Thai Flood 2011 Rapid
Assessment"; ERIA-DP-2013-34.

## Positives (documented flooded in 2011) — geocode queries

| # | name | geocode query | source / note |
|---|------|----------------|---------------|
| 1 | Don Mueang | Don Mueang, Bangkok, Thailand | district + domestic airport inundated/closed (Wikipedia; HII) |
| 2 | Sai Mai | Sai Mai, Bangkok, Thailand | could not drain to sea pumping stations → flooded (HII) |
| 3 | Khlong Sam Wa | Khlong Sam Wa, Bangkok, Thailand | NE district flooded (HII) |
| 4 | Lak Si | Lak Si, Bangkok, Thailand | assistance dispatched; flooded (Wikipedia) |
| 5 | Bang Khen | Bang Khen, Bangkok, Thailand | northern district flooded (HII/news) |
| 6 | Bang Sue | Bang Sue, Bangkok, Thailand | assistance dispatched; flooded (Wikipedia) |
| 7 | Rangsit | Rangsit, Pathum Thani, Thailand | Rangsit Univ. total inundation; businesses closed (Wikipedia) |
| 8 | Lam Luk Ka | Lam Luk Ka, Pathum Thani, Thailand | flooded with Rangsit corridor (Wikipedia) |
| 9 | Nava Nakorn industrial estate | Nava Nakhon, Khlong Luang, Pathum Thani, Thailand | major industrial-estate inundation (World Bank; Wikipedia) |
| 10 | Bang Bua Thong | Bang Bua Thong, Nonthaburi, Thailand | Nonthaburi western flooded (HII/news) |
| 11 | Pak Kret | Pak Kret, Nonthaburi, Thailand | riverside Nonthaburi flooded (news) |
| 12 | Mueang Nonthaburi | Mueang Nonthaburi, Nonthaburi, Thailand | provincial capital riverfront flooded (news) |
| 13 | Min Buri | Min Buri, Bangkok, Thailand | eastern district flooded (HII) |
| 14 | Nong Chok | Nong Chok, Bangkok, Thailand | far-eastern district flooded (HII) |
| 15 | Taling Chan | Taling Chan, Bangkok, Thailand | western district flooded (news) |
| 16 | Thawi Watthana | Thawi Watthana, Bangkok, Thailand | western district flooded (news) |
| 17 | Bang Phlat | Bang Phlat, Bangkok, Thailand | riverfront overtopping flooded (CBS/news) |

## Dry controls (documented defended / stayed dry in 2011) — geocode queries

| # | name | geocode query | source / note |
|---|------|----------------|---------------|
| 1 | Silom | Silom, Bang Rak, Bangkok, Thailand | central business core held dry (CNN; France24) |
| 2 | Sathorn | Sathon, Bangkok, Thailand | CBD held dry behind floodwalls (CNN) |
| 3 | Sukhumvit (Watthana) | Sukhumvit, Watthana, Bangkok, Thailand | commercial/tourist core stayed dry (CNN; CSMonitor) |
| 4 | Pathum Wan / Siam | Pathum Wan, Bangkok, Thailand | Siam CBD stayed dry (news) |
| 5 | Lumphini | Lumphini, Pathum Wan, Bangkok, Thailand | central, defended, dry (news) |
| 6 | Bang Rak | Bang Rak, Bangkok, Thailand | riverside CBD held by floodwall (news) |
| 7 | Ratchathewi | Ratchathewi, Bangkok, Thailand | inner district stayed dry (news) |

## Discipline notes

- **Model-blind:** positives = documented 2011 inundation; dry controls = documented
  defended-and-dry inner core. No model raster was consulted to choose any spot. Selection
  frozen here; the model is read only at the validation step.
- **Dry controls are LOW-lying (delta) but documented-dry** — they test specificity against
  the active-defense boundary. **Caveat to surface in the verdict:** the inner core stayed
  dry in 2011 partly because of *emergency* defenses (sandbags + diversion + pumping) that a
  steady-state design-RP model does not represent. If the model floods the defended core at
  RP100, that is a real, reportable finding (the King's-Dyke / pumping defense is not in the
  steady-state field) — NOT a reason to drop the control. A flooded dry control stays in and
  is reported (cardinal rule, SG #15).
- **17 positives + 7 dry controls** → KL parity. Geocoding + DEM verification is Task 4.


**Geocode/domain note (Task 4):** All 16 retained positives + 7 dry controls geocoded cleanly to low delta elevations (2-10 m). **Nava Nakorn industrial estate was DROPPED** — it geocodes to 14.11 N, north of the `bangkok` DEM extent (max 14.05 N), so it is out of the model domain and cannot be scored (cf. KL Taman Sri Muda); the in-domain Rangsit / Lam Luk Ka corridor already represents the upstream northern flooded belt. Final register: **16 positives + 7 dry controls**, `validate_manifest('bangkok')` clean.
