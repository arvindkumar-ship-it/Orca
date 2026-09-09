"""
ORCA — agents/route_agent.py (NEW)

Answers: "What is the safest route for a fishing vessel considering
weather?", "Where's the nearest safe harbor?" Wraps route_optimizer.optimizer
(A* search) and safe_harbor_service — both already built.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Session

from agents.base import AgentResult, ToolRegistry, ToolSpec
from app.services import safe_harbor_service
from route_optimizer.optimizer import find_safe_route


def plan_safe_route(db: Session, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float,
                     activity_type: str = "fishing", window_start: str = None, window_end: str = None, **_) -> AgentResult:
    ws = datetime.fromisoformat(window_start) if window_start else datetime.utcnow()
    we = datetime.fromisoformat(window_end) if window_end else datetime.utcnow()
    result = find_safe_route(db, (origin_lat, origin_lng), (dest_lat, dest_lng), activity_type, ws, we)
    if not result["feasible"]:
        return AgentResult(data=result, explanation=["No safe route found — all paths cross a no-entry zone."],
                            sources=["route_optimizer (A* risk-weighted grid search)"])
    explanation = [f"Route found: {result['distance_m']/1000:.1f}km, total cost {result['total_cost']}."]
    return AgentResult(data=result, explanation=explanation,
                        sources=["route_optimizer (A* risk-weighted grid search)", "risk_engine", "geofence_service"])


def find_nearest_safe_harbor(db: Session, lat: float, lng: float, marine_zone_id: str = None, **_) -> AgentResult:
    try:
        result = safe_harbor_service.compute_safe_harbor_guidance(db, user_id=None, lat=lat, lng=lng,
                                                                    marine_zone_id=marine_zone_id, trigger_reason="agent_query")
    except ValueError as e:
        return AgentResult(data={"error": str(e)}, explanation=["No safe harbor found within 50km."],
                            sources=["safe_harbors"])
    return AgentResult(data=result, explanation=[result["instruction"]], sources=["safe_harbors", "hazard_alerts"])


def build_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(ToolSpec(
        name="route_plan_safe_route",
        description="Plan the safest route between two points using a risk-weighted A* search, avoiding no-entry zones.",
        input_schema={
            "type": "object",
            "properties": {
                "origin_lat": {"type": "number"}, "origin_lng": {"type": "number"},
                "dest_lat": {"type": "number"}, "dest_lng": {"type": "number"},
                "activity_type": {"type": "string", "enum": ["fishing", "navigation", "diving"]},
                "window_start": {"type": "string", "description": "ISO 8601 datetime"},
                "window_end": {"type": "string", "description": "ISO 8601 datetime"},
            },
            "required": ["origin_lat", "origin_lng", "dest_lat", "dest_lng"],
        },
        handler=plan_safe_route,
    ))
    reg.register(ToolSpec(
        name="route_find_nearest_safe_harbor",
        description="Find the nearest safe harbor to divert to from a lat/lng point, ranked by hazard exposure and distance.",
        input_schema={"type": "object", "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}},
                      "required": ["lat", "lng"]},
        handler=find_nearest_safe_harbor,
    ))
    return reg
