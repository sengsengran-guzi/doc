# GZ-ORD-105 — 预购订单查询（C 端 + 后台基础）

**优先级**: P1
**复杂度**: S
**关联 PRD**: doc/02-prd.md M3 §用户操作流程 步骤 7 + M5 §用户操作流程 §进入会员中心
**关联拆解**: doc/02-需求拆解.md §3.2 第 729-738 行
**关联 mockup**: design/mockup/order-list.html + order-detail.html（仅布局参考；mp 视觉以 C 系统为准，doc/13；admin 走 ruoyi 默认）
**关联 ADR**: —
**依赖**: GZ-ORD-104 + GZ-USER-101 ✅（V1.0 已建会员中心骨架）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §6 V1.1 演进流 §6.6（ORD-104 实施时已写）+ §订单状态时间线
- **字段表**：doc/11-字段权威表.md §6.3 gz_ord_order + §6.4 物流字段（C1 简化）
- **UI 参考**：mp `order-list.html` + `order-detail.html` + doc/12 §MP-USER-ORDER-LIST / §MP-USER-ORDER-DETAIL

## What

用户在会员中心可查预购订单（C 端）+ 后台运营查所有预购订单（admin 基础）：

1. **C 端订单列表**（会员中心 → 订单 tab）：分 tab 展示 `全部 / 待支付 / 已支付 / 物流中 / 已完成`，下拉刷新 + 加载更多
2. **C 端订单详情**：商品 snapshot 信息 + 数量 + 总金额 + 收货地址 snapshot + **状态时间线**（5 节点 created/paid/in_logistics/delivered/closed 已发生节点高亮）+ **物流模块**（依赖 GZ-USER-103，本 ticket **仅占位** — 空状态 + 「跨境物流详情待 V1.1 后续完善」文案）+ 国内单号（如有，可点击复制）+ 「联系客服」CTA（C 端无退款入口，PAY-103 §AC 4 强约束）
3. **后台订单列表**（admin 基础占位）：复用 V1.0 ADMIN-103 订单详情骨架结构，列表页支持按 status / 用户手机号 / order_no 模糊查询；详情页复用 ADMIN-103 但加预购特定字段（snapshot 字段展示 + 物流单号录入）

## AC（验收标准）

- [ ] **AC 1**：mp `GET /app/gz/ord/order/list` 接口：
  - sa-token 校验 + 拿 user_id
  - 参数：page / size / status(`all`/`created`/`paid`/`logistics`/`done` — `logistics` 含 in_logistics+delivered；`done` 含 closed)
  - 查询：`WHERE user_id=? AND status IN (...)` ORDER BY created_at DESC
  - 返回每条 order 简版 VO（order_no / 商品名 + 主图 snapshot / 数量 / total_fen / status / created_at）
- [ ] **AC 2**：mp `GET /app/gz/ord/order/{id}` 详情接口：
  - 校验 order.user_id 等于当前 user（防越权）
  - 返回完整字段 + 状态时间线（推导自 created_at/paid_at/shipped_at/delivered_at 字段 + status 当前态）
- [ ] **AC 3**：mp 端会员中心订单 tab 入口（USER-101 已实现的会员中心页面接入）：
  - 「我的订单」cell 点击 → 跳 `/pages/user/order-list.vue`
  - 列表页顶部 5 个 status tab
- [ ] **AC 4**：mp 端 `pages/user/order-list.vue` 列表页 + `pages/user/order-detail.vue` 详情页：
  - 列表：商品卡 + 状态 chip（C token 配色：created var(--c-yellow) / paid var(--c-blue) / logistics var(--c-yellow) 橙调 / done var(--c-green) / cancelled var(--c-ink-3) 灰）+ 时间 + 金额
  - 详情：商品 snapshot 区 + 数量 / 总价 / 地址 snapshot / **状态时间线**（业务组件 BizOrderTimeline，含 5 节点）/ 物流模块占位（USER-103 未实现 → 显示「跨境物流详情待完善」+ 国内单号字段如有展示）/ 「联系客服」CTA
  - **状态 created 时**：显示「继续支付」CTA → 调 PAY-101 重新拉支付参数（同 bizOrderId 幂等）+「取消订单」CTA
  - **严禁** 显示「申请退款」按钮（PAY-103 §AC 4 锚定）
- [ ] **AC 5**：admin 端 `GET /system/gz/ord/order/list` 接口（owner / 运营角色）：
  - 参数：page / size / status / userPhone / orderNo
  - 查询关联 gz_user 拿手机号
- [ ] **AC 6**：admin 端 UI 基础（复用 ADMIN-103 骨架）：
  - `views/gz-ord/order/index.vue`（列表，复用 BizTable）
  - `views/gz-ord/order/detail.vue`（详情，复用 ADMIN-103 + 加 cn_logistics_no 录入字段 + 「申请退款」按钮接入 PAY-103）
  - menu_id 9010 预购订单管理（9000 ORD 段下）+ 9011 列表 / 9012 详情查看 / 9013 国内物流录入 / 9014 申请退款（owner）
- [ ] **AC 7**：admin `POST /system/gz/ord/order/cn-logistics` 接口：
  - 参数 orderId + cnLogisticsNo
  - 校验当前 status 为 in_logistics（仅物流中订单可录入国内单号）
  - UPDATE 单号 + UPDATE logistics_status='in_cn_logistics'
  - @Log 操作日志
- [ ] **AC 8**：单测：
  - C 端列表 status 过滤映射
  - 详情接口越权校验
  - 状态时间线推导逻辑（业务组件单测）
  - 共 ≥ 3 个测试方法
- [ ] **AC 9**：i18n 强制（订单状态 chip 文案 / tab 名 / 详情字段名）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-ord/`
  - `controller/applet/GzOrdOrderMpController.java`（ORD-104 已建，加 listForMp 方法）
  - `controller/admin/GzOrdOrderAdminController.java`（路径 `/system/gz/ord/order`）
  - `service/IGzOrdOrderService.java` 加 listForMp / listForAdmin / updateCnLogisticsNo 方法
  - VO 扩展（OrderListItemVO / OrderDetailVO / OrderTimelineVO）
  - menu_id 9010-9014（CLAUDE.md §6 ORD 段）
- **小程序**：
  - `pages/user/order-list.vue` + `pages/user/order-detail.vue`
  - `components/biz/BizOrderTimeline.vue`（业务组件 5 节点时间线）
  - `composables/useOrderList.ts`（分页 + 下拉刷新封装）
  - `api/gz-ord.ts` 加 getOrderListForMp / 复用 ORD-104 的 getOrderDetail
  - 会员中心页面（USER-101 已建）加「我的订单」入口 cell
  - i18n 字典扩展
- **Admin 前端**：`code/main/plus-ui/src/views/gz-ord/order/`
  - `index.vue` + `detail.vue`（复用 ADMIN-103 已有结构）
  - `api/gz-ord/order.ts`
- **测试**：mvn 单测 + 微信开发者工具走会员中心 → 订单列表 → 详情流程

## 备注

### 强约束

1. **C 端无退款入口**（PAY-103 §AC 4 + 合同 §4.5）— 详情页严禁出现「申请退款」按钮，仅「联系客服」
2. **C 端继续支付幂等** — 复用 PAY-101 same bizOrderId（重复 createOrder 走幂等）
3. **物流模块占位** — USER-103 在 D09 / D10 实现，本 ticket 仅留入口 + 空状态
4. **越权校验** — 详情接口必校 user_id 等于当前登录用户
5. **menu_id 9010-9014**（CLAUDE.md §6）
6. **business_line='preorder'** 列表过滤兜底（虽然 V1.1 首日仅预购单，但后续 GACHA / 拼豆 future 进入同表 — 本 ticket 不混查）
   - **决策**：gz_ord_order 仅存预购订单；GACHA 订单后续 D09 落在 gz_gacha_order；不同表不混
   - 因此本 ticket 列表查询不需 business_line 过滤（表名已分流）
7. **i18n 强制**

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 预购 / 扭蛋订单分表（gz_ord_order vs gz_gacha_order） | 业务字段差异大（扭蛋无地址、有奖品池关联）；表分离查询简单 |
| D2 | 状态时间线前端推导（不存独立表） | 简单场景；状态字段 + 时间字段已足够；复杂场景再加 order_status_log |
| D3 | admin 列表关联 gz_user 拿手机号 | 客服查单常用入口 |
| D4 | 物流模块占位 + USER-103 后续接入 | V1.1 首日聚焦预购骨架打通，物流详情拆到 D10 |
| D5 | mp 详情「继续支付」复用 PAY-101 幂等 | 不新增接口，统一支付入口 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 大量已 paid 订单状态停 paid（运营忘记录入物流）→ 用户不知何时发货 | admin 端加监控告警（paid > 7 天未 in_logistics 的订单数量）+ 运营 SOP |
| R2 | 越权访问其他用户订单 | AC 2 强校验 user_id |
| R3 | mp 列表分页时下拉刷新与上拉加载同时触发 | useOrderList composable 防抖 + 加载中态互斥 |
| R4 | admin 国内物流单号录入错误（无格式校验） | 本 ticket 不强约束格式（顺丰 / 中通 / 圆通 单号格式各异）；后续 D10 物流模块完善时加正则 |
| R5 | 物流模块空状态文案 i18n 漏译 | testing-human 必查 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
