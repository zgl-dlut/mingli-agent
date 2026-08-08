# 变更归档规则

## 规则

每次完成代码变更后，必须自动把变更记录追加到当天的归档文件中。

### 1. 归档目录

```
docs/change-logs/
```

### 2. 文件命名

按天命名：`YYYY-MM-DD.md`（如 `2026-08-08.md`）

当天所有变更都追加到同一个文件，不要新建多个文件。

### 3. 记录格式

每条记录用二级标题分隔：

```markdown
## HH:mm 变更主题

- 变更目标：xxx
- 涉及文件：xxx
- 主要改动：xxx
- 验证方式：xxx
- 风险点：xxx
```

### 4. 追加规则

- 如果当天文件不存在就新建
- 如果当天文件已存在，在文件末尾追加，不要覆盖之前的内容
- 每条记录之间用 `---` 分隔

### 5. 豁免条件

如果本次只是问答、分析，没有实际改动文件，则不需要追加记录。

## 自动化：post-commit Git Hook

项目已配置 `post-commit` 钩子（位于 `.git/hooks/post-commit`），在每次 `git commit` 成功后自动执行，从 commit message 中提取字段追加到当天归档文件。

### 6. Commit Message 格式约定

为了让 hook 正确解析，提交信息需遵守以下格式：

```
<type>: <主题，一行简述>

变更目标：<本次变更的目的>
涉及文件：<主要涉及的文件/模块，可逗号分隔>
主要改动：<核心改动点，可分多行>
验证方式：<如何验证，如测试通过/手动验证>
风险点：<潜在风险或遗留问题，无则填「无」>
```

**字段说明：**

- `<type>`：`feat` / `fix` / `refactor` / `docs` / `test` / `chore` / `perf` 等
- `<主题>`：一行简述，会作为归档记录的二级标题
- 五个字段必须出现在 body 中，每行一个字段，字段名后跟全角冒号 `：`
- 字段顺序不强制，但建议保持上述顺序便于阅读

**示例：**

```
feat: 追问报告结构化JSON改造

变更目标：将追问报告从 Markdown 改为 JSON 直渲染
涉及文件：followup_structured.py, FollowupReportView.tsx
主要改动：LLM 输出 JSON，Pydantic 校验，前端组件直渲染
验证方式：端到端测试通过，84 个用例全部 pass
风险点：非流式传输需等待完整 JSON
```

### 7. Hook 行为规则

- 解析 commit message body 中的五个字段（变更目标/涉及文件/主要改动/验证方式/风险点）
- 自动追加到 `docs/change-logs/YYYY-MM-DD.md`（按提交时间）
- 文件不存在时自动创建并写入标题行 `# 变更归档 — YYYY-MM-DD`
- 已存在时在末尾追加，记录间用 `---` 分隔
- 二级标题取 `<type>: <主题>` 部分并加上 `HH:mm` 时间前缀
- **跳过条件**（不写入归档）：
  - commit message body 不包含「变更目标」字段（视为普通提交，不触发归档）
  - merge commit（自动合并提交）
  - 通过 `--no-verify` 或环境变量 `SKIP_CHANGELOG=1` 提交时跳过

### 8. 手动跳过

提交时如不希望触发归档，可设置环境变量：

```bash
SKIP_CHANGELOG=1 git commit -m "..."
```

## 示例

```markdown
# 变更归档 — 2026-08-08

## 02:30 追问报告结构化JSON改造

- 变更目标：将追问报告从 Markdown 改为 JSON 直渲染
- 涉及文件：
  - backend/app/services/followup_structured.py
  - frontend/src/components/FollowupReportView.tsx
- 主要改动：
  - LLM 输出 JSON，Pydantic 校验
  - 前端 React 组件直渲染
- 验证方式：端到端测试通过
- 风险点：非流式传输需等待完整 JSON

---

## 03:00 清理死代码

- 变更目标：删除旧 Markdown 链路死代码
- 涉及文件：
  - backend/app/skills/content/ai_content_skill.py
  - backend/app/services/ai_service.py
- 主要改动：移除无调用方的旧函数
- 验证方式：grep 确认无残留引用
- 风险点：无
```
