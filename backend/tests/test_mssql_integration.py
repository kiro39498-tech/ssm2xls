import pytest
from app.core.config import get_settings
from app.db.mssql import check_mssql_health, get_mssql_session


@pytest.mark.integration
def test_live_mssql_connection():
    """
    Integration test: Attempts real connection to local SQL Server instance.
    This test will only pass when MSSQLSERVER is started and accessible via Windows Auth.
    """
    settings = get_settings()
    health = check_mssql_health()

    if not health.get("connected"):
        pytest.fail(
            f"Live SQL Server is unreachable. Ensure the service 'MSSQLSERVER' is running.\n"
            f"Error details: {health.get('error')}"
        )

    assert health["connected"] is True
    assert health["server"] == settings.sql_server
    assert "version" in health

    # Verify query execution on live connection
    with get_mssql_session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 42 AS answer;")
        row = cursor.fetchone()
        assert row[0] == 42
        cursor.close()

