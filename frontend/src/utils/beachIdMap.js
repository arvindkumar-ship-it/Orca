const MAP_KEY = "wavesafe.beach_id_map";
const CURRENT_BEACH_KEY = "wavesafe.current_beach";
const CURRENT_TRIP_KEY = "wavesafe.current_trip_context";
const CURRENT_INCIDENT_KEY = "wavesafe.current_incident_context";
function readJson(key, fallback) { try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) : fallback; } catch { return fallback; } }
export function saveBeachIdMapping(backendId, hardcodedId) { if (!backendId || !hardcodedId) return; const map = readJson(MAP_KEY, {}); map[String(backendId)] = String(hardcodedId); localStorage.setItem(MAP_KEY, JSON.stringify(map)); }
export function getHardcodedIdForBackendId(backendId) { if (!backendId) return null; return readJson(MAP_KEY, {})[String(backendId)] || null; }
export function getBackendIdForHardcodedId(hardcodedId) { if (!hardcodedId) return null; const entry = Object.entries(readJson(MAP_KEY, {})).find(([, value]) => String(value) === String(hardcodedId)); return entry?.[0] || null; }
export function getBeachPoint(beach) {
  const directLat = Number(beach?.lat ?? beach?.latitude);
  const directLng = Number(beach?.lng ?? beach?.longitude);
  if (Number.isFinite(directLat) && Number.isFinite(directLng)) return { lat: directLat, lng: directLng };

  const coordinates = beach?.geom?.coordinates;
  if (!Array.isArray(coordinates)) return null;

  // GeoJSON Polygon: [[[lng, lat], ...]]; MultiPolygon: [[[[lng, lat], ...]]].
  let point = coordinates;
  while (Array.isArray(point) && point.length && Array.isArray(point[0])) point = point[0];
  if (Array.isArray(point) && point.length >= 2 && !Array.isArray(point[0])) {
    const lng = Number(point[0]);
    const lat = Number(point[1]);
    if (Number.isFinite(lat) && Number.isFinite(lng)) return { lat, lng };
  }
  return null;
}

export function saveCurrentBeachContext(beach) {
  if (!beach) return;
  const point = getBeachPoint(beach);
  const normalized = point ? { ...beach, lat: point.lat, lng: point.lng } : beach;
  sessionStorage.setItem(CURRENT_BEACH_KEY, JSON.stringify(normalized));
}
export function getCurrentBeachContext() { try { const raw = sessionStorage.getItem(CURRENT_BEACH_KEY); return raw ? JSON.parse(raw) : null; } catch { return null; } }
export function saveCurrentTripContext(context) { if (context) sessionStorage.setItem(CURRENT_TRIP_KEY, JSON.stringify(context)); }
export function getCurrentTripContext() { try { const raw = sessionStorage.getItem(CURRENT_TRIP_KEY); return raw ? JSON.parse(raw) : null; } catch { return null; } }
export function saveCurrentIncidentContext(context) { if (context) sessionStorage.setItem(CURRENT_INCIDENT_KEY, JSON.stringify(context)); }
export function getCurrentIncidentContext() { try { const raw = sessionStorage.getItem(CURRENT_INCIDENT_KEY); return raw ? JSON.parse(raw) : null; } catch { return null; } }
