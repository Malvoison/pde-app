import datetime
import uuid
from pde_app.db.repository import Repository
from pde_app.mouth.prompt_builder import build_system_prompt, retrieve_rag_context, SUPPORTIVE_ISOLATION_DIRECTIVE

def test_supportive_isolation_directive_presence(test_user_id):
    """Verifies that the Supportive Isolation safety boundaries are compiled at the top of the system prompt."""
    prompt = build_system_prompt(test_user_id)
    
    # Check safety directive is present
    assert SUPPORTIVE_ISOLATION_DIRECTIVE.strip() in prompt
    # Check it is at the very beginning of the prompt blocks
    assert prompt.startswith(SUPPORTIVE_ISOLATION_DIRECTIVE.strip())


def test_active_life_event_bypass(test_user_id):
    """Verifies that active and stabilizing life events bypass RAG and are directly injected."""
    # Insert active bereavement event
    Repository.insert_life_event(
        user_id=test_user_id,
        event_type="bereavement",
        description="User's spouse passed away on 2026-03-03",
        occurred_at=datetime.date(2026, 3, 3),
        confidence=0.99,
        gravity_score=0.95,
        relevance_score=1.00
    )
    
    # Insert stabilizing health diagnosis
    Repository.insert_life_event(
        user_id=test_user_id,
        event_type="health_diagnosis",
        description="Diagnosed with mild hypertension",
        occurred_at=datetime.date(2026, 5, 1),
        confidence=0.90,
        gravity_score=0.50,
        relevance_score=1.00
    )
    
    # Compile prompt
    prompt = build_system_prompt(test_user_id)
    
    # Verify both are injected
    assert "CURRENT ACTIVE LIFE EVENTS" in prompt
    assert "User's spouse passed away on 2026-03-03" in prompt
    assert "Diagnosed with mild hypertension" in prompt
    assert "ACTIVE Event Type: bereavement" in prompt
    assert "Gravity: 0.95" in prompt
    assert "Gravity: 0.50" in prompt


def test_integrated_historical_rag_trigger(test_user_id):
    """Verifies that integrated/historical events are only retrieved when similarity trigger matches."""
    # 1. Insert integrated event with a specific query word mock embedding
    # We will query with "career change", get_embedding("career change") will return a deterministic mock vector
    # We'll link the integrated event's embedding to the embedding of "career change"
    from pde_app.services.vector import get_embedding
    
    event_desc = "User transitioned to system operations"
    event_emb = get_embedding(event_desc)
    
    event_id = Repository.insert_life_event(
        user_id=test_user_id,
        event_type="career_transition",
        description=event_desc,
        occurred_at=datetime.date(2025, 5, 1),
        confidence=0.95,
        gravity_score=0.00,
        relevance_score=0.50,
        embedding=event_emb
    )
    
    # Mark state as integrated
    Repository.save_life_event_state(event_id, "integrated", 0.00, 0.50)
    
    # 2. Query with matching text
    matching_text = "User transitioned to system operations"
    # mock embedding for "User transitioned to system operations" will be identical in mock fallback
    context = retrieve_rag_context(test_user_id, matching_text)
    
    assert "RELEVANT HISTORICAL LIFE EVENTS" in context
    assert event_desc in context
    
    # 3. Query with non-matching text (different mock embedding)
    non_matching_text = "making some food"
    context_empty = retrieve_rag_context(test_user_id, non_matching_text)
    
    # Should not trigger RAG retrieval because of cosine distance thresholds
    assert "RELEVANT HISTORICAL LIFE EVENTS" not in context_empty
    assert event_desc not in context_empty
