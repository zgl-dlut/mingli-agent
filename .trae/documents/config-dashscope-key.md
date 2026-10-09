# 配置 DashScope API Key

## 摘要
将用户提供的 DashScope API Key 填入 `.env` 文件，替换占位符，然后重启后端使 AI 模型生效。

## 改动
- **文件**: `backend/.env` 第 7 行
- **改动**: `DASHSCOPE_API_KEY=your-dashscope-api-key-here` → `DASHSCOPE_API_KEY=sk-sp-H.EPERR.aiMb.MEYCIQCDCKUFx6MwtdwSgOmWVCQOZzaVc1Rz-4EwMXnHfmY4FAIhANlbJsjf1Q3CIqYp4pQX09VEXARNom72xa55_An0_hWf`

## 后续
- 重启后端服务（`uvicorn app.lightweight_main:app --host 0.0.0.0 --port 8000`）
- 前端点击"开始解读"即可调用 Qwen-3.6-Flash 生成真实报告
