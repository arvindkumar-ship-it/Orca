"""
ORCA — Data Ingestion: ISRO Bhuvan / MOSDAC connector

Pulls Sea Surface Temperature (SST) and chlorophyll-a raster/grid products
from MOSDAC (Meteorological & Oceanographic Satellite Data Archival Centre)
and emits RawIngestRecord items of type RecordType.SST_RASTER /
RecordType.CHLOROPHYLL_RASTER (added to ingestion/schemas.py — see
ORCA_SCHEMA_PATCH.md).

Design mirrors ingestion/incois_connector.py exactly: BaseConnector supplies
retry/backoff/reject/missing-value machinery unmodified. This file supplies
only _fetch_raw and _parse.

MOSDAC's product API returns per-tile grid metadata (bounding box + a
download URL for the actual raster, typically GeoTIFF/HDF5) rather than
per-point values inline. We do NOT download/parse the raster body here —
that is a separate heavy job (raster ingestion is out of scope for the
conversational-agent ingestion path and belongs in a dedicated batch worker).
This connector's contract is: one RawIngestRecord per grid tile, geometry =
the tile's footprint polygon, parsed_fields carries the tile's summary
statistics (mean/min/max SST or chlorophyll) when MOSDAC's metadata endpoint
provides them, plus the raster_url for downstream fetch-on-demand by the
Ocean Analytics agent.

NOTE ON REAL API SHAPE: MOSDAC/Bhuvan does not expose one uniform public
JSON API the way this file assumes (`tiles: [...]`) — access is normally via
their catalog/OGC (WMS/WCS) services and typically requires a registered
account. The field names below (`bbox`, `mean_value`, `product_time`) are
placeholders standing in for whatever the real catalog response contains.
Exactly like incois_connector.py's own documented caveat: swap `_parse()`'s
field mapping to match a real captured MOSDAC/Bhuvan catalog payload before
this goes to staging. Retry, dedup, storage, rejection are correct and
source-shape-independent already.
"""
from __future__ import annotations

from typing import Any

import httpx

from .base_connector import BaseConnector, ConnectorError
from .config import settings
from .schemas import RecordType, SourceSystem


class MosdacBhuvanConnector(BaseConnector):
    source = SourceSystem.MOSDAC_BHUVAN

    # which product this instance polls — set at construction time by the
    # scheduler so one connector class serves both SST and chlorophyll,
    # instead of duplicating fetch/parse logic per product.
    def __init__(self, config, product: str = "sst"):
        super().__init__(config)
        if product not in ("sst", "chlorophyll"):
            raise ValueError(f"unsupported MOSDAC product: {product}")
        self.product = product

    def _fetch_raw(self, client: httpx.Client) -> Any:
        base_url = settings.mosdac_base_url
        if not base_url:
            raise ConnectorError("MOSDAC_BASE_URL not configured")
        try:
            resp = client.get(
                f"{base_url}/catalog/{self.product}",
                headers={"Authorization": f"Bearer {settings.mosdac_api_key}"} if settings.mosdac_api_key else {},
                params={"format": "json", "region": "IND_EEZ"},
            )
            resp.raise_for_status()
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError):
            raise
        return resp.json()

    def _parse(self, raw_payload: Any) -> list[dict]:
        items: list[dict] = []
        tiles = raw_payload.get("tiles", []) if isinstance(raw_payload, dict) else raw_payload
        record_type = RecordType.SST_RASTER if self.product == "sst" else RecordType.CHLOROPHYLL_RASTER

        for tile in tiles:
            tile_id = tile.get("tile_id") or tile.get("id")
            product_time = tile.get("product_time") or tile.get("acquisition_time")
            if tile_id is None:
                continue  # cannot dedup/attribute without a stable id — rejected upstream

            geometry = self._build_polygon_geometry(tile.get("bbox"))
            if geometry is None:
                continue  # a raster tile with no known footprint is useless to spatial joins

            items.append({
                "source": SourceSystem.MOSDAC_BHUVAN,
                "source_id": f"mosdac:{self.product}:{tile_id}:{product_time}",
                "type": record_type,
                "severity": None,
                "geometry": geometry,
                "start_time": product_time,
                "end_time": None,
                "raw_json": tile,
                "parsed_fields": {
                    "tile_id": tile_id,
                    "product": self.product,
                    "mean_value": tile.get("mean_value"),
                    "min_value": tile.get("min_value"),
                    "max_value": tile.get("max_value"),
                    "unit": "celsius" if self.product == "sst" else "mg_per_m3",
                    "raster_url": tile.get("download_url"),
                    "cloud_cover_pct": tile.get("cloud_cover_pct"),
                },
                "source_confidence": tile.get("quality_flag_ok", True) and 1.0 or 0.4,
            })
        return items

    @staticmethod
    def _build_polygon_geometry(bbox: Any) -> dict | None:
        """bbox expected as [min_lng, min_lat, max_lng, max_lat]."""
        if not bbox or len(bbox) != 4:
            return None
        min_lng, min_lat, max_lng, max_lat = bbox
        ring = [
            [min_lng, min_lat], [max_lng, min_lat],
            [max_lng, max_lat], [min_lng, max_lat],
            [min_lng, min_lat],
        ]
        return {"type": "Polygon", "coordinates": [ring]}
