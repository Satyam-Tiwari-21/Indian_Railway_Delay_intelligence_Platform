# app/models/schemas/report.py

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ReportRequest(BaseModel):
    title: str
    report_type: str           # EDA_SUMMARY | PREDICTION_BATCH | ANOMALY_REPORT | EXECUTIVE_MONTHLY
    file_format: str = "PDF"   # PDF | CSV
    parameters: Optional[dict] = None
    # Example parameters:
    # {"zone": "NR", "start_date": "2024-06-01", "end_date": "2024-08-31"}


class ReportOut(BaseModel):
    id: str
    title: str
    report_type: Optional[str]
    file_format: Optional[str]
    file_size_bytes: Optional[int]
    parameters: Optional[dict]
    generated_by: str
    created_at: datetime
    expires_at: Optional[datetime]
    download_url: Optional[str]    # Populated when file is ready

    model_config = {"from_attributes": True}