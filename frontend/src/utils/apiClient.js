const BASE = "/v1";
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export async function apiFetch(path, options = {}) {
  const token = localStorage.getItem("wavesafe.access_token");
  const headers = {
    ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };
  const response = await fetch(`${API_BASE_URL}${BASE}${path}`, { ...options, headers });
  let data = null;
  try { data = await response.json(); } catch {}
  if (response.status === 401) {
    localStorage.removeItem("wavesafe.access_token");
    localStorage.removeItem("wavesafe.auth");
    throw new Error("Your session has expired. Please sign in again.");
  }
  if (!response.ok) {
    const message = data?.detail || data?.message || `Request failed with status ${response.status}`;
    throw new Error(Array.isArray(message)
      ? message.map((item) => item?.msg || JSON.stringify(item)).join(", ")
      : String(message));
  }
  if (response.status === 204) return null;
  return data;
}
