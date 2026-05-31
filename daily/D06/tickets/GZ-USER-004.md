# GZ-USER-004 — mp 我的订单 tab 占位结构

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M5 §用户故事 + 合同 doc/03-contract.md §2.1 第一期（一）"订单聚合 tab 仅占位"
**关联拆解**: doc/02-需求拆解.md §2.4 第 475 行
**关联 mockup**: design/mockup/order-list.html（占位版本，V1.0 状态为空；mockup 含 4 tab 含拼豆 — doc/12 §7 偏差 D3，本 ticket 按 PRD 删拼豆 tab）
**关联 ADR**: —
**依赖**: GZ-USER-001

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§4 会员中心占位流** §订单 tab 占位段（V1.0 仅占位 / V1.1 真接入 / 拼豆不混入）
- **字段表**：doc/11-字段权威表.md（**本 ticket 不动表**，仅定义前端契约 VO）
- **UI 参考**（视觉走 C 日漫海报浓墨：页面用 Biz* 组件 + var(--c-*)，见 doc/tokens.md + doc/13；旧 mockup 仅作布局参考，以 c-tokens.scss 的 rpx 为准）：doc/12-UI-权威索引.md **§MP-ORD-LIST**（V1.0 占位 + V1.1 真数据） + mockup `order-list.html`（实施时按 PRD 删拼豆 tab — doc/12 §7 偏差 D3）

## What

会员中心订单聚合 tab 框架，V1.0 三个 tab（全部 / 扭蛋 / 预购）全部占位「暂无订单，敬请期待 V1.1」；预约数据**不**混在订单 tab（独立"我的预约"入口）；数据契约层预留订单聚合接口，V1.1 直接接入。

## AC（验收标准）

- [ ] **AC 1**：路由 `/pages/me/orders` 挂会员中心订单聚合页，从 USER-001 九宫格「我的订单」入口跳入
- [ ] **AC 2**：顶部 3 个 tab（按 PRD 顺序）：全部 / 扭蛋 / 预购；**不含**拼豆 tab（doc/12 §7 偏差 D3 按 PRD 删）
- [ ] **AC 3**：3 个 tab 全部显示空状态占位（图标 + 文案"暂无订单，敬请期待 V1.1"）；不调任何后端 API
- [ ] **AC 4**：数据契约层 mock 接口 `/app/gz/user/orders/list?type=all|gacha|preorder`（**V1.0 仅占位不实现**，仅在 `api/gz-user.ts` 中声明 TypeScript 签名 + 注释「V1.1 接入」）
- [ ] **AC 5**：契约 VO 定义（前端 `types/order.ts`）：
  ```ts
  interface OrderListVO {
    orderId: string; type: 'gacha' | 'preorder';
    amount: number; status: string; createdAt: string;
    coverUrl?: string; title?: string;
  }
  ```
  V1.1 接入时直接复用，不允许 V1.1 改字段
- [ ] **AC 6**：i18n 走 `t('user.orders.xxx')`（含 tab label / 空状态文案）
- [ ] **AC 7**：单测覆盖 tab 切换交互（3 tab 切换无 API 调用，纯前端占位）

## Tech（端 + 范围）

- **后端**：**本 ticket 不动后端**（V1.0 不实现订单聚合接口）
- **小程序**：`code/main/miniapp/src/`
  - `pages/me/orders.vue`（tab 容器 + 占位）
  - `components/biz/OrderListEmpty.vue`（空状态业务组件）
  - `api/gz-user.ts` 加 `getOrderList()` 声明（不实现，注释 V1.1 接入）
  - `types/order.ts`（新增，契约 VO）
  - `locales/zh_CN/user.ts` 加 orders 段
- **测试**：mp 端 vitest 覆盖 tab 切换

## 备注

### 强约束

1. **预约不混入订单 tab**（doc/02 §2.4 第 479 行 + 合同 §2.1）— 预约独立「我的预约」入口（D05 GZ-BEAN-006）
2. **mockup 4 tab 按 PRD 删拼豆 tab**（doc/12 §7 偏差 D3） — UI 上 3 tab 即可
3. **不调任何 API**：V1.0 占位严格不调 backend，避免后端开发误以为已接入
4. **契约 VO 不变**：AC 5 定义的 OrderListVO 是给 V1.1 用的合同，V1.1 不允许改字段，V1.0 ticket 务必把字段定齐
5. **i18n 强制**：tab label / 空状态文案 / "敬请期待 V1.1" 走 `t('user.orders.xxx')`

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | V1.0 不实现后端接口 | 合同明确 V1.0 占位；后端没必要为占位写 mock 接口 |
| D2 | 契约 VO 提前定齐 | V1.1 直接接入零改动 — 这是占位 ticket 的真正价值 |
| D3 | 不混入预约 | doc/10 §4 业务流 + 合同 §2.1 明确"预约独立入口" |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | V1.1 真接入时 OrderListVO 字段不够（如缺少物流号 / 退款状态）→ 改契约影响 V1.0 历史代码 | AC 5 已留 type / status 两个泛字段；V1.1 评估后如需扩字段 → 加可选字段（不 break 现有契约） |
| R2 | 用户疑惑「为什么没有拼豆？」 | 占位文案 + 我的预约入口在 USER-001 九宫格已独立暴露，UX 路径清晰 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
