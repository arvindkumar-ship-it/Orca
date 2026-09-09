import { useEffect, useState } from "react";
import { listBeaches } from "../../services/beaches";
import "./Beaches.css";

const beaches = [
  { name: "GOA", asset: "Rectangle 55.png", className: "" },
  { name: "MAHARASHTRA", asset: "Rectangle 55-1.png", className: "long-name" },
  { name: "GUJARAT", asset: "Rectangle 55-2.png", className: "" },
  { name: "KARNATAKA", asset: "Rectangle 55-3.png", className: "long-name" },
  { name: "KERALA", asset: "Rectangle 55-4.png", className: "" },
  { name: "TAMIL NADU", asset: "Rectangle 55-5.png", className: "long-name" },
  { name: "ANDHRA PRADESH", asset: "Rectangle 55-6.png", className: "extra-long-name" },
  { name: "ODISHA", asset: "Rectangle 55-7.png", className: "" },
  { name: "WEST BENGAL", asset: "Rectangle 55-8.png", className: "long-name" },
  { name: "LAKSHADWEEP", asset: "Rectangle 55-9.png", className: "long-name" },
  { name: "PUDUCHERRY", asset: "Rectangle 55-10.png", className: "long-name" },
  { name: "DAMAN & DIU", asset: "Rectangle 55-11.png", className: "long-name" },
];

function normalizeState(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]/g, "");
}

function unwrapItems(data) {
  const items = Array.isArray(data) ? data : data?.items;
  return Array.isArray(items) ? items : [];
}

export default function Beaches() {
  const [allBeaches, setAllBeaches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingState, setLoadingState] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function loadAllBeaches() {
      setLoading(true);
      setError("");
      try {
        const data = await listBeaches();
        if (!active) return;
        const items = unwrapItems(data);
        if (!items.length) {
          setError("No beach data returned by the backend.");
          setAllBeaches([]);
          return;
        }
        setAllBeaches(items);
      } catch (err) {
        if (!active) return;
        setError(err.message || "Unable to load beaches.");
      } finally {
        if (active) setLoading(false);
      }
    }
    loadAllBeaches();
    return () => { active = false; };
  }, []);

  async function openState(stateCard) {
    setLoadingState(stateCard.name);
    setError("");
    try {
      // The backend state filter is case-sensitive in some deployments.
      // Fetch the documented public beach list once and match state locally.
      const targetState = normalizeState(stateCard.name);
      let matches = allBeaches.filter((item) => normalizeState(item?.state) === targetState);

      // The public list endpoint is the source of truth, but some backend
      // deployments may return an empty unfiltered list. On a user click,
      // make one documented state-filter request as a fallback.
      if (!matches.length) {
        const variants = [
          stateCard.name,
          stateCard.name.charAt(0) + stateCard.name.slice(1).toLowerCase(),
        ];
        for (const state of variants) {
          try {
            const data = await listBeaches({ state });
            const items = unwrapItems(data);
            matches = items.filter((item) => normalizeState(item?.state) === targetState);
            if (matches.length) break;
          } catch {
            // Try the next state spelling.
          }
        }
      }

      const firstBeach = matches[0];
      const beachId = firstBeach?.id || firstBeach?.beach_id;
      if (!beachId) throw new Error(`No beach data returned for ${stateCard.name}.`);
      window.location.assign(`/beach-details?beach_id=${encodeURIComponent(beachId)}`);
    } catch (err) {
      setError(err.message || "Unable to open beach details.");
    } finally {
      setLoadingState("");
    }
  }

  return (
    <main className="beaches-page">
      <div className="breadcrumb-bar">
        <div className="breadcrumb">
          <a href="/" className="breadcrumb-home breadcrumb-home-link">Home</a>
          <span className="breadcrumb-separator" aria-hidden="true">|</span>
          <a href="/beaches" className="breadcrumb-beaches breadcrumb-beach-link" aria-current="page">Beaches</a>
        </div>
      </div>

      <h1 className="page-title">Indian Beaches</h1>
      {loading && <div style={{ textAlign: "center", color: "#0D7385", padding: "10px" }}>Loading beaches...</div>}
      {error && <div style={{ textAlign: "center", color: "#9b1c1c", padding: "10px" }}>{error}</div>}

      <section className="beach-grid" aria-label="Indian beaches">
        {beaches.map((beach) => (
          <button
            key={beach.name}
            type="button"
            onClick={() => openState(beach)}
            disabled={loading || Boolean(loadingState)}
            className={`beach-card ${beach.className}`.trim()}
            aria-label={`Explore ${beach.name}`}
          >
            <img className="beach-image" src={`/assets/${beach.asset}`} alt={`${beach.name} beach`} />
            <div className="beach-name-panel"><div className="beach-name">{loadingState === beach.name ? "Loading..." : beach.name}</div></div>
          </button>
        ))}
      </section>
    </main>
  );
}