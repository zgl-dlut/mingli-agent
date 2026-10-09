# 修复 DashScope API 401 错误

## 问题分析

报错：`Error code: 401 - Incorrect API key provided`

**根因**：阿里云百炼平台已升级，Base URL 格式变更。

| 项目 | 当前配置（旧版） | 最新官方（新版） |
|------|-----------------|-----------------|
| Base URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` |
| 模型名 | `qwen3.6-flash` | `qwen3.6-flash`（正确，无需改） |
| API Key | `sk-sp-...` | 可能需要在新版控制台重新生成 |

**注意**：`sk-sp-` 前缀是 DashScope 的特殊令牌（SP Token），这类 Token 可能与旧版 Base URL 绑定，平台升级后需要在新控制台获取新的 API Key 和 WorkspaceId。

## 修改方案

### 步骤 1：获取新的 API Key 和 WorkspaceId

前往 [阿里云百炼控制台](https://bailian.console.aliyun.com/cn-beijing?tab=model#/api-key)：
1. 获取或创建新的 **API Key**
2. 在「业务管理」中获取 **WorkspaceId**

### 步骤 2：修改 `.env` 文件

修改 `backend/.env` 中的 3 个配置项：

```env
# 修改前
DASHSCOPE_API_KEY=sk-sp-H.EPERR.aiMb.MEYCIQCDCKUFx6MwtdwSgOmWVCQOZzaVc1Rz-4EwMXnHfmY4FAIhANlbJsjf1Q3CIqYp4pQX09VEXARNom72xa55_An0_hWf
AI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 修改后（替换为实际值）
DASHSCOPE_API_KEY=<新的 API Key>
AI_BASE_URL=https://<WorkspaceId>.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
```

### 步骤 3：重启后端服务

后端使用 `--reload` 模式运行，修改 `.env` 后需手动重启。

### 步骤 4：验证

调用报告生成接口，确认不再报 401 错误。

## 涉及文件

| 文件 | 操作 |
|------|------|
| `backend/.env` | 更新 DASHSCOPE_API_KEY 和 AI_BASE_URL |
