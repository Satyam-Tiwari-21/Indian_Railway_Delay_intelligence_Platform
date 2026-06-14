# app/services/report_service.py

import csv
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.db.report import Report
from app.models.schemas.report import ReportOut
from app.services.auth_service import log_audit

logger = get_logger(__name__)

REPORTS_DIR = Path("reports")


def _ensure_reports_dir() -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR


def _to_out(report: Report, base_url: str = "") -> ReportOut:
    download_url = (
        f"{base_url}/api/v1/reports/{report.id}/download"
        if report.file_path else None
    )
    return ReportOut(
        id=report.id,
        title=report.title,
        report_type=report.report_type,
        file_format=report.file_format,
        file_size_bytes=report.file_size_bytes,
        parameters=report.parameters,
        generated_by=report.generated_by,
        created_at=report.created_at,
        expires_at=report.expires_at,
        download_url=download_url,
    )


# ── CSV Report ─────────────────────────────────────────────────

def generate_csv(
    db: Session,
    title: str,
    parameters: Optional[dict],
    user_id: str,
) -> ReportOut:
    """
    Generate a CSV of delay records filtered by parameters.
    Saved to /reports/ directory and registered in DB.
    """
    from app.models.db.delay_record import DelayRecord
    from app.models.db.train import Train
    from app.models.db.station import Station

    reports_dir = _ensure_reports_dir()
    filename = f"delay_report_{uuid.uuid4().hex[:8]}.csv"
    filepath = reports_dir / filename

    # Build query from parameters
    stmt = (
        select(
            DelayRecord.journey_date,
            Train.train_number,
            Train.name.label("train_name"),
            Train.category,
            Train.zone,
            Station.station_code,
            Station.name.label("station_name"),
            DelayRecord.arrival_delay_minutes,
            DelayRecord.departure_delay_minutes,
            DelayRecord.reason_code,
            DelayRecord.weather_condition,
        )
        .join(Train, DelayRecord.train_id == Train.id)
        .join(Station, DelayRecord.station_id == Station.id)
        .where(DelayRecord.is_cancelled == False)
        .order_by(DelayRecord.journey_date.desc())
        .limit(10_000)      # Cap at 10K rows per export
    )

    if parameters:
        if z := parameters.get("zone"):
            stmt = stmt.where(Train.zone == z)
        if cat := parameters.get("category"):
            stmt = stmt.where(Train.category == cat)
        if sd := parameters.get("start_date"):
            from datetime import date as date_type
            stmt = stmt.where(DelayRecord.journey_date >= sd)
        if ed := parameters.get("end_date"):
            stmt = stmt.where(DelayRecord.journey_date <= ed)

    rows = db.execute(stmt).all()

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Journey Date", "Train Number", "Train Name", "Category", "Zone",
            "Station Code", "Station Name",
            "Arrival Delay (min)", "Departure Delay (min)",
            "Reason Code", "Weather",
        ])
        for row in rows:
            writer.writerow([
                row.journey_date, row.train_number, row.train_name,
                row.category, row.zone, row.station_code, row.station_name,
                row.arrival_delay_minutes, row.departure_delay_minutes,
                row.reason_code, row.weather_condition,
            ])

    file_size = os.path.getsize(filepath)

    report = Report(
        id=str(uuid.uuid4()),
        title=title,
        report_type="DELAY_RECORDS",
        file_path=str(filepath),
        file_format="CSV",
        file_size_bytes=file_size,
        parameters=parameters,
        generated_by=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(report)
    db.flush()

    log_audit(
        db=db, action="EXPORT_CSV", user_id=user_id,
        resource_type="report", resource_id=report.id,
        response_status=200,
    )

    logger.info("CSV report generated", report_id=report.id, rows=len(rows), file=filename)
    return _to_out(report)


# ── PDF Report ─────────────────────────────────────────────────

def generate_pdf(
    db: Session,
    title: str,
    parameters: Optional[dict],
    user_id: str,
) -> ReportOut:
    """
    Generate a PDF summary report using ReportLab.
    Includes KPI table + top delayed routes.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.units import mm
    except ImportError:
        raise RuntimeError(
            "reportlab is not installed. Run: pip install reportlab"
        )

    reports_dir = _ensure_reports_dir()
    filename = f"report_{uuid.uuid4().hex[:8]}.pdf"
    filepath = reports_dir / filename

    doc = SimpleDocTemplate(str(filepath), pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Title
    story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%d %b %Y %H:%M')} | "
        f"India Railways Delay Intelligence Platform",
        styles["Normal"],
    ))
    story.append(Spacer(1, 10 * mm))

    # Parameters table
    if parameters:
        story.append(Paragraph("<b>Report Parameters</b>", styles["Heading2"]))
        param_data = [["Parameter", "Value"]] + [
            [k.replace("_", " ").title(), str(v)] for k, v in parameters.items()
        ]
        param_table = Table(param_data, colWidths=[80 * mm, 100 * mm])
        param_table.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#003580")),
            ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID",        (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ]))
        story.append(param_table)
        story.append(Spacer(1, 8 * mm))

    # KPI summary
    from app.services.analytics_service import get_overview
    from datetime import date as date_type
    overview = get_overview(db)
    story.append(Paragraph("<b>Network KPIs</b>", styles["Heading2"]))
    kpi_data = [
        ["Metric", "Value"],
        ["Total Active Trains",    str(overview.total_active_trains)],
        ["Average Delay (min)",    f"{overview.avg_delay_minutes:.1f}"],
        ["On-Time Performance",    f"{overview.otp_percentage:.1f}%"],
        ["Records Analysed",       f"{overview.total_records_analysed:,}"],
        ["Open Anomalies",         str(overview.open_anomalies)],
        ["Worst Zone",             overview.worst_zone or "N/A"],
    ]
    kpi_table = Table(kpi_data, colWidths=[100 * mm, 80 * mm])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#FF6B00")),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FFF3E0")]),
    ]))
    story.append(kpi_table)

    doc.build(story)
    file_size = os.path.getsize(filepath)

    report = Report(
        id=str(uuid.uuid4()),
        title=title,
        report_type="EXECUTIVE_MONTHLY",
        file_path=str(filepath),
        file_format="PDF",
        file_size_bytes=file_size,
        parameters=parameters,
        generated_by=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(report)
    db.flush()

    log_audit(
        db=db, action="EXPORT_PDF", user_id=user_id,
        resource_type="report", resource_id=report.id,
        response_status=200,
    )

    logger.info("PDF report generated", report_id=report.id, file=filename)
    return _to_out(report)


# ── Fetch ──────────────────────────────────────────────────────

def get_user_reports(db: Session, user_id: str, limit: int = 20) -> list[ReportOut]:
    """List the most recent reports for a user."""
    from sqlalchemy import desc
    rows = db.scalars(
        select(Report)
        .where(Report.generated_by == user_id)
        .order_by(desc(Report.created_at))
        .limit(limit)
    ).all()
    return [_to_out(r) for r in rows]


def get_report_path(db: Session, report_id: str, user_id: str) -> str:
    """Return the file path for download. Raises ValueError if not found/unauthorised."""
    report = db.get(Report, report_id)
    if report is None:
        raise ValueError(f"Report {report_id} not found")
    if report.generated_by != user_id:
        raise PermissionError("You can only download your own reports")
    if not report.file_path or not Path(report.file_path).exists():
        raise ValueError("Report file no longer exists")
    if report.is_expired:
        raise ValueError("Report has expired. Please generate a new one.")
    return report.file_path