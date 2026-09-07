from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, get_or_create_invite_code
from app.db.session import get_db
from app.models.user import User
from app.services.payment_service import get_transactions

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/invite-code")
async def get_invite_code(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取当前用户专属邀请码（懒生成，首次打开分享弹窗时创建）"""
    code = await get_or_create_invite_code(db, current_user)
    return {"invite_code": code}


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


class UpdateProfileRequest(BaseModel):
    name: str


@router.put("/profile")
async def update_profile(
    request: UpdateProfileRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """修改昵称（1-20 字符）"""
    name = (request.name or "").strip()
    if not name or len(name) > 20:
        raise HTTPException(status_code=400, detail="昵称需为 1-20 个字符")
    current_user.name = name
    await db.commit()
    await db.refresh(current_user)
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "avatar": current_user.avatar,
        "points": current_user.points,
        "created_at": current_user.created_at.isoformat(),
    }


@router.get("/transactions")
async def list_transactions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 100,
):
    """当前用户积分明细（充值/消耗流水，时间倒序）"""
    limit = max(1, min(limit, 200))
    transactions = await get_transactions(db, current_user.id, limit=limit)
    return {
        "items": [
            {
                "id": t.id,
                "type": t.type,
                "points": t.points,
                "biz_type": t.biz_type,
                "order_id": t.order_id,
                "description": t.description,
                "created_at": t.created_at.isoformat(),
            }
            for t in transactions
        ]
    }
