-- Rollback Migration 001: Drop all baseline tables
-- WARNING: Destructive operation. Only run in dev/staging.
-- Production rollbacks should use point-in-time recovery (PITR)
-- from the managed database provider.

-- Safety guard: abort if running against a production database.
-- Set ALLOW_DESTRUCTIVE_MIGRATION=true to override.
DO $$
BEGIN
  IF current_setting('app.allow_destructive_migration', true) IS DISTINCT FROM 'true' THEN
    RAISE EXCEPTION 'Destructive migration blocked. Set: SET app.allow_destructive_migration = ''true''; to proceed.';
  END IF;
END
$$;

BEGIN;

DROP TABLE IF EXISTS idempotency_keys CASCADE;
DROP TABLE IF EXISTS elo_ratings CASCADE;
DROP TABLE IF EXISTS match_moves CASCADE;
DROP TABLE IF EXISTS matches CASCADE;
DROP TABLE IF EXISTS ai_profiles CASCADE;
DROP TABLE IF EXISTS feature_flags CASCADE;
DROP TABLE IF EXISTS users CASCADE;

COMMIT;
