# 增强 subtopic 叙事性：lead 引导段 + closing 总结句

## 背景
用户要求增强叙事性：
1. 子问题开头加几句承上启下/总结性段落引出内容；末尾可选加一句总结
2. summary 可列表或叙事段落（已支持 items/narrative 二选一，无需改）

当前 Subtopic 结构只有 `{ title, blocks }`，无引导段和总结句。

## 改动

### 1. 后端 schema
文件：`backend/app/schemas/report_schema.py` Subtopic（L75-84）

加 lead 和 closing 可选字段：
```python
class Subtopic(BaseModel):
    title: str = Field(...)
    lead: Optional[str] = Field(
        None, description="可选，子问题开头的承上启下/总结性引导段落，1-2句，可内联**加粗**"
    )
    blocks: List[Block] = Field(...)
    closing: Optional[str] = Field(
        None, description="可选，子问题末尾一句总结/收尾，没必要则不填"
    )
```

### 2. 后端 prompt
文件：`backend/app/services/followup_structured.py`

**schema 示例（L59-66）**：subtopic 加 lead/closing：
```
"subtopics": [
  {
    "title": "...",
    "lead": "可选，1-2句承上启下或总结性引导，引出下面的内容",
    "blocks": [...],
    "closing": "可选，一句总结收尾，没必要则不填"
  }
]
```

**规则（L79-88）**：加一条说明 lead/closing：
- subtopic 的 lead 是可选的承上启下引导段落（1-2句），在 blocks 前输出；closing 是可选的末尾总结句，没必要则不填。两者都不是 block，不占用 blocks 的 keyword 槽位

### 3. 前端渲染
文件：`frontend/src/components/FollowupReportView.tsx`

**接口（L44-47）**：
```tsx
interface Subtopic {
  title: string
  lead?: string
  blocks: Block[]
  closing?: string
}
```

**SubtopicView（L179-192）**：渲染 lead（blocks 前）和 closing（blocks 后）：
```tsx
function SubtopicView({ data, index }) {
  const seq = CN_NUMS[index] || String(index + 1)
  return (
    <>
      <h2>{seq}、{data.title}</h2>
      {data.lead && renderInline(data.lead)}
      <div className="subtopic-blocks">
        {data.blocks.map((block, i) => (
          <BlockView key={i} data={block} />
        ))}
      </div>
      {data.closing && renderInline(data.closing)}
    </>
  )
}
```

## 不改动
- summary：已支持 items/narrative 二选一，无需改
- blocks 规则：仍只允许 type=keyword，lead/closing 是 subtopic 独立字段不是 block

## 验证
- `npx tsc --noEmit` 通过
- `python -c "import ast; ast.parse(open('backend/app/schemas/report_schema.py').read())"` 通过
- 硬刷新浏览器，生成追问，确认子问题有引导段和总结句
