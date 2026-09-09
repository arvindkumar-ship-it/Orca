import { useEffect, useMemo, useState } from "react";
import { listBeaches, resolveBackendBeachId } from "../services/beaches";
import { createTrip } from "../services/trips";
import { saveCurrentTripContext } from "../utils/beachIdMap";
import { findHardcodedBeach } from "../data/hardcodedBeaches";
import "./TripPlanning.css";

const activities = [
  { value: "swimming", label: "Swimming" },
  { value: "surfing", label: "Surfing" },
  { value: "scuba_diving", label: "Scuba diving" },
  { value: "snorkeling", label: "Snorkeling" },
  { value: "beach_walking", label: "Beach walking" },
  { value: "boating", label: "Boating" },
];

const fallbackStates = [
  "Goa",
  "Kerala",
  "Karnataka",
  "Maharashtra",
  "Tamil Nadu",
];

function toBackendDateTime(date, endOfDay = false) {
  if (!date) return "";
  return `${date}T${endOfDay ? "23:59:59" : "00:00:00"}`;
}

function today() {
  return new Date().toISOString().split("T")[0];
}

export default function TripPlanning() {

  const [state, setState] = useState("");
  const [beaches, setBeaches] = useState([]);
  const [allBeaches, setAllBeaches] = useState([]);
  const [beachId, setBeachId] = useState("");
  const [activity, setActivity] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const [states, setStates] = useState(fallbackStates);
  const [loadingBeaches, setLoadingBeaches] = useState(false);
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("");

  useEffect(() => {
    let active = true;

    async function loadInitialBeaches() {
      try {
        const items = await listBeaches();
        if (!active || !Array.isArray(items) || !items.length) return;
        setAllBeaches(items);

        const uniqueStates = [...new Set(
          items.map((item) => item.state).filter(Boolean)
        )].sort();

        if (uniqueStates.length) setStates(uniqueStates);
      } catch {
        // keep fallback states
      }
    }

    loadInitialBeaches();
    return () => { active = false; };
  }, []);

  const beachOptions = useMemo(
    () => beaches
      .map((item) => ({ id: item.id, name: item.name }))
      .filter((item) => item.id && item.name),
    [beaches]
  );

  const handleStateChange = async (value) => {
    setState(value);
    setBeachId("");
    setMessage("");
    setMessageType("");

    if (!value) {
      setBeaches([]);
      return;
    }

    setLoadingBeaches(true);
    try {
      const normalize = (input) => String(input || "")
        .toLowerCase()
        .replace(/&/g, "and")
        .replace(/[^a-z0-9]/g, "");
      const target = normalize(value);
      const source = allBeaches.length ? allBeaches : await listBeaches();
      const items = (Array.isArray(source) ? source : []).filter(
        (item) => normalize(item?.state) === target
      );
      setBeaches(items);
      if (!items.length) {
        setMessageType("error");
        setMessage("No beaches were returned for this state.");
      }
    } catch (error) {
      setBeaches([]);
      setMessageType("error");
      setMessage(error.message || "Unable to load beaches.");
    } finally {
      setLoadingBeaches(false);
    }
  };

  const handleStartDateChange = (e) => {
    const value = e.target.value;
    setStartDate(value);
    if (endDate && endDate < value) setEndDate("");
    setMessage("");
  };

  const submit = async (event) => {
    event.preventDefault();
    setMessage("");
    setMessageType("");

    if (!state || !beachId || !activity || !startDate || !endDate) {
      setMessageType("error");
      setMessage("Please complete all fields.");
      return;
    }

    if (endDate < startDate) {
      setMessageType("error");
      setMessage("End date must be on or after the start date.");
      return;
    }

    setCreating(true);
    try {
      const selectedBeach =
        beaches.find((item) => String(item.id) === String(beachId)) ||
        findHardcodedBeach(beachId);
      const backendBeachId = await resolveBackendBeachId(selectedBeach);
      const result = await createTrip({
        beach_id: backendBeachId,
        activity_type: activity,
        planned_from: toBackendDateTime(startDate),
        planned_to: toBackendDateTime(endDate, true),
      });

      saveCurrentTripContext({
        trip_id: result?.trip_id || null,
        beach_id: backendBeachId,
        hardcoded_beach_id: selectedBeach?.id || null,
        beach_name: selectedBeach?.name || "",
        activity_type: activity,
      });

      setMessageType("success");
      setMessage("Trip created successfully.");

      window.setTimeout(() => {
        const createdTripId = result?.trip_id;
        window.location.assign(
          createdTripId
            ? `/your-trips?created_trip_id=${encodeURIComponent(createdTripId)}`
            : "/your-trips"
        );
      }, 350);
    } catch (error) {
      setMessageType("error");
      setMessage(error.message || "Unable to create trip.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <main className="trip-planning-page">
      <div className="breadcrumb">
        <a href="/" className="home">Home</a>
        <span className="separator">|</span>

        <a href="/your-trips" className="current">Your Trips</a>
        <span className="separator">|</span>

        <span className="current">Trip Planning</span>
      </div>

      <h1>Plan a safer coastal trip</h1>

      <section className="planning-card">
        <form onSubmit={submit}>
          <div className="field state-field">
            <label htmlFor="state">State</label>
            <select
              id="state"
              value={state}
              disabled={creating}
              onChange={(e) => handleStateChange(e.target.value)}
            >
              <option value="">Select a state</option>
              {states.map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
          </div>

          <div className="field beach-field">
            <label htmlFor="beach">Beach</label>
            <select
              id="beach"
              value={beachId}
              disabled={!state || loadingBeaches || creating}
              onChange={(e) => setBeachId(e.target.value)}
            >
              <option value="">
                {loadingBeaches ? "Loading beaches..." : "Select a beach"}
              </option>
              {beachOptions.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
          </div>

          <div className="field activity-field">
            <label htmlFor="activity">Activity</label>
            <select
              id="activity"
              value={activity}
              disabled={creating}
              onChange={(e) => {
                setActivity(e.target.value);
                setMessage("");
              }}
            >
              <option value="">Select an activity</option>
              {activities.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </div>

          <div className="field start-field">
            <label htmlFor="start-date">Start date</label>
            <input
              id="start-date"
              type="date"
              value={startDate}
              min={today()}
              disabled={creating}
              onChange={handleStartDateChange}
            />
          </div>

          <div className="field end-field">
            <label htmlFor="end-date">End date</label>
            <input
              id="end-date"
              type="date"
              value={endDate}
              min={startDate || today()}
              disabled={creating}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>

          {message && (
            <div className={`message ${messageType}`} role="status">
              {message}
            </div>
          )}

          <button
            className="create-trip"
            type="submit"
            disabled={creating || loadingBeaches}
          >
            {creating ? "Creating trip..." : "Create a trip"}
          </button>
        </form>
      </section>
    </main>
  );
}