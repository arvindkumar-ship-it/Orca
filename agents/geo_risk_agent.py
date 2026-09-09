"""
ORCA — agents/geo_risk_agent.py (NEW)

Answers: "Is it safe to venture into the sea tomorrow morning?", "Which
zones should be avoided due to geofencing restrictions?" Wraps
geofence_service (R8) + zone_service.get_zone_risk (R5/R6) — both already
built, no new logic here.
"""
from __future__ import annotations
from sqlalchemy.orm import Session

from agents.base import AgentResult, ToolRegistry, ToolSpec
from app.services import geofence_service, zone_service


def check_safety_verdict(db: Session, zone_id: str, activity_type: str = "fishing", **_) -> AgentResult:
    risk = zone_service.get_zone_risk(db, zone_id, activity_type)
    explanation = [f"Risk verdict: {risk.verdict} (score {risk.risk_score})."]
    if risk.hard_override_reason:
        explanation.append(f"Hard override in effect: {risk.hard_override_reason}.")
    elif risk.explanation.top_factors:
        explanation.append(f"Top contributing factors: {', '.join(str(f) for f in risk.explanation.top_factors)}.")
    return AgentResult(data=risk.model_dump(), explanation=explanation,
                        sources=["risk_engine (logistic risk formula)", "zone_forecasts"])


def check_geofence(db: Session, lat: float, lng: float, **_) -> AgentResult:
    result = geofence_service.check_point(db, lat, lng)
    explanation = []
    if result["verdict"] == "breach_no_entry":
        explanation.append(f"Inside a no-entry MPA: {result['mpa_zone']['name']}. Do not proceed.")
    elif result["verdict"] == "advisory_zone":
        explanation.append(f"Inside an advisory/seasonal zone: {result['mpa_zone']['name']}.")
    elif result["verdict"] in ("boundary_critical", "boundary_warning"):
        explanation.append(f"{result['nearest_boundary_km']}km from {result['boundary_name']} ({result['boundary_type']}).")
    else:
        explanation.append("Clear of all restricted zones and maritime boundaries.")
    return AgentResult(data=result, explanation=explanation,
                        sources=["maritime_boundaries", "mpa_zones"])


def build_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(ToolSpec(
        name="geo_risk_check_safety",
        description="Get the safety risk verdict (safe/caution/unsafe) for a marine zone and activity type.",
        input_schema={
            "type": "object",
            "properties": {"zone_id": {"type": "string"},
                            "activity_type": {"type": "string", "enum": ["fishing", "navigation", "diving"]}},
            "required": ["zone_id"],
        },
        handler=check_safety_verdict,
    ))
    reg.register(ToolSpec(
        name="geo_risk_check_geofence",
        description="Check whether a lat/lng point is inside a restricted MPA or near a maritime boundary (IMBL/EEZ).",
        input_schema={"type": "object", "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}},
                      "required": ["lat", "lng"]},
        handler=check_geofence,
    ))
    return reg
