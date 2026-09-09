-- ORCA migration: marine_zones, safe_harbors (GENERALIZE of beaches/safe_zones),
-- maritime_boundaries, mpa_zones (NEW).
-- spatial_index=False in the SQLAlchemy models — indexes created explicitly
-- here, matching WaveSafe's own 001_extensions_and_tables.sql pattern
-- (idx_<table>_geom naming), so GeoAlchemy2 never auto-creates a colliding index.

CREATE TABLE marine_zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    zone_type TEXT NOT NULL CHECK (zone_type IN ('fishing_zone', 'open_sea_sector', 'coastal_beach')),
    state TEXT NOT NULL,
    district TEXT,
    coast_region TEXT,
    geom GEOMETRY(POLYGON, 4326) NOT NULL,
    centroid GEOMETRY(POINT, 4326),
    depth_m NUMERIC(8,2),
    has_lifeguard BOOLEAN DEFAULT false,
    public_access BOOLEAN DEFAULT true,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_marine_zones_geom ON marine_zones USING gist(geom);
CREATE INDEX idx_marine_zones_centroid ON marine_zones USING gist(centroid);
CREATE INDEX idx_marine_zones_type ON marine_zones(zone_type);
CREATE INDEX idx_marine_zones_name ON marine_zones(name);

CREATE TABLE safe_harbors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    marine_zone_id UUID REFERENCES marine_zones(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    geom GEOMETRY(POLYGON, 4326) NOT NULL,
    elevation_m NUMERIC(8,2),
    berthing_capacity INTEGER,
    has_fuel BOOLEAN DEFAULT false,
    route_notes TEXT,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_safe_harbors_geom ON safe_harbors USING gist(geom);

CREATE TABLE maritime_boundaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    boundary_type TEXT NOT NULL CHECK (boundary_type IN ('IMBL', 'EEZ', 'territorial_waters')),
    neighboring_country TEXT,
    geom GEOMETRY(MULTILINESTRING, 4326) NOT NULL,
    source_authority TEXT,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_maritime_boundaries_geom ON maritime_boundaries USING gist(geom);
CREATE INDEX idx_maritime_boundaries_type ON maritime_boundaries(boundary_type);

CREATE TABLE mpa_zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    restriction_level TEXT NOT NULL CHECK (restriction_level IN ('no_entry', 'seasonal', 'advisory')),
    season_start_month SMALLINT CHECK (season_start_month BETWEEN 1 AND 12),
    season_end_month SMALLINT CHECK (season_end_month BETWEEN 1 AND 12),
    geom GEOMETRY(MULTIPOLYGON, 4326) NOT NULL,
    governing_body TEXT,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_mpa_zones_geom ON mpa_zones USING gist(geom);
CREATE INDEX idx_mpa_zones_restriction ON mpa_zones(restriction_level);

-- jurisdictions, hospitals, rescue_posts: COPY, no migration needed — already
-- created by WaveSafe's 001_extensions_and_tables.sql and reused unchanged.
