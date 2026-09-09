CREATE TABLE safezone_guidance (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  incident_report_id uuid REFERENCES incident_reports(id) ON DELETE CASCADE,
  trip_plan_id uuid REFERENCES trip_plans(id) ON DELETE SET NULL,
  origin_geom geometry(Point, 4326) NOT NULL,
  safe_zone_id uuid NOT NULL REFERENCES safe_zones(id),
  route_geom geometry(LineString, 4326) NOT NULL,
  distance_m numeric(10,2) NOT NULL,
  elevation_gain_m numeric(8,2),
  hazard_exposure numeric(6,3) NOT NULL DEFAULT 0,
  crowd_risk numeric(6,3) NOT NULL DEFAULT 0,
  route_score numeric(8,5) NOT NULL,
  eta_minutes numeric(6,2) NOT NULL,
  instruction_text text NOT NULL,
  warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
  hazard_alert_ids uuid[] NOT NULL DEFAULT '{}',
  trigger_reason text NOT NULL DEFAULT 'initial',
  superseded boolean NOT NULL DEFAULT false,
  computed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_safezone_guidance_user ON safezone_guidance(user_id);
CREATE INDEX idx_safezone_guidance_incident ON safezone_guidance(incident_report_id);
CREATE INDEX idx_safezone_guidance_trip ON safezone_guidance(trip_plan_id);
CREATE INDEX idx_safezone_guidance_safezone ON safezone_guidance(safe_zone_id);
CREATE INDEX idx_safezone_guidance_origin_geom ON safezone_guidance USING gist(origin_geom);
CREATE INDEX idx_safezone_guidance_route_geom ON safezone_guidance USING gist(route_geom);

CREATE TABLE emergency_share_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_report_id uuid NOT NULL REFERENCES incident_reports(id) ON DELETE CASCADE,
  share_live_location boolean NOT NULL DEFAULT true,
  share_route boolean NOT NULL DEFAULT true,
  status text NOT NULL DEFAULT 'active',
  created_at timestamptz NOT NULL DEFAULT now(),
  stopped_at timestamptz
);
CREATE INDEX idx_emergency_share_sessions_incident ON emergency_share_sessions(incident_report_id);

CREATE TABLE emergency_share_targets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  share_session_id uuid NOT NULL REFERENCES emergency_share_sessions(id) ON DELETE CASCADE,
  contact_id uuid NOT NULL REFERENCES emergency_contacts(id),
  status text NOT NULL DEFAULT 'sent',
  last_error text
);
CREATE INDEX idx_emergency_share_targets_session ON emergency_share_targets(share_session_id);