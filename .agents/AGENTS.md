# Project-Scoped Rules for PDE App

This file defines project-specific rules, constraints, and development guidelines for AI agents working on the Persistent Digital Entity (PDE) codebase.

---

## 1. Architectural Philosophy
- **Decoupled Architecture:** Keep the synchronous chat interface ("mouth") strictly separated from the offline state machine and memory management ("mind").
- **Asynchronous Execution:** Heavy memory operations, significance classification, consolidation, and relationship score updates must occur in asynchronous offline loops or daemons, never blocking the live interaction runtime.

## 2. Database & Schema Rules
- **Schema Compliance:** All schema modifications must adhere to and build upon the schema defined in [pde-architecture-spec.md](file:///home/allawyer66/repos/pde-app/docs/pde-architecture-spec.md). Keep vector embeddings configured for `1536` dimensions (compatible with OpenAI text-embedding-3-small or equivalent).
- **Immutability:** The `raw_events` table represents an immutable ledger of all interactions. Never design functions that delete or modify `raw_events` entries directly.
- **Traceability:** Every entry created in `core_memories` or `life_events` must store the associated `source_event_ids` referencing the `raw_events` table for auditability and state replay.

## 3. Memory & State Machine Implementation
- **Deterministic State Transitions:** Follow the state transitions: `Active` ➔ `Stabilizing` ➔ `Integrated` ➔ `Historical`. Ensure transition logic strictly respects the `STATE_MACHINE_CONFIG` durations and distress/normalcy metrics.
- **Capped Mechanics:** Ensure scores (gravity, relevance, trust, engagement) are mathematically capped between `0.00` and `1.00`.
- **Replayability:** Design state modifications such that `life_events` and `core_memories` can be completely reconstructed by replaying observations chronologically against the raw event ledger.

## 4. Structured Output and Pydantic Schema
- **Explicit Schema Enforcement:** Fact extraction and session observation observers must use strictly validated schemas (e.g., Pydantic `BaseModel` versions of `ExtractedFact` and `SessionObservations`).
- **Confidence Filtering:** Ensure a confidence threshold of at least `0.80` is met before inserting facts into episodic or semantic memories.

## 5. Safety & Persona Boundaries
- **Supportive Isolation Directive:** Always enforce system prompt constraints that prevent the entity from matching/mirroring user grief or assuming the role of an emotional counselor. The persona must remain objective, stable, and intellectually supportive.
- **Traceability Pointer Verification:** Provide tools or logging that trace any transition in `life_events` directly to the conversational transcripts to prevent hallucinated context.

## 6. Rule Evolution & Maintenance
- **Rule Updates:** As new rules, architecture patterns, and coding conventions are added to or updated within the project, agents or developers must update this `AGENTS.md` file to reflect those modifications, ensuring that the rules remain a single, up-to-date source of truth.

