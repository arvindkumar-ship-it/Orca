import { apiFetch } from "../utils/apiClient";

export const getSyncBundle = ({ deviceId, beachIds = [], lastSyncedAt } = {}) => {
  const params = new URLSearchParams();
  if (beachIds.length) params.set("beach_ids", beachIds.join(","));
  if (lastSyncedAt) params.set("last_synced_at", lastSyncedAt);
  return apiFetch(`/sync/bundle${params.toString() ? `?${params}` : ""}`, {
    headers: { "X-Device-Id": deviceId || "wavesafe-web" },
  });
};

// Backend request-body schema is not specified in the master prompt.
// Keep the service transport generic rather than inventing a payload shape.
export const postOfflineSosQueue = (body) => apiFetch("/sync/sos-queue", {
  method: "POST",
  body: JSON.stringify(body),
});
