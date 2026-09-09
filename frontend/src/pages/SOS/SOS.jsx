import { useCallback, useState } from "react";
import { triggerSOS, getIncident, getIncidentStatus } from "../../services/sos";
import { startSession, ping } from "../../services/tracking";
import { getCurrentBeachContext, getCurrentTripContext, saveCurrentIncidentContext } from "../../utils/beachIdMap";
import "./SOS.css";

function getIncidentId(response) {
  return response?.incident_id ?? response?.incident?.incident_id ?? response?.data?.incident_id ?? null;
}

export default function SOS() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleTriggerSOS = useCallback(async () => {
    if (loading) return;

    setLoading(true);
    setError("");

    try {
      const beach = getCurrentBeachContext();
      const trip = getCurrentTripContext();
      const response = await triggerSOS({
        beachId: beach?.id || trip?.beach_id || null,
        activityType: trip?.activity_type || null,
        triggerType: "manual",
        incidentType: "general_emergency",
        severity: "critical",
      });
      const incidentId = getIncidentId(response);

      if (!incidentId) {
        throw new Error("SOS was triggered, but the response did not include an incident ID.");
      }

      const [incidentResult, statusResult] = await Promise.allSettled([
        getIncident(incidentId),
        getIncidentStatus(incidentId),
      ]);
      if (incidentResult.status === "rejected") {
        console.warn("Incident detail fetch failed:", incidentResult.reason);
      }
      const incidentStatus = statusResult.status === "fulfilled" ? statusResult.value : null;
      if (statusResult.status === "rejected") {
        console.warn("Incident status fetch failed:", statusResult.reason);
      }

      saveCurrentIncidentContext({
        incident_id: incidentId,
        beach_id: beach?.id || trip?.beach_id || null,
        trip_id: trip?.trip_id || null,
        status: incidentStatus || null,
        incident: incidentResult.status === "fulfilled" ? incidentResult.value : null,
        created_at: new Date().toISOString(),
      });

      let trackingSessionId = null;
      try {
        const tracking = await startSession(incidentId);
        trackingSessionId = tracking?.session_id || null;
        let position = null;
        try {
          position = await new Promise((resolve, reject) => {
            if (!navigator.geolocation) return reject(new Error("Geolocation unavailable"));
            navigator.geolocation.getCurrentPosition(resolve, reject, {
              enableHighAccuracy: true, timeout: 10000, maximumAge: 15000,
            });
          });
        } catch {
          const coordinates = beach?.geom?.coordinates;
          if (Array.isArray(coordinates) && coordinates.length >= 2) {
            const lng = Number(coordinates[0]);
            const lat = Number(coordinates[1]);
            if (Number.isFinite(lat) && Number.isFinite(lng)) {
              position = {
                coords: { lat, lng, accuracy: null, speed: null, heading: null },
                __source: "last_known",
              };
            }
          }
        }
        if (trackingSessionId && position?.coords) {
          await ping(trackingSessionId, {
            lat: position.coords.latitude ?? position.coords.lat,
            lng: position.coords.longitude ?? position.coords.lng,
            accuracy_m: position.coords.accuracy ?? null,
            speed_mps: position.coords.speed ?? null,
            heading: position.coords.heading ?? null,
            battery_pct: null,
            signal_strength: navigator.connection?.effectiveType || null,
            source: position.__source || "gps",
          });
        }
      } catch (trackingError) {
        // SOS remains valid even if tracking bootstrap fails; Track Incident can retry it.
        console.warn("Tracking bootstrap failed:", trackingError);
      }

      const params = new URLSearchParams({ incident_id: incidentId });
      if (trackingSessionId) params.set("tracking_session_id", trackingSessionId);
      window.location.assign(`/sos-request?${params.toString()}`);
    } catch (requestError) {
      setError(requestError.message || "Unable to trigger SOS. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [loading]);

  return (
    <main className="sos-page">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <a href="/" className="breadcrumb-home">Home</a>
        <span className="breadcrumb-separator" aria-hidden="true"> | </span>
        <a href="/sos" className="breadcrumb-sos breadcrumb-link" aria-current="page">SOS</a>
      </nav>

      <div className="sos-panel">
        <section className="sos-content" aria-labelledby="emergency-title">
          <h1 id="emergency-title">Emergency help needed?</h1>

          <button
            className="sos-button"
            type="button"
            aria-label="Activate SOS emergency assistance"
            onClick={handleTriggerSOS}
            disabled={loading}
          >
            <span>{loading ? "..." : "SOS"}</span>
          </button>

          <p className="sos-description">
            After pressing the SOS button we will <br />
            contact the nearest hospital , police stations <br />
            emergency gaurds to your current location
          </p>

          {error && <p className="sos-error" role="alert">{error}</p>}
        </section>
      </div>
    </main>
  );
}