"""Module 5 — Risk Engine: feature normalization (steps 1-6)."""
from __future__ import annotations
import statistics
from dataclasses import dataclass, field
from typing import Optional

EPSILON = 1e-6

FEATURE_KEYS = [
    "wave_height", "current_speed", "wind_speed", "swell_height",
    "water_quality", "rainfall", "tide_risk", "coverage_gap",
]


@dataclass
class FeatureWindow:
    """Rolling reference sample per beach+activity, used to compute median/IQR.
    Populate from last N beach_forecasts rows (e.g. 30-day trailing window)."""
    samples: dict[str, list[float]] = field(default_factory=lambda: {k: [] for k in FEATURE_KEYS})

    def add(self, features: dict[str, Optional[float]]) -> None:
        for k in FEATURE_KEYS:
            v = features.get(k)
            if v is not None:
                self.samples[k].append(v)

    def median_iqr(self, key: str) -> tuple[float, float]:
        vals = sorted(self.samples.get(key, []))
        if len(vals) < 4:
            return 0.0, 1.0  # insufficient history -> neutral z-score fallback
        med = statistics.median(vals)
        q1 = vals[len(vals) // 4]
        q3 = vals[(3 * len(vals)) // 4]
        return med, max(q3 - q1, EPSILON)


def robust_zscore(x: Optional[float], median: float, iqr: float) -> float:
    """z_i = (x_i - median) / (IQR + eps)"""
    if x is None:
        return 0.0  # missing feature contributes no risk, not undefined risk
    return (float(x) - float(median)) / (float(iqr) + EPSILON)


def tide_state_to_risk(tide_state: Optional[str]) -> float:
    mapping = {"low": 0.1, "rising": 0.4, "high": 0.6, "falling": 0.3, "slack": 0.0}
    return mapping.get((tide_state or "").lower(), 0.2)


def coverage_gap(has_lifeguard: bool, hour_of_day: int) -> float:
    """Higher = worse coverage. No lifeguard, or outside typical patrol hours."""
    if not has_lifeguard:
        return 1.0
    return 0.0 if 6 <= hour_of_day <= 18 else 0.5
