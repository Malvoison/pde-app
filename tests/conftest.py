import pytest
import uuid
from pde_app.db.connection import get_connection, init_pool, close_pool
from pde_app.db.migrate import run_migrations

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Initializes the database pool and runs migrations once for the test session."""
    init_pool()
    try:
        # Run migrations to ensure schema is up-to-date
        run_migrations()
    except Exception as e:
        pytest.fail(f"Could not connect to database or run migrations: {e}. Please ensure Postgres/pgvector is running.")
    
    yield
    
    close_pool()

@pytest.fixture(autouse=True)
def clean_db():
    """Cleans up the database tables after each test to ensure test isolation."""
    yield
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Disable triggers/FK checks temporarily or truncate in dependency order
            cur.execute("TRUNCATE session_observations, raw_events, core_memories, life_events, sessions, user_entities CASCADE;")
        conn.commit()

@pytest.fixture
def test_user_id() -> uuid.UUID:
    """Fixture supplying a deterministic test UUID for user identification."""
    return uuid.UUID("44444444-4444-4444-4444-444444444444")

@pytest.fixture
def test_session_id() -> uuid.UUID:
    """Fixture supplying a deterministic test UUID for session identification."""
    return uuid.UUID("99999999-9999-9999-9999-999999999999")
