import decimal
import uuid
from datetime import datetime, timezone
import pytest
import pyodbc
from fastapi.testclient import TestClient
from app.services.sql.executor import SQLExecutor, serialize_sql_value


@pytest.mark.unit
def test_serialize_sql_values():
    """Verify data type serialization."""
    now = datetime(2026, 11, 2, 8, 30, 0, tzinfo=timezone.utc)
    uid = uuid.uuid4()
    dec = decimal.Decimal("123.456")

    assert serialize_sql_value(None) is None
    assert serialize_sql_value(now) == "2026-11-02T08:30:00+00:00"
    assert serialize_sql_value(uid) == str(uid)
    assert serialize_sql_value(dec) == 123.456
    assert serialize_sql_value(b"\x01\x02\x03") == "010203"
    assert serialize_sql_value("Hello") == "Hello"
    assert serialize_sql_value(42) == 42


@pytest.mark.unit
def test_executor_rejects_invalid_sql_without_connecting(monkeypatch):
    """
    Executor must structurally validate before connecting.
    If SQL is invalid, it must never attempt to connect to SQL Server.
    """
    executor = SQLExecutor()

    # If get_mssql_connection were called, fail the test
    def fail_if_called(*args, **kwargs):
        pytest.fail("Database connection should not have been attempted for invalid SQL.")

    monkeypatch.setattr("app.services.sql.executor.get_mssql_connection", fail_if_called)

    res = executor.execute_query("DROP TABLE users;")
    assert res.status == "failed"
    assert "SQL Validation Error" in res.error_message
    assert res.row_count == 0


@pytest.mark.unit
def test_executor_handles_query_cancellation(monkeypatch):
    """
    Verify that an ODBC HY008 OperationalError is recognized as a user cancellation.
    """
    executor = SQLExecutor()

    class MockCursor:
        def __init__(self):
            self.timeout = 30
            self.description = [("col1", int, None, None, None, None, True)]

        def execute(self, *args, **kwargs):
            raise pyodbc.OperationalError("HY008", "[HY008] Operation canceled by user")

        def close(self):
            pass

    class MockConnection:
        def cursor(self):
            return MockCursor()

        def close(self):
            pass

    monkeypatch.setattr("app.services.sql.executor.get_mssql_connection", lambda db: MockConnection())

    res = executor.execute_query("SELECT 1 AS num;")
    assert res.status == "cancelled"
    assert "cancelled" in res.error_message.lower()


@pytest.mark.unit
def test_query_validation_api_endpoint(client: TestClient):
    """Test POST /api/queries/validate endpoint."""
    # 1. Valid query
    resp = client.post("/api/queries/validate", json={"sql": "SELECT id, name FROM users WHERE active = 1;"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert len(data["errors"]) == 0
    assert data["statement_type"] == "SELECT"

    # 2. Dangerous query
    resp = client.post("/api/queries/validate", json={"sql": "DELETE FROM users;"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is False
    assert len(data["errors"]) > 0


@pytest.mark.unit
def test_query_cancel_api_endpoint(client: TestClient):
    """Test POST /api/queries/cancel/{execution_id} endpoint."""
    # When ID is not active
    resp = client.post("/api/queries/cancel/non-existent-id")
    assert resp.status_code == 200
    data = resp.json()
    assert data["execution_id"] == "non-existent-id"
    assert data["cancelled"] is False

