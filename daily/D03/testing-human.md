# D03 — Testing-human（Kevin 真机 spot check）

> **B 方案**：admin + 后端 + 单测全部 AI 接管。本文件只列 Kevin 要点的具体动作。
>
> **本日 Tier 2 范围**：**只 GZ-ADMIN-005**（mp 5 tab + 占位页 + 客服浮层挂载 + 路由守卫）。
> 其他 4 个 ticket（ADMIN-001 / ADMIN-002 / ADMIN-004 / SYS-006）是**纯 admin/be，跳过 Tier 2** — AI Tier 1A + 1B 全 ✅ 即 close。
>
> **预计时间**：3-5 min

---

## 0. 启动前 check

| # | 检查项 | 命令 / 操作 | 状态 |
|---|---|---|---|
| 0.1 | docker 三容器 | `docker ps \| grep sensenran-dev` 看到 mysql/redis/minio 全 Up | ⬜ |
| 0.2 | 后端 8080 | `lsof -i:8080 -sTCP:LISTEN` 看到 java | ⬜ |
| 0.3 | mp dev 编译 | `cd code/main/miniapp && pnpm dev:mp-weixin` 等 "DONE Build complete" | ⬜ |
| 0.4 | 微信开发者工具 | 已导入 `code/main/miniapp/dist/dev/mp-weixin` | ⬜ |
| 0.5 | D02 d1 临时入口已清 | grep `Tier2-entry-temp` 在 `pages/index/index.vue` 应该**不存在**（ADMIN-005 完工时由 coder 清理）| ⬜ |

---

## 1. 测试清单

### 1.1 GZ-ADMIN-005 — mp 底部 5 tab + 全局布局 ⭐ 唯一 mp ticket

**入口路径**：微信开发者工具打开即首页（底部 tab 自动渲染）

| # | 测试动作 | 期望 | 判定 |
|---|---|---|---|
| A1 | 微信开发者工具刷新 → 进首页 → 看底部 | 5 tab：首页 / 扭蛋 / 预购 / 拼豆 / 我的；图标 + 中文 label 清晰；active tab 高亮主色 brand-primary（#FF6B81）| ⬜ |
| A2 | 点「扭蛋」tab | 跳 `pages/gacha/index` → 居中显示「扭蛋 敬请期待 V1.1」+ 返回首页 CTA | ⬜ |
| A3 | 点「预购」tab | 跳 `pages/ord/index` → 居中显示「预购 敬请期待 V1.1」+ 返回首页 CTA | ⬜ |
| A4 | 点「拼豆」tab（未登录）| 弹「登录后才能预约」二次引导（useNavGuard 拦截）| ⬜ |
| A5 | 点「我的」tab（未登录）| 弹「登录后才能查看」二次引导 | ⬜ |
| A6 | 点「首页」tab | 跳回首页（占位页 + 客服浮层显示）；首页不需要登录 | ⬜ |
| A7 | **D02 临时入口已清**：首页内容 | **不再**看到橙色虚线框 "🧪 d1 Tier 2 测试入口"（ADMIN-005 实施时 §0 grep `Tier2-entry-temp` 找到并清理 — coder 必须做） | ⬜ |
| A8 | **客服浮层在 5 个 tab 页全部可见**：依次切 5 个 tab | 每个 page 右下角💬 浮层都在 + 位置 132rpx 避开底 tab 栏 | ⬜ |
| A9 | 详情页 fixed CTA 测试（如 ADMIN-005 实施时建了演示详情页）| fixed CTA 条 与 tab 互斥（详情页隐藏 tab，CTA 显示）| ⬜ N/A |

---

## 2. 跨 ticket 联调（如有）

| # | 链路 | 期望 |
|---|---|---|
| C1 | 完整登录链路（依赖 D02 SYS-002）：未登录 → 点拼豆 tab → 触发登录引导 → 跳 login 页 → 微信一键登录 → 回到拼豆 tab | 全段 ✅ | ⬜ |

---

## 3. 不在此处测的（B 方案 — 已被 AI 覆盖）

| 范围 | 谁覆盖 |
|---|---|
| **ADMIN-001** 管理员登录 + owner/staff 角色 / 密码策略 / 5 次锁定 | kevin-qa Playwright（admin 端 owner 登录 → 切 staff → 看子集菜单）|
| **ADMIN-002** 账号 CRUD / 重置密码 / 禁用 / 操作日志 | kevin-qa Playwright + 后端 curl |
| **ADMIN-004** 后台路由 / 布局 / 侧边栏 / 默认跳转 / StoreSelector 占位 | kevin-qa Playwright（侧边栏菜单结构 + 角色权限差异 + 默认 path 跳转）|
| **SYS-006** 操作日志 @Log 注解 / 12 月清理 cron / staff 仅看自己 | kevin-qa 后端单测 + Playwright 操作日志页 |

如发现 AI Tier 1A/1B 漏验上面任一 → **不要自己补**，回 reports/<T>.md 看 kevin-coder/kevin-qa 输出，缺啥让对应 agent 补，写到 §revision 段触发闭环。

---

## 4. 判定结果（Kevin 填）

| Ticket | 进度 |
|---|---|
| ADMIN-005 mp 5 tab + 占位 + 浮层（A1-A8）| ⬜ 待测 |
| 跨 ticket 联调 C1（完整登录链路）| ⬜ 待测 |
| ADMIN-001 / 002 / 004 / SYS-006 | ⬜ 跳过 Tier 2，待 AI 全 ✅ 即 close |

**最终判定**：⬜ 全 ✅，可日终 closing ｜ ⬜ 有 ❌，待 revision

**Kevin 时间花费**：____ min（B 方案目标 3-5 min）
