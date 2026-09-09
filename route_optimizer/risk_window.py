"""
ORCA — GENERALIZE of trip_planner/risk.py -> route_optimizer/risk_window.py.

Same risk-window-scanning algorithm and R_trip = max-over-window (not
average — averaging hides danger, exactly as the original file's own
comment states), applied per grid-cell instead of per-beach. A grid cell is
identified by its (row, col) index into the route-optimizer's fixed lat/lng
grid (see optimizer.py for grid construction) rather than a marine_zones.id,
because the A* search needs a risk value at arbitrary cell coordinates that
mostly do NOT correspond to a named zone.

recommend_alternative_beaches (step 9 in the original) has NO equivalent
here — "recommend a different beach" doesn't translate to route planning,
where the entire point is finding the best path through the SAME space, not
substituting the destination. It is intentionally not ported.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

from forecast_engine.point_forecast import load_series_at_point
from forecast_engine.outlook import RiskPoint
from risk_engine.point_scoring import score_series_at_point


@dataclass
class CellRiskResult:
    max_risk: float
    worst_verdict: str
    dangerous_slots: list[tuple[datetime, datetime]]
    points: list[RiskPoint]


def compute_cell_risk(session, lat: float, lng: float, activity_type: str,
                       window_start: datetime, window_end: datetime) -> CellRiskResult:
    """R_cell = max over window (mirrors trip_planner's R_trip definition
    exactly — a single dangerous hour in the window makes the whole cell
    dangerous for that time window, it is not averaged away)."""
    hours_ahead = max(1, int((window_end - datetime.now(timezone.utc)).total_seconds() // 3600) + 1)
    series = load_series_at_point(session, lat, lng, hours_ahead=hours_ahead)
    series = [p for p in series if window_start <= p.forecast_time <= window_end]

    points = score_series_at_point(session, lat, lng, activity_type, series)
    if not points:
        return CellRiskResult(0.0, "unknown", [], [])

    max_point = max(points, key=lambda p: p.risk_score)
    dangerous = _merge([(p.forecast_time, p.forecast_time) for p in points if p.verdict != "safe"])

    return CellRiskResult(max_point.risk_score, max_point.verdict, dangerous, points)


def _merge(windows: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    if not windows:
        return []
    windows.sort()
    merged = [windows[0]]
    for s, e in windows[1:]:
        if (s - merged[-1][1]).total_seconds() <= 3600:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return merged
