import {
  findHardcodedBeach,
  findHardcodedBeachByState,
  getHardcodedBeaches,
} from "../data/hardcodedBeaches";
import { getBackendIdForHardcodedId, getHardcodedIdForBackendId, saveBeachIdMapping } from "../utils/beachIdMap";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const USE_BEACH_API = String(import.meta.env.VITE_USE_BEACH_API ?? "true").toLowerCase() === "true";

async function beachRequest(path) {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: "GET" });

  let data = null;
  try { data = await response.json(); } catch {}

  if (!response.ok) {
    const message = data?.detail || data?.message || `Request failed with status ${response.status}`;
    throw new Error(Array.isArray(message)
      ? message.map((item) => item.msg || JSON.stringify(item)).join(", ")
      : String(message));
  }
  return data;
}

export function isBeachApiEnabled() {
  return USE_BEACH_API;
}

export async function listBeaches({ state = "", activity = "", apiOnly = false } = {}) {
  if (!USE_BEACH_API && !apiOnly) return getHardcodedBeaches({ state, activity });

  const params = new URLSearchParams();
  if (state) params.set("state", state);
  if (activity) params.set("activity", activity);
  const query = params.toString();
  const data = await beachRequest(`/v1/beaches${query ? `?${query}` : ""}`);
  return data?.items || data || [];
}

export async function listBeachesFromApi({ state = "", activity = "" } = {}) {
  return listBeaches({ state, activity, apiOnly: true });
}

export async function resolveBackendBeachId(beach) {
  if (!beach) throw new Error("No beach was selected.");
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(beach.id || ""))) return beach.id;
  const mapped = getBackendIdForHardcodedId(beach.id);
  if (mapped) return mapped;
  const items = await listBeachesFromApi({ state: beach.state });
  const name = String(beach.name || "").trim().toLowerCase();
  const match = (Array.isArray(items) ? items : []).find((item) => String(item?.name || "").trim().toLowerCase() === name);
  const backendId = match?.id || match?.beach_id;
  if (!backendId) throw new Error(`Beach API did not return a backend UUID for ${beach.name}.`);
  saveBeachIdMapping(backendId, beach.id);
  return backendId;
}

export async function getBeach(beachId) {
  if (!USE_BEACH_API) {
    const mapped = getHardcodedIdForBackendId(beachId);
    return findHardcodedBeach(beachId) || (mapped ? findHardcodedBeach(mapped) : null) || getHardcodedBeaches()[0];
  }

  const data = await beachRequest(`/v1/beaches/${encodeURIComponent(beachId)}`);
  return data?.item || data;
}

export async function getBeachRisk(beachId, activity = "swimming") {
  if (!USE_BEACH_API) {
    const mapped = getHardcodedIdForBackendId(beachId);
    const beach = findHardcodedBeach(beachId) || (mapped ? findHardcodedBeach(mapped) : null) || getHardcodedBeaches()[0];
    const isCaution = beach.current_verdict === "caution";
    return {
      beach_id: beach.id,
      min_risk: isCaution ? "moderate" : "low",
      max_risk: isCaution ? "moderate" : "low",
      recommendation: isCaution
        ? "Exercise caution and follow lifeguard instructions."
        : "Conditions look suitable for normal beach activity.",
      safe_window_start: "2026-08-17T08:00:00+05:30",
      safe_window_end: "2026-08-17T18:00:00+05:30",
      explanation: {
        swimming: isCaution ? "Use caution" : "Recommended",
        surfing: isCaution ? "Use caution" : "Recommended",
        beach_walk: "Recommended",
        snorkeling: isCaution ? "Use caution" : "Recommended",
        diving: isCaution ? "Use caution" : "Check local guidance",
      },
    };
  }

  const params = new URLSearchParams({ activity });
  const data = await beachRequest(`/v1/beaches/${encodeURIComponent(beachId)}/risk?${params.toString()}`);
  return data?.item || data;
}

export async function getBeachForecast(beachId, activity = "swimming", hours = 24) {
  if (!USE_BEACH_API) {
    const mapped = getHardcodedIdForBackendId(beachId);
    const beach = findHardcodedBeach(beachId) || (mapped ? findHardcodedBeach(mapped) : null) || getHardcodedBeaches()[0];
    const caution = beach.current_verdict === "caution";
    return Array.from({ length: 7 }, (_, index) => ({
      day: index === 0 ? "Today" : `Day ${index + 1}`,
      high: `${28 + (index % 3)}°C`,
      low: `${24 + (index % 2)}°C`,
      icon: index % 3 === 0 ? "Group 31.svg" : "Group 31.svg",
      wave_height: caution ? "1.0 m" : "0.7 m",
      risk_score: caution ? 0.4 : 0.2,
    }));
  }

  const params = new URLSearchParams({ activity, hours: String(hours) });
  const data = await beachRequest(`/v1/beaches/${encodeURIComponent(beachId)}/forecast?${params.toString()}`);
  return data?.items || data?.forecast || data || [];
}

export function getBeachFromState(state) {
  return findHardcodedBeachByState(state);
}

export async function getAlerts({ lat, lng, radius_m = 50000 } = {}) {
  if (lat === undefined || lng === undefined) throw new Error("Latitude and longitude are required to load alerts.");
  const params = new URLSearchParams({ near: `${lat},${lng}`, radius_m: String(radius_m) });
  const data = await beachRequest(`/v1/alerts?${params.toString()}`);
  return data?.items || data || [];
}
