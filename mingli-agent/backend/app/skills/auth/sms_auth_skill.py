"""
手机号验证码认证 Skill
支持发送验证码、验证登录、Token 管理
- Mock 模式：固定验证码 111111（开发调试用，SMS_MOCK_MODE=true）
- 真实模式：调用阿里云短信服务发送随机6位验证码（SMS_MOCK_MODE=false）
"""
import random
import json
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.skills import BaseSkill, SkillMetadata, SkillResult
from app.core.security import create_access_token
from app.config import settings


class SmsCodeCache:
    """简单的验证码缓存"""
    _cache: Dict[str, Dict] = {}

    @classmethod
    def set(cls, phone: str, code: str, expire_seconds: int = 300):
        cls._cache[phone] = {
            "code": code,
            "expires_at": datetime.utcnow() + timedelta(seconds=expire_seconds),
            "attempts": 0
        }

    @classmethod
    def verify(cls, phone: str, code: str) -> bool:
        data = cls._cache.get(phone)
        if not data:
            return False
        if datetime.utcnow() > data["expires_at"]:
            cls._cache.pop(phone, None)
            return False
        data["attempts"] += 1
        if data["attempts"] > 5:
            cls._cache.pop(phone, None)
            return False
        return data["code"] == code

    @classmethod
    def remove(cls, phone: str):
        cls._cache.pop(phone, None)


class SmsAuthSkill(BaseSkill):
    """手机号验证码认证技能"""

    # Mock 模式万能验证码
    MOCK_CODE = "111111"

    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="sms_auth",
            display_name="手机验证码登录",
            description="手机号+验证码方式的用户认证",
            version="2.1.0",
            category="auth",
        )

    async def execute(self, action: str = "send_code", **kwargs) -> SkillResult:
        """
        执行认证操作
        action: send_code | verify_code | refresh_token
        kwargs:
            phone: str (手机号)
            code: str (验证码，verify_code 时需要)
            user_id: int (refresh_token 时需要)
        """
        if action == "send_code":
            return await self._send_code(kwargs.get("phone", ""))
        elif action == "verify_code":
            return await self._verify_code(kwargs.get("phone", ""), kwargs.get("code", ""))
        elif action == "refresh_token":
            return await self._refresh_token(kwargs.get("user_id"))
        else:
            return SkillResult(success=False, error=f"未知操作: {action}", skill_name=self.metadata().name)

    async def _send_code(self, phone: str) -> SkillResult:
        """发送验证码"""
        if not phone or len(phone) != 11 or not phone.startswith("1"):
            return SkillResult(success=False, error="手机号格式不正确", skill_name=self.metadata().name)

        # Mock 模式：固定验证码 111111（开发调试，返回 code 供前端展示）
        if settings.SMS_MOCK_MODE:
            code = self.MOCK_CODE
            SmsCodeCache.set(phone, code)
            print(f"[SMS MOCK MODE] 手机号: {phone}, 验证码: {code}")
            return SkillResult(
                success=True,
                data={"message": "验证码已发送", "code": code, "dev_mode": True},
                skill_name=self.metadata().name
            )

        # 真实模式：生成随机6位验证码，调用阿里云短信服务发送
        code = f"{random.randint(0, 999999):06d}"
        SmsCodeCache.set(phone, code)

        try:
            from alibabacloud_dysmsapi20170525.client import Client
            from alibabacloud_dysmsapi20170525 import models as dysmsapi_models
            from alibabacloud_tea_openapi import models as openapi_models

            config = openapi_models.Config(
                access_key_id=settings.SMS_ACCESS_KEY_ID,
                access_key_secret=settings.SMS_ACCESS_KEY_SECRET,
            )
            config.endpoint = "dysmsapi.aliyuncs.com"
            client = Client(config)

            req = dysmsapi_models.SendSmsRequest(
                phone_numbers=phone,
                sign_name=settings.SMS_SIGN_NAME,
                template_code=settings.SMS_TEMPLATE_CODE,
                template_param=json.dumps({"code": code}),
            )
            resp = client.send_sms(req)

            if resp.body.code != "OK":
                # 阿里云返回业务错误（签名/模板/额度等），日志记录具体原因，前端只看笼统提示
                print(f"[SMS ERROR] 阿里云返回失败: code={resp.body.code}, message={resp.body.message}")
                return SkillResult(
                    success=False,
                    error="验证码发送失败，请稍后重试",
                    skill_name=self.metadata().name
                )

            # 真实模式：不把验证码返回给前端（安全要求）
            return SkillResult(
                success=True,
                data={"message": "验证码已发送", "dev_mode": False},
                skill_name=self.metadata().name
            )
        except Exception as e:
            # SDK 异常（网络/凭证/签名不匹配等），日志记录，前端只看笼统提示
            print(f"[SMS ERROR] 发送异常: {type(e).__name__}: {e}")
            return SkillResult(
                success=False,
                error="验证码发送失败，请稍后重试",
                skill_name=self.metadata().name
            )

    async def _verify_code(self, phone: str, code: str) -> SkillResult:
        """验证码校验并登录/注册"""
        # Mock 模式：接受万能验证码 111111
        if settings.SMS_MOCK_MODE and code == self.MOCK_CODE:
            SmsCodeCache.set(phone, self.MOCK_CODE)

        if not SmsCodeCache.verify(phone, code):
            return SkillResult(success=False, error="验证码错误或已过期", skill_name=self.metadata().name)

        SmsCodeCache.remove(phone)

        return SkillResult(
            success=True,
            data={"phone": phone, "verified": True},
            skill_name=self.metadata().name
        )

    async def _refresh_token(self, user_id) -> SkillResult:
        """刷新 Token"""
        token = create_access_token(data={"sub": str(user_id), "id": user_id})
        return SkillResult(
            success=True,
            data={"access_token": token, "token_type": "bearer"},
            skill_name=self.metadata().name
        )
