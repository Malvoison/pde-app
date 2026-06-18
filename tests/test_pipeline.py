import uuid
import datetime
from pde_app.db.repository import Repository
from pde_app.mind.pipeline import process_post_session_assessment

def test_pipeline_fact_extraction_and_observations(test_session_id, test_user_id):
    # 1. Create a session and write some conversations
    Repository.create_session(test_session_id, test_user_id)
    
    # We write conversations that contain keywords matching our mock LLM structured completion triggers:
    # "coffee" triggers a LOW preference memory fact
    # "system operations" triggers a MEDIUM career memory fact
    # "wife died" triggers a HIGH bereavement life event fact
    Repository.insert_raw_event(test_session_id, test_user_id, "user", "I prefer black coffee in the morning.")
    Repository.insert_raw_event(test_session_id, test_user_id, "entity", "Understood.")
    Repository.insert_raw_event(test_session_id, test_user_id, "user", "I just transitioned to system operations.")
    Repository.insert_raw_event(test_session_id, test_user_id, "entity", "Congratulations on the role.")
    Repository.insert_raw_event(test_session_id, test_user_id, "user", "My wife died on 2026-03-03, I am feeling intense grief.")
    Repository.insert_raw_event(test_session_id, test_user_id, "entity", "I am here.")
    
    # 2. Run post session assessment
    process_post_session_assessment(test_session_id, test_user_id)
    
    # 3. Verify session was marked as processed
    session = Repository.get_session(test_session_id)
    assert session["status"] == "processed"
    
    # 4. Verify memories were created
    # LOW fact: "User prefers black coffee" -> episodic memory
    mems = Repository.search_core_memories(test_user_id, [0.1]*1536, limit=10)
    assert len(mems) >= 3 # episodic (coffee), episodic (sysops), semantic (sysops)
    
    episodic_contents = [m["content"] for m in mems if m["tier"] == "episodic"]
    semantic_contents = [m["content"] for m in mems if m["tier"] == "semantic"]
    
    assert "User prefers black coffee" in episodic_contents
    assert "User transitioned to system operations" in episodic_contents
    assert "User transitioned to system operations" in semantic_contents
    assert "User prefers black coffee" not in semantic_contents # low impact, episodic only
    
    # 5. Verify High Impact event was created
    active_events = Repository.get_active_and_stabilizing_events(test_user_id)
    assert len(active_events) == 1
    assert active_events[0]["event_type"] == "bereavement"
    assert "spouse passed away" in active_events[0]["description"]
    
    # 6. Verify Session Observation was recorded for the newly created active event
    event_id = active_events[0]["id"]
    observations = Repository.get_session_observations_for_event(event_id)
    assert len(observations) == 1
    assert observations[0]["session_id"] == test_session_id
    assert observations[0]["acute_distress_detected"] is True
    assert observations[0]["tone"] == "grieving"
    assert observations[0]["functional_normalcy_score"] <= 0.40
