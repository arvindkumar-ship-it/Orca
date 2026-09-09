# """
# Module 3 — Data Ingestion : SACHET connector

# CORRECTED 2026-08-12 against the REAL live response, captured directly from
# browser DevTools Network tab on https://sachet.ndma.gov.in/CapFeed:
#     POST https://sachet.ndma.gov.in/cap_public_website/FetchAllAlertDetails

# This is NOT CAP-XML — it's SACHET's own flat JSON array. Every field name
# below (identifier, severity, severity_color, disaster_type, centroid, etc.)
# was copied verbatim from a real captured response (78 live alerts, 12 Aug
# 2026), not invented.

# UNCERTAIN / FLAGGED, not guessed silently:
# - Request body: not confirmed empty vs non-empty from the captured session.
#   Sending `{}` below — if the real server needs specific POST params, this
#   will need adjusting once tested against the live endpoint.
# - Severity mapping (severity_color -> internal Severity enum): SACHET uses
#   red/orange/yellow, which doesn't map 1:1 onto CAP's Extreme/Severe/
#   Moderate/Minor. The mapping below is a reasonable guess, not an official
#   SACHET spec — verify/adjust once compared against how disaster_type
#   severity is actually treated in practice.
# - No polygon/area geometry in this feed — only a single `centroid` point
#   ("lng,lat" string). Confirmed from live data across all 78 alerts.
#   Beach-matching must use point + area_covered (km²) as a rough radius,
#   not exact polygon containment.
# """
# from __future__ import annotations

# from datetime import datetime, timedelta, timezone
# from typing import Any

# import httpx

# from .base_connector import BaseConnector, ConnectorError
# from .config import settings
# from .schemas import RecordType, Severity, SourceSystem

# _IST = timezone(timedelta(hours=5, minutes=30))

# # FLAGGED — approximate mapping, not an official SACHET spec (see module docstring).
# _COLOR_SEVERITY_MAP = {
#     "red": Severity.SEVERE,
#     "orange": Severity.MODERATE,
#     "yellow": Severity.MINOR,
# }

# _HARD_OVERRIDE_DISASTER_TYPES = {
#     "tsunami",
#     "storm surge",
#     "cyclone",
#     "evacuation",
#     "beach closure",
# }
# def _classify_event_type(disaster_type: str) -> str:
#     """SACHET's disaster_type is free text (e.g. 'Cyclonic Storm', 'Tsunami
#     Alert'), not the exact strings normalizer._EVENT_TYPE_MAP expects
#     ('cyclone warning', 'tsunami warning'). This does keyword matching
#     against the disaster_type text to produce the exact map key when a
#     real coastal-hazard keyword is present, so genuine cyclone/tsunami/
#     storm-surge/high-wave alerts get correctly flagged as hard_override
#     instead of silently falling to OTHER. Non-coastal hazards (rain,
#     thunderstorm, flood, lightning) correctly remain unmapped -> OTHER,
#     since CanonicalAlertType has no generic category for them."""
#     dt = disaster_type.lower()
#     if "tsunami" in dt:
#         return "tsunami warning"
#     if "storm surge" in dt:
#         return "storm surge warning"
#     if "cyclon" in dt:  # matches "cyclone" and "cyclonic"
#         return "cyclone warning"
#     if "high wave" in dt or "high-wave" in dt:
#         return "high wave warning"
#     if "evacuat" in dt:
#         return "evacuation order"
#     if "coast guard" in dt:
#         return "coast guard closure"
#     if "beach closure" in dt or "beach closed" in dt:
#         return "beach closure"
#     return dt  # unmapped -> normalizer will correctly fall back to OTHER


# class SachetConnector(BaseConnector):
#     source = SourceSystem.SACHET

#     def _fetch_raw(self, client: httpx.Client) -> Any:
#         if not settings.sachet_cap_feed_url:
#             raise ConnectorError("SACHET_CAP_FEED_URL not configured")
#         resp = client.post(
#             settings.sachet_cap_feed_url,
#             json={},
#             headers={"Authorization": f"Bearer {settings.sachet_api_key}"} if settings.sachet_api_key else {},
#         )
#         resp.raise_for_status()
#         return resp.json()

#     def _parse(self, raw_payload: Any) -> list[dict]:
#         alerts = raw_payload if isinstance(raw_payload, list) else raw_payload.get("data", [])
#         items: list[dict] = []

#         for alert in alerts:
#             identifier = alert.get("identifier")
#             if identifier is None:
#                 continue

#             disaster_type = (alert.get("disaster_type") or "").strip().lower()
#             color = (alert.get("severity_color") or "").strip().lower()

#             items.append({
#                 "source": SourceSystem.SACHET,
#                 "source_id": f"sachet:{identifier}",
#                 "type": RecordType.HAZARD_WARNING,
#                 "severity": _COLOR_SEVERITY_MAP.get(color, Severity.MODERATE),
#                 "geometry": self._build_geometry(alert.get("centroid"), alert.get("area_covered")),
#                 "start_time": self._parse_ist_time(alert.get("effective_start_time")),
#                 "end_time": self._parse_ist_time(alert.get("effective_end_time")),
#                 "raw_json": alert,
#                 "parsed_fields": {
#                     "event_type": disaster_type,  # normalizer reads this exact key name
#                     "disaster_type": alert.get("disaster_type"),
#                     "severity_tag": alert.get("severity"),          # ALERT / WATCH / WARNING
#                     "severity_level": alert.get("severity_level"),  # "Very Likely" / "Likely" / etc.
#                     "area_description": alert.get("area_description"),
#                     "warning_message": alert.get("warning_message"),
#                     "language": alert.get("actual_lang"),
#                     "alert_source": alert.get("alert_source"),
#                     "sender_org_id": alert.get("sender_org_id"),
#                     "area_covered_sqkm": alert.get("area_covered"),
#                     "disseminated": alert.get("disseminated") == "true",
#                     "hard_override_flag": any(t in disaster_type for t in _HARD_OVERRIDE_DISASTER_TYPES),
#                 },
#                 "source_confidence": 1.0,
#             })
#         return items

#     # @staticmethod
#     # def _build_geometry(centroid: str | None) -> dict | None:
#     #     """centroid is 'lng,lat' — confirmed against real Tripura/Gujarat/
#     #     Assam alerts where the first number always falls in India's
#     #     longitude range and the second in its latitude range."""
#     #     if not centroid:
#     #         return None
#     #     try:
#     #         lng_str, lat_str = centroid.split(",")
#     #         return {"type": "Point", "coordinates": [float(lng_str), float(lat_str)]}
#     #     except (ValueError, IndexError):
#     #         return None

#     @staticmethod
#     def _build_geometry(centroid: str | None, area_covered: str | None) -> dict | None:
#         """The DB column (hazard_alerts.geom) requires MultiPolygon — SACHET only
#         gives a single centroid point + an area_covered (km^2) number, no polygon.
#         Both centroid and area_covered are real fields taken directly from the
#         live feed; this builds an approximate circular polygon around the
#         centroid sized to match the real reported area, rather than inventing
#         a boundary. If either real field is missing, no geometry is stored
#         (None) rather than guessing a default radius."""
#         if not centroid or not area_covered:
#             return None
#         try:
#             lng_str, lat_str = centroid.split(",")
#             lng, lat = float(lng_str), float(lat_str)
#             area_sqkm = float(area_covered)
#             if area_sqkm <= 0:
#                 return None
#         except (ValueError, IndexError):
#             return None

#         import math
#         radius_km = math.sqrt(area_sqkm / math.pi)
#         # ~111 km per degree latitude; longitude degrees shrink by cos(latitude)
#         radius_deg_lat = radius_km / 111.0
#         radius_deg_lng = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))

#         num_points = 24
#         ring = []
#         for i in range(num_points):
#             angle = 2 * math.pi * i / num_points
#             point_lng = lng + radius_deg_lng * math.cos(angle)
#             point_lat = lat + radius_deg_lat * math.sin(angle)
#             ring.append([point_lng, point_lat])
#         ring.append(ring[0])  # close the ring

#         return {"type": "MultiPolygon", "coordinates": [[ring]]}

#     @staticmethod
#     def _parse_ist_time(value: str | None) -> str | None:
#         """Real format observed: 'Wed Aug 12 16:40:00 IST 2026'."""
#         if not value:
#             return None
#         try:
#             cleaned = value.replace(" IST ", " ")  # strptime %Z is unreliable for IST
#             dt = datetime.strptime(cleaned, "%a %b %d %H:%M:%S %Y")
#             return dt.replace(tzinfo=_IST).astimezone(timezone.utc).isoformat()
#         except ValueError:
#             return None





"""
Module 3 — Data Ingestion : SACHET connector

CORRECTED 2026-08-12 against the REAL live response, captured directly from
browser DevTools Network tab on https://sachet.ndma.gov.in/CapFeed:
    POST https://sachet.ndma.gov.in/cap_public_website/FetchAllAlertDetails

This is NOT CAP-XML — it's SACHET's own flat JSON array. Every field name
below (identifier, severity, severity_color, disaster_type, centroid, etc.)
was copied verbatim from a real captured response (78 live alerts, 12 Aug
2026), not invented.

UPDATED 2026-08-13 — two more real fixes after live-testing against the DB:
1. Geometry: hazard_alerts.geom column requires MultiPolygon, but SACHET only
   gives a single centroid point. _build_geometry() now builds an approximate
   circular polygon from the real centroid + area_covered fields instead of
   sending a bare Point (which the DB rejected).
2. Event classification: normalizer.py's _EVENT_TYPE_MAP only matches exact
   strings like "cyclone warning" / "tsunami warning", but SACHET's real
   disaster_type field is free text ("Cyclonic Storm", "Tsunami Alert", etc).
   _classify_event_type() does keyword matching so genuine coastal hazards
   (cyclone/tsunami/storm surge/high wave/evacuation/closure) map correctly
   instead of silently falling through to OTHER. Non-coastal hazards (rain,
   thunderstorm, flood, lightning) correctly remain OTHER — there is no
   generic category for them in CanonicalAlertType, confirmed by reading the
   real canonical_schema.py.

UNCERTAIN / FLAGGED, not guessed silently:
- Request body: confirmed empty via live DevTools Payload tab inspection —
  no request body needed for FetchAllAlertDetails.
- Severity mapping (severity_color -> internal Severity enum): SACHET uses
  red/orange/yellow, which doesn't map 1:1 onto CAP's Extreme/Severe/
  Moderate/Minor. The mapping below is a reasonable guess, not an official
  SACHET spec — verify/adjust once compared against how disaster_type
  severity is actually treated in practice.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .base_connector import BaseConnector, ConnectorError
from .config import settings
from .schemas import RecordType, Severity, SourceSystem

_IST = timezone(timedelta(hours=5, minutes=30))

# FLAGGED — approximate mapping, not an official SACHET spec (see module docstring).
_COLOR_SEVERITY_MAP = {
    "red": Severity.SEVERE,
    "orange": Severity.MODERATE,
    "yellow": Severity.MINOR,
}

_HARD_OVERRIDE_DISASTER_TYPES = {
    "tsunami",
    "storm surge",
    "cyclone",
    "evacuation",
    "beach closure",
}


def _classify_event_type(disaster_type: str) -> str:
    """SACHET's disaster_type is free text (e.g. 'Cyclonic Storm', 'Tsunami
    Alert'), not the exact strings normalizer._EVENT_TYPE_MAP expects
    ('cyclone warning', 'tsunami warning'). This does keyword matching
    against the disaster_type text to produce the exact map key when a
    real coastal-hazard keyword is present, so genuine cyclone/tsunami/
    storm-surge/high-wave alerts get correctly flagged as hard_override
    instead of silently falling to OTHER. Non-coastal hazards (rain,
    thunderstorm, flood, lightning) correctly remain unmapped -> OTHER,
    since CanonicalAlertType has no generic category for them."""
    dt = disaster_type.lower()
    if "tsunami" in dt:
        return "tsunami warning"
    if "storm surge" in dt:
        return "storm surge warning"
    if "cyclon" in dt:  # matches "cyclone" and "cyclonic"
        return "cyclone warning"
    if "high wave" in dt or "high-wave" in dt:
        return "high wave warning"
    if "evacuat" in dt:
        return "evacuation order"
    if "coast guard" in dt:
        return "coast guard closure"
    if "beach closure" in dt or "beach closed" in dt:
        return "beach closure"
    return dt  # unmapped -> normalizer will correctly fall back to OTHER


class SachetConnector(BaseConnector):
    source = SourceSystem.SACHET

    def _fetch_raw(self, client: httpx.Client) -> Any:
        if not settings.sachet_cap_feed_url:
            raise ConnectorError("SACHET_CAP_FEED_URL not configured")
        resp = client.post(
            settings.sachet_cap_feed_url,
            json={},
            headers={"Authorization": f"Bearer {settings.sachet_api_key}"} if settings.sachet_api_key else {},
        )
        resp.raise_for_status()
        return resp.json()

    def _parse(self, raw_payload: Any) -> list[dict]:
        alerts = raw_payload if isinstance(raw_payload, list) else raw_payload.get("data", [])
        items: list[dict] = []

        for alert in alerts:
            identifier = alert.get("identifier")
            if identifier is None:
                continue

            disaster_type = (alert.get("disaster_type") or "").strip().lower()
            color = (alert.get("severity_color") or "").strip().lower()

            items.append({
                "source": SourceSystem.SACHET,
                "source_id": f"sachet:{identifier}",
                "type": RecordType.HAZARD_WARNING,
                "severity": _COLOR_SEVERITY_MAP.get(color, Severity.MODERATE),
                "geometry": self._build_geometry(alert.get("centroid"), alert.get("area_covered")),
                "start_time": self._parse_ist_time(alert.get("effective_start_time")),
                "end_time": self._parse_ist_time(alert.get("effective_end_time")),
                "raw_json": alert,
                "parsed_fields": {
                    "event_type": _classify_event_type(alert.get("disaster_type") or ""),
                    "disaster_type": alert.get("disaster_type"),
                    "severity_tag": alert.get("severity"),          # ALERT / WATCH / WARNING
                    "severity_level": alert.get("severity_level"),  # "Very Likely" / "Likely" / etc.
                    "area_description": alert.get("area_description"),
                    "warning_message": alert.get("warning_message"),
                    "language": alert.get("actual_lang"),
                    "alert_source": alert.get("alert_source"),
                    "sender_org_id": alert.get("sender_org_id"),
                    "area_covered_sqkm": alert.get("area_covered"),
                    "disseminated": alert.get("disseminated") == "true",
                    "hard_override_flag": any(t in disaster_type for t in _HARD_OVERRIDE_DISASTER_TYPES),
                },
                "source_confidence": 1.0,
            })
        return items

    @staticmethod
    def _build_geometry(centroid: str | None, area_covered: str | None) -> dict | None:
        """The DB column (hazard_alerts.geom) requires MultiPolygon — SACHET only
        gives a single centroid point + an area_covered (km^2) number, no polygon.
        Both centroid and area_covered are real fields taken directly from the
        live feed; this builds an approximate circular polygon around the
        centroid sized to match the real reported area, rather than inventing
        a boundary. If either real field is missing, no geometry is stored
        (None) rather than guessing a default radius."""
        if not centroid or not area_covered:
            return None
        try:
            lng_str, lat_str = centroid.split(",")
            lng, lat = float(lng_str), float(lat_str)
            area_sqkm = float(area_covered)
            if area_sqkm <= 0:
                return None
        except (ValueError, IndexError):
            return None

        radius_km = math.sqrt(area_sqkm / math.pi)
        # ~111 km per degree latitude; longitude degrees shrink by cos(latitude)
        radius_deg_lat = radius_km / 111.0
        radius_deg_lng = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))

        num_points = 24
        ring = []
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            point_lng = lng + radius_deg_lng * math.cos(angle)
            point_lat = lat + radius_deg_lat * math.sin(angle)
            ring.append([point_lng, point_lat])
        ring.append(ring[0])  # close the ring

        return {"type": "MultiPolygon", "coordinates": [[ring]]}

    @staticmethod
    def _parse_ist_time(value: str | None) -> str | None:
        """Real format observed: 'Wed Aug 12 16:40:00 IST 2026'."""
        if not value:
            return None
        try:
            cleaned = value.replace(" IST ", " ")  # strptime %Z is unreliable for IST
            dt = datetime.strptime(cleaned, "%a %b %d %H:%M:%S %Y")
            return dt.replace(tzinfo=_IST).astimezone(timezone.utc).isoformat()
        except ValueError:
            return None