from datetime import datetime
import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.report_schema import FollowupReport


ReportType = Literal[
    "base_report",
    "monthly_brief",
    "annual_brief",
    "relation_report",
    "qa_reading",
]
ReportStatus = Literal["pending", "generating", "ready", "failed"]


class ReportContent(FollowupReport):
    payload: Dict[str, Any] = Field(default_factory=dict)


class ReportCreateRequest(BaseModel):
    report_type: ReportType
    primary_person_id: int
    secondary_person_id: Optional[int] = None
    period_key: Optional[str] = None

    @model_validator(mode="after")
    def validate_identity_fields(self):
        if self.report_type == "monthly_brief":
            if not self.period_key or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", self.period_key):
                raise ValueError("月运 period_key 必须为 YYYY-MM")
        elif self.report_type == "annual_brief":
            if not self.period_key or not re.fullmatch(r"(19|20|21)\d{2}", self.period_key):
                raise ValueError("年报 period_key 必须为 YYYY")
        elif self.report_type == "relation_report":
            if not self.secondary_person_id:
                raise ValueError("关系报告必须选择第二份档案")
            if self.secondary_person_id == self.primary_person_id:
                raise ValueError("关系报告需要两份不同档案")
        elif self.report_type == "qa_reading":
            raise ValueError("问答解读由解盘对话生成")
        return self


class ReportAccess(BaseModel):
    allowed: bool
    required_plan: Optional[str] = None


class ReportResponse(BaseModel):
    report_id: int
    report_type: ReportType
    status: ReportStatus
    primary_person_id: int
    secondary_person_id: Optional[int] = None
    period_key: Optional[str] = None
    title: str
    preview: Optional[Dict[str, Any]] = None
    content: Optional[Dict[str, Any]] = None
    chart_snapshot: Optional[Dict[str, Any]] = None
    prompt_version: str
    source_message_id: Optional[int] = None
    generated_at: Optional[datetime] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    access: ReportAccess


class ReportListResponse(BaseModel):
    items: List[ReportResponse]
    page: int
    page_size: int
    total: int


class LegacyImportResponse(BaseModel):
    imported: int
    existing: int
    scanned: int
