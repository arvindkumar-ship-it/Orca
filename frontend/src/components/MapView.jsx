import { MapContainer, TileLayer, Marker, Polyline, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";

/**
 * ORCA — components/MapView.jsx (NEW). Real interactive map (closes the
 * gap flagged in PROGRESS.md pass 6 — WaveSafe had no reusable dynamic
 * map component, only ExploreMap.jsx's static Google iframe embed).
 * Renders viz_agent.py's map_markers/route_polyline output shapes
 * directly — no reshaping needed on the frontend side.
 */
const DEFAULT_CENTER = [15.5, 73.8]; // Goa coast — reasonable default center for a coastal-India platform

export default function MapView({ markers = [], routePolyline = [], height = 320 }) {
  const points = markers.filter((m) => typeof m.lat === "number" && typeof m.lng === "number");
  const center = points[0] ? [points[0].lat, points[0].lng]
    : routePolyline[0] ? [routePolyline[0].lat, routePolyline[0].lng]
    : DEFAULT_CENTER;

  return (
    <div className="chat-map-container" style={{ height }}>
      <MapContainer center={center} zoom={points.length || routePolyline.length ? 9 : 6} scrollWheelZoom={false} style={{ height: "100%", width: "100%" }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {points.map((m, i) => (
          <Marker key={i} position={[m.lat, m.lng]}>
            <Popup>{m.label || m.kind}</Popup>
          </Marker>
        ))}
        {routePolyline.length > 1 && (
          <Polyline positions={routePolyline.map((p) => [p.lat, p.lng])} pathOptions={{ color: "#0D7385", weight: 4 }} />
        )}
      </MapContainer>
    </div>
  );
}
