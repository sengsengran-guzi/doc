# GZ-USER-102 — mp 订单详情统一布局

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M5 §关键页面 §订单详情
**关联拆解**: doc/02-需求拆解.md §3.4 第 862-872 行
**关联 mockup**: design/mockup/order-detail.html ⚠️ 当前文件是 7 节点时间线版本，**作废**；本 ticket 按 doc/12 §MP-ORD-DETAIL（物流 2 态简化）实施，旧 mockup 仅参考顶部商品块 / 订单信息块 / 操作区结构，不逐像素
**关联 ADR**: —（C1 物流 2 态裁定见 doc/10 §9 跨境物流权威状态 / doc/11 §8.1 / doc/12 §MP-ORD-DETAIL）
**依赖**: GZ-USER-101（订单聚合统一接口，本日上游）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：
  - doc/10-业务流权威图.md **§9 跨业务订单聚合 + 跨境物流流** §跨业务订单聚合（V1.1 GZ-USER-101/102）+ §跨境物流权威状态（C1 2 态 + 终态）+ §状态机（logistics_status）+ §关键节点 N3（U 进订单详情）
  - doc/10-业务流权威图.md **§8 扭蛋机抽奖全流程** §状态机（draw_status + gacha_order_status）+ §关键节点 N6/N7（中奖物 snapshot 入库口径）——扭蛋差异块字段来源
- **字段表**：
  - doc/11-字段权威表.md **§8.1 `gz_unified_order_view`**（详情字段口径完全复用 USER-101 的统一 VO 字段名）+ §8.2 business_status → UI 统一状态映射
  - doc/11-字段权威表.md **§6.3 `gz_ord_order`**（预购订单 `product_snapshot_json` + `sku_snapshot_json` 字段口径）
  - doc/11-字段权威表.md **§7.4 `gz_gacha_order`**（扭蛋衍生订单 `prize_snapshot_json` + `machine_snapshot_json` 字段口径）+ §7.3 `gz_gacha_draw`（snapshot 入库源）
  - doc/11-字段权威表.md **附录 A.5 / A.6 / A.7 / A.10**（业务状态字典 `gz_ord_business_status` / `gz_gacha_business_status`、物流字典 `gz_logistics_status`、稀有度字典 `gz_gacha_rarity`）
- **UI 参考**（mp ticket）：doc/12 §MP-ORD-DETAIL §页面结构（统一布局：状态卡 / 商品信息 / 物流模块 / 订单信息 / 底部 CTA）+ §跳转关系。视觉走 C 日漫海报浓墨：`Biz*` 组件 + `var(--c-*)`，doc/tokens.md + doc/13；稀有度边框/光晕用 doc/tokens.md §1.4 稀有度色 + doc/13 §3.2（V1.1 待建原子）；旧 mockup 仅布局参考

## What

mp 端订单详情统一页 `pages/me/order-detail.vue`：自上而下渲染 状态卡 → 商品信息块 → 物流模块（占位，USER-103 实装）→ 订单信息块 → 底部 CTA。后端补一个详情接口，返回值 = USER-101 统一 VO + 业务专属差异字段（扭蛋 / 预购各一组）。**复用 USER-101 的统一 view-model**，详情只比列表多带业务差异 snapshot 字段。

## AC（验收标准）

- [ ] **AC 1**：后端 mp 端 `GET /app/gz/user/orders/{orderNo}` 详情接口（sa-token-app 权限）；后端强制 `where user_id = ${current_user_id}`，非本人订单返 403（前端 hide 不算防御）
- [ ] **AC 2**：返回 VO = USER-101 `UnifiedOrderVO` 字段（`orderNo` / `businessType` / `productSnapshot`(JSON) / `totalAmountCent` / `businessStatus` / `logisticsStatus` / `cnCarrierCode` / `cnTrackingNo` / `addressSnapshot`(JSON) / `createdAt` / `paidTime` / `deliveredTime`）**追加业务专属差异字段**：
  - 扭蛋（`businessType=gacha`）：`gachaSnapshot = { prizeName, prizeImageId, rarity, machineName, paidTime }`（来源 `gz_gacha_order.prize_snapshot_json` + `machine_snapshot_json`，字段口径见 doc/11 §7.4）
  - 预购（`businessType=preorder`）：`preorderSnapshot = { productName, productImageId, skuSpec, deadlineText, arrivalText, unitPriceCent, qty }`（来源 `gz_ord_order.product_snapshot_json` + `sku_snapshot_json`，字段口径见 doc/11 §6.3）
- [ ] **AC 3**：差异字段一律从订单表的 `*_snapshot_json` 列直读，**不实时 join 主数据表**（`gz_gacha_machine` / `gz_gacha_prize` / `gz_ord_product` / `gz_ord_sku`）；图片字段返回 `image_id`（FK gz_file_object），**不返回裸 url**（前端换签名 URL，与 USER-101 同口径）
- [ ] **AC 4**：mp 端 `pages/me/order-detail.vue` 路由 `?id=<orderNo>`，调上述接口，统一布局**自上而下五段、顺序不可变**：
  1. nav-bar 返回 + 标题"订单详情"
  2. **状态卡**：业务状态 label + 颜色 chip。状态文案走 doc/11 §8.2 映射 + 字典（预购 `gz_ord_business_status` / 扭蛋 `gz_gacha_business_status`），**不在前端硬编码状态中文**
  3. **商品信息块**（`BizProductSnapshot`，按 `businessType` 分支渲染）：
     - 扭蛋：获得物图（`prizeImageId` 换 URL，带稀有度边框）+ 获得物名 + 来源扭蛋机名 + 稀有度 chip + 获得时间（`paidTime`）
     - 预购：商品图（`productImageId` 换 URL）+ 商品名 + SKU 规格 + 数量 + 单价（`unitPriceCent` 转元）
  4. **物流模块**：本 ticket 仅放占位 `<BizLogisticsCard :logisticsStatus :cnCarrierCode :cnTrackingNo :deliveredAt />`，props 从详情接口透传；卡片 UI 由 USER-103 实装（本 ticket 不渲染物流卡内部）
  5. **订单信息块**：订单号 + 创建时间 + 支付时间 + 收货地址 snapshot（扭蛋未补地址时该字段可空，按空兜底文案"中奖后补充地址"）
  6. **底部 fixed CTA 区**：按业务 + 状态显示（见 AC 6 / AC 7）
- [ ] **AC 5**：盲盒语义（仅扭蛋差异块）—— UI 可见文案 / i18n key 用 **获得物 / 获得时间 / 出现概率 / 稀有度**；**禁** 中奖 / 抽奖 / 开奖（doc/10 §8 盲盒语义约束）。后端 VO 字段名可保留 `draw`/`prize`（不强制改库）
- [ ] **AC 6**：底部 CTA 按状态条件渲染：
  - `in_china_dispatching` 态：显示"确认收货"按钮（USER-104 真实化，本 ticket 先置灰 disabled + tooltip"USER-104 完工后可用"）
  - 任何未终态订单：固定展示**纯文案** "如需退款请联系客服"（**无退款按钮**——退款 V1.1 仅全额，C 端无退款入口，铁律）
- [ ] **AC 7**：已签收（`logisticsStatus=delivered` / `businessStatus=delivered`）/ 已退款（`refunded`）订单：底部无操作按钮，详情只读
- [ ] **AC 8**：i18n 全覆盖（`order.detail.*`）；状态 / 物流 / 稀有度文案走字典编码（doc/11 §A.5 / §A.6 / §A.7 / §A.10），不混 emoji
- [ ] **AC 9**：单测可选；联调验：admin 端造 1 扭蛋衍生订单 + 1 预购订单 → mp 端分别进详情，验差异块字段（扭蛋 5 字段 / 预购 7 字段）渲染正确 + 非本人订单访问返 403
- [ ] **AC 10: Tier 2 入口可达**（mp ticket 强制，CLAUDE.md §8.3）— Kevin 从 mp 已上线「我的」→「我的订单」（USER-101/列表入口）点 1 张订单卡进入本详情页。
  - USER-101 列表卡 → MP-ORD-DETAIL?id=<orderNo>（doc/12 §MP-ORD-LIST §跳转关系）即现成路径
  - 如本 ticket spawn 时「我的订单」列表入口尚未接通 → 加临时入口到 `pages/index/index.vue` 跳本详情页（mock orderNo），注释 `<!-- TODO(Tier2-entry-temp): GZ-USER-102, remove when GZ-USER-101 mp 列表入口接通 -->`

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-user/`
  - `controller/applet/GzUserOrderMpController.java`（USER-101 已建，本 ticket 加 `getOrderDetail(orderNo)` 方法）
  - `service/IGzUnifiedOrderService.java` + impl 加 `getDetail(orderNo, userId)`：按 `orderNo` 前缀（`GACHA-` / `PREORD-`，doc/11 §6.3 / §7.4 命名规范）判断 businessType → 查对应订单表 → 校验归属 → 解 `*_snapshot_json` 拼差异字段
  - `domain/vo/UnifiedOrderDetailVO.java`（继承 / 组合 `UnifiedOrderVO` + `gachaSnapshot` / `preorderSnapshot` 字段）
  - **不落新 DDL**（消费 USER-101/D09 已建的 `gz_ord_order` + `gz_gacha_order` 表）
- **小程序**：`code/main/miniapp/src/`
  - `pages/me/order-detail.vue`（新建）
  - `api/gz-user.ts` 加 `getOrderDetail(orderNo)`
  - `components/biz/BizOrderHeader.vue`（顶部状态卡，复用 USER-101 列表用过的 chip 逻辑）
  - `components/biz/BizProductSnapshot.vue`（商品块，按 businessType 多态渲染，复用 USER-101 view-model）
  - `components/biz/BizLogisticsCard.vue`（**占位**，USER-103 实装；本 ticket 只接 props）
  - i18n：`order.detail.*` 进 `zh_CN.ts` / `en_US.ts`
- **测试**：mp 联调 + 后端归属校验（403）

## 备注

### 强约束

1. **统一布局五段顺序不可变**：状态卡 → 商品 → 物流 → 订单 → CTA（doc/12 §MP-ORD-DETAIL 锚定）
2. **复用 USER-101 view-model**：详情接口返回 = 列表 VO + 业务差异字段；mp 端商品块多态渲染逻辑与 USER-101 列表卡同一份（ADMIN-103 admin 端订单详情也复用本 view-model，doc D10 README §6）
3. **业务差异块限定字段**：扭蛋 5 字段（prizeName / prizeImageId / rarity / machineName / paidTime）/ 预购 7 字段（productName / productImageId / skuSpec / deadlineText / arrivalText / unitPriceCent / qty），不超出
4. **snapshot 字段从订单表 `*_snapshot_json` 直读**（D09 已 snapshot），**不**实时 join 主数据表 —— 主数据变了订单显示要冻结在下单时态；图片走 `image_id` 不存裸 url（doc/11 命名规范）
5. **退款铁律**：C 端无退款按钮 / 无金额 input，仅纯文案"如需退款请联系客服"（退款 V1.1 仅全额，入口在 admin owner 端 `gz:pay:refund:apply`）
6. **盲盒语义**（仅扭蛋）：UI 文案 / i18n key 用 获得物 / 获得时间 / 出现概率 / 稀有度；禁 中奖 / 抽奖 / 开奖（后端字段可保留 draw）
7. **Biz\* 组件 + `var(--c-*)`**：只用 `src/components/biz/Biz*` 原子组件，不直接撒 `<wd-*>`；视觉走 C 设计系统 token（主 CTA = `var(--c-red)`，成功态 chip = `var(--c-green)`），稀有度边框/光晕用 doc/tokens.md §1.4 稀有度色（`--r-ssr` 等），不硬编码 hex
8. **i18n 状态文案走字典**：预购 `gz_ord_business_status` / 扭蛋 `gz_gacha_business_status` / 物流 `gz_logistics_status` / 稀有度 `gz_gacha_rarity`，前端不硬编码状态中文
9. **物流模块只留占位 prop**：本 ticket 不实装物流卡 UI（USER-103 才做）；`BizLogisticsCard.vue` 内部由 USER-103 填充，本 ticket 仅传 props 接入点

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 详情接口 = USER-101 列表 VO + 业务专属差异字段 | 列表 / 详情字段语义对齐，前端可直接复用 view-model；详情仅多带 5-7 个 snapshot 字段 |
| D2 | businessType 走 orderNo 前缀（`GACHA-` / `PREORD-`）| doc/11 §6.3 / §7.4 已锁定订单号命名规范，省一次 DB 探测 |
| D3 | snapshot 直读不实时 join | 用户视角订单应冻结在下单时态，主数据修改不影响历史订单（doc/11 §6.3 / §7.4 snapshot 设计意图）|
| D4 | 物流卡占位 + props 接入点 | USER-103 实装时只填组件内部，不动 detail 页主体；解耦串行依赖 |
| D5 | "确认收货"本 ticket 置灰 | USER-104 才真实化签收逻辑；本 ticket 先占位，不阻塞串行链 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 上游 `gz_ord_order` / `gz_gacha_order` 表或 snapshot 列未实际落地（V1.1 从零起，不假设 D08/D09 已 merge）| **§0 自检 grep migration 目录确认上游表实际存在**：`ls .../db/migration/ \| grep -E 'GZ-ORD-104\|GZ-GACHA-104'` + `grep -rl 'product_snapshot_json\|prize_snapshot_json\|sku_snapshot_json\|machine_snapshot_json' .../db/migration/`；缺则 STOP 回 D09 收尾，本卡不开工 |
| R2 | snapshot JSON 字段名 / 结构与 doc/11 §6.3 / §7.4 不一致 | §0 自检抽一条 row `SELECT product_snapshot_json FROM gz_ord_order LIMIT 1` / `SELECT prize_snapshot_json,machine_snapshot_json FROM gz_gacha_order LIMIT 1` 比对字段名；不一致 → 改源头（回 D09 或修 doc/11，CLAUDE.md §9.5 #1）|
| R3 | USER-101 统一 VO 字段名变动（串行上游）| 详情 VO 直接继承 / 组合 USER-101 `UnifiedOrderVO`，跟随其字段，避免重复定义漂移 |
| R4 | 未登录 / 越权拿别人订单 | AC 1 后端 `where user_id` 强约束 + 归属校验返 403；前端隐藏不算防御 |

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
