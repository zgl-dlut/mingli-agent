"""
认证 API - 手机号验证码登录 + 微信 OAuth
"""
import logging
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.models.transaction import Transaction
from app.skills.auth.sms_auth_skill import SmsAuthSkill
from app.skills.security.security_skill import SecuritySkill
from app.skills import registry
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["认证"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

sms_auth = SmsAuthSkill()
security = SecuritySkill()


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    """获取当前用户（从 JWT Token 解析）"""
    from jose import jwt, JWTError

    credentials_exception = HTTPException(status_code=401, detail="无效的认证凭据")

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


class SendSmsRequest(BaseModel):
    phone: str


class VerifySmsRequest(BaseModel):
    phone: str
    code: str
    ref: int | None = None  # 邀请人用户ID（分享链接 ?ref= 带来）


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    phone: str
    name: str
    points: int


@router.post("/send-sms")
async def send_sms_code(request: SendSmsRequest):
    """发送短信验证码"""
    result = await sms_auth.execute(action="send_code", phone=request.phone)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return result.data


async def grant_new_user_bonus(db: AsyncSession, user: User) -> None:
    """新注册用户自动赠送免费体验积分（1次报告+2次追问）"""
    bonus = settings.NEW_USER_BONUS_POINTS
    if bonus <= 0:
        return
    user.points += bonus
    db.add(Transaction(
        user_id=user.id,
        type="bonus",
        points=bonus,
        description=f"新用户赠送{bonus}积分（1次报告+2次追问）",
        biz_type="new_user_bonus",
    ))
    await db.commit()
    logger.info(f"[AUTH] 新用户 {user.phone} 自动赠送 {bonus} 积分")


async def grant_share_reward(db: AsyncSession, inviter_id: int | None, new_user: User) -> None:
    """分享赚积分：新用户通过邀请链接注册后，给邀请人发放奖励积分。

    仅在新用户创建分支调用（老用户登录天然不触发，每个新用户只发一次）。
    任何异常都不阻断注册主流程。
    """
    if not inviter_id or not isinstance(inviter_id, int) or inviter_id <= 0:
        return
    try:
        if inviter_id == new_user.id:
            return  # 自我邀请防护（理论上不可能，双保险）
        inviter = (await db.execute(select(User).where(User.id == inviter_id))).scalar_one_or_none()
        if inviter is None:
            logger.warning(f"[SHARE] 邀请人 user#{inviter_id} 不存在，跳过分享奖励（新用户 {new_user.phone}）")
            return
        reward = settings.SHARE_REWARD_POINTS
        if reward <= 0:
            return
        inviter.points += reward
        masked_phone = f"{new_user.phone[:3]}****{new_user.phone[-4:]}" if len(new_user.phone) >= 7 else new_user.phone
        db.add(Transaction(
            user_id=inviter.id,
            type="bonus",
            points=reward,
            description=f"分享赚积分：好友{masked_phone}注册奖励",
            biz_type="share_reward",
        ))
        await db.commit()
        logger.info(f"[SHARE] 新用户 {new_user.phone} 由用户#{inviter_id} 邀请，发放 {reward} 积分")
    except Exception as e:
        logger.error(f"[SHARE] 分享奖励发放失败 inviter={inviter_id} new_user={new_user.phone}: {e}", exc_info=True)


@router.post("/login")
async def login_with_sms(request: VerifySmsRequest, db: AsyncSession = Depends(get_db)):
    """验证码登录（自动注册）"""
    # 1. 验证验证码
    result = await sms_auth.execute(action="verify_code", phone=request.phone, code=request.code)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    # 2. 查找或创建用户
    stmt = select(User).where(User.phone == request.phone)
    user = (await db.execute(stmt)).scalar_one_or_none()
    
    if user is None:
        # 自动注册
        user = User(phone=request.phone, name=f"用户{request.phone[-4:]}")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        # 新用户自动赠送免费体验积分
        await grant_new_user_bonus(db, user)
        # 分享赚积分：记录邀请人并发放奖励（仅新用户注册触发，老用户登录忽略）
        if request.ref and isinstance(request.ref, int) and request.ref > 0:
            user.inviter_id = request.ref
            await db.commit()
            await grant_share_reward(db, request.ref, user)
    
    # 3. 白名单手机号赠送积分（从数据库查询，持久化存储）
    from app.models.bonus_phone import BonusPhone
    bonus_record_check = await db.execute(
        select(BonusPhone).where(BonusPhone.phone == request.phone)
    )
    bonus_phone = bonus_record_check.scalar_one_or_none()
    
    if bonus_phone:
        # 检查是否已经赠送过（查询 biz_type='bonus' 的流水）
        bonus_stmt = select(Transaction).where(
            Transaction.user_id == user.id,
            Transaction.biz_type == "bonus"
        )
        bonus_tx = (await db.execute(bonus_stmt)).scalar_one_or_none()
        
        if bonus_tx is None:
            # 首次赠送：增加积分并记录流水
            user.points += bonus_phone.points
            transaction = Transaction(
                user_id=user.id,
                type="bonus",
                points=bonus_phone.points,
                description=f"内测用户赠送{bonus_phone.points}积分",
                biz_type="bonus"
            )
            db.add(transaction)
            await db.commit()
            logger.info(f"[AUTH] 内测用户 {request.phone} 赠送 {bonus_phone.points} 积分")
    
    # 4. 生成 Token
    token_result = await security.execute(
        action="create_token",
        data={"sub": user.phone, "id": user.id}
    )
    
    return TokenResponse(
        access_token=token_result.data["token"],
        user_id=user.id,
        phone=user.phone,
        name=user.name,
        points=user.points,
    )


@router.post("/refresh")
async def refresh_token(user_id: int):
    """刷新 Token"""
    result = await security.execute(action="create_token", data={"sub": str(user_id), "id": user_id})
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return {"access_token": result.data["token"], "token_type": "bearer"}


@router.get("/my-openid")
async def get_my_openid(current_user: User = Depends(get_current_user)):
    """获取当前用户的微信 openid"""
    return {"openid": current_user.wechat_openid}


@router.get("/wechat-oauth-url")
async def get_wechat_oauth_url(request: Request, current_user: User = Depends(get_current_user)):
    """获取微信 OAuth 授权 URL（用于 JSAPI 支付前获取 openid）"""
    if not settings.WECHAT_APP_ID or not settings.WECHAT_OAUTH_REDIRECT_URI or not settings.WECHAT_APP_SECRET:
        logger.error(
            f"[wechat-oauth] OAuth 配置不完整: APP_ID={'有' if settings.WECHAT_APP_ID else '无'} "
            f"APP_SECRET={'有' if settings.WECHAT_APP_SECRET else '无'} "
            f"REDIRECT_URI={settings.WECHAT_OAUTH_REDIRECT_URI!r}"
        )
        raise HTTPException(status_code=500, detail="微信 OAuth 未配置（缺少公众号AppSecret）")
    # 微信 OAuth 2.0 网页授权
    scope = "snsapi_base"  # 静默授权，只获取 openid
    # 在 state 中携带 user_id，回调时用于绑定 openid 到原用户
    state = f"payment_{current_user.id}"
    oauth_url = (
        f"https://open.weixin.qq.com/connect/oauth2/authorize"
        f"?appid={settings.WECHAT_APP_ID}"
        f"&redirect_uri={quote(settings.WECHAT_OAUTH_REDIRECT_URI, safe='')}"
        f"&response_type=code"
        f"&scope={scope}"
        f"&state={state}"
        f"#wechat_redirect"
    )
    return {"oauth_url": oauth_url}


class AdminLoginRequest(BaseModel):
    username: str
    password: str


@router.post("/admin-login")
async def admin_login(request: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    """管理员登录（用户名密码验证）"""
    # 硬编码管理员账号（生产环境应改为数据库存储）
    ADMIN_USERNAME = "admin"
    ADMIN_PASSWORD = "admin123"

    if request.username != ADMIN_USERNAME or request.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 查找admin用户获取真实ID
    admin_user = (await db.execute(select(User).where(User.phone == ADMIN_USERNAME))).scalar_one_or_none()
    admin_user_id = admin_user.id if admin_user else 0

    # 生成JWT token
    token_result = await security.execute(
        action="create_token",
        data={"sub": ADMIN_USERNAME, "id": admin_user_id, "role": "admin"}
    )

    return {
        "access_token": token_result.data["token"],
        "token_type": "bearer",
        "username": ADMIN_USERNAME,
        "role": "admin",
    }


@router.get("/wechat-callback")
async def wechat_oauth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    """微信 OAuth 回调：用 code 换取 openid，然后生成 JWT token"""
    import httpx

    if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
        logger.error("[wechat-oauth] 微信配置不完整：缺少 WECHAT_APP_SECRET（公众号AppSecret）")
        raise HTTPException(status_code=500, detail="微信配置不完整（缺少公众号AppSecret）")

    # 用 code 换取 openid（注意：必须用公众号AppSecret，不能用支付的APIv3密钥）
    token_url = (
        f"https://api.weixin.qq.com/sns/oauth2/access_token"
        f"?appid={settings.WECHAT_APP_ID}"
        f"&secret={settings.WECHAT_APP_SECRET}"
        f"&code={code}"
        f"&grant_type=authorization_code"
    )

    async with httpx.AsyncClient() as client:
        resp = await client.get(token_url)
        token_data = resp.json()

    if "openid" not in token_data:
        logger.error(f"[wechat-oauth] 获取 openid 失败: {token_data}")
        raise HTTPException(status_code=400, detail="微信授权失败")

    openid = token_data["openid"]
    logger.info(f"[wechat-oauth] 获取 openid 成功: {openid[:8]}...")

    # 从 state 中解析 user_id（格式：payment_{user_id}）
    user_id = None
    if state and state.startswith("payment_"):
        try:
            user_id = int(state.split("_")[1])
        except (IndexError, ValueError):
            pass

    user = None
    # 优先通过 state 中的 user_id 找到原用户并绑定 openid
    if user_id:
        stmt = select(User).where(User.id == user_id)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user:
            user.wechat_openid = openid
            await db.commit()
            logger.info(f"[wechat-oauth] 绑定 openid 到用户 {user_id} 成功")
        else:
            logger.warning(f"[wechat-oauth] state 中的 user_id={user_id} 不存在")

    # 回退：通过 openid 查找已有用户
    if user is None:
        stmt = select(User).where(User.wechat_openid == openid)
        user = (await db.execute(stmt)).scalar_one_or_none()

    # 都没有则创建新用户
    if user is None:
        user = User(phone=f"wx_{openid[:8]}", name=f"微信用户{openid[:4]}", wechat_openid=openid)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        # 新用户自动赠送免费体验积分
        await grant_new_user_bonus(db, user)

    # 生成 JWT token
    token_result = await security.execute(
        action="create_token",
        data={"sub": user.phone, "id": user.id}
    )

    # 重定向到充值页面，带上 token
    frontend_url = f"/recharge?token={token_result.data['token']}"
    return RedirectResponse(url=frontend_url, status_code=302)


