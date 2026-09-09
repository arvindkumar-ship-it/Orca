import { apiFetch } from "../utils/apiClient";

/**
 * ORCA — services/chat.js (NEW). Uses apiFetch (not beaches.js's bare
 * `beachRequest`) because POST /v1/chat is an authenticated, mutating call
 * (it creates/updates a chat_sessions row) — apiFetch already attaches the
 * bearer token and handles 401 session-expiry, exactly what beachRequest's
 * public GET-only beach reads didn't need.
 */
export async function sendChatMessage(message, sessionId = null) {
  return apiFetch("/chat", {
    method: "POST",
    body: JSON.stringify({ message, session_id: sessionId }),
  });
}
