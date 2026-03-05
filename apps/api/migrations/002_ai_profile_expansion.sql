-- Migration 002: AI Profile Expansion
-- Adds model selection, custom instructions, and cost tracking
-- Rollback: see 002_ai_profile_expansion_down.sql

BEGIN;

-- Model ID (e.g., "gpt-4o", "claude-sonnet-4-20250514")
ALTER TABLE ai_profiles ADD COLUMN model TEXT NOT NULL DEFAULT '';

-- Custom user instructions (max 15000 chars enforced at app layer)
ALTER TABLE ai_profiles ADD COLUMN custom_instructions TEXT;

-- Uploaded instruction file content and hash for dedup
ALTER TABLE ai_profiles ADD COLUMN instruction_file_content TEXT;
ALTER TABLE ai_profiles ADD COLUMN instruction_file_hash TEXT;

COMMIT;
