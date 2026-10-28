import logging
import re
import time
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, get_or_create_invite_code, sms_auth
from app.db.session import get_db
from app.models.badcase import BadCase
from app.models.message import ChatMessage
from app.models.person import Person
from app.models.session import ChatSession
from app.models.transaction import Transaction
from app.models.user import User
from app.models.content_unlock import ContentUnlock
from app.models.report import Report
from app.models.subscription import Subscription
from app.models.usage_counter import UsageCounter
from app.models.persona import Persona
from app.models.persona_conversation import PersonaConversation
from app.models.persona_message import PersonaMessage
from app.models.persona_memory import PersonaMemory
from app.models.safety_event import SafetyEvent
from app.services.payment_service import get_transactions

router = APIRouter(prefix="/api/user", tags=["user"])
logger = logging.getLogger(__name__)

_MOBILE_RE = re.compile(r"^1\d{10}$")


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
        "phone": current_user.phone,
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
        "phone": current_user.phone,
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


class DeleteAccountRequest(BaseModel):
    code: Optional[str] = None  # 短信验证码（手机号账号必填，微信临时账号免验）


@router.post("/delete-account")
async def delete_account(
    request: DeleteAccountRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """账号注销：短信验证身份后，删除全部个人数据并匿名化账号。

    - 直接删除：档案、两套对话、报告、人格记忆、安全事件、订阅和用量
    - 解除关联：badcases.person_id 置空（质量改进记录保留但不可回溯到个人）
    - 匿名保留：transactions/orders/ai_usage_logs（财务/用量依法保留，主体变为匿名账号）
    - users 行匿名化：手机号/微信openid/邮箱/昵称/邀请关系/积分全部清除，
      保留行本身以维持财务流水完整性，注销后原手机号可重新注册。
    """
    phone = current_user.phone or ""

    # 1. 身份验证：真实手机号账号必须校验短信验证码
    if _MOBILE_RE.match(phone):
        code = (request.code or "").strip()
        if not code:
            raise HTTPException(status_code=400, detail="请输入短信验证码")
        result = await sms_auth.execute(action="verify_code", phone=phone, code=code)
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)

    # 2. 收集该用户全部人物/会话 ID
    person_ids = list(
        (await db.execute(select(Person.id).where(Person.user_id == current_user.id))).scalars()
    )
    session_ids: list[int] = []
    if person_ids:
        session_ids = list(
            (
                await db.execute(
                    select(ChatSession.id).where(ChatSession.person_id.in_(person_ids))
                )
            ).scalars()
        )

    # 3. 删除 V3 人格、报告、权益数据（先子表后主体）
    await db.execute(
        delete(PersonaMessage).where(PersonaMessage.user_id == current_user.id)
    )
    await db.execute(
        delete(PersonaMemory).where(PersonaMemory.user_id == current_user.id)
    )
    await db.execute(
        delete(PersonaConversation).where(
            PersonaConversation.user_id == current_user.id
        )
    )
    await db.execute(delete(SafetyEvent).where(SafetyEvent.user_id == current_user.id))
    await db.execute(delete(Persona).where(Persona.user_id == current_user.id))
    await db.execute(delete(Report).where(Report.user_id == current_user.id))
    await db.execute(delete(UsageCounter).where(UsageCounter.user_id == current_user.id))
    await db.execute(delete(Subscription).where(Subscription.user_id == current_user.id))
    await db.execute(delete(ContentUnlock).where(ContentUnlock.user_id == current_user.id))

    # 4. 删除旧解盘消息 → 会话 → 人物（顺序解除逻辑归属）
    if session_ids:
        await db.execute(delete(ChatMessage).where(ChatMessage.session_id.in_(session_ids)))
    if person_ids:
        await db.execute(delete(ChatSession).where(ChatSession.person_id.in_(person_ids)))
        await db.execute(delete(Person).where(Person.user_id == current_user.id))
        # 质量记录解除人物关联，问题文本不含直接身份信息，保留用于规则改进
        await db.execute(
            update(BadCase).where(BadCase.person_id.in_(person_ids)).values(person_id=None)
        )

    # 5. 清洗他人（邀请人）流水中残留的本人脱敏手机号
    if _MOBILE_RE.match(phone):
        masked_phone = f"{phone[:3]}****{phone[-4:]}"
        linked_txs = (
            await db.execute(
                select(Transaction).where(
                    Transaction.biz_type == "share_reward",
                    Transaction.description.like(f"%{masked_phone}%"),
                )
            )
        ).scalars()
        for tx in linked_txs:
            tx.description = tx.description.replace(masked_phone, "已注销用户")

    # 6. 账号匿名化（墓碑行：id 保留供财务流水关联，身份字段全部清除）
    current_user.phone = f"deleted_{current_user.id}_{int(time.time())}"
    current_user.email = None
    current_user.hashed_password = None
    current_user.name = "已注销用户"
    current_user.avatar = None
    current_user.wechat_openid = None
    current_user.invite_code = None
    current_user.inviter_id = None
    current_user.points = 0

    await db.commit()
    logger.info(f"[ACCOUNT] 用户#{current_user.id} 已注销并匿名化（手机尾号 {phone[-4:] if len(phone) >= 4 else '?'}）")
    return {"message": "账号已注销"}
