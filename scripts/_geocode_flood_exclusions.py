"""Geocode the additional documented KL flood-prone areas (beyond the 17 positives)
to build a model-blind flood-EXCLUSION coordinate set for systematic hard-negative sampling."""
import sys, time, json, urllib.parse, urllib.request
from pathlib import Path
# Additional documented flood-prone areas (NOT already positives):
#  - DBKL 14-hotspot extras + Oct-2024 flash-flood roads (Malay Mail/NST/Scoop) + DID lists
EXTRA = [
    "Jalan Pudu, Kuala Lumpur, Malaysia",
    "Salak Selatan, Kuala Lumpur, Malaysia",
    "Jalan Kuching, Kuala Lumpur, Malaysia",
    "Jalan Pantai Baru, Kuala Lumpur, Malaysia",
    "Jalan Genting Klang, Setapak, Kuala Lumpur, Malaysia",
    "Jalan Tuanku Abdul Halim, Kuala Lumpur, Malaysia",
    "Jalan Gombak, Kuala Lumpur, Malaysia",
    "Jalan Manjalara, Kepong, Kuala Lumpur, Malaysia",
    "Jalan Maharajalela, Kuala Lumpur, Malaysia",
    "Wangsa Maju, Kuala Lumpur, Malaysia",
    "Jalan Syed Putra, Kuala Lumpur, Malaysia",
    "Jalan Peel, Kuala Lumpur, Malaysia",
    "Jalan Dutamas, Kuala Lumpur, Malaysia",
    "Taman Desa, Kuala Lumpur, Malaysia",
    "Kampung Bukit Lanchong, Subang Jaya, Selangor, Malaysia",
    "Kampung Sungai Lui, Hulu Langat, Selangor, Malaysia",
    "Batu Caves, Selangor, Malaysia",
    "OUG, Overseas Union Garden, Kuala Lumpur, Malaysia",
]
def geocode(q):
    p={"q":q,"format":"json","limit":1,"viewbox":"101.55,3.30,101.82,2.95","bounded":0}
    url="https://nominatim.openstreetmap.org/search?"+urllib.parse.urlencode(p)
    req=urllib.request.Request(url,headers={"User-Agent":"flood-v2-validation/1.0"})
    try:
        r=json.load(urllib.request.urlopen(req,timeout=25))
        return (float(r[0]["lon"]),float(r[0]["lat"])) if r else None
    except Exception as e:
        return None
out=[]
for q in EXTRA:
    c=geocode(q); time.sleep(1.1)
    print(f"{'OK ' if c else 'FAIL'} {q[:45]:45s} {c}")
    if c: out.append({"name":q.split(',')[0],"lon":c[0],"lat":c[1]})
Path("data/kuala_lumpur/_flood_exclusions.json").write_text(json.dumps(out,indent=1))
print(f"\nGeocoded {len(out)}/{len(EXTRA)} extra flood-prone areas -> data/kuala_lumpur/_flood_exclusions.json")
