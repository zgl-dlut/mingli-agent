from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class BirthProfileSnapshot(BaseModel):
    birth_date: str
    birth_time: str
    timezone: str = "Asia/Shanghai"
    gender: str
    location: str
    latitude: float
    longitude: float
    calendar_type: str = "solar"


class PillarSnapshot(BaseModel):
    stem: str = ""
    branch: str = ""


class DayMasterSnapshot(BaseModel):
    stem: str = ""
    element: str = "unknown"
    yin_yang: str = "unknown"


class StrengthSnapshot(BaseModel):
    level: str = "unknown"
    score: float = 0
    source: str = ""


class ChartSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    generated_at: datetime
    birth_profile: BirthProfileSnapshot
    pillars: Dict[str, PillarSnapshot]
    day_master: DayMasterSnapshot
    ten_gods: Dict[str, Any] = Field(default_factory=dict)
    strength: StrengthSnapshot
    useful_elements: List[str] = Field(default_factory=list)
    unfavorable_elements: List[str] = Field(default_factory=list)
    pattern: Dict[str, Any] = Field(default_factory=dict)
    luck_cycles: List[Dict[str, Any]] = Field(default_factory=list)
    annual_cycles: List[Dict[str, Any]] = Field(default_factory=list)
    monthly_cycles: List[Dict[str, Any]] = Field(default_factory=list)
    source_hash: str
