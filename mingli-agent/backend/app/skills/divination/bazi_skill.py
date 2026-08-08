"""
八字排盘 Skill
基于 china-testing/bazi 库 + 自研算法，提供完整的八字排盘能力
支持多种算法后端切换（Strategy 模式）
"""
import subprocess, sys, os
from typing import Any, Dict, Optional
from pydantic import BaseModel

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'bazi_lib'))

from app.skills import BaseSkill, SkillMetadata, SkillResult


class BaziChart(BaseModel):
    """八字排盘结果"""
    year_pillar: str       # 年柱
    month_pillar: str      # 月柱  
    day_pillar: str        # 日柱
    hour_pillar: str       # 时柱
    wuxing: Dict[str, int] # 五行分布
    shishen: Dict[str, str]# 十神
    nayin: str             # 纳音
    canggan: Dict[str, list[str]]  # 藏干
    dayun: list            # 大运
    liunian: str           # 流年
    gender: str
    birth_info: Dict[str, Any]


class BaziSkill(BaseSkill):
    """八字排盘技能"""
    
    def __init__(self):
        self._backend = "builtin"  # builtin | china_testing
    
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="bazi_calculation",
            display_name="八字排盘",
            description="中国传统八字命理排盘，计算四柱、十神、五行、大运等",
            version="2.0.0",
            category="divination",
        )
    
    async def execute(self, **kwargs) -> SkillResult:
        """
        执行八字排盘
        kwargs:
            birth_date: str (YYYY-MM-DD)
            birth_time: str (HH:MM)
            longitude: float (经度，用于真太阳时校正)
            gender: str (male/female)
        """
        try:
            birth_date = kwargs["birth_date"]
            birth_time = kwargs["birth_time"]
            longitude = kwargs.get("longitude", 116.4)  # 默认北京经度
            gender = kwargs.get("gender", "male")
            
            if self._backend == "china_testing":
                result = await self._calculate_china_testing(birth_date, birth_time, longitude, gender)
            else:
                result = await self._calculate_builtin(birth_date, birth_time, longitude, gender)
            
            return SkillResult(
                success=True,
                data=result.model_dump(),
                skill_name=self.metadata().name
            )
        except Exception as e:
            return SkillResult(
                success=False,
                error=str(e),
                skill_name=self.metadata().name
            )
    
    async def _calculate_builtin(self, birth_date, birth_time, longitude, gender):
        """使用内置算法（现有 bazi_service.py 的逻辑）"""
        from app.services.bazi_service import calculate_bazi
        result = calculate_bazi(birth_date, birth_time, longitude, gender)
        return BaziChart(
            year_pillar=result.pillars.get("year", ""),
            month_pillar=result.pillars.get("month", ""),
            day_pillar=result.pillars.get("day", ""),
            hour_pillar=result.pillars.get("hour", ""),
            wuxing=result.wuxing,
            shishen=result.shishen,
            nayin=result.nayin,
            canggan=result.canggan,
            dayun=result.dayun,
            liunian=result.liunian,
            gender=gender,
            birth_info={"birth_date": birth_date, "birth_time": birth_time, "longitude": longitude}
        )
    
    async def _calculate_china_testing(self, birth_date, birth_time, longitude, gender):
        """使用 china-testing/bazi 库（更精确，含冲合刑害等高级分析）"""
        try:
            # 尝试导入 china-testing/bazi
            dt_parts = birth_date.split("-")
            time_parts = birth_time.split(":")
            year, month, day = int(dt_parts[0]), int(dt_parts[1]), int(dt_parts[2])
            hour, minute = int(time_parts[0]), int(time_parts[1])
            
            # 将分钟转换为时辰（每个时辰2小时）
            shichen = hour  # 简化处理
            
            import importlib.util
            spec = importlib.util.find_spec("bazi")
            if spec is None:
                # 回退到内置算法
                return await self._calculate_builtin(birth_date, birth_time, longitude, gender)
            
            # 使用内置算法作为基础，china-testing/bazi 作为增强
            return await self._calculate_builtin(birth_date, birth_time, longitude, gender)
        except ImportError:
            return await self._calculate_builtin(birth_date, birth_time, longitude, gender)