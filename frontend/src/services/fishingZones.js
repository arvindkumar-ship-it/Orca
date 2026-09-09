const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

/** ORCA — services/fishingZones.js (NEW). Same request/error-handling shape
 * as services/beaches.js's beachRequest (GENERALIZE — zone endpoints are
 * public reads, same as beach reads were). No hardcoded-data fallback: that
 * existed in beaches.js only because a curated demo beach list already
 * existed (data/hardcodedBeaches.js) — ORCA has no equivalent seed dataset,
 * so this always calls the real API rather than silently faking one. */
async function zoneRequest(path) {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: "GET" });
  let data = null;
  try { data = await response.json(); } catch {}
  if (!response.ok) {
    const message = data?.detail || data?.message || `Request failed with status ${response.status}`;
    throw new Error(Array.isArray(message) ? message.map((i) => i.msg || JSON.stringify(i)).join(", ") : String(message));
  }
  return data;
}

export async function listZones({ state = "", zoneType = "", near = "", radiusM, activity = "" } = {}) {
  const params = new URLSearchParams();
  if (state) params.set("state", state);
  if (zoneType) params.set("zone_type", zoneType);
  if (near) params.set("near", near);
  if (radiusM) params.set("radius_m", String(radiusM));
  if (activity) params.set("activity", activity);
  const query = params.toString();
  return zoneRequest(`/v1/zones${query ? `?${query}` : ""}`);
}

export async function getZone(zoneId) {
  return zoneRequest(`/v1/zones/${encodeURIComponent(zoneId)}`);
}

export async function getZoneRisk(zoneId, activityType = "fishing") {
  const params = new URLSearchParams({ activity_type: activityType });
  return zoneRequest(`/v1/zones/${encodeURIComponent(zoneId)}/risk?${params.toString()}`);
}

export async function getZoneForecast(zoneId, activityType = "fishing", hours = 24) {
  const params = new URLSearchParams({ activity_type: activityType, hours: String(hours) });
  return zoneRequest(`/v1/zones/${encodeURIComponent(zoneId)}/forecast?${params.toString()}`);
}

export async function getNearestPfz(lat, lng) {
  return zoneRequest(`/v1/ocean/pfz?lat=${lat}&lng=${lng}`);
}

export async function getSstChlorophyllHotspots({ minLat, minLng, maxLat, maxLng, product = "chlorophyll" }) {
  const params = new URLSearchParams({ min_lat: minLat, min_lng: minLng, max_lat: maxLat, max_lng: maxLng, product });
  return zoneRequest(`/v1/ocean/hotspots?${params.toString()}`);
}

export async function getAlerts({ lat, lng, radiusM = 25000 } = {}) {
  if (lat === undefined || lng === undefined) throw new Error("Latitude and longitude are required to load alerts.");
  const params = new URLSearchParams({ lat: String(lat), lng: String(lng), radius_m: String(radiusM) });
  return zoneRequest(`/v1/alerts?${params.toString()}`);
}
