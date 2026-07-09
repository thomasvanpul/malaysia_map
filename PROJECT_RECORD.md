

---

## UPDATE — Amenity dots, transit lines, popups, map polish (Phase 1 complete)

### Files added
- **fetch_transit.py** — pulls all rail route relations from OSM Overpass API (subway/light_rail/monorail/train), assembles fragmented way-segments into full continuous coordinate lists via a stitching algorithm, applies official Rapid KL / KTMB brand colors per route ref
- **dedupe_transit.py** — filters out Singapore routes (leaked via bounding box), deduplicates A→B / B→A directional variants by canonical name normalization, rounds coords to 4dp, outputs clean transit.json
- **transit.json** — 15 deduplicated Malaysian rail routes (KJ, AG, SP, MRT Kajang, MRT Putrajaya, KL Monorail, LRT3, KLIA Ekspres/Transit, KTM Komuter Port Klang/Seremban/Skypark, KTM ETS, Butterworth intercity)
- **enrich_amenities.py** — re-fetches all amenities with full OSM tags (address, website, phone, opening_hours, brand, operator, wikidata ID), then batch-queries Wikidata SPARQL (50 IDs per request) for P18 image property, builds Wikimedia Commons thumbnail URLs
- **amenities.json** (updated) — now stores full coordinate arrays + metadata per amenity instead of counts only. 3,783 amenities total: 97% have names, 45% have websites, 35% have phones, 9% have Wikimedia photos (325 amenities — concentrated on major malls and rail stations)

### What changed in index.html
- Three toggle chips in header: Rail (dark teal), Malls (rust), Supermarkets (olive)
- Transit lines chip: 15 routes rendered as thin 2.5px single-stroke polylines with official colors, hover tooltip shows route name + ref
- Transit lines + Malls on by default; Rail + Supermarkets off by default
- Supermarkets auto-hide below zoom level 12 (3,000 dots at zoom-out = unusable)
- Click any amenity dot → rich popup card: Wikimedia photo (where available), name, kind + district, address, opening hours, phone, website link
- Hover tooltip still works for quick name reference without clicking
- District borders fixed: shapes rendered fill-only (stroke:false), single border layer drawn on top so shared edges don't double-stroke
- Selected district: amber border (#e0a422), fillOpacity drops to 0.45 so dots/lines underneath show through
- Zoom toward cursor: native Leaflet scrollWheelZoom disabled, replaced with custom wheel listener using map.setZoomAround() + requestAnimationFrame batching — immediate response, no animation queuing, no recoil
- Switched base tile provider from CARTO free tier to MapTiler (dataviz-light style, API key locked to thomasvanpul.github.io domain). Better CDN, faster edge tile loading, supports zoom 19

### Key findings
- **Singapore rail routes leak into the Overpass bounding box** — filtered by matching route names against a known-SG keyword list and checking that route centroid latitude > 1.5
- **Wikidata image URL double-encoding bug** — SPARQL returns already-URL-encoded filenames; applying urllib.parse.quote() again produced %2520 (double-encoded spaces). Fixed by applying unquote() once before storing. 323 URLs corrected.
- **sed is unreliable for HTML editing** — three separate bugs (duplicate attribution key, mangled URL, wrong prefix) came from using sed for substitutions. All subsequent edits use Python str.replace() with explicit assert checks.

### Glossary additions
**OSM route relation** — an OSM data structure grouping multiple way-segments that form a single transit route. Ways are stored in arbitrary order and must be stitched into sequence.
**Way stitching** — chaining OSM way-segments end-to-end by matching coordinates within a threshold (~100m). Segments may need reversing if stored tail-first.
**setZoomAround** — Leaflet method that zooms to a target level while keeping a specified pixel point fixed on screen (cursor-based zoom).
**requestAnimationFrame (rAF)** — browser API that batches visual updates to the next render frame, preventing animation queuing and perceived lag.
**Wikidata P18** — the "image" property in Wikidata's knowledge graph; links an entity to a Wikimedia Commons filename.
**MapTiler** — commercial tile provider with a free tier (100k requests/month). Vector-based, faster CDN than CARTO free tier. API key should be locked to allowed domains in MapTiler dashboard.
**SPARQL** — query language for RDF knowledge graphs; used here to batch-fetch Wikidata image properties for up to 50 entities per request.
