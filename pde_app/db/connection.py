from contextlib import contextmanager
from psycopg_pool import ConnectionPool
from pde_app.config import config

_pool = None

def init_pool():
    global _pool
    if _pool is None:
        # Construct the connection string from configuration
        conninfo = config.get_db_connection_string()
        _pool = ConnectionPool(
            conninfo=conninfo,
            min_size=1,
            max_size=10,
            open=True
        )

def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        init_pool()
    return _pool

def close_pool():
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None

@contextmanager
def get_connection():
    """Context manager to lease a connection from the pool and automatically return it."""
    pool = get_pool()
    with pool.connection() as conn:
        yield conn
