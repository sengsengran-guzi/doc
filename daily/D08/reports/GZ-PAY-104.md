# GZ-PAY-104 完工报告 — 业务通道账单对账批

> 每日 SnailJob 拉前一业务日微信资金账单（/v3/bill/fundflowbill），解析 CSV 按 transaction_id
> 覆盖式回写 gz_pay_transaction.fee_cent（fee 唯一真源）。纯后端跑批，无 mp / admin 页面 → 无人验。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A — 项目目录非 git 仓库（`git rev-parse` fatal not a repository），按约定不 commit |
| 上游依赖 GZ-PAY-101 merge | ✅ `pay/service/spi/`（PayCallbackHandler / PayCallbackDispatcher / PreorderPayCallbackHandler）已存在 |
| 支付模块定位（任务卡 Tech 笔误修正） | ✅ 模块=`ruoyi-gz-common` 包=`org.dromara.gz.common.pay.*`（无 `ruoyi-gz-pay` 模块），按主线程实证修正落地 |
| `gz_pay_transaction.fee_cent` 列存在 | ✅ V202606041200 行 77：`fee_cent BIGINT NULL`（仅 UPDATE 不 ALTER） |
| `gz_pay_transaction.transaction_id` 列存在 | ✅ V202606041200 行 80：`transaction_id VARCHAR(64) NULL` + `uk_tenant_transaction_id` |
| `gz_pay_transaction.status='paid'` 可过滤 | ✅ V202606041200 行 78：status 含 paid 态 |
| gz-common pom 有 `ruoyi-common-job` | ✅ pom.xml 行 87（SnailJob @JobExecutor 无需改 pom） |
| 编译基线（写前） | ✅ `mvn compile -pl ruoyi-gz-common` exit 0 |
| migration 时间戳 > 当前最大 | ✅ V202606061100 > V202606060901（GZ-ORD-101-menu） |
| 未注册任何 SPI handler（R2） | ✅ spi/handler/ 仅 PreorderPayCallbackHandler（PAY-101 的），我 3 个新文件无 Handler/onPaid/SPI 引用 |

### 权威蓝图引用摘录（§0 强制）

- **doc/10 §10 E6**：系统按 transaction 级实际 fee 字段汇总，**不依赖固定费率** → 本卡是其数据准备前置，把真实笔费灌进 `fee_cent`。
- **doc/11 §4.2**：回写目标 `fee_cent`（分）/ 关联键 `transaction_id` / 过滤 `status='paid'`。
- **doc/11 F4.3 / F9.2**：V3 回调 body **不含 fee** → 唯一来源 = 每日拉 `/v3/bill/fundflowbill`。本卡落地这条裁定。
- **doc/11 §9.1**：`gz_recon_daily.system_fee_cent = SUM(fee_cent WHERE business_type=? AND status='paid' AND DATE(paid_time)=?)` → 本卡是其上游唯一数据源（不回写 → D11 对账"通道费"列恒 0）。

## 实现摘要

> DDL + entity + mapper + CSV 解析器/构造器/row + IWechatPayClient.downloadFundFlowBill + MockWechatPayClient
> 由前序 partial 落地（已就位且齐全）。本次补齐缺的两块：**service（可单测核心）+ SnailJob 薄壳**，并写齐单测。

新增文件（本次）：

| 文件 | 行数 | 作用 |
|---|---|---|
| `pay/service/PayFundflowBillService.java` | 69 | service 接口 + `ReconcileResult` record（billTotal/matched/transactionNotFound/paidNoBill，AC5 可断言） |
| `pay/service/impl/PayFundflowBillServiceImpl.java` | 120 | 核心：拉账单→sha1 校验→解析→幂等 upsert→覆盖式回写→缺账/孤儿告警（AC3-6） |
| `pay/job/PayFundflowBillJob.java` | 70 | SnailJob 薄壳 `@JobExecutor(name="gzPayFundflowBillJob")`，仅取 bizDate=前一日→调 service→返结果 |
| `pay/service/PayFundflowBillServiceImplTest.java`（test） | 332 | 10 个单测，覆盖 CSV 解析/回写/AC5 两计数/AC6 幂等/hash 失败 |

已就位（前序 partial，本卡读取复用，未改）：
- DDL `V202606061100__GZ-PAY-104-pay-bill-fundflow.sql`（建 `gz_pay_bill_fundflow`）
- `domain/entity/GzPayBillFundflow.java` / `mapper/GzPayBillFundflowMapper.java`（upsertBill / updateFeeCentByTransactionId / selectPaidTransactionIdsByDate / countByBillDate）
- `service/internal/bill/{FundFlowBillCsvParser,FundFlowBillCsvBuilder,FundFlowBillRow}.java`
- `service/internal/IWechatPayClient.java`（扩 `downloadFundFlowBill(LocalDate)` + `FundFlowBill` record）+ `MockWechatPayClient`（setOverrideBillCsv/HashValue 注入钩子）

### DDL 表/字段（gz_pay_bill_fundflow）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK AUTO | 主键（不暴露前端） |
| bill_date | DATE NOT NULL | 账单业务日 |
| transaction_id | VARCHAR(64) NOT NULL | 微信交易号（关联回写键） |
| out_trade_no | VARCHAR(64) NULL | 业务订单号（冗余追溯） |
| fee_cent | BIGINT NOT NULL | 该笔真实通道手续费（分） |
| raw_line | TEXT NULL | 原始 CSV 行（争议追溯） |
| tenant_id | VARCHAR(20) NOT NULL DEFAULT '1001' | 多租户（INSERT 不显式赋，拦截器注入） |
| del_flag | CHAR(1) '0'/'1' | 软删 2 值 |
| + create/update_dept/by/time + remark | | 公共字段 |

约束：`UNIQUE uk_tenant_bill_date_transaction_id (tenant_id, bill_date, transaction_id)`（AC6 幂等基础）+ idx_bill_date + idx_transaction_id。**未改 gz_pay_transaction 结构**（仅 UPDATE）。

## AI 自测（Tier 1A）

### 1. 编译（写后，gz-common 单模块，无 -am）

```
$ mvn compile -pl ruoyi-modules/ruoyi-gz-common -q
EXIT=0   （无 error 输出）
```

### 2. 单测 — PayFundflowBillServiceImplTest（10 用例全过）

```
[INFO] Running org.dromara.gz.common.pay.service.PayFundflowBillServiceImplTest
15:47:23 WARN  ...PayFundflowBillServiceImpl -- [gz-pay-bill] 孤儿账单行（账单有但系统无 paid 交易）bill_date=2026-06-05 count=1 txnIds=[4200WX_ORPHAN]
15:47:23 WARN  ...PayFundflowBillServiceImpl -- [gz-pay-bill] 缺账（系统当日 paid 交易账单缺其行）bill_date=2026-06-05 count=1 txnIds=[4200WX_MISSING]
15:47:23 INFO  ...PayFundflowBillServiceImpl -- [gz-pay-bill] 对账完成 bill_date=2026-06-05 billTotal=2 matched=1 transactionNotFound=1 paidNoBill=1
[INFO] Tests run: 10, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.647 s -- in PayFundflowBillServiceImplTest
[INFO] BUILD SUCCESS
```

用例清单（AC 映射）：
1. happy path 2 笔全匹配回写（元→分换算断言：0.01→1 / 0.59→59）— AC3/AC4
2. 覆盖式回写 — 同交易号 2 个手续费行聚合 59 分一次性回写（非两次累加）— AC4
3. 孤儿账单 — 回写 affected=0 → transactionNotFound=1（明细列表）— AC5 ①
4. 缺账 — 系统 paid 但账单缺 → paidNoBill=1（明细列表）— AC5 ②
5. 孤儿+缺账同时触发（mock AC7 全链路）→ 两计数均 >0 — AC5/AC7
6. 同日重跑幂等 — upsert 调用对称、同笔 fee 始终 1（不累加）— AC6
7. hash 校验失败 → ServiceException + 不 upsert 不回写 — AC3
8. CSV 缺关键列（业务类型）→ 解析抛错 — AC3
9. 明细段中段空行 → 跳过容错、正常笔仍解析 — CSV 健壮性
10. bizDate=null → 早失败、不拉账单不回写 — 入参校验

### 3. 全模块回归（83 用例，0 失败）

```
[INFO] Tests run: 83, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
（含 PAY-001/101 既有 12 用例 + dashboard/wechat/staff 等，未被本卡影响。GzDashboardServiceImplTest 的单条 ERROR 日志是其自身异常路径断言，该测试 4/4 绿。）

### 4. 落 .m2（并行安全，仅 gz-common，无 -am）

```
$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-common
[INFO] Installing .../ruoyi-gz-common-5.6.1.jar to ~/.m2/.../ruoyi-gz-common-5.6.1.jar
[INFO] BUILD SUCCESS
```

## mock 全链路结论（AC7 = 本日 DoD）

`gz.pay.client.mode=mock`（matchIfMissing=true）→ `MockWechatPayClient.downloadFundFlowBill` 返回
`FundFlowBillCsvBuilder` 构造的可控 CSV（默认 2 笔 / 单测注入「正常+孤儿+缺账」）+ 自匹配 sha1。
单测驱动 AC3（解析+hash 校验）→ AC4（覆盖式回写）→ AC5（两类计数被触发，WARN 含明细 txnId 列表）→
AC6（幂等）全链路通过。**真实账单拉取 = 外部前置风险 R1（甲方商户配置滞后），不当默认就绪。**

## SnailJob 注册清单（人工在 SnailJob 控制台注册，不写迁移）

| 项 | 值 |
|---|---|
| 任务名称 | GZ-PAY-FUNDFLOW-BILL |
| 执行器路由 executor_info | `gzPayFundflowBillJob`（= `@JobExecutor(name)`） |
| 触发类型 / CRON | CRON `0 30 3 * * ?`（凌晨 3:30，账单 T+1 已生成，容器时区 Asia/Shanghai） |
| 阻塞策略 | 丢弃（DISCARD） |
| 组 | ruoyi_group |

bizDate 由壳取 `LocalDate.now().minusDays(1)`（前一业务日，账单 T+1 可用）。

## 是否注册 SPI handler

**否**（R2 遵守）：本卡是主动拉账单跑批，不注册支付/退款 SPI 回调 handler，不抢 PAY-102/103 的 SPI key。
spi/handler/ 仅含 PAY-101 的 PreorderPayCallbackHandler，本卡未新增。

## 风险提示 / 已知 issue

- **R1 外部前置（甲方商户配置）**：真实 `/v3/bill/fundflowbill` 需商户号 + cert + apiV3Key 就绪。本卡 DoD 仅认 mock 全链路；真实账单 CSV 列序/手续费列名以官方文档为准，真实端到端验证不当就绪 → 上线前需 real 模式回归。
- **多租户**：cron 用 `TenantHelper.ignore` + 常量 `TENANT_ID="1001"`（与 GzDashboardServiceImpl 同口径，V1.0 单租户）。未来多租户需改为遍历租户列表分批 —— 已在代码注释标注。
- **`updateFeeCentByTransactionId` affected 语义**：mapper 返回受影响行数，本卡用 `affected >= 1` 判命中。同一 transaction_id 在 gz_pay_transaction 至多 1 条 paid（uk_tenant_transaction_id 兜底），实际仅 0/1。
- 待 Kevin 批量人验关注：N/A — 纯后端 ticket，无 mp / admin 页面，AI Tier 1A ✅ 即终态（CLAUDE.md §8.2）。

## 对 D11 GZ-ADMIN-105 对账契约提示

- 本卡**只灌 `gz_pay_transaction.fee_cent`**（真实笔费），**不建 gz_recon_* 表、不算汇总、不做业务线 attribution** —— 那是 ADMIN-105 的范围。
- ADMIN-105 计算 `gz_recon_daily.system_fee_cent` 时直接 `SUM(gz_pay_transaction.fee_cent WHERE business_type=? AND status='paid' AND DATE(paid_time)=?)`（doc/11 §9.1）；本卡保证该列有真源。
- **fee_cent 可能为 NULL**（PAY-104 跑批未覆盖到的交易 / 账单缺该笔 = paidNoBill）→ ADMIN-105 SUM 时注意 `COALESCE(fee_cent,0)` 或 `WHERE fee_cent IS NOT NULL`，并把 paidNoBill 缺口体现在对账差异。
- `business_type='test'` 交易本卡照常回写 fee_cent（不预过滤）→ ADMIN-105 对账阶段才 exclude test 单（doc/10 §10 Q10.2 业务线 attribution）。
- 审计追溯：`gz_pay_bill_fundflow.raw_line` 存原始 CSV 行，对账争议时可回溯每笔 fee 来源。

## §AI 测试段（kevin-qa Tier 1B）

> 嵌套 spawn 限制 → 本 subagent 无法 spawn kevin-qa。Tier 1A 已做扎实（编译 + 10 单测 + 83 全模块回归 + mock 全链路 + .m2 install）。Tier 1B（集成 / 启动 Flyway 跑 DDL 真建表 + 真 DB upsert/回写）由主线程统一接管。
