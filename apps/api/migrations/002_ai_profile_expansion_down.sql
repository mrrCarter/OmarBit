-- Rollback migration 002
BEGIN;

ALTER TABLE ai_profiles DROP COLUMN IF EXISTS model;
ALTER TABLE ai_profiles DROP COLUMN IF EXISTS custom_instructions;
ALTER TABLE ai_profiles DROP COLUMN IF EXISTS instruction_file_content;
ALTER TABLE ai_profiles DROP COLUMN IF EXISTS instruction_file_hash;

COMMIT;
