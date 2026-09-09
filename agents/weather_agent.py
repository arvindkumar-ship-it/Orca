"""
ORCA — agents/weather_agent.py (NEW)

Answers: "Are there any lightning/cyclone alerts near me?", "What's the
wind/wave/tide forecast at my fishing location?" Wraps zone_service's
forecast/alert reads — no scoring logic here, that lives in risk_engine.
"""
from __future__ import annotations
from sqlalchemy.orm import Session

from agents.base import AgentResult, ToolRegistry, ToolSpec
from app.services import zone_service


def get_forecast(db: Session, zone_id: str, activity_type: str = "fishing", hours: int = 24, **_) -> AgentResult:
    forecast = zone_service.get_zone_forecast(db, zone_id, activity_type, hours)
    if not forecast:
        return AgentResult(data={"forecast": []}, explanation=["No forecast data available for this zone."],
                            sources=["zone_forecasts"])
    latest = forecast[0]
    explanation = [
        f"Latest forecast slot: wave height {latest.wave_height}m, wind {latest.wind_speed}m/s.",
        f"Verdict for {activity_type}: {latest.verdict or 'unknown'}.",
    ]
    return AgentResult(
        data={"forecast": [f.model_dump() for f in forecast]},
        explanation=explanation,
        sources=["forecast_engine (Open-Meteo Marine + Weather)", "zone_forecasts"],
    )


def get_active_hazard_alerts(db: Session, lat: float, lng: float, radius_m: int = 25000, **_) -> AgentResult:
    alerts = zone_service.get_active_alerts(db, lat, lng, radius_m)
    if not alerts:
        return AgentResult(data={"alerts": []}, explanation=["No active hazard alerts within range."],
                            sources=["hazard_alerts (SACHET/NDMA CAP feed)"])
    severities = sorted({a.severity for a in alerts})
    explanation = [f"{len(alerts)} active alert(s) within {radius_m/1000:.0f}km — severities: {', '.join(severities)}."]
    return AgentResult(
        data={"alerts": [a.model_dump() for a in alerts]},
        explanation=explanation,
        sources=["hazard_alerts (SACHET/NDMA CAP feed)"],
    )


def build_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(ToolSpec(
        name="weather_get_forecast",
        description="Get wind/wave/tide forecast for a marine zone over the next N hours.",
        input_schema={
            "type": "object",
            "properties": {
                "zone_id": {"type": "string"},
                "activity_type": {"type": "string", "enum": ["fishing", "navigation", "diving"]},
                "hours": {"type": "integer", "default": 24},
            },
            "required": ["zone_id"],
        },
        handler=get_forecast,
    ))
    reg.register(ToolSpec(
        name="weather_get_active_alerts",
        description="Get active weather/lightning/cyclone hazard alerts near a lat/lng point.",
        input_schema={
            "type": "object",
            "properties": {
                "lat": {"type": "number"}, "lng": {"type": "number"},
                "radius_m": {"type": "integer", "default": 25000},
            },
            "required": ["lat", "lng"],
        },
        handler=get_active_hazard_alerts,
    ))
    return reg
