import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_liveness_endpoint(client: TestClient):
    """Liveness check must return 200 OK without requiring SQL Server."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "SSMS2XLS_Test"
    assert data["environment"] == "test"
    assert "timestamp" in data


@pytest.mark.unit
def test_readiness_endpoint_with_stopped_sql_server(client: TestClient, monkeypatch):
    """
    Readiness check when SQL Server is unreachable:
    FastAPI should respond with 200 OK, overall status 'degraded',
    and clear component error messages without throwing an unhandled exception.
    """
    # Mock check_mssql_health to return unreachable
    monkeypatch.setattr(
        "app.api.v1.health.check_mssql_health",
        lambda: {
            "status": "unreachable",
            "connected": False,
            "server": "localhost",
            "database": "master",
            "error": "Server is down (simulated)",
        },
    )

    response = client.get("/api/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["app"]["status"] == "healthy"
    assert data["databases"]["sqlite"]["connected"] is True
    assert data["databases"]["sql_server"]["connected"] is False
    assert "simulated" in data["databases"]["sql_server"]["error"]


@pytest.mark.unit
def test_readiness_endpoint_when_all_healthy(client: TestClient, monkeypatch):
    """Readiness check when both SQLite and SQL Server are available."""
    monkeypatch.setattr(
        "app.api.v1.health.check_mssql_health",
        lambda: {
            "status": "connected",
            "connected": True,
            "server": "localhost",
            "server_instance": "MSSQLSERVER",
            "database": "master",
            "version": "Microsoft SQL Server 2022",
        },
    )

    response = client.get("/api/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["databases"]["sqlite"]["connected"] is True
    assert data["databases"]["sql_server"]["connected"] is True


@pytest.mark.unit
def test_database_health_endpoint(client: TestClient, monkeypatch):
    """Verify /api/health/db returns complete diagnostic structure."""
    monkeypatch.setattr(
        "app.api.v1.health.check_mssql_health",
        lambda: {
            "status": "unreachable",
            "connected": False,
            "server": "localhost",
            "database": "master",
            "error": "MSSQLSERVER service stopped",
        },
    )

    response = client.get("/api/health/db")
    assert response.status_code == 200
    data = response.json()
    assert "sqlite" in data
    assert "sql_server" in data
    assert data["sqlite"]["connected"] is True
    assert data["sql_server"]["connected"] is False

