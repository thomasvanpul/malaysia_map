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
        'Pulau Pinang','Selangor','Terengganu','W.P. Kuala Lumpur','W.P. Putrajaya']

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
}

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
        pick = lambda sx, ag, eth: float(
            g[(g["sex"] == sx) & (g["age"] == ag) & (g["ethnicity"] == eth)]["population"].iloc[0])
        eth = g[(g["sex"] == "both") & (g["age"] == "overall") & (g["ethnicity"] != "overall")]
        tr = pop[(pop["district_clean"] == d) & (pop["sex"] == "both")
                 & (pop["age"] == "overall") & (pop["ethnicity"] == "overall")].sort_values("date")
        s = {
            "total": pick("both", "overall", "overall"),
            "male": pick("male", "overall", "overall"),
            "female": pick("female", "overall", "overall"),
            "ethnicity": {r.ethnicity: float(r.population) for r in eth.itertuples()},
            "trend": [[int(r.date.year), float(r.population)] for r in tr.itertuples()],
            "state": g["state"].iloc[0],
        }
        di = inc[inc["district_clean"] == d].sort_values("date")
        if len(di):
            last = di.iloc[-1]
            s["income_mean"] = int(last["income_mean"])
            s["income_median"] = int(last["income_median"])
            s["income_year"] = int(last["date"].year)
            s["income_trend"] = [[int(r.date.year), int(r.income_median)] for r in di.itertuples()]
        dp = pov[pov["district_clean"] == d].sort_values("date")
        if len(dp):
            last = dp.iloc[-1]
            s["poverty_absolute"] = float(last["poverty_absolute"])
            s["poverty_relative"] = float(last["poverty_relative"])
        ft["properties"]["stats"] = s

    # merge amenities (OSM-derived, generated separately by fetch_amenities.py)
    try:
        with open("amenities.json") as f:
            amen = json.load(f)
        for ft in feats:
            a = amen.get(ft["properties"]["shapeName"])
            if a:
                ft["properties"]["stats"]["amenities"] = a
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
