# 分享赚积分功能实施方案

## 需求

1. 顶部导航余额徽章**左侧**加"分享赚积分"按钮
2. 点击弹窗：展示专属分享链接 + 复制按钮 + 活动说明（每注册1个新用户赚80积分），可关闭
3. 新用户通过分享链接注册后，自动给分享人发放 80 积分，流水类型"分享赚积分"

## 现有代码调研结论

- 顶部导航在 [Header.tsx](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/frontend/src/components/Header.tsx)，右侧只有余额徽章，按钮加在它左边即可
- 注册入口在 [auth.py](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/api/auth.py) 的 `/api/auth/login`：验证码校验通过后"查不到用户就自动注册"，新用户赠送在 `grant_new_user_bonus()`（L80），**分享奖励挂在同一处最自然**
- 登录请求体 `VerifySmsRequest`（phone/code），加一个可选 `ref` 字段即可，老前端不传不受影响
- 积分流水 `transactions` 表：type=bonus/recharge/consume，biz_type 细分（new_user_bonus/bonus/recharge/admin_recharge/first_reading/followup）→ 新增 `biz_type=share_reward`，type=bonus（收入，前端 + 号绿色自动正确）
- 积分明细页 [PointsHistoryPage.tsx](file:///Users/zhangguangling/Downloads/命理推算/mingli-agent/frontend/src/pages/PointsHistoryPage.tsx) 的 `buildLabel()` 按 biz_type 映射文案，需加 share_reward → "分享赚积分"
- 前端登录链路：LoginPage → userStore.loginWithSms → authApi.login；ref 参数沿这条链传递
- App.tsx 已有 URL 参数捕获先例（OAuthCallbackHandler 抓 ?token=），照此模式抓 ?ref=
- users 表需加 `inviter_id` 字段记录邀请人（审计+防自我邀请）

## 分享链接设计

```
https://www.qusuansuan.com/?ref={分享人user_id}
```

- 用户点开链接 → 前端把 ref 存 localStorage（`inviter_ref`）→ 登录/注册时随验证码登录请求带给后端
- 后端**仅在新用户创建分支**处理 ref：老用户登录忽略，天然每人只奖励一次
- 防作弊：ref 用户不存在→忽略；新用户不可能等于自己（尚未创建）；奖励发放 try/except 包裹，失败只记日志不阻断注册

## 改动清单

### 后端（3 文件 + 1 条 DB 迁移）

**1. `backend/app/config.py`**
- 新增 `SHARE_REWARD_POINTS: int = 80`

**2. `backend/app/models/user.py`**
- User 模型加 `inviter_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="邀请人用户ID")`

**3. DB 迁移**（生产 MySQL 执行）
```sql
ALTER TABLE users ADD COLUMN inviter_id INT NULL DEFAULT NULL COMMENT '邀请人用户ID';
```

**4. `backend/app/api/auth.py`**
- `VerifySmsRequest` 加 `ref: Optional[int] = None`
- 新增 `grant_share_reward(db, inviter_id, new_user_phone)`：
  - 校验 inviter 存在且 id 有效
  - inviter.points += 80
  - 写流水：`Transaction(user_id=inviter.id, type="bonus", points=80, description=f"分享赚积分：好友{phone[:3]}****{phone[-4:]}注册奖励", biz_type="share_reward")`
  - 整体 try/except，异常 logger.error 不抛出
- login 新用户创建分支：创建 user 后 `user.inviter_id = ref`（ref 有效时），调用 grant_share_reward
- 日志：`[SHARE] 新用户 {phone} 由用户#{ref} 邀请，发放{80}积分`

### 前端（5 文件）

**5. `src/App.tsx`**
- 新增 RefCapture 逻辑（仿 OAuthCallbackHandler）：挂载时读 `?ref=`，是纯数字则存 `localStorage.inviter_ref`，然后清掉 URL 参数

**6. `src/api/auth.ts`**
- `login(phone, code, ref?)` → body 带 `ref`

**7. `src/store/userStore.ts`**
- loginWithSms：登录前读 `localStorage.inviter_ref` 传入，登录完成后（无论新老用户）清除该 key

**8. `src/components/ShareModal.tsx`（新建）**
- 弹窗内容：
  - 标题：🎁 分享赚积分
  - 链接框：`https://www.qusuansuan.com/?ref={user.id}` + "复制链接"按钮（navigator.clipboard 优先，微信浏览器降级 textarea+execCommand）
  - 活动说明：
    - 每邀请 1 位新用户通过你的链接注册，立即获得 **80 积分**
    - 好友注册同时获得 240 新用户积分
    - 积分实时到账，可在「积分明细」查看
    - 邀请人数不限，多邀多得
  - 关闭按钮（右上 × + 底部"知道了"）
- 样式沿用现有 Modal 风格（RechargeModal 参照）

**9. `src/components/Header.tsx`**
- 余额徽章左侧加按钮："🎁 分享赚积分"（小胶囊，半透明白底，登录后才显示）
- 点击打开 ShareModal（组件内 useState 控制）

**10. `src/pages/PointsHistoryPage.tsx`**
- buildLabel 加：`if (t.biz_type === 'share_reward') return '分享赚积分'`

## 不做的事（范围控制）

- 微信 OAuth 回调创建的 wx_ 用户不处理 ref（极边缘路径，主注册入口是手机验证码）
- 管理后台"用户积分总览"的"赠送"统计（type=bonus）会包含分享奖励，biz_type 可区分，暂不改动后台统计

## 验证

1. DB 迁移执行后 `DESC users` 确认 inviter_id 列存在
2. 容器内脚本模拟：带 ref 注册新手机号 → 断言 ①新用户 inviter_id 正确 ②邀请人余额 +80 ③流水 biz_type=share_reward ④重复登录不重复发放 ⑤无效 ref 不报错；测试数据清理
3. 前端构建部署后：未登录访问 `/?ref=1` → localStorage 有 inviter_ref；Header 按钮弹出弹窗、复制可用；积分明细"分享赚积分"显示 +80 绿色
4. 首页 200、登录链路回归正常

## 风险

| 风险 | 处理 |
|---|---|
| 刷号作弊（批量注册给自己刷分） | 注册需短信验证码，成本天然存在；后台可按 inviter_id 审计异常邀请量，后续可加上限 |
| 微信浏览器 clipboard API 不可用 | textarea + execCommand 降级方案 |
| ref 被篡改成非法值 | 后端校验用户存在性，无效直接忽略 |
| 奖励发放失败影响注册 | try/except 包裹，注册主流程不受影响 |
