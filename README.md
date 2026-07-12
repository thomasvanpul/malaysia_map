# West Malaysia District Explorer

An interactive choropleth map of all 91 Peninsular Malaysia districts. Click any
district for its population, household income, poverty rates, ethnicity
breakdown, and multi-year trends — or compare any two districts side by side,
even across states. Amenity and transit layers overlay rail stations, malls,
supermarkets, and the full MRT/LRT/KTM/Monorail/ETS network.

Live: https://thomasvanpul.github.io/malaysia_map/

## What the map shows
- **Choropleth** of district population, binned into quintiles (each shade = 20%
  of districts) so the heavy skew doesn't wash the map out.
- **District panel** (click a district): total / male / female population, growth
  since 2020, median & mean household income, absolute & relative poverty,
  ethnicity split, and trend sparklines for population and income.
- **Compare** any two districts across every metric, including across states.
- **State dropdown** to zoom to a single state, or back to the whole peninsula.
- **Amenity layers** (toggle chips): rail stations, malls, supermarkets. Click a
  dot for a popup with name, brand, address, hours, website, and a Wikimedia
  Commons photo where a Wikidata link exists.
- **Transit lines**: 15 deduplicated MRT/LRT/KTM/Monorail/ETS routes in their
  official operator colors. Transit + malls are on by default.
- **Projects layer** (toggle chip, blue pins, clustered): government-registered
  housing projects from TEDUH/KPKT — real pricing, take-up %, status (Lancar/
  Lewat/Sakit/etc.), developer, expected completion, brochure links. Click a
  pin for the full detail panel. Refreshed daily via GitHub Actions
  (`teduh-daily.yml`), with a 90-day rolling take-up-rate history.
- **New Launches layer** (toggle chip, amber pins, clustered): 2,818 new-launch
  projects (2021–2025) sourced from Mr. Hock's dataset — tenure (freehold/
  leasehold), landed vs high-rise, developer, price range, units sold/total,
  launch date. Complements the Projects layer rather than duplicating it.

## Data sources
- **DOSM** (Department of Statistics Malaysia): population 2025 estimates;
  household income & poverty from HIES survey years 2019 / 2022 / 2024.
- **geoBoundaries** ADM2 for district polygons.
- **OpenStreetMap** via the Overpass API for amenities and transit geometry.
- **TEDUH/KPKT** official filing data for the Projects layer (daily crawl).
- **Mr. Hock's new-launches dataset** (`hik113-AI/Live-testing-`) for the
  New Launches layer, 2,818 projects 2021–2025.

## Files
- `index.html` — the entire app (Leaflet map + side panel), no build step
- `data.json` — district shapes + stats + amenity points (generated — never edit by hand)
- `transit.json` — deduplicated transit route geometry (generated; optional — the
  map still loads without it)
- `teduh_projects.json` — TEDUH/KPKT government housing project data (daily
  crawl output; the map still loads without it)
- `teduh_history.json` — 90-day rolling take-up-rate history for TEDUH projects
- `developer_new_launches.json` — Mr. Hock's new-launches dataset, converted to
  named JSON (generated from `hik113-AI/Live-testing-`; the map still loads
  without it)
- `build_data.py` — pipeline: downloads DOSM parquets, cleans district names,
  validates the join, regenerates data.json
- `clean_district_names.py` — the shared name-cleaning map applied to every dataset
- `geoBoundaries-MYS-ADM2_simplified.geojson` — district polygons (pipeline input)
- `.github/workflows/update-data.yml` — weekly auto-rebuild via GitHub Actions
- `*.parquet` — local copies of the DOSM source data (used by `--local` mode)
- `PROJECT_RECORD.md` — running log of decisions, data quirks, and the glossary

## Run locally
Double-clicking `index.html` will NOT work — browsers block a local page from
fetching `data.json`. Serve it instead. From this folder:

    python -m http.server

then open http://localhost:8000

## Rebuild the data manually
    pip install pandas fastparquet requests
    python build_data.py           # downloads fresh files from DOSM
    python build_data.py --local   # reuses the parquet files in this folder

The pipeline fails loudly if DOSM introduces a district name it doesn't
recognise — that's intentional. Fix the mapping in `clean_district_names.py`,
don't bypass it.

## Deploy (GitHub Pages — free)
1. Push this folder to a GitHub repository.
2. Repo Settings → Pages → Source: `main` branch, root.
3. Site is live at https://thomasvanpul.github.io/malaysia_map/
4. The weekly Action keeps `data.json` fresh automatically (Actions tab →
   "Rebuild data.json from DOSM" → Run workflow, to test it once manually).

## Known limitations & data quirks
- **W.P. Putrajaya**: stats exist, but the boundary file has no polygon for it —
  it appears in data but not on the map.
- **DOSM naming is inconsistent** across its own files (e.g. "Sp Selatan" vs
  "S.P. Selatan", "Larut Dan Matang" vs "Larut & Matang"). The cleaning map must
  be applied to every new dataset. A genuine DOSM data-entry error was also found
  and fixed: a truncated "Hulu" row that was actually Hulu Terengganu.
- **Income/poverty are survey years** (HIES runs every ~2–3 years), not annual.
- **Supermarkets are gated to zoom ≥ 12** to avoid rendering ~3,000 dots at once.
  Toggling the chip while zoomed out shows a "zoom in" hint rather than the dots.
- **Singapore transit leaks** into the Overpass bounding box and is filtered out
  by name-pattern and a minimum-latitude check during the transit build.

 
