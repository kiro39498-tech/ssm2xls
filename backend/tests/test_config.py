import pytest
from app.core.config import Settings


@pytest.mark.unit
def test_default_config_security():
    """Verify default security settings."""
    settings = Settings(
        app_name="SSMS2XLS",
        sqlite_db_path="data/metadata.db",
        sql_server="localhost",
        sql_database="master",
        sql_trust_server_certificate=False,
    )

    assert settings.sql_encrypt is True
    assert settings.sql_trust_server_certificate is False
    assert settings.sqlite_busy_timeout_ms == 30000


@pytest.mark.unit
def test_connection_string_builder():
    """Verify connection string formatting for ODBC Driver 18."""
    settings = Settings(
        sql_server="sql-cluster.corp.local",
        sql_database="FinancialReports",
        sql_driver="ODBC Driver 18 for SQL Server",
        sql_trusted_connection=True,
        sql_encrypt=True,
        sql_trust_server_certificate=False,
        sql_connection_timeout=10,
    )

    conn_str = settings.build_sql_server_connection_string()
    assert "DRIVER={ODBC Driver 18 for SQL Server}" in conn_str
    assert "SERVER=sql-cluster.corp.local" in conn_str
    assert "DATABASE=FinancialReports" in conn_str
    assert "Trusted_Connection=yes" in conn_str
    assert "Encrypt=yes" in conn_str
    assert "TrustServerCertificate=no" in conn_str


@pytest.mark.unit
def test_connection_string_builder_with_local_override():
    """Verify TrustServerCertificate=yes when explicitly configured for local dev."""
    settings = Settings(
        sql_server="localhost",
        sql_database="master",
        sql_trust_server_certificate=True,
    )

    conn_str = settings.build_sql_server_connection_string()
    assert "TrustServerCertificate=yes" in conn_str
