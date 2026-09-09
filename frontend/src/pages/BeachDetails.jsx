import { useEffect, useMemo, useState } from "react";
import { getBeach, getBeachForecast, getBeachRisk } from "../services/beaches";
import { saveCurrentBeachContext } from "../utils/beachIdMap";
import "./BeachPublicPage.css";

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

    if (rawVerdict.includes("unsafe") || rawVerdict.includes("danger") || rawVerdict.includes("avoid"))
        return { score: null, label: "UNSAFE", className: "unsafe", color: "unsafe" };
    if (rawVerdict.includes("caution") || rawVerdict.includes("moderate") || rawVerdict.includes("medium"))
        return { score: null, label: "CAUTION", className: "caution", color: "caution" };
    if (rawVerdict.includes("safe") || rawVerdict === "go")
        return { score: null, label: "SAFE", className: "safe", color: "safe" };
    return { score: null, label: "—", className: "unknown", color: "unknown" };
}

function formatDate(value) {
    if (!value || value === "—") return "—";
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString("en-IN", {
        day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit",
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

// ── Mock fallbacks jab backend data nahi aata ────────────────────────────────
function getMockRisk(activity = "swimming") {
    const scores = { swimming: 0.28, surfing: 0.42, beach_walk: 0.15, snorkeling: 0.35, diving: 0.48 };
    const score = scores[activity] ?? 0.28;
    const now = new Date();
    return {
        risk_score: score,
        verdict: score <= 0.33 ? "Safe conditions for beach activities." : score <= 0.66 ? "Exercise caution near the water." : "Unsafe — avoid water entry.",
        recommendation: "Monitor local conditions before entering water.",
        safe_window_start: now.toISOString(),
        safe_window_end: new Date(now.getTime() + 6 * 3600000).toISOString(),
        _isMock: true,
    };
}

function getMockForecast() {
    const now = new Date();
    return [0, 8, 16, 24, 32, 40].map((h, i) => {
        const forecastTime = new Date(now.getTime() + h * 3600000);
        const riskScore = Math.max(0.1, Math.min(0.9, 0.25 + Math.sin(i * 0.8) * 0.2));
        return {
            key: `mock-${i}`,
            day: forecastTime,
            forecastTime,
            waveHeight: (1.2 + Math.sin(i) * 0.4).toFixed(1),
            currentSpeed: (0.8 + Math.cos(i) * 0.3).toFixed(1),
            windSpeed: (4.5 + Math.sin(i * 1.2) * 1.5).toFixed(1),
            temperature: (28 + Math.sin(i * 0.5) * 2).toFixed(0),
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
            const rawTime = first(item, ["forecast_time", "forecastTime", "date", "timestamp", "time", "day"], null);
            const date = rawTime ? new Date(rawTime) : null;
            if (!date || Number.isNaN(date.getTime())) return null;
            return { item, date, index };
        })
        .filter(Boolean)
        .sort((a, b) => a.date - b.date);

    if (!points.length) return [];

    const firstTime = points[0].date.getTime();
    const selected = [];
    const used = new Set();

    for (let slot = 0; slot < 6; slot += 1) {
        const target = firstTime + slot * 8 * 3600000;
        let best = null;
        let bestDistance = Infinity;

        points.forEach((point) => {
            if (used.has(point.index)) return;
            const distance = Math.abs(point.date.getTime() - target);
            if (distance < bestDistance) { best = point; bestDistance = distance; }
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

export default function BeachPublicPage() {
    const params = new URLSearchParams(window.location.search);
    const pathParts = window.location.pathname.split("/").filter(Boolean);
    const pathId = pathParts.length >= 2 ? decodeURIComponent(pathParts[pathParts.length - 1]) : "";
    const beachId =
        params.get("beach_id") ||
        params.get("id") ||
        (pathParts[pathParts.length - 2] === "beaches" || pathParts[pathParts.length - 2] === "beach" ? pathId : "");

    const [beach, setBeach] = useState(null);
    const [risk, setRisk] = useState(null);
    const [activityRisks, setActivityRisks] = useState({});
    const [forecast, setForecast] = useState([]);
    const [favorite, setFavorite] = useState(false);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");


    useEffect(() => {
        let active = true;
        async function load() {
            setLoading(true);
            setError("");
            try {
                if (!beachId) throw new Error("Missing beach_id.");

                // ── Promise.allSettled — ek fail ho toh bhi page load ho ──
                const [beachRes, riskRes, forecastRes, ...activityRiskResults] = await Promise.allSettled([
                    getBeach(beachId),
                    getBeachRisk(beachId, "swimming"),
                    getBeachForecast(beachId, "swimming", 48),
                    ...ACTIVITIES.map((a) => getBeachRisk(beachId, a.key)),
                ]);

                if (!active) return;

                if (beachRes.status === "rejected") throw new Error("Beach not found.");

                const beachData = beachRes.value;
                const riskData = riskRes.status === "fulfilled" ? riskRes.value : null;
                const forecastData = forecastRes.status === "fulfilled" ? forecastRes.value : null;

                const nextActivityRisks = {};
                ACTIVITIES.forEach((activity, index) => {
                    const res = activityRiskResults[index];
                    nextActivityRisks[activity.key] = res?.status === "fulfilled" ? res.value : getMockRisk(activity.key);
                });

                const normalizedForecast = normalizeForecast(forecastData);
                const resolved = { ...beachData, id: beachData?.id || beachId };
                setBeach(resolved);
                saveCurrentBeachContext(resolved);
                setRisk(riskData || getMockRisk("swimming"));
                setActivityRisks(nextActivityRisks);
                setForecast(normalizedForecast.length ? normalizedForecast : getMockForecast());
            } catch (err) {
                if (active) setError(err?.message || "Unable to load beach details.");
            } finally {
                if (active) setLoading(false);
            }
        }
        load();
        return () => { active = false; };
    }, [beachId]);

    const name = text(first(beach, ["name", "beach_name", "title"], "Beach")).toUpperCase();
    const location = text(first(beach, ["location", "address", "city", "district"], ""));

    const overviewRisk = useMemo(() => {
        const forecastScores = forecast.map((item) => riskScore01(item.riskScore)).filter((s) => s !== null);
        return forecastScores.length ? { risk_score: Math.max(...forecastScores) } : risk;
    }, [forecast, risk]);

    const meta = useMemo(() => riskMeta(overviewRisk), [overviewRisk]);
    const safeStart = first(risk, ["safe_window_start"]);
    const safeEnd = first(risk, ["safe_window_end"]);
    const overviewMessage = meta.label === "SAFE"
        ? "Conditions are currently within the safe forecast range."
        : meta.label === "CAUTION"
            ? "Conditions require caution based on the forecast."
            : meta.label === "UNSAFE"
                ? "Conditions are unsafe based on the forecast."
                : "Safety information unavailable.";

    if (loading) return <main className="beach-details-page"><div className="api-loading">Loading beach details...</div></main>;

    if (error) return (
        <main className="beach-details-page">
            <div className="api-error">{error}</div>
            <div style={{ textAlign: "center", marginTop: "1rem" }}><a href="/beaches">Back to Beaches</a></div>
        </main>
    );

    return (
        <main className="beach-details-page">
            <header className="topbar">
                <div className="breadcrumbs" aria-label="Breadcrumb">
                    <a href="/">Home</a><span> | <a href="/beaches">Beaches</a> | </span><span className="current">{name}</span>
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
                    <button className={`favorite-btn ${favorite ? "is-favorite" : ""}`} type="button" aria-pressed={favorite} onClick={() => setFavorite((v) => !v)}>
                        <span className="heart" aria-hidden="true">{favorite ? "♥" : "♡"}</span>{" "}
                        {favorite ? "Added to favorites" : "Add to favorites"}
                    </button>
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
                            <div className={`safe-heading ${meta.className}`}>{meta.score !== null ? formatScore(meta.score) : meta.label}</div>
                            <div className={`risk-status ${meta.className}`}>{meta.label}</div>
                            <p>{overviewMessage}</p>
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
                        </div>
                        <div className="activity-list">
                            {ACTIVITIES.map((activity) => {
                                const activityRisk = activityRisks[activity.key];
                                const activityScore = riskScore01(first(activityRisk, ["risk_score", "score", "max_risk", "risk"], null));
                                const status = activityStatus(activity, activityScore);
                                return (
                                    <div className={`activity ${status.className}`} key={activity.key}>
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
                        2 days · every 8 hours

                    </span>
                </div>
                <div className="forecast-grid">
                    {forecast.map((item) => {
                        const fMeta = riskMeta({ risk_score: item.riskScore, verdict: item.verdict });
                        return (
                            <article className={`forecast-card forecast-card--${fMeta.className}`} key={item.key}>
                                <div className="forecast-day">
                                    {formatDay(item.day)}
                                    <span className="forecast-time">{item.forecastTime.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}</span>
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
                    <article className="service-card"><img src="/assets/beach-details/icons/Group 35.svg" alt="" /><h3>Hospital</h3><strong>{text(first(beach, ["services.hospital", "hospital_distance"]))}</strong><div className="service-bar"><i></i></div></article>
                    <article className="service-card"><img src="/assets/beach-details/icons/Group 36.svg" alt="" /><h3>Police Station</h3><strong>{text(first(beach, ["services.police_station", "police_distance"]))}</strong><div className="service-bar"><i></i></div></article>
                    <article className="service-card"><img src="/assets/beach-details/icons/Group 37.svg" alt="" /><h3>Lifeguard Post</h3><strong>{text(first(beach, ["services.lifeguard", "lifeguard"]))}</strong><div className="service-bar"><i></i></div></article>
                    <article className="service-card"><img src="/assets/beach-details/icons/car-inbound.svg" alt="" /><h3>Parking</h3><strong>{text(first(beach, ["services.parking", "parking"]))}</strong><div className="service-bar"><i></i></div></article>
                </div>
            </section>

            <section className="panel photos-panel" id="photos">
                <div className="panel-heading"><h2>Photos</h2></div>
                <div className="photo-grid"><img src="/assets/beach-details/images/baga-beach-hero.png" alt={`${name} beach`} /></div>
            </section>
        </main>
    );
}