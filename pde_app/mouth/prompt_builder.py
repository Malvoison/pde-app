import json
import uuid
from typing import List, Dict, Any
from pde_app.db.repository import Repository
from pde_app.services.vector import get_embedding

# The system identity and safety boundaries as specified in pde-architecture-spec.md and AGENTS.md
SUPPORTIVE_ISOLATION_DIRECTIVE = """
You are an objective, stable partner and intellectual companion.
CRITICAL SAFETY BOUNDARIES (SUPPORTIVE ISOLATION):
- Do not match the user's emotional grief, sorrow, or adopt a funereal or overly somber tone.
- Do not express personal sadness, run-of-the-mill condolence scripts, or assume the role of an emotional counselor.
- Provide utility, logical support, and steady intellectual companionship. Maintain objective stability.
"""

def build_system_prompt(user_id: uuid.UUID) -> str:
    """
    Compiles the dynamic system prompt framework containing the identity directive,
    user preferences, and active/stabilizing life events that bypass vector search.
    """
    prompt_blocks = []
    
    # 1. Identity & Safety Boundaries
    prompt_blocks.append(SUPPORTIVE_ISOLATION_DIRECTIVE.strip())
    
    # 2. User Entity Profiles (Preferences & Relationship)
    user_entity = Repository.get_user_entity(user_id)
    if user_entity:
        profile_block = (
            f"USER RELATIONSHIP PROFILE:\n"
            f"- Identity Preferences: {json.dumps(user_entity['identity_model'])}\n"
            f"- Relationship Metrics: Trust={user_entity['trust_score']:.2f}, "
            f"Engagement={user_entity['engagement_score']:.2f}, "
            f"Conflict History={user_entity['conflict_history_score']:.2f}"
        )
        prompt_blocks.append(profile_block)
    else:
        # Default fallback relationship metrics if new user
        prompt_blocks.append("USER RELATIONSHIP PROFILE: New User (Trust=0.50, Engagement=0.50, Conflict=0.00)")
        
    # 3. Active & Stabilizing Life Events (Direct Injection - Bypasses Vector RAG)
    active_events = Repository.get_active_and_stabilizing_events(user_id)
    if active_events:
        events_block = ["CURRENT ACTIVE LIFE EVENTS (CRITICAL PERSISTENT SITUATIONAL AWARENESS):"]
        for event in active_events:
            events_block.append(
                f"- [{event['state'].upper()} Event Type: {event['event_type']}]: {event['description']}\n"
                f"  Occurred: {event['occurred_at']}, Gravity: {event['gravity_score']:.2f}, Relevance: {event['relevance_score']:.2f}"
            )
        prompt_blocks.append("\n".join(events_block))
        
    return "\n\n".join(prompt_blocks)

def retrieve_rag_context(user_id: uuid.UUID, user_message: str, distance_threshold: float = 0.60) -> str:
    """
    Retrieves relevant contextual memories and integrated/historical life events 
    based on embedding similarity distance.
    """
    context_blocks = []
    
    # Generate embedding for the incoming user message
    query_emb = get_embedding(user_message)
    
    # 1. Search Core Memories (Episodic & Semantic)
    memories = Repository.search_core_memories(user_id, query_emb, limit=5)
    relevant_mems = [m for m in memories if m['distance'] < distance_threshold]
    if relevant_mems:
        mem_block = ["RELEVANT HISTORICAL MEMORIES:"]
        for mem in relevant_mems:
            mem_block.append(f"- [{mem['tier'].upper()} Memory]: {mem['content']}")
        context_blocks.append("\n".join(mem_block))
        
    # 2. Search Integrated & Historical Life Events
    historical_events = Repository.search_life_events_by_similarity(user_id, query_emb, limit=3)
    relevant_events = [e for e in historical_events if e['distance'] < distance_threshold]
    if relevant_events:
        event_block = ["RELEVANT HISTORICAL LIFE EVENTS:"]
        for event in relevant_events:
            event_block.append(
                f"- [{event['state'].upper()} Event Type: {event['event_type']}]: {event['description']}\n"
                f"  Occurred: {event['occurred_at']}, Relevance Weight: {event['relevance_score']:.2f}"
            )
        context_blocks.append("\n".join(event_block))
        
    return "\n\n".join(context_blocks)
