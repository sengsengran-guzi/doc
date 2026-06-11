# GZ-ADMIN-104 — 完工报告（跨境物流 2 态推进 / mp 店员端主形态 + plus-ui owner 兜底）

## §0 自检结果

| 检查项 | 结果 | 备注 |
|---|---|---|
| 上游依赖 | ✅ | gz_ord_order/gz_gacha_order 物流字段（logistics_status/cn_carrier_code/cn_tracking_no/cn_dispatched_at/delivered_time/business_status）+ gz_logistics_audit + gz_express_carrier 字典 9 项 真库确认存在 |
| 编译通过 | ✅ | mvn install gz-common + gz-ord BUILD SUCCESS |
| 权威蓝图 | doc/10 §9（C1 2 态 + 终态 + N2/N8/N9/E2/E5/E6）+ doc/11 §6.3/§7.4/§8.3 + 附录 A.7 | 逐字落地 |
| ADR | ADR-0004（mp 店员 RBAC 底座）/ ADR-0005（物流 2 态对齐合同 §2.3） | 已读，复用底座 |
| 合同范围 | V1.1 | 合同 §2.3 #14/#15（不自动抓取，仅展示甲方录入单号） |

### §0 真库确认（不假设上游）

```
gz_ord_order   cols: business_status,logistics_status,delivered_time,cn_carrier_code,cn_tracking_no,cn_dispatched_at,order_no ✓
gz_gacha_order cols: 同上 ✓
gz_logistics_audit 存在 ✓（action_type/from_*/to_*/reason/operator_type/operator_id/operated_time）
gz_express_carrier 字典 9 项 ✓（yto/sf/zto/yunda/jd/ems/debang/jitu/other）
```

## 实现摘要

### 新增/改动文件

```
后端（gz-ord；跨业务按 business_type 分流 UPDATE，gz_gacha_order 用裸 SQL 不依赖 gz-gacha 模块）：
  enums/ExpressCarrierEnum.java（改）                    +isValid() 9 项校验
  domain/dto/{LogisticsForwardDto,LogisticsCarrierUpdateDto,LogisticsRollbackDto}.java
  domain/vo/LogisticsOrderStateVo.java                  mapper 状态出参
  mapper/GzLogisticsMapper.java                         ${table} 状态推进 + 裸 INSERT gz_logistics_audit
  service/IGzLogisticsService.java + impl                状态机 + 9 项校验 + 必录校验 + 审计集中
  controller/GzLogisticsController.java                 /system/gz/ord/logistics（owner，含 rollback）
  controller/applet/GzLogisticsMpController.java        /app/gz/staff/logistics（mp 店员，无 rollback）
  service/GzLogisticsServiceImplTest.java               11 单测
  db/migration/V202606241100__GZ-ADMIN-104-logistics-menu.sql
plus-ui（owner 兜底）：
  api/gz-ord/logistics.ts                              forward/carrier/rollback
  views/gz-ord/orders/components/OrderDetailDrawer.vue（改）  占位按钮→真操作区 + 发货/改单号/回退弹窗
  lang/{zh_CN,en_US}.ts（+gzOrdOrders.logi* 段）
mp 店员端（主形态）：
  api/gz-ord/logistics.ts                              forwardStaffLogistics/updateStaffCarrier + EXPRESS_CARRIERS
  pages/me/staff-orders/detail.vue（改）                 物流推进操作区（快递 9 选 1 chips + 单号 input，Biz* + var(--c-*)）
  locale/staff.zh-CN.ts（+push* 段）
```

### 关键设计

- **状态机**：in_japan→in_china_dispatching（必录快递+单号，9 项字典校验，service assert + mp/owner 表单 disabled，doc/10 §9.E5）→ delivered；目标态由当前态决定（forward 推进一步），不可跳态/不可逆（回退走独立 owner 接口）。
- **条件 UPDATE 保状态机安全**：`WHERE order_no AND logistics_status='<源态>'`，源态不符 → 影响 0 行 → service 报错（防并发越级）。
- **跨业务复用**：`tableOf(businessType)` 白名单映射 preorder→gz_ord_order / gacha→gz_gacha_order；gz_gacha_order 用裸 SQL（不依赖 gz-gacha 模块，无循环依赖）。
- **审计**（doc/11 §8.3）：每次写 gz_logistics_audit；action_type = status_forward（含 to_status + to_carrier + to_tracking）/ carrier_update（记 from/to 单号）/ status_rollback（记 from/to/reason）；operator_type='admin'，operator_id=LoginHelper.getUsername()。
- **下沉**（Kevin 决策 2 / ADR-0004）：mp 店员端 push（主形态，店员手机现场发货）；plus-ui owner 兜底 + 独占 rollback（reason 必填，高危隔离）。
- **退款解耦**（doc/10 §9.E3）：business_status=refunded → service 拦截推进（E6）；logistics_status 与 business_status 并行独立。

## AI 自测

### 1. 单测 11/11（AC11 ≥6 raw assertion）

```
$ mvn -o test -pl ruoyi-modules/ruoyi-gz-ord -Dtest='GzLogisticsServiceImplTest'
[INFO] Tests run: 11, Failures: 0, Errors: 0, Skipped: 0 -- in GzLogisticsServiceImplTest
[INFO] BUILD SUCCESS
```
覆盖：in_japan→dispatching happy（字段+审计）/ 漏录单号→报错 / 非法快递编码→报错 / E6 refunded 拦截 / dispatching→delivered happy / delivered 终态再推→报错 / 改单号 carrier_update 记 from/to / 改单号非派送态→报错 / owner 回退 happy（记 reason）/ 回退 in_japan→报错 / gacha 路由到 gz_gacha_order 表。
> owner-only 回退权限 = controller `@SaCheckPermission("gz:ord:logistics:rollback")`（Playwright/集成覆盖）；reason 非空 = DTO `@NotBlank`（controller `@Validated`）。

### 2. DDL 应用（真库，幂等 menu）

```
SELECT menu_id, menu_name, perms FROM sys_menu WHERE menu_id IN (11003,11034);
11003  物流推进  gz:ord:logistics:push       （owner 100 + staff 101）
11034  物流回退  gz:ord:logistics:rollback   （仅 owner 100）
```

### 3. plus-ui build:prod 绿 + mp type-check 0 错误 + mp vitest 374 全过

```
$ pnpm build:prod                     → ✓ built（OrderDetailDrawer 物流操作区打包）
$ pnpm type-check (miniapp)           → 0 error TS（staff-orders/detail.vue + api/gz-ord/logistics.ts）
$ pnpm test (miniapp vitest)          → Test Files 40 passed / Tests 374 passed
```

## SnailJob / 注意

- **无 SnailJob 任务**（物流推进是人工触发，非定时）。**无新建表**（物流字段前序日已内联）。**无 sys_job INSERT**。
- 订阅消息 hook（doc/10 §9.N7 / R6）：本卡未接 ApplicationEventPublisher（USER-103 订阅 hook 未就绪），留待 hook 就绪后接，不阻塞推进事务。

## Tier 2 可达（AC12）+ 人验项

- **mp 店员端入口 = 现成真入口**：店员账号登 mp → 个人中心「门店管理」→「订单查看」(GZ-ADMIN-201 已建) → 订单详情 → 物流推进操作区（≤4 次点击，无需临时入口）。
- **进 progress.md「人验」列**（mp 部分）：店员真机 happy path — 选订单 → 发往中国（9 选 1 快递 + 单号，漏录提交 disabled）→ 改单号一次 → 推到已签收；owner 在 plus-ui 回退（reason 必填）；停用 sys_user 后即踢、再调 401/403。
- 详见 testing-human.md。
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
# GZ-ADMIN-106 — 完工报告（数据看板 V1.1 交易盘面）

## §0 自检结果

| 检查项 | 结果 | 备注 |
|---|---|---|
| 上游依赖 | ✅ | GZ-ADMIN-105（gz_recon_monthly + IGzReconQueryService）/ GZ-ADMIN-103（gz_ord_order/gz_gacha_order）/ gz_gacha_draw / gz_pay_transaction 真库确认存在 |
| 编译通过 | ✅ | mvn install gz-common BUILD SUCCESS |
| 权威蓝图 | doc/10 §8/§9/§10 + doc/11 §4.6/§9/§6.3/§7.3 | 复用 105 口径不重写 |
| ADR | 无相关 | — |
| 合同范围 | V1.1 | — |

## 实现摘要

### 新增文件

```
后端（gz.recon 域，与 105 同域便于复用 service）：
  recon/domain/vo/GzDashboardV11SummaryVO.java          单接口聚合返回（A/B 分流 + Top10）
  recon/mapper/GzReconDashboardMapper.java              今日订单/GMV + 扭蛋开盒/出货价值 + 待发货 + 热销 Top10
  recon/service/IGzReconDashboardService.java + impl      复用 IGzReconQueryService.monthlySummary
  recon/controller/admin/GzReconDashboardController.java  GET /v11-summary（单接口）
  recon/service/GzReconDashboardServiceImplTest.java     3 单测
  db/migration/V202606241050__GZ-ADMIN-106-dashboard-v11-perm.sql
Admin 前端：
  plus-ui/src/api/gz-recon/dashboard.ts                 getV11Summary()
  plus-ui/src/views/dashboard/components/V11SummaryRow.vue   V1.1 区块独立组件
  plus-ui/src/views/dashboard/index.vue                 追加 <V11SummaryRow v-if="showV11">（perm 门控）
  plus-ui/src/lang/{zh_CN,en_US}.ts（+dashboard.v11 段，盲盒语义）
```

### 关键设计

- **单聚合接口**（AC3）：`GET /system/gz/recon/dashboard/v11-summary` 一次返所有卡片，前端 1 次调用本地分发，不串行。
- **复用 105 口径**（AC4 / D2）：本月 GMV/退款/实际到账走 `IGzReconQueryService.monthlySummary(businessType, month, month)`，不在看板侧重算 4% 分成 —— 避免双口径漂移（CLAUDE.md §9.5 §1）。
- **盲盒语义**（强约束 #5）：扭蛋卡 i18n key = `gachaOpenCount` / `gachaAvgValue`（开盒数 / 平均出货价值），无「抽奖/中奖」；出货价值 = `SUM(prize_snapshot_json.referenceValueCent) / 开盒数`（整除取整）。
- **待发货口径**（强约束 #3）：`gz_ord_order WHERE business_status='paid' AND logistics_status='in_japan'`，用 C1 2 态字段，禁 logistics_node/7 节点。
- **业务线分流统一 business_type**（preorder/gacha，test exclude）。

### ⚠️ 与 ticket「无 DDL」的 1 处偏差（已记 DDL 注释）

ticket 原设「复用 V1.0 看板 menu、无 DDL」。但 V1.1 交易盘面含 GMV/退款/实际到账（财务敏感），需 owner-only perm `gz:recon:dashboard:v11`；该 perm 在仓库无任何 menu/role 行 → `@SaCheckPermission` 会对所有人 403。故加 1 个 **F 型按钮权限**（menu_id 302，挂现有「数据看板」menu 300 下，授 owner role_id=100），**不新增 C 型独立页菜单**（仍是同一首页区块扩展，符合「不新增独立页」本意）。无权限角色看 V1.0 老卡片，V1.1 区块 v-if 隐藏。

## AI 自测

### 1. 单测 3/3

```
$ mvn -o test -pl ruoyi-modules/ruoyi-gz-common -Dtest='GzReconDashboardServiceImplTest'
[INFO] Tests run: 3, Failures: 0, Errors: 0, Skipped: 0 -- in GzReconDashboardServiceImplTest
[INFO] BUILD SUCCESS
```
覆盖：单接口返所有卡片非空（复用 105 实际到账）/ 待发货口径 / 业务线 A·B 分流 + 扭蛋平均出货价值（40000/4=10000 整除）。

### 2. DDL 应用（真库，幂等 menu）

```
SELECT menu_id, menu_name, perms FROM sys_menu WHERE menu_id=302;
302  V1.1交易盘面  gz:recon:dashboard:v11   （owner role_id=100 已授权）
```

### 3. plus-ui build:prod 绿

```
$ pnpm build:prod
dist/assets/V11SummaryRow-*.js   4.79 kB
dist/assets/dashboard-*.js       2.80 kB
✓ built in 16.16s（无 error）
```

## 已知 issue / 下游提示

- **纯 admin/后端 ticket**：AI Tier 1A+1B 全 ✅ 即终态，无人验。无新建表、无 SnailJob。
- 待发货卡片点击 → `router.push('/gz-ord/orders')`（GZ-ADMIN-104 物流推进在订单详情操作）。
- 不做轮询/缓存（V1.1 数据量小直查，强约束 #6）。
# GZ-ADMIN-108 — 完工报告（软删恢复回收站）

## §0 自检结果

| 检查项 | 结果 | 备注 |
|---|---|---|
| 仓库 git | N/A | 本项目非 git 仓 |
| 上游依赖 | ✅ | GZ-ADMIN-101（gz_ord_*）/ GZ-NEWS-003（gz_news_article）软删字段已建（grep migration 命中） |
| 真实落表名 grep | ✅ | 见下 raw output，注册 6 张主数据表（不假设 gz_store/gz_product_sku 命名） |
| 编译通过 | ✅ | mvn install gz-common BUILD SUCCESS |
| 权威蓝图 | doc/11 §0.3（del_flag 仅 2 值）+ §10.3（menu 11006） | 逐字落地 |
| ADR | 无相关 | — |
| 合同范围 | V1.1 | — |

### §0 自检 — 真实落表名 + del_flag 列（AC1 强制）

```
$ grep -rhoiE 'CREATE TABLE[^(]*gz_[a-z_]+' .../db/migration/ | sort -u
（命中 30+ 张 gz_* 表；回收站只纳入「owner 可能误删的业务主数据」6 张，非流水/审计/快照表）

$ 真库确认 6 张纳入表的名称列：
gz_news_article  → title         （资讯文章）
gz_ord_product   → name          （预购商品）
gz_ord_sku       → spec_name     （预购 SKU）
gz_gacha_prize   → name          （扭蛋奖品）
gz_gacha_machine → name          （扭蛋机）
gz_bean_store    → name          （拼豆门店）
全部含 del_flag CHAR(1) + update_by + update_time（ruoyi 标准审计列）
```

## 实现摘要

### 新增文件

```
后端（gz-common，base 模块——无法 import gz-ord/gz-news Service，故用注册表 + 泛型表名 SQL）：
  recycle/service/internal/RecycleEntityRegistry.java   6 实体白名单（entityType→table/nameColumn/label）
  recycle/domain/vo/RecycleBinItemVO.java               统一行 VO
  recycle/domain/vo/RecycleRawRow.java                  mapper 裸出参
  recycle/domain/bo/RecycleActionBo.java                恢复/归档入参
  recycle/mapper/GzRecycleBinMapper.java                泛型 selectDeleted/restore/archive/cleanupExpired
  recycle/service/IGzRecycleBinService.java + impl       内存聚合分页 + 删除人昵称批量解析 + 物理清理
  recycle/job/GzRecycleCleanupJob.java                  SnailJob 薄壳
  recycle/controller/admin/GzRecycleBinAdminController.java   list/entity-types/restore/archive
  recycle/service/GzRecycleBinServiceImplTest.java      5 单测
  db/migration/V202606241000__GZ-ADMIN-108-recycle-bin-menu-and-archived-flag.sql
Admin 前端：
  plus-ui/src/api/gz-common/recycle-bin.ts
  plus-ui/src/views/gz-common/recycle-bin/index.vue
  plus-ui/src/lang/{zh_CN,en_US}.ts（+recycleBin 段）
```

### 关键设计

- **跨模块约束**：gz-common 是 base（gz-ord/gz-news/gz-gacha 反向依赖它），无法 import 各业务 Service → restore/archive/cleanup 走注册表 + 泛型表名 SQL（`${tableName}` 取值仅来自白名单，非用户输入，无注入）。
- **@InterceptorIgnore 实际不需要**：MyBatis-Plus 的 `@TableLogic` 仅对 BaseMapper 自动方法追加 `del_flag='0'`，自定义 SQL 原样执行——故显式写 `del_flag='2'` 即可查到已删记录；租户隔离由 TenantLineInnerInterceptor 自动保留（admin 登录态），cleanup 在 cron 走 TenantHelper.ignore + SQL 显式 tenant_id。
- **del_flag 严格 2 值**（doc/11 §0.3）：归档用独立列 `archived_flag TINYINT 0/1`，与 del_flag 正交；恢复 = del_flag 2→0；归档 = archived_flag=1（del_flag 保持 2）。

## AI 自测

### 1. 编译 + 单测 5/5

```
$ mvn -o test -pl ruoyi-modules/ruoyi-gz-common -Dtest='GzRecycleBinServiceImplTest'
[INFO] Tests run: 5, Failures: 0, Errors: 0, Skipped: 0 -- in GzRecycleBinServiceImplTest
[INFO] BUILD SUCCESS
```
覆盖：restore happy（del_flag 2→0 返名称）/ restore 影响 0 行抛业务异常（不静默成功，D6）/ 非法 entityType 白名单拦截 / archive happy / cleanupExpired 遍历 6 表求和。

### 2. DDL ALTER 语法验证（真库 apply → revert，留给 Flyway 重建）

```
ALTER TABLE gz_news_article ADD COLUMN archived_flag TINYINT NOT NULL DEFAULT 0 ... → ALTER ok
ALTER TABLE gz_news_article DROP COLUMN archived_flag                              → DROP revert ok
（未持久化，Flyway 启动时对 6 张表 fresh 应用 archived_flag）
```

### 3. plus-ui build:prod 绿

```
$ pnpm build:prod → ✓ built in；recycle-bin 视图打进 bundle，无 error
```

## SnailJob 任务（待 Kevin 控制台注册）

| 任务 | @JobExecutor name | CRON | 含义 |
|---|---|---|---|
| 回收站物理清理 | `gzRecycleCleanupJob` | `0 0 3 * * ?` | 每日 03:00 删 archived_flag=1 且超 30 天的 del_flag='2' 记录（分批 ≤1000） |

> 薄壳转调可单测 `cleanupExpired()`；**无 Flyway INSERT sys_job**（DDL 仅 ALTER + sys_menu/role_menu）。

## 已知 issue / 下游提示

- **纯 admin/后端 ticket**：AI Tier 1A+1B 全 ✅ 即终态，无人验。
- 物理清理 30 天阈值硬编码在 service 常量 `RETENTION_DAYS`（V1.1 够用；如需可配再走 sys_config）。
- doc/11 §0.3 原文：`del_flag CHAR(1) NOT NULL DEFAULT '0'`，**仅 2 值** `'0'`正常/`'2'`删除；归档用独立 `archived_flag`，**绝不复用 del_flag 第三值** —— 实现一致（单测断言 restore 后 del_flag∈{'0','2'}，归档走 archived_flag）。
