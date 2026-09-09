"""
app/ops/check_alert_latency.py — CLI gate: hazard ingestion -> hazard_alerts
row must land within threshold. Runbook step 11. Also importable by
app/ops/metrics.py for continuous monitoring (Module 32).
Usage: python -m app.ops.check_alert_latency --threshold-seconds 60
"""
import argparse
import sys
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.db import SessionLocal


def get_p95_alert_latency_seconds(db, window_minutes: int = 60) -> float | None:
    """
    Latency = hazard_alerts.created_at - the raw source payload's observed
    timestamp. Assumes raw source payloads carry a `source_observed_at`
    field (Module 2: 'raw source payload storage separate rakho').
    """
    row = db.execute(
        text(
            "SELECT percentile_cont(0.95) WITHIN GROUP ("
            "  ORDER BY EXTRACT(EPOCH FROM (ha.created_at - rp.source_observed_at))"
            ") "
            "FROM hazard_alerts ha "
            "JOIN raw_source_payloads rp ON rp.id = ha.source_payload_id "
            "WHERE ha.created_at > now() - make_interval(mins => :window)"
        ),
        {"window": window_minutes},
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold-seconds", type=float, required=True)
    parser.add_argument("--window-minutes", type=int, default=60)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        p95 = get_p95_alert_latency_seconds(db, args.window_minutes)
    finally:
        db.close()

    if p95 is None:
        print(f"[{datetime.now(timezone.utc).isoformat()}] No hazard alerts in window — nothing to check.")
        return 0

    print(f"[{datetime.now(timezone.utc).isoformat()}] p95 alert latency: {p95:.1f}s "
          f"(threshold {args.threshold_seconds:.1f}s)")

    if p95 > args.threshold_seconds:
        print("FAIL: alert latency exceeds threshold.")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
