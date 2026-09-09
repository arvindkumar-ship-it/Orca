import { apiFetch } from "../utils/apiClient";

/** ORCA — services/route.js (NEW). Both endpoints are POST + potentially
 * rate-limited-per-user, so this uses apiFetch (bearer token attached) same
 * as chat.js, not the bare public-GET pattern fishingZones.js uses. */
export async function planRoute({ originLat, originLng, destLat, destLng, activityType = "fishing", windowStart, windowEnd }) {
  return apiFetch("/route/plan", {
    method: "POST",
    body: JSON.stringify({
      origin_lat: originLat, origin_lng: originLng, dest_lat: destLat, dest_lng: destLng,
      activity_type: activityType, window_start: windowStart, window_end: windowEnd,
    }),
  });
}

export async function getSafeHarborGuidance({ lat, lng, marineZoneId = null }) {
  return apiFetch("/safe-harbors/guidance", {
    method: "POST",
    body: JSON.stringify({ lat, lng, marine_zone_id: marineZoneId }),
  });
}
