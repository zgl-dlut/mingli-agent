"""
认证 API - 手机号验证码登录
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.skills.auth.sms_auth_skill import SmsAuthSkill
from app.skills.security.security_skill import SecuritySkill
from app.skills import registry

router = APIRouter(prefix="/api/auth", tags=["认证"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

sms_auth = SmsAuthSkill()
security = SecuritySkill()


class SendSmsRequest(BaseModel):
    phone: str


class VerifySmsRequest(BaseModel):
    phone: str
    code: str


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
    
    # 3. 生成 Token
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


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    """获取当前用户（从 JWT Token 解析）"""
    from jose import jwt, JWTError
    from app.config import settings
    
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


