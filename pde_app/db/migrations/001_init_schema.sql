-- Enable the vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Memory Tier classification
DO $$ BEGIN
    CREATE TYPE memory_tier AS ENUM ('episodic', 'semantic');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Interaction status classification
DO $$ BEGIN
    CREATE TYPE interaction_quality AS ENUM ('positive', 'neutral', 'negative');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Life Event States
DO $$ BEGIN
    CREATE TYPE life_event_state AS ENUM ('active', 'stabilizing', 'integrated', 'historical');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Tiers 2 & 3: Core Memories (Vector & Document Store)
CREATE TABLE IF NOT EXISTS core_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    tier memory_tier NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536) NOT NULL, -- Configurable but default to 1536 (OpenAI small embeddings)
    confidence NUMERIC(3,2) NOT NULL CHECK (confidence >= 0.00 AND confidence <= 1.00),
    source_event_ids BIGINT[], -- references raw_events
    last_accessed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_memories_vector ON core_memories USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_memories_user_tier ON core_memories(user_id, tier);

-- Tier 4 & Relationship Store (User Entity Profiles)
CREATE TABLE IF NOT EXISTS user_entities (
    user_id UUID PRIMARY KEY,
    identity_model JSONB NOT NULL DEFAULT '{}'::jsonb, -- Core preferences, stable communication values
    trust_score NUMERIC(3,2) NOT NULL DEFAULT 0.50 CHECK (trust_score >= 0.00 AND trust_score <= 1.00),
    engagement_score NUMERIC(3,2) NOT NULL DEFAULT 0.50 CHECK (engagement_score >= 0.00 AND engagement_score <= 1.00),
    conflict_history_score NUMERIC(3,2) NOT NULL DEFAULT 0.00 CHECK (conflict_history_score >= 0.00 AND conflict_history_score <= 1.00),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tier 5: Life Events / State Transitions Table (The Situational Gravity Layer)
CREATE TABLE IF NOT EXISTS life_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL, -- e.g., 'bereavement', 'career_transition', 'health_diagnosis', 'relationship_dissolution'
    description TEXT NOT NULL,
    occurred_at DATE NOT NULL,
    confidence NUMERIC(3,2) NOT NULL CHECK (confidence >= 0.00 AND confidence <= 1.00),
    state life_event_state NOT NULL DEFAULT 'active',
    
    -- Dual Scoring Mechanics
    gravity_score NUMERIC(3,2) NOT NULL DEFAULT 1.00 CHECK (gravity_score >= 0.00 AND gravity_score <= 1.00),
    relevance_score NUMERIC(3,2) NOT NULL DEFAULT 1.00 CHECK (relevance_score >= 0.00 AND relevance_score <= 1.00),
    
    embedding VECTOR(1536), -- Added to support RAG on integrated/historical life events
    source_event_ids BIGINT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_life_events_user_state ON life_events(user_id, state);
CREATE INDEX IF NOT EXISTS idx_life_events_vector ON life_events USING hnsw (embedding vector_cosine_ops);
