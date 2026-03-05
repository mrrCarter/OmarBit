-- Rollback migration 003: Remove match commentary table

BEGIN;

DROP TABLE IF EXISTS match_commentary;
DELETE FROM feature_flags WHERE key = 'orchestrator_enabled';

COMMIT;
