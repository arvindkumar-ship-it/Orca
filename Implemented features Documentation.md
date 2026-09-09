# WaveSafe — Coastal Tourism Safety Platform
### Backend Architecture Documentation

**Prepared:** August 22, 2026

---

## 1. Project Overview

**WaveSafe** is a backend system for a **coastal tourism safety platform** aimed at India's beach destinations. Its stated non-negotiable principle (from `SCOPE_FREEZE.md`) is that it must not be "a notification wrapper" — it is built to do four real things:

1. Convert raw official hazard/weather data into a clear, per-beach safety decision.
2. Detect risk changes during a user's planned trip window.
3. Dispatch real emergencies (SOS) with exact location to the right responders.
4. Coordinate rescue across authorities and hospitals until the incident is closed.

The system ingests official hazard feeds (INCOIS ocean data, NDMA's SACHET disaster-alert feed), scores beach risk, plans and monitors trips, handles SOS/emergency dispatch through a formal state machine, routes incidents to police/coast guard and hospitals, shares live location with emergency contacts, and produces audit/analytics data for operators.

The six frozen user journeys are: **Pre-check → Trip check → Sudden danger → SOS → Rescue → Post-incident review.**

> **Note on scope:** This backend was built incrementally across many numbered "modules" (0–32+) in separate sessions. Some source files still retain large commented-out draft blocks above the final, active implementation (kept as in-code history) — this documentation describes only the code paths that are actually active and wired into `app/main.py`. A `frontend/` (Next.js) directory and a Prometheus `/metrics` endpoint are referenced in project notes but are **not present** in this codebase — see Section 9 (Limitations).

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3 |
| Web framework | FastAPI (`>=0.110`), Uvicorn (ASGI server) |
| Database | PostgreSQL 16 with **PostGIS 3.4** (geospatial extension), via `postgis/postgis:16-3.4` Docker image |
| ORM | SQLAlchemy 2.0 + GeoAlchemy2 (geometry columns) |
| DB driver | psycopg2-binary |
| Migrations | Raw SQL migration files (`app/db/migrations/*.sql`); Alembic listed as an optional upgrade path |
| Validation / settings | Pydantic v2 + pydantic-settings, `python-dotenv` |
| Background jobs | Celery (`>=5.3`) with Redis (`>=5.0`) as broker **and** result backend |
| HTTP clients | httpx, requests (used for INCOIS/SACHET/Open-Meteo polling and SMS gateway calls) |
| Auth / security | JWT (`python-jose`), password/OTP hashing via `passlib[bcrypt]` + `bcrypt`, `python-multipart` |
| Rate limiting | slowapi (public, unauthenticated endpoints) |
| Push notifications | pywebpush (Web Push / VAPID) |
| SMS (OTP + alerts) | Fast2SMS gateway integration (`app/services/sms_provider.py`, `channels/sms_channel.py`) |
| Object storage (optional) | boto3 (S3, used only if `RAW_STORAGE_BACKEND=s3`) |
| Ops / monitoring | prometheus_client (metric *definitions* only — see Limitations) |
| Testing | pytest, pytest-asyncio |
| Containerization | Docker + Docker Compose (separate `backend.Dockerfile` / `frontend.Dockerfile`) |
| External data sources | INCOIS (Indian ocean/wave forecast data), SACHET/NDMA (CAP disaster alerts), Open-Meteo (marine + weather API, used in the forecast engine) |

---

## 3. Folder Structure

```
WaveSafe/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI app entrypoint, router wiring
│   │   ├── constants.py
│   │   ├── redis_client.py
│   │   ├── api/                        # Route layer
│   │   │   ├── authority_router.py     # Internal + partner routes for police/coast guard dispatch
│   │   │   ├── hospital_router.py      # Internal + partner routes for hospital dispatch
│   │   │   ├── health.py               # /healthz, /readyz
│   │   │   ├── safezone.py             # Safe-zone guidance routes
│   │   │   ├── tracking.py             # Live location tracking routes
│   │   │   ├── internal_dispatch.py    # Internal dispatch state-machine routes
│   │   │   └── v1/
│   │   │       ├── auth_router.py      # OTP login/logout
│   │   │       ├── admin.py            # Admin CRUD + ops endpoints
│   │   │       ├── audit.py            # Analytics endpoints
│   │   │       ├── beach.py            # Public beach/risk/forecast/alerts endpoints
│   │   │       ├── trips.py            # Trip planning endpoints
│   │   │       ├── incidents.py        # SOS trigger + incident detail/ack/media
│   │   │       ├── emergency_share.py  # Live-location sharing with contacts
│   │   │       ├── notifications.py    # User notification inbox
│   │   │       ├── offline_sync.py     # Offline-first sync bundle + queued SOS
│   │   │       └── internal.py         # Server-to-server ingestion/risk-recompute
│   │   ├── core/                       # Cross-cutting infrastructure
│   │   │   ├── config.py               # Settings (env-driven)
│   │   │   ├── db.py                   # SQLAlchemy session/engine
│   │   │   ├── security.py             # JWT, OTP auth, internal/partner API keys
│   │   │   ├── rate_limit.py           # slowapi limiter
│   │   │   ├── cache.py                # Redis cache helpers for risk/forecast
│   │   │   ├── audit.py                # Audit event writer
│   │   │   ├── dispatch_states.py      # Canonical incident state + event enums
│   │   │   └── exceptions.py
│   │   ├── db/migrations/              # Hand-written SQL migrations (11 files)
│   │   ├── models/                     # SQLAlchemy ORM models
│   │   ├── schemas/                    # Pydantic request/response schemas
│   │   ├── services/                   # Business logic layer
│   │   │   └── channels/               # Notification delivery channels (push, SMS)
│   │   ├── workers/                    # Celery tasks + beat schedule
│   │   └── ops/                        # CLI/monitoring scripts, metric definitions
│   ├── ingestion/                      # Hazard-data ingestion connectors (INCOIS, SACHET, manual)
│   ├── normalization/                  # Raw feed → canonical schema conversion + unit conversion
│   ├── risk_engine/                    # Beach risk scoring engine
│   ├── forecast_engine/                # Time-series forecast + outlook engine (Open-Meteo)
│   ├── trip_planner/                   # Trip-window risk planning + advisory text
│   ├── data/raw_ingest/                # Locally stored raw ingested payloads (SACHET JSON dumps)
│   ├── data_templates/                 # GeoJSON seed templates (beaches, hospitals, safe zones, etc.)
│   ├── scripts/                        # DB/QA utility scripts
│   └── requirements.txt
├── deploy/
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile             # Present, but no frontend/ source directory in this package
│   └── runbook.sh                      # Deployment / test-gate runbook
├── docs/                               # Internal module notes (WIRING_LOG.md, README.md, etc.)
├── scripts/ , tests/                   # pytest suites (acceptance, dispatch state machine, failure
│                                        #   scenarios, e2e reference flow) + smoke-test script
├── docker-compose.yml                  # db, redis, api, 5 celery workers, beat, frontend
└── pytest.ini
```

---

## 4. Modules & Their Responsibilities

| Module / Package | Responsibility |
|---|---|
| **Auth Module** (`api/v1/auth_router.py`, `services/auth_service.py`) | Phone-number OTP login: request OTP → SMS via Fast2SMS → verify OTP → issue JWT access token; logout. |
| **Beach Module** (`api/v1/beach.py`, `services/beach_service.py`) | Public, rate-limited endpoints to search/list beaches, fetch beach detail, current risk verdict, forecast, and active hazard alerts. |
| **Risk Engine** (`risk_engine/`) | Computes a per-beach, per-activity risk score from normalized hazard features (wave height, current speed, wind, swell, water quality, rainfall, tide, data-coverage gaps), with hard overrides for events like tsunami/storm-surge warnings or official beach closures. |
| **Forecast Engine** (`forecast_engine/`) | Builds short-term outlook/trend from time-series data and Open-Meteo marine + weather data; feeds the Trip Planner. |
| **Ingestion Module** (`ingestion/`, `api/v1/internal.py`) | Pulls hazard data from INCOIS (ocean/wave conditions) and SACHET/NDMA (CAP disaster alerts), plus a manual/admin connector for operator-entered closures. Shared retry, timeout, dedup, raw-payload storage, and ops-failure alerting logic. |
| **Normalization Module** (`normalization/`) | Converts each source's raw payload into one canonical schema and performs unit conversion, so the risk engine doesn't need to know about individual data sources. |
| **Trip Planner** (`trip_planner/`, `api/v1/trips.py`, `services/trip_service.py`) | Lets a user plan a trip (beach + time window + activity); computes worst-case risk over that window, generates a plain-language advisory, and suggests alternative beaches when risk is high. |
| **SOS / Incident Module** (`api/v1/incidents.py`, `services/sos_service.py`, `services/incident_service.py`) | Handles SOS triggering, incident detail/status lookup, attaching media evidence, and authority/hospital acknowledgement of an incident. |
| **Dispatch State Machine** (`core/dispatch_states.py`, `services/dispatch_state_machine.py`) | Single authoritative owner of an incident's lifecycle status (created → validated → location_locked → packed → dispatched → acknowledged → routed → en_route → hospital_notified → safe_zone_shared → resolved → closed, plus failure branches: timeout, escalated, fallback_112, manual_ops). Every transition writes status history + an audit event and fires notification/escalation hooks. |
| **Authority Router** (`api/authority_router.py`, `services/authority_router_service.py`) | Dispatches an incident to the relevant police/marine-police/coast-guard jurisdiction and records their acknowledgement. |
| **Hospital Router** (`api/hospital_router.py`, `services/hospital_router_service.py`) | Dispatches an incident to the nearest/most relevant hospital and records their acknowledgement. |
| **Escalation Module** (`services/escalation_service.py`, `workers/escalation_worker.py`) | Persists a single active "ack timer" per incident; a Celery Beat task polls due timers every 15s and drives the state machine to `escalated`/`fallback_112` if a responder fails to acknowledge in time. |
| **Safe Zone Module** (`api/safezone.py`, `services/safezone_service.py`) | Computes safe-zone routing guidance (nearest safe assembly point + walking route) during an active incident, with recompute and share actions. |
| **Live Tracking Module** (`api/tracking.py`, `services/tracking_service.py`) | Starts/stops a live location-tracking session for a user, ingests location pings, and exposes the latest snapshot to admins/responders (flags stale pings and abnormal speed). |
| **Emergency Contact Sharing** (`api/v1/emergency_share.py`, `services/emergency_share_service.py`, `services/fanout_service.py`) | Starts/stops sharing a user's live location with their saved emergency contacts and fans out notifications to them. |
| **Notification Module** (`api/v1/notifications.py`, `services/notification_service.py`, `services/notification_templates.py`, `services/notification_inbox_service.py`, `services/channels/`) | Canonical notification enqueue/delivery contract; template rendering (`{{var}}` interpolation); delivery over Web Push (VAPID) and SMS channels; user-facing notification inbox with read/unread state. |
| **Offline Sync Module** (`api/v1/offline_sync.py`, `services/offline_sync_service.py`) | Serves a sync "bundle" for offline-first clients and accepts a queue of SOS reports created while offline, converting them into real incidents on reconnect. |
| **Admin Module** (`api/v1/admin.py`, `services/admin_service.py`) | Admin-only CRUD for beaches, activity-risk thresholds, jurisdictions, hospitals, and safe zones; incident listing/acknowledgement views; response-latency metrics; risk-rule tuning; log export. |
| **Audit & Analytics Module** (`api/v1/audit.py`, `core/audit.py`, `services/audit_service.py`) | Central audit-event writer used by every other module; analytics endpoints for mean response time, alert accuracy, missed-warning rate, and threshold-refit recommendations. |
| **Internal Service-to-Service Module** (`api/v1/internal.py`, `api/internal_dispatch.py`) | Machine-to-machine endpoints (protected by an internal API key, not JWT) for triggering ingestion, risk recomputation, and raw dispatch/escalation state transitions. |
| **Security Core** (`core/security.py`) | JWT issuance/verification (`get_current_user`, `get_current_admin`), and separate API-key guards for internal services (`verify_internal_key`) and external partner callbacks (`verify_partner_key`). |
| **Background Workers** (`app/workers/`) | Celery app + Beat schedule running: hazard-source polling, risk-score recomputation, notification-queue flushing, ack-timeout escalation checks, expired-cache cleanup, and periodic forecast sync. Each runs as its own container/queue (`ingestion`, `risk`, `notification`, `escalation`, `cleanup`). |
| **Ops Module** (`app/ops/`) | CLI acceptance-gate scripts (`check_alert_latency.py`, `check_sos_routing.py`) used in the deployment runbook, plus Prometheus metric *definitions* (not yet wired into the code paths they measure). |
| **Health Module** (`api/health.py`) | `/healthz` liveness and `/readyz` (DB-connectivity) readiness probes. |

---

## 5. Implemented Features (verified in code)

- Phone-number **OTP-based authentication** with JWT session tokens, via a real Fast2SMS gateway integration.
- **Beach discovery**: search/list beaches (with `near=lat,lng` filtering), beach detail, current risk verdict, and forecast — all public and rate-limited.
- **Risk scoring engine** combining 8 normalized features (wave height, current speed, wind speed, swell height, water quality, rainfall, tide risk, data-coverage gap) with configurable per-feature weights and hard-override rules for tsunami/storm-surge/evacuation/closure alerts.
- **Forecast engine** built on Open-Meteo marine + weather APIs, with trend/delta computation over a time series.
- **Multi-source hazard ingestion**: INCOIS ocean-data connector, SACHET/NDMA CAP-alert connector (built against a real captured SACHET response), and a manual/admin closure connector — all sharing retry/backoff, deduplication, and raw-payload persistence (payloads are stored on disk under `backend/data/raw_ingest/`).
- **Trip planning**: create a trip (beach + time window + activity), compute worst-case risk across the window, get a plain-language advisory, rescan on demand, and cancel a trip.
- **SOS / emergency dispatch** with a formal, auditable **dispatch state machine** covering the full incident lifecycle including automatic **escalation on missed acknowledgement** (ack-timer polled every 15 seconds) and a fallback-to-112 path.
- **Authority routing** (police / marine police / coast guard) and **hospital routing**, each with their own dispatch + acknowledgement endpoints, protected separately for internal callers vs. external partner callbacks.
- **Safe-zone guidance**: compute, recompute, list active, and share a nearest-safe-zone route during an incident.
- **Live location tracking sessions** with ping ingestion, staleness detection, and admin-only status override.
- **Emergency-contact live-location sharing** (start/stop a share session, fan out notifications to saved contacts).
- **Notification system**: template-based message rendering, delivery over Web Push (VAPID) and SMS channels, and a per-user notification inbox with mark-as-read.
- **Offline-first support**: a downloadable sync bundle for clients, and a queue endpoint that accepts SOS reports created while offline and converts them into real incidents.
- **Admin console API**: CRUD for beaches, activity-risk thresholds, jurisdictions, hospitals, safe zones; incident + acknowledgement views; response-latency metrics; risk-rule tuning; audit-log export.
- **Audit & analytics**: every state transition and key action is written to an append-only audit trail; analytics endpoints compute mean response time, alert accuracy, missed-warning rate, and threshold-refit suggestions.
- **Background job system**: 5 dedicated Celery workers (ingestion, risk, notification, escalation, cleanup) plus a Celery Beat scheduler running 6 periodic tasks.
- **Data-retention policy enforced by design**: audit and incident-status-history tables have no auto-delete job (per `SCOPE_FREEZE.md`); consent flags (`consent_location`, `consent_emergency_share`) gate location/contact sharing except during an active SOS.
- **Health checks**: liveness (`/healthz`) and DB-readiness (`/readyz`) probes.
- **Ops acceptance gates**: CLI scripts that fail a deployment if hazard-ingestion latency or SOS-routing target counts don't meet thresholds; wired into `deploy/runbook.sh`.
- **Automated test suite**: pytest-based dispatch-state-machine tests, acceptance-criteria tests, failure-scenario tests, and an in-process end-to-end reference flow (trip → SOS → dispatch → ack/timeout → escalation → resolve/close → notifications → audit), plus a live-HTTP smoke-test script for staging.
- **Containerized deployment**: Docker Compose stack with PostGIS, Redis, the API, 5 worker containers, 1 Beat container, and a frontend container definition.

---

## 6. API Endpoints

All routes below are actively mounted in `app/main.py`. Internal (`/internal/...`) routes require an internal API key (`verify_internal_key`); partner-callback routes require a separate partner key (`verify_partner_key`); all other non-public routes require a JWT (`get_current_user` / `get_current_admin`).

### Auth — `/v1/auth`
| Method | Route | Purpose |
|---|---|---|
| POST | `/v1/auth/otp/request` | Request an OTP to a phone number |
| POST | `/v1/auth/otp/verify` | Verify OTP, receive JWT access token |
| POST | `/v1/auth/logout` | Log out |

### Beaches — `/v1`
| Method | Route | Purpose |
|---|---|---|
| GET | `/v1/beaches` | Search/list beaches (supports `near=lat,lng`) |
| GET | `/v1/beaches/{beach_id}` | Beach detail |
| GET | `/v1/beaches/{beach_id}/risk` | Current risk verdict for a beach |
| GET | `/v1/beaches/{beach_id}/forecast` | Forecast outlook for a beach |
| GET | `/v1/alerts` | Active hazard alerts |

### Trips — `/v1/trips`
| Method | Route | Purpose |
|---|---|---|
| GET | `/v1/trips` | List the current user's trips |
| POST | `/v1/trips` | Create a planned trip |
| GET | `/v1/trips/{trip_id}` | Trip detail |
| GET | `/v1/trips/{trip_id}/risk` | Trip risk assessment over its window |
| POST | `/v1/trips/{trip_id}/rescan` | Re-run risk assessment on demand |
| POST | `/v1/trips/{trip_id}/cancel` | Cancel a trip |

### SOS & Incidents — `/v1/sos`, `/v1/incidents`
| Method | Route | Purpose |
|---|---|---|
| POST | `/v1/sos` | Trigger an SOS / emergency |
| GET | `/v1/incidents/{incident_id}` | Incident detail |
| GET | `/v1/incidents/{incident_id}/status` | Current dispatch status |
| POST | `/v1/incidents/{incident_id}/media` | Attach evidence/media to an incident |
| POST | `/v1/incidents/{incident_id}/ack` | Acknowledge an incident |

### Emergency Location Sharing — `/v1/emergency/share`
| Method | Route | Purpose |
|---|---|---|
| POST | `/v1/emergency/share/start` | Start sharing live location with emergency contacts |
| POST | `/v1/emergency/share/stop` | Stop an active share session |
| GET | `/v1/emergency/share/{share_session_id}` | Get share-session detail |

### Notifications — `/v1/notifications`
| Method | Route | Purpose |
|---|---|---|
| GET | `/v1/notifications` | List current user's notifications |
| POST | `/v1/notifications/{notification_id}/read` | Mark a notification as read |

### Offline Sync — `/v1/sync`
| Method | Route | Purpose |
|---|---|---|
| GET | `/v1/sync/bundle` | Download an offline-first data bundle |
| POST | `/v1/sync/sos-queue` | Submit queued SOS reports created while offline |

### Admin — `/v1/admin`
| Method | Route | Purpose |
|---|---|---|
| POST | `/v1/admin/beaches` | Create a beach |
| GET | `/v1/admin/beaches/{beach_id}/validate-geometry` | Validate a beach's geometry |
| POST | `/v1/admin/activity-thresholds` | Set activity-based risk thresholds |
| POST | `/v1/admin/jurisdictions` | Create a jurisdiction (police/coast guard area) |
| POST | `/v1/admin/hospitals` | Register a hospital |
| POST | `/v1/admin/safe-zones` | Create a safe zone |
| GET | `/v1/admin/incidents` | List incidents (admin view) |
| GET | `/v1/admin/incidents/{incident_id}/acknowledgements` | View acknowledgement history for an incident |
| GET | `/v1/admin/metrics/response-latency` | Response-latency metrics (`window_days` param) |
| POST | `/v1/admin/risk-rules/tune` | Update risk-scoring rules/weights |
| POST | `/v1/admin/logs/export` | Export audit logs |

### Audit & Analytics — `/v1/admin/analytics`
| Method | Route | Purpose |
|---|---|---|
| GET | `/v1/admin/analytics/response-time` | Mean response time (`window_days`) |
| GET | `/v1/admin/analytics/alert-accuracy` | Alert accuracy rate |
| GET | `/v1/admin/analytics/missed-warnings` | Missed-warning rate |
| GET | `/v1/admin/analytics/threshold-recommendations` | Suggested risk-threshold refits |

### Safe Zone — `/v1/safezone`
| Method | Route | Purpose |
|---|---|---|
| POST | `/v1/safezone/guidance` | Compute safe-zone routing guidance |
| POST | `/v1/safezone/guidance/{guidance_id}/recompute` | Recompute guidance |
| GET | `/v1/safezone/guidance/active` | Get active guidance (optionally by incident) |
| POST | `/v1/safezone/guidance/{guidance_id}/share` | Share guidance with others |

### Live Tracking — `/v1/tracking`
| Method | Route | Purpose |
|---|---|---|
| POST | `/v1/tracking/sessions` | Start a live-tracking session |
| POST | `/v1/tracking/sessions/{session_id}/ping` | Submit a location ping |
| GET | `/v1/tracking/sessions/{session_id}` | Get latest tracking snapshot |
| PATCH | `/v1/tracking/sessions/{session_id}/status` | Admin: update session status |
| POST | `/v1/tracking/sessions/{session_id}/stop` | Stop a tracking session |

### Internal (server-to-server, internal API key) — `/internal`
| Method | Route | Purpose |
|---|---|---|
| POST | `/internal/ingest/incois` | Ingest a raw INCOIS payload |
| POST | `/internal/ingest/sachet` | Ingest a raw SACHET payload |
| POST | `/internal/recompute/risk` | Force risk recomputation |
| POST | `/internal/router/dispatch` | Drive an incident's dispatch state transition |
| POST | `/internal/router/escalate` | Drive an incident's escalation transition |
| GET | `/internal/router/incident/{incident_id}/status` | Get raw dispatch state-machine status |

### Authority Router — internal key / partner key
| Method | Route | Purpose |
|---|---|---|
| POST | `/internal/authority-router/dispatch` | Dispatch incident to police/coast guard/marine police |
| POST | `/authority-router/routes/{route_id}/ack` | Authority partner acknowledges dispatch |

### Hospital Router — internal key / partner key
| Method | Route | Purpose |
|---|---|---|
| POST | `/internal/hospital-router/dispatch` | Dispatch incident to a hospital |
| POST | `/hospital-router/routes/{route_id}/ack` | Hospital partner acknowledges dispatch |

### Health
| Method | Route | Purpose |
|---|---|---|
| GET | `/healthz` | Liveness probe |
| GET | `/readyz` | Readiness probe (checks DB connectivity) |

---

## 7. Environment Variables & Setup

### 7.1 Environment variables (`.env`, based on `.env.example`)

```bash
# --- Core ---
APP_BASE_URL=http://localhost:8000
ENVIRONMENT=local
SECRET_KEY=change-me-to-a-random-secret
INTERNAL_API_KEY=change-me

# --- Database ---
DATABASE_URL=postgresql://coastal:mypassword123@db:5432/coastal_safety
POSTGRES_DB=coastal_safety
POSTGRES_USER=coastal
POSTGRES_PASSWORD=changeme
TEST_DATABASE_URL=postgresql+psycopg://coastal:changeme@localhost:5432/coastal_safety_test

# --- Redis / Celery (broker = backend = same Redis instance) ---
REDIS_URL=redis://localhost:6379/0

# --- Ingestion sources ---
INCOIS_BASE_URL=
INCOIS_API_KEY=
INCOIS_POLL_SECONDS=900
SACHET_CAP_FEED_URL=
SACHET_API_KEY=
SACHET_POLL_SECONDS=120

# --- Raw payload storage ---
RAW_STORAGE_BACKEND=local
RAW_STORAGE_LOCAL_PATH=/var/data/raw_ingest
RAW_STORAGE_S3_BUCKET=
RAW_STORAGE_S3_PREFIX=raw-ingest

# --- Ops alerting ---
OPS_ALERT_WEBHOOK_URL=
OPS_ALERT_MIN_FAILURES=3

# --- Notifications ---
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:ops@yourdomain.com
SMS_GATEWAY_URL=
SMS_GATEWAY_KEY=

# --- Frontend build-time (consumed only by a Next.js frontend, not present in this package) ---
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

# --- Staging-only smoke test (leave blank locally) ---
PUBLIC_API_BASE_URL=
SMOKE_TEST_PHONE=
SMOKE_TEST_OTP=
```

Two settings used by `app/core/config.py` but **not present** in `.env.example` and needing to be added manually: `JWT_ALGORITHM` (defaults to `HS256`) and `JWT_EXPIRE_MINUTES` (defaults to 7 days) — these have code-level defaults, so they are optional overrides, not hard requirements.

### 7.2 Install & run — local (without Docker)

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example ../.env         # .env is expected at the repo root, not inside backend/
# then edit ../.env and fill in SECRET_KEY, INTERNAL_API_KEY, DB/Redis credentials

# Ensure PostgreSQL has the PostGIS extension available, then apply migrations in order:
psql "$DATABASE_URL" -f app/db/migrations/001_extensions_and_tables.sql
# ...continue in numeric order through 020_incident_reports_activity_type.sql

# Run the API
uvicorn app.main:app --reload --port 8000

# Run a Celery worker (repeat per queue: ingestion, risk, notification, escalation, cleanup)
celery -A app.workers.celery_app worker -Q ingestion --loglevel=info

# Run Celery Beat (only ONE beat instance should ever run)
celery -A app.workers.celery_app beat --loglevel=info
```

### 7.3 Run with Docker Compose (recommended)

```bash
# from the repo root
cp .env.example .env    # fill in required values (SECRET_KEY, POSTGRES_PASSWORD, etc.)
docker compose up --build
```

This brings up: `db` (PostGIS), `redis`, `api` (port 8000), `worker_ingestion`, `worker_risk`, `worker_notification`, `worker_escalation`, `worker_cleanup`, `beat`, and a `frontend` service definition (note: no frontend source is included in this package — see Limitations).

### 7.4 Running tests

```bash
pytest -m "not disaster_sim"    # standard test suite
pytest -m disaster_sim          # disaster-simulation tests (non-local environments only)
pytest -m e2e                   # in-process end-to-end reference flow
python scripts/e2e_smoke_test.py --base-url <staging-url>   # live HTTP smoke test
```

---

## 8. Database Migrations (applied in order)

| File | Purpose |
|---|---|
| `001_extensions_and_tables.sql` | PostGIS extension + base schema |
| `013_notification_queue_columns.sql` | Notification queue columns |
| `013b_notification_templates.sql` | Notification template table |
| `014_otp_codes.sql` | OTP codes table |
| `015_users_role_column.sql` | Adds `role` column to users |
| `016_tracking_safezone_emergency_share_tables.sql` | Tracking, safe-zone, emergency-share tables |
| `016b_safezone_emergency_share_tables.sql` | Additional safe-zone/emergency-share tables |
| `017_incident_routes_packet_payload.sql` | Adds packet payload to incident routes |
| `018_incident_reports_client_incident_id.sql` | Client-generated incident ID (for offline sync dedup) |
| `019_ack_timers.sql` | `ack_timers` table for escalation polling |
| `020_incident_reports_activity_type.sql` | Adds `activity_type` to incident reports |

---

## 9. Known Limitations / Future Improvements

- **No frontend source in this package.** `deploy/frontend.Dockerfile` and a `frontend` service in `docker-compose.yml` exist, and `docs/WIRING_LOG.md` documents an assumed API contract for it (`frontend/lib/api.ts`), but no `frontend/` directory or Next.js code is present in this zip.
- **Prometheus metrics are defined but not wired in.** `app/ops/metrics.py` only defines the instruments (counters/histograms); the actual `.inc()`/`.observe()` calls inside the dispatch/ingestion/risk code paths, and a `/metrics` HTTP endpoint, are not yet implemented.
- **External API field mappings are placeholders in places.** The INCOIS connector's field names (`wave_ht`, `curr_spd`, etc.) are explicitly flagged in-code as placeholders pending a real captured INCOIS response; the SACHET connector, by contrast, is built against a real captured response and is more trustworthy.
- **Cross-module contracts (signatures for `notification_service.enqueue()`, `audit.record_event()`, etc.) were built by inference** where the producing module wasn't available in the same session — flagged throughout `docs/WIRING_LOG.md` as assumptions rather than confirmed contracts. These should be spot-checked against the live database schema before production use.
- **Several service files retain large commented-out earlier drafts** above their final, active implementation (e.g. `admin_service.py`, `beach_service.py`, `trip_service.py`, `offline_sync_service.py`). This doesn't affect runtime behavior but is worth cleaning up for readability.
- **Local raw-payload storage only by default** (`RAW_STORAGE_BACKEND=local`); S3 support exists in code (`boto3`) but needs bucket/credentials configured to use.
- **Single Celery Beat instance is a hard operational requirement** — running more than one Beat container will double-fire scheduled tasks (explicitly called out as a critical rule in `docs/WIRING_LOG.md`), and there's no built-in safeguard against accidentally starting two.
- **Deployment runbook (`deploy/runbook.sh`)** assumes staging/pilot environments provide `PUBLIC_API_BASE_URL`, `SMOKE_TEST_PHONE`, and `SMOKE_TEST_OTP` for its live smoke test; these are not in `.env.example` and must be added per environment, along with staging-only OTP-bypass support in the auth module.
- **Alembic is listed as an optional upgrade path** but the project currently manages schema changes via hand-written, numbered raw SQL files rather than a migration framework.

---

*This documentation was generated by directly analyzing the provided source code (`WaveSafe_complete.zip`) — routes, models, services, workers, and configuration. No feature or module described above was inferred beyond what exists in the code.*
