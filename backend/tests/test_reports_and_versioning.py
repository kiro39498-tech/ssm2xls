import pytest
from fastapi.testclient import TestClient
from app.db.schema import init_schema
from app.services.reports.audit_service import get_audit_service, mask_sensitive_params
from app.services.reports.report_service import get_report_service


@pytest.fixture(autouse=True)
def setup_test_schema(test_settings):
    """Ensure database schema is created for test database."""
    init_schema(test_settings.get_sqlite_path())


@pytest.mark.unit
def test_create_report_and_initial_draft_v1(client: TestClient):
    """Verify creating a report generates parent query and Draft v1."""
    payload = {
        "title": "Monthly Active Users",
        "description": "Calculates monthly active users by region",
        "category": "Analytics",
        "initial_sql": "SELECT region, COUNT(DISTINCT user_id) as active_users FROM sessions GROUP BY region;",
    }

    resp = client.post("/api/reports", json=payload, headers={"X-Remote-User": "CORP\\dev_alice"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Monthly Active Users"
    assert data["category"] == "Analytics"
    assert data["is_active"] is True
    assert data["created_by"] == "CORP\\dev_alice"
    assert data["current_version_id"] is not None
    assert data["current_version"]["version_number"] == 1
    assert data["current_version"]["status"] == "Draft"
    assert "sessions" in data["current_version"]["sql_text"]


@pytest.mark.unit
def test_update_draft_version(client: TestClient):
    """Verify modifying a Draft version succeeds."""
    create_payload = {
        "title": "Product Catalog",
        "initial_sql": "SELECT id, name FROM products;",
    }
    c_resp = client.post("/api/reports", json=create_payload)
    v1_id = c_resp.json()["current_version_id"]

    # Update draft v1
    update_payload = {
        "sql": "SELECT id, name, price, stock FROM products WHERE is_active = 1;",
        "change_summary": "Added price, stock and active filter",
    }
    u_resp = client.put(f"/api/reports/versions/{v1_id}", json=update_payload)
    assert u_resp.status_code == 200
    data = u_resp.json()
    assert data["version_number"] == 1
    assert data["status"] == "Draft"
    assert "price, stock" in data["sql_text"]
    assert data["change_summary"] == "Added price, stock and active filter"


@pytest.mark.unit
def test_immutability_enforcement_on_approved_and_active_versions(client: TestClient):
    """
    CORE SECURITY RULE: Approved, Active, or Archived versions CANNOT be modified in place.
    Attempts to update must be rejected with an immutability violation error.
    """
    create_payload = {
        "title": "Financial Audit Report",
        "initial_sql": "SELECT account_id, balance FROM accounts;",
    }
    c_resp = client.post("/api/reports", json=create_payload)
    v1_id = c_resp.json()["current_version_id"]

    # 1. Test -> Approve v1
    client.post(f"/api/reports/versions/{v1_id}/test")
    client.post(f"/api/reports/versions/{v1_id}/approve")

    # 2. Attempt to modify Approved v1 in-place -> Must be REJECTED!
    tamper_payload = {
        "sql": "SELECT account_id, balance, secret_routing_num FROM accounts;",
    }
    resp = client.put(f"/api/reports/versions/{v1_id}", json=tamper_payload)
    assert resp.status_code == 400
    assert "immutable" in resp.json()["detail"].lower()


@pytest.mark.unit
def test_clone_to_new_draft_and_approval_workflow(client: TestClient):
    """
    Full lifecycle test:
    1. Create Report (Draft v1)
    2. Test & Approve v1
    3. Activate v1 (production)
    4. Clone to Draft v2
    5. Modify Draft v2
    6. Test, Approve, and Activate v2
    7. Verify v1 is now Archived and v2 is Active
    """
    # 1. Create Report (Draft v1)
    c_resp = client.post(
        "/api/reports",
        json={"title": "Sales Performance", "initial_sql": "SELECT rep_id, total FROM sales;"},
    )
    report_id = c_resp.json()["id"]
    v1_id = c_resp.json()["current_version_id"]

    # 2. Test & Approve v1
    t_resp = client.post(f"/api/reports/versions/{v1_id}/test?test_summary=Verified 100 rows in 12ms")
    assert t_resp.json()["status"] == "Tested"

    a_resp = client.post(f"/api/reports/versions/{v1_id}/approve")
    assert a_resp.json()["status"] == "Approved"

    # 3. Activate v1
    act_resp = client.post(f"/api/reports/versions/{v1_id}/activate")
    assert act_resp.json()["status"] == "Active"

    # 4. Clone to Draft v2
    new_draft_resp = client.post(
        f"/api/reports/{report_id}/new-draft",
        json={"change_summary": "Adding regional grouping"},
    )
    assert new_draft_resp.status_code == 201
    v2_id = new_draft_resp.json()["id"]
    assert new_draft_resp.json()["version_number"] == 2
    assert new_draft_resp.json()["status"] == "Draft"

    # 5. Modify Draft v2 (Modifying v2 succeeds while v1 remains frozen)
    mod_resp = client.put(
        f"/api/reports/versions/{v2_id}",
        json={"sql": "SELECT rep_id, region, SUM(total) as regional_total FROM sales GROUP BY rep_id, region;"},
    )
    assert mod_resp.status_code == 200
    assert "regional_total" in mod_resp.json()["sql_text"]

    # 6. Test, Approve, and Activate v2
    client.post(f"/api/reports/versions/{v2_id}/test")
    client.post(f"/api/reports/versions/{v2_id}/approve")
    client.post(f"/api/reports/versions/{v2_id}/activate")

    # 7. Check Version History: v2 is Active, v1 is Archived
    vers_resp = client.get(f"/api/reports/{report_id}/versions")
    versions = vers_resp.json()
    assert len(versions) == 2
    v2_entry = next(v for v in versions if v["version_number"] == 2)
    v1_entry = next(v for v in versions if v["version_number"] == 1)

    assert v2_entry["status"] == "Active"
    assert v1_entry["status"] == "Archived"

    # Check parent report points to v2
    rep_resp = client.get(f"/api/reports/{report_id}")
    assert rep_resp.json()["current_version_id"] == v2_id
    assert rep_resp.json()["current_version"]["version_number"] == 2


@pytest.mark.unit
def test_toggle_report_disabled(client: TestClient):
    """Verify enabling and disabling a report."""
    c_resp = client.post("/api/reports", json={"title": "Temporary Metric", "initial_sql": "SELECT 1;"})
    report_id = c_resp.json()["id"]
    assert c_resp.json()["is_active"] is True

    # Disable
    resp_off = client.post(f"/api/reports/{report_id}/toggle-active?is_active=false")
    assert resp_off.status_code == 200
    assert resp_off.json()["is_active"] is False

    # Enable
    resp_on = client.post(f"/api/reports/{report_id}/toggle-active?is_active=true")
    assert resp_on.status_code == 200
    assert resp_on.json()["is_active"] is True


@pytest.mark.unit
def test_audit_logging_and_parameter_masking(client: TestClient, test_settings):
    """Verify audit logging records query execution and masks sensitive parameters."""
    audit_service = get_audit_service()

    # Test parameter masking utility
    params = {
        "client_id": 1042,
        "db_password": "super_secret_password",
        "api_token": "token_xyz123",
        "start_date": "2026-01-01",
    }
    masked = mask_sensitive_params(params)
    assert masked["client_id"] == 1042
    assert masked["start_date"] == "2026-01-01"
    assert masked["db_password"] == "***MASKED***"
    assert masked["api_token"] == "***MASKED***"

    # Record execution via audit service
    log_id = audit_service.record_execution(
        executed_by="CORP\\auditor",
        execution_type="Preview",
        database_name="master",
        duration_ms=35,
        rows_returned=50,
        status="Success",
        query_id="query_abc",
        parameters=params,
    )
    assert log_id > 0

    # Query audit logs via API endpoint
    resp = client.get("/api/reports/audit/all?user=CORP\\auditor")
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) >= 1
    latest = logs[0]
    assert latest["executed_by"] == "CORP\\auditor"
    assert latest["rows_returned"] == 50
    assert "super_secret_password" not in latest["parameters_json"]
    assert "***MASKED***" in latest["parameters_json"]

