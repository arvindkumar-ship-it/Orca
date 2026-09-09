# Coastal Safety Platform — Modules 27, 29, 30, 31, 32 (partial)

Ye zip un modules ka poora code hai jo is conversation me bana. Modules
0-26, 28, 33, 34 is package me NAHI hain (unka code nahi likha gaya —
sirf dependencies ke roop me assume kiya gaya).

## Structure
```
backend/app/
  core/dispatch_states.py           Module 27
  services/dispatch_state_machine.py Module 27
  services/escalation_service.py     Module 27 (wiring → 26)
  workers/escalation_worker.py       Module 27 (wiring → 26)
  workers/celery_app.py              Module 30
  workers/beat_schedule_addition.py  Module 27 (wiring → 26)
  api/internal_dispatch.py           Module 27 (wiring → 25)
  api/health.py                      Module 30
  ops/metrics.py                     Module 32 (partial — definitions only)
  ops/check_alert_latency.py         Module 31/32
  ops/check_sos_routing.py           Module 31/32
  db/migrations/ack_timers.sql       Module 27 (transparent addition)

frontend/                            Module 29 — full Next.js app dir
deploy/                              Module 30 — Docker, compose, runbook, env
tests/ + pytest.ini                  Module 31
tests/e2e/                           Module 28 (in-process reference flow)
scripts/e2e_smoke_test.py            Module 28 (live-system smoke test)

WIRING_LOG.md                        <- sabse pehle ye padho
```

## Read this first
**`WIRING_LOG.md`** — har cross-module connection, har transparent addition,
aur har assumption jo maine banayi hai wo yahan highlighted hai. Isse pehle
integrate karo, phir code.

## Module 28 note
Original spec ne Module 28 ko "test-only, no code" kaha tha. User ne real
code manga "real systems ke liye" — isliye do layers banaye: in-process
pytest suite (`tests/e2e/`) aur live-deployment smoke script
(`scripts/e2e_smoke_test.py`, real HTTP calls staging/pilot ke against).
Dono `deploy/runbook.sh` me wired hain (steps 8b/8c).

## Not done yet (Module 32 incomplete)
- Prometheus alert_rules.yml
- `/metrics` FastAPI endpoint
- Actual `.inc()`/`.observe()` calls wired into Module 27/26 code
