import React from "react";
import ReactDOM from "react-dom/client";
import Landing from "./pages/Landing";
import SignUp from "./pages/SignUp";
import OTPVerification from "./pages/OTPVerification";
import ExploreMap from "./pages/ExploreMap/ExploreMap";
import Profile from "./pages/Profile/Profile";
import Beaches from "./pages/Beaches/Beaches";
import YourTrips from "./pages/YourTrips";
import TripPlanning from "./pages/TripPlanning";
import BeachDetails from "./pages/BeachDetails";
import SOS from "./pages/SOS/SOS";
import SOSRequest from "./pages/SOS/SOSRequest";
import TrackIncident from "./pages/SOS/TrackIncident";
import Chat from "./pages/Chat/Chat";
import "./styles/global.css";

function isAuthenticated() {
  return Boolean(localStorage.getItem("wavesafe.access_token"));
}

const path = window.location.pathname.toLowerCase();

let Page;

if (path === "/signup" || path === "/sign-up") {
  Page = SignUp;
} else if (path === "/otp" || path === "/verify-otp") {
  Page = OTPVerification;
} else if (path === "/explore-map" || path === "/map") {
  Page = isAuthenticated() ? ExploreMap : SignUp;
} else if (path === "/profile") {
  Page = isAuthenticated() ? Profile : SignUp;
} else if (path === "/beaches") {
  Page = isAuthenticated() ? Beaches : SignUp;
} else if (path === "/beach-details" || path === "/beach") {
  Page = isAuthenticated() ? BeachDetails : SignUp;
} else if (path === "/sos") {
  Page = isAuthenticated() ? SOS : SignUp;
} else if (path === "/sos-request") {
  Page = isAuthenticated() ? SOSRequest : SignUp;
} else if (path === "/track-incident") {
  Page = isAuthenticated() ? TrackIncident : SignUp;
} else if (path === "/your-trips") {
  Page = isAuthenticated() ? YourTrips : SignUp;
} else if (path === "/trip-planning" || path === "/trip-planner") {
  Page = isAuthenticated() ? TripPlanning : SignUp;
} else if (path === "/chat" || path === "/ask-orca") {
  // NEW — ORCA's conversational entry point (R1-R10). Auth-gated same as
  // every other data page (route_agent/geo_risk_agent calls need a user
  // context for safe_harbor_guidance/voyage_watches persistence).
  Page = isAuthenticated() ? Chat : SignUp;
} else {
  Page = isAuthenticated() ? Landing : SignUp;
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Page />
  </React.StrictMode>
);
