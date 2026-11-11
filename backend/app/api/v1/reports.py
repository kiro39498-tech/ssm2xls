from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from app.api.v1.exports import get_current_user
from app.schemas.reports import (
    CreateReportRequest,
    UpdateDraftVersionRequest,
    NewDraftVersionRequest,
    QueryVersionResponse,
    ReportResponse,
    ReportListResponse,
    AuditLogResponse,
)
from app.services.reports.report_service import get_report_service
from app.services.reports.audit_service import get_audit_service

router = APIRouter(prefix="/reports", tags=["Reports & Versioning"])


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: CreateReportRequest,
    request: Request,
    x_remote_user: str | None = Header(default=None),
) -> ReportResponse:
    """Create a new saved report query and initial Draft v1."""
    user = get_current_user(request, x_remote_user)
    service = get_report_service()
    try:
        return service.create_report(payload, user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("", response_model=ReportListResponse, status_code=status.HTTP_200_OK)
def list_reports(
    search: Optional[str] = Query(None, description="Search by title or description"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ReportListResponse:
    """List saved reports with filtering and pagination."""
    service = get_report_service()
    reports, total = service.list_reports(
        search=search,
        category=category,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return ReportListResponse(reports=reports, total=total)


@router.get("/{query_id}", response_model=ReportResponse, status_code=status.HTTP_200_OK)
def get_report(query_id: str) -> ReportResponse:
    """Get report details and its current active or draft version."""
    service = get_report_service()
    report = service.get_report(query_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{query_id}' not found.",
        )
    return report


@router.put("/versions/{version_id}", response_model=QueryVersionResponse, status_code=status.HTTP_200_OK)
def update_draft_version(
    version_id: str,
    payload: UpdateDraftVersionRequest,
    request: Request,
    x_remote_user: str | None = Header(default=None),
) -> QueryVersionResponse:
    """
    Update a draft version.
    IMMUTABILITY: Approved, Active, or Archived versions cannot be modified in place.
    """
    user = get_current_user(request, x_remote_user)
    service = get_report_service()
    try:
        return service.update_draft_version(version_id, payload, user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{query_id}/new-draft", response_model=QueryVersionResponse, status_code=status.HTTP_201_CREATED)
def clone_to_new_draft(
    query_id: str,
    payload: NewDraftVersionRequest,
    request: Request,
    x_remote_user: str | None = Header(default=None),
) -> QueryVersionResponse:
    """
    Clone an existing approved/active version into a new Draft with an incremented version number.
    Preserves all previous versions intact.
    """
    user = get_current_user(request, x_remote_user)
    service = get_report_service()
    try:
        return service.clone_to_new_draft(
            query_id=query_id,
            from_version_id=payload.from_version_id,
            change_summary=payload.change_summary,
            user=user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/versions/{version_id}/test", response_model=QueryVersionResponse, status_code=status.HTTP_200_OK)
def test_version(
    version_id: str,
    test_summary: str = Query(default="Preview test executed successfully"),
    request: Request = None,
    x_remote_user: str | None = Header(default=None),
) -> QueryVersionResponse:
    """Mark a draft version as Tested."""
    user = get_current_user(request, x_remote_user)
    service = get_report_service()
    try:
        return service.test_version(version_id, test_summary, user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/versions/{version_id}/approve", response_model=QueryVersionResponse, status_code=status.HTTP_200_OK)
def approve_version(
    version_id: str,
    request: Request,
    x_remote_user: str | None = Header(default=None),
) -> QueryVersionResponse:
    """Approve a tested query version. Freezes version from further in-place edits."""
    user = get_current_user(request, x_remote_user)
    service = get_report_service()
    try:
        return service.approve_version(version_id, user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/versions/{version_id}/activate", response_model=QueryVersionResponse, status_code=status.HTTP_200_OK)
def activate_version(
    version_id: str,
    request: Request,
    x_remote_user: str | None = Header(default=None),
) -> QueryVersionResponse:
    """
    Activate an approved query version for production reports.
    Archives previous active version and updates the current active version pointer.
    """
    user = get_current_user(request, x_remote_user)
    service = get_report_service()
    try:
        return service.activate_version(version_id, user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{query_id}/toggle-active", response_model=ReportResponse, status_code=status.HTTP_200_OK)
def toggle_report_active(
    query_id: str,
    is_active: bool = Query(...),
) -> ReportResponse:
    """Enable or disable an entire report."""
    service = get_report_service()
    try:
        return service.toggle_report_active(query_id, is_active)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{query_id}/versions", response_model=List[QueryVersionResponse], status_code=status.HTTP_200_OK)
def list_report_versions(query_id: str) -> List[QueryVersionResponse]:
    """Retrieve full version history for a query ordered by version number descending."""
    service = get_report_service()
    return service.list_versions(query_id)


@router.get("/{query_id}/audit", response_model=List[AuditLogResponse], status_code=status.HTTP_200_OK)
def get_report_audit_history(
    query_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> List[AuditLogResponse]:
    """Retrieve execution audit logs specifically for this report."""
    audit_service = get_audit_service()
    logs, _ = audit_service.list_logs(query_id=query_id, limit=limit, offset=offset)
    return logs


@router.get("/audit/all", response_model=List[AuditLogResponse], status_code=status.HTTP_200_OK)
def get_global_audit_trail(
    user: Optional[str] = Query(None, description="Filter by executing user"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> List[AuditLogResponse]:
    """Retrieve system-wide execution audit logs."""
    audit_service = get_audit_service()
    logs, _ = audit_service.list_logs(executed_by=user, limit=limit, offset=offset)
    return logs

