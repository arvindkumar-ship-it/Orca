CREATE TABLE live_tracking_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_report_id uuid NOT NULL REFERENCES incident_reports(id) ON DELETE CASCADE,
  user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  status text NOT NULL DEFAULT 'awaiting_acknowledgment',
  tracking_mode text NOT NULL DEFAULT 'critical',
  started_at timestamptz NOT NULL DEFAULT now(),
  last_ping_at timestamptz,
  ended_at timestamptz,
  end_reason text
);
CREATE INDEX idx_live_tracking_sessions_incident ON live_tracking_sessions(incident_report_id);
CREATE INDEX idx_live_tracking_sessions_user ON live_tracking_sessions(user_id);

CREATE TABLE location_pings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES live_tracking_sessions(id) ON DELETE CASCADE,
  geom geometry(Point, 4326) NOT NULL,
  accuracy_m numeric(8,2),
  speed_mps numeric(8,3),
  heading numeric(6,2),
  battery_pct int,
  signal_strength text,
  source text NOT NULL DEFAULT 'gps',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_location_pings_session ON location_pings(session_id);
CREATE INDEX idx_location_pings_geom ON location_pings USING gist(geom);