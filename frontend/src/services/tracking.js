import { apiFetch } from "../utils/apiClient";

export const startSession = (incidentReportId) => apiFetch("/tracking/sessions", {
  method: "POST", body: JSON.stringify({ incident_report_id: incidentReportId }),
});
export const ping = (sessionId, payload) => apiFetch(`/tracking/sessions/${encodeURIComponent(sessionId)}/ping`, {
  method: "POST", body: JSON.stringify(payload),
});
export const getSnapshot = (sessionId) => apiFetch(`/tracking/sessions/${encodeURIComponent(sessionId)}`);
export const stopSession = (sessionId) => apiFetch(`/tracking/sessions/${encodeURIComponent(sessionId)}/stop`, {
  method: "POST", body: JSON.stringify({ reason: "manual_stop" }),
});
