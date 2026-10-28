# V3 MVP 实操截图

截图由 `frontend/e2e/v3-mvp.spec.ts` 从真实运行应用生成，不使用静态设计稿替代。

视口项目：

- `mobile-390`：390×844
- `mobile-430`：430×932
- `desktop-1440`：1440×900

文件前缀与测试链路：

1. `01-today-rhythm`：`/today`，今日节律与四 Tab。
2. `02-reading-home`：`/reading`，解读首页。
3. `03-report-library`：`/reading/reports`，旧报告惰性导入后的报告库。
4. `04-free-subscription-wall`：`/subscription?required=light`，免费订阅墙。
5. `05-full-subscription`：`/subscription`，全享模拟开通。
6. `06-persona-home`：`/persona`，命局人格主页。
7. `07-persona-crisis`：`/persona/chat/:id`，危机输入退出角色且回合数不增加。
8. `08-persona-memory`：`/persona/:id/memory`，记忆查看、开关与清空入口。

对应测试：`V3 navigation, reports, persona safety and subscription states`。
