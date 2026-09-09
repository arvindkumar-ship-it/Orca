import { clearAuthSession, getAuthSession } from "./auth";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

async function tripRequest(path, options = {}) {
  const token = localStorage.getItem("wavesafe.access_token");

  if (!token) {
    clearAuthSession();
    window.location.assign("/signup");
    throw new Error("Authentication required.");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers || {}),
    },
  });

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (response.status === 401) {
    clearAuthSession();
    window.location.assign("/signup");
    throw new Error("Your session has expired. Please sign in again.");
  }

  if (!response.ok) {
    const message =
      data?.detail ||
      data?.message ||
      `Request failed with status ${response.status}`;

    throw new Error(
      Array.isArray(message)
        ? message.map((item) => item.msg || JSON.stringify(item)).join(", ")
        : String(message)
    );
  }

  return data;
}

export async function listTrips() {
  return tripRequest("/v1/trips", { method: "GET" });
}

export async function createTrip({
  beach_id,
  activity_type,
  planned_from,
  planned_to,
}) {
  return tripRequest("/v1/trips", {
    method: "POST",
    body: JSON.stringify({
      beach_id,
      activity_type,
      planned_from,
      planned_to,
    }),
  });
}

export async function getTrip(tripId) {
  return tripRequest(`/v1/trips/${encodeURIComponent(tripId)}`, {
    method: "GET",
  });
}

export async function getTripRisk(tripId) {
  return tripRequest(`/v1/trips/${encodeURIComponent(tripId)}/risk`, {
    method: "GET",
  });
}

export async function rescanTrip(tripId) {
  return tripRequest(`/v1/trips/${encodeURIComponent(tripId)}/rescan`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function cancelTrip(tripId) {
  return tripRequest(`/v1/trips/${encodeURIComponent(tripId)}/cancel`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}
