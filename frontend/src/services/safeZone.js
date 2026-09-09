import { apiFetch } from "../utils/apiClient";

export const computeGuidance = (payload) => apiFetch("/safezone/guidance", { method: "POST", body: JSON.stringify(payload) });
export const recompute = (guidanceId, payload) => apiFetch(`/safezone/guidance/${encodeURIComponent(guidanceId)}/recompute`, { method: "POST", body: JSON.stringify(payload) });
export const getActive = (incidentReportId) => {
  const q = incidentReportId ? `?incident_report_id=${encodeURIComponent(incidentReportId)}` : "";
  return apiFetch(`/safezone/guidance/active${q}`);
};
export const shareGuidance = (guidanceId) => apiFetch(`/safezone/guidance/${encodeURIComponent(guidanceId)}/share`, { method: "POST" });
