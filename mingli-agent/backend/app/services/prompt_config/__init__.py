"""
Prompt规则配置模块
提供prompt规则配置的加载和管理功能
"""
import json
import os
from typing import Dict, Optional


class PromptConfig:
    """
    Prompt规则配置管理器
    
    从JSON配置文件加载prompt规则，提供统一的访问接口
    """
    
    _instance = None
    _config: Dict = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._load_config()
        return cls._instance
    
    @classmethod
    def _load_config(cls):
        """从JSON文件加载配置"""
        config_path = os.path.join(
            os.path.dirname(__file__),
            "prompt_rules.json"
        )
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cls._config = json.load(f)
        except Exception as e:
            print(f"加载prompt配置失败: {e}")
            cls._config = {}
    
    @classmethod
    def reload(cls):
        """重新加载配置"""
        cls._load_config()
    
    @property
    def format_directive(self) -> str:
        """排版格式指令"""
        return self._config.get("format_directive", "")
    
    @property
    def role_definition(self) -> str:
        """角色定位"""
        return self._config.get("role_definition", "")
    
    @property
    def input_conditions(self) -> str:
        """固定输入条件"""
        return self._config.get("input_conditions", "")
    
    @property
    def core_rules(self) -> str:
        """小白友好强制核心规则"""
        return self._config.get("core_rules", "")
    
    @property
    def output_rules(self) -> str:
        """灵活问答式输出规则"""
        return self._config.get("output_rules", "")
    
    @property
    def hard_specs(self) -> str:
        """最终硬性输出规范"""
        return self._config.get("hard_specs", "")
    
    @property
    def output_example(self) -> str:
        """输出格式示例"""
        return self._config.get("output_example", "")
    
    @property
    def version(self) -> str:
        """配置版本"""
        return self._config.get("version", "1.0.0")
    
    @property
    def examples(self) -> Dict:
        """示例数据（case1, case2, case3）"""
        return self._config.get("examples", {})
    
    def get_example(self, case_name: str) -> Optional[Dict]:
        """
        获取指定示例
        
        参数:
            case_name: 示例名称，如 "case1", "case2", "case3"
        
        返回:
            示例字典，包含 question 和 answer
        """
        return self._config.get("examples", {}).get(case_name)
    
    def build_prompt(self, **kwargs) -> str:
        """
        根据配置构建完整的prompt
        
        参数:
            kwargs: 模板变量，如 current_time, rizhu, gender 等
        
        返回:
            完整的prompt字符串
        """
        parts = [
            self.role_definition,
            self.input_conditions,
            self.core_rules,
            self.output_rules,
            self.hard_specs,
            self.output_example,
        ]
        
        prompt = "\n\n".join(parts)
        return prompt.format(**kwargs)


# 全局配置实例
prompt_config = PromptConfig()
