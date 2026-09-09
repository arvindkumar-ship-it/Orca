-- ORCA migration: pfz_advisories + raster_products (backing tables for
-- app/models/ocean_products.py — see that file's header for why these
-- didn't already exist in WaveSafe's schema).

CREATE TABLE pfz_advisories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    landing_center_id TEXT NOT NULL,
    landing_center_name TEXT,
    state TEXT,
    advisory_date TIMESTAMPTZ NOT NULL,
    geom GEOMETRY(POINT, 4326) NOT NULL,
    distance_from_coast_km NUMERIC(8,2),
    bearing_deg NUMERIC(6,2),
    depth_m NUMERIC(8,2),
    sst_celsius NUMERIC(6,2),
    chlorophyll_mg_m3 NUMERIC(8,3),
    source_confidence NUMERIC(4,3) DEFAULT 1.0,
    raw_payload JSONB,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pfz_advisories_geom ON pfz_advisories USING gist(geom);
CREATE INDEX idx_pfz_advisories_date ON pfz_advisories(advisory_date);
CREATE INDEX idx_pfz_advisories_state ON pfz_advisories(state);

CREATE TABLE raster_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product TEXT NOT NULL CHECK (product IN ('sst', 'chlorophyll')),
    tile_id TEXT NOT NULL,
    product_time TIMESTAMPTZ NOT NULL,
    footprint GEOMETRY(POLYGON, 4326) NOT NULL,
    mean_value NUMERIC(10,4),
    min_value NUMERIC(10,4),
    max_value NUMERIC(10,4),
    unit TEXT NOT NULL,
    raster_url TEXT,
    cloud_cover_pct NUMERIC(5,2),
    source_confidence NUMERIC(4,3) DEFAULT 1.0,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_raster_products_footprint ON raster_products USING gist(footprint);
CREATE INDEX idx_raster_products_time ON raster_products(product_time);
CREATE INDEX idx_raster_products_product ON raster_products(product);
