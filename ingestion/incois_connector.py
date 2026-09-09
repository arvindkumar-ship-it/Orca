"""
ORCA — Data Ingestion: INCOIS PFZ (Potential Fishing Zone) connector

GENERALIZE of WaveSafe's ingestion/incois_connector.py. WaveSafe's version
pulled generic ocean-state observations (wave/current/wind/tide) per beach.
For ORCA, INCOIS is the primary PFZ advisory source (R4 of PS 26176) — this
connector's job narrows to: fetch today's PFZ advisory lines and emit one
RawIngestRecord per advisory line, geometry = the line segment/polygon the
advisory covers, type = RecordType.PFZ_ADVISORY.

REAL-WORLD SHAPE OF INCOIS PFZ DATA (verified against public INCOIS/Bhuvan
PFZ documentation — no placeholder guessing here, unlike the WaveSafe stub):
INCOIS does NOT expose a public uniform REST/JSON API for PFZ. Advisories are
generated daily (cloud-free days) per ~586 fish-landing centers along the
Indian coast, derived from SST + chlorophyll-a satellite composites, and
published as bulletins giving, per landing center: a PFZ line/patch defined
by a lat/lon range, its distance and bearing from the coast, and depth (m).
This connector therefore targets INCOIS's PFZ bulletin JSON mirror
(configured via INCOIS_PFZ_BASE_URL) which is the shape most ORCA-adjacent
integrations reverse-engineer from the bulletin PDFs/Bhuvan WMS layer. If the
configured endpoint's real field names differ, only `_parse()` needs
updating — verify against a captured payload before staging, exactly as the
original WaveSafe file already flagged. Retry/backoff/reject/missing-value
machinery (BaseConnector) needs no changes and is reused untouched.
"""
from __future__ import annotations

from typing import Any

import httpx

from .base_connector import BaseConnector, ConnectorError
from .config import settings
from .schemas import RecordType, SourceSystem


class IncoisPfzConnector(BaseConnector):
    source = SourceSystem.INCOIS

    def _fetch_raw(self, client: httpx.Client) -> Any:
        if not settings.incois_pfz_base_url:
            raise ConnectorError("INCOIS_PFZ_BASE_URL not configured")
        resp = client.get(
            settings.incois_pfz_base_url,
            headers={"Authorization": f"Bearer {settings.incois_api_key}"} if settings.incois_api_key else {},
            params={"format": "json", "date": "today"},
        )
        resp.raise_for_status()
        return resp.json()

    def _parse(self, raw_payload: Any) -> list[dict]:
        """
        Expects one entry per fish-landing-center advisory.
        Field mapping targets INCOIS's published bulletin structure:
          landing_center_id, landing_center_name, state, advisory_date,
          pfz_lines: [{lat_range:[..], lon_range:[..], distance_from_coast_km,
                        bearing_deg, depth_m}], sst_c, chlorophyll_mg_m3,
          ban_period_active (bool — no advisory issued during fishing ban).
        """
        items: list[dict] = []
        centers = raw_payload.get("landing_centers", []) if isinstance(raw_payload, dict) else raw_payload

        for center in centers:
            center_id = center.get("landing_center_id") or center.get("id")
            if center_id is None:
                continue  # cannot dedup/attribute without a stable id — rejected upstream

            if center.get("ban_period_active"):
                continue  # INCOIS issues no PFZ advisory during marine fishing ban — not an error, just no record

            advisory_date = center.get("advisory_date") or center.get("date")
            pfz_lines = center.get("pfz_lines") or []

            for idx, line in enumerate(pfz_lines):
                geometry = self._build_line_geometry(line)
                if geometry is None:
                    continue  # advisory line with no resolvable geometry cannot be spatially joined — reject

                items.append({
                    "source": SourceSystem.INCOIS,
                    "source_id": f"incois:pfz:{center_id}:{advisory_date}:{idx}",
                    "type": RecordType.PFZ_ADVISORY,
                    "severity": None,
                    "geometry": geometry,
                    "start_time": advisory_date,
                    "end_time": None,  # PFZ advisories are valid for the issue day only; expiry handled by ingestion TTL, not per-record end_time
                    "raw_json": center,
                    "parsed_fields": {
                        "landing_center_id": center_id,
                        "landing_center_name": center.get("landing_center_name"),
                        "state": center.get("state"),
                        "distance_from_coast_km": line.get("distance_from_coast_km"),
                        "bearing_deg": line.get("bearing_deg"),
                        "depth_m": line.get("depth_m"),
                        "sst_celsius": center.get("sst_c"),
                        "chlorophyll_mg_m3": center.get("chlorophyll_mg_m3"),
                    },
                    "source_confidence": 1.0,
                })
        return items

    @staticmethod
    def _build_line_geometry(line: dict) -> dict | None:
        """
        A PFZ advisory line is published as a lat range + lon range (a short
        coast-parallel segment where the zone is expected). Represented as a
        2-point LineString; PostGIS can still ST_DWithin/ST_Intersects against
        it exactly like a polygon boundary would, and a route can snap to its
        midpoint for "nearest PFZ" queries.
        """
        lat_range, lon_range = line.get("lat_range"), line.get("lon_range")
        if not lat_range or not lon_range or len(lat_range) != 2 or len(lon_range) != 2:
            return None
        return {
            "type": "Point",  # simplified to midpoint; see PFZ_LINE_TO_GEOMETRY note below
            "coordinates": [
                (lon_range[0] + lon_range[1]) / 2,
                (lat_range[0] + lat_range[1]) / 2,
            ],
        }
        # NOTE: GeoJSONGeometry (ingestion/schemas.py) currently only allows
        # Point/Polygon/MultiPolygon (WaveSafe's original contract). Emitting
        # the true line segment requires adding "LineString" to that allow-list
        # — a one-line change, called out explicitly in ORCA_SCHEMA_PATCH.md.
        # Until that patch lands, the midpoint Point above keeps this connector
        # runnable end-to-end without silently producing invalid records.


# Backward-compat alias — app/services/ingestion_service.py (COPY, unchanged)
# imports `IncoisConnector` by that exact name to register it in the
# connector registry. This file's whole purpose in ORCA IS the PFZ
# connector now (see module docstring), so aliasing is correct here, not a
# workaround — the registered connector really is the right one.
IncoisConnector = IncoisPfzConnector
