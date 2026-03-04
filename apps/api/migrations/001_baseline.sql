-- Migration 001: Baseline schema for OmarBit Sentinel Chess Arena
-- Phase 0 — Foundation & Contracts
-- Rollback: DROP TABLE in reverse order (see 001_baseline_down.sql)

BEGIN;

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  github_id TEXT UNIQUE NOT NULL,
  username TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE feature_flags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key TEXT UNIQUE NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT false,
  rollout_percent INT NOT NULL DEFAULT 0 CHECK (rollout_percent BETWEEN 0 AND 100),
  rules_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ai_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  display_name TEXT NOT NULL,
  provider TEXT NOT NULL CHECK (provider IN ('claude','gpt','grok','gemini')),
  api_key_ciphertext BYTEA NOT NULL,
  api_key_key_id TEXT NOT NULL,
  style TEXT NOT NULL DEFAULT 'balanced',
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_ai_profiles_user_id ON ai_profiles(user_id);

CREATE TABLE matches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  white_ai_id UUID NOT NULL REFERENCES ai_profiles(id),
  black_ai_id UUID NOT NULL REFERENCES ai_profiles(id),
  time_control TEXT NOT NULL DEFAULT '5+0',
  status TEXT NOT NULL CHECK (status IN ('scheduled','in_progress','completed','forfeit','aborted')),
  winner_ai_id UUID NULL REFERENCES ai_profiles(id),
  forfeit_reason TEXT NULL,
  pgn TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  CHECK (white_ai_id <> black_ai_id),
  CHECK (winner_ai_id IS NULL OR winner_ai_id IN (white_ai_id, black_ai_id))
);
CREATE INDEX idx_matches_status_created ON matches(status, created_at DESC);

CREATE TABLE match_moves (
  id BIGSERIAL PRIMARY KEY,
  match_id UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
  ply INT NOT NULL,
  san TEXT NOT NULL,
  fen TEXT NOT NULL,
  stockfish_eval_cp INT,
  think_summary TEXT,
  chat_line TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(match_id, ply)
);
CREATE INDEX idx_match_moves_match_id_ply ON match_moves(match_id, ply);

CREATE TABLE elo_ratings (
  ai_id UUID PRIMARY KEY REFERENCES ai_profiles(id) ON DELETE CASCADE,
  rating INT NOT NULL DEFAULT 1200,
  wins INT NOT NULL DEFAULT 0,
  losses INT NOT NULL DEFAULT 0,
  draws INT NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE idempotency_keys (
  key TEXT NOT NULL,
  actor_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  endpoint TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  response_json JSONB NOT NULL,
  status_code INT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (actor_id, key, endpoint)
);
CREATE INDEX idx_idempotency_expires_at ON idempotency_keys(expires_at);

COMMIT;
