# GZ-ORD-105 — 预购订单查询（C 端列表 + 详情 + admin 只读基础）

**优先级**: P1
**复杂度**: S
**关联 PRD**: doc/02-prd.md M3 §用户操作流程 步骤 7（查订单）+ M5 §进入会员中心 §我的订单 tab
**关联拆解**: doc/02-需求拆解.md §3.2（预购订单查询）
**关联 mockup**: design/mockup/order-list.html + order-detail.html（**仅布局参考**；order-detail.html 当前是 7 节点时间线 ⚠️ 已作废，按 C1 物流 2 态 + 终态实现；mp 视觉以 C 系统为准 doc/13；admin 走 ruoyi 默认）
**关联 ADR**: —（C1 物流 2 态裁定记 doc/10 §9，未单列 ADR；本卡不涉及 ADR-0005 合同对齐）
**依赖**: GZ-ORD-104 ✅（建 `gz_ord_order` + snapshot 字段 + `logistics_status` 默认 `in_japan`）+ GZ-USER-004 占位页 ✅（会员中心「我的订单」tab 占位结构，本卡把占位换成预购真数据）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

> 业务流 + 字段表是实施蓝图，缺引用 = 凭字面猜实现 = 翻车前兆。UI 索引在设计冻结期为视觉参考。

- **业务流**：
  - doc/10-业务流权威图.md **§7 预定货品全流程**（预购订单状态机 `created → paid → in_logistics → delivered`，delivered = 终态，无独立 closed — §7 Q7.2 裁定）
  - doc/10-业务流权威图.md **§9 跨业务订单聚合 + 跨境物流流**（C1 物流 2 态 + 终态 `in_japan` / `in_china_dispatching` / `delivered`，与 business_status 并行独立；N3 用户看详情 / N4 复制单号）
- **字段表**：
  - doc/11-字段权威表.md **§6.3 `gz_ord_order`**（字段口径：`order_no` / `business_status` / `logistics_status` / `total_amount_cent` / `*_snapshot_json` / `paid_time` / `delivered_time` / `cn_carrier_code` / `cn_tracking_no` / `cn_dispatched_at`）
  - doc/11-字段权威表.md **附录 A.5**（预购 business_status → 中文 label + mp 统一 chip 映射）+ **附录 A.7**（logistics_status 2 态 + 终态字典 `gz_logistics_status`）
  - doc/11-字段权威表.md **§8.2 business_status + logistics_status → UI 统一状态 chip 映射**（mp 端兜底逻辑，不入 DB）
- **UI 参考**（设计冻结期）：
  - mp ticket：`design/mockup/order-list.html` + `order-detail.html`（视觉参考，不逐像素；order-detail 7 节点时间线已作废，按物流 2 态卡实现）+ doc/12-UI-权威索引.md §MP-ORD-LIST / §MP-ORD-DETAIL
  - admin 部分：N/A（设计冻结期 admin 走 ruoyi 默认）

## What

用户在会员中心「我的订单」tab 查预购订单列表 + 详情（C 端）；admin 端提供预购订单只读列表 + 详情查询基础（运营/客服查单用）。详情展示商品 snapshot + business_status 状态时间线（delivered 为终态，去 closed）+ 物流 `logistics_status` 2 态 + 终态独立并行展示 + 国内快递公司/单号（如有）+「联系客服」文案（C 端无退款入口）。**本卡仅订单查询；物流推进/录单号 = GZ-ADMIN-104（下沉 mp，下游），退款 = GZ-PAY-103，均不在本卡。**

## AC（验收标准）

- [ ] **AC 1**：mp `GET /app/gz/ord/order/list` 列表接口：
  - sa-token 校验 + 取当前 `user_id`（同租户 1001）
  - 参数：`pageNum` / `pageSize` / `chipStatus`（用户视角统一 chip：`all` / `to_pay` / `to_ship` / `shipping` / `done` / `cancelled` / `refunded`）
  - chip → 后端过滤映射严格按 doc/11 §8.2：
    - `to_pay` = `business_status='created'`
    - `to_ship` = `business_status='paid'`（即 `logistics_status='in_japan'`）
    - `shipping` = `business_status='in_logistics'`（即 `logistics_status='in_china_dispatching'`）
    - `done` = `business_status='delivered'`
    - `cancelled` = `business_status='cancelled'`；`refunded` = `business_status='refunded'`
    - `all` = 不加 business_status 过滤
  - 查询 `WHERE user_id=? [AND business_status IN (...)]` ORDER BY `created_at` DESC，分页
  - 每条返回列表 VO：`order_no` / 商品名 + 主图 image_id（从 `product_snapshot_json` 取，不查商品表）/ 规格名 / `qty` / `total_amount_cent` / `business_status` / `logistics_status` / 统一 chip label / `created_at`
- [ ] **AC 2**：mp `GET /app/gz/ord/order/{id}` 详情接口：
  - **越权校验**：`order.user_id` ≠ 当前登录 user → 返回 403 / 业务错误（不返回他人订单数据）
  - 返回完整详情 VO：商品 snapshot（名/主图 image_id/规格名/单价分）+ `qty` + `total_amount_cent` + 地址 snapshot（recipient/mobile/完整地址，从 `address_snapshot_json`）+ `business_status` + 状态时间线节点 + `logistics_status` + `cn_carrier_code` + `cn_tracking_no` + `paid_time` / `delivered_time` / `created_at`
  - **状态时间线推导**（前后端约定 4 节点，**无 closed**，delivered = 终态）：`created`（用 `created_at`）→ `paid`（用 `paid_time`）→ `in_logistics`（物流推进，节点时间取 `cn_dispatched_at`）→ `delivered`（用 `delivered_time`）；当前 `business_status` 之前的节点高亮已发生，之后置灰未发生；`cancelled` / `refunded` 单独显示，不走时间线
- [ ] **AC 3**：mp 端会员中心「我的订单」tab 接入真数据（GZ-USER-004 占位结构改造）：
  - GZ-USER-004 已建 3 tab（全部/扭蛋/预购）占位；本卡把「预购」tab + 「全部」tab 的预购数据从占位改为调 AC 1 接口拉真数据（扭蛋 tab 仍占位，D09 GACHA 接入）
  - 列表卡点击 → 跳详情页携 `id`
- [ ] **AC 4**：mp 端 `pages/me/orders.vue`（订单列表，GZ-USER-004 路由）+ `pages/me/order-detail.vue`（详情）：
  - 列表卡：商品 thumb + 商品名 + 规格 + 数量 + 金额（元，`total_amount_cent / 100`）+ 统一状态 chip（C token 配色，按 §8.2 映射文案：待支付/待发货/运输中/已完成/已取消/已退款）+ 时间
  - 详情：商品 snapshot 区 + 数量/总价（元）+ 地址 snapshot 区 + **状态时间线**（业务组件 `BizOrderTimeline`，4 节点，去 closed）+ **物流模块**（独立卡，并行展示，**非占位**）：
    - `logistics_status='in_japan'`：文案「商品在日本备货中」+ 副文，无可操作元素
    - `logistics_status='in_china_dispatching'`：显示快递公司中文名（`cn_carrier_code` 经字典 `gz_express_carrier` 翻译）+ 快递单号 `cn_tracking_no` + 「复制单号」按钮（`uni.setClipboardData`）+ 提示「请到快递公司官方渠道查询轨迹」
    - `logistics_status='delivered'`：显示「已签收」
  - **`business_status='created'` 时**：显示「继续支付」CTA（复用 GZ-PAY-101 same `order_no` 幂等拉支付参数）+「取消订单」CTA（仅 `created` 态可见）
  - **严禁** 出现「申请退款」按钮（PAY-103 §强约束 + 合同 §4.5）；仅文案「如需退款请联系客服」
- [ ] **AC 5**：admin `GET /system/gz/ord/order/list` 列表接口（只读，运营/客服）：
  - 参数：`pageNum` / `pageSize` / `businessStatus` / `userPhone`（模糊）/ `orderNo`（模糊）
  - 关联 `gz_user` 取手机号显示（同租户 1001）
  - `@SaCheckPermission("gz:ord:order:list")`
- [ ] **AC 6**：admin `GET /system/gz/ord/order/{id}` 详情接口（只读）+ admin UI 只读基础：
  - `@SaCheckPermission("gz:ord:order:query")`，返回订单全字段 + snapshot 解析 + logistics 字段 + 用户手机号
  - `views/gz-ord/order/index.vue`（列表，复用 BizTable，从零建）+ `views/gz-ord/order/detail.vue`（详情只读，从零建）
  - **本卡 admin 仅订单查询**：不含物流推进/录单号写接口（= GZ-ADMIN-104，下沉 mp，下游）、不含退款按钮（= GZ-PAY-103）
  - menu_id 走 **9100 段（GZ-ORD admin）**：9110 预购订单管理（目录）/ 9111 `gz:ord:order:list`（列表）/ 9112 `gz:ord:order:query`（详情查看）；DDL seed 仅授 owner（100）
- [ ] **AC 7**：单测（≥ 3 个测试方法）：
  - C 端 chip → business_status 过滤映射（覆盖 to_pay/to_ship/shipping/done 至少 4 个分支）
  - 详情接口越权校验（他人订单返回拒绝，不泄漏数据）
  - 状态时间线推导逻辑（给定 business_status + 各时间字段 → 节点高亮/置灰序列正确，4 节点无 closed）
- [ ] **AC 8**：i18n 强制——订单状态 chip / tab 名 / 物流态文案 / 时间线节点名 / 详情字段名全走 `t('gz.ord.xxx')` + zh-CN（默认）/ en-US；不混 emoji
- [ ] **AC 9: Tier 2 入口可达**（mp ticket 强制，CLAUDE.md §8.3）— Kevin 从**会员中心首页（「我的」tab）→「我的订单」cell** 点 1 次到达 `pages/me/orders.vue`，切到「预购」tab 见真数据列表，点任一卡 1 次到达 `pages/me/order-detail.vue`。
  - 入口为 GZ-USER-004 已上线的会员中心「我的订单」cell（现成路径，**无需临时入口**）；本卡只把该 tab 的占位换成真数据 + 接上详情页跳转。

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-ord/`
  - `controller/applet/GzOrdOrderMpController.java`（GZ-ORD-104 已建详情接口 → 加 `list` 方法；本卡查询逻辑）
  - `controller/admin/GzOrdOrderController.java`（路径 `/system/gz/ord/order`，只读 list + detail；`@SaCheckPermission`）
  - `service/IGzOrdOrderService.java` + impl 加 `pageForMp` / `getDetailForMp`（含越权校验）/ `pageForAdmin` / `getDetailForAdmin` 方法
  - VO：`OrdOrderListItemVo` / `OrdOrderDetailVo` / 时间线 `OrdOrderTimelineNodeVo`（snapshot 字段从 `*_snapshot_json` 反序列化，不查商品表）
  - 统一 chip 映射 + 时间线推导放可单测 service / util（不写在 controller）
  - DDL（仅 admin 菜单 seed，**无新建业务表** —— gz_ord_order 由 ORD-104 建）：`ruoyi-admin/src/main/resources/db/migration/V202606080500__GZ-ORD-105-admin-order-query-menu.sql`（menu_id 9110/9111/9112 + perm `gz:ord:order:{list,query}` + 仅 owner 100 授权；时间戳 > 当前最大 V202606051200）
- **小程序**：`code/main/miniapp/`
  - `pages/me/orders.vue`（GZ-USER-004 占位页改真数据）+ `pages/me/order-detail.vue`（新建详情页）
  - `components/biz/BizOrderTimeline.vue`（业务组件，4 节点时间线，C token，`Biz` 前缀 easycom）
  - `composables/useOrderList.ts`（分页 + 下拉刷新 + 上拉加载，加载态互斥防抖）
  - `api/gz-ord.ts` 加 `getOrderListForMp` + 复用 ORD-104 `getOrderDetail`
  - i18n 字典扩展（zh-CN / en-US）
- **Admin 前端**：`code/main/plus-ui/src/views/gz-ord/order/`
  - `index.vue`（列表，复用 BizTable，从零建）+ `detail.vue`（只读详情，从零建）+ `api/gz-ord/order.ts`
- **测试**：mvn 单测（chip 映射 / 越权 / 时间线推导）+ mp dev:mp-weixin 走「我的」→「我的订单」→「预购」tab → 详情

## 备注

### 强约束

1. **金额字段 `total_amount_cent`（分）**，不用 `total_fen`；UI 显示除 100 转元（doc/11 §6.3 + 字段铁律）。
2. **状态字段是 `business_status`**（不是 `status`），枚举 `created/paid/cancelled/in_logistics/delivered/refunded`，**delivered = 终态无 closed**（doc/10 §7 Q7.2 + 附录 A.5）。时间线 **4 节点**：created → paid → in_logistics → delivered。
3. **物流 `logistics_status` 独立并行**（不是订单状态的子态，不互相覆盖）：`in_japan` / `in_china_dispatching` / `delivered`（C1，doc/10 §9 + 附录 A.7）。详情物流卡是**真实展示**（非占位），有单号就展示快递公司 + 单号 + 复制按钮。
4. **时间字段命名钉死**：支付时间 `paid_time`、签收时间 `delivered_time`、国内派送起算 `cn_dispatched_at`（**禁用 `paid_at` / `shipped_at` / `delivered_at`**，doc/11 §6.3 末段）。
5. **业务线分流不在订单表**：gz_ord_order **无** `business_line` / `biz_line` / A-B 列；分流真源在 `gz_pay_transaction.business_type='preorder'`（字段铁律）。本卡列表查询不需 business_type 过滤（gz_ord_order 仅存预购单，扭蛋落 D09 gz_gacha_order，分表不混查）。
6. **C 端无退款入口**（PAY-103 §强约束 + 合同 §4.5）：详情页严禁「申请退款」按钮，仅文案「如需退款请联系客服」。退款服务 = GZ-PAY-103；本卡不实现退款。
7. **C 端继续支付幂等**：复用 GZ-PAY-101 same `order_no`（重复 createOrder 走幂等，不新增接口）。
8. **越权校验**：详情接口（mp）必校 `order.user_id` 等于当前登录 user。
9. **图片用 image_id**：列表/详情商品图取 `product_snapshot_json` 里的主图 `image_id`（FK gz_file_object），不存/不返裸 url。
10. **admin 本卡仅订单查询（只读）**：物流推进 + 录单号是 GZ-ADMIN-104（下沉 mp 店员端，plus-ui owner 兜底，下游）；退款是 GZ-PAY-103。本卡 admin **不**含 cn-logistics 写接口、不含退款按钮。
11. **menu_id 9100 段**（GZ-ORD admin，9110/9111/9112）；perm key `gz:ord:order:list` / `gz:ord:order:query`，走 `@SaCheckPermission`（不用 `@SaCheckRole`），仅 owner 100 授权。
12. **i18n 强制**（AC 8）。

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 统一状态 chip 映射放 service/util（不入 DB） | doc/11 §8.2 兜底逻辑；business_status + logistics_status → 用户视角 chip，前后端约定 |
| D2 | 状态时间线 4 节点前端推导（不存独立 log 表） | delivered = 终态无 closed（Q7.2）；business_status + 时间字段已足够还原顺序 |
| D3 | 列表/详情商品信息读 `*_snapshot_json`（不查商品表） | 防商品下架/改名/调价后历史订单显示异常（ORD-104 已 snapshot） |
| D4 | 物流卡真实展示（非占位） | C1 物流 2 态 + 终态字段在 gz_ord_order 已落地（ORD-104），无需等下游；有单号即展示，无单号显「在日本」 |
| D5 | admin 本卡只读查询，不含物流/退款写 | 物流推进 = ADMIN-104（下沉 mp），退款 = PAY-103；职责单一，避免与下游撞接口 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | **上游表未实际存在就开工**（gz-ord 是空脚手架） | **§0 自检 grep migration 目录确认上游表实际存在**：`ls db/migration/ \| grep GZ-ORD-104` + grep `gz_ord_order` 建表语句存在 + `gz_ord_order` 含 `business_status` / `logistics_status` / `total_amount_cent` / `*_snapshot_json` / `cn_carrier_code` / `cn_tracking_no` / `paid_time` / `delivered_time` / `cn_dispatched_at` 字段；缺 → STOP 报 Kevin，不假设 ORD-104 已建 |
| R2 | 误把 logistics 当 business_status 子态 / 误删 closed 后又漏改时间线为 4 节点 | 时间线推导单测固定 4 节点（AC 7）；logistics 卡独立组件，与 business chip 解耦 |
| R3 | 越权访问他人订单 | AC 2 强校验 user_id + 单测覆盖 |
| R4 | chip 映射与 doc/11 §8.2 不一致（如把 to_ship 错配 in_logistics） | 映射表逐条对齐 §8.2；单测覆盖 ≥ 4 分支 |
| R5 | mp 列表下拉刷新与上拉加载并发触发 | useOrderList 加载态互斥 + 防抖 |
| R6 | 字段名用错（total_fen / status / paid_at） | §0 自检比对 doc/11 §6.3 实际列名；kevin-qa Tier 1B grep VO/SQL 无 `_fen` / `paid_at` / `business_line` |
| R7 | 物流态文案 / 时间线节点名 i18n 漏译 | Tier 2 批量人验必查；AC 8 强制 |

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
- 问题 1：<现象> / 期望：<期望>
- 问题 2：...
-->
