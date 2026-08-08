from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.user import User

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/profile")
async def get_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await db.refresh(current_user)

    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "avatar": current_user.avatar,
        "points": current_user.points,
        "created_at": current_user.created_at.isoformat(),
    }


class RechargeRequest(BaseModel):
    points: int


@router.post("/recharge")
async def recharge(
    request: RechargeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """充值积分（直接到账，用于测试/模拟支付场景）"""
    if request.points <= 0 or request.points > 10000:
        return {"error": "积分数量无效"}
    current_user.points += request.points
    await db.commit()
    await db.refresh(current_user)
    return {"points": current_user.points, "message": f"充值{request.points}积分成功"}
