"""
fetch_amenities.py — pulls OSM amenities for West Malaysia, keeps coordinates.

Output: amenities.json
  { district_name: { rail_stations: [{name,lat,lon},...],
                     malls:         [{name,lat,lon},...],
                     supermarkets:  [{name,lat,lon},...] } }

Point-in-polygon assignment uses the same geoBoundaries file the site uses,
fetched from the live GitHub Pages so a boundary change on the site is
automatically reflected here.
"""

import json
import time
import requests
from shapely.geometry import shape, Point
from shapely.prepared import prep

SITE = "https://thomasvanpul.github.io/west_malaysia_map"
GEOJSON_URL = SITE + "/geoBoundaries-MYS-ADM2_simplified.geojson"

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
HEADERS = {"User-Agent": "west-malaysia-district-explorer/1.1 (student project)"}
BBOX = "0.8,99.4,6.9,104.7"  # West Malaysia bounding box

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
        print(f"  {url.split('/')[2]} returned {r.status_code}, next mirror in 15s...")
        time.sleep(15)
    raise RuntimeError("All Overpass mirrors refused. 406=blocked, 429=rate-limited, 504=busy.")


def coords(el):
    if "lat" in el:
        return el["lon"], el["lat"]
    if "center" in el:
        return el["center"]["lon"], el["center"]["lat"]
    return None


print("downloading district polygons...")
geo = requests.get(GEOJSON_URL, timeout=60).json()
districts = {f["properties"]["shapeName"]: prep(shape(f["geometry"]))
             for f in geo["features"]}
print(f"  {len(districts)} districts loaded")

result = {d: {"rail_stations": [], "malls": [], "supermarkets": []} for d in districts}

for kind, q in QUERIES.items():
    print(f"querying OSM for {kind}...")
    elements = overpass(q)
    print(f"  {len(elements)} found, assigning...")
    assigned = 0
    for el in elements:
        c = coords(el)
        if not c:
            continue
        p = Point(c)
        for dname, poly in districts.items():
            if poly.contains(p):
                name = el.get("tags", {}).get("name")
                # store coord rounded to 5dp (~1m precision) to keep file small
                result[dname][kind].append({
                    "name": name,
                    "lat": round(c[1], 5),
                    "lon": round(c[0], 5),
                })
                assigned += 1
                break
    print(f"  {assigned} inside West Malaysia districts")
    time.sleep(10)

with open("amenities.json", "w") as f:
    json.dump(result, f, ensure_ascii=False)

top = sorted(result.items(), key=lambda kv: -len(kv[1]["malls"]))[:5]
print("\nTop 5 districts by mall count (sanity check):")
for d, v in top:
    print(f"  {d}: {len(v['malls'])} malls, {len(v['supermarkets'])} supermarkets, {len(v['rail_stations'])} rail stations")

# rough file size
import os
print(f"\namenities.json size: {os.path.getsize('amenities.json')//1024} KB")
print("DONE.")
