import uuid
import datetime
from pde_app.db.repository import Repository

def test_session_lifecycle(test_session_id, test_user_id):
    # 1. Create session
    Repository.create_session(test_session_id, test_user_id)
    session = Repository.get_session(test_session_id)
    assert session is not None
    assert session["status"] == "active"
    assert session["user_id"] == test_user_id
    
    # 2. Update status
    Repository.set_session_status(test_session_id, "processed")
    session = Repository.get_session(test_session_id)
    assert session["status"] == "processed"
    assert session["processed_at"] is not None
    
    # 3. End session
    Repository.end_session(test_session_id, "completed")
    session = Repository.get_session(test_session_id)
    assert session["status"] == "completed"
    assert session["ended_at"] is not None


def test_raw_events_ledger(test_session_id, test_user_id):
    Repository.create_session(test_session_id, test_user_id)
    
    # Insert events
    ev_id1 = Repository.insert_raw_event(test_session_id, test_user_id, "user", "Hello there!", {"meta": "data"})
    ev_id2 = Repository.insert_raw_event(test_session_id, test_user_id, "entity", "Greetings companion.", {})
    
    assert ev_id1 is not None
    assert ev_id2 is not None
    
    # Get events
    events = Repository.get_raw_events(test_session_id)
    assert len(events) == 2
    assert events[0]["speaker"] == "user"
    assert events[0]["content"] == "Hello there!"
    assert events[0]["metadata"] == {"meta": "data"}
    assert events[1]["speaker"] == "entity"


def test_user_entity_profiles(test_user_id):
    identity_pref = {"style": "direct", "theme": "dark"}
    
    # Save profile
    Repository.save_user_entity(test_user_id, identity_pref, 0.85, 0.90, 0.05)
    
    # Retrieve profile
    entity = Repository.get_user_entity(test_user_id)
    assert entity is not None
    assert entity["identity_model"] == identity_pref
    assert entity["trust_score"] == 0.85
    assert entity["engagement_score"] == 0.90
    assert entity["conflict_history_score"] == 0.05


def test_core_memories_rag(test_user_id):
    # Dummy embedding (1536 floats)
    emb_a = [0.1] * 1536
    emb_b = [0.0] * 1536
    emb_b[0] = 1.0 # different vector
    
    Repository.insert_core_memory(test_user_id, "episodic", "Spoke about road trips", emb_a, 0.95, [1, 2])
    Repository.insert_core_memory(test_user_id, "semantic", "User prefers black coffee", emb_b, 0.99, [3])
    
    # Search closest to emb_a
    results = Repository.search_core_memories(test_user_id, emb_a, limit=2)
    assert len(results) == 2
    # The one with emb_a should be first (distance closest to 0)
    assert results[0]["content"] == "Spoke about road trips"
    assert results[0]["tier"] == "episodic"
    
    # Search tier semantic
    sem_results = Repository.search_core_memories(test_user_id, emb_b, tier="semantic", limit=1)
    assert len(sem_results) == 1
    assert sem_results[0]["content"] == "User prefers black coffee"


def test_life_events_and_observations(test_session_id, test_user_id):
    Repository.create_session(test_session_id, test_user_id)
    
    # Insert Life Event
    emb = [0.1] * 1536
    event_id = Repository.insert_life_event(
        user_id=test_user_id,
        event_type="bereavement",
        description="User's spouse passed away on 2026-03-03",
        occurred_at=datetime.date(2026, 3, 3),
        confidence=0.99,
        gravity_score=1.0,
        relevance_score=1.0,
        embedding=emb,
        source_event_ids=[1, 2]
    )
    
    assert event_id is not None
    
    # Fetch active & stabilizing
    active_events = Repository.get_active_and_stabilizing_events(test_user_id)
    assert len(active_events) == 1
    assert active_events[0]["event_type"] == "bereavement"
    assert active_events[0]["state"] == "active"
    
    # Similarity search
    # Change state to integrated so it is included in similarity search
    Repository.save_life_event_state(event_id, "integrated", 0.00, 1.00)
    
    sim_events = Repository.search_life_events_by_similarity(test_user_id, emb, limit=1)
    assert len(sim_events) == 1
    assert sim_events[0]["id"] == event_id
    
    # Save Observation
    obs_id = Repository.save_session_observation(
        session_id=test_session_id,
        life_event_id=event_id,
        direct_reference_to_life_event=True,
        acute_distress_detected=True,
        tone="grieving",
        functional_normalcy_score=0.35,
        reactivation_trigger_detected=False,
        source_event_ids=[1, 2]
    )
    
    assert obs_id is not None
    
    # Fetch Observations
    observations = Repository.get_session_observations_for_event(event_id)
    assert len(observations) == 1
    assert observations[0]["tone"] == "grieving"
    assert observations[0]["functional_normalcy_score"] == 0.35
