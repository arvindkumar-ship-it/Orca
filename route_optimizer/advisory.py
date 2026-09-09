"""ORCA — COPY of trip_planner/advisory.py's explanation-generation pattern,
applied to a route (sequence of cells) instead of a single trip window."""
from __future__ import annotations
from .risk_window import CellRiskResult

_ADVICE = {
    "safe": "Conditions look safe along the planned route. Standard precautions apply.",
    "caution": "Part of the route may turn risky. Check the flagged segments before departing.",
    "unsafe": "At least one segment of this route is unsafe. We recommend the suggested alternative route.",
    "unknown": "Not enough forecast data yet for part of this route — recheck closer to departure.",
}


def generate_route_advisory(worst_cell: CellRiskResult, geofence_result: dict,
                             alternative_available: bool) -> str:
    base = _ADVICE.get(worst_cell.worst_verdict, _ADVICE["unknown"])
    if worst_cell.dangerous_slots:
        slots = "; ".join(f"{s.strftime('%H:%M')}-{e.strftime('%H:%M')}" for s, e in worst_cell.dangerous_slots)
        base += f" Risky time slots: {slots}."
    if geofence_result.get("no_entry_violations"):
        names = ", ".join(v["name"] for v in geofence_result["no_entry_violations"])
        base += f" Route crosses restricted zone(s): {names} — rerouting required, not optional."
    elif geofence_result.get("closest_boundary_km") is not None and geofence_result["closest_boundary_km"] <= 5.0:
        base += f" Route passes within {geofence_result['closest_boundary_km']:.1f} km of {geofence_result.get('closest_boundary_name')}."
    if worst_cell.worst_verdict == "unsafe" and alternative_available:
        base += " A safer alternative route was found — see the suggested path."
    return base
