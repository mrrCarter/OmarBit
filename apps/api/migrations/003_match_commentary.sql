-- Migration 003: Match commentary table for orchestrator LLM output
-- Feature: Spectator commentary (feature-flagged via orchestrator_enabled)

BEGIN;

CREATE TABLE IF NOT EXISTS match_commentary (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id    UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    ply_start   INT NOT NULL,
    ply_end     INT NOT NULL,
    commentary  TEXT NOT NULL,
    opening_name TEXT,
    game_phase  TEXT CHECK (game_phase IN ('opening', 'middlegame', 'endgame')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_match_commentary_match_id ON match_commentary(match_id);

-- Add feature flag for orchestrator
INSERT INTO feature_flags (key, description, enabled, rollout_percent)
VALUES ('orchestrator_enabled', 'Enable LLM spectator commentary during matches', false, 0)
ON CONFLICT (key) DO NOTHING;

COMMIT;
