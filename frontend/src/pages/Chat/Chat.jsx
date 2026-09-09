import { useState, useRef, useEffect } from "react";
import "./Chat.css";
import { sendChatMessage } from "../../services/chat";
import MapView from "../../components/MapView";

/**
 * ORCA — pages/Chat/Chat.jsx (NEW)
 *
 * HONEST NOTE ON REUSE: the build spec asked for this page to be "cloned"
 * from BeachPublicPage.jsx/ExploreMap's shell. What IS reused: the
 * breadcrumb nav markup/class names (ExploreMap.jsx), and every visual
 * token (font, colors, spacing) from styles/global.css, applied via this
 * page's own Chat.css rather than inline styles — "frontend theme frozen"
 * per the build spec. What is NOT reused: BeachPublicPage.jsx's 390 lines
 * are beach-detail-page-specific (hero image, activity tabs, forecast
 * cards) and ExploreMap.jsx's "map" is a static Google Maps iframe embed
 * with no marker/overlay API — neither has any chat-shaped or
 * dynamic-marker-rendering component to actually clone. Cloning either
 * verbatim would be copying unrelated markup for the sake of following the
 * letter of the instruction, which is the "vague reuse" this project's own
 * rules (Section 0, non-negotiable constraints) explicitly forbid. Marker/
 * route rendering uses ../../components/MapView.jsx (Leaflet, NEW —
 * WaveSafe had no reusable dynamic map component to draw from either).
 */
export default function Chat() {
  const [messages, setMessages] = useState([]); // {role, text, explanation?, sources?, visuals?}
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function handleSend(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;
    setError("");
    setMessages((prev) => [...prev, { role: "user", text }]);
    setInput("");
    setSending(true);
    try {
      const res = await sendChatMessage(text, sessionId);
      setSessionId(res.session_id);
      setMessages((prev) => [...prev, {
        role: "assistant", text: res.answer, explanation: res.explanation,
        sources: res.sources, visuals: res.visuals, language: res.detected_language,
      }]);
    } catch (err) {
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <main className="chat-page">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <a href="/" className="breadcrumb-home" aria-label="Go back to Home">Home</a>
        <span className="breadcrumb-separator" aria-hidden="true">{"  |  "}</span>
        <a href="/chat" className="breadcrumb-current" aria-current="page" aria-label="Ask ORCA">Ask ORCA</a>
      </nav>

      <section className="chat-stage" aria-label="ORCA marine intelligence chat">
        <div className="chat-history" ref={scrollRef}>
          {messages.length === 0 && (
            <p className="chat-empty-hint">
              Ask about PFZ locations, sea safety, weather alerts, geofencing, or route planning — in any language.
            </p>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`chat-bubble chat-bubble-${m.role}`}>
              <p className="chat-bubble-text">{m.text}</p>
              {m.role === "assistant" && m.explanation?.length > 0 && (
                <details className="chat-explanation">
                  <summary>Why this answer</summary>
                  <ul>{m.explanation.map((line, j) => <li key={j}>{line}</li>)}</ul>
                </details>
              )}
              {m.role === "assistant" && m.sources?.length > 0 && (
                <p className="chat-sources">Sources: {m.sources.join(", ")}</p>
              )}
              {m.role === "assistant" && (m.visuals?.map_markers?.length > 0 || m.visuals?.route_polyline?.length > 0) && (
                <MapView markers={m.visuals.map_markers || []} routePolyline={m.visuals.route_polyline || []} />
              )}
            </div>
          ))}
        </div>

        {error && <p className="chat-error" role="alert">{error}</p>}

        <form className="chat-input-row" onSubmit={handleSend}>
          <input
            className="chat-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="e.g. Is it safe to venture into the sea tomorrow morning?"
            disabled={sending}
            aria-label="Message ORCA"
          />
          <button className="chat-send-btn" type="submit" disabled={sending || !input.trim()}>
            {sending ? "..." : "Send"}
          </button>
        </form>
      </section>
    </main>
  );
}
