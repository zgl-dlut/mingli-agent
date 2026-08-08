"""
安全 Skill
JWT Token 管理、密码哈希、权限校验、Rate Limiting
"""
from typing import Any, Dict, Optional
from datetime import datetime, timedelta

from app.skills import BaseSkill, SkillMetadata, SkillResult
from app.core.security import create_access_token, verify_password, get_password_hash


class SecuritySkill(BaseSkill):
    """安全技能"""
    
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="security",
            display_name="安全管理",
            description="JWT Token、密码哈希、权限校验",
            version="2.0.0",
            category="security",
        )
    
    async def execute(self, action: str = "create_token", **kwargs) -> SkillResult:
        try:
            if action == "create_token":
                token = create_access_token(
                    data=kwargs.get("data", {}),
                    expires_delta=kwargs.get("expires_delta")
                )
                return SkillResult(success=True, data={"token": token}, skill_name=self.metadata().name)
            
            elif action == "hash_password":
                hashed = get_password_hash(kwargs["password"])
                return SkillResult(success=True, data={"hashed_password": hashed}, skill_name=self.metadata().name)
            
            elif action == "verify_password":
                result = verify_password(kwargs["plain"], kwargs["hashed"])
                return SkillResult(success=result, data={"verified": result}, skill_name=self.metadata().name)
            
            else:
                return SkillResult(success=False, error=f"未知操作: {action}", skill_name=self.metadata().name)
        except Exception as e:
            return SkillResult(success=False, error=str(e), skill_name=self.metadata().name)