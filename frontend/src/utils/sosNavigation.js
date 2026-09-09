export function goToSOS() {
  window.location.assign("/sos");
}

export function goToTrackIncident(incidentId, trackingSessionId = null) {
  if (!incidentId) return;
  const params = new URLSearchParams({ incident_id: incidentId });
  if (trackingSessionId) params.set("tracking_session_id", trackingSessionId);
  window.location.assign(`/track-incident?${params.toString()}`);
}
