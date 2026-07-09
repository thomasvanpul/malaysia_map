"""
fetch_amenities_v2.py — extends the amenity fetch to include schools and hospitals.
Run this, then rebuild data.json.
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
]
HEADERS = {"User-Agent": "west-malaysia-district-explorer/2.0 (student project)"}
BBOX = "0.8,99.4,6.9,104.7"

NEW_QUERIES = {
    "schools": f"""
        [out:json][timeout:400];
        ( node["amenity"="school"]({BBOX});
          node["amenity"="university"]({BBOX});
          node["amenity"="college"]({BBOX});
          way["amenity"="school"]({BBOX});
          way["amenity"="university"]({BBOX}); );
        out center tags;""",
    "hospitals": f"""
        [out:json][timeout:400];
        ( node["amenity"="hospital"]({BBOX});
          node["amenity"="clinic"]({BBOX});
          node["healthcare"="hospital"]({BBOX});
          way["amenity"="hospital"]({BBOX}); );
        out center tags;""",
}

def overpass(query):
    for attempt in range(6):
        url = OVERPASS_MIRRORS[attempt % len(OVERPASS_MIRRORS)]
        r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=400)
        if r.status_code == 200:
            return r.json()["elements"]
        print(f"  {url.split('/')[2]}: {r.status_code}, retry {attempt+1}/6 in 15s")
        time.sleep(15)
    raise RuntimeError("All mirrors failed")

def coords(el):
    if "lat" in el: return el["lon"], el["lat"]
    if "center" in el: return el["center"]["lon"], el["center"]["lat"]
    return None

print("Loading district polygons...")
geo = requests.get(GEOJSON_URL, timeout=60).json()
districts = {f["properties"]["shapeName"]: prep(shape(f["geometry"])) for f in geo["features"]}
print(f"  {len(districts)} districts")

print("Loading existing amenities.json...")
with open("/Users/TvpPro/Documents/west_malaysia_map/amenities.json") as f:
    amen = json.load(f)

# Add empty lists for new categories in each district
for d in amen:
    for cat in ("schools", "hospitals"):
        if cat not in amen[d]:
            amen[d][cat] = []

for kind, q in NEW_QUERIES.items():
    print(f"Querying OSM for {kind}...")
    elements = overpass(q)
    print(f"  {len(elements)} found, assigning...")
    assigned = 0
    for el in elements:
        c = coords(el)
        if not c: continue
        p = Point(c)
        t = el.get("tags", {})
        for dname, poly in districts.items():
            if poly.contains(p):
                entry = {
                    "name": t.get("name"),
                    "lat": round(c[1], 5),
                    "lon": round(c[0], 5),
                    "type": t.get("amenity") or t.get("healthcare"),
                }
                if t.get("website") or t.get("contact:website"):
                    entry["website"] = t.get("website") or t.get("contact:website")
                if t.get("phone") or t.get("contact:phone"):
                    entry["phone"] = t.get("phone") or t.get("contact:phone")
                amen.get(dname, {k: [] for k in ["rail_stations","malls","supermarkets","schools","hospitals"]})[kind].append(entry)
                assigned += 1
                break
    print(f"  {assigned} assigned to West Malaysia districts")
    time.sleep(10)

with open("/Users/TvpPro/Documents/west_malaysia_map/amenities.json", "w") as f:
    json.dump(amen, f, ensure_ascii=False)

import os
print(f"\namenities.json: {os.path.getsize('/Users/TvpPro/Documents/west_malaysia_map/amenities.json')//1024} KB")
# Sanity check
kl = amen.get("Kuala Lumpur", {})
print(f"KL schools: {len(kl.get('schools',[]))} | hospitals: {len(kl.get('hospitals',[]))}")
