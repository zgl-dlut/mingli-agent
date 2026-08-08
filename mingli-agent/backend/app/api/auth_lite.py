"""
轻量版认证路由 - 微信 OAuth 登录（无数据库依赖）
"""
import logging
import time
import httpx
import jwt
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth-lite"])

# 内存存储用户（生产环境应替换为数据库）
_users: dict = {}  # openid -> {"phone": ..., "created_at": ...}


class WechatCallbackRequest(BaseModel):
    code: str


@router.get("/wechat-login-url")
async def get_wechat_login_url(redirect_uri: str = ""):
    """
    生成微信 OAuth2.0 授权 URL（snsapi_userinfo）
    前端跳转到此 URL，用户授权后微信会回调 redirect_uri?code=xxx
    """
    if not settings.WECHAT_APP_ID:
        raise HTTPException(status_code=503, detail="微信 APP_ID 未配置")

    if not redirect_uri:
        redirect_uri = "http://localhost:5173/login"

    url = (
        f"https://open.weixin.qq.com/connect/oauth2/authorize"
        f"?appid={settings.WECHAT_APP_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=snsapi_userinfo"
        f"&state=mingli#wechat_redirect"
    )
    return {"url": url}


@router.post("/wechat-login")
async def wechat_login(body: WechatCallbackRequest):
    """
    用微信授权 code 换取用户信息，返回 JWT token
    """
    if not settings.WECHAT_APP_ID:
        raise HTTPException(status_code=503, detail="微信 APP_ID 未配置")

    # 1. 用 code 换取 access_token + openid
    try:
        async with httpx.AsyncClient() as client:
            token_res = await client.get(
                "https://api.weixin.qq.com/sns/oauth2/access_token",
                params={
                    "appid": settings.WECHAT_APP_ID,
                    "secret": settings.WECHAT_API_KEY,
                    "code": body.code,
                    "grant_type": "authorization_code",
                },
            )
            token_data = token_res.json()
    except Exception as e:
        logger.error(f"微信 token 交换失败: {e}")
        raise HTTPException(status_code=500, detail="微信授权失败")

    openid = token_data.get("openid")
    if not openid:
        raise HTTPException(status_code=400, detail="无效的授权码")

    # 2. 获取用户信息（可选）
    access_token = token_data.get("access_token")
    nickname = ""
    if access_token:
        try:
            async with httpx.AsyncClient() as client:
                user_res = await client.get(
                    "https://api.weixin.qq.com/sns/userinfo",
                    params={"access_token": access_token, "openid": openid, "lang": "zh_CN"},
                )
                user_data = user_res.json()
                nickname = user_data.get("nickname", "")
        except Exception:
            pass

    # 3. 创建或查找用户
    if openid not in _users:
        _users[openid] = {
            "openid": openid,
            "nickname": nickname,
            "created_at": time.time(),
        }

    user = _users[openid]

    # 4. 生成 JWT
    expire = int(time.time()) + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    payload = {
        "sub": openid,
        "nickname": nickname,
        "exp": expire,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return {
        "token": token,
        "user": {
            "openid": openid,
            "nickname": nickname,
        },
    }
