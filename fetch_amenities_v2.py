"""fetch_amenities_v2.py — extends the amenity fetch to include schools and hospitals,
across all of Malaysia (Peninsular + Sabah/Sarawak).

Run this, then rebuild data.json.
"""

import json
import time
import requests
from shapely.geometry import shape, Point
from shapely.prepared import prep

GEOJSON_FILE = "geoBoundaries-MYS-ADM2_simplified.geojson"
AMENITIES_FILE = "amenities.json"

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
HEADERS = {"User-Agent": "west-malaysia-district-explorer/2.1 (student project)"}

PENINSULAR_BBOX = "0.8,99.4,6.9,104.7"
EAST_MALAYSIA_BBOX = "0.8,109.4,7.5,119.5"  # Sabah + Sarawak + Labuan

def build_queries(bbox):
    return {
        "schools": f"""
            [out:json][timeout:400];
            ( node["amenity"="school"]({bbox});
              node["amenity"="university"]({bbox});
              node["amenity"="college"]({bbox});
              way["amenity"="school"]({bbox});
              way["amenity"="university"]({bbox}); );
            out center tags;""",
        "hospitals": f"""
            [out:json][timeout:400];
            ( node["amenity"="hospital"]({bbox});
              node["amenity"="clinic"]({bbox});
              node["healthcare"="hospital"]({bbox});
              way["amenity"="hospital"]({bbox}); );
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
with open(GEOJSON_FILE) as f:
    geo = json.load(f)
districts = {f["properties"]["shapeName"]: prep(shape(f["geometry"])) for f in geo["features"]}
print(f"  {len(districts)} districts")

print("Loading existing amenities.json...")
with open(AMENITIES_FILE) as f:
    amen = json.load(f)

# Ensure EVERY district (including ones amenities.json has never seen before, e.g. the
# newly-added Sabah/Sarawak districts) has a real entry before assignment. The previous
# version used amen.get(dname, {...default...}) inside the assignment loop, which for any
# district missing from the file returns a throwaway dict that's never written back —
# results for brand-new districts were silently discarded.
for d in districts:
    if d not in amen:
        amen[d] = {"rail_stations": [], "malls": [], "supermarkets": [], "schools": [], "hospitals": []}
    for cat in ("schools", "hospitals"):
        if cat not in amen[d]:
            amen[d][cat] = []

for region_name, bbox in [("Peninsular", PENINSULAR_BBOX), ("East Malaysia", EAST_MALAYSIA_BBOX)]:
    for kind, q in build_queries(bbox).items():
        print(f"Querying OSM for {kind} in {region_name}...")
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
                    amen[dname][kind].append(entry)
                    assigned += 1
                    break
        print(f"  {assigned} assigned to {region_name} districts")
        time.sleep(10)

with open(AMENITIES_FILE, "w") as f:
    json.dump(amen, f, ensure_ascii=False)

import os
print(f"\namenities.json: {os.path.getsize(AMENITIES_FILE)//1024} KB")

kl = amen.get("Kuala Lumpur", {})
kk = amen.get("Kota Kinabalu", {})
print(f"KL schools: {len(kl.get('schools',[]))} | hospitals: {len(kl.get('hospitals',[]))}")
print(f"Kota Kinabalu schools: {len(kk.get('schools',[]))} | hospitals: {len(kk.get('hospitals',[]))}")
