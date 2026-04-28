-- Recovery Debt — full schema (PRD §8 + BUILD_GUIDE Day 2 + Tier-1 goals table).
-- Run this in the Supabase SQL editor on a fresh project.
-- Idempotency: every per-day table has UNIQUE (user_id, day) so backfills can be re-run safely.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ──────────────────────────────────────────────────────────────────────────────
-- Identity & auth
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE users (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  whoop_user_id   BIGINT UNIQUE,
  email           TEXT,
  timezone        TEXT NOT NULL DEFAULT 'America/New_York',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE whoop_tokens (
  user_id         UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  access_token    TEXT NOT NULL,
  refresh_token   TEXT NOT NULL,
  expires_at      TIMESTAMPTZ NOT NULL,
  scope           TEXT,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ──────────────────────────────────────────────────────────────────────────────
-- WHOOP-derived per-day tables
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE recoveries (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  day             DATE NOT NULL,
  recovery_score  INT,
  hrv_rmssd_ms    FLOAT,
  rhr_bpm         INT,
  spo2_pct        FLOAT,
  skin_temp_c     FLOAT,
  score_state     TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, day)
);

CREATE TABLE cycles (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  day             DATE NOT NULL,
  strain          FLOAT,
  kilojoule       FLOAT,
  avg_hr_bpm      INT,
  max_hr_bpm      INT,
  start_ts        TIMESTAMPTZ,
  end_ts          TIMESTAMPTZ,
  score_state     TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, day)
);

CREATE TABLE sleeps (
  id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  day                 DATE NOT NULL,
  in_bed_ms           BIGINT,
  awake_ms            BIGINT,
  light_ms            BIGINT,
  deep_ms             BIGINT,
  rem_ms              BIGINT,
  efficiency_pct      FLOAT,
  consistency_pct     FLOAT,
  respiratory_rate    FLOAT,
  sleep_need_ms       BIGINT,
  disturbances        INT,
  start_ts            TIMESTAMPTZ,
  end_ts              TIMESTAMPTZ,
  score_state         TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, day)
);

-- Workouts are per-event, not per-day. WHOOP's workout id is the natural key.
CREATE TABLE workouts (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  whoop_id        BIGINT NOT NULL,
  day             DATE NOT NULL,
  start_ts        TIMESTAMPTZ,
  end_ts          TIMESTAMPTZ,
  strain          FLOAT,
  sport_id        INT,
  avg_hr_bpm      INT,
  max_hr_bpm      INT,
  kilojoule       FLOAT,
  distance_m      FLOAT,
  zone_durations  JSONB,
  score_state     TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, whoop_id)
);

-- ──────────────────────────────────────────────────────────────────────────────
-- User-supplied per-day check-in (PRD §8 + Day 6)
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE checkins (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  day             DATE NOT NULL,
  alcohol_drinks  INT     NOT NULL DEFAULT 0,
  caffeine_mg     INT     NOT NULL DEFAULT 0,
  stress_1to10    INT     CHECK (stress_1to10 BETWEEN 1 AND 10),
  late_meal       BOOLEAN NOT NULL DEFAULT FALSE,
  ill             BOOLEAN NOT NULL DEFAULT FALSE,
  traveling       BOOLEAN NOT NULL DEFAULT FALSE,
  menstrual_day   INT,
  raw_text        TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, day)
);

-- ──────────────────────────────────────────────────────────────────────────────
-- ML outputs
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE models (
  id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  version           TEXT NOT NULL,
  trained_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  n_training_days   INT,
  metrics           JSONB,
  artifact_path     TEXT,
  UNIQUE (user_id, version)
);

CREATE TABLE predictions (
  id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  target_day          DATE NOT NULL,
  predicted_recovery  FLOAT NOT NULL,
  prediction_lower    FLOAT,
  prediction_upper    FLOAT,
  model_version       TEXT NOT NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One row per (prediction, feature). SHAP integrity test asserts
-- base_value + Σ contribution ≈ predicted_recovery within 0.01.
CREATE TABLE shap_values (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prediction_id   UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
  feature_name    TEXT NOT NULL,
  contribution    FLOAT NOT NULL,
  base_value      FLOAT,
  UNIQUE (prediction_id, feature_name)
);

-- ──────────────────────────────────────────────────────────────────────────────
-- Tier-1 differentiation: Inverse Planner (PRD §16 / BUILD_GUIDE §6.A)
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE goals (
  id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id               UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  target_day            DATE NOT NULL,
  target_recovery       FLOAT NOT NULL,
  solved_plan           JSONB,
  infeasibility_reason  TEXT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ──────────────────────────────────────────────────────────────────────────────
-- Indexes for hot read paths
-- ──────────────────────────────────────────────────────────────────────────────

CREATE INDEX idx_recoveries_user_day  ON recoveries(user_id, day DESC);
CREATE INDEX idx_cycles_user_day      ON cycles(user_id, day DESC);
CREATE INDEX idx_sleeps_user_day      ON sleeps(user_id, day DESC);
CREATE INDEX idx_workouts_user_day    ON workouts(user_id, day DESC);
CREATE INDEX idx_checkins_user_day    ON checkins(user_id, day DESC);
CREATE INDEX idx_predictions_user_day ON predictions(user_id, target_day DESC);
CREATE INDEX idx_shap_prediction      ON shap_values(prediction_id);
CREATE INDEX idx_goals_user_day       ON goals(user_id, target_day DESC);
