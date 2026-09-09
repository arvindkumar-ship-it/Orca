import { useCallback, useEffect, useState } from "react";
import { listTrips, cancelTrip } from "../services/trips";
import { getAlerts, getBeach } from "../services/beaches";
import "./YourTrips.css";
import { getBeachPoint, getHardcodedIdForBackendId, saveCurrentBeachContext, saveCurrentTripContext } from "../utils/beachIdMap";
import { findHardcodedBeach } from "../data/hardcodedBeaches";

function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatDateOnly(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function normalizeTrips(data) {
  const items = Array.isArray(data) ? data : data?.items;
  return Array.isArray(items) ? items : [];
}

function getBeachName(trip) {
  if (trip.beach_name || trip.beach?.name) return trip.beach_name || trip.beach?.name;
  const mapped = getHardcodedIdForBackendId(trip.beach_id);
  return (mapped && findHardcodedBeach(mapped)?.name) || trip.beach_id || "Beach";
}

function getStatus(trip) {
  const status = String(trip.status || "planned");
  return status.charAt(0).toUpperCase() + status.slice(1).replaceAll("_", " ");
}

export default function YourTrips() {
  const [trips, setTrips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [cancellingId, setCancellingId] = useState(null);
  const [activatingId, setActivatingId] = useState(null);
  const createdTripId = new URLSearchParams(window.location.search).get("created_trip_id");

  const loadTrips = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listTrips();
      const nextTrips = normalizeTrips(data);
      setTrips(nextTrips);
      if (createdTripId) {
        window.setTimeout(() => {
          document.getElementById(`trip-${createdTripId}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
        }, 0);
      }
    } catch (err) {
      setError(err.message || "Unable to load your trips.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadTrips(); }, [loadTrips]);

  const createFirstTrip = () => window.location.assign("/trip-planning");

  const openTripDetails = (trip) => {
    const beachId = trip?.beach_id || trip?.beach?.id;
    if (!beachId || !trip?.trip_id) {
      setError("This trip is missing its beach or trip ID.");
      return;
    }
    sessionStorage.setItem("wavesafe.current_trip_context", JSON.stringify(trip));
    window.location.assign(`/beach-details?beach_id=${encodeURIComponent(beachId)}&trip_id=${encodeURIComponent(trip.trip_id)}`);
  };

  const handleSelect = (e, tripId) => {
    e.stopPropagation();
    setSelectedId((prev) => (prev === tripId ? null : tripId));
  };

  const handleSetCurrentBeach = async (e, trip) => {
    e.stopPropagation();
    if (!trip?.trip_id || !trip?.beach_id || activatingId) return;

    setActivatingId(trip.trip_id);
    setError("");
    try {
      const beach = await getBeach(trip.beach_id);
      const point = getBeachPoint(beach);
      let alerts = [];
      if (point) {
        try {
          alerts = await getAlerts({ lat: point.lat, lng: point.lng });
        } catch (alertError) {
          console.warn("Unable to preload beach alerts:", alertError);
        }
      }
      const context = {
        ...trip,
        trip_id: trip.trip_id,
        beach_id: trip.beach_id,
        beach_name: trip.beach_name || beach?.name || "",
        geom: beach?.geom || null,
        lat: point?.lat ?? null,
        lng: point?.lng ?? null,
        alerts,
        current_for_sos: true,
        activated_at: new Date().toISOString(),
      };
      saveCurrentTripContext(context);
      saveCurrentBeachContext({
        ...beach,
        id: beach?.id || trip.beach_id,
        trip_id: trip.trip_id,
        activity_type: trip.activity_type || null,
        planned_from: trip.planned_from || null,
        planned_to: trip.planned_to || null,
        lat: point?.lat ?? null,
        lng: point?.lng ?? null,
        alerts,
      });
      setSelectedId(trip.trip_id);
    } catch (err) {
      setError(err.message || "Unable to set this trip as your current beach.");
    } finally {
      setActivatingId(null);
    }
  };

  const handleCancel = async (e, tripId) => {
    e.stopPropagation();
    setCancellingId(tripId);
    try {
      await cancelTrip(tripId);
      await loadTrips();
      setSelectedId(null);
    } catch (err) {
      setError(err.message || "Unable to cancel trip.");
    } finally {
      setCancellingId(null);
    }
  };

  return (
    <main className="your-trips-page">
      <div className="breadcrumb">
        <a href="/" className="home">Home</a>
        <span className="separator">|</span>
        <span className="current">Your Trips</span>
      </div>

      <h1>Your Trips</h1>

      <section className={`trips-card ${trips.length ? "has-trips" : ""}`}>
        {loading ? (
          <div className="no-trips">Loading your trips...</div>
        ) : error && !trips.length ? (
          <>
            <div className="no-trips">{error}</div>
            <button type="button" onClick={loadTrips}>Retry</button>
          </>
        ) : !trips.length ? (
          <>
            <img
              className="trip-icon"
              src="public/assets/Vector(1).svg"
              alt=""
              aria-hidden="true"
            />
            <div className="no-trips">No trips yet</div>
            <button type="button" onClick={createFirstTrip}>
              Create your trip
            </button>
          </>
        ) : (
          <>
            {error && <div className="message error">{error}</div>}

            <div className="trip-list" aria-label="Your trips">
              {trips.map((trip) => {
                const status = getStatus(trip);
                const isCancelled = status.toLowerCase() === "cancelled";
                const isSelected = selectedId === trip.trip_id;
                const isCancelling = cancellingId === trip.trip_id;

                return (
                  <article
                    className={`trip-list-item
                      ${createdTripId === trip.trip_id ? "is-created" : ""}
                      ${isSelected ? "is-selected" : ""}
                      ${isCancelled ? "is-cancelled" : ""}
                    `}
                    id={`trip-${trip.trip_id}`}
                    key={trip.trip_id}
                    onClick={(e) => handleSelect(e, trip.trip_id)}
                    onKeyDown={(e) => {
                      if (e.key === " ") { e.preventDefault(); handleSelect(e, trip.trip_id); }
                    }}
                    role="button"
                    tabIndex={0}
                    aria-label={`${getBeachName(trip)} trip`}
                    aria-pressed={isSelected}
                  >
                    <div className="trip-list-main">
                      {/* Beach name — single click navigates to detail page */}
                      <div
                        className="trip-list-title"
                        onClick={(e) => {
                          e.stopPropagation();
                          openTripDetails(trip);
                        }}
                        role="link"
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.stopPropagation();
                            openTripDetails(trip);
                          }
                        }}
                      >
                        {getBeachName(trip)}
                      </div>

                      <div className="trip-list-activity">
                        {trip.activity_type || "Activity"}
                      </div>

                      <div className="trip-list-dates">
                        {formatDateTime(trip.planned_from)} – {formatDateTime(trip.planned_to)}
                      </div>

                      {(trip.created_at || trip.booked_at) && (
                        <div className="trip-list-booked">
                          Booked on: {formatDateOnly(trip.created_at || trip.booked_at)}
                        </div>
                      )}
                    </div>

                    <div className="trip-list-actions">
                      <span className={`trip-status ${isCancelled ? "cancelled" : ""}`}>
                        {status}
                      </span>

                      {isSelected && !isCancelled && (
                        <>
                          <button
                            type="button"
                            className="trip-action cancel"
                            disabled={activatingId === trip.trip_id}
                            onClick={(e) => handleSetCurrentBeach(e, trip)}
                          >
                            {activatingId === trip.trip_id ? "Setting…" : "I'm at this beach"}
                          </button>
                          <button
                            type="button"
                            className="trip-action cancel"
                            disabled={isCancelling}
                            onClick={(e) => handleCancel(e, trip.trip_id)}
                          >
                            {isCancelling ? "Cancelling…" : "Cancel trip"}
                          </button>
                        </>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>

            <button
              type="button"
              className="trips-card-create create-another"
              onClick={createFirstTrip}
            >
              Create your trip
            </button>
          </>
        )}
      </section>
    </main>
  );
}