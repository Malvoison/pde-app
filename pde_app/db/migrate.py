import os
import pathlib
from pde_app.db.connection import get_connection, close_pool

def run_migrations():
    migrations_dir = pathlib.Path(__file__).parent / "migrations"
    if not migrations_dir.exists():
        print(f"Migrations directory not found: {migrations_dir}")
        return

    # Find and sort all SQL migrations
    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        print("No migration files found.")
        return

    print(f"Found {len(migration_files)} migration files. Running migrations...")

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Create migrations tracking table if not exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.commit()

        for migration_path in migration_files:
            version = migration_path.name
            
            with conn.cursor() as cur:
                # Check if already applied
                cur.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (version,))
                if cur.fetchone():
                    print(f"Migration {version} is already applied.")
                    continue

                print(f"Applying migration {version}...")
                with open(migration_path, "r", encoding="utf-8") as f:
                    sql_content = f.read()

                try:
                    # Run migration in a transaction block
                    cur.execute(sql_content)
                    cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
                    conn.commit()
                    print(f"Successfully applied {version}.")
                except Exception as e:
                    conn.rollback()
                    print(f"CRITICAL: Failed to apply migration {version}: {e}")
                    raise e

    print("All migrations completed successfully.")

if __name__ == "__main__":
    try:
        run_migrations()
    finally:
        close_pool()
