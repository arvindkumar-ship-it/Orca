# Module 3 (Data Ingestion) + Module 4 (Normalization Engine)

Continues directly from your completed Module 2 (schema + ORM). Full code,
not pseudocode — but there are **4 explicit assumptions** below that I could
not verify without your actual repo. Fix these before running against real
data; everything else is spec-exact and doesn't depend on them.

## Files

```
module_03_ingestion/
  ingestion/
    config.py            # source configs, env-driven
    schemas.py            # RawIngestRecord — the contract every connector emits
    base_connector.py      # retry/backoff/timeout/reject/latency (shared)
    incois_connector.py    # ocean forecast source
    sachet_connector.py    # CAP hazard warning source
    manual_connector.py    # admin-submitted closures (event-driven, not polled)
    dedup.py               # Redis-based dedup by source+alert_id+valid window
    raw_storage.py          # raw payload object storage (local/S3)
    persistence.py          # writes hazard_alerts/beach_forecasts, triggers risk recompute
    scheduler.py             # polling interval logic
    ops_alerts.py             # alerts ops on repeated source failure
  workers/
    ingestion_worker.py       # Celery tasks wiring the whole pipeline end-to-end
  requirements_module_3_4.txt

module_04_normalization/
  normalization/
    canonical_schema.py  # CanonicalHazardEvent / CanonicalForecastEvent
    unit_conversion.py    # knots->m/s, feet->m, etc.
    normalizer.py          # RawIngestRecord -> canonical event, steps 1-8
```

## The 4 assumptions — verify against your repo

1. **ORM class names & session.** `persistence.py` imports
   `from app.models import Beach, BeachForecast, HazardAlert` and
   `from app.db import get_session`. If your `models/__init__.py` uses
   different class names or a different session pattern, only these two
   import lines change.
2. **Celery + Redis wiring.** `ingestion_worker.py` imports
   `celery_app` from `app.celery_app` and `redis_client` from
   `app.redis_client`. Swap the two import lines to match your actual
   app factory.
3. **INCOIS field names.** `incois_connector.py`'s `_parse()` uses
   placeholder field names (`wave_ht`, `curr_spd`, etc.) — I don't have
   your INCOIS API credentials/contract. Capture one real response and
   I'll fix the mapping in five minutes.
4. **SACHET feed format.** `sachet_connector.py` assumes a JSON CAP feed.
   If your actual SACHET integration is XML/RSS CAP (common in real CAP
   deployments), only `_fetch_raw`/`_parse` need an XML parser swap — the
   CAP field semantics (severity map, hard-override event types,
   polygon parsing) stay correct either way.

## What's spec-complete and doesn't need verification

- Retry/backoff, timeout, malformed-record rejection, missing-value
  tagging, ingestion latency logging (Module 3 steps 2,3,10,11,13).
- Dedup by source + alert_id + valid time window (step 8).
- Raw payload storage before normalization (step 6), swappable local/S3.
- Ops alert on repeated source failure (step 14).
- Canonical schema mapping, UTC conversion, unit normalization, uncertainty
  tagging, malformed-alert rejection (Module 4 steps 1-8).
- Hard-override flag logic matches Module 5's override list exactly
  (tsunami, storm surge, evacuation, beach closure, coast guard closure).
- Downstream risk recompute trigger via Redis pub/sub
  (`risk_engine:recompute_trigger`) — Module 5's worker should subscribe
  to this channel next.

## Next module in sequence

Per Module 34's build order: **Module 5 (Risk Engine)** — subscribes to
`risk_engine:recompute_trigger`, loads `beach_activity_profiles` +
`beach_forecasts` + active `hazard_alerts`, computes the logistic risk
score with hard overrides, writes `beach_risk_scores`. Say the word and
I'll build that next, same standard: real code, assumptions flagged, not
guessed.
