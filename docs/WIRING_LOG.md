# WIRING LOG — cross-module connections

This file exists so nothing is silent. Har jagah jahan ek module doosre ko
touch karta hai, ya jo naya (transparent) add hua hai, wo yahan flagged hai.

---

## 🔗 Module 27 → Module 25 (Internal Router)
**File:** `backend/app/api/internal_dispatch.py`
- Naye endpoints add hue: `POST /internal/router/dispatch`, `POST /internal/router/escalate`, `GET /internal/router/incident/{id}/status`
- Sab `DispatchStateMachine.transition()` ke through jaate hain — koi raw status UPDATE nahi, single source of truth.
- Guard: `verify_internal_key` (Module 25 ka existing dependency) — JWT nahi.

## 🔗 Module 27 → Module 26 (Background Workers)
**Files:** `escalation_worker.py`, `escalation_service.py`, `beat_schedule_addition.py`
- **⚠️ TRANSPARENT ADDITION:** naya table `ack_timers` (`backend/app/db/migrations/ack_timers.sql`) — original schema me nahi tha. Minimal purpose: ek incident ka ek active timer track karna, restart-survivable.
- `escalation_worker.check_ack_timeouts` Celery task Beat se 15s interval pe chalta hai — merge `beat_schedule_addition.py` ka entry apne existing `beat_schedule` dict me.
- Worker re-check karta hai current state before firing (agar ops ne already manually intervene kar diya to double-escalate nahi karega).

## 🔗 Module 27 → Module 23 (Notifications)
- `DispatchStateMachine._on_enter()` har state-entry pe `notification_service.enqueue(...)` call karta hai.
- **⚠️ ASSUMED SIGNATURE:** `enqueue(db, incident_report_id, type, priority, title, body)` — agar Module 23 ka actual signature alag hai, is call ko match karna padega.

## 🔗 Module 27 → audit (Module 0-19 dependency)
- Har transition `app.audit.record_event(db, event_type, entity_type, entity_id, actor_type, actor_id, payload)` call karta hai.
- **⚠️ ASSUMED SIGNATURE** — same caveat as above.

## 🔗 Module 30 (Deployment) → Module 26 (Workers)
**File:** `deploy/docker-compose.yml`, `backend/app/workers/celery_app.py`
- Ek hi backend image, alag `CMD` se: `api`, `worker_ingestion`, `worker_risk`, `worker_notification`, `worker_escalation`, `worker_cleanup`, `beat` — 7 services total.
- **⚠️ CRITICAL RULE:** sirf ek `beat` container chale — duplicate beat = duplicate escalation firing.
- `celery_app.py` ka `task_routes` dict queue names ko docker-compose ke `-Q` flags se match karta hai — dono ko sath me edit karna.

## 🔗 Module 30 → Module 31 (Testing)
**File:** `deploy/runbook.sh`
- Step 8 (`sandbox tests`) → `pytest -m "not disaster_sim"`
- Step 9 (`disaster simulations`) → `pytest -m disaster_sim`, sirf non-local envs me chalta hai
- Step 11/12 → `backend/app/ops/check_alert_latency.py` aur `check_sos_routing.py` — ye scripts runbook.sh ne call kiye the isliye ban gaye (backward dependency).

## 🔗 Module 28 (E2E Reference Flow) — real code, not test-only
**Files:** `tests/e2e/test_e2e_reference_flow.py`, `scripts/e2e_smoke_test.py`
- Original breakdown marked Module 28 "test-only, no code" — banaya gaya kyunki aapne explicitly "real systems ke liye" manga.
- **Two layers, deliberately different:**
  1. `tests/e2e/test_e2e_reference_flow.py` — in-process, DB-direct (jaisa Module 31), lekin poora lifecycle ek hi test me: trip → SOS → dispatch → ack/timeout → escalation chain → resolve/close → notifications → audit. `pytest -m e2e`.
  2. `scripts/e2e_smoke_test.py` — **real HTTP calls** ek actual deployed instance (staging/pilot) ke against, `requests` library se. Ye confirm karta hai ki Celery Beat + workers real environment me zinda hain, sirf code compile nahi hota.
- **⚠️ `--full-timing` flag:** default me ack-timer wait skip hota hai (deploy fast rahe), lekin `--full-timing` pass karne pe real 90/120/180s escalation chain wait karta hai — sirf staging me chalao, CI me nahi.
- **Wired into `deploy/runbook.sh`** naye steps 8b/8c ke roop me — sandbox tests ke baad, disaster_sim se pehle. Non-local envs pe `scripts/e2e_smoke_test.py` chalta hai; local pe skip.
- **⚠️ NEW ENV VARS REQUIRED** (add to `.env.<environment>`, not yet in `.env.example`): `PUBLIC_API_BASE_URL`, `SMOKE_TEST_PHONE`, `SMOKE_TEST_OTP` (staging-only test-mode OTP bypass — Module 24 ko ye support karna hoga, ya `SMOKE_TEST_OTP` ko real SMS-received code se replace karo).

## 🔗 Module 31 → Module 27
**Files:** `tests/test_dispatch_state_machine.py`, `tests/test_acceptance_criteria.py`, `tests/test_failure_scenarios.py`
- Directly `DispatchStateMachine` aur `escalation_service` import karke test karte hain — real Postgres+PostGIS test DB chahiye (sqlite nahi, kyunki geom columns generated/PostGIS-specific hain).
- **⚠️ ASSUMPTION:** tables `users`, `beaches`, `incident_reports`, `incident_routes`, `notification_queue`, `offline_sync_queue`, `beach_risk_scores`, `hazard_alerts` schema me exist karte hain jaisa `conftest.py` ke fixtures assume karte hain — agar column names alag hain, fixtures update karne honge.

## 🔗 Module 32 (Ops) → Module 27/26/25
**File:** `backend/app/ops/metrics.py`
- **⚠️ NOT YET WIRED** — ye sirf metric *definitions* hain. Actual `.inc()`/`.observe()` calls abhi kisi bhi module me add nahi kiye (avoid touching already-delivered files without asking). File ke docstring me exact integration points likhe hain (e.g. `DispatchStateMachine.transition()` me `observe_dispatch_latency()` call karna hoga).
- `/metrics` FastAPI endpoint bhi abhi tak nahi bana — pending.

## 🔗 Module 29 (Frontend) → Backend APIs
**File:** `frontend/lib/api.ts`
- Public APIs assume kiye: `/v1/sos`, `/v1/sos/{id}`, `/v1/sos/{id}/routes`, `/v1/sos/{id}/ack`, `/v1/safe-zones/nearest`, `/v1/auth/otp/*`, `/v1/beaches`, `/v1/trips`, `/v1/notifications`, `/v1/emergency-contacts`, `/v1/admin/*`.
- **⚠️ ASSUMPTION:** exact response shapes match `BeachSummary`, `BeachDetail`, `TripPlan`, etc. TypeScript interfaces — backend response agar different hai to types mismatch honge.
- **⚠️ GAP:** `map/page.tsx` ko beach `lat`/`lng` chahiye map marker ke liye — `BeachSummary` me abhi wo fields nahi the (sirf list view ke liye). Backend response me add karna hoga.
- Frontend `/internal/*` routes kabhi call nahi karta — wo server-to-server only hain (security boundary maintained).

## 🔗 Module 30 → Module 29 (Frontend)
**Files:** `deploy/frontend.Dockerfile`, `frontend/next.config.js`
- `output: "standalone"` zaroori hai Dockerfile ke slim runtime stage ke liye — bina iske build fail hoga.
- `NEXT_PUBLIC_API_BASE_URL` build-time arg hai (Next.js ka rule — runtime env nahi chalega client-side code ke liye).

---

## Summary: Naye (transparent) additions is package me
1. `ack_timers` table — Module 27/26 ke liye ack-timeout persistence
2. `/internal/router/dispatch`, `/internal/router/escalate`, `/internal/router/incident/{id}/status` — 3 naye internal endpoints
3. `manual_ops → {dispatched, acknowledged, closed}` transitions — state graph me diagram se extra (warna manual_ops dead-end ban jata)

## Summary: Cheezein jo maine banayi kyunki kisi aur file ne unhe reference kiya tha (backward-fill)
- `app/ops/check_alert_latency.py`, `check_sos_routing.py` — `runbook.sh` unhe call karta hai
- `app/api/health.py` — `backend.Dockerfile`'s `HEALTHCHECK` unhe hit karta hai
- `app/workers/celery_app.py` — `docker-compose.yml` aur `escalation_worker.py` dono isko import karte hain
