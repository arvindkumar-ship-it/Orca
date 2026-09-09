import { apiFetch } from "../utils/apiClient";
export const listNotifications = () => apiFetch("/notifications");
export const markRead = (notificationId) => apiFetch(`/notifications/${encodeURIComponent(notificationId)}/read`, { method: "POST" });
