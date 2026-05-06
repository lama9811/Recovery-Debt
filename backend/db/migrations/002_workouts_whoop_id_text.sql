-- Migration 002 — workouts.whoop_id BIGINT → TEXT for WHOOP API v2.
-- v2 workout IDs are UUID strings (not int64s like v1). Widening to TEXT
-- preserves existing rows (cast int → text) and accepts UUIDs going forward.
-- Apply once against existing databases. Idempotent (no-op if already TEXT).

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'workouts'
      AND column_name = 'whoop_id'
      AND data_type = 'bigint'
  ) THEN
    ALTER TABLE workouts
      ALTER COLUMN whoop_id TYPE TEXT USING whoop_id::TEXT;
  END IF;
END$$;
