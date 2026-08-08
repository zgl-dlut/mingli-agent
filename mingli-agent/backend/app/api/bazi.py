from pydantic import BaseModel
from fastapi import APIRouter

from app.services.bazi_service import calculate_bazi
from app.skills.orchestrator import generate_full_analysis

router = APIRouter(prefix="/api/bazi", tags=["bazi"])


class BaziRequest(BaseModel):
    birth_date: str
    birth_time: str
    longitude: float
    gender: str


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
