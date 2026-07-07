"""
fetch_amenities.py — run this in Google Colab (free), NOT locally required.

What it does:
  1. Downloads the district polygons from YOUR live GitHub Pages site
  2. Queries OpenStreetMap (Overpass API) for West Malaysia:
       - rail stations (MRT/LRT/KTM/monorail)
       - shopping malls
       - supermarkets
  3. Assigns every amenity to its district (point-in-polygon)
  4. Writes amenities.json  -> download it and upload back to Claude

How to run in Colab:
  1. https://colab.research.google.com -> New notebook
  2. Paste this whole file into a cell
  3. FIX THE REPO URL on the line marked <<< FIX ME
  4. Run the cell (takes ~2-5 min, mostly waiting for Overpass)
  5. Files panel (left sidebar) -> download amenities.json
"""

import json
import time
import requests
from shapely.geometry import shape, Point
from shapely.prepared import prep

# <<< FIX ME: your GitHub Pages URL, no trailing slash
SITE = "https://thomasvanpul.github.io/west_malaysia_map"

GEOJSON_URL = SITE + "/geoBoundaries-MYS-ADM2_simplified.geojson"
# Multiple mirrors: the main instance blocks generic user agents and shared IPs (Colab).
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
HEADERS = {"User-Agent": "west-malaysia-district-explorer/1.0 (student project)"}

# West Malaysia bounding box: (south, west, north, east)
BBOX = "0.8,99.4,6.9,104.7"

QUERIES = {
    "rail_stations": f"""
        [out:json][timeout:300];
        ( node["railway"="station"]({BBOX});
          way["railway"="station"]({BBOX}); );
        out center;""",
    "malls": f"""
        [out:json][timeout:300];
        ( node["shop"="mall"]({BBOX});
          way["shop"="mall"]({BBOX}); );
        out center;""",
    "supermarkets": f"""
        [out:json][timeout:300];
        ( node["shop"="supermarket"]({BBOX});
          way["shop"="supermarket"]({BBOX}); );
        out center;""",
}


def overpass(query):
    for attempt in range(6):
        url = OVERPASS_MIRRORS[attempt % len(OVERPASS_MIRRORS)]
        r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=360)
        if r.status_code == 200:
            return r.json()["elements"]
        print(f"  {url.split('/')[2]} returned {r.status_code}, trying next mirror in 15s...")
        time.sleep(15)
    raise RuntimeError("All Overpass mirrors refused. 406=blocked request, 429=rate limit, 504=server busy.")


def coords(el):
    if "lat" in el:
        return el["lon"], el["lat"]
    if "center" in el:
        return el["center"]["lon"], el["center"]["lat"]
    return None


print("downloading district polygons...")
geo = requests.get(GEOJSON_URL, timeout=60).json()
districts = {}
for f in geo["features"]:
    districts[f["properties"]["shapeName"]] = prep(shape(f["geometry"]))
print(f"  {len(districts)} districts loaded")

result = {d: {"rail_stations": 0, "malls": 0, "supermarkets": 0,
              "rail_names": [], "mall_names": []} for d in districts}

for kind, q in QUERIES.items():
    print(f"querying OSM for {kind}...")
    elements = overpass(q)
    print(f"  {len(elements)} found, assigning to districts...")
    assigned = 0
    for el in elements:
        c = coords(el)
        if not c:
            continue
        p = Point(c)
        for dname, poly in districts.items():
            if poly.contains(p):
                result[dname][kind] += 1
                name = el.get("tags", {}).get("name")
                if name and kind == "rail_stations" and len(result[dname]["rail_names"]) < 12:
                    result[dname]["rail_names"].append(name)
                if name and kind == "malls" and len(result[dname]["mall_names"]) < 8:
                    result[dname]["mall_names"].append(name)
                assigned += 1
                break
    print(f"  {assigned} inside West Malaysia districts")
    time.sleep(10)  # be polite to the free API between queries

with open("amenities.json", "w") as f:
    json.dump(result, f, ensure_ascii=False)

top = sorted(result.items(), key=lambda kv: -kv[1]["malls"])[:5]
print("\nTop 5 districts by mall count (sanity check):")
for d, v in top:
    print(f"  {d}: {v['malls']} malls, {v['supermarkets']} supermarkets, {v['rail_stations']} rail stations")
print("\nDONE — download amenities.json from the Files panel and upload it to Claude.")
