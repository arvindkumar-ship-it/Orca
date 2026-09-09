-- ORCA migration: conversation memory (R3 — multi-turn, contextual,
-- refinable conversations). One row per session, turns stored as a JSONB
-- array in Anthropic Messages API format so planner_agent.py can load it
-- straight into its `messages` list with no reshaping.

CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    detected_language_code TEXT,
    detected_language_name TEXT,
    turns JSONB NOT NULL DEFAULT '[]'::jsonb,   -- [{role, content}, ...] — Anthropic Messages API shape
    resolved_entities JSONB NOT NULL DEFAULT '{}'::jsonb,  -- e.g. {"last_zone_id": "...", "last_lat": .., "last_lng": ..}
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chat_sessions_user ON chat_sessions(user_id, last_active_at DESC);
