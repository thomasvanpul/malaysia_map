"""dedupe_transit.py — dedup route variants + strict Singapore filter."""
import json, re

# Peninsular Malaysia proper starts at lat ~1.2 (Johor's southern tip is ~1.26).
# Singapore is 1.16-1.47 — overlaps slightly. Use a country-name blacklist for
# routes with lat<1.5 to catch Singapore lines whose top edge crosses into JB.
SG_KEYWORDS = re.compile(r"\b(mrt (east|north|circle|downtown|thomson|jurong)|"
                          r"punggol|sengkang|bukit panjang|sentosa|singapore|"
                          r"north east line|north south line|east west line|"
                          r"jurong regional|thomson.?east coast)\b", re.I)

# Also skip airport-internal skytrains — they're not useful at district scale
AIRPORT_SHUTTLE = re.compile(r"\b(skytrain|aerotrain|sentosa express|funicular)\b", re.I)


def is_malaysian_transit(r):
    """Reject if route name matches known Singapore lines or airport shuttles."""
    name = r["name"] or ""
    if SG_KEYWORDS.search(name):
        return False
    if AIRPORT_SHUTTLE.search(name):
        return False
    # Also reject if the whole route sits south of lat 1.5 (Singapore proper)
    lats = [p[1] for c in r["chains"] for p in c]
    if lats and max(lats) < 1.5:
        return False
    return True


def canonical_name(name):
    n = name.lower()
    n = re.sub(r"\([^)]*\)", " ", n)
    n = re.sub(r"\s*(?:→|←|-->|<-->|<--|—|–|-|<->|=>|\bto\b|\bke\b)\s*", "|", n)
    n = re.sub(r"\s+", " ", n).strip()
    parts = sorted(p.strip() for p in n.split("|") if p.strip())
    return "|".join(parts)


data = json.load(open("transit.json"))
routes = data["routes"]
print(f"input: {len(routes)} routes")

routes = [r for r in routes if is_malaysian_transit(r)]
print(f"after MY-only filter: {len(routes)}")

buckets = {}
for r in routes:
    key = canonical_name(r["name"])
    total_pts = sum(len(c) for c in r["chains"])
    if key not in buckets or total_pts > buckets[key][0]:
        buckets[key] = (total_pts, r)
routes = [v[1] for v in buckets.values()]
print(f"after dedupe: {len(routes)}")

for r in routes:
    r["chains"] = [[[round(lon, 4), round(lat, 4)] for lon, lat in c] for c in r["chains"]]

json.dump({"routes": routes}, open("transit.json", "w"), ensure_ascii=False)

import os
print(f"\ntransit.json: {os.path.getsize('transit.json')//1024} KB\n")
routes.sort(key=lambda r: -sum(len(c) for c in r["chains"]))
for r in routes:
    pts = sum(len(c) for c in r["chains"])
    print(f"  {r['color']} {(r['ref'] or '-'):8} {r['kind']:12} {pts:5} pts — {r['name'][:70]}")
