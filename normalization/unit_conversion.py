"""ORCA — GENERALIZE of normalization/unit_conversion.py. Adds
fahrenheit_to_celsius (SST unit handling — mosdac_bhuvan_connector.py
already emits Celsius natively, but a future source might not) and a
documented no-op for chlorophyll (mg/m3 IS the internal unit already, no
conversion function needed — noted here so nobody wonders why one's
missing). Every existing function copied verbatim, unchanged."""
from __future__ import annotations
from typing import Optional


def knots_to_mps(knots: Optional[float]) -> Optional[float]:
    if knots is None:
        return None
    return round(knots * 0.514444, 3)


def kmh_to_mps(kmh: Optional[float]) -> Optional[float]:
    if kmh is None:
        return None
    return round(kmh / 3.6, 3)


def feet_to_meters(feet: Optional[float]) -> Optional[float]:
    if feet is None:
        return None
    return round(feet * 0.3048, 3)


def inches_to_mm(inches: Optional[float]) -> Optional[float]:
    if inches is None:
        return None
    return round(inches * 25.4, 3)


def miles_to_km(miles: Optional[float]) -> Optional[float]:
    if miles is None:
        return None
    return round(miles * 1.60934, 3)


def fahrenheit_to_celsius(fahrenheit: Optional[float]) -> Optional[float]:
    """NEW — SST unit handling. mosdac_bhuvan_connector.py's real catalog
    payload is documented as already Celsius, so this is defensive, not on
    the hot path — kept so a future SST source reporting °F doesn't need a
    new file, just a call to this."""
    if fahrenheit is None:
        return None
    return round((fahrenheit - 32) * 5.0 / 9.0, 3)


# NOTE: no chlorophyll_mg_m3 conversion function — mg/m3 (milligrams per
# cubic meter) IS this system's internal chlorophyll-a unit already
# (matches raster_products.unit / pfz_advisories.chlorophyll_mg_m3), so
# there is nothing to convert from for the one source (MOSDAC) currently
# ingested. Add one here if a future source reports a different scale.


def clamp_water_quality_index(raw_value: Optional[float], source_scale_max: float = 100.0) -> Optional[float]:
    if raw_value is None:
        return None
    normalized = (raw_value / source_scale_max) * 100.0
    return round(max(0.0, min(100.0, normalized)), 3)
