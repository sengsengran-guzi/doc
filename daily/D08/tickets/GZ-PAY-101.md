# GZ-PAY-101 — 业务统一支付服务（V3 / business_type 分流 / SPI 回调路由 / 回调幂等）

**优先级**: P1
**复杂度**: M（V1.1 首日 ⭐ — 后续 ORD/GACHA 所有支付场景的通用底座，禁止快速过 §0 自检）
**关联 PRD**: doc/02-prd.md M1 §微信支付 / §下单支付 / §异常分支
**关联拆解**: doc/02-需求拆解.md §3.1 业务支付统一服务
**关联 mockup**: design/mockup/order-confirm.html + pay-result.html（仅布局参考；本 ticket 为后端底座不写 mp UI，mp 视觉走 C 系统 doc/13 由 ORD-103/104 落地）
**关联 ADR**: doc/_adr/0003-payment-channel-v3.md（微信支付 V3 选型 + apiV3Key + AES-GCM NotificationParser；**必读，本 ticket 在其上做业务通用化，不改选型**）
**依赖**: GZ-PAY-001 ✅（**实证已交付**：微信支付 V3 通道 + 统一表 gz_pay_transaction + 订单号生成器 + V3 回调入口；见下「上游已交付实证」）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md
  - **§2 微信支付通道接入流**（V1.0 已建 test 单最小闭环）— 重读状态机 + N1~N9
  - **§6 业务支付流（M1-业务接入，V1.1）**全文 — N1~N7（业务侧建预订单 → 统一下单 → 回调验签幂等 → **按 out_trade_no 前缀 / business_type 分发到业务回调**）+ 状态机（created/pending/paid/timeout/closed/refunding/refunded）+ E1 重复回调幂等 / E2 业务回调失败
- **字段表**：doc/11-字段权威表.md
  - **§4.2 gz_pay_transaction 支付订单（统一表）** — 字段口径 + 索引 + business_type 取值（preorder/gacha/pindou/test）+ out_trade_no 格式 + version 乐观锁
  - **§4.3 gz_pay_callback_log 回调原始流水** — callback_type（payment/refund）+ process_status（received/processed/duplicated/failed）幂等去重依据
  - **§4.6 4% 分成核心计算口径** — business_type 分流是分成核算前提（业务线 A preorder / B gacha 分别核算，不交叉冲抵）
- **UI 参考**：N/A（本 ticket 纯后端 + mp 调起契约，无 mp 页面；mp 调起在 ORD-103/104 接入）

## What

把 PAY-001 已交付的"仅 test 单"微信支付 V3 通道，升级为**业务可调用的统一支付服务**：业务方（ORD/GACHA）传 `business_type` + `business_order_no` 即可创建 pending 交易并拿到 mp 调起参数；支付成功回调按 `business_type` 经 **SPI 路由**分发到对应业务 handler 完成自己的订单状态变更。**扩展已落地的 `gz_pay_transaction`，不新建任何支付表；复用 PAY-001 的 V3 client + V3 回调入口，不回退 V2。**

## AC（验收标准）

- [ ] **AC 1：通用建单服务**（不是 createTestOrder 的特例）。`IGzPayTransactionService` 新增 `createBusinessOrder(CreateOrderBo)`，入参 `business_type`（`preorder`/`gacha`/`test`）+ `business_order_no` + `amount_cent` + `openid` + `user_id` + `description`，返回 `MpPayParamsVO`（含 out_trade_no + timeStamp/nonceStr/package/signType/paySign 供 mp `uni.requestPayment`）。流程：① `PayOrderNoGenerator.generate(business_type)` 生成 out_trade_no → ② INSERT `gz_pay_transaction` status=`created` + expire_time=now+5min（**不显式赋 tenant_id**，走自动填充）→ ③ 调 `IWechatPayClient.createJsapiOrder` 拿 prepay_id + UPDATE status=`pending` → ④ `buildPayParams` 返回 5 参签名。复用 PAY-001 的 `PayOrderNoGenerator` / `IWechatPayClient`，**不重写**。
- [ ] **AC 2：订单号格式锚定**（全 V1.1 复用）。`out_trade_no` = `<域大写前缀>-yyyyMMdd-<6位日内序号>`，前缀枚举 `PayBusinessType.toOutTradePrefix`：`preorder→PREORD` / `gacha→GACHA` / `test→TEST`（与 D07 已发 `TEST-20260604-NNNNNN` 单格式一致）。全局唯一靠 DB `uk_tenant_out_trade_no (tenant_id, out_trade_no)`（已存在）。验证：连续建 2 笔 preorder → 拿到 `PREORD-yyyyMMdd-000001` / `PREORD-yyyyMMdd-000002`，序号连续不撞。
- [ ] **AC 3：business_type 分流落 transaction 表**。`gz_pay_transaction.business_type` 写入入参值；`business_order_no` 写业务订单业务码（如 `gz_ord_order.order_no`）。**禁止**在业务订单表（gz_ord_order/gz_gacha_order）加 `business_line`/`biz_line`/A-B 列 —— 分流真源只在 `gz_pay_transaction.business_type`。验证：建 1 笔 preorder + 1 笔 gacha → `SELECT business_type, count(*) FROM gz_pay_transaction GROUP BY business_type` 各 1 行。
- [ ] **AC 4：SPI 回调路由接口 + 注册中心**。新增接口：
  ```java
  public interface PayCallbackHandler {
      String supportedBusinessType();   // 返回 preorder / gacha / test
      void onPaid(GzPayTransaction txn); // 业务方在自己事务内更新自己的业务订单状态
  }
  ```
  注册中心按 Spring Bean 类型注入 `Map<String, PayCallbackHandler>`（key=`supportedBusinessType()`），**禁止硬编码 switch-case**（新业务接入零改动 PAY-101）。启动时校验同 `business_type` 不得注册多个 handler，重复 → fail-fast 抛 `IllegalStateException`。本 ticket 提供分发骨架 + **preorder 占位 handler**（仅打印日志 + TODO 注释 `// ORD-104 填实现`，注明非空 TODO 说明，不算违反铁律 #7）；gacha handler 由 D09 注册。
- [ ] **AC 5：回调接入 SPI 分发**。扩展 `handlePaymentNotify(NotifyContext)`：现有「验签 → 写 callback_log received → 幂等去重 → 乐观锁 pending→paid → callback_log processed」流程**保留不动**，在「乐观锁 UPDATE 成功（pending→paid）」之后、`callback_log processed` 之前，按该交易行的 `business_type` 从注册中心取 handler 调 `onPaid(txn)`（同一事务 REQUIRED 传播）。`business_type=test` 无 handler 时跳过分发（不报错，保持 PAY-001 test 单行为）。handler 抛异常 → 整笔事务回滚（交易行保 pending）→ callback 返回 500 让微信重试（doc/10 §6.E2）。
- [ ] **AC 6：回调幂等两道防线**（doc/10 §6.E1 + §2.N7，复用 PAY-001 已实现机制）：① 入口按 `transaction_id` 在 `gz_pay_callback_log` 去重，已处理 → 写 `duplicated` 直接返回 success；② 乐观锁 `UPDATE ... WHERE id=? AND version=? AND status='pending'`，affected=0（已 paid / 并发）→ 标 duplicated 不重复分发 SPI handler。验证：同一 NotifyContext 调 `handlePaymentNotify` 两次 → handler `onPaid` **仅被调一次**，第二次 callback_log 记 `duplicated`。
- [ ] **AC 7：复用 V3 回调入口 + V3 解析**。回调端点固定 `POST /api/pay/v3/notify`（PAY-001 已建 `WechatPayNotifyController`，`@SaIgnore` 无 sa-token），用 PAY-001 的 `IWechatPayClient.parseAndVerifyNotify`（V3 `NotificationParser` 验 Wechatpay-Signature + AES-GCM 解密）。**禁止**新建 `/api/wxpay/pay-notify` 端点 / V2 XML 解析 / api-key 旧签名体系。
- [ ] **AC 8：mp 调起契约**。`GzPayMpController`（`/app/gz/pay`，`@SaCheckLogin`）提供业务下单调起入口（或暴露 service 供 ORD-103/104 同模块直接注入调用）；返回 `MpPayParamsVO` 字段齐全（out_trade_no + 5 参签名），mp 端 `uni.requestPayment` 可直接用。本 ticket 验证 mock 模式下返回参数结构正确（不依赖真实 mp 真机）。
- [ ] **AC 9：单测 ≥ 4 个方法**（业务核心 service，覆盖率目标 ≥ 60%）：
  - happy path：`createBusinessOrder(preorder)` → 落 created → mock client 返 prepay_id → status=pending；模拟 mock 回调 → status=paid + preorder handler `onPaid` 被调 1 次
  - SPI 路由：注册 2 个 mock handler（preorder/gacha）→ 一笔 preorder 回调只触发 preorder handler，gacha handler 0 次
  - 幂等：同 transaction_id 二次回调 → handler 仅 1 次 + 第二次 callback_log=`duplicated`
  - handler 异常回滚：mock preorder handler 抛异常 → 交易行保 pending（未变 paid）+ 返回处理失败（让微信重试）
  - fail-fast：同 business_type 注册 2 个 handler → 启动期注册中心校验抛 `IllegalStateException`
- [ ] **AC 10：Mock 全链路自测通过**（本日 DoD，Kevin 决策 1）。`gz.pay.client.mode=mock`（`MockWechatPayClient`）下端到端：`createBusinessOrder(preorder)` → mock 调起 → mock V3 回调（AES-GCM 解析路径）→ SPI 路由 preorder handler → status=paid。reports 贴 raw output（建单 SQL 行 + 回调日志 + handler 命中日志，≥ 3 个代码 block）。**真实商户号 / 0.01 元端到端列为【外部前置风险】**（见备注 R1），不当默认就绪。

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/`（PAY 通用底座，复用 PAY-001 现有 `pay/` 子包）
  - 新增 `pay/service/spi/PayCallbackHandler.java`（SPI 接口）+ `pay/service/spi/PayCallbackDispatcher.java`（注册中心，注入 `Map<String, PayCallbackHandler>` + 启动校验 fail-fast）
  - 新增 `pay/service/spi/handler/PreorderPayCallbackHandler.java`（preorder 占位，TODO `// ORD-104 填实现`）
  - 扩展 `pay/service/IGzPayTransactionService.java` + `impl/GzPayTransactionServiceImpl.java`：加 `createBusinessOrder(CreateOrderBo)`（通用建单）+ `handlePaymentNotify` 内接入 SPI 分发
  - 新增 `pay/domain/bo/CreateOrderBo.java`（business_type + business_order_no + amount_cent + openid + user_id + description）
  - **复用不改**：`PayOrderNoGenerator` / `PayBusinessType` / `PayStatus` / `IWechatPayClient`(`MockWechatPayClient`/`WechatPayV3ClientImpl`) / `WechatPayNotifyController`(`/api/pay/v3/notify`) / `GzPayTransaction` 实体 / `GzPayCallbackLog` / 三表 schema
  - **DDL：本 ticket 无需新建迁移**（`gz_pay_transaction` 已含 `business_type`/`business_order_no`/`fee_cent`/`version`，`gz_pay_callback_log` 已含 `callback_type`/`process_status`，PAY-001 `V202606041200` 落齐）。如 §0 自检发现确缺列（实证为准，不假设），新建 `V<yyyyMMdd HHmm>__GZ-PAY-101-<desc>.sql`（时间戳 > `V202606051200`，**已应用迁移不可改**）。
  - mp 调起：`GzPayMpController` 复用（业务下单调起在 ORD-103/104 接入本 service）
- **小程序**：本 ticket 不涉及 mp 页面改动（mp 调用方在 ORD-103/104 接入 `createBusinessOrder` + `uni.requestPayment`）
- **测试**：`mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -am`（AC 9 单测）+ mock 全链路自测（AC 10）

## 备注

### 强约束 ⭐（违反直接打回）

1. **V3 only**：复用 PAY-001 的 `IWechatPayClient`（V3）+ apiV3Key + V3 `NotificationParser`（AES-GCM）+ 回调 `/api/pay/v3/notify`。**禁止**：V2 / XML / api-key（旧签名密钥）/ 新建 `gz_pay_order` 表 / `amount_fen` 列 / `/api/wxpay/pay-notify` 端点。
2. **不新建支付表**：扩展已落地 `gz_pay_transaction` / `gz_pay_callback_log`（PAY-001 `V202606041200`）。金额列名 `amount_cent`（分），**不用 `_fen`**。
3. **business_type 分流真源**：`gz_pay_transaction.business_type`（取值 `preorder`/`gacha`/`test`）。**禁止**在业务订单表加 `business_line`/`biz_line`/A-B 列。两业务线 4% 分成靠 `business_type` + `fee_cent` 分别核算，不交叉冲抵（合同 §4.1 / doc/11 §4.6）。
4. **SPI 用 Spring Bean Map 注入**，不硬编码 switch-case；同 business_type 多 handler 启动 fail-fast。新业务（gacha D09 / 未来）接入零改动 PAY-101。
5. **回调幂等两道防线缺一不可**：transaction_id 在 callback_log 去重 + version 乐观锁 pending→paid（doc/10 §6.E1 / §2.N7）。
6. **回调端点不走 sa-token**：复用 PAY-001 `@SaIgnore` + `TenantHelper.ignore`（微信服务器直发无登录态、无租户上下文）。
7. **fee_cent 本 ticket 不回写**：V3 支付回调 body 含 `amount.payer_total` 但不含通道手续费；`fee_cent` 由 PAY-104 每日 SnailJob 拉 `/v3/bill/fundflowbill` 异步回写（对账依赖，doc/11 F4.3）。本 ticket 建单时 `fee_cent` 留 NULL。
8. **TODO 必带说明**：preorder 占位 handler 的 `// ORD-104 填实现` 是带说明的下游交接 TODO（不违反铁律 #7「不留无说明 TODO」）。

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | PAY 通用底座留在 ruoyi-gz-common（不新建 ruoyi-gz-pay） | PAY-001 已在 gz-common 落 `pay/` 子包 + 三表 + V3 client；通用化是同质扩展，新建模块成本高且割裂 |
| D2 | SPI 路由用 Spring Bean Map 注入（key=business_type） | 业务方接入零侵入 PAY-101 代码；gacha/未来业务只注册自己的 handler |
| D3 | `createBusinessOrder` 与 PAY-001 `createTestOrder` 共用底层（订单号生成 / client / 落库） | PAY-001 已注「createTransaction 抽象到位，V1.1 调用方传 business_type + business_order_no 即可」；本 ticket 兑现该抽象，不重写 |
| D4 | handler 异常 → 整事务回滚 + 微信重试 / PAY-102 补单兜底 | 微信回调会重试 + PAY-102 主动查单兜底，不强求当次成功（doc/10 §6.E2） |
| D5 | 推进姿态 = mock 全链路自测（dev/staging `gz.pay.client.mode=mock`） | Kevin 决策 1；真实商户号端到端 = 外部前置风险，不当默认就绪 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 ⭐【外部前置风险】| 真实微信支付商户号 / cert / apiV3Key / 0.01 元端到端验证滞后（甲方挂号就绪滞后） | 本 ticket DoD 仅认 mock 全链路（`gz.pay.client.mode=mock`）；真实端到端标注【外部前置风险】不当默认就绪；并行催甲方完成 V1.0 验收 + 提供商户配置 |
| R2 | §0 自检若**假设**上游表/类已建而实际未建 → 实施踩空 | **§0 自检 grep migration 目录确认上游表实际存在**（`ls db/migration/ \| grep PAY` + grep `gz_pay_transaction` schema 含 `business_type`/`version`），grep `pay/service/internal/` 确认 `IWechatPayClient`/`PayOrderNoGenerator` 类存在，不假设上游已建 |
| R3 | PAY-104/102/103 都注册 SPI（支付/退款）→ 路由 key 撞或混乱 | 本 ticket 先定 SPI 接口 + 路由表（支付回调按 business_type）；退款回调 SPI（PAY-103）用**独立 key 空间**（payment vs refund 分流，callback_log.callback_type 区分）；104/102/103 落地后串行 review 一次路由表 |
| R4 | 跨域事务（ORD-104）调本 service 建单与业务建单事务边界不清 | 本 ticket 文档强约束：`createBusinessOrder` 为 REQUIRED 传播，业务方在同事务内调用（ORD-104 建 gz_ord_order + 扣库存 + 调本 service 一个事务）；handler `onPaid` 内仅更新业务订单状态，不再触发新支付 |
| R5 | 同日 PAY-101 是 ORD-104 上游契约，未 close 前被 ORD-104 抢跑 | 严格按 D08 依赖图波次（PAY-101 波次 1 → ORD-104 波次 3）；ORD-104 §0 自检若 SPI 契约未定 → STOP 报 Kevin |

### ADR 关联

- **ADR-0003**：微信支付 V3 选型（PAY-001 已落 + 本 ticket 沿用，必读不改选型）
- 如本 ticket SPI 路由设计需固化为决策，可在 ADR-0003 末追加「§业务回调 SPI 路由」段，不单独新建 ADR

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
