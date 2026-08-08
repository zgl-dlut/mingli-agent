"""
AI 内容生成 Skill
封装 Prompt 构建、AI 对话、流式输出能力
"""
from typing import Any, Dict, Optional, AsyncGenerator

from app.skills import BaseSkill, SkillMetadata, SkillResult


class AiContentSkill(BaseSkill):
    """AI 内容生成技能"""
    
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="ai_content",
            display_name="AI命理解读",
            description="基于命盘数据的 AI 综合解读，支持多轮对话和流式输出",
            version="2.0.0",
            category="content",
            dependencies=["bazi_calculation", "astrology_calculation"],
        )
    
    async def execute(self, action: str = "first_reading", **kwargs) -> SkillResult:
        """
        action: first_reading | follow_up | build_prompt
        """
        try:
            if action == "build_prompt":
                from app.services.prompt_builder import build_system_prompt
                prompt = build_system_prompt(
                    kwargs["bazi_data"], kwargs["astro_data"],
                    kwargs.get("gender", "male"),
                    kwargs.get("birth_time", ""), kwargs.get("location", ""),
                    kwargs.get("longitude", 0), kwargs.get("latitude", 0)
                )
                return SkillResult(success=True, data={"system_prompt": prompt}, skill_name=self.metadata().name)
            
            elif action == "first_reading":
                from app.services.ai_service import generate_first_reading
                # 返回生成器引用，供 API 层使用流式输出
                return SkillResult(
                    success=True,
                    data={"action": "first_reading", "params": kwargs},
                    skill_name=self.metadata().name
                )
            
            elif action == "follow_up":
                return SkillResult(
                    success=True,
                    data={"action": "follow_up", "params": kwargs},
                    skill_name=self.metadata().name
                )
            
            else:
                return SkillResult(success=False, error=f"未知操作: {action}", skill_name=self.metadata().name)
        except Exception as e:
            return SkillResult(success=False, error=str(e), skill_name=self.metadata().name)
    
    async def stream_first_reading(self, bazi_data: dict, astro_data: dict, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成首次解读"""
        from app.services.ai_service import generate_first_reading
        async for chunk in generate_first_reading(bazi_data, astro_data, **kwargs):
            yield chunk