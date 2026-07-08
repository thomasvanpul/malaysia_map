"""
enrich_amenities.py — re-fetches amenities with full OSM tags AND looks up
Wikimedia Commons photos via Wikidata for amenities that have wikidata tags.

Reads:  live geoBoundaries (from GitHub Pages)
Writes: amenities.json

Adds per amenity (where available in OSM):
  address, website, phone, opening_hours, brand, wikidata id
Adds per amenity (via Wikidata batch query):
  image_url (Wikimedia Commons thumbnail, 400px wide)
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
HEADERS = {"User-Agent": "west-malaysia-district-explorer/1.3 (student project)"}
BBOX = "0.8,99.4,6.9,104.7"


def q_full(tag_key, tag_val):
    """Ask Overpass for full tags (not just name/coord) so we get website/hours/etc."""
    return f"""
[out:json][timeout:400];
( node["{tag_key}"="{tag_val}"]({BBOX});
  way["{tag_key}"="{tag_val}"]({BBOX}); );
out center tags;"""


QUERIES = {
    "rail_stations": q_full("railway", "station"),
    "malls": q_full("shop", "mall"),
    "supermarkets": q_full("shop", "supermarket"),
}


def overpass(query):
    for attempt in range(6):
        url = OVERPASS_MIRRORS[attempt % len(OVERPASS_MIRRORS)]
        r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=400)
        if r.status_code == 200:
            return r.json()["elements"]
        print(f"  {url.split('/')[2]} returned {r.status_code}, retry in 15s")
        time.sleep(15)
    raise RuntimeError("Overpass refused all mirrors")


def coords(el):
    if "lat" in el:
        return el["lon"], el["lat"]
    if "center" in el:
        return el["center"]["lon"], el["center"]["lat"]
    return None


def build_address(tags):
    """Assemble a readable address from OSM addr:* tags."""
    parts = []
    hn = tags.get("addr:housenumber")
    st = tags.get("addr:street")
    if hn and st:
        parts.append(f"{hn} {st}")
    elif st:
        parts.append(st)
    for k in ("addr:suburb", "addr:city", "addr:state", "addr:postcode"):
        v = tags.get(k)
        if v:
            parts.append(v)
    return ", ".join(parts) or None


print("downloading district polygons...")
geo = requests.get(GEOJSON_URL, timeout=60).json()
districts = {f["properties"]["shapeName"]: prep(shape(f["geometry"]))
             for f in geo["features"]}
print(f"  {len(districts)} districts")

result = {d: {"rail_stations": [], "malls": [], "supermarkets": []} for d in districts}
wikidata_ids = set()  # collect all Wikidata IDs to batch-lookup later

for kind, q in QUERIES.items():
    print(f"querying OSM for {kind}...")
    elements = overpass(q)
    print(f"  {len(elements)} found")
    assigned = 0
    for el in elements:
        c = coords(el)
        if not c:
            continue
        p = Point(c)
        for dname, poly in districts.items():
            if poly.contains(p):
                t = el.get("tags", {})
                entry = {
                    "name": t.get("name"),
                    "lat": round(c[1], 5),
                    "lon": round(c[0], 5),
                }
                # Optional fields — only include when present, keeps JSON smaller
                for src, dst in [
                    ("website", "website"), ("contact:website", "website"),
                    ("phone", "phone"), ("contact:phone", "phone"),
                    ("opening_hours", "hours"),
                    ("brand", "brand"),
                    ("operator", "operator"),
                    ("wikidata", "wikidata"),
                ]:
                    if src in t and dst not in entry:
                        entry[dst] = t[src]
                addr = build_address(t)
                if addr:
                    entry["address"] = addr
                if entry.get("wikidata"):
                    wikidata_ids.add(entry["wikidata"])
                result[dname][kind].append(entry)
                assigned += 1
                break
    print(f"  {assigned} inside West Malaysia")
    time.sleep(10)

print(f"\n{len(wikidata_ids)} unique Wikidata IDs found across all amenities")

# Wikidata batch lookup for images
# We use the SPARQL endpoint since it can return P18 (image) for many IDs at once.
def wikidata_images(ids):
    """Return dict {Q_id: commons_filename} for IDs that have a P18 image."""
    if not ids:
        return {}
    print(f"  looking up {len(ids)} Wikidata IDs in batches of 50...")
    out = {}
    ids = list(ids)
    for i in range(0, len(ids), 50):
        batch = ids[i:i+50]
        values = " ".join(f"wd:{q}" for q in batch)
        query = f"""
SELECT ?item ?image WHERE {{
  VALUES ?item {{ {values} }}
  ?item wdt:P18 ?image .
}}"""
        r = requests.get(
            "https://query.wikidata.org/sparql",
            params={"query": query, "format": "json"},
            headers={**HEADERS, "Accept": "application/sparql-results+json"},
            timeout=120,
        )
        if r.status_code != 200:
            print(f"    batch {i//50}: HTTP {r.status_code}, skipping")
            time.sleep(10)
            continue
        for row in r.json()["results"]["bindings"]:
            qid = row["item"]["value"].rsplit("/", 1)[-1]
            img_url = row["image"]["value"]
            # img_url is a Commons file URL; we'll build a thumbnail URL instead
            filename = img_url.rsplit("/", 1)[-1]
            out[qid] = filename
        time.sleep(2)  # be polite
        print(f"    batch {i//50+1}/{(len(ids)-1)//50+1} done, {len(out)} images so far")
    return out


images = wikidata_images(wikidata_ids)
print(f"\n{len(images)} of {len(wikidata_ids)} Wikidata entities have images")

def commons_thumb(filename, width=400):
    """Build the Wikimedia Commons Special:FilePath thumbnail URL."""
    from urllib.parse import quote
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(filename)}?width={width}"

# Attach image URLs to amenities that have wikidata IDs with photos
n_attached = 0
for district_data in result.values():
    for cat in ("rail_stations", "malls", "supermarkets"):
        for e in district_data[cat]:
            qid = e.get("wikidata")
            if qid and qid in images:
                e["image"] = commons_thumb(images[qid])
                n_attached += 1

print(f"attached image URL to {n_attached} amenities")

with open("amenities.json", "w") as f:
    json.dump(result, f, ensure_ascii=False)

import os
print(f"\namenities.json size: {os.path.getsize('amenities.json')//1024} KB")

# Sanity: how many amenities have each optional field?
totals = {"total":0, "name":0, "website":0, "phone":0, "hours":0, "address":0, "wikidata":0, "image":0}
for d in result.values():
    for cat in ("rail_stations","malls","supermarkets"):
        for e in d[cat]:
            totals["total"] += 1
            for k in ("name","website","phone","hours","address","wikidata","image"):
                if k in e and e[k]:
                    totals[k] += 1
print("\nField coverage:")
for k, v in totals.items():
    pct = f"{100*v/max(1,totals['total']):.0f}%" if k != "total" else ""
    print(f"  {k:10} {v:5} {pct}")
