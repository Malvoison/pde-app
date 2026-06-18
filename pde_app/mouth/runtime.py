import uuid
from pde_app.db.repository import Repository
from pde_app.mouth.prompt_builder import build_system_prompt, retrieve_rag_context
from pde_app.services.llm import get_completion

def execute_session_turn(session_id: uuid.UUID, user_id: uuid.UUID, user_message: str) -> str:
    """
    Executes a single synchronous conversational interaction turn:
    1. Instantiates or verifies the session status.
    2. Writes the user's incoming message to the raw_events immutable log.
    3. Assembles the dynamic system prompt (safety + user preferences + active events).
    4. Gathers relevant RAG context via embedding similarity.
    5. Retrieves the full session history transcript.
    6. Calls the LLM completion engine.
    7. Writes the entity's response back to raw_events.
    """
    # 1. Ensure the session exists in the database
    Repository.create_session(session_id, user_id)
    
    # 2. Write incoming user event to raw log
    Repository.insert_raw_event(
        session_id=session_id,
        user_id=user_id,
        speaker="user",
        content=user_message
    )
    
    # 3. Assemble components of system instruction prompt
    system_prompt = build_system_prompt(user_id)
    
    # 4. Retrieve similarity RAG context (semantic memories & historical events)
    rag_context = retrieve_rag_context(user_id, user_message)
    
    # 5. Fetch full chronological session transcript (includes the user message just saved)
    events = Repository.get_raw_events(session_id)
    transcript_lines = []
    for ev in events:
        speaker_label = "User" if ev["speaker"] == "user" else "Entity"
        transcript_lines.append(f"{speaker_label}: {ev['content']}")
    transcript_str = "\n".join(transcript_lines)
    
    # 6. Build the prompt payload
    prompt_payload = []
    if rag_context:
        prompt_payload.append(rag_context)
        
    prompt_payload.append("CURRENT SESSION TRANSCRIPT:")
    prompt_payload.append(transcript_str)
    prompt_payload.append("Entity:")
    
    full_prompt = "\n\n".join(prompt_payload)
    
    # 7. Query LLM completion engine
    response_text = get_completion(full_prompt, system_prompt=system_prompt)
    
    # 8. Write entity response to raw log
    Repository.insert_raw_event(
        session_id=session_id,
        user_id=user_id,
        speaker="entity",
        content=response_text
    )
    
    return response_text
