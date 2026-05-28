# GZ-USER-001 — mp 会员中心首页

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M5 §用户操作流程 §进入会员中心 步骤 1-3
**关联拆解**: doc/02-需求拆解.md §2.4 第 433 行
**关联 mockup**: design/mockup/me-home.html（视觉参考，V1.0 设计冻结期不强求逐像素；mockup 含 PRD 外内容见下方"特殊约束"）
**关联 ADR**: —
**依赖**: GZ-SYS-002 ✅(D02)

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§4 会员中心占位流**（M5，V1.0）— 进入会员中心 / 数据来源 / 各入口跳转目标
- **字段表**：doc/11-字段权威表.md **§2.1 `gz_user` 用户主表**（本 ticket 仅读：avatar_url / nick_name / phone_num / last_login_at；不动 schema）
- **UI 参考**（设计冻结期降级为视觉参考）：doc/12-UI-权威索引.md **§MP-ME-HOME** + mockup `me-home.html`

## What

mp 端「我的」tab 落地页：顶部头像 / 昵称 + 功能区九宫格入口（我的订单 / 我的预约 / 地址簿 / 客服 / 关于）。本 ticket 是 USER-004 订单 tab 容器的入口，也是其他 USER ticket 的跳转源头。

## AC（验收标准）

- [ ] **AC 1**：路由 `/pages/me/index` 挂底部 5 tab 的「我的」tab；未登录态显示"点击登录"占位（点击触发 useAuth 流程，复用 D02 SYS-002 composable）
- [ ] **AC 2**：已登录态顶部展示头像（默认占位图 → 用户头像）+ 昵称（默认"微信用户" → 用户昵称）
- [ ] **AC 3**：功能区九宫格入口（按 PRD 顺序）：
  1. 我的订单 → `/pages/me/orders`（USER-004 落地）
  2. 我的预约 → `/pages/me/bookings/list`（D05 GZ-BEAN-006 落地，**以 D05 实际路由为准**）
  3. 地址簿 → `/pages/me/address/list`（USER-003 落地）
  4. 客服 → 触发 GZ-SYS-004 客服全局浮层（`<button open-type="contact">`）
  5. 关于 → `/pages/me/about`（静态页，本 ticket 内一起做：版本号 + 合规备案 + 服务协议链接）
- [ ] **AC 4**：mockup 含的 PRD 外功能（等级 LV3 / 签到 / 邀请好友 / 优惠券 — doc/12 §7 偏差 D4）**全部不做**；保留收藏 UI 占位（数字硬编码 0，路由灰色不可点）
- [ ] **AC 5**：i18n 走 `t('user.home.xxx')`，新增 `zh_CN.ts` user 段
- [ ] **AC 6**：单测覆盖（mp 端 vitest）：head 区头像 / 昵称的两态切换（未登录 / 已登录）

## Tech（端 + 范围）

- **小程序**：`code/main/miniapp/src/`
  - `pages/me/index.vue`（落地页主组件）
  - `pages/me/about.vue`（静态页）
  - `components/biz/MeHeader.vue`（头像 + 昵称 head 区，业务组件包一层 — CLAUDE.md §7.5 组件库无关纪律）
  - `components/biz/MeGrid.vue`（九宫格组件，传入 items 数组）
  - `locales/zh_CN/user.ts`（新增）
  - 不动 store；从 pinia user store 读现成数据
- **后端**：**本 ticket 不动后端**（数据全部从 D02 SYS-002 已落库的 user store 读）
- **测试**：mp 端 vitest 覆盖头/未登录态切换

## 备注

### 强约束

1. **不动 gz_user schema**（数据全部由 SYS-002 落库，本 ticket 只读）
2. **九宫格入口路径**：跳转目标必须用真实路由名，不允许写 TODO 跳空白页（如 USER-004 未完工时本 ticket 可临时跳空白 toast「敬请期待」，待 USER-004 ✅ 后回改）
3. **mockup PRD 外功能严格删**：等级 / 签到 / 邀请好友 / 优惠券 — 不做，不留 UI 占位
4. **业务组件命名**：`MeHeader` / `MeGrid` 放 `components/biz/`，不允许在页面里直接撒 `<wd-*>` 标签（CLAUDE.md §7.5 组件库无关纪律）
5. **i18n 强制**：所有可见字符串走 `t('user.xxx')`，包括 "点击登录" / "微信用户" / 九宫格 label / 关于页内容

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 不依赖 USER-004 完工本 ticket 也能落 | 订单入口先跳 `/pages/me/orders` 路由占位，USER-004 接管该路由 |
| D2 | 关于页合并到本 ticket | 内容极少（版本号 + 链接 3 行），单开 ticket 不值 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 九宫格入口的 5 个跳转目标，其中我的预约依赖 D05 BEAN-006 真实路径 | 实施前先 grep `code/main/miniapp/src/pages/me/bookings/` 确认 D05 已建路由；未建则按 README 假设走 `/pages/me/bookings/list` + 报 Kevin 确认 |
| R2 | mockup 偏差实施时 AI 容易"还原全部" | §0 自检强制读 doc/12 §7 偏差 D4 全段，AC 4 已明确删除范围 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
