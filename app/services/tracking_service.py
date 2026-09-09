from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core import audit

STALE_AFTER_SECONDS = 90
CRITICAL_SPEED_THRESHOLD_MPS = 0.3
AMBULANCE_AVG_SPEED_MPS = 8.3  # heuristic, shared with hospital-router module
WALK_SPEED_MPS = 1.1


def start_tracking(db: Session, incident_report_id: str, user_id: str | None) -> str:
    row = db.execute(text("""
        INSERT INTO live_tracking_sessions (incident_report_id, user_id, status, tracking_mode)
        VALUES (:irid, :uid, 'awaiting_acknowledgment', 'critical') RETURNING id
    """), {"irid": incident_report_id, "uid": user_id}).mappings().first()
    db.commit()
    audit.log_audit_event(db, event_type="tracking.session.started", entity_type="live_tracking_sessions",
                     entity_id=str(row["id"]), actor_type="user" if user_id else "system", actor_id=user_id,
                     payload={"incident_report_id": incident_report_id})
    return str(row["id"])


def ingest_ping(db: Session, session_id: str, p) -> None:
    sess = db.execute(text("SELECT status, ended_at FROM live_tracking_sessions WHERE id = :id"),
                       {"id": session_id}).mappings().first()
    if not sess:
        raise ValueError("SESSION_NOT_FOUND")
    if sess["ended_at"]:
        raise ValueError("SESSION_ALREADY_ENDED")

    db.execute(text("""
        INSERT INTO location_pings (session_id, geom, accuracy_m, speed_mps, heading, battery_pct, signal_strength, source)
        VALUES (:sid, ST_SetSRID(ST_MakePoint(:lng,:lat),4326), :acc, :speed, :heading, :batt, :sig, :src)
    """), {"sid": session_id, "lng": p.lng, "lat": p.lat, "acc": p.accuracy_m, "speed": p.speed_mps,
           "heading": p.heading, "batt": p.battery_pct, "sig": p.signal_strength, "src": p.source})

    mode = "stable" if (p.speed_mps or 0) < CRITICAL_SPEED_THRESHOLD_MPS else "critical"
    db.execute(text("UPDATE live_tracking_sessions SET last_ping_at = now(), tracking_mode = :m WHERE id = :id"),
               {"m": mode, "id": session_id})
    db.commit()


def update_status(db: Session, session_id: str, status: str, actor_type: str, actor_id: str | None) -> None:
    res = db.execute(text("""UPDATE live_tracking_sessions SET status = :s
                              WHERE id = :id AND ended_at IS NULL RETURNING id"""),
                      {"s": status, "id": session_id})
    if res.rowcount == 0:
        raise ValueError("SESSION_NOT_FOUND_OR_ENDED")
    db.commit()
    audit.log_audit_event(db, event_type="tracking.status.updated", entity_type="live_tracking_sessions",
                     entity_id=session_id, actor_type=actor_type, actor_id=actor_id, payload={"status": status})


def stop_tracking(db: Session, session_id: str, reason: str, actor_id: str | None) -> None:
    res = db.execute(text("""
        UPDATE live_tracking_sessions SET ended_at = now(), end_reason = :r,
               status = CASE WHEN :r = 'resolved' THEN 'resolved' ELSE status END
        WHERE id = :id AND ended_at IS NULL RETURNING id
    """), {"r": reason, "id": session_id})
    if res.rowcount == 0:
        raise ValueError("SESSION_NOT_FOUND_OR_ALREADY_ENDED")
    db.commit()
    audit.log_audit_event(db, event_type="tracking.session.stopped", entity_type="live_tracking_sessions",
                     entity_id=session_id, actor_type="user" if actor_id else "system", actor_id=actor_id,
                     payload={"reason": reason})


def _eta_minutes(db: Session, lat: float, lng: float, to_geom_sql: str, params: dict, speed_mps: float) -> float | None:
    row = db.execute(text(f"""
        SELECT ST_Distance(ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, ({to_geom_sql})::geography) AS dist_m
    """), {"lng": lng, "lat": lat, **params}).mappings().first()
    if not row or row["dist_m"] is None:
        return None
    return round(float(row["dist_m"]) / speed_mps / 60, 1)


def get_snapshot(db: Session, session_id: str) -> dict:
    r = db.execute(text("""
        SELECT lts.id, lts.incident_report_id, lts.status, lts.tracking_mode,
               lp.created_at AS ping_time, ST_X(lp.geom) AS lng, ST_Y(lp.geom) AS lat
        FROM live_tracking_sessions lts
        LEFT JOIN LATERAL (SELECT * FROM location_pings WHERE session_id = lts.id ORDER BY created_at DESC LIMIT 1) lp ON true
        WHERE lts.id = :id
    """), {"id": session_id}).mappings().first()
    if not r:
        raise ValueError("SESSION_NOT_FOUND")

    last_ping = None
    hospital_eta = safe_zone_eta = responder_eta = None

    if r["ping_time"]:
        is_stale = (datetime.now(timezone.utc) - r["ping_time"]).total_seconds() > STALE_AFTER_SECONDS
        last_ping = {"lat": float(r["lat"]), "lng": float(r["lng"]), "created_at": r["ping_time"].isoformat(), "is_stale": is_stale}

        hosp_route = db.execute(text("""
            SELECT h.id FROM incident_routes rt JOIN hospitals h ON h.id = rt.target_id
            WHERE rt.incident_report_id = :irid AND rt.target_type = 'hospital' ORDER BY rt.route_rank ASC LIMIT 1
        """), {"irid": r["incident_report_id"]}).mappings().first()
        if hosp_route:
            hospital_eta = _eta_minutes(db, r["lat"], r["lng"], "SELECT geom FROM hospitals WHERE id = :hid",
                                         {"hid": hosp_route["id"]}, AMBULANCE_AVG_SPEED_MPS)

        sz = db.execute(text("""
            SELECT eta_minutes FROM safezone_guidance
            WHERE incident_report_id = :irid AND superseded = false ORDER BY computed_at DESC LIMIT 1
        """), {"irid": r["incident_report_id"]}).mappings().first()
        if sz:
            safe_zone_eta = float(sz["eta_minutes"])

        responder = db.execute(text("""
            SELECT rp.id FROM incident_routes rt JOIN rescue_posts rp ON rp.id = rt.target_id
            WHERE rt.incident_report_id = :irid AND rt.target_type = 'rescue_post' AND rt.ack_status != 'failed'
            ORDER BY rt.route_rank ASC LIMIT 1
        """), {"irid": r["incident_report_id"]}).mappings().first()
        if responder:
            responder_eta = _eta_minutes(db, r["lat"], r["lng"], "SELECT geom FROM rescue_posts WHERE id = :rid",
                                          {"rid": responder["id"]}, WALK_SPEED_MPS)

    return {
        "session_id": str(r["id"]), "incident_report_id": str(r["incident_report_id"]), "status": r["status"],
        "tracking_mode": r["tracking_mode"], "last_ping": last_ping, "hospital_eta_minutes": hospital_eta,
        "safe_zone_eta_minutes": safe_zone_eta, "responder_eta_minutes": responder_eta,
    }


def find_stale_sessions(db: Session) -> list[str]:
    # Called by Celery Beat instead of a Node worker loop.
    rows = db.execute(text(f"""
        SELECT id FROM live_tracking_sessions
        WHERE ended_at IS NULL AND last_ping_at IS NOT NULL
          AND last_ping_at < now() - interval '{STALE_AFTER_SECONDS} seconds'
    """)).mappings().all()
    return [str(r["id"]) for r in rows]
