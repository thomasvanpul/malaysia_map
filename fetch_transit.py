"""
fetch_transit.py — pulls rail transit routes (MRT/LRT/monorail/KTM) from OSM
for West Malaysia and stitches them into full ordered coordinate lists.

Output: transit.json
  { "routes": [ { name, ref, kind, color, coords: [[lon,lat],...] }, ... ] }
"""

import json
import time
import requests

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
HEADERS = {"User-Agent": "west-malaysia-district-explorer/1.2 (student project)"}
BBOX = "0.8,99.4,6.9,104.7"

QUERY = f"""
[out:json][timeout:600];
(
  relation["type"="route"]["route"~"^(subway|light_rail|monorail|train|tram)$"]({BBOX});
);
out body;
>>;
out geom;
"""

COLOR_MAP = {
    "KJ": "#e21a2c",
    "AG": "#f68b1f",
    "SP": "#f68b1f",
    "MR": "#8dc63f",
    "KG": "#00a651",
    "PY": "#fdb913",
    "SBK": "#00a651",
    "SSP": "#fdb913",
    "KA": "#7e57c2",
    "KB": "#0072ce",
    "BRT": "#00b4d8",
    "ETS": "#8b4513",
    "KLIA Ekspres": "#c8102e",
    "KLIA Transit": "#00539b",
}


def overpass(query):
    for attempt in range(6):
        url = OVERPASS_MIRRORS[attempt % len(OVERPASS_MIRRORS)]
        print(f"  trying {url.split('/')[2]} (attempt {attempt+1})...")
        r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=600)
        if r.status_code == 200:
            return r.json()
        print(f"    got {r.status_code}, backing off 20s")
        time.sleep(20)
    raise RuntimeError("Overpass mirrors all refused; try again later.")


def pick_color(tags):
    ref = (tags.get("ref") or "").strip()
    if ref in COLOR_MAP:
        return COLOR_MAP[ref]
    prefix = "".join(c for c in ref if c.isalpha())
    if prefix in COLOR_MAP:
        return COLOR_MAP[prefix]
    if tags.get("colour"):
        c = tags["colour"]
        return c if c.startswith("#") else "#" + c
    name = (tags.get("name") or "").lower()
    for key, color in COLOR_MAP.items():
        if key.lower() in name:
            return color
    return "#666"


def stitch(way_geoms):
    if not way_geoms:
        return []
    chains = [list(way_geoms[0])]
    for w in way_geoms[1:]:
        if not w:
            continue
        last_chain = chains[-1]
        last = last_chain[-1]
        first_of_w = w[0]
        last_of_w = w[-1]
        thr = 0.001
        def near(a, b):
            return abs(a[0]-b[0]) < thr and abs(a[1]-b[1]) < thr
        if near(last, first_of_w):
            last_chain.extend(w[1:])
        elif near(last, last_of_w):
            last_chain.extend(reversed(w[:-1]))
        elif near(last_chain[0], first_of_w):
            chains[-1] = list(reversed(w[1:])) + last_chain
        elif near(last_chain[0], last_of_w):
            chains[-1] = list(w[:-1]) + last_chain
        else:
            chains.append(list(w))
    return chains


print("querying OSM for rail routes...")
data = overpass(QUERY)
elements = data["elements"]

ways = {e["id"]: [(g["lon"], g["lat"]) for g in e["geometry"]]
        for e in elements if e["type"] == "way" and "geometry" in e}
relations = [e for e in elements if e["type"] == "relation"]
print(f"  {len(relations)} route relations, {len(ways)} ways")

routes = []
skipped_reason = {"no_ways": 0, "too_short": 0}
for rel in relations:
    tags = rel.get("tags", {})
    name = tags.get("name") or tags.get("ref") or "unnamed"
    kind = tags.get("route", "rail")
    if tags.get("service") in ("night", "special"):
        continue
    member_ways = [m["ref"] for m in rel.get("members", []) if m["type"] == "way"]
    geoms = [ways[wid] for wid in member_ways if wid in ways]
    if not geoms:
        skipped_reason["no_ways"] += 1
        continue
    chains = stitch(geoms)
    total_pts = sum(len(c) for c in chains)
    if total_pts < 5:
        skipped_reason["too_short"] += 1
        continue
    routes.append({
        "name": name,
        "ref": tags.get("ref"),
        "kind": kind,
        "color": pick_color(tags),
        "chains": chains,
    })

with open("transit.json", "w") as f:
    json.dump({"routes": routes}, f, ensure_ascii=False)

print(f"\nkept {len(routes)} routes | skipped: {skipped_reason}")
print("\nTop 15 routes by point count:")
routes.sort(key=lambda r: -sum(len(c) for c in r["chains"]))
for r in routes[:15]:
    pts = sum(len(c) for c in r["chains"])
    chains = len(r["chains"])
    print(f"  {r['color']} {(r['ref'] or ''):8} {r['kind']:12} {pts:5} pts / {chains} chain(s) — {r['name'][:60]}")

import os
print(f"\ntransit.json: {os.path.getsize('transit.json')//1024} KB")
