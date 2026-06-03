# GZ-PAY-102 完工报告 — 主动查单 + 补单

> SnailJob 每分钟扫 pending → 微信 V3 查单 → SUCCESS 走 PAY-101 同一幂等补单路径补单 / NOTPAY 超 30min 关单 / CLOSED→closed / PAYERROR→failed。
> V1.1 D08 波次2 · 复杂度 S · 模块 ruoyi-gz-common · 包 org.dromara.gz.common.pay

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A — 仓库非 git（`git rev-parse` 报 not a repository） |
| 上游依赖 PAY-101 已交付 | ✅ grep 确认 spi/{PayCallbackHandler,PayCallbackDispatcher,handler/PreorderPayCallbackHandler} + GzPayTransactionServiceImpl.handlePaymentNotify（含 SELECT + 状态判定 + markPaid 乐观锁 + dispatch + callback_log）全在位 |
| 包名实证 | ✅ 实际 `org.dromara.gz.common.pay`（任务卡行50 `org.dromara.gz.pay` 是笔误，已按主线程修正落位） |
| gz-common pom 含 ruoyi-common-job | ✅ GzPayExpireOrderJob / PayFundflowBillJob 在用 `@JobExecutor`，无需改 pom |
| 复用 PAY-101 补单核心（非另写） | ✅ 抽出 `applyPaid()` 私有单点，回调（行230）+ 查单 reconcilePaid（行301）两个调用点共用 |
| 状态枚举存在（doc/11 §4.2） | ✅ PayStatus.{PAID,TIMEOUT,CLOSED,FAILED,PENDING} 齐全，未新造别名 |
| 编译通过 | ✅ `mvn compile -pl ruoyi-modules/ruoyi-gz-common` BUILD SUCCESS |
| migration 最大版本 | ✅ V202606061100（PAY-104），本卡**无新 DDL**（AC10），未编辑已应用迁移 |
| ADR | N/A（任务卡标 N/A，无相关 ADR） |
| 违禁项（Quartz/sys_job INSERT/_fen/新造状态） | ✅ grep 全空（仅 javadoc 说明文字提及"不通过 INSERT sys_job"） |
| 并行安全（与 ORD-103 同波次） | ✅ 仅改 gz-common；install 用 `-pl ruoyi-modules/ruoyi-gz-common`（不加 -am） |

## 实现摘要

### 改动 / 新增文件（相对 code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/src/）

**新增（4）**
- `main/.../pay/service/IPayOrderQueryService.java` — 查单服务接口 + `ReconcileResult` 统计 record
- `main/.../pay/service/impl/PayOrderQueryServiceImpl.java` — 扫描循环 + 逐单查单 + 状态分发（SUCCESS→reconcilePaid / NOTPAY<30min 保持 / NOTPAY>30min closeOrder+timeout / CLOSED|REVOKED→closed / PAYERROR→failed / USERPAYING 保持 / 单条异常隔离）
- `main/.../pay/job/PayOrderQueryJobExecutor.java` — SnailJob 薄壳（`@Component` + `@JobExecutor(name="payOrderQueryJob")`，仅调 scanAndReconcile）
- `test/.../pay/service/PayOrderQueryServiceImplTest.java` — 7 个测试（覆盖 AC9 五条 + 并发跳过 + 单条异常隔离）

**修改（5）**
- `main/.../pay/service/internal/IWechatPayClient.java` — 加 `queryByOutTradeNo` / `closeOrder` 接口方法 + `QueryResult` record
- `main/.../pay/service/internal/MockWechatPayClient.java` — 实现查单（可配置 trade_state + payerTotal）/ 关单（计数）+ 测试注入 setter
- `main/.../pay/service/internal/WechatPayV3ClientImpl.java` — 实现 real 查单/关单（SDK `JsapiServiceExtension.queryOrderByOutTradeNo` / `closeOrder`）
- `main/.../pay/service/IGzPayTransactionService.java` — 加 `reconcilePaid()` 补单单点入口 + `ReconcileOutcome` 枚举
- `main/.../pay/service/impl/GzPayTransactionServiceImpl.java` — **抽出 `applyPaid()` 幂等补单单点**（回调 ④⑤⑥ 与查单共用）+ 新增 `reconcilePaid()`（SELECT FOR UPDATE + 状态判定 + applyPaid）
- `main/.../pay/mapper/GzPayTransactionMapper.java` — 加 `selectReconcilePendingIds`（5min-24h+LIMIT100）/ `selectByIdForUpdate`（FOR UPDATE）/ `markClosed` / `markFailed`
- `test/.../pay/service/GzPayTransactionServiceImplTest.java` — 加 3 个 reconcilePaid 单点测试（10→13 方法）

### 复用 PAY-101 补单路径（类 + 方法名）

被动回调 `GzPayTransactionServiceImpl.handlePaymentNotify` 原内联的「markPaid 乐观锁 + SPI dispatch + callback_log processed」（步骤 ④⑤⑥）抽成私有方法：

```
GzPayTransactionServiceImpl#applyPaid(GzPayTransaction tx, String transactionId,
    Long feeCent, String outTradeNo, String rawBody, String signature) : boolean
```

- 被动回调 `handlePaymentNotify` 验签 + SELECT byOutTradeNo + 已 paid 判定后 → 调 `applyPaid(...)`
- 主动查单 `reconcilePaid(txId, transactionId, feeCent, rawBody)` → `selectByIdForUpdate` 行锁 + 非 pending 跳过后 → 调**同一个** `applyPaid(...)`（signature 传 null，rawBody = 查单报文）

→ markPaid 乐观锁 / SPI `PayCallbackDispatcher.dispatch` / callback_log 写入**单点维护**，主动补单与被动回调绝无两套 paid 推进逻辑（强约束 #1 / 决策 D4）。

## AI 自测（Tier 1A）

### 编译

```
$ mvn compile -pl ruoyi-modules/ruoyi-gz-common -q
BUILD SUCCESS
（首轮报 illegal character → 踩坑：javadoc 内 CRON `0 */1` 的 `*/` 提前闭合 /** */ 块注释。改 `0 0/1` + HTML 实体 *&#47;1 修复，见下方踩坑）
```

### 单测（gz-common 全量）

```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common
[INFO] Running org.dromara.gz.common.pay.service.PayOrderQueryServiceImplTest
[INFO] Tests run: 7, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.028 s
[INFO] Running org.dromara.gz.common.pay.service.GzPayTransactionServiceImplTest
[INFO] Tests run: 13, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.116 s
...
[INFO] Tests run: 93, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

> 日志里 `ERROR ... 主动查单单条失败 id=1001` 是 `scan_singleException_isolated` 测试**故意注入**查单异常验证单条隔离（风险 R2），是预期断言路径，该测试通过。

### 新增测试方法清单（10 个，覆盖 AC9 五条 + 扩展）

PayOrderQueryServiceImplTest（7）：
```
scan_success_delegatesReconcilePaid          AC4 SUCCESS → 委托 reconcilePaid 补单单点 + 不另写 paid 推进
scan_idempotent_secondRoundSkipped           AC5 同笔连扫两轮 → 第二轮 SKIPPED_TERMINAL，补单仅计一次
scan_notpay_under30min_keepsPending          AC6 NOTPAY<30min → 保持 pending，不关单不补单
scan_notpay_over30min_closeAndTimeout        AC8 NOTPAY>30min → closeOrder + markTimeout
scan_closed_payerror_userpaying_branches     AC7 CLOSED→closed / PAYERROR→failed / USERPAYING→保持
scan_alreadyTerminal_skips                   AC5 并发 selectById 已 paid → 跳过不查单
scan_singleException_isolated                R2 单条查单异常 → 隔离不卡整批
```
GzPayTransactionServiceImplTest 新增（3）：
```
reconcilePaid_pending_marksPaidAndDispatchOnce   AC4 行锁 pending → markPaid+dispatch 一次+processed 日志
reconcilePaid_alreadyPaid_idempotentSkip         AC5 行锁已 paid → SKIPPED_TERMINAL，不二次 markPaid/dispatch
reconcilePaid_optimisticConflict_duplicated      AC5 行锁内 markPaid affected=0 → SKIPPED_TERMINAL（duplicated 审计）
```

### install 到 m2（仅 gz-common，并行安全）

```
$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-common
[INFO] Installing .../ruoyi-gz-common-5.6.1.jar to ~/.m2/.../ruoyi-gz-common-5.6.1.jar
[INFO] BUILD SUCCESS
```

## SnailJob 待注册清单（人工在控制台注册，禁 Flyway INSERT sys_job）

| 项 | 值 |
|---|---|
| 任务名称 | GZ-PAY-ORDER-QUERY |
| 执行器路由 executor_info | `payOrderQueryJob`（= `@JobExecutor(name)`） |
| 触发类型 | CRON |
| CRON 表达式 | `0 0/1 * * * ?`（每分钟，等价 `0 */1 * * * ?`，决策 D1；容器时区 Asia/Shanghai） |
| 阻塞策略 | 丢弃 DISCARD（上轮未跑完不叠加） |
| 组 | ruoyi_group |

## 是否新增 SPI 路由 key

**否。** 复用 PAY-101 既有 `payment` SPI 分发（`PayCallbackDispatcher` 按 business_type 路由），主动查单补单与被动回调走同一 `applyPaid` → `dispatch`。callback_log `callback_type` 仍恒为 `payment`，靠 raw_body 来源（查单报文 `"source":"query"` vs 解密通知报文）区分主动/被动，不新增列（决策 D5）。

## 对「PAY 三票 SPI 路由 review」的输入（R4）

- **本卡复用的路由段**：`PayCallbackDispatcher.dispatch(GzPayTransaction)` → `resolve(business_type)` → `PayCallbackHandler.onPaid`，key 空间 = business_type（preorder/gacha），callback_type = `payment`。
- **本卡未新增任何 handler / 路由 key**：查单补单不注册新 handler，完全走 PAY-101 既有 payment 分发。
- **三票交集点**：PAY-102（主动查单补单，payment key）/ PAY-103（退款，独立 callback_type=`refund` key 空间）/ PAY-104（对账批，不走 SPI 直接回写 fee_cent）。三者落地后 review 确认 payment（PAY-101/102 共用）与 refund（PAY-103）两套 key 空间不混用即可，**本卡不引入撞 key 风险**。

## 风险提示 / 已知 issue

- **R-真实端到端（外部前置风险）**：真实微信 V3 查单 `GET /v3/pay/transactions/out-trade-no/{no}` + 关单 `POST .../close` 依赖甲方商户号 + cert + apiV3Key（申请中）。`WechatPayV3ClientImpl` 已用官方 SDK 0.2.17（`JsapiServiceExtension.queryOrderByOutTradeNo` / `closeOrder`）实现，但**未做真实端到端联调**。本日 DoD = mock 全链路（Kevin 决策 1），real 联调列 buffer 期补打。
- **R2 已缓解**：handler 异常 → reconcilePaid 整笔事务回滚（保持 pending）→ 下轮重扫重试；单条查单异常被扫描循环隔离不卡整批。连续失败由 callback_log `process_status` / 应用日志 ERROR 暴露，运维介入。
- **关单非事务保护**（AC8）：`closeOrder`（微信）+ `markTimeout`（本地）两步非原子。若关单成功但 markTimeout affected=0（并发已变）→ 下轮重扫，微信关单幂等，安全。
- **30min 关单时间基准**：用 `create_time`（BaseEntity，java.util.Date）+ 30min < now 判定（不用 expire_time，expire_time = create+5min 是回调超时用途，语义不同）。

## 对下游 ticket 的提示

- **PAY 三票 SPI review（主线程接管）**：本卡复用 payment key，无撞 key；review 时确认 refund（PAY-103）独立 key 空间即可。
- **PAY-103 退款**：退款回调请走**独立 callback_type=refund + 独立 SPI key 空间**（PayCallbackHandler 仅服务支付成功 payment，不要复用本卡 payment 路由）。
- **集成测试（Tier 1B 主线程接管）**：可用 `gz.pay.client.mode=mock` + `MockWechatPayClient.setQueryTradeState(...)` 注入各 trade_state，INSERT 一条 `create_time=NOW()-INTERVAL 10 MINUTE` + `status='pending'` 的 gz_pay_transaction（业务类型 preorder + 已注册 PreorderPayCallbackHandler）→ 调 `scanAndReconcile()` 验证推进 paid + handler 出单 + callback_log 落 raw_body=查单报文。
- **真实端到端**：商户配置就绪后切 `real` profile，注入 env（WECHAT_PAY_MCH_ID 等），用 0.01 元单验证查单/关单/补单全链路。

## 踩坑记录（learnings 候选）

**javadoc 块注释内含 CRON `*/N` 提前闭合 `/** */`**：`@JobExecutor` javadoc 写 CRON 表达式 `0 */1 * * * ?` 时，`*/` 序列把 `/** ... */` 块注释提前闭合，后续中文字符全被当代码体非法字符（`illegal character: '，'` 误导成"编码问题"，实为注释提前结束）。修复：javadoc 内 CRON 改 `0 0/1`（功能等价无 `*/`）或用 HTML 实体 `*&#47;1`。任何 java 块注释里写含 `*/` 的字面量（CRON / 正则 / 路径）都会触发，注意。

## §AI 测试段（Tier 1B — kevin-qa / 主线程接管追加）

（占位。本卡 kevin-coder 嵌套限制无法 spawn kevin-qa；Tier 1A 已做扎实，Tier 1B 集成测试由主线程接管追写到此。）
