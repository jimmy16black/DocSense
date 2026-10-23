"""ISSUE-016: Verify Alembic migration drift and schema parity with SQLAlchemy models."""

import os
from pathlib import Path

from alembic.config import Config

from alembic import command


def test_alembic_migrations_and_check():
    backend_dir = Path(__file__).resolve().parent.parent
    ini_path = backend_dir / "alembic.ini"
    assert ini_path.exists(), "alembic.ini must exist in backend directory"

    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    # Test against temporary sqlite database
    test_db = backend_dir / "test_migration_drift.db"
    if test_db.exists():
        test_db.unlink()

    sqlite_url = f"sqlite+aiosqlite:///{test_db}"
    alembic_cfg.set_main_option("sqlalchemy.url", sqlite_url)
    os.environ["ALEMBIC_DB_URL"] = sqlite_url

    try:
        # Upgrade to head
        command.upgrade(alembic_cfg, "head")

        # Verify no schema drift
        command.check(alembic_cfg)
    finally:
        if test_db.exists():
            test_db.unlink()
