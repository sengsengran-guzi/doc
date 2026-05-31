# D<N>（d<X>）— Testing-human（Kevin mp 真机批量人验清单）

> admin + 后端 + 单测全部 AI 接管（Tier 1A coder + Tier 1B kevin-qa）。本文件只列 **Kevin 要点的具体动作** — mp 端真机 + 微信原生能力 + 产品 sense。
>
> **本日 mp 人验项**：<列当日 mp ticket，纯 admin/be ticket 跳过>。coder 每天预填，**Kevin 不必当天测** —— 累计 3-4 天 mp ticket 后集中跑一轮，跨多个 D<N>/testing-human.md。
>
> **节奏**：不强求每天；纯 admin/be 日本文件全空，直接 closing。

---

## 0. 启动前 check

| # | 检查项 | 命令 / 操作 | 状态 |
|---|---|---|---|
| 0.1 | docker 三容器 | `docker ps \| grep sensenran-dev` 看到 mysql/redis/minio 全 Up | ⬜ |
| 0.2 | 后端 8080 | `lsof -i:8080 -sTCP:LISTEN` 看到 java 进程 | ⬜ |
| 0.3 | mp dev 编译 | `cd code/main/miniapp && pnpm dev:mp-weixin` 后等 "DONE Build complete" | ⬜ |
| 0.4 | 微信开发者工具 | 已导入 `code/main/miniapp/dist/dev/mp-weixin` | ⬜ |

---

## 1. 测试清单（表格驱动，逐行勾选）

### 1.1 GZ-XXX-NNN — <标题> ⭐（如是主流程标⭐）

**入口路径**（必填，CLAUDE.md §8.3 可达性约束）：从 `<已有页 / 临时入口>` 点 N 次 → 本新页
- 如 ticket 任务卡 AC N "Tier 2 入口可达" 描述了临时入口（`<!-- TODO(Tier2-entry-temp) -->`）→ 在此列入口位置
- 如 ticket 未列入口路径 → **STOP，回 §revision 段写「问题：入口不可达，请 coder 加临时入口」**，不要自己切编译模式 / console 跳

| # | 测试动作 | 期望 | 判定 |
|---|---|---|---|
| A1 | 打开 X 页 / 点 Y 按钮 | 看到 Z UI 元素 | ⬜ |
| A2 | 输入 / 操作 ... | API 返 200 / DB 落库 / toast 显示 ... | ⬜ |
| A3 | 微信原生能力（wx.login / 支付 / 客服 / 扫码 / getPhoneNumber） | 弹原生授权 / 调起原生接口 | ⬜ |
| A4 | 边界 / 异常路径（拒授权 / 网络断 / 已登录态重进）| 友好降级 / 不报 500 | ⬜ |
| A5 | DB 验证（如需要）| `docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -e "SELECT ..."` 输出符合 | ⬜ |

### 1.2 GZ-XXX-NNN — <第二个 mp ticket>

（同 1.1 格式）

---

## 2. 跨 ticket 联调（如有 — 当日 mp ticket 间有强协作时单独跑）

| # | 链路 | 期望 |
|---|---|---|
| C1 | <ticket A 入口> → <ticket B 流程> → <ticket C 收尾> | 全段 ✅ | ⬜ |

---

## 3. 不在此处测的（已被 AI 覆盖）

| 范围 | 谁覆盖 | 在哪看结果 |
|---|---|---|
| 后端单测 / 集成 / curl API | kevin-coder Tier 1A + kevin-qa Tier 1B | `reports/<T>.md` §AI 自测段 + §AI 测试段 |
| admin Playwright E2E | kevin-qa Tier 1B | `reports/<T>.md` §AI 测试段 |
| Flyway DDL / Redis / MinIO | kevin-coder Tier 1A | reports §AI 自测段 |
| mp vitest unit | kevin-coder Tier 1A + kevin-qa 复测 | reports §AI 测试段 |
| admin / mp 视觉评判（颜色 / 间距 / 圆角） | **不测**（设计冻结期，6/10-6/14 风格统一时 review） | — |

---

## 4. 判定

- ✅ **该 ticket 过** → progress.md「人验」列标 ✅（**不 gate 日终 closing** —— closing 每天照常，ticket 在 AI ✅ 时已 close）
- ❌ **有问题** → 在对应 ticket 任务卡 `D<N>/tickets/<T>.md §revision` 段写"问题 N: 现象 / 期望"（ticket 已 close 也照填）→ 喊 `@coder 修 D<N>/<T> revision 段`

---

## 跳过判定

| 条件 | 动作 |
|---|---|
| 今日所有 ticket Tech 段都不含 `miniapp/` 路径 | **跳过本文件**，AI Tier 1A + 1B 全 ✅ 即 close |
| 今日 ticket 涉及微信支付 / 登录 / 客服 / 扫码 / 手机号 | **必须**走 §1 mp 真机段 |
| 客户演示前一天（如 6/04 / 6/14 / 7/30） | 走 §5 全栈回归段（30-45 min，例外） |

---

## 5. 客户演示前全栈回归（仅 V1.0 6/04 / V1.1 7/30 等节点性触发）

> 平时不跑。仅客户演示前一天跑。预算 30-45 min。

| # | 范围 | 内容 |
|---|---|---|
| R1 | mp 端全栈 happy path | 微信登录 → 个人资料 → 拼豆全流程 → 资讯阅读 → 客服浮层 → 退出（V1.1 加：预购下单 → 支付 → 订单详情 → 扭蛋抽奖 → 抽奖历史 → 图鉴）|
| R2 | admin 端 spot check | 登录 → 用户列表 → 拼豆配置 → 操作日志（V1.1 加：商品 / 扭蛋池 / 订单 / 物流 / 对账 / 看板）|
| R3 | 文案 / 视觉一致性 | 主色一致 / emoji / 中文文案 / tokens.md 主色应用 |
| R4 | 数据 sense | admin 看板数字 / 用户列表分页 |

---

## 判定结果（Kevin 填）

| Ticket | 进度 |
|---|---|
| GZ-XXX-NNN（A1-AN）| ⬜ 待测 |
| GZ-YYY-NNN（B1-BN）| ⬜ 待测 |
| 跨 ticket 联调（C1-CN）| ⬜ 待测 |

**本轮批量人验结论**：⬜ 全 ✅ ｜ ⬜ 有 ❌，已回填对应 ticket §revision

**Kevin 时间花费**：____ min（一轮批量人验，扫掉累计的 mp ticket）
