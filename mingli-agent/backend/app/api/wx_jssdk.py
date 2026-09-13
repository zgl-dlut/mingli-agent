"""微信 JS-SDK 签名接口：前端 wx.config 前获取签名（语音提问等功能用）"""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.auth import get_current_user
from app.config import settings
from app.services.wx_jssdk import build_jssdk_signature

router = APIRouter(prefix="/api/wechat", tags=["wechat"])


@router.get("/jssdk-sign")
async def jssdk_sign(
    url: str = Query(..., description="当前页面完整URL（不含#hash）"),
    current_user=Depends(get_current_user),
):
    if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
        raise HTTPException(status_code=503, detail="微信配置未就绪")
    if not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="url 必须是 https 完整地址")
    try:
        return await build_jssdk_signature(url)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"微信签名服务暂不可用: {e}")
