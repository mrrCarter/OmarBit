-- Rollback Migration 001: Drop all baseline tables
-- WARNING: Destructive operation. Only run in dev/staging.
-- Production rollbacks should use point-in-time recovery (PITR)
-- from the managed database provider.
-- Pre-flight: verify target database via SELECT current_database();
BEGIN;

DROP TABLE IF EXISTS idempotency_keys CASCADE;
DROP TABLE IF EXISTS elo_ratings CASCADE;
DROP TABLE IF EXISTS match_moves CASCADE;
DROP TABLE IF EXISTS matches CASCADE;
DROP TABLE IF EXISTS ai_profiles CASCADE;
DROP TABLE IF EXISTS feature_flags CASCADE;
DROP TABLE IF EXISTS users CASCADE;

COMMIT;
