import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def init_db(db_path: Path | None = None) -> None:
    """
    Initialize SQLite metadata database and enable WAL mode.
    Called once during application startup.
    """
    settings = get_settings()
    path = db_path or settings.get_sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing SQLite database at %s with WAL mode", path)
    conn = sqlite3.connect(str(path))
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        result = cursor.fetchone()
        journal_mode = result[0] if result else "unknown"
        logger.info("SQLite journal_mode set to: %s", journal_mode)
    finally:
        conn.close()


def get_sqlite_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """
    Create a new SQLite connection with busy_timeout and foreign_keys enabled.
    Per requirements, busy_timeout and foreign_keys must be applied to EVERY connection.
    """
    settings = get_settings()
    path = db_path or settings.get_sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    timeout_sec = max(1.0, settings.sqlite_busy_timeout_ms / 1000.0)

    conn = sqlite3.connect(
        str(path),
        timeout=timeout_sec,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()
    cursor.execute(f"PRAGMA busy_timeout = {settings.sqlite_busy_timeout_ms};")
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.close()

    return conn


@contextmanager
def get_db_connection(db_path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite database connection."""
    conn = get_sqlite_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def check_sqlite_health(db_path: Path | None = None) -> dict:
    """Verify SQLite connection and report configuration status."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 AS alive;")
            cursor.fetchone()

            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0]

            cursor.execute("PRAGMA foreign_keys;")
            foreign_keys = bool(cursor.fetchone()[0])

            cursor.execute("PRAGMA busy_timeout;")
            busy_timeout = cursor.fetchone()[0]

            cursor.close()

            return {
                "status": "healthy",
                "connected": True,
                "database_path": str(db_path or get_settings().get_sqlite_path()),
                "journal_mode": journal_mode,
                "foreign_keys_enabled": foreign_keys,
                "busy_timeout_ms": busy_timeout,
            }
    except Exception as exc:
        logger.error("SQLite health check failed: %s", exc)
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(exc),
        }
