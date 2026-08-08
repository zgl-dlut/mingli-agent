"""
Skill 基础框架 - 所有 Skill 的抽象基类和注册机制
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, AsyncGenerator
from pydantic import BaseModel


class SkillMetadata(BaseModel):
    """Skill 元数据"""
    name: str                    # Skill 唯一标识
    display_name: str            # 显示名称
    description: str             # 描述
    version: str = "1.0.0"       # 版本
    category: str = "general"   # 分类: divination, auth, payment, content, security
    dependencies: list[str] = [] # 依赖的其他 Skill


class SkillResult(BaseModel):
    """Skill 统一返回结果"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    skill_name: str


class BaseSkill(ABC):
    """Skill 抽象基类"""
    
    @abstractmethod
    def metadata(self) -> SkillMetadata:
        """返回 Skill 元数据"""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> SkillResult:
        """执行 Skill 主逻辑"""
        pass
    
    async def initialize(self) -> None:
        """Skill 初始化（可选重写）"""
        pass
    
    async def shutdown(self) -> None:
        """Skill 关闭（可选重写）"""
        pass
    
    async def health_check(self) -> bool:
        """健康检查"""
        return True


class SkillRegistry:
    """Skill 注册中心 - 单例模式"""
    _instance = None
    _skills: Dict[str, BaseSkill] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._skills = {}
        return cls._instance
    
    def register(self, skill: BaseSkill) -> None:
        meta = skill.metadata()
        self._skills[meta.name] = skill
    
    def get(self, name: str) -> Optional[BaseSkill]:
        return self._skills.get(name)
    
    def list_skills(self) -> list[SkillMetadata]:
        return [s.metadata() for s in self._skills.values()]
    
    async def initialize_all(self) -> None:
        for skill in self._skills.values():
            await skill.initialize()
    
    async def shutdown_all(self) -> None:
        for skill in self._skills.values():
            await skill.shutdown()


# 全局注册中心实例
registry = SkillRegistry()
