"""微信 JS-SDK 签名服务：全局 access_token / jsapi_ticket 缓存 + wx.config 签名。

用途：公众号网页内调用微信原生能力（当前为语音转文字 translateVoice）。
注意：这里的 access_token 是 cgi-bin 全局 token，与 OAuth 用户级 token 互不相干；
     单进程内存缓存即可（后端单容器部署，ticket 有效期 7200 秒）。
"""
import hashlib
import random
import string
import time

import httpx

from app.config import settings

_access_token: dict = {"value": None, "expires_at": 0.0}
_jsapi_ticket: dict = {"value": None, "expires_at": 0.0}


async def _fetch_json(url: str, params: dict) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(url, params=params)
        return res.json()


async def get_access_token() -> str:
    """获取公众号全局 access_token，提前 5 分钟过期以避免边界失效"""
    if _access_token["value"] and time.time() < _access_token["expires_at"]:
        return _access_token["value"]
    data = await _fetch_json(
        "https://api.weixin.qq.com/cgi-bin/token",
        {
            "grant_type": "client_credential",
            "appid": settings.WECHAT_APP_ID,
            "secret": settings.WECHAT_APP_SECRET,
        },
    )
    if "access_token" not in data:
        raise RuntimeError(f"获取微信 access_token 失败: {data}")
    _access_token["value"] = data["access_token"]
    _access_token["expires_at"] = time.time() + data.get("expires_in", 7200) - 300
    return _access_token["value"]


async def get_jsapi_ticket() -> str:
    if _jsapi_ticket["value"] and time.time() < _jsapi_ticket["expires_at"]:
        return _jsapi_ticket["value"]
    token = await get_access_token()
    data = await _fetch_json(
        "https://api.weixin.qq.com/cgi-bin/ticket/getticket",
        {"access_token": token, "type": "jsapi"},
    )
    if data.get("errcode") != 0:
        raise RuntimeError(f"获取 jsapi_ticket 失败: {data}")
    _jsapi_ticket["value"] = data["ticket"]
    _jsapi_ticket["expires_at"] = time.time() + data.get("expires_in", 7200) - 300
    return _jsapi_ticket["value"]


async def build_jssdk_signature(url: str) -> dict:
    """按微信官方算法生成 wx.config 所需参数。

    url 必须与前端调用 wx.config 时页面 URL 完全一致（不含 #hash 部分）。
    """
    ticket = await get_jsapi_ticket()
    noncestr = "".join(random.choices(string.ascii_letters + string.digits, k=16))
    timestamp = str(int(time.time()))
    raw = f"jsapi_ticket={ticket}&noncestr={noncestr}&timestamp={timestamp}&url={url}"
    signature = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return {
        "appId": settings.WECHAT_APP_ID,
        "timestamp": timestamp,
        "nonceStr": noncestr,
        "signature": signature,
    }
