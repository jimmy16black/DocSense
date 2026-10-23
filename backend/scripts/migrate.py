"""Supabase PostgreSQL Migration Runner.

Applies SQL migrations in chronological order from `infra/supabase/migrations/`.
Can be run locally, in CI, or in deployment pipelines via `make db-migrate`.
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import engine

logger = get_logger("db.migrate")
settings = get_settings()

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "infra" / "supabase" / "migrations"


async def run_migrations() -> None:
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        print(f"No migration files found in {MIGRATIONS_DIR}")
        return

    print(
        f"Applying {len(migration_files)} migrations against {settings.SUPABASE_DB_URL.split('@')[-1]}..."
    )
    async with engine.begin() as conn:
        for file in migration_files:
            print(f"  -> Applying {file.name}...", end=" ", flush=True)
            sql = file.read_text(encoding="utf-8")
            try:
                # asyncpg supports multi-statement script execution via raw connection
                raw_conn = await conn.get_raw_connection()
                await raw_conn.driver_connection.execute(sql)
                print("✓")
            except Exception:
                # Fallback to standard execute
                try:
                    await conn.execute(text(sql))
                    print("✓")
                except Exception as inner_e:
                    print(f"✗ FAILED\nError in {file.name}: {inner_e}")
                    raise inner_e

    print("All migrations applied successfully.")


if __name__ == "__main__":
    try:
        asyncio.run(run_migrations())
    except Exception as exc:
        print(f"Migration error: {exc}", file=sys.stderr)
        sys.exit(1)
