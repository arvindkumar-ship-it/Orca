"""Module 6 — Forecast Engine: safe-window detection (steps 5-10)."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from risk_engine.data_loaders import (  # Module 5 reuse — same scoring, forward-applied
    build_feature_window, extract_current_features, load_activity_profile, load_beach,
)
from risk_engine.scoring import compute_risk

CHANGE_THRESHOLD = 0.15  # step 9: risk delta considered a meaningful change


@dataclass
class RiskPoint:
    forecast_time: datetime
    risk_score: float
    verdict: str


@dataclass
class ForecastOutlook:
    current_verdict: str
    current_risk: float
    window_3h: Optional[str]
    window_12h: Optional[str]
    safe_window_start: Optional[datetime]
    safe_window_end: Optional[datetime]
    no_go_windows: list[tuple[datetime, datetime]]
    expected_improvement_time: Optional[datetime]
    confidence: float


def score_series(session, beach_id: str, activity_type: str, series) -> list[RiskPoint]:
    """step 6: apply Module 5's scoring to each future forecast point (no hazard
    overrides applied here — those are point-in-time and re-checked live by
    Module 5 at request time; this projects the deterministic feature-based risk)."""
    beach = load_beach(session, beach_id)
    profile = load_activity_profile(session, beach_id, activity_type)
    if beach is None or profile is None:
        return []
    fw = build_feature_window(session, beach_id)
    medians_iqrs = {k: fw.median_iqr(k) for k in
                     ("wave_height", "current_speed", "wind_speed", "swell_height",
                      "water_quality", "rainfall", "tide_risk", "coverage_gap")}

    points = []
    for row in series:
        features = {
            "wave_height": row.wave_height, "current_speed": row.current_speed,
            "wind_speed": row.wind_speed, "swell_height": None,
            "water_quality": None, "rainfall": None, "tide_risk": 0.0, "coverage_gap": 0.0,
        }
        score, verdict, _ = compute_risk(features, medians_iqrs, active_alert_types=[],
                                          weights=profile.risk_weights or None)
        points.append(RiskPoint(row.forecast_time, score, verdict))
    return points


def find_safe_windows(points: list[RiskPoint]) -> tuple[Optional[datetime], Optional[datetime], list[tuple]]:
    """steps 6-7: identify best safe window + all no-go windows."""
    safe_start, safe_end = None, None
    best_len = -1.0
    no_go: list[tuple[datetime, datetime]] = []

    run_start = None
    for i, p in enumerate(points):
        if p.verdict == "safe":
            if run_start is None:
                run_start = p.forecast_time
        else:
            if run_start is not None:
                run_len = (points[i - 1].forecast_time - run_start).total_seconds()
                if run_len > best_len:
                    best_len, safe_start, safe_end = run_len, run_start, points[i - 1].forecast_time
                run_start = None
        if p.verdict == "unsafe":
            no_go.append((p.forecast_time, p.forecast_time))

    if run_start is not None:
        run_len = (points[-1].forecast_time - run_start).total_seconds()
        if run_len > best_len:
            safe_start, safe_end = run_start, points[-1].forecast_time

    no_go = _merge_adjacent(no_go)
    return safe_start, safe_end, no_go


def _merge_adjacent(windows: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    if not windows:
        return []
    windows.sort(key=lambda w: w[0])
    merged = [windows[0]]
    for s, e in windows[1:]:
        if (s - merged[-1][1]).total_seconds() <= 3600:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return merged


def build_outlook(points: list[RiskPoint], now: datetime) -> ForecastOutlook:
    """steps 6-11: assemble full outlook including 3h/12h windows and confidence."""
    if not points:
        return ForecastOutlook("unknown", 0.0, None, None, None, None, [], None, 0.0)

    current = points[0]
    v3 = _worst_verdict_in(points, now, 3)
    v12 = _worst_verdict_in(points, now, 12)
    safe_start, safe_end, no_go = find_safe_windows(points)

    improvement_time = None
    for p in points:
        if p.verdict == "safe" and current.verdict != "safe":
            improvement_time = p.forecast_time
            break

    confidence = min(1.0, len(points) / 24.0)  # step 8: fewer forward points -> lower confidence

    return ForecastOutlook(
        current_verdict=current.verdict, current_risk=current.risk_score,
        window_3h=v3, window_12h=v12,
        safe_window_start=safe_start, safe_window_end=safe_end,
        no_go_windows=no_go, expected_improvement_time=improvement_time,
        confidence=round(confidence, 2),
    )


def _worst_verdict_in(points: list[RiskPoint], now: datetime, hours: int) -> Optional[str]:
    order = {"safe": 0, "caution": 1, "unsafe": 2}
    window = [p for p in points if (p.forecast_time - now).total_seconds() <= hours * 3600]
    if not window:
        return None
    return max(window, key=lambda p: order[p.verdict]).verdict
