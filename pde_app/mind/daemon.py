import datetime
import uuid
from typing import Dict, Any, List
from pde_app.db.repository import Repository

# State machine configuration matching pde-architecture-spec.md
STATE_MACHINE_CONFIG = {
    "bereavement": {
        "active_min_days": 60,
        "stabilizing_min_days": 300,
        "never_expire_relevance": True,
        "base_decay_rate": 0.005  # Slow daily baseline drop
    },
    "career_transition": {
        "active_min_days": 14,
        "stabilizing_min_days": 90,
        "never_expire_relevance": False,
        "base_decay_rate": 0.02
    },
    "health_diagnosis": {
        "active_min_days": 30,
        "stabilizing_min_days": 180,
        "never_expire_relevance": True,
        "base_decay_rate": 0.01
    },
    "relationship_dissolution": {
        "active_min_days": 45,
        "stabilizing_min_days": 365,
        "never_expire_relevance": False,
        "base_decay_rate": 0.01
    }
}

def reconcile_life_event_state(event_id: uuid.UUID) -> None:
    """
    Rebuilds a life event's state (gravity_score, relevance_score, state)
    deterministically by replaying all historical session_observations chronologically.
    This guarantees idempotency and prevents drift.
    """
    event = Repository.get_life_event(event_id)
    if not event:
        return
        
    config = STATE_MACHINE_CONFIG.get(event["event_type"], STATE_MACHINE_CONFIG["career_transition"])
    occurred_at = event["occurred_at"]
    
    # Fetch all observations for this life event, sorted chronologically
    observations = Repository.get_session_observations_for_event(event_id)
    
    # 1. Initialize Baseline State at occurred_at
    current_state = "active"
    gravity = 1.00
    relevance = 1.00
    
    # Group observations by date (date -> list of observations)
    obs_by_date: Dict[datetime.date, List[Dict[str, Any]]] = {}
    for obs in observations:
        obs_date = obs["created_at"].date()
        obs_by_date.setdefault(obs_date, []).append(obs)
        
    # Iterate day-by-day from occurred_at to today
    current_date = occurred_at
    today = datetime.datetime.now(datetime.timezone.utc).date()
    
    while current_date <= today:
        # A. Apply daily base decay if active or stabilizing
        if current_state in ("active", "stabilizing"):
            gravity -= config["base_decay_rate"]
            
        # B. Apply observations for this specific date
        day_obs = obs_by_date.get(current_date, [])
        reinforcement = 0.0
        recovery_signals = 0.0
        reactivation_triggered = False
        distress_detected_today = False
        normalcy_scores = []
        
        for obs in day_obs:
            if obs["direct_reference_to_life_event"]:
                reinforcement += 0.05
            if obs["acute_distress_detected"]:
                reinforcement += 0.10
                distress_detected_today = True
            if obs["reactivation_trigger_detected"]:
                reinforcement += 0.15
                reactivation_triggered = True
                
            recovery_signals += obs["functional_normalcy_score"] * 0.08
            if obs["tone"] in ["reflective", "neutral", "humorous"]:
                recovery_signals += 0.05
                
            normalcy_scores.append(obs["functional_normalcy_score"])
            
        # Update gravity with daily metrics and cap it
        gravity = gravity + reinforcement - recovery_signals
        gravity = max(0.00, min(1.00, gravity))
        
        # C. Evaluate State Machine Guard Transitions
        days_since_occurrence = (current_date - occurred_at).days
        
        if current_state == "active":
            # Active -> Stabilizing transitions require min time AND evidence of functional normalcy
            if days_since_occurrence >= config["active_min_days"]:
                avg_normalcy = sum(normalcy_scores) / len(normalcy_scores) if normalcy_scores else 1.0
                if not distress_detected_today and avg_normalcy > 0.60:
                    current_state = "stabilizing"
                    gravity = min(gravity, 0.70)  # Cap stabilizing gravity
                    
        elif current_state == "stabilizing":
            # Stabilizing -> Integrated transitions require minimum stabilizing duration
            total_stabilizing_duration = days_since_occurrence - config["active_min_days"]
            if total_stabilizing_duration >= config["stabilizing_min_days"]:
                direct_references = any(o["direct_reference_to_life_event"] for o in day_obs) if day_obs else False
                if not direct_references:
                    current_state = "integrated"
                    gravity = 0.00
                    if not config["never_expire_relevance"]:
                        relevance = 0.50
                        
        elif current_state == "integrated":
            # Integrated -> Historical
            if days_since_occurrence > 365 and not config["never_expire_relevance"]:
                current_state = "historical"
                relevance = 0.10
                
        # D. Handle Reactivation Triggers
        # If integrated/historical, reactivate back to active on triggers or acute distress
        if current_state in ("integrated", "historical"):
            has_trigger = reactivation_triggered or (distress_detected_today and day_obs)
            if has_trigger:
                current_state = "active"
                gravity = max(gravity, 0.85)
                relevance = 1.00
                
        # Advance to next day
        current_date += datetime.timedelta(days=1)
        
    # 2. Commit deterministic results back to DB
    Repository.save_life_event_state(
        life_event_id=event_id,
        state=current_state,
        gravity_score=gravity,
        relevance_score=relevance
    )

def run_memory_daemon_run(user_id: uuid.UUID) -> None:
    """
    Executes the memory daemon reconciliation for a given user.
    Loads all unresolved life events and updates their state.
    """
    unresolved_events = Repository.get_all_unresolved_life_events(user_id)
    for event in unresolved_events:
        reconcile_life_event_state(event["id"])
