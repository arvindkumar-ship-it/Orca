import { clearAuthSession, getAuthSession } from "./auth";
import { getBackendIdForHardcodedId, getCurrentBeachContext, getCurrentTripContext } from "../utils/beachIdMap";
import { apiFetch } from "../utils/apiClient";

function getDeviceId() {
  const key = "wavesafe.device_id";
  const existing = localStorage.getItem(key);
  if (existing) return existing;
  let id = null;
  try {
    id = typeof crypto?.randomUUID === "function" ? crypto.randomUUID() : null;
  } catch {}
  if (!id) {
    id = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = Math.random() * 16 | 0;
      const v = c === "x" ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }
  localStorage.setItem(key, id);
  return id;
}

function getBeachCoordinates(beach) {
  const directLat = Number(beach?.lat ?? beach?.latitude);
  const directLng = Number(beach?.lng ?? beach?.longitude);
  if (Number.isFinite(directLat) && Number.isFinite(directLng)) {
    return { lat: directLat, lng: directLng, accuracy_m: null, source: "last_known" };
  }
  const coordinates = beach?.geom?.coordinates;
  if (!Array.isArray(coordinates)) return null;
  let point = coordinates;
  while (Array.isArray(point) && point.length && Array.isArray(point[0])) point = point[0];
  if (!Array.isArray(point) || point.length < 2 || Array.isArray(point[0])) return null;
  const lng = Number(point[0]);
  const lat = Number(point[1]);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  return { lat, lng, accuracy_m: null, source: "last_known" };
}

function getLocation(beach) {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error("Location services are unavailable in this browser."));
    navigator.geolocation.getCurrentPosition(
      (position) => resolve({
        lat: position.coords.latitude,
        lng: position.coords.longitude,
        accuracy_m: position.coords.accuracy,
        source: "gps",
      }),
      () => {
        const fallback = getBeachCoordinates(beach);
        if (fallback) return resolve(fallback);
        reject(new Error("Location permission is required to send an SOS."));
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }
    );
  });
}

async function getDeviceState() {
  let battery_pct = null;
  try {
    if (typeof navigator.getBattery === "function") {
      const battery = await navigator.getBattery();
      battery_pct = Math.round(battery.level * 100);
    }
  } catch {}
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  return {
    battery_pct,
    signal_strength: connection?.effectiveType || null,
    offline: !navigator.onLine,
  };
}

function buildHazardContext(beach) {
  const flags = [];
  if (beach?.current_verdict === "caution") flags.push("beach_caution");
  if (beach?.current_verdict === "unsafe") flags.push("beach_unsafe");
  const alerts = Array.isArray(beach?.alerts) ? beach.alerts : [];
  alerts.forEach((alert) => {
    if (alert?.id) flags.push(`alert:${alert.id}`);
    else if (alert?.alert_type) flags.push(`alert:${alert.alert_type}`);
  });
  return {
    current_verdict: beach?.current_verdict || null,
    alert_flags: flags,
    eta_minutes: null,
  };
}

export async function triggerSOS({ beachId: requestedBeachId = null, activityType = null, triggerType = "manual", severity = "critical", incidentType = "general_emergency" } = {}) {
  const userId = getAuthSession()?.user_id;
  if (!userId) {
    clearAuthSession();
    window.location.assign("/signup");
    throw new Error("Your login session does not contain a user ID. Please sign in again.");
  }

  const beach = getCurrentBeachContext();
  const trip = getCurrentTripContext();
  const contextBeachId = requestedBeachId || beach?.id || null;
  const beachId = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(contextBeachId || ""))
    ? contextBeachId
    : (getBackendIdForHardcodedId(contextBeachId) || trip?.beach_id || null);

  if (!beachId) {
    throw new Error("Please select a beach before triggering SOS.");
  }

  const [location, deviceState] = await Promise.all([getLocation(beach), getDeviceState()]);

  return apiFetch("/sos", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      device_id: getDeviceId(),
      trigger_type: triggerType,
      incident_type: incidentType,
      severity,
      ...(beachId ? { beach_id: beachId } : {}),
      ...((activityType || trip?.activity_type) ? { activity_type: activityType || trip.activity_type } : {}),
      location,
      hazard_context: buildHazardContext(beach),
      device_state: deviceState,
      contacts: [],
      media: [],
      notes: null,
    }),
  });
}

export const getIncident = (incidentId) => apiFetch(`/incidents/${encodeURIComponent(incidentId)}`);
export const getIncidentStatus = (incidentId) => apiFetch(`/incidents/${encodeURIComponent(incidentId)}/status`);

export const attachIncidentMedia = (incidentId, payload) => apiFetch(`/incidents/${encodeURIComponent(incidentId)}/media`, {
  method: "POST",
  body: JSON.stringify(payload),
});

export const acknowledgeIncident = (incidentId, {
  target_type = "user",
  target_name = "Current user",
  ack_status = "received",
  external_ref = null,
} = {}) => apiFetch(`/incidents/${encodeURIComponent(incidentId)}/ack`, {
  method: "POST",
  body: JSON.stringify({ target_type, target_name, ack_status, external_ref }),
});

export const startEmergencyShare = (payload) => apiFetch("/emergency/share/start", {
  method: "POST",
  body: JSON.stringify(payload),
});
export const stopEmergencyShare = (shareSessionId) =>
  apiFetch(`/emergency/share/stop?share_session_id=${encodeURIComponent(shareSessionId)}`, { method: "POST" });
export const getEmergencyShare = (shareSessionId) =>
  apiFetch(`/emergency/share/${encodeURIComponent(shareSessionId)}`);
