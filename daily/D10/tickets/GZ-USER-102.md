# GZ-USER-102 — 订单详情统一布局

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M5 §关键页面 §订单详情
**关联拆解**: doc/02-需求拆解.md §3.4 第 862-872 行
**关联 mockup**: design/mockup/order-detail.html ⚠️ mockup 当前是 7 节点时间线版本，**作废**；本 ticket 按 doc/12 §MP-ORD-DETAIL（物流 2 态简化）实施，mockup 仅参考顶部商品块 + 订单信息块 + 操作区结构
**关联 ADR**: —（C1 裁定见 doc/10 §9 / doc/11 §6.4 / doc/12 §MP-ORD-DETAIL）
**依赖**: GZ-USER-101 ✅(D10)

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md **§9 跨业务订单聚合 + 跨境物流流** §关键节点 N3（U 进订单详情）+ §状态机（logistics_status）+ §异常分支 E1/E2/E3
- **字段表**：doc/11-字段权威表.md **§8.1 `gz_unified_order_view`**（详情字段口径完全复用列表字段）+ §6.3 `gz_ord_order`（预购订单 + 关联 SKU snapshot 字段）+ §7.3 `gz_gacha_draw`（抽奖记录 — 详情显示中奖物时消费）+ §7.4 `gz_gacha_order`（扭蛋衍生订单）+ §8.2 business_status → UI 统一状态映射 + §A.7 物流字段口径
- **UI 参考**：doc/12 §MP-ORD-DETAIL §页面结构（统一布局五段：状态卡 / 商品信息 / 物流模块 / 订单信息 / 底部 CTA）+ §跳转关系。视觉走 C 日漫海报浓墨：Biz* 组件 + var(--c-*)，doc/tokens.md + doc/13；旧 mockup 仅布局参考

## What

mp 端订单详情统一页：顶部商品信息 → 状态时间线 → 物流模块（USER-103 落） → 国内单号 → 操作区。**按业务类型展示差异块**：扭蛋显示中奖物 snapshot + 机器名 + 稀有度；预购显示规格 + 截止日 / 到货日 snapshot。后端补一个详情接口（基于 USER-101 的统一 VO + 业务专属字段）。

## AC（验收标准）

- [ ] **AC 1**：mp 端 `GET /app/gz/user/orders/{orderNo}` 详情接口；权限同 USER-101（`where user_id = current_user_id`，非本人订单 → 403）
- [ ] **AC 2**：返回字段在 USER-101 统一 VO 基础上**追加业务专属字段**：
  - 扭蛋（businessType=gacha）：`drawSnapshot = {prizeName, prizeCover, rarity, machineName, drawnAt}`
  - 预购（businessType=preorder）：`skuSnapshot = {productName, productCover, skuSpec, productDeadline, productArrivalAt, qty}`
- [ ] **AC 3**：mp 端 `pages/me/order-detail.vue` 路由 `?id=<orderNo>`，调上述接口；统一布局**自上而下**：
  1. nav-bar 返回 + "订单详情"
  2. 顶部**状态卡**（业务状态文案 + 颜色 chip）：扭蛋"已抽待发" / "已完成" / 预购"待发货" / "运输中" / "已签收"等，按 doc/11 §8.2 映射
  3. **商品信息块**：扭蛋显示中奖物 thumb（带稀有度边框）+ 机器名 + 中奖时间；预购显示商品 thumb + SKU 规格 + 数量
  4. **物流模块**（USER-103 实施，本 ticket 留 `<BizLogisticsCard :status :carrier :trackingNo />` 占位 props 接入点）
  5. 订单信息块：订单号 + 创建时间 + 支付时间 + 收货地址 snapshot
  6. 底部 fixed CTA 区：按业务 + 状态显示（参考 doc/12 §MP-ORD-DETAIL §页面结构 第 6 项）
- [ ] **AC 4**：扭蛋差异块详情字段从 `gz_gacha_draw` join 拿（drawSnapshot 字段对应 prize_name / prize_cover / rarity / machine_name / drawn_at —— D09 GACHA-104 已在订单表里 snapshot 这几个字段，本 ticket 直读，不重新 join 主数据表）
- [ ] **AC 5**：预购差异块详情字段从 `gz_ord_order` 的 snapshot 字段拿（D09 ORD-104 落 sku_snapshot JSON 字段，含 productName / sku_spec / deadline / arrival_at）
- [ ] **AC 6**：未签收（business_status != closed/delivered）订单底部 CTA：扭蛋"申请退款（特例走客服）"；预购"确认收货"（按钮置灰，待 USER-104 真实化）+ "申请退款（特例走客服）"
- [ ] **AC 7**：已签收 / 已退款订单底部无 CTA，详情只读
- [ ] **AC 8**：i18n 全覆盖（`order.detail.xxx`）；状态文案走 doc/11 §A.5 / §A.6 字典编码
- [ ] **AC 9**：单测可选；联调验：admin 端造 1 扭蛋订单 + 1 预购订单 → mp 端进详情验差异块字段渲染正确

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-user/`
  - `controller/applet/GzUserOrderMpController.java`（USER-101 已建，本 ticket 加 `getOrderDetail(orderNo)` 方法）
  - `service/IGzUnifiedOrderService.java` + impl 加 `getDetail(orderNo, userId)`（按 orderNo 前缀判断 businessType → 分别 join 业务专属 snapshot 字段）
  - `domain/vo/UnifiedOrderDetailVO.java`（继承 UnifiedOrderVO + 增加 drawSnapshot / skuSnapshot 字段）
  - **不落新 DDL**
- **小程序**：`code/main/miniapp/src/`
  - `pages/me/order-detail.vue`（新建）
  - `api/gz-user.ts` 加 `getOrderDetail(orderNo)`
  - `components/biz/BizOrderHeader.vue`（顶部状态卡，复用 USER-101 list 用过的 chip 组件）
  - `components/biz/BizProductSnapshot.vue`（商品块，按 businessType 分支渲染）
  - `components/biz/BizLogisticsCard.vue`（**占位**，USER-103 实装）
- **测试**：mp 联调

## 备注

### 强约束

1. **统一布局五段顺序不可变**：状态卡 → 商品 → 物流 → 订单 → CTA（doc/12 §MP-ORD-DETAIL 锚定）
2. **业务差异块限定字段**：扭蛋 5 字段（prizeName/cover/rarity/machineName/drawnAt） / 预购 6 字段（productName/cover/skuSpec/deadline/arrivalAt/qty），不超出
3. **snapshot 字段从订单表直读**（D09 已 snapshot），**不**实时 join 主数据表（主数据变了订单显示要保持下单时的状态）
4. **Biz* 组件（不直接撒 wd-*）+ var(--c-*)**：视觉走 C 设计系统 token（var(--c-*)，主 CTA = var(--c-red)），状态 chip 用 c 变量（选中/价格 var(--c-red)、成功 var(--c-green)），不硬编码 hex（doc/tokens.md）
5. **物流模块只留占位 prop**：本 ticket 不实装物流卡 UI（USER-103 才做）；BizLogisticsCard.vue 内部 USER-103 实施时再填充
6. **i18n 状态文案走字典**：doc/11 §A.5 `gz_preorder_order_status` + §A.6 `gz_gacha_draw_status` / `gz_gacha_order_status` 字典 — 不在前端硬编码状态中文

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 详情接口返回 = 列表 VO + 业务专属差异字段 | 列表 + 详情字段语义对齐，前端 store 可直接更新；详情多带 5-6 字段而已 |
| D2 | 业务类型判断走 orderNo 前缀（`GACHA-` / `PREORD-`）| D08/D09 已锁定 orderNo 命名规范（doc/10 §6.N1）；省一次 DB 查询 |
| D3 | snapshot 字段直读不实时 join | 用户视角订单显示应"冻结在下单时态"，主数据修改不应影响历史订单 |
| D4 | 占位组件 + props 接入点 | USER-103 实施时只填充组件内部，不动 detail 页主体；解耦 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | D09 订单表的 snapshot 字段命名 / JSON 结构未对齐 doc/11 | §0 自检：`DESC gz_ord_order` 验 sku_snapshot 列存在 + 抽一条 row `SELECT sku_snapshot FROM gz_ord_order LIMIT 1` 看 JSON 字段名；缺则回 D09 修 |
| R2 | 扭蛋订单 drawSnapshot 字段未在 D09 落 | 同 R1，校验 `gz_gacha_order` 的 prize_snapshot 列；缺则回 D09 修 |
| R3 | 未登录 / 越权拿别人订单 | AC 1 明确后端 `where user_id` 强约束；前端隐藏不算 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
