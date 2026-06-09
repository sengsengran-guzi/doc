# GZ-ADMIN-105 ⭐ — 对账中心（合同 §4.1 4% 分成兑现核心 / 跑批表 + 季度结算）

**优先级**: P1
**复杂度**: L（V1.1 最高优先级 ticket — 合同 §4.1 4% 分成兑现唯一权威数据来源；零容忍金额误差；L 级思考密度，禁止快速过 §0 自检；reports 必须含「对账数据 vs mock/沙箱流水」三层比对 raw output，误差 = 0）
**关联 PRD**: doc/02-prd.md M7.8 对账中心 + 合同 §4.1（分成口径）+ §4.2（结算节奏）+ §4.6（月度维护费）
**关联拆解**: doc/02-需求拆解.md §3.5
**关联 mockup**: ⚠️ 缺口（AD-ADMIN-FINANCE 待补；admin 走 ruoyi/Element Plus 默认审美（**不套用 C 系统**），用 plus-ui BizTable + el-statistic + el-tabs + el-date-picker + ruoyi 自带 EasyExcel；不引 mockup 像素，不评判视觉）
**关联 ADR**: —（如真实通道费颗粒度 / 跨业务线退款归属遇到分歧 → 新建 ADR-V1.1-FN-01；本卡 mock 全链路自测口径已由 doc/11 §9 + 合同 §4.1 锁定，无需新 ADR）
**依赖**: **GZ-ADMIN-103**（订单聚合管理，提供按 `business_type` 回查 `gz_pay_transaction` 的能力）+ **GZ-PAY-104**（拉 `/v3/bill/fundflowbill` 回写 `gz_pay_transaction.fee_cent` 真实笔费 —— 对账通道费的唯一来源；mock 模式下由 D08/D09 mock 链路产生 `fee_cent`）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡 + ★ 反复读）

> 对账中心是合同 §4.1 4% 分成兑现的唯一权威数据来源。**口径逐字落地 doc/11 §9 + §4.6，不自行发挥。** 任一字段歧义 → 先回补 doc/11 §9 再写代码（9.5 复盘优先级 §1），不在 ticket 内 patch。

- **字段表**：[doc/11-字段权威表.md](../../../11-字段权威表.md)
  - **§9 对账中心域（唯一权威 — 全文必读）**：4 表字段口径
    - §9.1 `gz_recon_daily`（每日跑批，UNIQUE `(tenant_id, business_day, business_type)`，每业务线一条）
    - §9.2 `gz_recon_monthly`（月度对账单，含 `commission_rate_bp` 默认 400 + `commission_cent`）
    - §9.3 `gz_recon_exception`（系统侧 vs 通道侧 diff 异常，V1.1 建表 + 留 hook）
    - §9.4 `gz_recon_settle`（季度结算记录，含 `maintenance_total_cent` + `payable_total_cent`）
    - §9.5 待澄清（F9.2 fee_cent 来源 / F9.3 负流水 MAX(0,..) / F9.4 commission_rate_bp 走 sys_config / F9.5 Excel 5 列颗粒度）
  - **§4.6 4% 分成核心计算口径**（跨表计算源 — 全文必读）：实际到账流水公式 + A/B 分别核算不交叉冲抵 + 退款按 `refunded_time` 当日归属（C4 裁定）
  - §4.2 `gz_pay_transaction`（`amount_cent` / `fee_cent` / `paid_time` / `business_type` / `status`，对账 GMV·通道费源）
  - §4.x `gz_pay_refund`（`refund_amount_cent` / `refunded_time`，对账退款源；V1.1 仅全额退款）
  - §10.3 menu_id 段（对账中心 **11004** / 季度结算 **11005**，无 FINANCE 段）+ §10.4 sys_config（`gz.commission.rate.preorder` / `gz.commission.rate.gacha` / `gz.commission.maintenance.monthly.cent`）+ §10.2 字典 `gz_recon_status` / `gz_business_type`
- **业务流**：[doc/10-业务流权威图.md](../../../10-业务流权威图.md)
  - **§10 对账中心流（业务流权威 — 全文必读）**：N1 凌晨 02:00 跑批 / N2 月度对账单 / N3 双方确认 / N4 季度合并支付（含月维护费）/ N5 Excel 导出 / N6 异常处理 / Q10.2（fee 按订单粒度 GROUP BY business_type）/ Q10.4（A/B 负流水该月该线分成 = 0，不交叉冲抵）/ E4（business_type 强分流）/ E5（退款发生当月核算，不追溯已结算月）
- **合同**：[doc/03-contract.md](../../../03-contract.md) §1.5（实际到账流水定义）+ §4.1（4% 分成口径 + A/B 独立核算）+ §4.2.1（Excel 导出明细颗粒度）+ §4.2.3（季度合并支付）+ §4.6（月度维护费 ¥3000）
- **UI 参考**（admin 走 ruoyi/Element Plus 默认审美，不套用 C 系统）：admin ticket — **N/A**（plus-ui BizTable + el-statistic 四栏数字卡片 + el-tabs 业务线 A/B 切换 + el-date-picker-range 周期筛选 + ruoyi EasyExcel）

## What

admin 端「对账中心」：SnailJob 每日 02:00 跑批前一日，按 `business_type`（A=preorder / B=gacha，`test` exclude）从 `gz_pay_transaction`（`amount_cent` / `fee_cent`，status=paid）+ `gz_pay_refund`（`refund_amount_cent`，按 `refunded_time` 当日）落 `gz_recon_daily`，逐月汇总 `gz_recon_monthly`（含 `commission_cent` = `settle_cent × 400 / 10000` 向下取整，A/B 不交叉冲抵、负流水该月该线 = 0），每季度末月 15 日前汇总 `gz_recon_settle`（季度分成合计 + 月维护费 ¥3000×3 = `payable_total_cent`）；admin 页按业务线 tab 看 GMV / 退款 / 通道费 / 实际到账 + Excel 每笔颗粒度导出对照微信商户后台流水比对。

## AC（验收标准）

- [ ] **AC 1**：DDL 建对账域 4 表（doc/11 §9 逐字落地，时间戳 > `V202606051200`）：
  - `V202606191000__GZ-ADMIN-105-create-gz_recon-tables.sql`：建 `gz_recon_daily`（§9.1）/ `gz_recon_monthly`（§9.2）/ `gz_recon_exception`（§9.3）/ `gz_recon_settle`（§9.4）
  - 每表 `tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'` + `del_flag` 2 值（0/2）+ ruoyi 标准审计列；金额全 `_cent` BIGINT（**不用 `_fen`**）
  - UNIQUE 必含 tenant_id：`gz_recon_daily(tenant_id, business_day, business_type)` / `gz_recon_monthly(tenant_id, business_month, business_type)` / `gz_recon_settle(tenant_id, quarter)`
  - **不建 MySQL VIEW**（删旧卡 `v_gz_finance_daily`）—— 对账是跑批落表（非实时视图），SnailJob 写入 `gz_recon_daily/monthly/settle`
- [ ] **AC 2**：DDL 菜单 + 字典 + sys_config（`V202606191001__GZ-ADMIN-105-menu-config.sql`）：
  - 菜单（doc/11 §10.3，**无 FINANCE 段**）：对账中心 **menu_id 11004** / 季度结算 **menu_id 11005**（挂「谷子管理」或「财务」目录下；目录如不存在同 DDL 建，目录 menu_id 也落 11000-11099 段）
  - 字典（如前序日未 seed）：`gz_recon_status`（`generating`/`generated`/`confirmed`/`settled`/`exception`，doc/11 §10.2）
  - sys_config（doc/11 §10.4 / F9.4）：`gz.commission.rate.preorder` = `400` / `gz.commission.rate.gacha` = `400`（千分之，400 = 4%）/ `gz.commission.maintenance.monthly.cent` = `300000`（¥3000）
- [ ] **AC 3**：`gz_recon_daily` 每日跑批口径（doc/11 §9.1 逐字，按 `business_type` 各一条）：
  - `system_gmv_cent` = `SUM(gz_pay_transaction.amount_cent WHERE business_type=? AND status='paid' AND DATE(paid_time)=business_day)`
  - `system_refund_cent` = `SUM(gz_pay_refund.refund_amount_cent WHERE 关联 transaction.business_type=? AND DATE(refunded_time)=business_day)`（退款按 `refunded_time` 当日归属，**不追溯成交日**，C4 裁定）
  - `system_fee_cent` = `SUM(gz_pay_transaction.fee_cent WHERE business_type=? AND status='paid' AND DATE(paid_time)=business_day)`（`fee_cent` 来自 GZ-PAY-104 拉 fundflowbill 回写）
  - `system_settle_cent` = `system_gmv_cent − system_refund_cent − system_fee_cent`（实际到账流水，合同 §1.5）
  - **`business_type='test'` 单 exclude**（doc/11 F4.2 不进对账）；`channel_*` / `diff_*` 列 mock 模式留 NULL（无真实账单），不阻塞
- [ ] **AC 4**：`gz_recon_monthly` 月度跑批 + 分成口径（doc/11 §9.2 逐字，A/B 不交叉冲抵）：
  - `gmv_cent` / `refund_cent` / `channel_fee_cent` = `SUM(gz_recon_daily.对应字段 WHERE business_month AND business_type)`
  - `settle_cent` = `MAX(0, gmv_cent − refund_cent − channel_fee_cent)`（**任一业务线该月负流水 → 该业务线该月 settle_cent = 0，不倒贴 / 不冲减另一业务线分成基数**，doc/10 Q10.4）
  - `commission_rate_bp` = 取 sys_config（preorder/gacha 各自 400）；`commission_cent` = `settle_cent × commission_rate_bp / 10000`（**向下取整到分**）
  - A（preorder）/ B（gacha）**分别一条**，各自独立算 `commission_cent`，**不交叉冲抵**（合同 §4.1.2）
- [ ] **AC 5**：`gz_recon_settle` 季度结算口径（doc/11 §9.4，锚 3/6/9/12 月 15 日前）：
  - `quarter` = `yyyy-Q1`/`Q2`/`Q3`/`Q4`；`commission_total_cent` = `SUM(gz_recon_monthly.commission_cent WHERE quarter)`（**A + B 业务线相加**）
  - `maintenance_total_cent` = `gz.commission.maintenance.monthly.cent × 3`（= `300000 × 3` = `900000`，¥3000 月维护 × 3，合同 §4.6）
  - `payable_total_cent` = `commission_total_cent + maintenance_total_cent`（季度应付合计，**分成 + 月维护费合并一项**）
- [ ] **AC 6**：SnailJob 跑批（**非 sys_job**，doc/11 §9 / CLAUDE.md SnailJob 约束）：
  - `ruoyi-gz-common`（recon 域）pom **显式加 `ruoyi-common-job` 依赖**
  - 跑批逻辑写**可单测 service**（`GzReconBatchService.runDaily(LocalDate)` / `runMonthly(YearMonth)` / `runQuarterly(String quarter)`，纯方法，不依赖 SnailJob 上下文），外层 `@Component + @JobExecutor` 薄壳（`GzReconDailyJobExecutor` / `GzReconMonthlyJobExecutor` / `GzReconSettleJobExecutor`）只转调 service
  - **任务名 + CRON 写进 reports + testing-human 由 Kevin 在 SnailJob 控制台手动注册**：daily `gz_recon_daily_job` CRON `0 0 2 * * ?`（02:00 跑前一日）/ monthly `gz_recon_monthly_job` CRON `0 0 3 1 * ?`（每月 1 日 03:00 跑前月）/ settle `gz_recon_settle_job` CRON `0 0 4 15 3,6,9,12 ?`（季度末月 15 日跑）
  - **禁止** Quartz / **禁止** Flyway INSERT sys_job（启动 hard-fail）
  - 跑批幂等：同 `(business_day, business_type)` 重跑 = UPSERT（不重复累加）
- [ ] **AC 7**：admin 端 `views/gz-recon/reconcile/index.vue` 对账中心页（plus-ui BizTable + Element Plus 默认）：
  - 顶部 **el-tabs**：业务线 A（预定）/ 业务线 B（扭蛋）；底层 WHERE `business_type IN ('preorder')` / `('gacha')`（**tab 仅 UI 标签 A/B，底层一律按 `business_type` 过滤；禁止在 SQL/表里出现 business_line/biz_line/A/B 列**）
  - 顶部 **筛选区**：el-date-picker-range（按月查 `gz_recon_monthly` / 按日查 `gz_recon_daily`）
  - 中部 **四栏 el-statistic 卡片**：GMV（`gmv_cent`）/ 退款（`refund_cent`）/ 通道费（`channel_fee_cent`）/ **实际到账（`settle_cent`，高亮加粗）** + **应付分成卡片（`commission_cent`，显示 `4%`）**
  - 下部 **BizTable 明细**（分页）：列 = 业务月 / 业务线 / GMV / 退款 / 通道费 / 实际到账 / 分成 / 状态（`gz_recon_status` 字典翻译）
  - 季度结算 tab/页（menu 11005）：列出 `gz_recon_settle`（季度 / 分成合计 / 月维护费 / 应付合计 / 状态）
- [ ] **AC 8**：Excel 导出（合同 §4.2.1 强制 / doc/10 §10.N5 / doc/11 F9.5）：
  - 用 ruoyi 自带 EasyExcel + `@ExcelProperty`（**不引新依赖**）
  - **明细颗粒度 = 每笔交易一行**（源 `gz_pay_transaction` join `gz_pay_refund`），列：统一订单号（`business_order_no`，格式 `域大写-yyyyMMdd-6位序号`）/ 金额（元）/ 时间（`paid_time` / `refunded_time`）/ 状态（`paid` / `refunded`）/ 通道费（`fee_cent` 元）
  - 末尾**四项汇总行**：GMV / 退款 / 通道费 / 实际到账（加粗灰底）
  - **不做透视表 / 不合并单元格 / 不做月度小计行**（让甲方一键复制到银行流水 Excel 比对，合同 §4.2.1）
  - 业务线 A、B 各自一份导出（不合并到一个 sheet）；文件名含业务线 + 周期（如 `对账明细_业务线A_2026-06.xlsx`）
  - 导出 Controller 方法 `@Log(businessType=EXPORT, title="对账中心导出")` 写 sys_oper_log
- [ ] **AC 9** ⭐：reports 必须含「对账数据 vs mock/沙箱流水」**三层比对 raw output（金额误差 = 0）**：
  - 第一层：手动 SQL `SELECT business_type, SUM(amount_cent), SUM(fee_cent) FROM gz_pay_transaction WHERE status='paid' AND DATE(paid_time) BETWEEN ... GROUP BY business_type` + `SELECT SUM(refund_amount_cent) FROM gz_pay_refund WHERE DATE(refunded_time) BETWEEN ...`
  - 第二层：跑批后 `gz_recon_daily` SUM → `gz_recon_monthly` 的 `gmv_cent` / `refund_cent` / `channel_fee_cent` / `settle_cent` / `commission_cent`
  - 第三层：对账中心 API JSON 响应（四栏聚合 + 分成）
  - **三层数值对齐表 + `commission_cent = settle_cent × 400 / 10000`（向下取整）逐月校验**；`business_type='test'` 已 exclude
  - **误差 = 0**；若有误差 → 立刻 STOP 报 Kevin，**不能 close ticket**
  - **推进姿态 = mock 全链路自测**（Kevin 决策 1）：dev/staging `gz.pay.client.mode=mock`，对账跑批 + 比对在 D08/D09 mock 产生的交易/退款数据上闭环；**真实商户号 / 0.01 元端到端 / 真实 fundflowbill 笔费 / 微信商户后台流水比对列为【外部前置风险】**（见备注 R2），不当默认就绪
- [ ] **AC 10**：单测覆盖（核心计算 service，全 raw assertion）：
  - happy path：业务线 A 当月聚合（mock 多笔 paid + 全额 refund → 验 `gmv_cent` / `refund_cent` / `channel_fee_cent` / `settle_cent` / `commission_cent`）
  - **A/B 不交叉冲抵**：A 当月退款 + 通道费 > GMV（负流水）→ A `settle_cent = 0`、`commission_cent = 0`，且**不冲减 B 的分成基数**（B 照常算）
  - **退款归属**：跨月退款（如成交在上月、退款在本月）→ 按 `refunded_time` 计入本月 `system_refund_cent`，不追溯上月
  - **`business_type='test'` exclude**：mock 含 test 单 → 不进 `gz_recon_daily`
  - **commission 取整**：`settle_cent` 非整 4% 倍数 → `commission_cent` 向下取整到分
  - **季度 settle**：3 个月 monthly → `commission_total_cent`（A+B）+ `maintenance_total_cent`（300000×3）= `payable_total_cent`
  - **跑批幂等**：同日重跑 → `gz_recon_daily` 不重复累加（UPSERT）
- [ ] **AC 11**：权限（doc/11 + CLAUDE.md，走 `@SaCheckPermission` 不用 `@SaCheckRole`）：
  - 对账中心 / 季度结算端点 `@SaCheckPermission("gz:recon:reconcile:list")` / `:export` / `:settle:list` 等；菜单仅 owner 角色授权
  - 无权限店员访问 → 403
- [ ] **AC 12**：reports 末尾必引 doc/11 §9.1 + §4.6 原文片段（`system_settle_cent = system_gmv_cent − system_refund_cent − system_fee_cent` + A/B 不交叉冲抵 + 退款 `refunded_time` 当日归属）证明实现一致

> **纯 admin + 纯后端 ticket，跳过 Tier 2 入口可达 AC**（CLAUDE.md §8.2 / §8.3：Tech 段无 `miniapp/` 路径 + AC 无微信原生能力 → 不进人验列，AI Tier 1A + 1B 全 ✅ 即终态）。

## Tech（端 + 范围）

- **后端**：新建对账域包 `org.dromara.gz.recon.{controller,service,mapper,domain,dto}`，挂 `ruoyi-gz-common` 模块（跨域聚合，消费 `gz.pay.*` 数据）
  - `controller/admin/GzReconReconcileAdminController.java`（admin 路径 `/admin/gz/recon/reconcile`）：
    - `GET /summary`（params: `business_type` + `start_month` + `end_month` → 四栏聚合 + `commission_cent`，查 `gz_recon_monthly`）
    - `GET /daily`（params: `business_type` + `start_date` + `end_date` → `gz_recon_daily` 明细分页）
    - `GET /settle/list`（季度结算列表，查 `gz_recon_settle`）
    - `GET /export`（params: `business_type` + 周期 → EasyExcel 每笔颗粒度流，`@Log(EXPORT)`）
  - `service/IGzReconBatchService.java` + impl（`runDaily` / `runMonthly` / `runQuarterly`，**可单测纯方法**）
  - `service/IGzReconQueryService.java` + impl（admin 查询聚合）
  - `service/internal/ReconCalculator.java`（`settle_cent` MAX(0,..) + `commission_cent` 向下取整纯函数，独立 Bean 便于单测）
  - `job/GzReconDailyJobExecutor.java` / `GzReconMonthlyJobExecutor.java` / `GzReconSettleJobExecutor.java`（`@Component + @JobExecutor` 薄壳，转调 service）
  - `domain/GzReconDaily / GzReconMonthly / GzReconException / GzReconSettle`（4 实体）+ `domain/vo/ReconSummaryVo` / `ReconDetailRowVo`（带 `@ExcelProperty` 供导出复用）
  - `mapper/GzReconDailyMapper / GzReconMonthlyMapper / GzReconSettleMapper`（含跑批 UPSERT + 聚合查询 SQL）
  - **pom 显式加 `ruoyi-common-job` 依赖**（SnailJob @JobExecutor）
  - DDL × 2（4 表 + 菜单/字典/config）
- **Admin 前端**：`code/main/plus-ui/`
  - `views/gz-recon/reconcile/index.vue`（el-tabs A/B + 筛选 + el-statistic 四栏 + 分成卡片 + BizTable 明细）
  - `views/gz-recon/settle/index.vue`（季度结算列表）
  - `api/gz-recon/reconcile.ts`（summary / daily / settle / export 封装）
  - i18n：`zh_CN.ts` / `en_US.ts` 加 `recon.*` 段（实际到账 / 业务线 / 分成 / 通道费 / 季度结算 等术语）
- **测试**：mvn 单测（AC 10 七组）+ admin Playwright E2E（kevin-qa）+ 三层比对 raw output（AC 9）

## 备注

### 强约束 ★

1. **doc/11 §9 + §4.6 是唯一权威**（CLAUDE.md §6 #5 + 9.5 复盘优先级 §1）—— 字段口径逐字落地，实施前读全文 + reports 引原文片段；字段歧义先回补 doc/11 §9 再写代码，不在 ticket 内 patch
2. **对账 = 跑批落表**（`gz_recon_daily/monthly/settle`），**不是实时 VIEW**（删旧卡 `v_gz_finance_daily`）；SnailJob 02:00 跑批前一日
3. **业务线分流统一 `business_type`**（`preorder`=A / `gacha`=B，`test` exclude）—— tab 可显 A/B 但底层 WHERE `business_type`；**禁止** 在表/SQL 加 `business_line` / `biz_line` / A/B 列
4. **A/B 不交叉冲抵**（合同 §4.1.2 / doc/10 Q10.4）—— 各自独立算 `commission_cent`；任一线负流水该月 `settle_cent = MAX(0,..) = 0`、分成 0，不倒贴 / 不冲减另一线
5. **退款仅全额**（V1.1），按 `refunded_time` **当日归属**（不追溯成交日 / 不追溯调整已结算月，C4 + doc/10 E5）
6. **金额全 `_cent`**（不用 `_fen`）；`commission_cent = settle_cent × bp / 10000` **向下取整到分**
7. **季度 settle 含月维护费合并项**：`payable_total_cent = commission_total（A+B）+ maintenance（300000×3）`（合同 §4.6）
8. **SnailJob 跑批（非 sys_job）**：可单测 service + `@JobExecutor` 薄壳；模块 pom 加 `ruoyi-common-job`；任务名/CRON 写 reports/testing-human 由人在控制台注册；**禁止** Quartz / Flyway INSERT sys_job
9. **Excel 每笔颗粒度**（合同 §4.2.1 / F9.5）：订单号 / 金额 / 时间 / 状态 / 通道费 5 列 + 四项汇总；**不透视 / 不合并单元格 / 不小计行**
10. **menu 落 11004（对账）/ 11005（季度结算）**（doc/11 §10.3，**无 FINANCE 11100 段**）
11. **不动微信支付商户号配置**（合同 §2.1 商户号挂甲方公司）—— 本 ticket 只读 `gz_pay_*` 数据
12. **`commission_rate_bp` 走 sys_config**（F9.4，默认 400），不硬编码；通道费 = 真实 `fee_cent`（GZ-PAY-104 来源），**不用 0.6% 近似比例费率**（删旧卡 D3 决策）
13. **DDL 命名 `V<yyyyMMddHHmm>__GZ-ADMIN-105-<desc>.sql`**，时间戳 > `V202606051200`（已有最大版本）；已应用迁移不可改
14. **权限走 `@SaCheckPermission`**（如 `gz:recon:reconcile:list` / `:export`），不用 `@SaCheckRole`；菜单仅 owner 授权
15. **`del_flag` 2 值**（0/2，对齐 ruoyi `@TableLogic`）；`tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`（INSERT 不显式赋，走自动填充；UNIQUE 必含 tenant_id）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 对账跑批落 `gz_recon_daily/monthly/settle` 表，**不用实时 VIEW** | doc/11 §9 已定 4 表；跑批可审计 / 可比对 / 可存历史结算单；实时 VIEW 绕 ruoyi 租户·软删拦截器 + 无法存 channel 侧比对数据 |
| D2 | 通道费用真实 `fee_cent`（GZ-PAY-104 拉 fundflowbill 回写），**不用比例费率近似** | doc/10 Q10.2 + doc/11 F9.2 已裁定按订单粒度 `fee_cent` 汇总；mock 模式由 mock 链路产生 `fee_cent`，对账口径一致 |
| D3 | `commission_cent` 存 `gz_recon_monthly`（不只前端算） | doc/11 §9.2 字段已定；存 DB 支撑季度 settle SUM + 历史结算单存档 + 甲方书面确认锁定（`confirmed`/`settled` 状态） |
| D4 | A/B 负流水 `settle_cent = MAX(0,..)` 在 service 计算 | doc/10 Q10.4 / doc/11 §9.2 已裁定；不让乙方倒贴、不交叉冲抵 |
| D5 | Excel 用 ruoyi 自带 EasyExcel | CLAUDE.md §6 #8 不引未澄清新依赖 |
| D6 | SnailJob 跑批薄壳 + 可单测 service 分离 | CLAUDE.md SnailJob 约束；跑批逻辑单测覆盖（不依赖 SnailJob 运行时）；任务由人在控制台注册 |
| D7 | 季度 settle 月维护费走 `gz.commission.maintenance.monthly.cent × 3` | 合同 §4.6 月维护 ¥3000 × 3 合并进季度应付；走 sys_config 便于重谈 |

### 风险提示 ★

| # | 风险 | 缓解 |
|---|---|---|
| R1 ⭐ | 对账金额口径出错 → 4% 分成兑现错 → 合同纠纷 | doc/11 §9 + §4.6 唯一权威逐字落地 + AC 9 三层比对 raw output（误差 = 0）+ AC 10 单测覆盖 A/B 分流·负流水·test exclude·退款 refunded_time 归属·commission 取整·幂等 + reports 引原文片段 |
| R2 ⭐（外部前置）| 真实通道费 `fee_cent` 依赖 GZ-PAY-104 拉 fundflowbill；真实商户号未开通 → 真实笔费 / 微信商户后台流水比对做不了 | **推进姿态 = mock 全链路自测**（Kevin 决策 1，dev/staging `gz.pay.client.mode=mock`）；真实笔费 + 商户后台流水比对列为外部前置风险，验收前与甲方拿真实商户对账单跑一遍；`commission_rate_bp` 走 sys_config 可调 |
| R3 | A/B 业务线归类错 → 预购退款算到扭蛋 | 统一按 `gz_pay_transaction.business_type` 强分流（doc/10 E4）；**禁止** business_line/biz_line/A·B 列；单测覆盖跨业务线退款归属 |
| R4 | SnailJob 误用 Quartz / Flyway INSERT sys_job → 启动 hard-fail | 跑批 = `@JobExecutor` 薄壳 + 可单测 service；pom 加 `ruoyi-common-job`；任务名/CRON 写 reports 由人在控制台注册；**禁止** sys_job INSERT |
| R5 | 跑批重复执行 → 金额重复累加 | 跑批 UPSERT（同 `(business_day, business_type)` 覆盖不累加）；AC 10 幂等单测 |
| R6 | §0 自检假设 `gz_recon_*` 已建 → 实际从零起翻车 | **§0 自检 grep migration 目录确认上游表实际存在**（`gz_pay_transaction.fee_cent` 由 PAY-104 回写在位 / `gz_pay_refund` 已建 / `gz_recon_*` 应查不到 = 本卡从零建） |
| R7 | 跨月退款使业务线当月负流水（成交上月、退款本月）| 设计意图（doc/10 E5 / C4）：退款按 `refunded_time` 当月核算；负流水时 `settle_cent = 0`、分成 0；季度结算正负不相抵（业务线独立） |
| R8 | Excel 大数据量 OOM | EasyExcel 流式写不 OOM；V1.1 数据量小（< 1000 单/月）不限行；如压测 > 30s 加进度条（v2） |

### §0 自检要点（kevin-coder 实施前 grep migration 目录确认上游表实际存在，不假设）

```bash
# 上游必须存在（PAY-104 回写 fee_cent / PAY-103 退款表 / ADMIN-103 订单聚合）
ls code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/ \
  | grep -E 'GZ-PAY-104|GZ-PAY-103|GZ-ADMIN-103'
grep -rl 'fee_cent\|gz_pay_refund\|business_type' \
  code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/
# gz_recon_* 应查不到 = 本卡从零建（正常）
ls code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/ | grep -E 'gz_recon|GZ-ADMIN-105' \
  || echo "gz_recon 不存在 = 正常，本卡从零建"
```
上游 `gz_pay_transaction.fee_cent` / `gz_pay_refund` 缺 → STOP 报 Kevin（先回 D08 PAY-103/104 收尾），不自行开始。

### ADR 候选（如本日实施时遇到分歧）

- **ADR-V1.1-FN-01**：真实通道费颗粒度（已定 = 真实 `fee_cent` 来自 fundflowbill；如甲方真实商户对账后口径有出入则记 ADR）
- **ADR-V1.1-FN-02**：`commission_cent` 结算后是否锁定不可改（默认 `confirmed`/`settled` 状态软锁；如甲方要求历史结算金额硬冻结则升级）

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!-- 纯 admin/后端 ticket，AI Tier 1A + 1B 全 ✅ 即终态，无 mp 人验；如对账金额复核发现问题在此写：
- 问题 1：<现象> / 期望：<期望>
@coder 修 D15/GZ-ADMIN-105 revision 段 -->
