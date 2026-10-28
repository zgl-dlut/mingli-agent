from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel


class UsageAllowance(BaseModel):
    limit: Optional[int]
    used: int
    remaining: Optional[int]


class EntitlementSnapshot(BaseModel):
    plan_code: str
    status: str
    expires_at: Optional[datetime]
    profile: UsageAllowance
    qa_daily: UsageAllowance
    persona_session_monthly: UsageAllowance
    persona_turn_limit: int
    report_access: Dict[str, bool]


class UsageResult(BaseModel):
    metric: str
    period_key: str
    used: int
    limit: Optional[int]
    remaining: Optional[int]


class PlanDefinition(BaseModel):
    plan_code: str
    name: str
    monthly_price_yuan: int
    annual_price_yuan: int
    profile_limit: Optional[int]
    qa_daily_limit: Optional[int]
    persona_session_monthly_limit: Optional[int]
    persona_turn_limit: int
    report_access: Dict[str, bool]
    highlights: List[str]
