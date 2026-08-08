"""
占星排盘 Skill
基于 flatlib + pyswisseph 库，提供西方占星排盘能力
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel

from app.skills import BaseSkill, SkillMetadata, SkillResult


class AstrologyChart(BaseModel):
    """占星排盘结果"""
    sun_sign: str
    sun_degree: float
    moon_sign: str
    moon_degree: float
    ascendant: str
    mc_sign: str
    planets: list[Dict[str, Any]]
    houses: list[Dict[str, Any]]
    aspects: list[Dict[str, Any]]
    elements: Dict[str, int]
    modes: Dict[str, int]


class AstrologySkill(BaseSkill):
    """占星排盘技能"""
    
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="astrology_calculation",
            display_name="占星排盘",
            description="西方占星术星盘计算，行星位置、宫位、相位等",
            version="2.0.0",
            category="divination",
        )
    
    async def execute(self, **kwargs) -> SkillResult:
        """
        执行占星排盘
        kwargs:
            birth_date: str (YYYY-MM-DD)
            birth_time: str (HH:MM)
            latitude: float
            longitude: float
        """
        try:
            birth_date = kwargs["birth_date"]
            birth_time = kwargs["birth_time"]
            latitude = kwargs.get("latitude", 39.9)
            longitude = kwargs.get("longitude", 116.4)
            
            from app.services.astrology_service import calculate_astrology
            result = calculate_astrology(birth_date, birth_time, latitude, longitude)
            
            chart = AstrologyChart(
                sun_sign=result.sun_sign,
                sun_degree=result.sun_degree,
                moon_sign=result.moon_sign,
                moon_degree=result.moon_degree,
                ascendant=result.ascendant,
                mc_sign=result.mc_sign,
                planets=[p.model_dump() for p in result.planets],
                houses=[h.model_dump() for h in result.houses],
                aspects=[a.model_dump() for a in result.aspects],
                elements=result.elements,
                modes=result.modes,
            )
            
            return SkillResult(
                success=True,
                data=chart.model_dump(),
                skill_name=self.metadata().name
            )
        except Exception as e:
            return SkillResult(
                success=False,
                error=str(e),
                skill_name=self.metadata().name
            )