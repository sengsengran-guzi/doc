# GZ-PAY-103 完工报告 — 退款服务（仅全额 / @SaCheckPermission / V3 退款回调 / gz_pay_refund）

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git 状态 | code/main 非 git 仓库（项目从零起，符合约定）；不 commit |
| 上游 PAY-101 已落 | ✅ `gz_pay_transaction` / `gz_pay_callback_log` 已建（V202606041200）；支付 SPI `PayCallbackHandler`/`PayCallbackDispatcher`/`PreorderPayCallbackHandler` 已存在 |
| 关键类/表存在 | ✅ `IWechatPayClient`/`MockWechatPayClient`/`WechatPayV3ClientImpl`/`PayOrderNoGenerator`/`GzPayCallbackLogMapper` 均在 |
| 包名实证 | ✅ 实际 `org.dromara.gz.common.pay.*`（任务卡行77 `org.dromara.gz.pay` 是笔误，已按实际包名落地） |
| migration 时间戳 | ✅ 现最大 V202606061100（PAY-104）；本卡用 V202606061300（建表）+ V202606061301（菜单），均 > 最大值 |
| menu_id 5100 段占用 | ✅ grep 确认 5100-5105 已用（PAY-001）；本卡用 5106/5107/5108 |
| 编译通过 | ✅ `mvn compile -pl ruoyi-gz-common` EXIT 0 |
| ADR 已读 | ADR-0004（mp+admin 权限底座，本卡 admin 走 @SaCheckPermission） |

### 支付 SPI 现状硬探（grep 实证）

PAY-101 支付 SPI：`PayCallbackHandler`（key=business_type，`onPaid`）+ `PayCallbackDispatcher`（payment 注册中心，启动 fail-fast）+ `PreorderPayCallbackHandler`（占位）。callback_log `callback_type='payment'`。`PayCallbackHandler` javadoc §key 空间约定 R3 已明示「退款回调走独立 SPI key 空间」——本卡严格遵循。

## 退款 SPI 路由 key 空间说明（供 PAY 三票串行 review，README R2）

| 维度 | 支付（PAY-101/102） | 退款（PAY-103，本卡） | 隔离确认 |
|---|---|---|---|
| SPI 接口 | `PayCallbackHandler.onPaid` | `IRefundCallbackHandler.onRefunded` | 不同接口 |
| 注册中心 | `PayCallbackDispatcher`（payment 路由表） | `RefundCallbackDispatcher`（refund 路由表） | **独立 Bean，路由表完全隔离** |
| 路由 key | business_type（preorder/gacha） | business_type（preorder/gacha） | 取值同，但**各自 dispatcher 各自命中**，不撞 |
| callback_log.callback_type | `'payment'` | `'refund'` | **DB 层隔离** |
| 回调 endpoint | `/api/pay/v3/notify` | `/api/pay/v3/refund-notify` | **独立 endpoint** |
| 占位 handler | `PreorderPayCallbackHandler` | `PreorderRefundCallbackHandler` | 不同类 |

结论：退款 SPI 与支付 SPI **完全平行、零交叉**，同 business_type 在两个 dispatcher 各自路由，绝不混淆。

## 实现摘要

### 新增产物（后端 ruoyi-gz-common，包 org.dromara.gz.common.pay）

- `domain/entity/GzPayRefund.java` — 退款单 entity（含非持久化 `transientTransactionRowId`）
- `domain/bo/RefundApplyBo.java` — 申请入参（仅 `transactionId`+`reason`，**无 amountCent**）
- `domain/vo/GzPayRefundVO.java` — VO（id String 化，refund_no 业务码）
- `mapper/GzPayRefundMapper.java` — countActiveByTransactionId / selectByRefundNoForUpdate / markRefunded / markFailed / selectMaxDailySeq
- `service/IPayRefundService.java` + `service/impl/PayRefundServiceImpl.java` — apply / handleRefundNotify / selectPageList
- `service/internal/PayRefundTxService.java` — 退款 DB 事务原子操作（独立 Bean，规避 self-invocation 事务失效）
- `service/spi/IRefundCallbackHandler.java` + `service/spi/RefundCallbackDispatcher.java` + `service/spi/handler/PreorderRefundCallbackHandler.java` — 退款 SPI（独立 key 空间）
- `controller/PayRefundController.java` — `POST /system/gz/pay/refund/apply`（@SaCheckPermission + @Log OTHER）+ `GET .../list`
- `controller/external/WechatPayRefundNotifyController.java` — `POST /api/pay/v3/refund-notify`（@SaIgnore）

### 改动的既有文件（后端）

- `enums/PayStatus.java` — 加 `REFUNDING`/`REFUNDED` 常量
- `service/internal/IWechatPayClient.java` — 加 `refund()` / `parseAndVerifyRefundNotify()` + records（RefundRequest/RefundResult/RefundCallbackResult）
- `service/internal/MockWechatPayClient.java` — 实现退款 / 退款回调 mock + `buildMockRefundCallbackBody` + `setRefundAcceptFail`
- `service/internal/WechatPayV3ClientImpl.java` — real 退款（SDK RefundService.create）+ 退款回调（NotificationParser parse RefundNotification，复用同套 AES-GCM）
- `service/internal/PayOrderNoGenerator.java` — 加 `generateRefundNo()`（前缀 RF，查 refund 表序号空间）+ 注入 GzPayRefundMapper
- `config/WechatPayProperties.java` — 加 `refundNotifyUrl`
- `mapper/GzPayTransactionMapper.java` — 加 markRefunding / markRefunded / rollbackRefundingToPaid（状态机守卫 UPDATE）
- `test/.../GzPayBusinessFullChainMockTest.java` — 适配 PayOrderNoGenerator 新构造参数（加 refundMapper mock）

### 新增产物（admin plus-ui）

- `src/api/gz-pay/refund.ts` — applyRefund / listRefund + 类型（id String）
- `src/views/gz-pay/refund/index.vue` — 退款记录 el-table + 「申请退款」disabled 占位（订单看板未完工）
- `src/views/gz-pay/refund/RefundApplyDialog.vue` — 退款弹窗（只读全额金额 + reason textarea 必填≤255 + v-hasPermi）
- `src/lang/zh_CN.ts` / `src/lang/en_US.ts` — `gzRefund` i18n 段（zh/en）

### DDL（Flyway）

- `V202606061300__GZ-PAY-103-create-gz_pay_refund.sql` — 建表
- `V202606061301__GZ-PAY-103-menu.sql` — 菜单 5106/5107/5108 + owner(100) 授权

#### gz_pay_refund 表/字段（严格对齐 doc/11 §4.4）

| 列 | 类型 | 说明 |
|---|---|---|
| id | BIGINT UNSIGNED PK | 不暴露前端 |
| refund_no | VARCHAR(64) NOT NULL | RF-yyyyMMdd-6位 |
| transaction_id | VARCHAR(64) NOT NULL | FK 微信交易号 |
| out_trade_no | VARCHAR(64) NOT NULL | 原业务订单号 |
| wechat_refund_id | VARCHAR(64) NULL | 微信退款单号 |
| **refund_amount_cent** | BIGINT NOT NULL | 分（**非 _fen**），全额=原单 amount_cent |
| reason | VARCHAR(255) NOT NULL | 退款原因 |
| status | VARCHAR(16) DEFAULT 'refunding' | refunding/refunded/failed |
| triggered_by | VARCHAR(64) NOT NULL | username（**非 operator_id**） |
| triggered_time | DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3) | |
| refunded_time | DATETIME(3) NULL | |
| + 公共字段 | | tenant_id DEFAULT '1001' / del_flag 2 值 |

约束：`UNIQUE(tenant_id, refund_no)` / `UNIQUE(tenant_id, wechat_refund_id)`（NULL 并存）/ IDX(tenant_id,transaction_id)、(tenant_id,status)、(tenant_id,out_trade_no)。**未建 gz_pay_order，未在 gz_pay_transaction 加 refund_fen 累计列**。

### 退款回调 endpoint

`POST /api/pay/v3/refund-notify`（@SaIgnore，与 PAY-001 `/api/pay/v3/notify` 分离），复用 V3 NotificationParser AES-GCM。

## AI 自测（Tier 1A）

### 编译 + install

```
$ mvn compile -pl ruoyi-modules/ruoyi-gz-common -q
COMPILE_EXIT=0

$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-common -q
INSTALL_EXIT=0
```

### 单测（AC9 ≥ 4，本卡 5 个）

```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -Dtest=PayRefundServiceImplTest
[INFO] Tests run: 5, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.743 s -- in PayRefundServiceImplTest
[INFO] BUILD SUCCESS
```

5 个测试方法（覆盖 AC9 全部分支）：
1. happy path：paid → apply → mock 受理成功 → V3 退款回调 SUCCESS → refund=refunded + transaction=refunded + 退款 SPI 命中 preorder（callback_type='refund'）
2. 非 paid（pending）不允许退 → ServiceException「仅已支付」
3. 重复退拦截：同 transaction 已 refunding → ServiceException「已有进行中或已完成的退款」
4. 回调幂等：已 refunded 二次回调 → duplicated，不重复变更
5. 受理失败回滚：mock 受理失败 → refund=failed + transaction 回 paid + ServiceException

退款 SPI 命中日志（happy path raw）：
```
RefundCallbackDispatcher -- [gz-pay] 退款回调 SPI 路由表就绪，已注册 1 个 handler：[preorder]
MockWechatPayClient -- [gz-pay-mock] refund ... → 受理成功 refund_id=mock_refund_id_RF-... (PROCESSING)
RefundCallbackDispatcher -- [gz-pay] 退款 SPI 分发 business_type=preorder → PreorderRefundCallbackHandler refund_no=RF-...
PreorderRefundCallbackHandler -- [gz-pay] PreorderRefundCallbackHandler.onRefunded 命中（占位）... SKU 库存不归还 待 ORD-104 填实现
```

### pay 包全量回归（确认未破坏上游 PAY-001/101/102/104 测试）

```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -Dtest='org.dromara.gz.common.pay.**'
GzPayBusinessFullChainMockTest      Tests run: 2  ✅（已适配 PayOrderNoGenerator 新构造）
GzPayTransactionServiceImplTest     Tests run: 13 ✅
PayFundflowBillServiceImplTest      Tests run: 10 ✅
PayOrderQueryServiceImplTest        Tests run: 7  ✅
PayCallbackDispatcherTest           Tests run: 6  ✅
PayRefundServiceImplTest            Tests run: 5  ✅
[INFO] Tests run: 43, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

### admin build（plus-ui）

```
$ npx vue-tsc --noEmit  → refund 相关文件 0 新增类型错误
$ pnpm build:prod        → 构建成功，emit dist/assets/RefundApplyDialog-C1Mq_ijz.js（+ refund/index 进 index-* chunk）
```

## 风险提示 / 已知 issue

- R1 真实退款端到端 = **外部前置风险**（商户号 + apiV3Key + 商户私钥未到位，Kevin 决策 1）。本卡 DoD = mock 全链路自测；real 路径已实现（SDK RefundService.create + NotificationParser parse RefundNotification）但**未做真实联调**。staging/prod 切 real 需注入 `gz.pay.refund-notify-url`（完整域名 URL）。
- R3 真实退款 API 失败（余额不足/网络）→ status 卡 refunding。本卡：受理失败已回滚 paid；回调返 ABNORMAL/CLOSED → failed 留人工（doc/10 §6.E4）。admin 退款记录列表可见 failed 态供人工介入；refunding 态重试退款入口待订单看板（ADMIN-103）落地后接通。
- 受理成功返回的 refund_id 暂不落库（以异步回调写 wechat_refund_id 为准，避免半态写入）；若需「受理后即展示微信退款单号」可在 D1x 增量补。
- 「申请退款」按钮当前 disabled 占位（订单详情看板 ADMIN-103 未完工）。RefundApplyDialog 已就绪并 `defineExpose({ open })`，看板落地后直接 `dialogRef.open(txId, outTradeNo, amountCent)` 接通，本卡不依赖看板。

## 对下游 ticket 的提示

- **GZ-ORD-104（预购退款 handler 填实现）**：把 `PreorderRefundCallbackHandler.onRefunded` 填实——注入 IGzOrdOrderService 把 out_trade_no/business_order_no 对应的 `gz_ord_order` paid→refunded（同 PAY-103 退款回调事务 REQUIRED）。**强约束（doc/10 §6.N10 / §7.N13）：退款 SKU 库存不归还**（货已采购），仅推进订单状态，不回写 gz_ord_sku.stock。可二选一：把该 handler 移到 ruoyi-gz-ord 模块，或在本类注入 ord service（§0 自检定）。
- **GZ-ORD-105 / GACHA 订单详情（mp）**：C 端**绝对无退款入口**（合同 §4.5 / 强约束 #5）。订单详情页仅展示文案「如需退款请联系客服」+ 客服入口（GZ-SYS-004 已实现）。§0 自检 grep 确认无「申请退款」按钮，Kevin 批量人验必查。
- **GACHA 退款 handler**：扭蛋退款需自行实现 `IRefundCallbackHandler`（supportedBusinessType=gacha），退款回滚策略（是否回收奖品/库存）由扭蛋域决策。
- **ADMIN-103 订单看板**：退款按钮接通点 = `dialogRef.open(交易行 id, out_trade_no, amount_cent)`；退款记录可复用 `/system/gz/pay/refund/list?outTradeNo=`。

## 收尾说明

- 退款 admin ticket（纯 admin/后端，C 端无退款入口、无 mp 人验面）→ **跳过 Tier 2 入口可达**（CLAUDE.md §8.2 例外：Tech 段无 miniapp/ + AC 无微信原生能力）。AI Tier 1A 全 ✅ 即终态。
- 嵌套限制无法 spawn kevin-qa；Tier 1A 已做扎实（编译 + install + 5 退款单测 + 43 pay 全量回归 + admin build）。
- 未 commit（按要求）。

## §AI 测试段（kevin-qa 完工后追加）

（本卡纯 admin/后端，无 mp 人验面；如需 Tier 1B 由 Kevin 主线程 spawn kevin-qa 跑 admin Playwright + 后端集成）
