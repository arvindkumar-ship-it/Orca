# Module 0 & Module 1 — How to build these (not code modules, process deliverables)

Modules 3-12 tumhare paas code hain kyunki wo runtime logic hain. Module 0 aur 1
alag kism ke hain — inka deliverable ek **document + verified data**, code nahi.
Yaha exact instructions hain ki kaise banayein, real system ke hisaab se.

## Module 0 — Product Scope Freeze

**Deliverable:** ek `SCOPE_FREEZE.md` document — code nahi, decisions hain.
Iska purpose: baaki har module (3-12+) implicitly is document pe depend karta
hai (incident_type enum, activity_type enum, jo already tumhare Module 8
schemas.py me hardcoded hain).

**Kaise banayein:**
1. `SCOPE_FREEZE.md` file banao apne repo root me.
2. In 5 sections likho, exact wording final rakho (ye baad me enums/constants ban jayenge):
   - User journeys (6): pre-check, trip check, sudden danger, SOS, rescue, post-incident review
   - Incident types (6): drowning, injury, panic, harassment, cyclone_storm_surge, missing_person — **ye already `sos/schemas.py`'s `IncidentType` enum me hain, is document ko us enum ka single source of truth banao**
   - Activity types (5): swimming, surfing, boating, beach_walk, family_outing — **ye `beach_activity_profiles.activity_type` aur trip_planner me use ho raha hai, yahi freeze karo**
   - Response roles (8): 112, local_police, marine_police, lifeguard, coast_guard, ambulance, hospital, district_disaster_authority — **`jurisdictions.authority_type` aur `hospitals.type` isi list se aate hain**
   - Privacy boundaries: consent_location, consent_emergency_share (already `users` table me columns hain), audit retention period, data minimization rules
3. Is document ko as constants file bhi banao taaki code aur doc drift na ho:

```python
# app/constants.py — single source of truth, generated from SCOPE_FREEZE.md
INCIDENT_TYPES = ["drowning", "injury", "panic", "harassment", "cyclone_storm_surge", "missing_person"]
ACTIVITY_TYPES = ["swimming", "surfing", "boating", "beach_walk", "family_outing"]
RESPONSE_ROLES = ["112", "local_police", "marine_police", "lifeguard", "coast_guard",
                   "ambulance", "hospital", "district_disaster_authority"]
```
4. Sab modules (3-12+) me jahan bhi ye strings hardcoded hain (jaise Module 8's
   `sos/schemas.py` ka `IncidentType` enum), unhe `app.constants` se import karke
   sync me lao — abhi wo independently defined hain, jo drift risk hai.

**Effort:** ~1 din, no engineering — sirf decisions freeze karna + constants file.

---

## Module 1 — Geospatial / Data Foundation

**Deliverable:** verified spatial data — actual rows in `beaches`, `safe_zones`,
`jurisdictions`, `hospitals`, `rescue_posts` (jo Module 2 create karega) —
code nahi, **data**. Bina is data ke Module 3-11 ka koi bhi query khali result
dega (jaise Module 9's `find_candidates`, Module 11's `find_nearest_zones`).

**Kaise banayein — sequence:**

1. **Coast/state list freeze** — kaunse states/beaches MVP me cover honge, list
   likho (e.g. Goa, Kerala, TN coast — jo bhi tumhara target hai).

2. **Beach master records** — har beach ke liye ek row draft karo (name, state,
   district, coast_region) — CSV me pehle, phir DB me load.

3. **Beach polygon digitization** — QGIS (free tool) use karke Google
   satellite imagery pe har beach ka boundary polygon manually draw karo,
   GeoJSON export karo. Script se import:

```python
# scripts/load_beaches.py — one-time data loader, not a running service
import json
from geoalchemy2.functions import ST_GeomFromGeoJSON, ST_SetSRID
from app.db import get_session
from app.models import Beach

def load_beaches_from_geojson(path: str):
    with open(path) as f:
        data = json.load(f)
    with get_session() as session:
        for feature in data["features"]:
            props = feature["properties"]
            session.add(Beach(
                name=props["name"], state=props["state"], district=props.get("district"),
                coast_region=props.get("coast_region"),
                geom=ST_SetSRID(ST_GeomFromGeoJSON(json.dumps(feature["geometry"])), 4326),
                has_lifeguard=props.get("has_lifeguard", False),
            ))
        session.commit()
```
   Same pattern safe_zones, jurisdictions, hospitals, rescue_posts ke liye —
   sirf GeoJSON source aur target model badlega.

4. **Jurisdiction polygons** — marine police / coast guard / lifeguard service
   areas ke liye MultiPolygon banao QGIS me, same loader se import.

5. **Hospital points + capability metadata** — lat/lng + `capabilities` jsonb
   (trauma/emergency_ward/icu/pediatric flags) — ye seedha Module 10's
   `hospital_router` ke `required_capabilities` check se match hona chahiye.

6. **Area naming normalize + duplicate merge** — ek script likho jo
   `ST_DWithin(a.geom, b.geom, 50)` se overlapping/duplicate beach entries
   dhoondhe for manual review — automatic merge mat karo, sirf flag karo.

7. **Versioning** — har spatial table me `updated_at` already hai (Module 2
   schema me); har edit pe naya row nahi, update + `audit_events` me log
   (Module 2D ka `audit_events` table isi ke liye hai).

8. **Geometry validation:**
```sql
-- run after every load — invalid polygons break every downstream ST_ query
SELECT id, name FROM beaches WHERE NOT ST_IsValid(geom);
```

9. **GiST indexes** — Module 2 ke SQL me already included hain
   (`idx_beaches_geom` etc.) — kuch extra karne ki zaroorat nahi.

10. **Admin QA map screen** — ek simple internal tool (Streamlit/simple
    HTML+Leaflet page) jo saari beaches/zones/jurisdictions map pe render
    kare taaki local staff visually verify kar sake. Chhota standalone tool
    hai — bata do agar ye bhi chahiye, alag se bana dunga.

11. **Field verification log** — ek `field_verifications` table (optional,
    add kar sakte ho Module 2D ke "Optional support tables" pattern follow
    karke) jisme staff confirm karta hai ki polygon field-visit se match
    karta hai.

**Effort:** Ye sabse zyada manual-labor-heavy module hai — QGIS digitization
me din lagte hain per-beach. Code sirf loader scripts hain (~50 lines each),
asli kaam data collection + verification hai.

---

Ab dono clear ho gaye — code Module 2 (neeche) provide kar raha hoon, jo
Module 0's constants aur Module 1's data dono ko structurally support karta
hai.
