import json
import uuid
import datetime
from typing import List, Dict, Any, Optional
from pde_app.db.connection import get_connection

class Repository:
    
    # --- Sessions ---
    @staticmethod
    def create_session(session_id: uuid.UUID, user_id: uuid.UUID) -> None:
        query = """
            INSERT INTO sessions (id, user_id, status)
            VALUES (%s, %s, 'active')
            ON CONFLICT (id) DO NOTHING;
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (session_id, user_id))
            conn.commit()

    @staticmethod
    def end_session(session_id: uuid.UUID, status: str = "completed") -> None:
        query = """
            UPDATE sessions
            SET ended_at = CURRENT_TIMESTAMP, status = %s
            WHERE id = %s;
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (status, session_id))
            conn.commit()

    @staticmethod
    def set_session_status(session_id: uuid.UUID, status: str) -> None:
        query = """
            UPDATE sessions
            SET status = %s, processed_at = CASE WHEN %s = 'processed' THEN CURRENT_TIMESTAMP ELSE processed_at END
            WHERE id = %s;
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (status, status, session_id))
            conn.commit()

    @staticmethod
    def get_session(session_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        query = """
            SELECT id, user_id, started_at, ended_at, processed_at, status
            FROM sessions WHERE id = %s;
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (session_id,))
                row = cur.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "user_id": row[1],
                        "started_at": row[2],
                        "ended_at": row[3],
                        "processed_at": row[4],
                        "status": row[5]
                    }
        return None

    # --- Raw Events ---
    @staticmethod
    def insert_raw_event(session_id: uuid.UUID, user_id: uuid.UUID, speaker: str, content: str, metadata: Dict[str, Any] = None) -> int:
        query = """
            INSERT INTO raw_events (session_id, user_id, speaker, content, metadata)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
        """
        meta_json = json.dumps(metadata or {})
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (session_id, user_id, speaker, content, meta_json))
                row = cur.fetchone()
                event_id = row[0] if row else None
            conn.commit()
            return event_id

    @staticmethod
    def get_raw_events(session_id: uuid.UUID) -> List[Dict[str, Any]]:
        query = """
            SELECT id, session_id, user_id, speaker, content, metadata, created_at
            FROM raw_events
            WHERE session_id = %s
            ORDER BY id ASC;
        """
        events = []
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (session_id,))
                rows = cur.fetchall()
                for row in rows:
                    events.append({
                        "id": row[0],
                        "session_id": row[1],
                        "user_id": row[2],
                        "speaker": row[3],
                        "content": row[4],
                        "metadata": row[5],
                        "created_at": row[6]
                    })
        return events

    # --- User Entities ---
    @staticmethod
    def get_user_entity(user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        query = """
            SELECT user_id, identity_model, trust_score, engagement_score, conflict_history_score, updated_at
            FROM user_entities WHERE user_id = %s;
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (user_id,))
                row = cur.fetchone()
                if row:
                    return {
                        "user_id": row[0],
                        "identity_model": row[1],
                        "trust_score": float(row[2]),
                        "engagement_score": float(row[3]),
                        "conflict_history_score": float(row[4]),
                        "updated_at": row[5]
                    }
        return None

    @staticmethod
    def save_user_entity(user_id: uuid.UUID, identity_model: Dict[str, Any], trust_score: float, engagement_score: float, conflict_history_score: float) -> None:
        query = """
            INSERT INTO user_entities (user_id, identity_model, trust_score, engagement_score, conflict_history_score, updated_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE
            SET identity_model = EXCLUDED.identity_model,
                trust_score = EXCLUDED.trust_score,
                engagement_score = EXCLUDED.engagement_score,
                conflict_history_score = EXCLUDED.conflict_history_score,
                updated_at = CURRENT_TIMESTAMP;
        """
        identity_json = json.dumps(identity_model)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (user_id, identity_json, trust_score, engagement_score, conflict_history_score))
            conn.commit()

    # --- Core Memories ---
    @staticmethod
    def insert_core_memory(user_id: uuid.UUID, tier: str, content: str, embedding: List[float], confidence: float, source_event_ids: List[int]) -> uuid.UUID:
        query = """
            INSERT INTO core_memories (user_id, tier, content, embedding, confidence, source_event_ids)
            VALUES (%s, %s, %s, %s::vector, %s, %s)
            RETURNING id;
        """
        # Convert float list to vector string format: '[0.1,0.2,...]'
        vector_str = f"[{','.join(map(str, embedding))}]"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (user_id, tier, content, vector_str, confidence, source_event_ids))
                row = cur.fetchone()
                mem_id = row[0] if row else None
            conn.commit()
            return mem_id

    @staticmethod
    def search_core_memories(user_id: uuid.UUID, query_embedding: List[float], tier: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        vector_str = f"[{','.join(map(str, query_embedding))}]"
        if tier:
            query = """
                SELECT id, tier, content, confidence, source_event_ids, created_at, (embedding <=> %s::vector) AS distance
                FROM core_memories
                WHERE user_id = %s AND tier = %s
                ORDER BY distance ASC
                LIMIT %s;
            """
            params = (vector_str, user_id, tier, limit)
        else:
            query = """
                SELECT id, tier, content, confidence, source_event_ids, created_at, (embedding <=> %s::vector) AS distance
                FROM core_memories
                WHERE user_id = %s
                ORDER BY distance ASC
                LIMIT %s;
            """
            params = (vector_str, user_id, limit)

        memories = []
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                for row in rows:
                    memories.append({
                        "id": row[0],
                        "tier": row[1],
                        "content": row[2],
                        "confidence": float(row[3]),
                        "source_event_ids": row[4],
                        "created_at": row[5],
                        "distance": float(row[6]) if row[6] is not None else 1.0
                    })
        return memories

    # --- Life Events ---
    @staticmethod
    def insert_life_event(
        user_id: uuid.UUID,
        event_type: str,
        description: str,
        occurred_at: datetime.date,
        confidence: float,
        gravity_score: float = 1.0,
        relevance_score: float = 1.0,
        embedding: Optional[List[float]] = None,
        source_event_ids: List[int] = None
    ) -> uuid.UUID:
        query = """
            INSERT INTO life_events (user_id, event_type, description, occurred_at, confidence, state, gravity_score, relevance_score, embedding, source_event_ids)
            VALUES (%s, %s, %s, %s, %s, 'active', %s, %s, %s::vector, %s)
            RETURNING id;
        """
        vector_str = f"[{','.join(map(str, embedding))}]" if embedding is not None else None
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (user_id, event_type, description, occurred_at, confidence, gravity_score, relevance_score, vector_str, source_event_ids))
                row = cur.fetchone()
                event_id = row[0] if row else None
            conn.commit()
            return event_id

    @staticmethod
    def get_life_event(event_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        query = """
            SELECT id, user_id, event_type, description, occurred_at, confidence, state, gravity_score, relevance_score, source_event_ids, created_at, updated_at
            FROM life_events WHERE id = %s;
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (event_id,))
                row = cur.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "user_id": row[1],
                        "event_type": row[2],
                        "description": row[3],
                        "occurred_at": row[4],
                        "confidence": float(row[5]),
                        "state": row[6],
                        "gravity_score": float(row[7]),
                        "relevance_score": float(row[8]),
                        "source_event_ids": row[9],
                        "created_at": row[10],
                        "updated_at": row[11]
                    }
        return None

    @staticmethod
    def get_active_and_stabilizing_events(user_id: uuid.UUID) -> List[Dict[str, Any]]:
        query = """
            SELECT id, event_type, description, occurred_at, confidence, state, gravity_score, relevance_score
            FROM life_events
            WHERE user_id = %s AND state IN ('active', 'stabilizing')
            ORDER BY occurred_at DESC;
        """
        events = []
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (user_id,))
                rows = cur.fetchall()
                for row in rows:
                    events.append({
                        "id": row[0],
                        "event_type": row[1],
                        "description": row[2],
                        "occurred_at": row[3],
                        "confidence": float(row[4]),
                        "state": row[5],
                        "gravity_score": float(row[6]),
                        "relevance_score": float(row[7])
                    })
        return events

    @staticmethod
    def get_all_unresolved_life_events(user_id: uuid.UUID) -> List[Dict[str, Any]]:
        # Unresolved means active, stabilizing, or integrated. Historical is excluded.
        query = """
            SELECT id, event_type, description, occurred_at, confidence, state, gravity_score, relevance_score
            FROM life_events
            WHERE user_id = %s AND state != 'historical'
            ORDER BY occurred_at DESC;
        """
        events = []
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (user_id,))
                rows = cur.fetchall()
                for row in rows:
                    events.append({
                        "id": row[0],
                        "event_type": row[1],
                        "description": row[2],
                        "occurred_at": row[3],
                        "confidence": float(row[4]),
                        "state": row[5],
                        "gravity_score": float(row[6]),
                        "relevance_score": float(row[7])
                    })
        return events

    @staticmethod
    def search_life_events_by_similarity(user_id: uuid.UUID, query_embedding: List[float], limit: int = 3) -> List[Dict[str, Any]]:
        vector_str = f"[{','.join(map(str, query_embedding))}]"
        # Search integrated and historical events via cosine similarity
        query = """
            SELECT id, event_type, description, occurred_at, confidence, state, gravity_score, relevance_score, (embedding <=> %s::vector) AS distance
            FROM life_events
            WHERE user_id = %s AND state IN ('integrated', 'historical') AND embedding IS NOT NULL
            ORDER BY distance ASC
            LIMIT %s;
        """
        events = []
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (vector_str, user_id, limit))
                rows = cur.fetchall()
                for row in rows:
                    events.append({
                        "id": row[0],
                        "event_type": row[1],
                        "description": row[2],
                        "occurred_at": row[3],
                        "confidence": float(row[4]),
                        "state": row[5],
                        "gravity_score": float(row[6]),
                        "relevance_score": float(row[7]),
                        "distance": float(row[8]) if row[8] is not None else 1.0
                    })
        return events

    @staticmethod
    def save_life_event_state(life_event_id: uuid.UUID, state: str, gravity_score: float, relevance_score: float) -> None:
        query = """
            UPDATE life_events
            SET state = %s, gravity_score = %s, relevance_score = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (state, gravity_score, relevance_score, life_event_id))
            conn.commit()

    # --- Session Observations ---
    @staticmethod
    def save_session_observation(
        session_id: uuid.UUID,
        life_event_id: uuid.UUID,
        direct_reference_to_life_event: bool,
        acute_distress_detected: bool,
        tone: str,
        functional_normalcy_score: float,
        reactivation_trigger_detected: bool,
        source_event_ids: List[int]
    ) -> uuid.UUID:
        query = """
            INSERT INTO session_observations (session_id, life_event_id, direct_reference_to_life_event, acute_distress_detected, tone, functional_normalcy_score, reactivation_trigger_detected, source_event_ids)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (
                    session_id,
                    life_event_id,
                    direct_reference_to_life_event,
                    acute_distress_detected,
                    tone,
                    functional_normalcy_score,
                    reactivation_trigger_detected,
                    source_event_ids
                ))
                row = cur.fetchone()
                obs_id = row[0] if row else None
            conn.commit()
            return obs_id

    @staticmethod
    def get_session_observations_for_event(life_event_id: uuid.UUID) -> List[Dict[str, Any]]:
        query = """
            SELECT id, session_id, life_event_id, direct_reference_to_life_event, acute_distress_detected, tone, functional_normalcy_score, reactivation_trigger_detected, source_event_ids, created_at
            FROM session_observations
            WHERE life_event_id = %s
            ORDER BY created_at ASC;
        """
        observations = []
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (life_event_id,))
                rows = cur.fetchall()
                for row in rows:
                    observations.append({
                        "id": row[0],
                        "session_id": row[1],
                        "life_event_id": row[2],
                        "direct_reference_to_life_event": row[3],
                        "acute_distress_detected": row[4],
                        "tone": row[5],
                        "functional_normalcy_score": float(row[6]),
                        "reactivation_trigger_detected": row[7],
                        "source_event_ids": row[8],
                        "created_at": row[9]
                    })
        return observations
