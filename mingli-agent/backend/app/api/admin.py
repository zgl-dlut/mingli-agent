"""
管理后台 API - AI 用量记录 / 充值订单（仅查看）/ 管理员充值
访问控制由 nginx BasicAuth（admin.shisuansuan.com）保障，与反馈后台一致
"""
import logging
import re
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError
from app.db.session import get_db
from app.models.order import Order
from app.models.usage_log import AiUsageLog
from app.models.user import User
from app.services import payment_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/usage-logs")
async def list_usage_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    biz_type: Optional[str] = None,
    success: Optional[bool] = None,
    user_id: Optional[int] = None,
):
    """AI 用量记录：每次首次报告/追问的字数、token、模型、成败、用时"""
    conditions = []
    if biz_type:
        conditions.append(AiUsageLog.biz_type == biz_type)
    if success is not None:
        conditions.append(AiUsageLog.success == success)
    if user_id is not None:
        conditions.append(AiUsageLog.user_id == user_id)

    total = (
        await db.execute(select(func.count()).select_from(AiUsageLog).where(*conditions))
    ).scalar() or 0

    rows = (
        await db.execute(
            select(AiUsageLog, User.name)
            .join(User, User.id == AiUsageLog.user_id, isouter=True)
            .where(*conditions)
            .order_by(AiUsageLog.created_at.desc(), AiUsageLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()

    return {
        "total": total,
        "items": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "user_name": name or f"用户{log.user_id}",
                "session_id": log.session_id,
                "biz_type": log.biz_type,
                "input_chars": log.input_chars,
                "input_tokens": log.input_tokens,
                "output_chars": log.output_chars,
                "output_tokens": log.output_tokens,
                "total_tokens": log.total_tokens,
                "cached_tokens": log.cached_tokens,
                "model": log.model,
                "success": log.success,
                "duration_ms": log.duration_ms,
                "created_at": log.created_at.isoformat(),
            }
            for log, name in rows
        ],
    }


@router.get("/orders")
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    user_id: Optional[int] = None,
):
    """充值订单记录（微信支付相关）"""
    conditions = []
    if status:
        conditions.append(Order.status == status)
    if user_id is not None:
        conditions.append(Order.user_id == user_id)

    total = (
        await db.execute(select(func.count()).select_from(Order).where(*conditions))
    ).scalar() or 0

    rows = (
        await db.execute(
            select(Order, User.name)
            .join(User, User.id == Order.user_id, isouter=True)
            .where(*conditions)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()

    return {
        "total": total,
        "items": [
            {
                "id": o.id,
                "user_id": o.user_id,
                "user_name": name or f"用户{o.user_id}",
                "points": o.points,
                "amount": o.amount,
                "pay_method": o.pay_method,
                "status": o.status,
                "trade_no": o.trade_no,
                "created_at": o.created_at.isoformat(),
                "paid_at": o.paid_at.isoformat() if o.paid_at else None,
            }
            for o, name in rows
        ],
    }


class RechargeByPhoneRequest(BaseModel):
    phone: str
    points: int
    remark: str = ""


@router.post("/recharge-by-phone")
async def recharge_by_phone(
    body: RechargeByPhoneRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """管理员通过手机号给用户充值积分"""
    # 手机号格式校验
    if not re.match(r"^1[3-9]\d{9}$", body.phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")
    if body.points < 1 or body.points > 100000:
        raise HTTPException(status_code=400, detail="充值积分需在 1~100000 之间")

    try:
        result = await payment_service.admin_recharge_points(
            db, body.phone, body.points, body.remark
        )
        logger.info(
            f"[admin] 管理员充值 phone={body.phone} points={body.points} user_id={result['user_id']}"
        )
        return result
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[admin] 充值失败: {e}")
        raise HTTPException(status_code=500, detail="充值失败，请稍后重试")
