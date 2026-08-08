"""
排版格式 Skill
负责加载和管理命理报告的排版格式规则，提供统一的格式指令
"""
import json
import os
from typing import Dict, Optional

from app.skills import BaseSkill, SkillMetadata, SkillResult


class FormatSkill(BaseSkill):
    """排版格式技能"""
    
    def __init__(self):
        self._format_rules = {}
        self._prompt_rules_path = os.path.join(
            os.path.dirname(__file__), 
            '../../services/prompt_config/prompt_rules.json'
        )
    
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="format",
            display_name="排版格式",
            description="负责加载和管理命理报告的排版格式规则，提供统一的格式指令",
            version="1.0.0",
            category="content",
            dependencies=[],
        )
    
    async def initialize(self) -> None:
        """初始化 - 加载排版格式规则"""
        self._load_format_rules()
    
    def _load_format_rules(self) -> None:
        """加载排版格式规则"""
        try:
            if os.path.exists(self._prompt_rules_path):
                with open(self._prompt_rules_path, 'r', encoding='utf-8') as f:
                    self._format_rules = json.load(f)
        except Exception as e:
            print(f"加载排版格式规则失败: {e}")
            self._format_rules = {}
    
    async def execute(self, action: str = "get_format_directive", **kwargs) -> SkillResult:
        """
        action: get_format_directive | get_full_rules
        """
        try:
            if action == "get_format_directive":
                directive = self._format_rules.get("format_directive", "")
                return SkillResult(
                    success=True,
                    data={"format_directive": directive},
                    skill_name=self.metadata().name
                )
            
            elif action == "get_full_rules":
                return SkillResult(
                    success=True,
                    data=self._format_rules,
                    skill_name=self.metadata().name
                )
            
            elif action == "refresh":
                self._load_format_rules()
                return SkillResult(
                    success=True,
                    data={"message": "排版格式规则已刷新"},
                    skill_name=self.metadata().name
                )
            
            else:
                return SkillResult(success=False, error=f"未知操作: {action}", skill_name=self.metadata().name)
        except Exception as e:
            return SkillResult(success=False, error=str(e), skill_name=self.metadata().name)
    
    def get_format_directive_sync(self) -> str:
        """同步获取排版格式指令"""
        if not self._format_rules:
            self._load_format_rules()
        return self._format_rules.get("format_directive", "")