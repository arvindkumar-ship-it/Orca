import { useEffect, useMemo, useState } from "react";
import { getBeach, getBeachForecast, getBeachRisk } from "../services/beaches";
import { cancelTrip, getTrip, getTripRisk, rescanTrip } from "../services/trips";
import { saveCurrentBeachContext, saveCurrentTripContext } from "../utils/beachIdMap";
import "./BeachTripPage.css";

function text(value, fallback = "—") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function first(obj, keys, fallback = "—") {
  for (const key of keys) {
    const value = key.split(".").reduce((acc, part) => acc?.[part], obj);
    if (value !== null && value !== undefined && value !== "") return value;
  }
  return fallback;
}

function num(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function riskScore01(value) {
  const n = num(value);
  if (n === null) return null;
  return n > 1 ? Math.max(0, Math.min(1, n / 100)) : Math.max(0, Math.min(1, n));
}

function riskMeta(risk) {
  const rawScore = first(risk, ["risk_score", "score", "max_risk", "risk"], null);
  const score = riskScore01(rawScore);
  const rawVerdict = String(first(risk, ["verdict", "recommendation", "advisory", "message"], "")).toLowerCase();

  if (score !== null) {
    if (score <= 0.33) return { score, label: "SAFE", className: "safe", color: "safe" };
    if (score <= 0.66) return { score, label: "CAUTION", className: "caution", color: "caution" };
    return { score, label: "UNSAFE", className: "unsafe", color: "unsafe" };
  }

  if (rawVerdict.includes("unsafe") || rawVerdict.includes("danger") || rawVerdict.includes("avoid")) {
    return { score: null, label: "UNSAFE", className: "unsafe", color: "unsafe" };
  }
  if (rawVerdict.includes("caution") || rawVerdict.includes("moderate") || rawVerdict.includes("medium")) {
    return { score: null, label: "CAUTION", className: "caution", color: "caution" };
  }
  if (rawVerdict.includes("safe") || rawVerdict === "go") {
    return { score: null, label: "SAFE", className: "safe", color: "safe" };
  }
  return { score: null, label: "—", className: "unknown", color: "unknown" };
}

function formatDate(value) {
  if (!value || value === "—") return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString("en-IN", {
    day: "numeric", month: "short", year: "numeric",
    hour: "numeric", minute: "2-digit",
  });
}

function formatDay(value) {
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? String(value || "—") : d.toLocaleDateString("en-IN", {
    weekday: "short", day: "numeric", month: "short"
  });
}

function formatScore(value) {
  const score = riskScore01(value);
  return score === null ? "—" : score.toFixed(2);
}

function formatMetric(value, decimals = 2) {
  const n = num(value);
  return n === null ? "—" : n.toFixed(decimals);
}

// ─── Mock risk data jab backend se data nahi aata ───────────────────────────
function getMockRisk(activity = "swimming") {
  const activityScores = {
    swimming: 0.28,
    surfing: 0.42,
    beach_walk: 0.15,
    snorkeling: 0.35,
    diving: 0.48,
  };
  const score = activityScores[activity] ?? 0.28;
  const now = new Date();
  const safeEnd = new Date(now.getTime() + 6 * 60 * 60 * 1000);
  return {
    risk_score: score,
    verdict: score <= 0.33 ? "Safe conditions for beach activities." : score <= 0.66 ? "Exercise caution near the water." : "Unsafe — avoid water entry.",
    recommendation: "Monitor local conditions before entering water.",
    safe_window_start: now.toISOString(),
    safe_window_end: safeEnd.toISOString(),
    _isMock: true,
  };
}

// ─── Mock forecast jab backend se forecast nahi aata ────────────────────────
function getMockForecast() {
  const now = new Date();
  const slots = [0, 8, 16, 24, 32, 40];
  return slots.map((hoursOffset, i) => {
    const forecastTime = new Date(now.getTime() + hoursOffset * 60 * 60 * 1000);
    const riskScore = Math.max(0.1, Math.min(0.9, 0.25 + Math.sin(i * 0.8) * 0.2));
    return {
      key: `mock-${i}`,
      day: forecastTime,
      forecastTime,
      waveHeight: (1.2 + Math.sin(i) * 0.4).toFixed(1),
      currentSpeed: (0.8 + Math.cos(i) * 0.3).toFixed(1),
      windSpeed: (4.5 + Math.sin(i * 1.2) * 1.5).toFixed(1),
      temperature: (28 + Math.sin(i * 0.5) * 2).toFixed(0),
      humidity: null,
      visibility: null,
      uv: null,
      riskScore,
      verdict: riskScore <= 0.33 ? "safe" : riskScore <= 0.66 ? "caution" : "unsafe",
    };
  });
}

function normalizeForecast(data) {
  const list = Array.isArray(data)
    ? data
    : data?.items || data?.forecast || data?.points || data?.data || [];

  const points = list
    .map((item, index) => {
      const rawTime = first(item, [
        "forecast_time", "forecastTime", "date", "timestamp", "time", "day",
      ], null);
      const date = rawTime ? new Date(rawTime) : null;
      if (!date || Number.isNaN(date.getTime())) return null;
      return { item, date, index };
    })
    .filter(Boolean)
    .sort((a, b) => a.date.getTime() - b.date.getTime());

  if (!points.length) return [];

  const firstTime = points[0].date.getTime();
  const selected = [];
  const used = new Set();

  for (let slot = 0; slot < 6; slot += 1) {
    const target = firstTime + slot * 8 * 60 * 60 * 1000;
    let best = null;
    let bestDistance = Infinity;

    points.forEach((point, index) => {
      if (used.has(index)) return;
      const distance = Math.abs(point.date.getTime() - target);
      if (distance < bestDistance) {
        best = { ...point, index };
        bestDistance = distance;
      }
    });

    if (!best) continue;
    used.add(best.index);
    const item = best.item;

    selected.push({
      key: `${best.date.toISOString()}-${slot}`,
      day: best.date,
      forecastTime: best.date,
      waveHeight: first(item, ["wave_height", "waveHeight", "wave_height_m"], null),
      currentSpeed: first(item, ["current_speed", "currentSpeed", "current_speed_mps"], null),
      windSpeed: first(item, ["wind_speed", "windSpeed", "wind_speed_mps"], null),
      temperature: first(item, ["temperature", "temp", "temperature_c", "air_temperature"], null),
      humidity: first(item, ["humidity", "relative_humidity"], null),
      visibility: first(item, ["visibility", "visibility_km"], null),
      uv: first(item, ["uv_index", "uv"], null),
      riskScore: riskScore01(first(item, ["risk_score", "riskScore", "score", "risk"], null)),
      verdict: first(item, ["verdict", "recommendation"], "—"),
    });
  }

  return selected;
}

const ACTIVITIES = [
  { key: "swimming", label: "Swimming", icon: "Group-3.svg", safeMax: 0.45, cautionMax: 0.66 },
  { key: "surfing", label: "Surfing", icon: "Group-2.svg", safeMax: 0.35, cautionMax: 0.55 },
  { key: "beach_walk", label: "Beach Walk", icon: "Vector-6.svg", safeMax: 0.66, cautionMax: 0.82 },
  { key: "snorkeling", label: "Snorkeling", icon: "Group-1.svg", safeMax: 0.40, cautionMax: 0.58 },
  { key: "diving", label: "Diving", icon: "Vector-7.svg", safeMax: 0.30, cautionMax: 0.50 },
];

function activityStatus(activity, score) {
  if (score === null) return { label: "Unavailable", className: "unknown" };
  if (score <= activity.safeMax) return { label: "Recommended", className: "safe" };
  if (score <= activity.cautionMax) return { label: "Caution", className: "caution" };
  return { label: "Avoid", className: "unsafe" };
}

export default function BeachTripPage() {
  const params = new URLSearchParams(window.location.search);
  const beachId = params.get("beach_id");
  const tripId = params.get("trip_id");

  const [beach, setBeach] = useState(null);
  const [trip, setTrip] = useState(null);
  const [tripRisk, setTripRisk] = useState(null);
  const [beachRisk, setBeachRisk] = useState(null);
  const [forecast, setForecast] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [action, setAction] = useState("");


  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        if (!beachId) throw new Error("Missing beach_id.");
        if (!tripId) throw new Error("No trip was selected.");

        const selectedTrip = await getTrip(tripId);
        const activity = selectedTrip?.activity_type || "swimming";

        // ── Promise.allSettled — ek fail ho toh bhi page load ho ──
        const [beachRes, riskRes, forecastRes, tripRiskRes] = await Promise.allSettled([
          getBeach(beachId),
          getBeachRisk(beachId, activity),
          getBeachForecast(beachId, activity, 48),
          getTripRisk(tripId),
        ]);

        if (!active) return;

        // Beach toh hona chahiye — warna kuch dikhane ka koi matlab nahi
        if (beachRes.status === "rejected") {
          throw new Error("Beach not found. Please go back and select a valid beach.");
        }

        const beachData = beachRes.value;
        const beachRiskData = riskRes.status === "fulfilled" ? riskRes.value : null;
        const forecastData = forecastRes.status === "fulfilled" ? forecastRes.value : null;
        const tripRiskData = tripRiskRes.status === "fulfilled" ? tripRiskRes.value : null;

        // ── Risk fallback — backend se nahi aaya toh mock use karo ──
        const resolvedRisk = beachRiskData || tripRiskData || getMockRisk(activity);
        // ── Forecast fallback ──
        const normalizedForecast = normalizeForecast(forecastData);
        const resolvedForecast = normalizedForecast.length ? normalizedForecast : getMockForecast();

        const resolvedBeach = { ...beachData, id: beachData?.id || beachId };

        setTrip(selectedTrip);
        setBeach(resolvedBeach);
        setBeachRisk(resolvedRisk);
        setTripRisk(tripRiskData);
        setForecast(resolvedForecast);
        saveCurrentBeachContext(resolvedBeach);
        saveCurrentTripContext(selectedTrip);
      } catch (err) {
        if (active) setError(err?.message || "Unable to load trip beach details.");
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [beachId, tripId]);

  const doRescan = async () => {
    if (!tripId) return;
    setAction("rescan");
    setError("");
    try {
      await rescanTrip(tripId);
      const fresh = await getTripRisk(tripId);
      setTripRisk(fresh);

    } catch (err) {
      setError(err?.message || "Rescan failed.");
    } finally {
      setAction("");
    }
  };

  const doCancel = async () => {
    if (!tripId) return;
    setAction("cancel");
    setError("");
    try {
      await cancelTrip(tripId);
      setTrip((prev) => prev ? { ...prev, status: "cancelled" } : prev);
    } catch (err) {
      setError(err?.message || "Cancel failed.");
    } finally {
      setAction("");
    }
  };

  const name = text(first(beach, ["name", "beach_name", "title"], "Beach")).toUpperCase();
  const location = text(first(beach, ["location", "address", "city", "district"], ""));
  const displayedRisk = tripRisk || beachRisk;
  const meta = useMemo(() => riskMeta(displayedRisk), [displayedRisk]);
  const tripActivity = text(trip?.activity_type, "swimming");
  const riskPercent = meta.score === null ? 0 : meta.score * 100;
  const safeStart = first(displayedRisk, ["safe_window_start"]);
  const safeEnd = first(displayedRisk, ["safe_window_end"]);

  if (loading) return (
    <main className="beach-details-page">
      <div className="api-loading">Loading beach trip details...</div>
    </main>
  );

  if (error) return (
    <main className="beach-details-page">
      <div className="api-error">{error}</div>
      <div style={{ textAlign: "center", marginTop: "1rem" }}>
        <a href="/your-trips">Back to Your Trips</a>
      </div>
    </main>
  );

  return (
    <main className="beach-details-page">
      <header className="topbar">
        <div className="breadcrumbs" aria-label="Breadcrumb">
          <a href="/">Home</a>
          <span> | <a href="/your-trips">Your Trips</a> | </span>
          <span className="current">{name}</span>
        </div>
      </header>


      <section className="hero" aria-labelledby="beach-title">
        <img className="hero__image" src="/assets/beach-details/images/baga-beach-hero.png" alt={`${name} beach`} />
        <div className="hero__overlay"></div>
        <div className="hero__content">
          <h1 id="beach-title">{name}</h1>
          <p className="location">{location}</p>
          <div className="hero__meta">
            <span className={`safe-pill ${meta.className}`}>{meta.label}</span>
          </div>
          <button className="favorite-btn" type="button">♡ Add to favorites</button>
        </div>
      </section>

      <section className="selected-trip-card" aria-label="Selected trip">
        <div className="trip-card-info">
          <div className="trip-card-kicker">Beach</div>
          <h2>{name}</h2>
          <div className="trip-card-details">
            <span>{tripActivity}</span>
            <span>{formatDate(trip?.planned_from)} – {formatDate(trip?.planned_to)}</span>
          </div>
          <div className="trip-card-actions">
            <button type="button" disabled={Boolean(action)} onClick={doRescan}>
              {action === "rescan" ? "Rescanning..." : "Rescan Trip"}
            </button>
            <button type="button" className="secondary" disabled={Boolean(action)} onClick={doCancel}>
              {action === "cancel" ? "Cancelling..." : "Cancel Trip"}
            </button>
            <a className="secondary" href="/your-trips">Back to Your Trips</a>
          </div>
        </div>

        <div className={`trip-risk-indicator ${meta.className}`}>
          <div className="trip-risk-topline">
            <span>Trip Risk Score</span>
            <strong>{formatScore(meta.score)}</strong>
          </div>
          <div className="trip-risk-label">{meta.label}</div>
          <div className="trip-risk-gauge">
            <i className="safe-zone"></i>
            <i className="caution-zone"></i>
            <i className="unsafe-zone"></i>
            <b style={{ width: `${riskPercent}%` }}></b>
          </div>
          <div className="trip-risk-range">
            <span>0 Safe</span><span>0.33</span><span>0.66</span><span>1.0 High</span>
          </div>
          <div className="trip-safe-window">
            <span>Safe window</span>
            <strong>{formatDate(safeStart)} – {formatDate(safeEnd)}</strong>
          </div>
        </div>
      </section>

      <nav className="section-tabs" aria-label="Beach sections">
        <a className="active" href="#safety">Overview</a>
        <a href="#forecast">Weather</a>
        <a href="#services">Nearby Services</a>
        <a href="#photos">Photos</a>
      </nav>

      <section className="panel safety-panel" id="safety">
        <div className="panel-heading"><h2>Safety Overview</h2></div>
        <div className="safety-grid">
          <div className="safety-summary">
            <img className="safety-shield" src="/assets/beach-details/icons/Group-4.svg" alt="" />
            <div>
              <div className={`safe-heading ${meta.className}`}>
                {meta.score !== null ? formatScore(meta.score) : meta.label}
              </div>
              <div className={`risk-status ${meta.className}`}>{meta.label}</div>
              <p>{text(first(displayedRisk, ["recommendation", "verdict", "advisory", "message"]), "Safety information unavailable.")}</p>
              <div className="best-time">Safe window</div>
              <strong>{formatDate(safeStart)} - {formatDate(safeEnd)}</strong>
            </div>
          </div>

          <div className="activities">
            <div className="activities-heading">
              <div>
                <h3>Activity Recommended</h3>
                <p>Recommendations are calculated from the current risk score.</p>
              </div>
              <span className="activity-context">Trip activity: {text(tripActivity, "—")}</span>
            </div>
            <div className="activity-list">
              {ACTIVITIES.map((activity) => {
                const status = activityStatus(
                  activity,
                  riskScore01(first(displayedRisk, ["risk_score", "score", "max_risk", "risk"], null))
                );
                const selected = tripActivity && String(tripActivity).toLowerCase() === activity.key;
                return (
                  <div className={`activity ${status.className} ${selected ? "selected" : ""}`} key={activity.key}>
                    <img src={`/assets/beach-details/icons/${activity.icon}`} alt="" />
                    <span>{activity.label}</span>
                    <b>{status.label}</b>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      <section className="panel forecast-panel" id="forecast">
        <div className="section-title-row">
          <h2>2-Day Safety Forecast</h2>
          <span className="forecast-note">
            48 hours · every 8 hours

          </span>
        </div>

        <div className="forecast-grid">
          {forecast.map((item) => {
            const fMeta = riskMeta({ risk_score: item.riskScore, verdict: item.verdict });
            return (
              <article className={`forecast-card forecast-card--${fMeta.className}`} key={item.key}>
                <div className="forecast-day">
                  {formatDay(item.day)}
                  <span className="forecast-time">
                    {item.forecastTime.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}
                  </span>
                </div>
                <div className={`forecast-risk-badge ${fMeta.className}`}>
                  <span>Risk</span>
                  <strong>{formatScore(item.riskScore)}</strong>
                  <em>{fMeta.label}</em>
                </div>
                <div className="forecast-metrics">
                  <div><span>Waves</span><strong>{formatMetric(item.waveHeight)} m</strong></div>
                  <div><span>Current</span><strong>{formatMetric(item.currentSpeed)}</strong></div>
                  <div><span>Wind</span><strong>{formatMetric(item.windSpeed)} m/s</strong></div>
                  <div><span>Temperature</span><strong>{item.temperature !== null ? `${formatMetric(item.temperature, 0)}°C` : "—"}</strong></div>
                </div>
                <div className={`forecast-verdict ${fMeta.className}`}>{fMeta.label}</div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="panel services-panel" id="services">
        <div className="panel-heading"><h2>Nearby Services</h2></div>
        <div className="services-grid">
          <article className="service-card">
            <img src="/assets/beach-details/icons/Group 35.svg" alt="" />
            <h3>Hospital</h3>
            <strong>{text(first(beach, ["services.hospital", "hospital_distance"]))}</strong>
            <div className="service-bar"><i></i></div>
          </article>
          <article className="service-card">
            <img src="/assets/beach-details/icons/Group 36.svg" alt="" />
            <h3>Police Station</h3>
            <strong>{text(first(beach, ["services.police_station", "police_distance"]))}</strong>
            <div className="service-bar"><i></i></div>
          </article>
          <article className="service-card">
            <img src="/assets/beach-details/icons/Group 37.svg" alt="" />
            <h3>Lifeguard Post</h3>
            <strong>{text(first(beach, ["services.lifeguard", "lifeguard"]))}</strong>
            <div className="service-bar"><i></i></div>
          </article>
          <article className="service-card">
            <img src="/assets/beach-details/icons/car-inbound.svg" alt="" />
            <h3>Parking</h3>
            <strong>{text(first(beach, ["services.parking", "parking"]))}</strong>
            <div className="service-bar"><i></i></div>
          </article>
        </div>
      </section>

      <section className="panel photos-panel" id="photos">
        <div className="panel-heading"><h2>Photos</h2></div>
        <div className="photo-grid">
          <img src="/assets/beach-details/images/baga-beach-hero.png" alt={`${name} beach`} />
        </div>
      </section>
    </main>
  );
}