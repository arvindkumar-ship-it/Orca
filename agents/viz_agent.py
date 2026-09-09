"""
ORCA — agents/viz_agent.py (NEW)

R6: every response carries a structured explanation object rendered into
map/chart/advisory-card artifacts. This agent does NOT render pixels — that
is frontend/src/pages/Chat's job (Section 7 of the build spec). It converts
raw AgentResult.data from other agents into the specific
map_markers/chart_series/advisory_card shapes the frontend's existing
map/chart components already expect (same components ExploreMap.jsx and
BeachPublicPage.jsx use — no new frontend chart library, only new data
feeding the existing ones, per the "frontend theme is frozen" constraint).
"""
from __future__ import annotations
from typing import Any

from agents.base import AgentResult, ToolRegistry, ToolSpec


def to_map_markers(pfz_or_zone_data: dict, **_) -> AgentResult:
    """Turns pfz_advisories / zones / safe_harbors result shapes into a flat
    marker list: [{lat, lng, label, kind}], the shape ExploreMap.jsx already
    consumes for beach markers today — just fed different source data."""
    markers: list[dict[str, Any]] = []
    for item in pfz_or_zone_data.get("pfz_advisories", []):
        markers.append({"lat": item.get("lat"), "lng": item.get("lng"), "label": item.get("landing_center_name"),
                         "kind": "pfz_advisory",
                         "meta": {"sst_celsius": item.get("sst_celsius"), "chlorophyll_mg_m3": item.get("chlorophyll_mg_m3")}})
    for item in pfz_or_zone_data.get("safe_harbors", []) or pfz_or_zone_data.get("alerts", []):
        # NOTE: safe_harbors/alerts result shapes (safe_harbor_service.py's
        # compute_safe_harbor_guidance / zone_service.get_active_alerts) don't
        # currently expose a plain lat/lng field either — they carry a
        # route_geojson / a geom-backed row without a flattened lat/lng key.
        # Left as None here rather than guessing a wrong field name; a real
        # fix is adding lat/lng to those two result shapes, same as the
        # pfz_advisories fix just made above.
        markers.append({"lat": item.get("lat"), "lng": item.get("lng"),
                         "label": item.get("name") or item.get("title"), "kind": "safe_harbor_or_alert", "meta": item})
    return AgentResult(data={"map_markers": markers}, explanation=[f"{len(markers)} marker(s) prepared for the map."], sources=[])


def to_route_polyline(route_data: dict, **_) -> AgentResult:
    """route_optimizer's `path` is already [(lat,lng), ...] — this just
    validates/labels it for the frontend's polyline renderer, matching the
    GeoJSON LineString-ish shape the map component expects."""
    path = route_data.get("path", [])
    polyline = [{"lat": lat, "lng": lng} for lat, lng in path]
    return AgentResult(
        data={"route_polyline": polyline, "feasible": route_data.get("feasible", False)},
        explanation=[f"Route drawn with {len(polyline)} waypoints." if polyline else "No route to draw — infeasible."],
        sources=[],
    )


def to_risk_chart_series(forecast_points: list[dict], **_) -> AgentResult:
    """Turns a forecast/risk point list into {x: time, y: risk_score}
    series the existing chart component (already used for beach risk
    timelines) can render unchanged."""
    series = [{"x": p.get("forecast_time"), "y": p.get("risk_score")} for p in forecast_points]
    return AgentResult(data={"chart_series": series}, explanation=[f"{len(series)} point(s) charted."], sources=[])


def build_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(ToolSpec(
        name="viz_to_map_markers",
        description="Convert a data result (PFZ advisories, zones, alerts, safe harbors) into map marker format.",
        input_schema={"type": "object", "properties": {"pfz_or_zone_data": {"type": "object"}}, "required": ["pfz_or_zone_data"]},
        handler=to_map_markers,
    ))
    reg.register(ToolSpec(
        name="viz_to_route_polyline",
        description="Convert a route_optimizer result into a map polyline.",
        input_schema={"type": "object", "properties": {"route_data": {"type": "object"}}, "required": ["route_data"]},
        handler=to_route_polyline,
    ))
    reg.register(ToolSpec(
        name="viz_to_risk_chart_series",
        description="Convert a forecast/risk point list into chart series format.",
        input_schema={"type": "object", "properties": {"forecast_points": {"type": "array", "items": {"type": "object"}}},
                      "required": ["forecast_points"]},
        handler=to_risk_chart_series,
    ))
    return reg
