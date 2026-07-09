"""
fetch_teduh.py — fetches ALL 24,712 TEDUH licensed private housing projects 
in one paginated pass, then filters to West Malaysia states.

The TEDUH API ignores the negeri (state) filter parameter — it always returns
all projects. So we fetch everything once and filter locally.

~1,236 pages at 100 per page with 0.3s delay = ~6 minutes total.
"""

import json
import time
import urllib.request
from datetime import datetime

WEST_MALAYSIA = {
    "01": "Johor", "02": "Kedah", "03": "Kelantan", "04": "Melaka",
    "05": "Negeri Sembilan", "06": "Pahang", "07": "Perak", "08": "Perlis",
    "09": "Pulau Pinang", "10": "Selangor", "11": "Terengganu",
    "14": "W.P. Kuala Lumpur", "15": "W.P. Labuan", "16": "W.P. Putrajaya",
}

STATUS_MAP = {
    "0": "Belum Mula", "1": "Lancar", "2": "Sakit", "3": "Lewat",
    "5": "Siap Dengan CCC", "7": "Siap Dengan CFO", "B": "Permit Dibatalkan",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120",
    "Accept": "application/json",
    "Referer": "https://teduh.kpkt.gov.my/semakan-status-kemajuan",
}

BASE = "https://teduh.kpkt.gov.my/api/projek-swasta"


def fetch_page(page):
    url = f"{BASE}?page={page}&per_page=100&q=&search_type=projek"
    req = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


def clean(p):
    dev = p.get("pemaju") or {}
    sc = p.get("kod_negeri_id", "")
    lat = p.get("latitud")
    lon = p.get("longitud")
    try:
        lat = float(lat) if lat else None
        lon = float(lon) if lon else None
    except:
        lat = lon = None
    return {
        "id": p.get("id"),
        "name": p.get("nama"),
        "phase": p.get("kod_fasa"),
        "state_code": sc,
        "state": WEST_MALAYSIA.get(sc, ""),
        "lat": lat,
        "lon": lon,
        "status": STATUS_MAP.get(p.get("status_projek", ""), p.get("status_projek", "")),
        "expected_completion": p.get("tarikh_jangkaan_ccc"),
        "bumi_quota_pct": p.get("peratus_kuotabumi"),
        "developer": {
            "name": dev.get("nama"),
            "phone": dev.get("telefon"),
            "phone2": dev.get("telefon2"),
            "email": dev.get("emel"),
            "website": dev.get("alamat_web"),
            "ssm": dev.get("no_ssm"),
            "address": " ".join(filter(None, [
                dev.get("alamat_perniagaan1"),
                dev.get("alamat_perniagaan2"),
                str(dev.get("poskod_perniagaan") or ""),
            ])).strip() or None,
        },
    }


# Fetch first page to get pagination info
print("Fetching page 1...")
raw = fetch_page(1)
proj_meta = raw.get("projects", {})
last_page = proj_meta.get("last_page", 1)
total_api = proj_meta.get("total", 0)
print(f"Total in API: {total_api} | Pages: {last_page}")

all_projects = []

def process_page(raw):
    proj_meta = raw.get("projects", {})
    data = proj_meta.get("data", [])
    for p in data:
        if p.get("kod_negeri_id") in WEST_MALAYSIA:
            all_projects.append(clean(p))

process_page(raw)
time.sleep(0.3)

for page in range(2, last_page + 1):
    try:
        raw = fetch_page(page)
        process_page(raw)
        if page % 50 == 0 or page == last_page:
            print(f"  page {page}/{last_page} | WM projects so far: {len(all_projects)}")
        time.sleep(0.3)
    except Exception as e:
        print(f"  ERROR page {page}: {e} — retrying in 5s")
        time.sleep(5)
        try:
            raw = fetch_page(page)
            process_page(raw)
            time.sleep(0.3)
        except Exception as e2:
            print(f"  SKIPPED page {page}: {e2}")

# Stats
with_coords = sum(1 for p in all_projects if p["lat"] and p["lon"])
status_counts = {}
for p in all_projects:
    status_counts[p["status"]] = status_counts.get(p["status"], 0) + 1

output = {
    "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "total": len(all_projects),
    "with_coordinates": with_coords,
    "projects": all_projects,
}

with open("teduh_projects.json", "w") as f:
    json.dump(output, f, ensure_ascii=False)

print(f"\n=== DONE ===")
print(f"West Malaysia projects: {len(all_projects)}")
print(f"With coordinates: {with_coords} ({100*with_coords//max(1,len(all_projects))}%)")
print("By status:")
for s, n in sorted(status_counts.items(), key=lambda x: -x[1]):
    print(f"  {s}: {n}")
import os
print(f"\nteduh_projects.json: {os.path.getsize('teduh_projects.json')//1024} KB")
