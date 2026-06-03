# GZ-ORD-104 — 预购下单跨域事务（建 gz_ord_order / business_type=preorder 落 gz_pay_transaction / C1 物流 2 态默认 in_japan）

**优先级**: P1
**复杂度**: M（V1.1 第一个跨域事务 ⭐ — ORD 落单 + 扣 SKU 库存 + 调 PAY-101 写 gz_pay_transaction，业务线 A 端到端打通核心，禁止草率过 §0 自检）
**关联 PRD**: doc/02-prd.md M3 §状态机 + §关键字段 PreorderOrder
**关联拆解**: doc/02-需求拆解.md §3.2（预购下单 + 支付 + 订单生成）
**关联 mockup**: design/mockup/order-confirm.html（仅布局参考；视觉以 C 系统为准，doc/13）
**关联 ADR**: doc/_adr/0005-cross-border-logistics-2-state.md（C1 物流 2 态裁定，本卡落 logistics 字段时遵循）
**依赖**: GZ-ORD-103（下单确认页 + 传参 + snapshot 来源）+ GZ-PAY-101（统一支付服务 / 统一订单号 / business_type 分流 / SPI 回调路由）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡 + ★ 重点反复读）

> 业务流 + 字段表是 ticket 实施的"蓝图"，缺引用 = AI 凭字面猜实现 = 翻车前兆。

- **业务流**：doc/10-业务流权威图.md
  - **§7 预定货品全流程**（M3，V1.1）—— 本卡核心：N6（U 提交订单：事务内扣 SKU 库存乐观锁 → 写 gz_ord_order snapshot → 创 gz_pay_transaction）/ N7（调统一支付 §6）/ N8（支付成功业务回调 → 订单 `paid`）；异常 E1/E2/E3/E7/E8（截止 / 库存 / 下架 / 超时 / 取消）
  - **§7 状态机**：`created → paid → in_logistics → delivered`（**`delivered` 即终态，不维护独立 `closed`** —— doc/11 F6.4）；`cancelled` 仅 `created`（未支付）态可达；`refunded` 走 PAY-103，本卡不实现
  - **§6 业务支付流**（V1.1）N6：V3 回调按 `out_trade_no` 前缀（`PREORD-`）分发到预购 paid 回调（§7.N8）；幂等基于 `transaction_id`
  - **§9 跨业务订单聚合 + 跨境物流流**：本卡仅落 `logistics_status` 默认 `in_japan` + 物流字段，admin 推进（进 `in_china_dispatching` 录 carrier + 单号）留 D10
- **字段表**：doc/11-字段权威表.md
  - **§6.3 gz_ord_order 预购订单**（完整 DDL — 本卡落 DDL 锚定，逐字段对齐）
  - §6.4 物流字段说明（C1 简化 2 态 + 终态；本卡只建字段 + 默认 in_japan，不实现 admin 推进 / 自动签收 cron）
  - §4 gz_pay_transaction（PAY-101 已扩展 `business_type` / `fee_cent`；本卡通过 `pay_transaction_id` 关联其 `transaction_id`）
  - 附录 A.5（business_status UI label）/ A.7（logistics_status UI label）
- **UI 参考**：mp `order-confirm.html` 提交按钮区（布局参考，不逐像素还原）

## What

ORD-103 确认订单页点「提交订单」→ 跨域事务出单：同事务内扣 SKU 库存（乐观锁）+ INSERT `gz_ord_order`（商品 / SKU / 地址三段 `*_snapshot_json`）+ 调 PAY-101 `createOrder(business_type=preorder)` 写 `gz_pay_transaction` → mp 调起 mock V3 支付 → V3 回调按 `PREORD-` 前缀 SPI 路由到预购 handler → 订单 `business_status='paid'`。物流字段建表即落（`logistics_status` 默认 `in_japan`），admin 推进留 D10。

## AC（验收标准）

- [ ] **AC 1**：DDL `V<ts>__GZ-ORD-104-create-gz_ord_order.sql`（ts > `V202606051200`）落 `gz_ord_order` 表，**逐字段对齐 doc/11 §6.3**：
  - `order_no` VARCHAR(64) NOT NULL，格式 `PREORD-yyyyMMdd-6位序号`，UNIQUE `(tenant_id, order_no)`
  - `user_id` BIGINT UNSIGNED NOT NULL（FK gz_user.id，IDX）/ `product_id` BIGINT UNSIGNED NOT NULL（IDX）/ `sku_id` BIGINT UNSIGNED NOT NULL
  - `product_snapshot_json` JSON NOT NULL（商品名 / 主图 file_id / IP / 截止日 / 到货日文案）
  - `sku_snapshot_json` JSON NOT NULL（规格名 + `price_cent`）
  - `address_snapshot_json` JSON NOT NULL（recipient / mobile / 完整地址，**不含 receiver_id** —— F6.2）
  - `qty` INT NOT NULL / `total_amount_cent` BIGINT NOT NULL（= `sku_snapshot.price_cent × qty`，下单锁定）
  - `business_status` VARCHAR(16) NOT NULL DEFAULT `'created'`，枚举 `created`/`paid`/`cancelled`/`in_logistics`/`delivered`/`refunded`（IDX）
  - `logistics_status` VARCHAR(20) NOT NULL DEFAULT `'in_japan'`，枚举 `in_japan`/`in_china_dispatching`/`delivered`（IDX，独立于 business_status 并行）
  - `pay_transaction_id` VARCHAR(64) NULL（FK gz_pay_transaction.transaction_id；UNIQUE WHERE NOT NULL）
  - `paid_time` / `delivered_time` / `cancelled_time` DATETIME(3) NULL（**命名钉死 `_time`，禁出现 `paid_at`/`delivered_at`**）
  - `cn_carrier_code` VARCHAR(32) NULL / `cn_tracking_no` VARCHAR(64) NULL / `cn_dispatched_at` DATETIME(3) NULL（C1 物流字段；本卡建表即落，admin 推进时才写，**本卡不写值**）
  - `user_note` VARCHAR(255) NULL / `version` INT NOT NULL DEFAULT 0（乐观锁）
  - 公共字段（create_by/create_time/update_by/update_time/del_flag 2 值）+ `tenant_id` VARCHAR(20) NOT NULL DEFAULT `'1001'`（**INSERT 不显式赋，走自动填充**）
  - 索引：UNIQUE `(tenant_id, order_no)` / UNIQUE `(tenant_id, pay_transaction_id)` WHERE NOT NULL / IDX `(tenant_id, user_id, paid_time DESC)` / `(tenant_id, business_status)` / `(tenant_id, logistics_status)` / `(tenant_id, cn_tracking_no)`
  - **不出 `business_line`/`biz_line`/A·B 列**（业务线分流真源在 `gz_pay_transaction.business_type`，铁律）
- [ ] **AC 2**：mp 端 `POST /app/gz/ord/order/submit`（`@SaCheckLogin`，事务）：
  - 入参 `{productId, skuId, qty, addressId, userNote?}`；从会话取 `user_id`
  - 校验商品 `status='on_shelf' AND deadline > NOW()` → 否则 errCode `PRODUCT_OFF`（doc/10 §7.E1/E3）
  - 校验地址归属：`gz_user_address.user_id == 当前 user_id` → 否则 errCode `ADDRESS_INVALID`
  - 调 ORD-101 SKU 库存扣减（乐观锁 `UPDATE ... SET stock_remain=stock_remain-?, version=version+1 WHERE id=? AND version=? AND stock_remain>=?`）；**`stock_total IS NULL`（不限库存）的 SKU 跳过扣减**；扣减失败 → errCode `SKU_OUT_OF_STOCK`（doc/10 §7.E2）
  - 生成 `order_no`（`PREORD-yyyyMMdd-6位序号`，复用 PAY-101 统一订单号生成器，全局唯一含 tenant_id）
  - INSERT `gz_ord_order` `business_status='created'`，三段 `*_snapshot_json` 完整落库，`total_amount_cent = sku_snapshot.price_cent × qty`
  - 调 PAY-101 `createOrder(businessType='preorder', orderNo, totalAmountCent, openId, description)` → 拿 V3 支付参数 + `transaction_id`
  - UPDATE `gz_ord_order SET pay_transaction_id=?` WHERE id=?
  - 返回 `{ordOrderId, orderNo, payParams:{appId, timeStamp, nonceStr, package, signType, paySign}}`（V3 字段）
  - 事务边界见 §备注强约束 #1
- [ ] **AC 3**：注册 PAY-101 SPI 预购回调 handler（填 PAY-101 提供的占位）：
  - `@Component class PreorderPayCallbackHandler implements <PAY-101 SPI 接口>`，`supportedType() = 'preorder'`（business_type）
  - `onPaid(tx)`：按 `tx` 关联订单（`order_no == out_trade_no`）→ `SELECT ... FOR UPDATE` 行锁 → 仅 `business_status='created'` 时 UPDATE → `business_status='paid'` + `paid_time = tx.paidTime` + `pay_transaction_id = tx.transactionId`；已 `paid`（重复回调）直接 return（幂等，依赖 PAY-101 transaction_id 去重 + 本侧状态判断）
- [ ] **AC 4**：mp 端 `pages/ord/order-confirm.vue` 提交按钮接入：
  - 点提交 → 调 submit → 成功后 `uni.requestPayment(payParams)`（V3 参数）
  - 支付成功回调 → 跳 `/pages/ord/pay-result?orderId={ordOrderId}`
  - 支付取消 / 失败（requestPayment fail）→ toast「支付未完成，可在订单中心继续支付」+ 订单保持 `created`（**不重复落库 / 不重复扣库存**）
- [ ] **AC 5**：mp 端 `pages/ord/pay-result.vue` 支付结果页：
  - onLoad 拉 `GET /app/gz/ord/order/{id}`
  - `business_status='paid'` → 显示「支付成功」+ 商品 snapshot 信息 + 「查看订单」CTA（跳 ORD-105 详情）
  - `business_status='created'` → 显示「支付处理中」+ 每 3s 轮询订单状态，**上限 10 次（30s）** 仍 `created` → 提示「如已扣款请稍后在订单中心查看」+ 客服入口（不阻死页面）
  - `business_status='cancelled'` → 显示「订单已取消」+ 跳商品详情 CTA
- [ ] **AC 6**：mp 端 `POST /app/gz/ord/order/cancel/{id}`（`@SaCheckLogin`，事务）：
  - 仅 `business_status='created'` 可 cancel；`SELECT ... FOR UPDATE` 行锁防与回调竞争（doc/10 §7.E8）
  - UPDATE `business_status='cancelled'` + `cancelled_time = NOW()` + 回滚 SKU 库存（`UPDATE gz_ord_sku SET stock_remain=stock_remain+? WHERE id=?`，跳过不限库存 SKU）
  - 已 `paid` 订单返回 errCode `ORDER_NOT_CANCELLABLE`（已支付走 PAY-103 退款，本卡不实现）
- [ ] **AC 7**：单测 ⭐ ≥ 5 个测试方法覆盖：
  - happy path：submit → 扣库存 → INSERT created → PAY 调用 → 模拟 SPI onPaid → `business_status=paid` + `paid_time` 写入
  - 库存不足 → 整事务回滚，不落 order（`SKU_OUT_OF_STOCK`）
  - 商品过期 / 下架 → 不落 order（`PRODUCT_OFF`）
  - 重复回调 → 仅第一次更新（幂等，第二次 onPaid 不改 `paid_time`）
  - cancel created 订单 → `cancelled` + 库存回滚；cancel 已 paid 订单 → `ORDER_NOT_CANCELLABLE`，库存不变
- [ ] **AC 8**：reports 含**完整 mock 全链路自测 raw output**（`gz.pay.client.mode=mock`）：createOrder → mock V3 回调（AES-GCM 解析）→ `PREORD-` 前缀 SPI 路由到预购 handler → DB 查 `gz_ord_order.business_status='paid'` + `gz_pay_transaction.business_type='preorder'` + `logistics_status='in_japan'`；≥ 3 个代码 block
- [ ] **AC 9: Tier 2 入口可达**（mp ticket 强制，CLAUDE.md §8.3）—— Kevin 从「首页预购 teaser → 商品列表（ORD-102）→ 商品详情（ORD-103）→ 确认订单页（ORD-103）」点击进入，点「提交订单」即触发本卡全链路；ORD-103 已建确认页入口为现成路径，**本卡不需新增临时入口**（在 §AI 自测段截图验证从确认页可达 submit）。

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-ord/`（包 `org.dromara.gz.ord.*`）
  - `controller/applet/GzOrdOrderMpController.java`（路径 `/app/gz/ord/order`）：submit / cancel / getDetail
  - `service/IGzOrdOrderService.java` + `service/impl/GzOrdOrderServiceImpl.java`（跨域事务 + 补偿）
  - `service/callback/PreorderPayCallbackHandler.java`（PAY-101 SPI 实现，business_type=preorder）
  - `domain/GzOrdOrder.java`（对齐 §6.3 字段，snapshot JSON 用 `@TableField(typeHandler=...)` 或 String）+ dto req/vo
  - `mapper/GzOrdOrderMapper.java`
  - `enums/OrdBusinessStatusEnum.java` + `enums/LogisticsStatusEnum.java`
  - DDL × 1：`ruoyi-admin/src/main/resources/db/migration/V<ts>__GZ-ORD-104-create-gz_ord_order.sql`
- **小程序**：`code/main/miniapp/src/`
  - `pages/ord/order-confirm.vue`（ORD-103 已建，本卡接入提交逻辑）
  - `pages/ord/pay-result.vue`（新建，C 系统 Biz* 原子组件 + `var(--c-*)` token）
  - `composables/useOrderSubmit.ts`（编排：submit → requestPayment → 跳转）
  - `api/gz-ord.ts` 加 submitOrder / cancelOrder / getOrderDetail
- **测试**：mvn 单测 ≥ 5 个（`-DskipTests=false -pl ruoyi-modules/ruoyi-gz-ord -am`）+ mock 全链路自测

## 备注

### 强约束 ★

1. **跨域事务边界**（doc/10 §7.N6）：
   - 同事务内：扣 SKU 库存（乐观锁）+ INSERT `gz_ord_order`（`created`）+ 调 PAY-101 `createOrder` 写 `gz_pay_transaction`。doc/10 §7.N6 将三步定义为同一下单事务；PAY-101 在 mock 模式下 createOrder 是本地事务可控操作（非远程阻塞），随同回滚安全。
   - 若实现中发现 PAY-101 `createOrder` 含不可回滚的远程副作用 → STOP 报 Kevin，按 ADR 拆补偿事务（事务监听器范式），**不擅自改 doc/10 §7.N6 契约**。
   - 支付回调（SPI onPaid）是**独立事务**：回调侧 `SELECT ... FOR UPDATE` + 状态判断推进 `paid`，与下单事务解耦。
2. **business_type=preorder 落在 `gz_pay_transaction`**（PAY-101 写）—— 4% 分成对账分流真源；**`gz_ord_order` 不加 `business_line`/`biz_line`/A·B 列**（铁律，kevin-qa Tier 1B grep schema 验证）。
3. **三段 snapshot 完整**（doc/11 §6.3）：`product_snapshot_json`（商品名 / 主图 file_id / IP / 截止日 / 到货日文案）+ `sku_snapshot_json`（规格名 + price_cent）+ `address_snapshot_json`（recipient / mobile / 完整地址，不含 receiver_id）。snapshot 来源是 ORD-103 确认页已校验的数据，下单瞬间锁定，防商品下架 / 改名 / 调价后历史订单异常。
4. **状态机严格**：`created → paid → in_logistics → delivered`（delivered 终态，**无 closed**，doc/11 F6.4）；`cancelled` 仅 `created` 可达；`refunded` 走 PAY-103 不在本卡；不允许跳态。
5. **C1 物流 2 态**（ADR-0005）：本卡建表落 `logistics_status` DEFAULT `in_japan` + `cn_carrier_code`/`cn_tracking_no`/`cn_dispatched_at` 字段，**本卡不写物流值、不实现 admin 推进、不实现自动签收 cron**（留 D10 GZ-ADMIN-104）。**禁止**：7 节点 / `logistics_node` / `gz_logistics_node` 表 / 批次推进 / 自动归集 GROUP BY / `gz_express_company` / 物流时间线色 / tokens 1.5。
6. **金额 `_cent`、时间 `_time`**（钉死）：`total_amount_cent` / `paid_time` / `delivered_time` / `cancelled_time`；**禁出现 `_fen` / `paid_at` / `delivered_at`**。
7. **已 paid 订单不允许 cancel**（走 PAY-103 退款）；C 端无退款入口，仅文案「如需退款请联系客服」（订单详情，ORD-105）。
8. **i18n 强制**：mp 可见字符串走 `t('xxx.yyy')` + zh-CN 默认，不混 emoji。
9. **menu_id 不涉及**（纯 mp 路径 + 后端，无 admin 菜单）。

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 ⭐ | 下单三步（扣库存 + INSERT order + createOrder）同事务（mock 模式 createOrder 可回滚）；回调 onPaid 独立事务 | 对齐 doc/10 §7.N6；mock 下无远程阻塞副作用，整体回滚安全 |
| D2 | 支付取消 / 失败不重复落库（订单保 created，可在订单中心继续支付） | 用户重试不双扣库存；R1 缓解 |
| D3 | 三段 snapshot 完整存（不存外键反查） | 商品下架 / SKU 改名 / 调价后历史订单仍可展示原貌（doc/10 §7.E4） |
| D4 | 地址 snapshot 用 JSON 列（不分多列、不含 receiver_id） | F6.2 裁定；地址字段多 + 不需单字段查询 |
| D5 | cancel 时库存回滚（实际扣减，非软扣） | 库存只锁实际成功订单，取消即释放（doc/10 §7.E8） |
| D6 | pay-result 轮询（3s × 10 上限）非长连接 | uni-app 长连接复杂 + 预购流量小不必要 |
| D7 | `stock_total IS NULL` 跳过扣减 / 回滚 | 不限库存 SKU 语义（ORD-101 口径） |

### 风险提示 ★

| # | 风险 | 缓解 |
|---|---|---|
| R0 ⭐ | **§0 自检假设上游表已建** | §0 自检 **grep migration 目录确认 `gz_ord_product`/`gz_ord_sku`（ORD-101）+ `gz_pay_transaction` 已扩展 `business_type`（PAY-101）+ `gz_user_address`（已交付）实际存在**；缺任一 → STOP 报 Kevin，不假设 |
| R1 | 下单事务提交后、用户未完成支付 → 订单停 `created` | 用户重进订单页见 `created` + 「继续支付」CTA → 复用同 `order_no` 调 PAY-101（幂等）；超时取消走 PAY-102 查单补单 / cancel |
| R2 | 用户 cancel 与回调 onPaid 竞争 | 两侧均 `SELECT ... FOR UPDATE` 行锁 + 检查 `business_status='created'` 才推进 |
| R3 | 库存乐观锁高并发失败 | V1.1 预购并发预计低，重试 ≤ 3 次足够；失败抛 `SKU_OUT_OF_STOCK` 用户重试 |
| R4 | 商品 deadline 提交瞬间过期 | submit 再校验 `deadline > NOW()` 兜底（doc/10 §7.E1） |
| R5 | 重复回调 | PAY-101 transaction_id 去重 + 本侧 `business_status='created'` 才推进（双层幂等） |
| R6 | business_type 误落订单表（biz_line / A-B 列） | 真源只在 `gz_pay_transaction.business_type`；kevin-qa Tier 1B grep `gz_ord_order` schema 无 `business_line`/`biz_line` |
| R7 | C1 物流被实现成 7 节点 / 批次推进 | 本卡 logistics 仅 3 字段 + 默认 `in_japan`，禁建 node 表；admin 推进留 D10 |
| R8 | 真实微信支付商户号 / 0.01 元端到端 = **外部前置风险** | 本卡 DoD 仅认 mock 全链路（`gz.pay.client.mode=mock`）；真实端到端依赖甲方挂号 + cert + apiV3Key，**列外部前置风险不当默认就绪**；并行催甲方完成 V1.0 验收 |

### ADR 候选

- 若 PAY-101 `createOrder` 在真实模式下含不可回滚远程副作用 → 新建 ADR 记补偿事务实现方式（事务监听器 `TransactionSynchronizationManager` vs Spring 事件 vs MQ）；mock 阶段不触发，按 D1 同事务即可。

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
