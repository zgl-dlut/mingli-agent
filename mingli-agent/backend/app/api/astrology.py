from pydantic import BaseModel
from fastapi import APIRouter

from app.services.astrology_service import calculate_astrology

router = APIRouter(prefix="/api/astrology", tags=["astrology"])


class AstrologyRequest(BaseModel):
    birth_date: str
    birth_time: str
    latitude: float
    longitude: float


@router.post("/calculate")
async def calculate_astrology_endpoint(request: AstrologyRequest):
    chart = calculate_astrology(
        birth_date=request.birth_date,
        birth_time=request.birth_time,
        latitude=request.latitude,
        longitude=request.longitude,
    )
    return chart.model_dump()
