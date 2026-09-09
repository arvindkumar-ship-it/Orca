import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  acknowledgeIncident,
  getEmergencyShare,
  getIncident,
  getIncidentStatus,
  startEmergencyShare,
  stopEmergencyShare,
} from "../../services/sos";
import { getAlerts } from "../../services/beaches";
import { startSession, getSnapshot, stopSession, ping } from "../../services/tracking";
import { computeGuidance } from "../../services/safeZone";
import { getCurrentBeachContext, getCurrentIncidentContext, getCurrentTripContext, saveCurrentIncidentContext } from "../../utils/beachIdMap";
import { goToSOS } from "../../utils/sosNavigation";
import "./TrackIncident.css";

function unwrap(data) {
  return data?.item || data?.data || data?.incident || data;
}

function pick(data, keys, fallback = null) {
  for (const key of keys) if (data?.[key] !== undefined && data?.[key] !== null) return data[key];
  return fallback;
}

function getBatteryPct() {
  return typeof navigator.getBattery === "function"
    ? navigator.getBattery().then((battery) => Math.round(battery.level * 100)).catch(() => null)
    : Promise.resolve(null);
}

function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatCoords(location) {
  if (!location?.lat && location?.lat !== 0) return "Waiting for location";
  if (!location?.lng && location?.lng !== 0) return "Waiting for location";
  return `${Number(location.lat).toFixed(5)}, ${Number(location.lng).toFixed(5)}`;
}

function getLocationFromIncident(incident, beach) {
  const current = incident?.current_location;
  if (current?.lat !== undefined && current?.lng !== undefined) return current;
  const lat = Number(beach?.lat);
  const lng = Number(beach?.lng);
  return Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng, source: "last_known" } : null;
}

export default function TrackIncident() {
  const params = useMemo(() => new URLSearchParams(window.location.search), []);
  const incidentId = params.get("incident_id");
  const initialSessionId = params.get("tracking_session_id");
  const sessionIdRef = useRef(initialSessionId);
  const watchIdRef = useRef(null);
  const trackingStoppedRef = useRef(false);
  const lastGuidanceAtRef = useRef(0);
  const incidentRef = useRef(null);
  const statusRef = useRef(null);

  const [incident, setIncident] = useState(null);
  const [status, setStatus] = useState(null);
  const [tracking, setTracking] = useState(null);
  const [safeZone, setSafeZone] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [lastPingAt, setLastPingAt] = useState(null);
  const [liveLocation, setLiveLocation] = useState(null);
  const [share, setShare] = useState(null);
  const [loading, setLoading] = useState(Boolean(incidentId));
  const [actionLoading, setActionLoading] = useState(false);
  const [evacuated, setEvacuated] = useState(false);
  const [error, setError] = useState("");

  const contextBeach = useMemo(() => getCurrentBeachContext(), []);
  const contextTrip = useMemo(() => getCurrentTripContext(), []);
  const contextIncident = useMemo(() => getCurrentIncidentContext(), []);

  const loadLiveServices = useCallback(async (location, incidentData) => {
    if (!location || !incidentId || trackingStoppedRef.current) return;
    const now = Date.now();
    const shouldRecompute = now - lastGuidanceAtRef.current > 12000;
    const alertPromise = getAlerts({ lat: location.lat, lng: location.lng, radius_m: 50000 });
    const guidancePromise = shouldRecompute
      ? computeGuidance({
        lat: location.lat,
        lng: location.lng,
        beach_id: incidentData?.beach_id || contextBeach?.id || contextTrip?.beach_id || null,
        incident_report_id: incidentId,
        trip_plan_id: contextTrip?.trip_id || null,
      })
      : Promise.resolve(null);

    const [alertResult, guidanceResult] = await Promise.allSettled([alertPromise, guidancePromise]);
    if (alertResult.status === "fulfilled") setAlerts(Array.isArray(alertResult.value) ? alertResult.value : []);
    if (guidanceResult.status === "fulfilled" && guidanceResult.value) {
      lastGuidanceAtRef.current = now;
      setSafeZone(guidanceResult.value);
    }
  }, [contextBeach, contextTrip, incidentId]);

  const loadIncident = useCallback(async () => {
    if (!incidentId) {
      setError("Incident ID is missing. Return to SOS and trigger a new emergency request.");
      return;
    }
    setLoading(true);
    try {
      const [incidentResult, statusResult] = await Promise.allSettled([
        getIncident(incidentId),
        getIncidentStatus(incidentId),
      ]);

      let nextIncident = incidentRef.current;
      if (incidentResult.status === "fulfilled") {
        nextIncident = unwrap(incidentResult.value);
        incidentRef.current = nextIncident;
        setIncident(nextIncident);
        const location = getLocationFromIncident(nextIncident, contextBeach);
        if (location) {
          setLiveLocation((current) => current || location);
          loadLiveServices(location, nextIncident).catch(() => { });
        }
      } else if (!incidentRef.current) {
        setError(incidentResult.reason?.message || "Unable to load incident details.");
      }

      if (statusResult.status === "fulfilled") {
        const nextStatus = unwrap(statusResult.value);
        statusRef.current = nextStatus;
        setStatus(nextStatus);
      }
      else if (!incidentRef.current) setError(statusResult.reason?.message || "Unable to load incident status.");

      saveCurrentIncidentContext({
        ...(contextIncident || {}),
        incident_id: incidentId,
        beach_id: nextIncident?.beach_id || contextBeach?.id || contextTrip?.beach_id || null,
        trip_id: contextTrip?.trip_id || contextIncident?.trip_id || null,
        incident: nextIncident || null,
        status: statusResult.status === "fulfilled" ? unwrap(statusResult.value) : statusRef.current || null,
        tracking_session_id: sessionIdRef.current || null,
        updated_at: new Date().toISOString(),
      });
    } finally {
      setLoading(false);
    }
  }, [contextBeach, contextIncident, contextTrip, incidentId, loadLiveServices]);

  useEffect(() => {
    let active = true;
    loadIncident();
    const intervalId = window.setInterval(() => {
      if (active && !trackingStoppedRef.current && !document.hidden) loadIncident();
    }, 5000);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [loadIncident]);

  const sendPing = useCallback(async (sessionId, position) => {
    if (!sessionId || !position?.coords || !navigator.onLine || trackingStoppedRef.current) return;
    const batteryPct = await getBatteryPct();
    if (trackingStoppedRef.current) return;
    const lat = position.coords.latitude ?? position.coords.lat;
    const lng = position.coords.longitude ?? position.coords.lng;
    const location = { lat, lng, accuracy_m: position.coords.accuracy ?? null, source: position.__source || "gps" };
    setLiveLocation(location);
    await ping(sessionId, {
      lat,
      lng,
      accuracy_m: position.coords.accuracy ?? null,
      speed_mps: position.coords.speed ?? null,
      heading: position.coords.heading ?? null,
      battery_pct: batteryPct,
      signal_strength: navigator.connection?.effectiveType || null,
      source: position.__source || "gps",
    });
    setLastPingAt(new Date().toISOString());
    if (trackingStoppedRef.current) return;
    const snapshot = await getSnapshot(sessionId);
    setTracking(snapshot);
    loadLiveServices(location, incidentRef.current).catch(() => { });
  }, [loadLiveServices]);

  useEffect(() => {
    let cancelled = false;

    async function ensureTracking() {
      if (!incidentId || trackingStoppedRef.current) return;
      try {
        let sessionId = sessionIdRef.current;
        if (!sessionId) {
          const started = await startSession(incidentId);
          sessionId = started?.session_id || null;
          sessionIdRef.current = sessionId;
          if (started) setTracking(started);
        } else {
          const snapshot = await getSnapshot(sessionId);
          if (!cancelled) setTracking(snapshot);
        }
        if (!sessionId || cancelled) return;

        let initialPosition = null;
        if (navigator.geolocation && navigator.onLine) {
          try {
            initialPosition = await new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, {
              enableHighAccuracy: true, timeout: 10000, maximumAge: 15000,
            }));
          } catch { }
        }

        if (!initialPosition) {
          const fallback = getLocationFromIncident(incidentRef.current, contextBeach);
          if (fallback) initialPosition = { coords: { latitude: fallback.lat, longitude: fallback.lng, accuracy: null, speed: null, heading: null }, __source: "last_known" };
        }
        if (!cancelled && initialPosition) await sendPing(sessionId, initialPosition);

        if (navigator.geolocation && !cancelled && !trackingStoppedRef.current) {
          watchIdRef.current = navigator.geolocation.watchPosition(
            (position) => sendPing(sessionId, position).catch(() => { }),
            () => { },
            { enableHighAccuracy: true, maximumAge: 10000, timeout: 10000 }
          );
        }
      } catch (trackingError) {
        if (!cancelled) setError((current) => current || trackingError.message || "Unable to start live tracking.");
      }
    }

    ensureTracking();
    return () => {
      cancelled = true;
      if (watchIdRef.current !== null) {
        navigator.geolocation?.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
    };
  }, [incidentId, contextBeach, sendPing]);

  const stopTracking = useCallback(async () => {
    const sessionId = sessionIdRef.current;
    if (!sessionId || trackingStoppedRef.current) return true;

    trackingStoppedRef.current = true;
    if (watchIdRef.current !== null) {
      navigator.geolocation?.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }

    try {
      const response = await stopSession(sessionId);
      if (response) setTracking(response);
      return true;
    } catch (requestError) {
      trackingStoppedRef.current = false;
      setError(requestError.message || "Unable to stop live tracking.");
      return false;
    }
  }, []);

  const handleEvacuated = async () => {
    if (actionLoading || evacuated) return;
    setActionLoading(true);
    setError("");
    try {
      const stopped = await stopTracking();
      if (!stopped) return;
      setEvacuated(true);
      saveCurrentIncidentContext({
        ...(contextIncident || {}),
        incident_id: incidentId,
        beach_id: contextBeach?.id || contextTrip?.beach_id || null,
        trip_id: contextTrip?.trip_id || null,
        tracking_session_id: sessionIdRef.current || null,
        evacuated: true,
        evacuated_at: new Date().toISOString(),
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleAcknowledge = async () => {
    if (!incidentId || actionLoading) return;
    setActionLoading(true);
    try {
      setStatus(unwrap(await acknowledgeIncident(incidentId)));
      await loadIncident();
    } catch (requestError) {
      setError(requestError.message || "Unable to acknowledge the incident.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleStartShare = async () => {
    if (!incidentId || actionLoading) return;
    setActionLoading(true);
    try {
      const response = unwrap(await startEmergencyShare({ incident_id: incidentId, share_with: [], share_live_location: true, share_route: true }));
      setShare(response);
      if (response?.share_session_id) {
        try { setShare(unwrap(await getEmergencyShare(response.share_session_id))); } catch { }
      }
    } catch (requestError) {
      setError(requestError.message || "Unable to start emergency sharing.");
    } finally {
      setActionLoading(false);
    }
  };

  const shareSessionId = pick(share, ["share_session_id"]);
  const handleStopShare = async () => {
    if (!shareSessionId || actionLoading) return;
    setActionLoading(true);
    try { setShare(unwrap(await stopEmergencyShare(shareSessionId))); }
    catch (requestError) { setError(requestError.message || "Unable to stop emergency sharing."); }
    finally { setActionLoading(false); }
  };

  const routing = incident?.routing || {};
  const riskState = incident?.risk_state || {};
  const safeZoneName = safeZone?.safe_zone_name || incident?.safe_zone?.name || "No safe zone returned yet";
  const safeZoneEta = safeZone?.eta_minutes ?? tracking?.safe_zone_eta_minutes ?? incident?.safe_zone?.route_eta_min;
  const incidentState = pick(status, ["state", "status"], pick(incident, ["status"], "active"));
  const nextAction = pick(status, ["next_action"], "Emergency response in progress");
  const authority = routing?.primary_authority || "Awaiting authority response";
  const hospital = routing?.hospital || "Awaiting hospital routing";
  const responderEta = tracking?.responder_eta_minutes;
  const hospitalEta = tracking?.hospital_eta_minutes;
  const contactStatus = routing?.contact_status || "Pending";
  const currentCoords = liveLocation || incident?.current_location || contextBeach;

  return (
    <main className="track-page">
      <header className="track-header">
        <div>
          <nav className="track-breadcrumb" aria-label="Breadcrumb">
            <a href="/">Home</a><span>|</span><a href="/sos">SOS</a><span>|</span><strong>Track Incident</strong>
          </nav>
          <p className="track-eyebrow">LIVE EMERGENCY RESPONSE</p>
          <h1>We’re tracking your SOS</h1>
          <p className="track-subtitle">Your location, emergency response and safest route are being refreshed while this incident is active.</p>
        </div>
        <div className={`live-pill ${evacuated ? "stopped" : ""}`}><span />{evacuated ? "Tracking stopped" : "Live tracking"}</div>
      </header>

      {error && <div className="track-alert error" role="alert">{error}</div>}

      <section className="track-status-banner">
        <div className="status-icon">SOS</div>
        <div><strong>{String(incidentState).replaceAll("_", " ")}</strong><span>{nextAction}</span></div>
        <div className="status-meta"><span>Incident</span><b>{incidentId || "—"}</b></div>
        <div className="status-meta"><span>Last update</span><b>{formatTime(incident?.timestamps?.last_update || status?.at || lastPingAt)}</b></div>
      </section>

      <section className="track-grid">
        <article className="track-card live-location-card">
          <div className="card-heading"><div><span className="card-kicker">YOUR LOCATION</span><h2>Live position</h2></div><span className="online-dot">● Online</span></div>
          <div className="location-coordinates">{formatCoords(currentCoords)}</div>
          <div className="location-source">Source: {currentCoords?.source === "last_known" ? "Beach / last known position" : "GPS"}</div>
          <div className="mini-map"><div className="map-grid" /><div className="map-ring ring-a" /><div className="map-ring ring-b" /><div className="map-pin">●</div><span className="map-label">You</span></div>
          <div className="live-metrics"><div><span>Last ping</span><b>{formatTime(lastPingAt || tracking?.last_ping?.at || tracking?.last_ping?.timestamp)}</b></div><div><span>Accuracy</span><b>{liveLocation?.accuracy_m ? `${Math.round(liveLocation.accuracy_m)} m` : "—"}</b></div></div>
        </article>

        <article className="track-card safe-card">
          <div className="card-heading"><div><span className="card-kicker">SAFE ROUTE</span><h2>Nearest safe zone</h2></div><span className="safe-badge">SAFE</span></div>
          <div className="safe-zone-name">{safeZoneName}</div>
          <div className="safe-zone-stats"><div><span>Distance</span><b>{safeZone?.distance_m != null ? `${Math.round(safeZone.distance_m)} m` : "—"}</b></div><div><span>Walk ETA</span><b>{safeZoneEta != null ? `${safeZoneEta} min` : "—"}</b></div><div><span>Route score</span><b>{safeZone?.route_score != null ? `${Math.round(safeZone.route_score * 100)}%` : "—"}</b></div></div>
          <p className="safe-instruction">{safeZone?.instruction || "Safe-zone guidance will update as your location changes."}</p>
          {Array.isArray(safeZone?.warnings) && safeZone.warnings.length > 0 && <div className="warning-list">{safeZone.warnings.slice(0, 3).map((item, index) => <span key={`${item}-${index}`}>⚠ {item}</span>)}</div>}
        </article>

        <article className="track-card services-card">
          <div className="card-heading"><div><span className="card-kicker">EMERGENCY SERVICES</span><h2>Response around you</h2></div></div>
          <div className="service-row"><span className="service-icon">✚</span><div><b>Hospital</b><span>{hospital}</span></div><strong>{hospitalEta != null ? `${hospitalEta} min` : "Live"}</strong></div>
          <div className="service-row"><span className="service-icon">⌖</span><div><b>Authority</b><span>{authority}</span></div><strong>{contactStatus}</strong></div>
          <div className="service-row"><span className="service-icon">◉</span><div><b>Responder</b><span>{status?.acknowledged_by?.length ? "Acknowledged" : "Dispatch in progress"}</span></div><strong>{responderEta != null ? `${responderEta} min` : "Live"}</strong></div>
        </article>

        <article className="track-card alerts-card">
          <div className="card-heading"><div><span className="card-kicker">HAZARD ALERTS</span><h2>What’s around you</h2></div><span className="refresh-label">Auto refresh</span></div>
          {alerts.length ? <div className="alert-list">{alerts.slice(0, 4).map((alert) => <div className="alert-item" key={alert.id || `${alert.alert_type}-${alert.title}`}><span className={`severity-dot ${String(alert.severity || "").toLowerCase()}`} /><div><b>{alert.title || alert.alert_type || "Active hazard"}</b><span>{alert.severity || "Alert active"}</span></div></div>)}</div> : <div className="empty-state">No active hazard alerts returned for this location.</div>}
        </article>
      </section>

      <section className="track-card response-card">
        <div><span className="card-kicker">INCIDENT STATUS</span><h2>Response timeline</h2></div>
        <div className="timeline"><div className="timeline-step done"><i>✓</i><span>SOS received</span></div><div className={`timeline-step ${status?.acknowledged_by?.length ? "done" : "active"}`}><i>2</i><span>Authority acknowledgement</span></div><div className="timeline-step active"><i>3</i><span>Response in progress</span></div><div className={`timeline-step ${safeZone ? "done" : ""}`}><i>4</i><span>Safe-zone guidance</span></div></div>
        <div className="risk-line"><span>Beach risk: <b>{riskState?.beach_verdict || "Monitoring"}</b></span><span>Hazards: <b>{Array.isArray(riskState?.hazards) ? riskState.hazards.length : alerts.length}</b></span><span>Incident severity: <b>{incident?.severity || "Critical"}</b></span></div>
      </section>

      <section className="track-actions">
        <button type="button" className="secondary-action" onClick={() => goToSOS()}>Back to SOS</button>
        <button type="button" className="secondary-action" onClick={loadIncident} disabled={loading || actionLoading}>{loading ? "Refreshing…" : "Refresh status"}</button>
        <button type="button" className="secondary-action" onClick={shareSessionId ? handleStopShare : handleStartShare} disabled={actionLoading}>{shareSessionId ? "Stop emergency share" : "Share live location"}</button>
        <button type="button" className="secondary-action" onClick={handleAcknowledge} disabled={actionLoading}>Acknowledge</button>
        <button type="button" className="evacuated-action" onClick={handleEvacuated} disabled={actionLoading || evacuated}>{evacuated ? "✓ Evacuated — tracking stopped" : actionLoading ? "Stopping tracking…" : "I’m safe / Evacuated"}</button>
      </section>

      <p className="track-footer">Tracking session: {sessionIdRef.current || "starting…"} · {evacuated ? "Live GPS updates are stopped." : "Location updates continue while this incident is active."}</p>
    </main>
  );
}