# Prompt 长度优化计划

## 优化目标

**只做历史摘要截断**：保留最近5轮历史，预计节省3000-4000字

## 当前状态

- Prompt 总长度：40029字
- 历史摘要：5435字（56轮对话）
- 优化后预计：36000-37000字（减少8-10%）

## 实施步骤

### 修改 `_build_history_summary` 函数

**文件**：`mingli-agent/backend/app/services/followup_structured.py` 第42-100行

**改动**：
1. 在函数开头添加 `max_rounds=5` 参数
2. 只处理最近5轮 assistant 消息（从后往前取）
3. 保持现有提取逻辑不变（开头句式、核心结论、子问题标题、总结风格）

**代码改动**：
```python
def _build_history_summary(history: list, max_rounds: int = 5) -> str:
    """从历史 assistant 消息提取关键结论，构建历史摘要文本。
    
    只保留最近 max_rounds 轮历史，避免 prompt 过长。
    """
    # 只取最近 max_rounds 轮 assistant 消息
    assistant_msgs = [msg for msg in history if msg.get("role") == "assistant"]
    recent_msgs = assistant_msgs[-max_rounds:] if len(assistant_msgs) > max_rounds else assistant_msgs
    
    summaries = []
    for i, msg in enumerate(recent_msgs):
        # ... 现有提取逻辑不变
```

## 验证方式

1. 重启后端
2. 发送追问问题
3. 检查日志中 `prompt长度` 和 `摘要` 字数
4. 确认生成速度提升、输出质量保持

## 风险

- **低风险**：历史摘要仅供风格轮换参考，5轮足够
- 不影响命盘数据、用户问题、核心规则
