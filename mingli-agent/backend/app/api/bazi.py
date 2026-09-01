from pydantic import BaseModel, field_validator
from fastapi import APIRouter

from app.services.bazi_service import calculate_bazi, normalize_gender
from app.skills.orchestrator import generate_full_analysis

router = APIRouter(prefix="/api/bazi", tags=["bazi"])


class BaziRequest(BaseModel):
    birth_date: str
    birth_time: str
    longitude: float
    gender: str

    @field_validator("gender")
    @classmethod
    def _normalize_gender(cls, v: str) -> str:
        """性别归一化为英文 male/female，兼容中文/数字"""
        return normalize_gender(v)


@router.post("/calculate")
async def calculate_bazi_endpoint(request: BaziRequest):
    chart = calculate_bazi(
        birth_date=request.birth_date,
        birth_time=request.birth_time,
        longitude=request.longitude,
        gender=request.gender,
    )
    return chart.model_dump()


class AnalyzeRequest(BaseModel):
    birth_date: str
    birth_time: str
    longitude: float
    latitude: float
    gender: str
    location: str = ""

    @field_validator("gender")
    @classmethod
    def _normalize_gender(cls, v: str) -> str:
        """性别归一化为英文 male/female，兼容中文/数字"""
        return normalize_gender(v)


@router.post("/analyze")
async def analyze_endpoint(request: AnalyzeRequest):
    result = generate_full_analysis(
        birth_date=request.birth_date,
        birth_time=request.birth_time,
        longitude=request.longitude,
        latitude=request.latitude,
        gender=request.gender,
        location=request.location,
    )
    return result
