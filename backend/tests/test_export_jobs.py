import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.db.schema import init_schema
from app.schemas.exports import CreateExportJobRequest
from app.services.exports.job_service import JobService, get_job_service


@pytest.fixture(autouse=True)
def setup_test_schema(test_settings):
    """Ensure database schema is created for test database."""
    init_schema(test_settings.get_sqlite_path())


@pytest.mark.unit
def test_create_export_job_api_success(client: TestClient):
    """Verify POST /api/exports/jobs queues a valid job."""
    payload = {
        "report_title": "Monthly Revenue",
        "sql": "SELECT month, SUM(revenue) FROM sales GROUP BY month;",
        "database": "master",
        "include_sql": False,
    }

    resp = client.post("/api/exports/jobs", json=payload, headers={"X-Remote-User": "CORP\\analyst1"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["report_title"] == "Monthly Revenue"
    assert data["status"] == "Pending"
    assert data["requested_by"] == "CORP\\analyst1"
    assert "id" in data
    assert "file_path" not in data  # Never expose physical file path


@pytest.mark.unit
def test_create_export_job_api_rejects_invalid_sql(client: TestClient):
    """Verify POST /api/exports/jobs rejects prohibited SQL."""
    payload = {
        "report_title": "Sneaky Drop",
        "sql": "DROP TABLE critical_data;",
    }

    resp = client.post("/api/exports/jobs", json=payload)
    assert resp.status_code == 400
    assert "SQL Validation Error" in resp.json()["detail"]


@pytest.mark.unit
def test_atomic_job_claim_and_duplicate_prevention(test_settings):
    """Verify only one worker can claim a pending job."""
    job_service = JobService(test_settings.get_sqlite_path())

    req = CreateExportJobRequest(
        report_title="Exclusive Job",
        sql="SELECT 1 AS num;",
    )
    job = job_service.create_job(req, requested_by="user1")

    # Worker 1 claims job
    claimed_1 = job_service.claim_next_job("worker_node_1")
    assert claimed_1 is not None
    assert claimed_1["id"] == job.id

    # Worker 2 attempts to claim while worker 1 is running it
    claimed_2 = job_service.claim_next_job("worker_node_2")
    assert claimed_2 is None  # No jobs pending


@pytest.mark.unit
def test_job_download_lifecycle(client: TestClient, test_settings, tmp_path: Path):
    """Test full download lifecycle: cannot download while pending, download succeeds when completed."""
    job_service = JobService(test_settings.get_sqlite_path())

    req = CreateExportJobRequest(
        report_title="Downloadable Report",
        sql="SELECT 1 AS val;",
    )
    job = job_service.create_job(req, requested_by="user1")

    # 1. Attempt download while Pending -> 400 Bad Request
    resp = client.get(f"/api/exports/jobs/{job.id}/download")
    assert resp.status_code == 400
    assert "not available" in resp.json()["detail"]

    # 2. Simulate worker completing the job with a real temp file
    dummy_file = tmp_path / "test_download.xlsx"
    dummy_file.write_bytes(b"PK\x03\x04DummyExcelBytes")

    job_service.complete_job(
        job_id=job.id,
        file_path=str(dummy_file),
        file_size_bytes=len(dummy_file.read_bytes()),
        total_rows=10,
        duration_ms=100,
    )

    # 3. Attempt download after completion -> 200 OK with binary stream
    resp = client.get(f"/api/exports/jobs/{job.id}/download")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert resp.content == b"PK\x03\x04DummyExcelBytes"


@pytest.mark.unit
def test_job_cancellation(client: TestClient, test_settings):
    """Test cancelling an active or pending job."""
    job_service = JobService(test_settings.get_sqlite_path())

    req = CreateExportJobRequest(
        report_title="Cancel Me",
        sql="SELECT 1 AS val;",
    )
    job = job_service.create_job(req, requested_by="user1")

    resp = client.post(f"/api/exports/jobs/{job.id}/cancel")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cancelled"] is True
    assert data["status"] == "Cancelled"

    # Verify status in database
    updated = job_service.get_job(job.id)
    assert updated.status == "Cancelled"


@pytest.mark.unit
def test_stale_job_recovery(test_settings):
    """Verify worker recovers jobs where worker heartbeat timed out."""
    job_service = JobService(test_settings.get_sqlite_path())

    req = CreateExportJobRequest(
        report_title="Crashed Worker Job",
        sql="SELECT 1 AS val;",
    )
    job = job_service.create_job(req, requested_by="user1")
    claimed = job_service.claim_next_job("dead_worker")
    assert claimed is not None

    # Manually backdate heartbeat by 30 minutes
    old_heartbeat = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    from app.db.sqlite import get_db_connection
    with get_db_connection(test_settings.get_sqlite_path()) as conn:
        conn.execute("UPDATE export_jobs SET heartbeat_at = ? WHERE id = ?", (old_heartbeat, job.id))

    # Run recovery with 15-minute threshold
    recovered = job_service.recover_stale_jobs(stale_timeout_minutes=15)
    assert recovered == 1

    updated = job_service.get_job(job.id)
    assert updated.status == "Failed"
    assert "heartbeat timeout" in updated.error_message


@pytest.mark.unit
def test_expired_file_cleanup(test_settings, tmp_path: Path):
    """Verify expired files are removed from disk after retention period."""
    job_service = JobService(test_settings.get_sqlite_path())

    # Create dummy file
    exp_file = tmp_path / "expired_report.xlsx"
    exp_file.write_bytes(b"old_data")

    req = CreateExportJobRequest(
        report_title="Old Report",
        sql="SELECT 1 AS val;",
    )
    # Retention period: -1 day (already expired)
    job = job_service.create_job(req, requested_by="user1", retention_days=-1)
    job_service.complete_job(
        job_id=job.id,
        file_path=str(exp_file),
        file_size_bytes=8,
        total_rows=1,
        duration_ms=10,
    )

    assert exp_file.exists()

    # Trigger cleanup
    deleted = job_service.cleanup_expired_files()
    assert deleted == 1
    assert not exp_file.exists()

