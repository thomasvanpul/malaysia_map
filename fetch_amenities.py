"""fetch_amenities.py — pulls OSM amenities for all of Malaysia (Peninsular + Sabah/
Sarawak), keeps coordinates.

Output: amenities.json
  { district_name: { rail_stations: [{name,lat,lon},...],
                     malls:         [{name,lat,lon},...],
                     supermarkets:  [{name,lat,lon},...] } }

Point-in-polygon assignment uses the local geoBoundaries file (same one build_data.py
reads) — previously this fetched from the live site over HTTP, which silently broke
whenever the site URL changed (it did, after a repo rename) and added a needless
network dependency for data that's already sitting right next to this script.
"""

import json
import time
import requests
from shapely.geometry import shape, Point
from shapely.prepared import prep

GEOJSON_FILE = "geoBoundaries-MYS-ADM2_simplified.geojson"

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
HEADERS = {"User-Agent": "west-malaysia-district-explorer/1.2 (student project)"}

# Two disjoint regions rather than one giant bbox spanning the South China Sea between
# them, which would waste Overpass query time scanning empty ocean.
PENINSULAR_BBOX = "0.8,99.4,6.9,104.7"
EAST_MALAYSIA_BBOX = "0.8,109.4,7.5,119.5"  # Sabah + Sarawak + Labuan

def build_queries(bbox):
    return {
        "rail_stations": f"""
            [out:json][timeout:300];
            ( node["railway"="station"]({bbox});
              way["railway"="station"]({bbox}); );
            out center;""",
        "malls": f"""
            [out:json][timeout:300];
            ( node["shop"="mall"]({bbox});
              way["shop"="mall"]({bbox}); );
            out center;""",
        "supermarkets": f"""
            [out:json][timeout:300];
            ( node["shop"="supermarket"]({bbox});
              way["shop"="supermarket"]({bbox}); );
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

print("loading district polygons...")
with open(GEOJSON_FILE) as f:
    geo = json.load(f)
districts = {f["properties"]["shapeName"]: prep(shape(f["geometry"]))
             for f in geo["features"]}
print(f"  {len(districts)} districts loaded")

result = {d: {"rail_stations": [], "malls": [], "supermarkets": []} for d in districts}

for region_name, bbox in [("Peninsular", PENINSULAR_BBOX), ("East Malaysia", EAST_MALAYSIA_BBOX)]:
    for kind, q in build_queries(bbox).items():
        print(f"querying OSM for {kind} in {region_name}...")
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
                    result[dname][kind].append({
                        "name": name,
                        "lat": round(c[1], 5),
                        "lon": round(c[0], 5),
                    })
                    assigned += 1
                    break
        print(f"  {assigned} inside {region_name} districts")
        time.sleep(10)

with open("amenities.json", "w") as f:
    json.dump(result, f, ensure_ascii=False)

top = sorted(result.items(), key=lambda kv: -len(kv[1]["malls"]))[:5]
print("\nTop 5 districts by mall count (sanity check):")
for d, v in top:
    print(f"  {d}: {len(v['malls'])} malls, {len(v['supermarkets'])} supermarkets, {len(v['rail_stations'])} rail stations")

import os
print(f"\namenities.json size: {os.path.getsize('amenities.json')//1024} KB")
print("DONE.")
