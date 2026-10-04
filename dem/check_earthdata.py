"""Verify EarthData auth via earthaccess. Prints NO credentials."""
import earthaccess

auth = earthaccess.login(strategy="netrc")
print("authenticated:", bool(auth.authenticated))

# Tiny metadata-only search to confirm the token actually works against CMR.
# Bangkok bbox (lon_min, lat_min, lon_max, lat_max).
bbox = (100.35, 13.45, 100.95, 14.00)
for short_name, daac in [("ATL08", "NSIDC"), ("GEDI02_A", "ORNL")]:
    try:
        results = earthaccess.search_data(
            short_name=short_name,
            bounding_box=bbox,
            temporal=("2020-01-01", "2020-12-31"),
            count=3,
        )
        print(f"{short_name:10s} ({daac}): {len(results)} granules found (metadata OK)")
    except Exception as e:
        print(f"{short_name:10s} ({daac}): SEARCH ERROR {type(e).__name__}: {e}")
