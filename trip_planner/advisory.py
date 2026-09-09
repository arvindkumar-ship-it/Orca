"""Module 7 — Trip Planner: advisory generation (step 8)."""
from __future__ import annotations
from .risk import TripRiskResult

_ADVICE = {
    "safe": "Conditions look safe for your planned window. Standard precautions apply.",
    "caution": "Conditions may turn risky during part of your window. Check the flagged time slots before heading out.",
    "unsafe": "Conditions are unsafe for at least part of your planned window. We recommend rescheduling or choosing an alternative beach.",
    "unknown": "Not enough forecast data yet for this window — check again closer to your trip.",
}


def generate_advisory(result: TripRiskResult, alternatives: list[dict]) -> str:
    base = _ADVICE.get(result.worst_verdict, _ADVICE["unknown"])
    if result.dangerous_slots:
        slots = "; ".join(
            f"{s.strftime('%H:%M')}-{e.strftime('%H:%M')}" for s, e in result.dangerous_slots
        )
        base += f" Risky time slots: {slots}."
    if result.worst_verdict == "unsafe" and alternatives:
        names = ", ".join(a["name"] for a in alternatives)
        base += f" Safer alternatives nearby: {names}."
    return base
