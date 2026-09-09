import { useMemo } from "react";
import { goToSOS, goToTrackIncident } from "../../utils/sosNavigation";
import "./SOSRequest.css";

export default function SOSRequest() {
  const { incidentId, trackingSessionId } = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return {
      incidentId: params.get("incident_id"),
      trackingSessionId: params.get("tracking_session_id"),
    };
  }, []);

  const handleTrack = () => {
    if (!incidentId) return;
    goToTrackIncident(incidentId, trackingSessionId);
  };

  return (
    <main className="sos-page sos-request-page">
      <nav className="sos-breadcrumb" aria-label="Breadcrumb">
        <a className="teal sos-home-link" href="/">Home</a>
        <span className="breadcrumb-separator" aria-hidden="true"> | </span>
        <a className="red sos-label breadcrumb-link" href="/sos">SOS</a>
        <span className="breadcrumb-separator" aria-hidden="true"> | </span>
        <span className="teal">SOS Request</span>
      </nav>

      <section className="sos-card" aria-live="polite">
        <div className="sos-title">SOS Request Sent</div>

        <div className="sos-orbit-wrapper">
          <div className="sos-orbit orbit-one" />
          <div className="sos-orbit orbit-two" />
          <div className="sos-core">
            <span>Sent</span>
          </div>
        </div>

        <button
          type="button"
          className="track-incident-button"
          onClick={handleTrack}
          disabled={!incidentId}
          title={!incidentId ? "Incident ID is required to track this SOS" : undefined}
        >
          Track Incident
        </button>

        {!incidentId && (
          <p className="sos-error" role="alert">
            Incident ID was not returned by the SOS response, so tracking cannot be opened yet.
          </p>
        )}
      </section>
    </main>
  );
}