# Module 1 — Geospatial / Data Foundation

Code here is only the loader/QA tooling (steps 6, 8-11 of the spec).
Steps 1-5 and 7 (coast list freeze, polygon digitization, jurisdiction
digitization, field verification) are manual GIS work — no code produces them.

## Workflow

1. Freeze target coast/state list (a plain list, e.g. in `SCOPE_FREEZE.md`).
2. In QGIS (free): load satellite basemap, manually trace each beach polygon,
   safe zone polygon, jurisdiction service-area polygon, and drop hospital /
   rescue-post points. Export each layer as GeoJSON — one file per table.
   Use `data_templates/beaches_template.geojson` as the property-field shape
   to match (`scripts/load_geojson.py`'s `FIELD_MAP` expects these exact keys).
3. Load into the DB:
   ```
   python -m scripts.load_geojson beaches beaches.geojson
   python -m scripts.load_geojson safe_zones safe_zones.geojson
   python -m scripts.load_geojson jurisdictions jurisdictions.geojson
   python -m scripts.load_geojson hospitals hospitals.geojson
   python -m scripts.load_geojson rescue_posts rescue_posts.geojson
   ```
4. Run QA before trusting the data anywhere downstream:
   ```
   python -m scripts.qa_validation
   ```
   This checks `ST_IsValid()` on every geometry and flags features within
   50m of each other as possible duplicates (manual review — never auto-merged).
5. Field verification: track confirmed-correct locations in `audit_events`
   (Module 2D) with `event_type='field_verified'`, `entity_type=<table>`,
   `entity_id=<row id>` — no new table needed, reuses the audit trail.

## Why no admin QA map screen is included here
That's a small standalone visual tool (Leaflet/Streamlit map showing all
loaded geometries for staff to eyeball), not part of this module's core data
pipeline. Say the word and I'll build it as its own piece.
