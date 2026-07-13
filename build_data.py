"""
build_data.py — rebuilds data.json for the West Malaysia District Explorer.

What it does, in order:
  1. Downloads 3 parquet files from DOSM (or uses local copies with --local)
  2. Cleans district names (both DOSM naming styles + the 'Hulu' data-entry error)
  3. Joins stats onto the geoBoundaries district polygons
  4. Validates the join — fails LOUDLY if any district doesn't match
  5. Writes data.json for the site

Run:  python build_data.py            (downloads fresh data)
      python build_data.py --local    (uses parquet files already in this folder)

Requires: pip install pandas fastparquet requests
"""

import json
import sys
import pandas as pd

# ---------------------------------------------------------------- sources
# NOTE: population URL is confirmed working. VERIFY the income/poverty URLs
# once: open the catalogue pages below, right-click the parquet download
# button, "Copy link address", and correct here if different.
#   https://open.dosm.gov.my/data-catalogue/hh_income_district
#   https://open.dosm.gov.my/data-catalogue/hh_poverty_district
SOURCES = {
    "population_district.parquet": "https://storage.dosm.gov.my/population/population_district.parquet",
    "hh_income_district.parquet": "https://storage.dosm.gov.my/hies/hh_income_district.parquet",
    "hh_poverty_district.parquet": "https://storage.dosm.gov.my/hies/hh_poverty_district.parquet",
}

GEOJSON_FILE = "geoBoundaries-MYS-ADM2_simplified.geojson"

WEST = ['Johor','Kedah','Kelantan','Melaka','Negeri Sembilan','Pahang','Perak','Perlis',
        'Pulau Pinang','Selangor','Terengganu','W.P. Kuala Lumpur','W.P. Putrajaya',
        'Sabah','Sarawak','W.P. Labuan']  # name kept as WEST for min diff; now covers all Malaysia

# Covers BOTH DOSM naming styles (population file vs income/poverty files)
CLEAN = {
    "Cameron Highland": "Cameron Highlands",
    "Sp Selatan": "Seberang Perai Selatan",
    "Sp Tengah": "Seberang Perai Tengah",
    "Sp Utara": "Seberang Perai Utara",
    "Larut Dan Matang": "Larut dan Matang",
    "W.P. Kuala Lumpur": "Kuala Lumpur",
    "W.P. Labuan": "Labuan",
    "Kulai": "Kulaijaya",
    "Tangkak": "Ledang",
    "Nabawan": "Nabawan / Persiangan",
    "S.P. Selatan": "Seberang Perai Selatan",
    "S.P.Tengah": "Seberang Perai Tengah",
    "S.P.Utara": "Seberang Perai Utara",
    "Larut & Matang": "Larut dan Matang",
    "Hulu": "Hulu Terengganu",  # DOSM data-entry error (truncated, 2024 income row)
    "Lubok antu": "Lubok Antu",  # capitalization mismatch vs geoBoundaries
    # Sarawak/Sabah districts elevated from sub-district status (2021-2022) after this
    # boundary dataset was published — geoBoundaries has no separate polygon for them yet,
    # so their DOSM stats are merged back into the parent district they were carved from.
    # Population is summed correctly (see MERGED_DISTRICTS aggregation below); income/poverty
    # medians for these merged districts are a simple (non population-weighted) average of
    # the parent + sub-district values — a documented approximation affecting only these 6
    # of 159 districts, not worth a full weighted-aggregation pipeline for.
    "Gedong": "Simunjan",       # elevated 2021, was part of Simunjan
    "Sebuyau": "Simunjan",      # elevated 2021, was part of Simunjan
    "Pantu": "Sri Aman",        # elevated 2021, was part of Sri Aman
    "Lingga": "Sri Aman",       # elevated 2021, was part of Sri Aman
    "Siburan": "Serian",        # elevated Nov 2021, was part of Serian
    "Membakut": "Beaufort",     # Sabah sub-district, part of Beaufort
}
MERGED_DISTRICTS = {"Simunjan", "Sri Aman", "Serian", "Beaufort"}  # targets of the above merges

KNOWN_NO_POLYGON = {"W.P. Putrajaya"}  # stats exist, boundary file has no shape


def download_all():
    import requests
    for fname, url in SOURCES.items():
        print(f"downloading {fname} ...")
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        with open(fname, "wb") as f:
            f.write(r.content)
        print(f"  ok ({len(r.content)//1024} KB)")


def load(fname):
    df = pd.read_parquet(fname)
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["state"].isin(WEST)].copy()
    df["district_clean"] = df["district"].replace(CLEAN)
    return df


def main():
    if "--local" not in sys.argv:
        download_all()

    pop = load("population_district.parquet")
    inc = load("hh_income_district.parquet")
    pov = load("hh_poverty_district.parquet")

    with open(GEOJSON_FILE) as f:
        geo = json.load(f)
    geo_names = {ft["properties"]["shapeName"] for ft in geo["features"]}

    # ---- validation: fail loudly on ANY new name mismatch --------------
    problems = []
    for label, df in [("population", pop), ("income", inc), ("poverty", pov)]:
        bad = set(df["district_clean"].unique()) - geo_names - KNOWN_NO_POLYGON
        if bad:
            problems.append(f"{label}: unmatched districts {sorted(bad)}")
    if problems:
        sys.exit("JOIN VALIDATION FAILED — fix CLEAN mapping first:\n" + "\n".join(problems))

    # ---- build stats per district --------------------------------------
    latest_pop = pop["date"].max()
    feats = [ft for ft in geo["features"]
             if ft["properties"]["shapeName"] in set(pop["district_clean"])]

    for ft in feats:
        d = ft["properties"]["shapeName"]
        g = pop[(pop["district_clean"] == d) & (pop["date"] == latest_pop)]
        # sum() not iloc[0]: for MERGED_DISTRICTS this correctly combines the parent
        # district's row with its merged-in sub-district's row; for every other district
        # there's only ever one matching row so sum() == that single value, unchanged.
        pick = lambda sx, ag, eth: float(
            g[(g["sex"] == sx) & (g["age"] == ag) & (g["ethnicity"] == eth)]["population"].sum())
        eth_rows = g[(g["sex"] == "both") & (g["age"] == "overall") & (g["ethnicity"] != "overall")]
        eth_sums = {}
        for r in eth_rows.itertuples():
            eth_sums[r.ethnicity] = eth_sums.get(r.ethnicity, 0.0) + float(r.population)
        tr_rows = pop[(pop["district_clean"] == d) & (pop["sex"] == "both")
                 & (pop["age"] == "overall") & (pop["ethnicity"] == "overall")]
        tr_sums = {}
        for r in tr_rows.itertuples():
            y = int(r.date.year)
            tr_sums[y] = tr_sums.get(y, 0.0) + float(r.population)
        s = {
            "total": pick("both", "overall", "overall"),
            "male": pick("male", "overall", "overall"),
            "female": pick("female", "overall", "overall"),
            "ethnicity": eth_sums,
            "trend": sorted([[y, v] for y, v in tr_sums.items()]),
            "state": g["state"].iloc[0],
        }
        di = inc[inc["district_clean"] == d].sort_values("date")
        if len(di):
            if d in MERGED_DISTRICTS:
                # simple average across merged sub-district rows for the latest date
                # (documented approximation — see CLEAN dict comment above)
                latest_date = di["date"].max()
                latest_rows = di[di["date"] == latest_date]
                s["income_mean"] = int(latest_rows["income_mean"].mean())
                s["income_median"] = int(latest_rows["income_median"].mean())
                s["income_year"] = int(latest_date.year)
                trend_by_year = di.groupby(di["date"].dt.year)["income_median"].mean()
                s["income_trend"] = [[int(y), int(v)] for y, v in trend_by_year.items()]
            else:
                last = di.iloc[-1]
                s["income_mean"] = int(last["income_mean"])
                s["income_median"] = int(last["income_median"])
                s["income_year"] = int(last["date"].year)
                s["income_trend"] = [[int(r.date.year), int(r.income_median)] for r in di.itertuples()]
        dp = pov[pov["district_clean"] == d].sort_values("date")
        if len(dp):
            if d in MERGED_DISTRICTS:
                latest_date = dp["date"].max()
                latest_rows = dp[dp["date"] == latest_date]
                s["poverty_absolute"] = float(latest_rows["poverty_absolute"].mean())
                s["poverty_relative"] = float(latest_rows["poverty_relative"].mean())
            else:
                last = dp.iloc[-1]
                s["poverty_absolute"] = float(last["poverty_absolute"])
                s["poverty_relative"] = float(last["poverty_relative"])
        ft["properties"]["stats"] = s

    # merge amenities (OSM-derived, generated separately by fetch_amenities.py)
    # amenities.json format: {district: {rail_stations:[{name,lat,lon},...], malls:[...], supermarkets:[...]}}
    try:
        with open("amenities.json") as f:
            amen = json.load(f)
        for ft in feats:
            a = amen.get(ft["properties"]["shapeName"])
            if a:
                # emit counts alongside arrays so old panel/compare code still works
                ft["properties"]["stats"]["amenities"] = {
                    "rail_stations": len(a.get("rail_stations", [])),
                    "malls":         len(a.get("malls", [])),
                    "supermarkets":  len(a.get("supermarkets", [])),
                    "rail_names":    [x["name"] for x in a.get("rail_stations", []) if x.get("name")][:12],
                    "mall_names":    [x["name"] for x in a.get("malls", []) if x.get("name")][:8],
                    "schools":       len(a.get("schools", [])),
                    "hospitals":     len(a.get("hospitals", [])),
                    # full coord arrays for map markers
                    "rail_points":        a.get("rail_stations", []),
                    "mall_points":        a.get("malls", []),
                    "supermarket_points": a.get("supermarkets", []),
                    "school_points":      a.get("schools", []),
                    "hospital_points":    a.get("hospitals", []),
                }
        print("amenities merged.")
    except FileNotFoundError:
        print("WARNING: amenities.json not found — building without amenities layer.")

    # every feature must have every layer — no silent partial data
    incomplete = [ft["properties"]["shapeName"] for ft in feats
                  if "income_median" not in ft["properties"]["stats"]
                  or "poverty_absolute" not in ft["properties"]["stats"]]
    if incomplete:
        sys.exit(f"INCOMPLETE DATA for: {incomplete}")

    with open("data.json", "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f)
    print(f"data.json written: {len(feats)} districts, all layers complete.")


if __name__ == "__main__":
    main()
