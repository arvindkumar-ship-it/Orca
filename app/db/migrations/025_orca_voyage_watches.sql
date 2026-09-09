-- ORCA migration: voyage_watches (backs route_optimizer/watcher.py)
CREATE TABLE voyage_watches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    marine_zone_id UUID NOT NULL REFERENCES marine_zones(id) ON DELETE CASCADE,
    activity_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','completed','cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_voyage_watches_zone_activity ON voyage_watches(marine_zone_id, activity_type) WHERE status = 'active';
CREATE INDEX idx_voyage_watches_user ON voyage_watches(user_id);
