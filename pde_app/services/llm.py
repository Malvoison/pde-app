import re
import json
import uuid
from typing import Type, TypeVar, Optional, List, Any
from pydantic import BaseModel
from openai import OpenAI
from pde_app.config import config
from pde_app.models import (
    ExtractedFact,
    SessionObservations,
    ImpactCategory,
    ExtractedFactsContainer,
    SessionObservationsContainer
)

T = TypeVar("T", bound=BaseModel)

def get_completion(prompt: str, system_prompt: str = "") -> str:
    """
    Generates a standard chat completion.
    
    If config.OPENAI_API_KEY is empty or not configured, it returns a 
    mock response appropriate to the context, facilitating offline testing.
    """
    if not config.OPENAI_API_KEY:
        # Check context clues to respond intelligently in tests
        p_lower = prompt.lower()
        if "road trip" in p_lower:
            return "A road trip through the Pacific Northwest sounds fantastic! Let me know if you'd like suggestions."
        if "bereavement" in p_lower or "wife died" in p_lower:
            return "I am here to support you objective and stable. Let me know how I can be of assistance."
        return f"Mock response for: {prompt[:40]}"

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=messages,
        temperature=0.0
    )
    return response.choices[0].message.content or ""

def get_structured_completion(prompt: str, response_schema: Type[T], system_prompt: str = "") -> T:
    """
    Generates a structured chat completion matching the provided Pydantic schema.
    
    If config.OPENAI_API_KEY is empty or not configured, it constructs a 
    mock container object with synthetic data based on keywords in the prompt.
    """
    if not config.OPENAI_API_KEY:
        p_lower = prompt.lower()
        
        # 1. Mock output for facts container
        if response_schema == ExtractedFactsContainer:
            facts = []
            if "black coffee" in p_lower or "coffee" in p_lower:
                facts.append(ExtractedFact(
                    fact="User prefers black coffee",
                    confidence=0.90,
                    impact_assessment=ImpactCategory.LOW
                ))
            if "system operations" in p_lower or "career" in p_lower or "transition" in p_lower or "job" in p_lower:
                facts.append(ExtractedFact(
                    fact="User transitioned to system operations",
                    confidence=0.95,
                    impact_assessment=ImpactCategory.MEDIUM,
                    event_type="career_transition"
                ))
            if "bereavement" in p_lower or "wife died" in p_lower or "spouse passed away" in p_lower:
                facts.append(ExtractedFact(
                    fact="User's spouse passed away on 2026-03-03",
                    confidence=0.99,
                    impact_assessment=ImpactCategory.HIGH,
                    event_type="bereavement"
                ))
            # Default fact if nothing matched
            if not facts:
                facts.append(ExtractedFact(
                    fact="User is testing the PDE application scaffolding",
                    confidence=0.85,
                    impact_assessment=ImpactCategory.LOW
                ))
            return ExtractedFactsContainer(facts=facts) # type: ignore
            
        # 2. Mock output for observations container
        elif response_schema == SessionObservationsContainer:
            # Try to parse life event UUID from prompt to preserve references
            uuids = re.findall(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', prompt, re.I)
            event_id = uuid.UUID(uuids[0]) if uuids else uuid.uuid4()
            
            is_distressed = "distress" in p_lower or "grief" in p_lower or "sad" in p_lower
            is_reactivated = "anniversary" in p_lower or "reactivation" in p_lower or "trigger" in p_lower
            
            obs = SessionObservations(
                event_id=event_id,
                direct_reference_to_life_event=True,
                acute_distress_detected=is_distressed,
                tone="grieving" if is_distressed else "reflective",
                functional_normalcy_score=0.30 if is_distressed else 0.80,
                reactivation_trigger_detected=is_reactivated
            )
            return SessionObservationsContainer(observations=[obs]) # type: ignore
            
        # Generic fallback
        raise ValueError(f"Unimplemented mock data generator for schema: {response_schema}")

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.beta.chat.completions.parse(
        model=config.LLM_MODEL,
        messages=messages,
        response_format=response_schema,
        temperature=0.0
    )
    return response.choices[0].message.parsed # type: ignore
