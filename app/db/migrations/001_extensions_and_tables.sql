-- Module 2 — exact schema from spec, source of truth (apply before ORM use,
-- or use as the Alembic initial revision body).

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ===== Module 2A: Core master tables =====
CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  phone text UNIQUE,
  email text UNIQUE,
  name text,
  preferred_language text DEFAULT 'en',
  consent_location boolean DEFAULT false,
  consent_emergency_share boolean DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE user_devices (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  platform text NOT NULL,
  device_token text NOT NULL,
  push_enabled boolean DEFAULT true,
  sms_enabled boolean DEFAULT true,
  last_seen_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_user_devices_user_id ON user_devices(user_id);

CREATE TABLE emergency_contacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name text NOT NULL,
  phone text NOT NULL,
  relation text,
  priority int DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ===== Module 2B: Geospatial tables =====
CREATE TABLE beaches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  state text NOT NULL,
  district text,
  coast_region text,
  geom geometry(Polygon, 4326) NOT NULL,
  centroid geometry(Point, 4326),
  has_lifeguard boolean DEFAULT false,
  public_access boolean DEFAULT true,
  active boolean DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_beaches_geom ON beaches USING gist(geom);
CREATE INDEX idx_beaches_name ON beaches(name);

CREATE TABLE safe_zones (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  beach_id uuid REFERENCES beaches(id) ON DELETE SET NULL,
  name text NOT NULL,
  geom geometry(Polygon, 4326) NOT NULL,
  elevation_m numeric(8,2),
  route_notes text,
  active boolean DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_safe_zones_geom ON safe_zones USING gist(geom);

CREATE TABLE jurisdictions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  authority_type text NOT NULL,
  contact_phone text,
  contact_email text,
  service_area_geom geometry(MultiPolygon, 4326) NOT NULL,
  escalation_level int DEFAULT 1,
  active boolean DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_jurisdictions_geom ON jurisdictions USING gist(service_area_geom);

CREATE TABLE hospitals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  type text NOT NULL,
  geom geometry(Point, 4326) NOT NULL,
  contact_phone text,
  contact_email text,
  capabilities jsonb NOT NULL DEFAULT '{}'::jsonb,
  capacity_status text DEFAULT 'unknown',
  active boolean DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_hospitals_geom ON hospitals USING gist(geom);

CREATE TABLE rescue_posts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  post_type text NOT NULL,
  geom geometry(Point, 4326) NOT NULL,
  contact_phone text,
  active boolean DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_rescue_posts_geom ON rescue_posts USING gist(geom);

-- ===== Module 2C: Forecast & risk tables =====
CREATE TABLE beach_activity_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  beach_id uuid NOT NULL REFERENCES beaches(id) ON DELETE CASCADE,
  activity_type text NOT NULL,
  min_safe_wave_height numeric(8,3),
  max_safe_current_speed numeric(8,3),
  max_safe_wind_speed numeric(8,3),
  max_safe_swell numeric(8,3),
  water_quality_min numeric(8,3),
  tide_sensitivity numeric(8,3),
  risk_weights jsonb NOT NULL DEFAULT '{}'::jsonb,
  active boolean DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uniq_beach_activity ON beach_activity_profiles(beach_id, activity_type);

CREATE TABLE beach_forecasts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  beach_id uuid NOT NULL REFERENCES beaches(id) ON DELETE CASCADE,
  forecast_time timestamptz NOT NULL,
  wave_height numeric(8,3),
  current_speed numeric(8,3),
  wind_speed numeric(8,3),
  swell_height numeric(8,3),
  tide_state text,
  rainfall numeric(8,3),
  visibility numeric(8,3),
  water_quality numeric(8,3),
  source text NOT NULL,
  raw_payload jsonb,
  ingested_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_beach_forecasts_beach_time ON beach_forecasts(beach_id, forecast_time);

CREATE TABLE hazard_alerts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_system text NOT NULL,
  source_alert_id text,
  alert_type text NOT NULL,
  severity text NOT NULL,
  title text,
  description text,
  geom geometry(MultiPolygon, 4326),
  issued_at timestamptz NOT NULL,
  valid_from timestamptz,
  valid_to timestamptz,
  eta_minutes int,
  hard_override_flag boolean DEFAULT false,
  raw_payload jsonb,
  status text DEFAULT 'active',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_hazard_alerts_geom ON hazard_alerts USING gist(geom);
CREATE INDEX idx_hazard_alerts_validity ON hazard_alerts(valid_from, valid_to);

CREATE TABLE beach_risk_scores (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  beach_id uuid NOT NULL REFERENCES beaches(id) ON DELETE CASCADE,
  activity_type text NOT NULL,
  forecast_time timestamptz NOT NULL,
  computed_at timestamptz NOT NULL DEFAULT now(),
  risk_score numeric(8,5) NOT NULL,
  verdict text NOT NULL,
  explanation jsonb NOT NULL DEFAULT '{}'::jsonb,
  hard_override_reason text,
  version int NOT NULL DEFAULT 1
);
CREATE INDEX idx_risk_scores_lookup ON beach_risk_scores(beach_id, activity_type, forecast_time DESC);

CREATE TABLE trip_plans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  beach_id uuid NOT NULL REFERENCES beaches(id),
  activity_type text NOT NULL,
  planned_from timestamptz NOT NULL,
  planned_to timestamptz NOT NULL,
  status text NOT NULL DEFAULT 'active',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_trip_plans_user ON trip_plans(user_id);

CREATE TABLE trip_risk_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  trip_plan_id uuid NOT NULL REFERENCES trip_plans(id) ON DELETE CASCADE,
  computed_at timestamptz NOT NULL DEFAULT now(),
  min_risk numeric(8,5),
  max_risk numeric(8,5),
  recommendation text,
  safe_window_start timestamptz,
  safe_window_end timestamptz,
  explanation jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- ===== Module 2D: Incident, notification & audit tables =====
CREATE TABLE incident_reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  beach_id uuid REFERENCES beaches(id) ON DELETE SET NULL,
  incident_type text NOT NULL,
  severity text NOT NULL,
  lat numeric(10,7) NOT NULL,
  lng numeric(10,7) NOT NULL,
  geom geometry(Point, 4326) GENERATED ALWAYS AS (
    ST_SetSRID(ST_MakePoint(lng, lat), 4326)
  ) STORED,
  description text,
  media jsonb NOT NULL DEFAULT '[]'::jsonb,
  status text NOT NULL DEFAULT 'created',
  trigger_type text NOT NULL,
  battery_pct int,
  signal_strength text,
  current_hazard_context jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_incidents_geom ON incident_reports USING gist(geom);
CREATE INDEX idx_incidents_status ON incident_reports(status);

CREATE TABLE incident_routes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_report_id uuid NOT NULL REFERENCES incident_reports(id) ON DELETE CASCADE,
  target_type text NOT NULL,
  target_name text NOT NULL,
  target_id uuid,
  jurisdiction_id uuid REFERENCES jurisdictions(id),
  route_rank int NOT NULL,
  routed_at timestamptz NOT NULL DEFAULT now(),
  ack_status text NOT NULL DEFAULT 'sent',
  ack_time timestamptz,
  external_ref text,
  last_error text
);
CREATE INDEX idx_incident_routes_incident ON incident_routes(incident_report_id);

CREATE TABLE incident_status_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_report_id uuid NOT NULL REFERENCES incident_reports(id) ON DELETE CASCADE,
  from_status text,
  to_status text NOT NULL,
  reason text,
  changed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE notification_queue (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  incident_report_id uuid REFERENCES incident_reports(id) ON DELETE SET NULL,
  type text NOT NULL,
  priority text NOT NULL,
  title text NOT NULL,
  body text NOT NULL,
  channel text NOT NULL,
  status text NOT NULL DEFAULT 'queued',
  scheduled_for timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz,
  delivery_meta jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX idx_notification_queue_status ON notification_queue(status, scheduled_for);

CREATE TABLE audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type text NOT NULL,
  entity_type text NOT NULL,
  entity_id uuid,
  actor_type text NOT NULL,
  actor_id uuid,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_events_entity ON audit_events(entity_type, entity_id);

CREATE TABLE user_contacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name text NOT NULL,
  phone text NOT NULL,
  relation text,
  priority int DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE offline_sync_queue (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  entity_type text NOT NULL,
  entity_id uuid,
  action_type text NOT NULL,
  payload jsonb NOT NULL,
  status text DEFAULT 'pending',
  created_at timestamptz NOT NULL DEFAULT now()
);
