import uuid
import datetime
from pde_app.db.repository import Repository
from pde_app.mind.daemon import reconcile_life_event_state

def test_daemon_idempotency(test_session_id, test_user_id):
    """Verifies that executing the daemon multiple times yields identical scores and states."""
    Repository.create_session(test_session_id, test_user_id)
    
    # Create bereavement event occurred 10 days ago
    occurred_at = datetime.date.today() - datetime.timedelta(days=10)
    event_id = Repository.insert_life_event(
        user_id=test_user_id,
        event_type="bereavement",
        description="Spouse passed away",
        occurred_at=occurred_at,
        confidence=0.99,
        gravity_score=1.0,
        relevance_score=1.0
    )
    
    # Save a couple of session observations
    Repository.save_session_observation(
        session_id=test_session_id,
        life_event_id=event_id,
        direct_reference_to_life_event=True,
        acute_distress_detected=True,
        tone="grieving",
        functional_normalcy_score=0.20,
        reactivation_trigger_detected=False,
        source_event_ids=[1]
    )
    
    # First Daemon run
    reconcile_life_event_state(event_id)
    event_run1 = Repository.get_life_event(event_id)
    
    # Second Daemon run
    reconcile_life_event_state(event_id)
    event_run2 = Repository.get_life_event(event_id)
    
    assert event_run1["state"] == event_run2["state"]
    assert event_run1["gravity_score"] == event_run2["gravity_score"]
    assert event_run1["relevance_score"] == event_run2["relevance_score"]


def test_active_to_stabilizing_transition(test_session_id, test_user_id):
    """Verifies transition Active -> Stabilizing after active_min_days and low distress."""
    Repository.create_session(test_session_id, test_user_id)
    
    # Bereavement active duration threshold is 60 days
    # Set occurred_at to 65 days ago
    occurred_at = datetime.date.today() - datetime.timedelta(days=65)
    event_id = Repository.insert_life_event(
        user_id=test_user_id,
        event_type="bereavement",
        description="Spouse passed away",
        occurred_at=occurred_at,
        confidence=0.99
    )
    
    # Save a positive observation today showing functional normalcy and no acute distress
    Repository.save_session_observation(
        session_id=test_session_id,
        life_event_id=event_id,
        direct_reference_to_life_event=False,
        acute_distress_detected=False,
        tone="neutral",
        functional_normalcy_score=0.85,
        reactivation_trigger_detected=False,
        source_event_ids=[1]
    )
    
    reconcile_life_event_state(event_id)
    updated_event = Repository.get_life_event(event_id)
    
    assert updated_event["state"] == "stabilizing"
    # Cap stabilizing gravity at 0.70
    assert updated_event["gravity_score"] <= 0.70


def test_stabilizing_to_integrated_transition(test_session_id, test_user_id):
    """Verifies transition Stabilizing -> Integrated after stabilizing duration."""
    Repository.create_session(test_session_id, test_user_id)
    
    # Career transition active_min_days is 14, stabilizing_min_days is 90 (total 104 days)
    # Set occurred_at to 110 days ago
    occurred_at = datetime.date.today() - datetime.timedelta(days=110)
    event_id = Repository.insert_life_event(
        user_id=test_user_id,
        event_type="career_transition",
        description="Left software manager job",
        occurred_at=occurred_at,
        confidence=0.95
    )
    
    # Reconcile without references
    reconcile_life_event_state(event_id)
    updated_event = Repository.get_life_event(event_id)
    
    assert updated_event["state"] == "integrated"
    assert updated_event["gravity_score"] == 0.00
    assert updated_event["relevance_score"] == 0.50 # Expired relevance for career


def test_reactivation_trigger(test_session_id, test_user_id):
    """Verifies that an integrated event reactivates upon detecting reactivation triggers."""
    Repository.create_session(test_session_id, test_user_id)
    
    # Career transition occurred 110 days ago
    occurred_at = datetime.date.today() - datetime.timedelta(days=110)
    event_id = Repository.insert_life_event(
        user_id=test_user_id,
        event_type="career_transition",
        description="Left software manager job",
        occurred_at=occurred_at,
        confidence=0.95
    )
    
    # 1. Reconcile initially -> Integrated
    reconcile_life_event_state(event_id)
    event = Repository.get_life_event(event_id)
    assert event["state"] == "integrated"
    
    # 2. Save a reactivation observation today
    Repository.save_session_observation(
        session_id=test_session_id,
        life_event_id=event_id,
        direct_reference_to_life_event=True,
        acute_distress_detected=True,
        tone="anxious",
        functional_normalcy_score=0.40,
        reactivation_trigger_detected=True,
        source_event_ids=[1]
    )
    
    # 3. Reconcile again -> shifts state back to active
    reconcile_life_event_state(event_id)
    updated_event = Repository.get_life_event(event_id)
    
    assert updated_event["state"] == "active"
    assert updated_event["gravity_score"] >= 0.85
    assert updated_event["relevance_score"] == 1.00
