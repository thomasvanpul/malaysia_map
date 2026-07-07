# West Malaysia District Explorer

Interactive map: click any of 91 Peninsular Malaysia districts for population,
household income, poverty rates, trends, and side-by-side comparison.

Data: DOSM (population 2025; HIES income/poverty 2019/2022/2024).
Boundaries: geoBoundaries ADM2.

## Files
- `index.html` — the entire app (Leaflet map + side panel)
- `data.json` — all district shapes + stats (generated — do not edit by hand)
- `build_data.py` — pipeline: downloads DOSM parquets, cleans district names,
  validates the join, regenerates data.json
- `geoBoundaries-MYS-ADM2_simplified.geojson` — district polygons (pipeline input)
- `.github/workflows/update-data.yml` — weekly auto-rebuild via GitHub Actions
- `*.parquet` — local copies of the DOSM source data (used by `--local` mode)

## Run locally
Double-clicking index.html will NOT work — browsers block a local page from
fetching data.json (CORS). Serve it instead. From this folder:

    python -m http.server

then open http://localhost:8000

## Rebuild the data manually
    pip install pandas fastparquet requests
    python build_data.py           # downloads fresh files from DOSM
    python build_data.py --local   # reuses the parquet files in this folder

The pipeline fails loudly if DOSM introduces a district name it doesn't
recognise — that's intentional. Fix the CLEAN mapping, don't bypass it.

## Deploy (GitHub Pages — free)
1. Push this folder to a GitHub repository
2. Repo Settings -> Pages -> Source: main branch, root
3. Site is live at https://USERNAME.github.io/REPO/
4. The weekly Action keeps data.json fresh automatically (Actions tab ->
   "Rebuild data.json from DOSM" -> Run workflow, to test it once manually)

## Known limitations
- W.P. Putrajaya: stats exist, but the boundary file has no polygon for it
- Income/poverty are survey years (HIES runs every ~2-3 years), not annual
- The income/poverty parquet URLs in build_data.py should be verified once
  against the actual download links on the OpenDOSM catalogue pages
