-- ORCA migration: zone-keyed forecast/risk tables (GENERALIZE of
-- beach_activity_profiles/beach_forecasts/beach_risk_scores) +
-- safe_harbor_guidance (GENERALIZE of safezone_guidance, closes the gap
-- flagged in PROGRESS.md #11).

CREATE TABLE zone_activity_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    marine_zone_id UUID NOT NULL REFERENCES marine_zones(id) ON DELETE CASCADE,
    activity_type TEXT NOT NULL,
    min_safe_wave_height NUMERIC(8,3),
    max_safe_current_speed NUMERIC(8,3),
    max_safe_wind_speed NUMERIC(8,3),
    max_safe_swell NUMERIC(8,3),
    water_quality_min NUMERIC(8,3),
    tide_sensitivity NUMERIC(8,3),
    risk_weights JSONB NOT NULL DEFAULT '{}'::jsonb,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (marine_zone_id, activity_type)
);

CREATE TABLE zone_forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    marine_zone_id UUID NOT NULL REFERENCES marine_zones(id) ON DELETE CASCADE,
    forecast_time TIMESTAMPTZ NOT NULL,
    wave_height NUMERIC(8,3),
    current_speed NUMERIC(8,3),
    wind_speed NUMERIC(8,3),
    swell_height NUMERIC(8,3),
    tide_state TEXT,
    rainfall NUMERIC(8,3),
    visibility NUMERIC(8,3),
    water_quality NUMERIC(8,3),
    source TEXT NOT NULL,
    raw_payload JSONB,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_zone_forecasts_zone_time ON zone_forecasts(marine_zone_id, forecast_time);

CREATE TABLE zone_risk_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    marine_zone_id UUID NOT NULL REFERENCES marine_zones(id) ON DELETE CASCADE,
    activity_type TEXT NOT NULL,
    forecast_time TIMESTAMPTZ NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    risk_score NUMERIC(8,5) NOT NULL,
    verdict TEXT NOT NULL,
    explanation JSONB NOT NULL DEFAULT '{}'::jsonb,
    hard_override_reason TEXT,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_zone_risk_scores_lookup ON zone_risk_scores(marine_zone_id, activity_type, forecast_time);

-- safe_harbor_guidance: GENERALIZE of safezone_guidance, backs
-- app/services/safe_harbor_service.py. crowd_risk/elevation_gain_m dropped,
-- operational_penalty added (see that file's module docstring for why).
CREATE TABLE safe_harbor_guidance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    incident_report_id UUID REFERENCES incident_reports(id) ON DELETE SET NULL,
    origin_geom GEOMETRY(POINT, 4326) NOT NULL,
    safe_harbor_id UUID NOT NULL REFERENCES safe_harbors(id),
    route_geom GEOMETRY(LINESTRING, 4326),
    distance_m NUMERIC(10,2),
    hazard_exposure NUMERIC(6,3),
    operational_penalty NUMERIC(6,3),
    route_score NUMERIC(8,5),
    eta_minutes NUMERIC(8,2),
    instruction_text TEXT,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    hazard_alert_ids UUID[] NOT NULL DEFAULT '{}',
    trigger_reason TEXT NOT NULL DEFAULT 'initial',
    superseded BOOLEAN NOT NULL DEFAULT false,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_safe_harbor_guidance_user ON safe_harbor_guidance(user_id) WHERE superseded = false;
CREATE INDEX idx_safe_harbor_guidance_incident ON safe_harbor_guidance(incident_report_id) WHERE superseded = false;
