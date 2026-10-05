# GZ-PAY-106 完工报告：支付单过期后不能再付，超时后的付款不再被吞

> 主线程代为落盘（impl subagent 写 .md 被 hook 拦截，原文回传）。

## §0 自检
| 检查项 | 结果 |
|---|---|
| 分支 | RuoYi-Vue-Plus、plus-ui 均 `task/D7`，开工前干净，基线 `676dd3012` |
| 上游依赖 | 无 |
| 关键类和表 | `GzPayTransactionServiceImpl`、`PayOrderQueryServiceImpl`、`GzPayTransactionMapper`、`IWechatPayClient` real/mock 已读。`gz_pay_callback_log.process_status` varchar(16) 放得下 `late_paid`，无迁移 |
| `time_expire` 格式 | 微信 V3 官方文档 pay.weixin.qq.com/doc/v3/merchant/4012791856：RFC3339，示例 `2015-05-20T13:29:35+08:00`；不早于下单后 1 分钟、不晚于 15 天。实现格式串 `yyyy-MM-dd'T'HH:mm:ssxxx`，截到秒 |
| 蓝图 | FLOW:F-JP-06.step4、step4b |

## 改动文件
**RuoYi-Vue-Plus**（`658b8adbf`，task/D7）11 文件 +1031/-10：`GzPayTransactionQueryBo` / `GzPayTransactionVO` / `GzPayTransactionMapper` / `IGzPayTransactionService` / `GzPayTransactionServiceImpl` / `PayOrderQueryServiceImpl` / `IWechatPayClient` / `MockWechatPayClient` / `WechatPayV3ClientImpl` / 新增 `PayLatePaidTest`、`PayTimeExpireTest`。

**plus-ui**（`1850a79`，task/D7）：`src/views/gz-pay/transaction/list.vue`、`src/lang/zh_CN.ts`、`src/lang/en_US.ts`、`src/api/gz-pay/index.ts`（**越界**：TS 类型加可选 `latePaid`，否则列表页只能写 any）。

## 实现说明
1. **统一下单带 time_expire**：`UnifiedOrderRequest` 新增可空 `OffsetDateTime timeExpire`，5 参构造器显式保留；`createOrderInternal` 把落库 `expire_time`（截到秒）传下去；real 实现非空时 `PrepayRequest.setTimeExpire`；mock 记录最近一次请求（`getLastUnifiedOrderRequest()`）。
2. **标 timeout 同时关微信单**：`expireTimeoutOrders` 中 `markTimeout` affected=1 后 `closeOrder`；异常只 warn，不回滚本地 timeout、不打断整批。
3. **迟到付款记 late_paid**：回调遇本地 timeout/closed → callback_log `late_paid`（process_error 带 amount_cent / payer_total / transaction_id）+ `log.error` + 应答微信成功；不 markPaid、不分发。回调与超时并发：`markPaid` affected=0 时重读状态，若已 timeout/closed 记 late_paid 而非 duplicated。`reconcilePaid` 锁行后发现 timeout/closed 返回新枚举 `ReconcileOutcome.LATE_PAID`。查单任务新增 `selectLatePaidCheckTimeoutIds`（近 24h timeout 且无 late_paid 记录，NOT EXISTS 去重，每轮 ≤100），SUCCESS → 记 late_paid，NOTPAY → 补关微信单；进程内 10 分钟最多一次。
4. **admin 支付流水**：`latePaid=true` 筛选（late_paid 子查询）；行带 `latePaid` 标记；「只看迟到付款」复选框、行标红 +「迟到付款」标签、顶部红色提示「需在商户平台人工原路退款或补单」；详情弹窗同提示；i18n 中英齐。

## 三条硬约束证明（git diff，基线 676dd3012）
- 既有 public 方法签名零改动：被删行只有一个调用点、一行注释、两行日志、枚举末尾加逗号（追加 `LATE_PAID`）、record 组件追加 `timeExpire`（5 参构造显式保留）。
- `PayRefundController` / `PayRefundServiceImpl` / `PayRefundTxService`：`git diff --stat` 为空。
- `IWechatPayClient` 既有方法签名不变：变化只在 record 内部新增 3 行。

## AI 自测
### accept #0
```
ACCEPT#0 exit=0
name="org.dromara.gz.common.pay.service.PayTimeExpireTest" tests="5" errors="0" skipped="0" failures="0"
[gz-pay-mock] createJsapiOrder out_trade_no=PINDOU-20261005-000001 amount=3000 appid=wx2f8b93e09703f07d time_expire=2026-10-05T07:40:51+08:00
[gz-pay] createJsapiOrder out_trade_no=PINDOU-20261005-000001 ... time_expire=2026-10-05T07:40:52+08:00 → prepay_id=wx_prepay_captured
[gz-pay] createJsapiOrder out_trade_no=PINDOU-20261005-000003 ... time_expire=2026-10-05T04:05:00+00:00
[gz-pay] createJsapiOrder out_trade_no=PINDOU-20261005-000004 ... time_expire=null   ← 旧 5 参构造
```
real 通道用例用 SDK 真实 `JsapiServiceExtension` + mock 签名器 + 抓包 HTTP 客户端，断言 `/v3/pay/transactions/jsapi` 请求体含 RFC3339 `time_expire` 且与落库 `expire_time` 同一时刻。
反向验证：临时去掉 `setTimeExpire` → `Tests run: 5, Failures: 1, Errors: 1`（`realChannel_requestBodyCarriesTimeExpire` 红），已恢复。

### accept #1
```
ACCEPT#1 exit=0
name="org.dromara.gz.common.pay.service.PayLatePaidTest" tests="12" errors="0" skipped="0" failures="0"
ERROR [gz-pay] 迟到付款 out_trade_no=PINDOU-20261005-000007 ... status=timeout amount_cent=3000 payer_total=3000 transaction_id=4200002612202610050000000007 source=回调 —— 未推进 paid、未分发业务，需人工原路退款或补单
ERROR [gz-pay] 迟到付款 ... status=timeout ... source=并发超时
ERROR [gz-pay] 迟到付款 ... status=timeout ... source=查单
ERROR [gz-pay] 迟到付款 ... status=closed ... source=回调
INFO  [gz-pay] 迟到付款核查完成：扫描 timeout 单 1 / 发现迟到付款 1
INFO  [gz-pay] timeout 单微信侧仍可付，已补关微信单 out_trade_no=PINDOU-20261005-000007
WARN  [gz-pay] 超时关单后关微信单失败（本地 timeout 不回滚）id=81 ... 微信关单超时
INFO  [gz-pay] 超时关单完成：扫描 2 / 关单 2 / 跳过 0
```
12 用例：超时关微信单 / 关单失败不回滚；timeout、closed 回调记 late_paid（断言无 duplicated、无 markPaid、无分发、无 updateById）；回调与超时并发；回归 pending 正常付款与 paid 重复回调；`reconcilePaid` → LATE_PAID；24h 扫描发现丢回调 / NOTPAY 补关 / 10 分钟限流；admin 筛选 SQL 与行标记。

### 受影响模块全部单测
`mvn test -DskipTests=false -pl gz-common,gz-bean,gz-recycle,gz-jp -am` → BUILD SUCCESS
| 模块 | tests / fail / err |
|---|---|
| gz-common | 277 / 0 / 0 |
| gz-coupon | 56 / 0 / 0 |
| gz-bean | 329 / 0 / 0 |
| gz-user | 42 / 0 / 0 |
| gz-recycle | 125 / 0 / 0 |
| gz-jp | 217 / 0 / 0 |

### DB
新 mapper SQL 在 dev 库实跑：EXPLAIN 子查询命中 `idx_out_trade_no`（Extra `Not exists`）；窗口放宽到 2020 年后返回 dev 库 5 条 timeout 单。

### plus-ui
`pnpm build:prod` exit 0（19.25s；pnpm 在 `~/.nvm/versions/node/v24.11.1/bin`）。eslint 改动文件仅剩 list.vue 69/126 行两条既有 prettier 报错；`vue-tsc --noEmit` 全项目 72 条既有报错，gz-pay 相关 0 条。

## 风险
- 迟到付款只能被动发现（ERROR 日志 / admin 筛选 / 回调日志），无主动告警（不在本卡范围）。
- 每个 timeout 单 24h 窗口约被查 144 次；prod 每天 4–5 单 → 每天多几百次查单，CLOSED 不写库。
- 10 分钟限流是进程内的；多实例极端并发可能多写一条审计日志，不影响资金。
- 24h 扫描只看 timeout（ticket 原文）；closed 单回调路径同样记 late_paid。
- 真机「等 6 分钟再付，微信提示过期」只能真商户号验 → D15 R7。

## 对下游
- GZ-JP 复用支付单（REQ-SNAP-046）：「未过期」用 `expire_time > now` 且留余量（剩 <1 分钟就新建一笔）。
- 其他业务方无需改动，`createBusinessOrder` 自动带 time_expire。
