# app/api/v1/reports.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.db.user import User
from app.models.schemas.report import ReportOut, ReportRequest
import app.services.report_service as svc

router = APIRouter()


@router.post(
    "/generate",
    response_model=ReportOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a CSV or PDF report",
)
def generate_report(
    body: ReportRequest,
    user: User = Depends(require_permission("can_export")),
    db: Session = Depends(get_db),
):
    """
    Generates a report file and registers it in the DB.
    Returns metadata including download_url.
    Supported formats: CSV (fast), PDF (formatted summary).
    """
    try:
        if body.file_format.upper() == "PDF":
            return svc.generate_pdf(db, body.title, body.parameters, str(user.id))
        else:
            return svc.generate_csv(db, body.title, body.parameters, str(user.id))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {exc}",
        )


@router.get(
    "/",
    response_model=list[ReportOut],
    summary="List the current user's generated reports",
)
def list_reports(
    limit: int = 20,
    user: User = Depends(require_permission("can_export")),
    db: Session = Depends(get_db),
):
    return svc.get_user_reports(db, str(user.id), limit=limit)


@router.get(
    "/{report_id}/download",
    summary="Download a generated report file",
)
def download_report(
    report_id: str,
    user: User = Depends(require_permission("can_export")),
    db: Session = Depends(get_db),
):
    """Streams the report file as a download response."""
    try:
        path = svc.get_report_path(db, report_id, str(user.id))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    filename = path.split("/")[-1]
    media_type = "application/pdf" if filename.endswith(".pdf") else "text/csv"
    return FileResponse(path=path, filename=filename, media_type=media_type)