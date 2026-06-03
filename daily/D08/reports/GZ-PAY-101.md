# GZ-PAY-101 完工报告 — 业务统一支付服务（V3 / business_type 分流 / SPI 回调路由 / 回调幂等）

> 波次 1 · ruoyi-gz-common · 后端 service 底座（无新表）· mock 全链路自测通过

## §0 自检结果

| 检查项 | 结果 | 实证 |
|---|---|---|
| git 状态 | N/A | 当前目录非 git repo（环境提示 `Is directory a git repo: No`）；按 ticket 收尾约定本 ticket 不 commit |
| 上游 PAY-001 已交付 | ✅ | grep `pay/` 子包：`IWechatPayClient`(`MockWechatPayClient`/`WechatPayV3ClientImpl`) / `PayOrderNoGenerator` / `PayBusinessType` / `PayStatus` / `GzPayTransaction` 实体 + `GzPayTransactionServiceImpl` / `WechatPayNotifyController`(`/api/pay/v3/notify`) / `GzPayTestController` 全部实证存在 |
| 关键表 schema 齐全 | ✅ | grep `V202606041200`：`gz_pay_transaction` 已含 `business_type`/`business_order_no`/`fee_cent`/`amount_cent`/`out_trade_no`/`transaction_id`/`version` + `uk_tenant_out_trade_no` + `uk_tenant_transaction_id` + `idx_business_type_status`；`gz_pay_callback_log` 含 `callback_type`/`process_status` → **本 ticket 无需新建迁移** |
| migration 最大版本 | ✅ | `V202606051200`（本 ticket 不新增迁移，故无需 > 它） |
| 编译通过 | ✅ | `mvn compile -pl ruoyi-modules/ruoyi-gz-common`（无 -am）EXIT=0 |
| ADR 已读 | ✅ | ADR-0003（实际文件名 `0003-wechat-pay-channel-mock-degradation.md`）：mock+real 双实现 profile 切换 / 官方 SDK / SnailJob 调度 / 真实端到端=外部前置风险 —— 沿用不改选型 |
| 权威蓝图引用 | ✅ | doc/10 §2（V3 通道 N1~N9）+ §6（业务支付 N1~N10 + 状态机 + E1 幂等/E2 业务回调失败回滚）；doc/11 §4.2 gz_pay_transaction + §4.3 callback_log + §4.6 4% 分成（business_type+fee_cent 分别核算）已 Read 摘录 |

**权威约束摘录（落地依据）**：
- doc/10 §6.N6：「业务回调：根据 out_trade_no 前缀 / business_type 分发到业务回调」→ 落地为 SPI 按 `business_type` 路由（非前缀字符串匹配，更稳）。
- doc/10 §6.E2：业务回调事务异常 → 整笔回滚 + 微信重试 + PAY-102 补单兜底 → 落地为 handler 异常向上透传致 `@Transactional` 回滚 + callback 返失败。
- doc/11 §4.2：`fee_cent` 回调中提取「W → S」，但 F4.3 已裁定 V3 回调 body 不含通道费，由 PAY-104 拉 `/v3/bill/fundflowbill` 回写 → 本 ticket 建单 `fee_cent` 留 NULL（强约束 #7）。
- doc/11 §4.6：分流真源只在 `gz_pay_transaction.business_type`，业务订单表禁加 biz_line/A-B 列。

## 实现摘要

**新增（6 文件）**：
- `pay/service/spi/PayCallbackHandler.java` — SPI 接口（`supportedBusinessType()` + `onPaid(GzPayTransaction)`），含 key 空间约定（支付按 business_type / 退款 PAY-103 独立 key）+ 事务/幂等契约文档。
- `pay/service/spi/PayCallbackDispatcher.java` — 注册中心：构造注入 `List<PayCallbackHandler>` → `@PostConstruct validate()` 建 `Map<businessType, handler>` 路由表 + fail-fast（同 type 多 handler 抛 `IllegalStateException`）；`dispatch(txn)` 按 business_type 取 handler，无 handler（test 单）跳过不报错，handler 异常向上透传。**无 switch-case**。
- `pay/service/spi/handler/PreorderPayCallbackHandler.java` — preorder 占位 handler（`@Component`，命中即日志 + 带说明 TODO `// ORD-104 填实现`）。
- `pay/domain/bo/CreateOrderBo.java` — 通用建单入参（businessType/businessOrderNo/amountCent/openid/userId/description + 校验注解）。
- `(test) pay/service/spi/PayCallbackDispatcherTest.java` — 6 测：fail-fast / 正常建表 / 路由命中 / test 无 handler 跳过 / handler 异常透传 / 空列表。
- `(test) pay/service/GzPayBusinessFullChainMockTest.java` — 2 测：preorder 全链路（建单→mock 调起→mock V3 回调→真 SPI 路由真 PreorderPayCallbackHandler→paid→重复幂等）+ test 单全链路（无 handler 跳过仍 paid）。in-memory mapper 模拟 DB UNIQUE + 乐观锁。

**改动（4 文件）**：
- `pay/service/IGzPayTransactionService.java` — `+ createBusinessOrder(CreateOrderBo)`。
- `pay/service/impl/GzPayTransactionServiceImpl.java` — ① 抽 `createOrderInternal(...)` 通用建单底层（`createTestOrder` 改为薄壳调它，决策 D3：test 单=业务单特例，**不重写**底层）；② `+ createBusinessOrder`；③ `handlePaymentNotify` 在 markPaid affected=1 后、callback_log processed 前接入 `callbackDispatcher.dispatch(tx)`（同事务 REQUIRED）；幂等两道防线（已 paid SELECT / 乐观锁 affected=0）均 **不进入分发** → onPaid 至多一次；④ 注入 `PayCallbackDispatcher`。
- `pay/controller/GzPayTestController.java` — `+ /create-business-order`（`@SaCheckPermission("gz:pay:test")`，AC 10 mock 全链路驱动入口；prod 关 perm）。
- `(test) pay/service/GzPayTransactionServiceImplTest.java` — 构造器 +1 mock(`callbackDispatcher`) + 改 3 个旧回调测加 dispatch 断言（happy=1 次 / duplicated=0 / 乐观锁冲突=0）+ 4 新测（业务建单 happy + 未知 type 失败 + SPI 路由命中传 paid 行 + handler 异常透传致回滚）。

**无新建迁移**（表已齐全）。**AC 8 选型**：业务下单走「业务模块在自己跨域事务内注入 service 调 `createBusinessOrder`」（ticket AC 8「或」分支），不暴露通用 mp 建单端点（避免任意 business_order_no 越权建单）；mp 调起 5 参由 `MpPayParamsVO` 提供，ORD-104 接入。

## AI 自测（Tier 1A）

### 1. 编译（gz-common only，无 -am）

```
$ mvn compile -pl ruoyi-modules/ruoyi-gz-common -q
COMPILE_EXIT=0   （无 error 输出）
```

### 2. 单测（service 10 + dispatcher 6 + 全链路 2 = 18，全 gz-common 73 全绿）

```
[INFO] Running org.dromara.gz.common.pay.service.GzPayBusinessFullChainMockTest
[INFO] Tests run: 2, Failures: 0, Errors: 0, Skipped: 0
[INFO] Running org.dromara.gz.common.pay.service.GzPayTransactionServiceImplTest
[INFO] Tests run: 10, Failures: 0, Errors: 0, Skipped: 0
[INFO] Running org.dromara.gz.common.pay.service.spi.PayCallbackDispatcherTest
[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0
...（其余 gz-common 测试 47 个全绿）
[INFO] Tests run: 73, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

AC 9 五项单测覆盖确认：
- happy path（建单 created→pending + 回调 paid + SPI 命中 1 次）→ `createBusinessOrder_preorder_happyPath` + `handlePaymentNotify_preorder_spiDispatched`
- SPI 路由（preorder 回调只命中 preorder handler，gacha 0 次）→ `PayCallbackDispatcherTest.dispatch_routesToCorrectHandler`
- 幂等（同回调二次 → onPaid 仅 1 次 + duplicated）→ `handlePaymentNotify_duplicated_alreadyPaid`/`_optimisticLockConflict`（dispatch never）+ 全链路测重复回调断言 markPaid times(1)
- handler 异常回滚（交易行保 pending / 异常透传）→ `handlePaymentNotify_handlerThrows_propagatesForRollback`（processed 日志未写）+ `dispatch_handlerThrows_propagates`
- fail-fast（同 business_type 2 handler 启动抛 IllegalStateException）→ `PayCallbackDispatcherTest.validate_duplicateBusinessType_failFast`

### 3. AC 10 mock 全链路 raw log（preorder 端到端 + 重复幂等）

```
[gz-pay-mock] createJsapiOrder out_trade_no=PREORD-20260603-000001 amount=9900 → prepay_id=mock_prepay_PREORD-20260603-000001
[gz-pay] 建单成功 business_type=preorder out_trade_no=PREORD-20260603-000001 business_order_no=PREORD-ORDER-20260604-001 amount=9900 prepay_id=mock_prepay_PREORD-20260603-000001
[gz-pay] SPI 分发支付回调 business_type=preorder → PreorderPayCallbackHandler out_trade_no=PREORD-20260603-000001 business_order_no=PREORD-ORDER-20260604-001
[gz-pay] PreorderPayCallbackHandler.onPaid 命中（占位）out_trade_no=PREORD-20260603-000001 business_order_no=PREORD-ORDER-20260604-001 amount_cent=9900 —— 实际出单逻辑待 ORD-104 填实现
[gz-pay] 回调处理成功 out_trade_no=PREORD-20260603-000001 business_type=preorder → paid transaction_id=mock_wx_txn_PREORD-20260603-000001
[gz-pay] 重复回调（已 paid）out_trade_no=PREORD-20260603-000001          ← 第二次回调幂等
```

**断言（全链路测内）**：建单后 status=pending + business_type=preorder + business_order_no 写入 + fee_cent=NULL + prepay_id=mock_prepay_* + packageVal 一致；回调后 status=paid + transaction_id 写入 + callback_log [received, processed]；重复回调后 status 仍 paid + callback_log 追加 [received, duplicated] + markPaid 仅调 1 次。test 单链路：无 handler dispatch 跳过仍 paid。

### 4. 强约束反例自查（应全空 → 已确认空）

```
$ grep -rn "gz_pay_order\|amount_fen\|/api/wxpay\|api-key\|switch.*business" pay/service/spi/ pay/domain/bo/CreateOrderBo.java
(空 — 无违反：无新表 / 无 _fen / 无 V2 端点 / SPI 无硬编码 switch)
```

### 5. 落 .m2（并行安全，无 -am）

```
$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-common
Installing .../ruoyi-gz-common-5.6.1.jar to ~/.m2/.../ruoyi-gz-common-5.6.1.jar
BUILD SUCCESS
```

## 风险提示 / 已知 issue

- **R1【外部前置风险】真实 0.01 元端到端未跑**：本 ticket DoD = mock 全链路（`gz.pay.client.mode=mock`）。真实商户号/cert/apiV3Key 就绪后切 real profile 在 staging 跑（ADR-0003 §2 四步），不当默认就绪。
- **DB 真链路 SQL 未跑**：单测用 in-memory mapper 模拟 DB（UNIQUE + 乐观锁语义），未起真实 MySQL 跑 INSERT/UPDATE。乐观锁 SQL（`markPaid` WHERE version + status）+ UNIQUE 约束在 PAY-001 已经真链路验过，本 ticket 复用未改 mapper SQL，风险低；Tier 1B 主线程集成可起库验真 SQL。
- **PreorderPayCallbackHandler 占位归属待 ORD-104 定**：当前占位 Bean 在 gz-common（让 PAY-101 本身可验 preorder 路由命中）。ORD-104 接手时二选一：(a) 在本类注入 `IGzOrdOrderService` 填实现；(b) 把本类移到 ruoyi-gz-ord 模块 + 删 gz-common 占位（dispatcher 自动收新 Bean，零改 PAY-101）。**推荐 (a)**（保留 gz-common 单一支付域，handler 跨模块注入 ord service 即可）。注意：方案 (b) 移走后 gz-common 内 `GzPayBusinessFullChainMockTest` 仍 new PreorderPayCallbackHandler 直测，会编译失败 → 届时该测改用匿名 handler。
- 待 Kevin 批量人验关注：**N/A — 纯后端 service 底座，无 mp 页面、无微信原生能力**（Tech 段无 `miniapp/` 路径），按 CLAUDE.md §8.2「纯后端 ticket 无人验」，AI Tier 1A+1B 全 ✅ 即终态 close。

## 对下游 ticket 的提示（SPI 契约 + 路由 key 空间）

### 给 ORD-104（预购下单跨域事务，波次 3）— 最关键

1. **建单契约**：在 ORD-104 下单事务内注入 `IGzPayTransactionService`，调
   ```java
   MpPayParamsVO params = payService.createBusinessOrder(CreateOrderBo.builder()
       .businessType(PayBusinessType.PREORDER)
       .businessOrderNo(ordOrder.getOrderNo())   // gz_ord_order.order_no
       .amountCent(totalCent)
       .openid(openid).userId(userId)
       .description("谷子宇宙预购：" + productName)
       .build());
   ```
   `createBusinessOrder` 是 `@Transactional(REQUIRED)` → 与 ORD-104「建 gz_ord_order + 扣 sku.stock_remain（乐观锁）+ 调本方法」**同一事务**，任一失败整体回滚（R4）。`params` 含 out_trade_no + 5 参签名返 mp `uni.requestPayment`。
2. **出单契约（填 PreorderPayCallbackHandler.onPaid）**：支付成功回调由 PAY-101 在自己事务内调 `onPaid(GzPayTransaction txn)`。ORD-104 在 `onPaid` 内用 `txn.getBusinessOrderNo()` 定位 `gz_ord_order` → created→paid（建议带 `WHERE business_status='created'` 守卫防御）。**onPaid 至多调一次**（PAY-101 已保证幂等，无需自己再做支付幂等）。**抛异常 = 整笔回调事务回滚 → 微信重试 + PAY-102 补单**，故 onPaid 内只更新订单状态，不调外部不可回滚操作。
3. **占位 handler 归属**：见上「已知 issue」，推荐方案 (a) 本类注入 ord service。

### 给 PAY-104（fundflowbill 回写笔费）

- `fee_cent` 建单时已留 NULL（本 ticket 不回写）。PAY-104 SnailJob 按 `transaction_id` 拉 `/v3/bill/fundflowbill` 回写 `gz_pay_transaction.fee_cent`。无需改 PAY-101 任何代码。

### 给 PAY-102（主动查单补单）

- 查到 paid 但本地 pending 时，复用本 ticket 的 `handlePaymentNotify` 链路（构造等价 NotifyContext）即可走同一套乐观锁 + SPI 分发，自动幂等。或直接调内部推进 + `callbackDispatcher.dispatch(tx)`（建议走 handlePaymentNotify 保持单一真源）。

### 给 PAY-103（退款，独立 key 空间 — R3 核心）

- **支付回调 SPI 路由 key = `business_type`**（preorder/gacha/...），由 `PayCallbackHandler` + `PayCallbackDispatcher` 承载。
- **退款回调走独立 SPI key 空间**：`gz_pay_callback_log.callback_type='refund'` 区分，**新建独立的 RefundCallbackHandler + RefundCallbackDispatcher**（或同一 dispatcher 加 `callback_type` 维度），**不要复用本 `PayCallbackHandler`**（避免支付/退款路由 key 撞）。PAY-103 落地后主线程串行 review 一次路由表（R2）。
- 退款会用到 PayStatus.REFUNDING/REFUNDED 常量（本 ticket 未加，PAY-103 加到 `PayStatus`）。

### SPI 契约摘要（供主线程派 ORD-104）

```
接口  org.dromara.gz.common.pay.service.spi.PayCallbackHandler
      String supportedBusinessType();          // 路由 key，取 PayBusinessType 常量
      void   onPaid(GzPayTransaction txn);      // PAY-101 回调事务内调用，至多一次
注册  实现 @Component 即自动被 PayCallbackDispatcher 收集（List 注入 + @PostConstruct 建表 + fail-fast）
路由  支付成功回调 → 按 txn.businessType 取 handler.onPaid；test 单无 handler 跳过不报错
事务  onPaid 同 handlePaymentNotify 事务（REQUIRED）；抛异常 → 整笔回滚 → 微信重试 + PAY-102 兜底
建单  IGzPayTransactionService.createBusinessOrder(CreateOrderBo) → MpPayParamsVO（out_trade_no + 5 参）
key 空间  支付回调=business_type；退款回调（PAY-103）=独立 key（callback_type=refund），二者不混
```

## §AI 测试段（kevin-qa Tier 1B / 主线程集成接管）

> kevin-coder 作为 subagent 时 Agent 工具不可用（嵌套限制）→ 本 ticket 未 spawn kevin-qa。
> Tier 1A 已做扎实（编译 + 18 单测 + mock 全链路 raw log + 强约束反例自查 + .m2 install）。
> Tier 1B（起真实 MySQL 跑集成验真 SQL / 全量 `mvn install -am` 集成编译）由主线程在波次结束统一接管。
