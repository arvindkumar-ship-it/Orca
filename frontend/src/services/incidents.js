import { apiFetch } from "../utils/apiClient";

export const getIncident = (incidentId) => apiFetch(`/incidents/${encodeURIComponent(incidentId)}`);
export const getIncidentStatus = (incidentId) => apiFetch(`/incidents/${encodeURIComponent(incidentId)}/status`);
export const attachMedia = (incidentId, payload) => apiFetch(`/incidents/${encodeURIComponent(incidentId)}/media`, {
  method: "POST", body: JSON.stringify(payload),
});
export const ackIncident = (incidentId, payload) => apiFetch(`/incidents/${encodeURIComponent(incidentId)}/ack`, {
  method: "POST", body: JSON.stringify(payload),
});
