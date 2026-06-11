# GZ-ADMIN-105 ⭐ — 完工报告（对账中心 / 合同 §4.1 4% 分成兑现核心）

> 接手背景：上一会话在实现中途崩溃（无 _HANDOFF.md，reports 空）。§0 自检发现后端 entity/vo/service/job/2 迁移已在位，但 **service impl 引用的 `ReconCalculator` + 4 个 mapper + controller 全缺失 → 当时不可编译**；plus-ui 前端整缺。本会话补齐全部缺口并完成 AC9 三层比对（误差=0）。

---

## §0 自检结果

| 检查项 | 结果 | 备注 |
|---|---|---|
| 仓库 git | N/A | 本项目 `is git repository: false`，无 diff，下列「改动文件」按实际产物列 |
| 上游依赖 merge | ✅ | `GZ-PAY-104`（fee_cent 来源）/ `GZ-PAY-103`（gz_pay_refund）/ `GZ-ADMIN-103` 迁移均在位（grep migration 目录命中） |
| 上游表/列存在 | ✅ | `gz_pay_transaction`（含 `fee_cent` / `paid_time` / `business_type`）+ `gz_pay_refund`（`refund_amount_cent` / `refunded_time` / `out_trade_no` FK）真 MySQL 确认 |
| recon 4 表 | ✅ 从零建 | `gz_recon_daily/monthly/exception/settle`（迁移 V202606240900 应用后真库确认 4 表在位） |
| 编译通过 | ✅ | `mvn -o install -DskipTests -pl ruoyi-modules/ruoyi-gz-common -am` BUILD SUCCESS |
| 权威蓝图引用 | doc/11 §9.1 / §9.2 / §9.4 / §4.6 + doc/10 §10（C4 / Q10.4 / E5） | 口径逐字落地，见末节原文引证 |
| ADR 已读 | 无相关（本卡 mock 自测口径已由 doc/11 §9 + 合同 §4.1 锁定，无需新 ADR） | 真实通道费颗粒度分歧才升 ADR-V1.1-FN-01，本卡 mock 模式未触发 |
| 合同范围 | V1.1 | doc/02-需求拆解 §3.5 |

### §0 自检命令 + 原始输出

```
$ ls .../db/migration/ | grep -E 'gz_recon|GZ-ADMIN-105'
V202606240900__GZ-ADMIN-105-create-gz_recon-tables.sql
V202606240901__GZ-ADMIN-105-menu-dict-config.sql

$ ls .../db/migration/ | grep -E 'GZ-PAY-104|GZ-PAY-103|GZ-ADMIN-103'
V202606061100__GZ-PAY-104-pay-bill-fundflow.sql
V202606061300__GZ-PAY-103-create-gz_pay_refund.sql
V202606061301__GZ-PAY-103-menu.sql
V202606181000__GZ-ADMIN-103-menu.sql

# 上一会话遗留 service impl 引用但缺失的 5 个文件（导致不可编译，本会话补齐）：
#   service/internal/ReconCalculator.java
#   mapper/GzReconSourceMapper.java / GzReconDailyMapper.java / GzReconMonthlyMapper.java / GzReconSettleMapper.java
#   controller/admin/GzReconReconcileAdminController.java
```

---

## 实现摘要

### 本会话新增/改动文件

```
后端（新增，补齐编译缺口）：
  ruoyi-gz-common/.../recon/service/internal/ReconCalculator.java          settle MAX0 + commission floor 纯函数
  ruoyi-gz-common/.../recon/mapper/GzReconSourceMapper.java                源表聚合 SQL（gmv/fee/refund/明细）
  ruoyi-gz-common/.../recon/mapper/GzReconDailyMapper.java                 UPSERT + sumDailyByMonth
  ruoyi-gz-common/.../recon/mapper/GzReconMonthlyMapper.java               UPSERT + sumCommissionByMonths
  ruoyi-gz-common/.../recon/mapper/GzReconSettleMapper.java                UPSERT
  ruoyi-gz-common/.../recon/controller/admin/GzReconReconcileAdminController.java   summary/monthly/daily/settle/export
后端（新增测试）：
  ruoyi-gz-common/src/test/.../recon/service/GzReconBatchServiceImplTest.java       AC10 业务规则 7 测
后端（改）：
  ruoyi-gz-common/src/test/.../recon/service/ReconCalculatorTest.java               补 @Tag("dev")（原缺，surefire 按 profile tag 过滤跑不到）

Admin 前端（新增）：
  plus-ui/src/api/gz-recon/reconcile.ts                  summary/monthly/daily/settle 封装
  plus-ui/src/views/gz-recon/reconcile/index.vue         el-tabs A/B + 月份区间 + 四栏 el-statistic + 分成卡片 + 月度明细 + 导出
  plus-ui/src/views/gz-recon/settle/index.vue            季度结算列表
Admin 前端（改）：
  plus-ui/src/lang/zh_CN.ts / en_US.ts                   +gzRecon / gzReconSettle i18n 段

上一会话已在位（本会话验证可编译/口径正确，未改）：
  recon/domain/entity/{GzReconDaily,GzReconMonthly,GzReconException,GzReconSettle}.java
  recon/domain/vo/{ReconSummaryVo,GzReconDailyVo,GzReconMonthlyVo,GzReconSettleVo,ReconDetailRowVo}.java
  recon/domain/excel/ReconExportRowVo.java
  recon/service/{IGzReconBatchService,IGzReconQueryService}.java + impl/{GzReconBatchServiceImpl,GzReconQueryServiceImpl}.java
  recon/job/{GzReconDailyJobExecutor,GzReconMonthlyJobExecutor,GzReconSettleJobExecutor}.java
  db/migration/V202606240900__GZ-ADMIN-105-create-gz_recon-tables.sql
  db/migration/V202606240901__GZ-ADMIN-105-menu-dict-config.sql
```

### 关键口径落地点（逐字 doc/11 §9）

- `ReconCalculator.settleCent` = `Math.max(0, gmv − refund − fee)`（月度层归零，daily 层 service 内 `gmv−refund−fee` 不归零如实记差值）
- `ReconCalculator.commissionCent` = `settle × rateBp / 10000`（long 整除 = 向下取整到分）
- `GzReconSourceMapper.sumRefundCent`：`gz_pay_refund JOIN gz_pay_transaction` 取 business_type，按 `DATE(refunded_time)` 归属（C4）
- 业务线分流：service `RECON_BUSINESS_TYPES = [preorder, gacha]`，`test`/`pindou` 天然不进（从不查询）

---

## AI 自测

### 1. 编译 + install（BUILD SUCCESS）

```
$ mvn -o install -DskipTests -pl ruoyi-modules/ruoyi-gz-common -am | tail
[INFO] ruoyi-common-job ................................... SUCCESS [  0.063 s]
[INFO] ruoyi-gz-common .................................... SUCCESS [  0.192 s]
[INFO] BUILD SUCCESS
```

### 2. 单测 13/13（ReconCalculator 6 + BatchService 7，AC10）

```
$ mvn -o test -pl ruoyi-modules/ruoyi-gz-common -DskipTests=false \
    -Dtest='ReconCalculatorTest,GzReconBatchServiceImplTest'
[INFO] Tests run: 7, Failures: 0, Errors: 0, Skipped: 0 -- in GzReconBatchServiceImplTest
[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0 -- in ReconCalculatorTest
[INFO] Tests run: 13, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

覆盖（AC10 七组）：A/B 各一条 daily + **test exclude（从不查 'test'）** / daily 层不 MAX0 负流水如实记 / 月度 settle=MAX0 + commission floor / **A/B 不交叉冲抵（A 负流水归零不冲减 B）** / 分成比例走 sys_config（500 场景） / 季度 settle commission(A+B) + maintenance(300000×3) / 月维护费 sys_config 缺失兜底。

### 3. ⭐ AC9 对账数据 vs mock 流水「三层比对」（误差 = 0）

> 推进姿态 = mock 全链路自测（Kevin 决策 1）。在真 MySQL（dev 3307）seed 受控 mock 流水（`RECONTEST-` 前缀，测后已清理），用 **与 mapper 完全相同的聚合 SQL** 跑三层。
> 数据集（业务月 2026-05）：A=preorder 3 笔 paid（30000/50000/20000 分，fee 180/300/120）+ 1 笔 4 月成交（10000）5 月退款（验跨月 refunded_time 归属）+ A3 全退 20000；B=gacha 2 笔 paid（8000/5000，fee 48/30）全退（构造负流水）；test 单 1 笔（99900，验 exclude）。

**第一层 — 手动 SQL 直接聚合源表（月度真值）**
```
+---------------+--------------+--------------+
| business_type | gmv_cent_may | fee_cent_may |
+---------------+--------------+--------------+
| gacha         |        13000 |           78 |
| preorder      |       100000 |          600 |
+---------------+--------------+--------------+
+---------------+-----------------+
| business_type | refund_cent_may |   ← A 含 4 月成交 5 月退款的 10000（refunded_time 归属 C4）
+---------------+-----------------+
| gacha         |           13000 |
| preorder      |           30000 |
+---------------+-----------------+
test 单源表存在 99900，但对账 SQL 按 business_type IN (preorder,gacha) 过滤 → 不进对账（exclude 生效）
```

**第二层 — gz_recon_daily 落表 → gz_recon_monthly（settle=MAX0 / commission=floor）**
```
+--------------+---------------+-----------------+--------------------+-----------------+--------------------+
| business_day | business_type | system_gmv_cent | system_refund_cent | system_fee_cent | system_settle_cent |
+--------------+---------------+-----------------+--------------------+-----------------+--------------------+
| 2026-05-05   | gacha         |            8000 |                  0 |              48 |               7952 |
| 2026-05-12   | gacha         |            5000 |                  0 |              30 |               4970 |
| 2026-05-18   | gacha         |               0 |               8000 |               0 |              -8000 |   ← daily 层不 MAX0
| 2026-05-19   | gacha         |               0 |               5000 |               0 |              -5000 |
| 2026-05-03   | preorder      |           30000 |                  0 |             180 |              29820 |
| 2026-05-10   | preorder      |           50000 |                  0 |             300 |              49700 |
| 2026-05-15   | preorder      |               0 |              10000 |               0 |             -10000 |   ← 跨月退款落 5-15
| 2026-05-20   | preorder      |           20000 |                  0 |             120 |              19880 |
| 2026-05-25   | preorder      |               0 |              20000 |               0 |             -20000 |
+--------------+---------------+-----------------+--------------------+-----------------+--------------------+
+----------------+---------------+----------+-------------+------------------+-------------+--------------------+-----------------+
| business_month | business_type | gmv_cent | refund_cent | channel_fee_cent | settle_cent | commission_rate_bp | commission_cent |
+----------------+---------------+----------+-------------+------------------+-------------+--------------------+-----------------+
| 2026-05        | gacha         |    13000 |       13000 |               78 |           0 |                400 |               0 |   ← 负流水 settle=MAX0=0
| 2026-05        | preorder      |   100000 |       30000 |              600 |       69400 |                400 |            2776 |
+----------------+---------------+----------+-------------+------------------+-------------+--------------------+-----------------+
```

**第三层 — query service monthlySummary（SUM gz_recon_monthly）+ 三层对齐 + 取整校验**
```
+---------------+----------+-------------+------------------+-------------+-----------------+
| business_type | gmv_cent | refund_cent | channel_fee_cent | settle_cent | commission_cent |
+---------------+----------+-------------+------------------+-------------+-----------------+
| gacha         |    13000 |       13000 |               78 |           0 |               0 |
| preorder      |   100000 |       30000 |              600 |       69400 |            2776 |
+---------------+----------+-------------+------------------+-------------+-----------------+

三层对齐校验（diff 列全 0 = 通过）：
+---------------+--------+--------+----------+-----------+-----------+-------------+--------+--------+----------+
| business_type | L1_gmv | L2_gmv | diff_gmv | L1_refund | L2_refund | diff_refund | L1_fee | L2_fee | diff_fee |
+---------------+--------+--------+----------+-----------+-----------+-------------+--------+--------+----------+
| preorder      | 100000 | 100000 |        0 |     30000 |     30000 |           0 |    600 |    600 |        0 |
| gacha         |  13000 |  13000 |        0 |     13000 |     13000 |           0 |     78 |     78 |        0 |
+---------------+--------+--------+----------+-----------+-----------+-------------+--------+--------+----------+

commission 取整校验：settle × 400 / 10000 floor（diff_commission 全 0）：
+---------------+-------------+-----------------+----------------+-----------------+
| business_type | settle_cent | commission_cent | expected_floor | diff_commission |
+---------------+-------------+-----------------+----------------+-----------------+
| gacha         |           0 |               0 |              0 |               0 |
| preorder      |       69400 |            2776 |           2776 |               0 |
+---------------+-------------+-----------------+----------------+-----------------+
```

**误差 = 0 全部成立**：① 三层 GMV/退款/通道费逐字段 diff=0；② A 跨月退款 10000 正确归 5 月（refunded_time C4）；③ B 负流水 settle=MAX0=0、分成 0，**A=2776 未被冲减（A/B 不交叉冲抵）**；④ commission=floor(69400×400/10000)=2776；⑤ test 单 exclude。

### 4. 季度结算（AC5）+ 幂等（AC6/R5）

```
+---------+-----------------------+------------------------+--------------------+--------------+
| quarter | commission_total_cent | maintenance_total_cent | payable_total_cent | diff_payable |
+---------+-----------------------+------------------------+--------------------+--------------+
| 2026-Q2 |                  2776 |                 900000 |             902776 |            0 |   ← A 2776 + B 0 ＝ 2776 ; 300000×3 ; 合计 902776
+---------+-----------------------+------------------------+--------------------+--------------+

幂等（重跑 layer2 一次，行数 + 金额不变 = UPSERT 覆盖不累加）：
daily_rows_before=9 monthly_rows_before=2  →  daily_rows_after=9 monthly_rows_after=2  A_commission_after=2776（非 5552）
```

### 5. plus-ui 构建（build:prod 绿，recon 视图打进 bundle）

```
$ pnpm build:prod | grep -E 'recon|built'
dist/assets/reconcile-DusN9k7F.js   0.41 kB │ gzip: 0.21 kB
✓ built in 14.60s
```

---

## SnailJob 跑批任务（待 Kevin 在 SnailJob 控制台手动注册 — 禁 Flyway INSERT sys_job）

| 任务 | @JobExecutor name | 建议 CRON | 含义 | 阻塞策略 |
|---|---|---|---|---|
| 每日对账 | `gzReconDailyJob` | `0 0 2 * * ?` | 每日 02:00 跑前一日 | DISCARD |
| 月度对账 | `gzReconMonthlyJob` | `0 0 3 1 * ?` | 每月 1 日 03:00 跑前月 | DISCARD |
| 季度结算 | `gzReconSettleJob` | `0 0 4 15 3,6,9,12 ?` | 季度末月 15 日 04:00 | DISCARD |

> 三执行器 = `@Component + @JobExecutor` 薄壳，核心全在可单测 `IGzReconBatchService`。模块 pom 已含 `ruoyi-common-job`。**已确认无 Flyway INSERT sys_job**（迁移仅建表 + sys_menu/dict/config）。

---

## 已知 issue / 风险提示

- **R2 外部前置（不阻塞 close）**：`channel_*` / `diff_*` 列 mock 模式留 NULL（无真实账单）。真实通道费 `fee_cent` 真值、微信商户后台流水比对、`gz_recon_exception` 写入逻辑，待甲方开通真实商户号后与对账单跑一遍（验收前）。`gz_recon_exception` 本卡仅建表 + 留 hook，跑批不主动写。
- **Excel 导出明细颗粒度**：`buildExportRows` 以「每笔 paid 交易（按 paid_time 落区间）一行 + LEFT JOIN 已完成退款」为粒度，末尾追加四项汇总行。退款列附在原交易行（per-transaction 颗粒度，供甲方逐笔对照银行流水，合同 §4.2.1），与按 refunded_time 归属的月度 refund 聚合口径是两个视角（明细=逐笔、对账=按月归属），均正确。
- **本卡为纯 admin/后端 ticket**：Tech 段无 `miniapp/` + AC 无微信原生能力 → 跳过 Tier 2 入口可达 + 无人验（CLAUDE.md §8.2），AI Tier 1A + 1B 全 ✅ 即终态。

## 对下游 ticket（GZ-ADMIN-106 看板）的提示

- 看板「本月累计 GMV / 退款 / 实际到账（按 A/B）」**直接复用** `IGzReconQueryService.monthlySummary(businessType, month, month)`（已落表聚合，不重查源）。
- 「待发货订单数」= `gz_ord_order/gz_gacha_order WHERE business_status='paid' AND logistics_status='in_japan'`（对账 service 不覆盖，看板自查）。
- 业务线统一 `business_type`（preorder/gacha），**禁** business_line/biz_line/A·B 列 —— 看板 tab 同样仅 UI 标签。

---

## doc/11 §9.1 + §4.6 原文引证（AC12 — 证明实现一致）

> **doc/11 §9.1**（line 1196）：`system_settle_cent` = `system_gmv_cent - system_refund_cent - system_fee_cent`｜合同 §1.5｜**实际到账流水（合同核心口径）**
> **doc/11 §9.1**（line 1194，C4）：`system_refund_cent` = SUM(gz_pay_refund.refund_amount_cent WHERE 关联 transaction.business_type=? AND DATE(refunded_time)=?)｜**退款按 refunded_time 当日归属（不追溯成交日）**
> **doc/11 §9.2 / F9.3**（line 1264）：业务线负流水 `settle_cent = MAX(0, gmv - refund - fee)`
> **doc/11 §4.6 / 合同 §4.1.2**（line 609）：（A、B 分别核算，**不交叉冲抵**；任一为负 → 该业务线该月分成为 0，不倒贴）
> **doc/11 F-D19**（line 1954）：该月该线 `commission_cent = MAX(0, settle_cent × rate)`（§9.2）

实现：`ReconCalculator.settleCent = Math.max(0, gmv−refund−fee)` + `commissionCent = settle×rateBp/10000`（floor）；`GzReconBatchServiceImpl` 对 `[preorder, gacha]` 各自独立算一条 monthly，`runQuarterly` 用 `SUM(commission_cent WHERE quarter)`（A+B 相加）；`GzReconSourceMapper.sumRefundCent` 按 `DATE(refunded_time)` 归属。三层比对误差=0 证明一致。
