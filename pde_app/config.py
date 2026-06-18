import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class Config:
    # Database Settings
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_USER: str = os.getenv("DB_USER", "pde_user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "pde_password")
    DB_NAME: str = os.getenv("DB_NAME", "pde_db")

    # DB Connection String (for psycopg3)
    @classmethod
    def get_db_connection_string(cls) -> str:
        return f"host={cls.DB_HOST} port={cls.DB_PORT} user={cls.DB_USER} password={cls.DB_PASSWORD} dbname={cls.DB_NAME}"

    # LLM Settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

    # Vector Settings
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "1536"))

config = Config()
