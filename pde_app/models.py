import enum
import uuid
import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class ImpactCategory(str, enum.Enum):
    LOW = "low"         # Transient facts, preferences (e.g., "prefers black coffee")
    MEDIUM = "medium"   # Shift in routines, tools (e.g., "adopting Go for system backends")
    HIGH = "high"       # Fundamental structural shift (e.g., "lost job", "spouse passed away")

class ExtractedFact(BaseModel):
    fact: str = Field(description="Durable, concrete fact or preference revealed by the user.")
    confidence: float = Field(description="Confidence weight score from 0.0 to 1.0.")
    impact_assessment: ImpactCategory = Field(description="Estimated structural impact on user's daily life.")
    event_type: Optional[str] = Field(default=None, description="If High impact, classify (e.g., 'bereavement', 'career_transition', 'health_diagnosis', 'relationship_dissolution').")
    occurred_at: Optional[datetime.date] = Field(default=None, description="Stated date of event occurrence.")

class SessionObservations(BaseModel):
    event_id: uuid.UUID = Field(description="Database UUID of the associated Life Event.")
    direct_reference_to_life_event: bool = Field(description="Did the user explicitly mention or heavily imply the event?")
    acute_distress_detected: bool = Field(description="Are there semantic signals of high acute distress or mourning?")
    tone: str = Field(description="One-word descriptor of tone: e.g., grieving, anxious, reflective, neutral, humorous.")
    functional_normalcy_score: float = Field(description="Score from 0.0 (debilitated) to 1.0 (full engagement on unrelated topics).")
    reactivation_trigger_detected: bool = Field(description="Did conversation touch on triggers (anniversaries, legal milestones, acute physical setbacks)?")

class ExtractedFactsContainer(BaseModel):
    facts: List[ExtractedFact]

class SessionObservationsContainer(BaseModel):
    observations: List[SessionObservations]

