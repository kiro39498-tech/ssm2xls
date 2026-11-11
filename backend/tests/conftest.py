import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.core.config import Settings, get_settings
from app.db.sqlite import init_db
from app.main import create_application


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Provide a path to a temporary SQLite database for testing."""
    return tmp_path / "test_metadata.db"


@pytest.fixture
def test_settings(temp_db_path: Path) -> Settings:
    """Provide test settings pointing to the temporary SQLite database."""
    return Settings(
        app_name="SSMS2XLS_Test",
        app_env="test",
        debug=True,
        sqlite_db_path=str(temp_db_path),
        sqlite_busy_timeout_ms=5000,
        sql_server="localhost",
        sql_database="master",
        sql_driver="ODBC Driver 18 for SQL Server",
        sql_trusted_connection=True,
        sql_encrypt=True,
        sql_trust_server_certificate=False,
        sql_connection_timeout=2,
        sql_query_timeout=2,
    )


@pytest.fixture
def client(test_settings: Settings, monkeypatch) -> TestClient:
    """FastAPI TestClient with test settings and initialized SQLite database."""
    # Ensure get_settings returns test_settings
    monkeypatch.setattr("app.core.config.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.db.sqlite.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.db.mssql.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.api.v1.health.get_settings", lambda: test_settings)

    init_db(test_settings.get_sqlite_path())

    app = create_application()
    with TestClient(app) as test_client:
        yield test_client

