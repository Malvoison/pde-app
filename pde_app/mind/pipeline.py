import uuid
import datetime
from typing import List
from pde_app.db.repository import Repository
from pde_app.models import (
    ExtractedFactsContainer,
    SessionObservationsContainer,
    ImpactCategory
)
from pde_app.services.llm import get_structured_completion
from pde_app.services.vector import get_embedding

def process_post_session_assessment(session_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """
    Asynchronous post-session pipeline:
    1. Fetches full session transcript and raw event IDs.
    2. Runs LLM-based fact extraction (enforces confidence >= 0.80).
       - LOW: Inserts episodic memory.
       - MEDIUM: Inserts episodic + semantic memory.
       - HIGH: Inserts life_event (if no active event of that type exists).
    3. Runs LLM-based observation extraction for existing active/stabilizing events.
    4. Saves observations to session_observations table for daemon processing.
    5. Updates session status to 'processed'.
    """
    # 1. Fetch transcript and event IDs for source verification
    events = Repository.get_raw_events(session_id)
    if not events:
        # Nothing to process
        Repository.set_session_status(session_id, "processed")
        return
        
    event_ids = [ev["id"] for ev in events]
    
    # Format the transcript text block for the LLM
    transcript_lines = []
    for ev in events:
        speaker_label = "User" if ev["speaker"] == "user" else "Entity"
        transcript_lines.append(f"{speaker_label}: {ev['content']}")
    transcript_str = "\n".join(transcript_lines)

    # 2. Fact Extraction and Significance Assessment
    facts_prompt = (
        f"Analyze the following session transcript between User and Entity.\n"
        f"Extract persistent facts, preferences, or major life changes, and classify their lifecycle impact category (low, medium, high).\n"
        f"For HIGH impact events, specify the event_type ('bereavement', 'career_transition', 'health_diagnosis', 'relationship_dissolution') and occurred_at if stated.\n\n"
        f"SESSION TRANSCRIPT:\n{transcript_str}"
    )
    
    extracted = get_structured_completion(
        prompt=facts_prompt,
        response_schema=ExtractedFactsContainer,
        system_prompt="You are an expert fact extractor and significance assessor."
    )
    
    for item in extracted.facts:
        if item.confidence < 0.80:
            continue
            
        emb = get_embedding(item.fact)
        
        if item.impact_assessment == ImpactCategory.LOW:
            # Low impact -> Episodic memory
            Repository.insert_core_memory(
                user_id=user_id,
                tier="episodic",
                content=item.fact,
                embedding=emb,
                confidence=item.confidence,
                source_event_ids=event_ids
            )
        elif item.impact_assessment == ImpactCategory.MEDIUM:
            # Medium impact -> Episodic + Semantic memory
            Repository.insert_core_memory(
                user_id=user_id,
                tier="episodic",
                content=item.fact,
                embedding=emb,
                confidence=item.confidence,
                source_event_ids=event_ids
            )
            Repository.insert_core_memory(
                user_id=user_id,
                tier="semantic",
                content=item.fact,
                embedding=emb,
                confidence=item.confidence,
                source_event_ids=event_ids
            )
        elif item.impact_assessment == ImpactCategory.HIGH:
            # High impact -> Life Event (if none currently active of that type)
            event_type = item.event_type or "career_transition"
            active_events = Repository.get_active_and_stabilizing_events(user_id)
            existing_active = any(e["event_type"] == event_type for e in active_events)
            
            if not existing_active:
                occurred_date = item.occurred_at or datetime.datetime.now(datetime.timezone.utc).date()
                Repository.insert_life_event(
                    user_id=user_id,
                    event_type=event_type,
                    description=item.fact,
                    occurred_at=occurred_date,
                    confidence=item.confidence,
                    gravity_score=1.0,
                    relevance_score=1.0,
                    embedding=emb,
                    source_event_ids=event_ids
                )

    # 3. Extract Session Observations for Existing Active State Transitions
    active_and_stabilizing = Repository.get_active_and_stabilizing_events(user_id)
    if active_and_stabilizing:
        events_summary = []
        for e in active_and_stabilizing:
            events_summary.append(f"Event ID: {e['id']}, Type: {e['event_type']}, Description: {e['description']}")
        events_str = "\n".join(events_summary)
        
        obs_prompt = (
            f"Given these active life events of the user:\n{events_str}\n\n"
            f"Evaluate the user's interaction in this transcript to extract observations for each event.\n"
            f"Specify if the user directly referred to it, whether acute distress was detected, "
            f"tone characteristics, normalcy levels (0.0 to 1.0), and triggers.\n\n"
            f"SESSION TRANSCRIPT:\n{transcript_str}"
        )
        
        obs_extracted = get_structured_completion(
            prompt=obs_prompt,
            response_schema=SessionObservationsContainer,
            system_prompt="You are an expert mental/semantic state observer."
        )
        
        for obs in obs_extracted.observations:
            Repository.save_session_observation(
                session_id=session_id,
                life_event_id=obs.event_id,
                direct_reference_to_life_event=obs.direct_reference_to_life_event,
                acute_distress_detected=obs.acute_distress_detected,
                tone=obs.tone,
                functional_normalcy_score=obs.functional_normalcy_score,
                reactivation_trigger_detected=obs.reactivation_trigger_detected,
                source_event_ids=event_ids
            )
            
    # 4. Mark session status as processed
    Repository.set_session_status(session_id, "processed")
