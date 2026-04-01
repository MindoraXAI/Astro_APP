-- AIS PostgreSQL Schema Initialization

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email       TEXT UNIQUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Natal charts table (encrypted birth data)
CREATE TABLE IF NOT EXISTS natal_charts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    full_name       TEXT,
    birth_place     TEXT,
    birth_date      DATE NOT NULL,
    birth_time      TIME NOT NULL,
    timezone        TEXT NOT NULL,
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    time_confidence TEXT DEFAULT 'approximate',
    chart_state_json JSONB,
    tradition       TEXT DEFAULT 'vedic',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Predictions table
CREATE TABLE IF NOT EXISTS predictions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chart_id        UUID REFERENCES natal_charts(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    domain          TEXT NOT NULL,
    statement       TEXT NOT NULL,
    confidence      DOUBLE PRECISION,
    source_rules    JSONB,
    activation_start DATE,
    activation_end   DATE,
    severity        TEXT,
    alm_version     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Prediction feedback table  
CREATE TABLE IF NOT EXISTS prediction_feedback (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prediction_id   UUID REFERENCES predictions(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    accuracy_rating INT CHECK (accuracy_rating BETWEEN 1 AND 5),
    outcome_desc    TEXT,
    timing_accuracy TEXT,
    collected_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_charts_user ON natal_charts(user_id);
CREATE INDEX IF NOT EXISTS idx_predictions_chart ON predictions(chart_id);
CREATE INDEX IF NOT EXISTS idx_predictions_domain ON predictions(domain);
CREATE INDEX IF NOT EXISTS idx_feedback_prediction ON prediction_feedback(prediction_id);
