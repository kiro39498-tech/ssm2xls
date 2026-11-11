import os
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from app.core.config import get_settings
from app.schemas.exports import (
    CreateExportJobRequest,
    ExportJobResponse,
    ExportJobListResponse,
    CancelJobResponse,
)
from app.services.exports.job_service import get_job_service

router = APIRouter(prefix="/exports", tags=["Exports"])


def get_current_user(request: Request, x_remote_user: str | None = Header(default=None)) -> str:
    """
    Determine caller's Windows identity.
    In IIS / Reverse Proxy deployment, reads REMOTE_USER or X-Remote-User header.
    In local dev, falls back to Windows USERNAME / USERDOMAIN.
    """
    if x_remote_user:
        return x_remote_user

    # Check client host / environment
    username = os.getenv("USERNAME") or os.getenv("USER") or "developer"
    domain = os.getenv("USERDOMAIN")
    if domain:
        return f"{domain}\\{username}"
    return username


@router.post("/jobs", response_model=ExportJobResponse, status_code=status.HTTP_201_CREATED)
def create_export_job(
    payload: CreateExportJobRequest,
    request: Request,
    x_remote_user: str | None = Header(default=None),
) -> ExportJobResponse:
    """
    Create a new asynchronous export job.
    Validates SQL AST, queues job in SQLite, and returns a job identifier.
    Long-running execution is handled out-of-band by the Export Worker.
    """
    user_identity = get_current_user(request, x_remote_user)
    job_service = get_job_service()

    try:
        job = job_service.create_job(req=payload, requested_by=user_identity)
        return job
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get("/jobs/{job_id}", response_model=ExportJobResponse, status_code=status.HTTP_200_OK)
def get_export_job(job_id: str) -> ExportJobResponse:
    """Retrieve current status, row counts, and progress of an export job."""
    job_service = get_job_service()
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export job '{job_id}' not found.",
        )
    return job


@router.get("/jobs", response_model=ExportJobListResponse, status_code=status.HTTP_200_OK)
def list_export_jobs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    my_jobs_only: bool = Query(default=False),
    x_remote_user: str | None = Header(default=None),
) -> ExportJobListResponse:
    """List export jobs with pagination and optional user filter."""
    job_service = get_job_service()
    filter_user = get_current_user(request, x_remote_user) if my_jobs_only else None

    jobs, total = job_service.list_jobs(
        requested_by=filter_user,
        limit=limit,
        offset=offset,
    )

    return ExportJobListResponse(jobs=jobs, total=total)


@router.post("/jobs/{job_id}/cancel", response_model=CancelJobResponse, status_code=status.HTTP_200_OK)
def cancel_export_job(
    job_id: str,
    request: Request,
    x_remote_user: str | None = Header(default=None),
) -> CancelJobResponse:
    """Request cancellation of an active or pending export job."""
    user_identity = get_current_user(request, x_remote_user)
    job_service = get_job_service()
    return job_service.cancel_job(job_id, requested_by=user_identity)


@router.get("/jobs/{job_id}/download")
def download_export_file(
    job_id: str,
    request: Request,
    x_remote_user: str | None = Header(default=None),
):
    """
    Securely download completed Excel export file.
    Physical disk paths are NEVER exposed to the client.
    """
    job_service = get_job_service()
    raw_job = job_service.get_job_raw(job_id)

    if not raw_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export job '{job_id}' not found.",
        )

    if raw_job["status"] != "Completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Export file is not available (Current status: {raw_job['status']}).",
        )

    file_path_str = raw_job.get("file_path")
    if not file_path_str or not os.path.exists(file_path_str):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Export file has expired or was removed from storage.",
        )

    file_path = Path(file_path_str)
    safe_title = "".join(c for c in raw_job["report_title"] if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
    download_filename = f"{safe_title}.xlsx"

    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=download_filename,
    )

