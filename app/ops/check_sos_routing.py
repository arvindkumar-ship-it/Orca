"""
app/ops/check_sos_routing.py — CLI gate: every incident dispatched in the
window must have reached >= --min-targets distinct incident_routes rows
(acceptance criterion, re-checked continuously in Module 32 monitoring).
Usage: python -m app.ops.check_sos_routing --min-targets 2
"""
import argparse
import sys
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.db import SessionLocal


def find_undertargeted_incidents(db, min_targets: int, window_minutes: int) -> list[str]:
    rows = db.execute(
        text(
            "SELECT ir.id, COUNT(DISTINCT rt.target_type) AS target_count "
            "FROM incident_reports ir "
            "LEFT JOIN incident_routes rt ON rt.incident_report_id = ir.id "
            "WHERE ir.status NOT IN ('created', 'validated', 'location_locked', 'packed') "
            "  AND ir.created_at > now() - make_interval(mins => :window) "
            "GROUP BY ir.id "
            "HAVING COUNT(DISTINCT rt.target_type) < :min_targets"
        ),
        {"window": window_minutes, "min_targets": min_targets},
    ).fetchall()
    return [str(r[0]) for r in rows]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-targets", type=int, required=True)
    parser.add_argument("--window-minutes", type=int, default=60)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        offenders = find_undertargeted_incidents(db, args.min_targets, args.window_minutes)
    finally:
        db.close()

    ts = datetime.now(timezone.utc).isoformat()
    if offenders:
        print(f"[{ts}] FAIL: {len(offenders)} incident(s) below {args.min_targets} routed targets:")
        for oid in offenders:
            print(f"  - {oid}")
        return 1

    print(f"[{ts}] PASS: all dispatched incidents reached >= {args.min_targets} targets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
