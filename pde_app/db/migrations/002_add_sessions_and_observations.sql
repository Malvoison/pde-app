-- Session lifecycle status classification
DO $$ BEGIN
    CREATE TYPE session_status AS ENUM ('active', 'completed', 'processed', 'failed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Sessions Table
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP WITH TIME ZONE,
    processed_at TIMESTAMP WITH TIME ZONE,
    status session_status NOT NULL DEFAULT 'active'
);

-- Tier 1: Raw Events Table (Immutable Event Log)
CREATE TABLE IF NOT EXISTS raw_events (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    speaker VARCHAR(50) NOT NULL, -- 'user' or 'entity'
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_raw_events_session ON raw_events(session_id);
CREATE INDEX IF NOT EXISTS idx_raw_events_user ON raw_events(user_id);

-- Session Observations Table (persisting LLM-extracted observations for active/stabilizing life events)
CREATE TABLE IF NOT EXISTS session_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    life_event_id UUID NOT NULL REFERENCES life_events(id) ON DELETE CASCADE,
    direct_reference_to_life_event BOOLEAN NOT NULL,
    acute_distress_detected BOOLEAN NOT NULL,
    tone VARCHAR(50) NOT NULL,
    functional_normalcy_score NUMERIC(3,2) NOT NULL CHECK (functional_normalcy_score >= 0.00 AND functional_normalcy_score <= 1.00),
    reactivation_trigger_detected BOOLEAN NOT NULL,
    source_event_ids BIGINT[] NOT NULL, -- references raw_events table ids
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index observations chronologically for deterministic state-machine replay
CREATE INDEX IF NOT EXISTS idx_session_observations_event ON session_observations(life_event_id, created_at ASC);
