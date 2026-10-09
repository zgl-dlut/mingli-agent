# closing 智能化：根据实际情况决定保留/丰富/省略

## 背景
用户要求 closing 由 LLM 根据实际情况判断：
- 有必要收尾时：输出，且叙事化有感情（朋友式嘱咐/鼓励），不是干巴巴套话
- 没必要时：不输出

当前 closing 描述是"可选，一句总结收尾，没必要则不填"，没说明叙事化要求。

## 改动（纯 prompt + schema 描述，前端不动）

### 1. followup_structured.py
- **subtopic closing 示例（L67）**：
  `"可选，根据实际情况决定是否输出；若输出则2-3句朋友式嘱咐/鼓励/情绪收尾，有感情叙事化，不要干巴巴的总结套话；没必要则不填"`
- **summary closing 示例（L75）**：同步调整
- **规则（L91）**：subtopic 的 closing 描述同步调整为"根据实际情况决定，输出则叙事化有感情，不输出则省略"

### 2. report_schema.py
- **Subtopic.closing description（L88-89）**：
  `"可选，根据子问题实际情况决定；若输出则2-3句朋友式嘱咐/鼓励/情绪收尾，有感情叙事化；没必要则不填"`
- **Summary.closing description（L116）**：同步调整

## 不改动
- 前端 SubtopicView/SummaryView：renderInline 已支持多句和 **加粗，不动
- closing 字段仍是 Optional，LLM 按实际情况决定

## 验证
- python3 ast.parse 通过
- 生成追问，确认 closing 有时出现（叙事化）、有时省略
