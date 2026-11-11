import sqlite3
import pytest
from pathlib import Path
from app.db.sqlite import (
    init_db,
    get_sqlite_connection,
    get_db_connection,
    check_sqlite_health,
)


@pytest.mark.unit
def test_sqlite_wal_mode_and_pragmas(temp_db_path: Path, test_settings, monkeypatch):
    """
    Verify:
    1. init_db initializes WAL mode.
    2. get_sqlite_connection applies busy_timeout and foreign_keys on EVERY connection.
    """
    monkeypatch.setattr("app.db.sqlite.get_settings", lambda: test_settings)

    # 1. Initialize
    init_db(temp_db_path)

    # 2. Check connection pragma values
    conn = get_sqlite_connection(temp_db_path)
    try:
        cursor = conn.cursor()

        # Check WAL mode
        cursor.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0]
        assert journal_mode.lower() == "wal"

        # Check busy_timeout
        cursor.execute("PRAGMA busy_timeout;")
        busy_timeout = cursor.fetchone()[0]
        assert busy_timeout == test_settings.sqlite_busy_timeout_ms

        # Check foreign_keys
        cursor.execute("PRAGMA foreign_keys;")
        foreign_keys = cursor.fetchone()[0]
        assert foreign_keys == 1

        cursor.close()
    finally:
        conn.close()


@pytest.mark.unit
def test_sqlite_context_manager_commit_and_rollback(temp_db_path: Path, test_settings, monkeypatch):
    """Verify transaction management: commits on exit, rollbacks on exception."""
    monkeypatch.setattr("app.db.sqlite.get_settings", lambda: test_settings)
    init_db(temp_db_path)

    # Create test table
    with get_db_connection(temp_db_path) as conn:
        conn.execute("CREATE TABLE test_items (id INTEGER PRIMARY KEY, name TEXT);")

    # Verify commit on success
    with get_db_connection(temp_db_path) as conn:
        conn.execute("INSERT INTO test_items (name) VALUES ('Item A');")

    with get_db_connection(temp_db_path) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM test_items;")
        assert cursor.fetchone()[0] == 1

    # Verify rollback on error
    with pytest.raises(ValueError):
        with get_db_connection(temp_db_path) as conn:
            conn.execute("INSERT INTO test_items (name) VALUES ('Item B');")
            raise ValueError("Forced error to test rollback")

    with get_db_connection(temp_db_path) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM test_items;")
        assert cursor.fetchone()[0] == 1  # Item B was rolled back


@pytest.mark.unit
def test_sqlite_health_check(temp_db_path: Path, test_settings, monkeypatch):
    """Verify SQLite health check reporting."""
    monkeypatch.setattr("app.db.sqlite.get_settings", lambda: test_settings)
    init_db(temp_db_path)

    health = check_sqlite_health(temp_db_path)
    assert health["status"] == "healthy"
    assert health["connected"] is True
    assert health["journal_mode"].lower() == "wal"
    assert health["foreign_keys_enabled"] is True
    assert health["busy_timeout_ms"] == test_settings.sqlite_busy_timeout_ms

