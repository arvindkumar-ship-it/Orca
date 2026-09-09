# Modules 8, 9, 10, 11, 12, 13, 14 — Latest FastAPI versions (as delivered in chat, no changes)

## Contents
- Module 8  — SOS / Emergency Dispatch: app/services/sos_service.py, app/schemas/sos.py
- Module 9  — Authority Router: app/services/authority_router_service.py, app/schemas/authority_router.py, app/api/authority_router.py
- Module 10 — Hospital Router: app/services/hospital_router_service.py, app/schemas/hospital_router.py, app/api/hospital_router.py
- Module 11 — Safe-Zone Guidance: app/models/safezone.py, app/schemas/safezone.py, app/services/safezone_service.py, app/api/safezone.py
- Module 12 — Live Tracking: app/models/tracking.py, app/schemas/tracking.py, app/services/tracking_service.py, app/api/tracking.py
    + frontend/ (Next.js PWA: useLiveTracking hook, idb offline queue, service worker addition, track page + components)
- Module 13 — Notification System (canonical deliver()/enqueue() contract): app/models/notification.py,
    app/services/notification_service.py, app/services/notification_templates.py,
    app/services/channels/{push_channel.py, sms_channel.py}, app/db/migrations/013*.sql
- Module 14 — Emergency Contact Fanout: app/services/fanout_service.py, app/schemas/fanout.py

## NOT included (external dependencies — assumed to already exist in your project)
- app/core/db.py (Base, get_db, SessionLocal)
- app/core/security.py (get_current_user, get_current_admin, verify_internal_key) —
  `verify_partner_key` used by Modules 9/10's ack webhooks is REFERENCED but NOT DEFINED anywhere —
  still needs to be written, confirmed missing during the Module 24 file review.
- app/core/config.py (settings.APP_BASE_URL, VAPID_*, SMS_GATEWAY_*)
- app/core/audit.py — log_audit_event(db, event_type, entity_type, entity_id, actor_type, actor_id, payload)
  (confirmed real, used by Module 25's internal_service.py)
- app/core/dispatch_states.py, app/services/dispatch_state_machine.py — Module 27, YOUR file, not modified
- app/services/audit.py — log_event(...) (used by Modules 11/12, alternate import path — see open item below)

## Known open items (flagged during consistency review, not resolved)
1. Module 10's acknowledge_hospital_route: sequencing gap between Module 8's PARALLEL
   authority+hospital dispatch and Module 27's LINEAR state graph
   (DISPATCHED -> ACKNOWLEDGED -> ROUTED -> EN_ROUTE -> HOSPITAL_NOTIFIED). Currently has a
   defensive try/except that silently skips the state transition if out of sequence — this is
   a band-aid, not a real fix. Needs a decision: either add HOSPITAL_NOTIFIED as a valid
   transition target from DISPATCHED in Module 27's TRANSITIONS graph, or change Module 8 to
   dispatch sequentially.
2. Two audit import paths seen across files: `app.core.audit.log_audit_event` (Module 25,
   confirmed real) vs `app.audit.record_event` (Module 27's dispatch_state_machine.py) vs
   `app.services.audit.log_event` (Modules 11/12/14 in this zip, from an earlier session).
   NOT reconciled — confirm which of these actually exists in your codebase and adjust imports
   in Modules 11/12/14 if `app.services.audit` isn't real.
3. Module 13's earlier raw-SQL version (enqueue_notification/process_queue) is superseded by
   this canonical enqueue()/deliver() version — if any other module still calls the old
   function names, those calls need updating to match this file.
4. verify_partner_key (Modules 9/10 ack endpoints) — not defined anywhere in your uploaded
   Module 24 files. Must be added to app/core/security.py before these routes will import successfully.

## Superseded / deleted (do not use)
- Module 15 (Escalation Policy) — fully discarded, replaced by Module 27's ack_timers +
  DispatchStateMachine system.
- Old app/workers/escalation_worker.py (ORM-based, check_ack_timers) — replace with Module 27's version.
- Old app/services/escalation_service.py (escalate() function) — replace with Module 27's version.
- /internal/router/escalate in module-25's internal.py — removed, Module 27's internal_dispatch.py owns this path now.
