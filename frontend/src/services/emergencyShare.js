import { apiFetch } from "../utils/apiClient";

export const startShare = (payload) => apiFetch("/emergency/share/start", { method: "POST", body: JSON.stringify(payload) });
export const stopShare = (shareSessionId) => apiFetch(`/emergency/share/stop?share_session_id=${encodeURIComponent(shareSessionId)}`, { method: "POST" });
export const getShare = (shareSessionId) => apiFetch(`/emergency/share/${encodeURIComponent(shareSessionId)}`);
