# GZ-PAY-104 — 业务通道账单对账批（每日 SnailJob 拉 fundflowbill 回写真实笔费 fee_cent）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M7.8 对账中心 / §4.5 对账规则
**关联拆解**: doc/02-需求拆解.md §业务支付域（V1.1，PAY 系列）
**关联 mockup**: N/A（纯后端跑批，无 UI）
**关联 ADR**: N/A
**依赖**: GZ-PAY-101（业务统一支付服务 — 锚定 `gz_pay_transaction.business_type` / `transaction_id` / `fee_cent` 列 + `IWechatPayClient` V3）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

> 业务流 + 字段表是 ticket 实施的"蓝图"，缺引用 = AI 凭字面猜实现 = 翻车前兆。

- **业务流**：doc/10 §10 对账中心流（M7.8）—— 尤其 **E6**「系统按 transaction 级实际 fee 字段汇总，不依赖固定费率」+ **Q10.2** 通道费按订单粒度 attribute 业务线。本卡是 §10 的**数据准备前置**：把每笔真实通道费灌进 `gz_pay_transaction.fee_cent`，§10 对账 SUM 才有真源。
- **字段表**：
  - doc/11 §4.2 `gz_pay_transaction` —— 回写目标列 `fee_cent`（BIGINT N NULL，分单位，**通道手续费**）；关联键 `transaction_id`（VARCHAR(64)，微信交易号）；过滤维度 `business_type` / `status='paid'` / `paid_time`。
  - doc/11 **F4.3 / F9.2**（裁定本卡存在的依据）：微信 V3 回调 body **不含** fee；通道费唯一来源 = 每日跑批拉 `/v3/bill/fundflowbill`（资金账单）按 `transaction_id` 关联。**字段早已保留，本卡是落地这条裁定（即 doc 中暂记的 GZ-PAY-101.b）**。
  - doc/11 §9.1 `gz_recon_daily.system_fee_cent` 计算口径 = `SUM(gz_pay_transaction.fee_cent WHERE business_type=? AND status='paid' AND DATE(paid_time)=?)` —— 本卡是其上游唯一数据源（**fee_cent 不回写 → D11 GZ-ADMIN-105 对账"通道费"列恒为 0**）。
- **UI 参考**（V1.0 设计冻结期）：N/A（纯后端，无 admin/mp 页面）

## What

新建每日跑批：用 `IWechatPayClient`（V3）拉前一业务日的微信**资金账单** `/v3/bill/fundflowbill`，下载并解析返回的 CSV（gzip），按 `transaction_id` 关联回写 `gz_pay_transaction.fee_cent`（真实通道手续费，分）。这是 D11 GZ-ADMIN-105 对账"通道费"的**唯一真实数据源**（微信 V3 支付回调 body 不含 fee）。跑批以 SnailJob `@JobExecutor` 薄壳触发，业务逻辑下沉到可单测 service；同日重跑幂等（不重复累计）；缺账 / 对不上记可观测告警。

## AC（验收标准）

- [ ] AC 1：**新建账单批表**（DDL 见 Tech）`gz_pay_bill_fundflow` 记录每个 `transaction_id` 的账单原始笔费 —— 至少含 `transaction_id` / `out_trade_no` / `fee_cent` / `bill_date`(账单业务日 DATE) / `raw_line`(原始 CSV 行，便于追溯)；UNIQUE `(tenant_id, bill_date, transaction_id)`。`tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`（INSERT 不显式赋值，走自动填充），`del_flag` 2 值。
- [ ] AC 2：**SnailJob 薄壳**：新增 `@Component` + `@JobExecutor(name="gzPayFundflowBillJob")`，仅做"取 bizDate（默认前一日）→ 调 service → 返回 SnailJob 执行结果"，**无业务逻辑在壳内**；业务全在可单测 service `PayFundflowBillService#reconcileFee(LocalDate bizDate)`。**不写 Quartz、不写 Flyway `INSERT sys_job`**（会启动 hard-fail）；任务名 + CRON 写进 reports + testing-human 由人在 SnailJob 控制台注册。
- [ ] AC 3：**拉账单 + 解析 CSV**：service 调 `IWechatPayClient` 拉 `/v3/bill/fundflowbill?bill_date=yyyy-MM-dd`（返回 `download_url` + `hash_value`）→ 下载 gzip CSV → 解析每行提取 `transaction_id` / `out_trade_no` / 手续费列（分）。解析得到的笔费**先落 `gz_pay_bill_fundflow`**（按 AC1 UNIQUE 幂等 upsert），再据此回写。校验下载文件 `hash_value`（sha1）不匹配 → 抛错 + 告警，不静默回写脏数据。
- [ ] AC 4：**按 transaction_id 关联回写 fee_cent**：对账单中每个 `transaction_id`，`UPDATE gz_pay_transaction SET fee_cent=? WHERE tenant_id=? AND transaction_id=? AND status='paid'`。仅回写 `status='paid'` 的交易；`business_type='test'` 的交易**照常回写 fee_cent**（对账阶段才 exclude，本卡不预过滤，避免取数错源）。
- [ ] AC 5：**缺账 / 对不上告警（可断言，非主观）**：service 返回结构化结果 `{billTotal, matched, transactionNotFound, paidNoBill}`：① 账单有 `transaction_id` 但系统无对应 `gz_pay_transaction`（`transactionNotFound`，孤儿账单行）；② 系统有当日 `status='paid'` 交易但账单缺其行（`paidNoBill`，缺账）。两类计数 > 0 时打 `log.warn`（含明细 transaction_id 列表）。**单测断言这两个计数器**，不依赖人眼看日志。
- [ ] AC 6：**同日重跑幂等（不重复累计 fee）**：`fee_cent` 是**覆盖式回写**（`SET fee_cent=?` 绝对值，非 `fee_cent = fee_cent + ?` 累加）；`gz_pay_bill_fundflow` 按 `(tenant_id, bill_date, transaction_id)` UNIQUE upsert。**单测**：同一 `bizDate` 连跑 2 次，`gz_pay_bill_fundflow` 行数不翻倍、某笔 `fee_cent` 第二次跑后值不变（不叠加）。
- [ ] AC 7：**mock 模式自测可跑**：`gz.pay.client.mode=mock` 时 `MockWechatPayClient` 返回可控的 mock fundflowbill（构造一份含 N 笔 `transaction_id` 的 mock CSV，至少含 1 笔正常匹配 + 1 笔孤儿 + 制造 1 笔缺账），驱动 AC3-AC6 全链路 + AC5 两类告警计数被触发。**本卡 DoD 以 mock 为准**；真实账单拉取 = 外部前置风险（见备注）。

> **纯后端 ticket：跳过 Tier 2 入口可达 AC**（无 mp / 无 admin 页面，CLAUDE.md §8.2）。

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-pay/`（PAY 域；包 `org.dromara.gz.pay.{controller,service,mapper,domain,dto}`）
  - **pom 依赖**：本卡用 SnailJob `@JobExecutor` → 确认 `ruoyi-gz-pay` pom **已显式加 `ruoyi-common-job`**（PAY-101 若已加则复用；未加则本卡 §0 自检发现后补上，先 `mvn install -pl ruoyi-modules/ruoyi-gz-pay -am` 再写 executor）。
  - 新增：`PayFundflowBillJob`（`@Component`+`@JobExecutor` 薄壳）/ `PayFundflowBillService`(+Impl，可单测核心) / `GzPayBillFundflowMapper` + domain/dto / fundflowbill CSV 解析器（`IWechatPayClient` 扩 `downloadFundFlowBill(billDate)` 或本域内封装 V3 调用 —— 与 PAY-101 协商接口归属，避免改 ruoyi 源码）。
  - **DDL**：`ruoyi-admin/src/main/resources/db/migration/V202606061100__GZ-PAY-104-pay-bill-fundflow.sql`（时间戳 > 当前最大 `V202606051200`；已应用迁移不可改）。建 `gz_pay_bill_fundflow`（AC1 字段 + UNIQUE 含 tenant_id）。**不改 `gz_pay_transaction` 结构**（`fee_cent` 列已由 PAY-101 在扩展迁移中加好；本卡 §0 自检 grep migration 确认该列存在，仅 UPDATE 不 ALTER）。
- **Admin / 小程序**：无（纯后端）。
- **测试**：
  - 单测覆盖 `PayFundflowBillService`：CSV 解析（正常行 / 表头 / 空行 / 列缺失抛错）；transaction_id 关联回写；AC5 两类告警计数（孤儿 + 缺账）；AC6 同日重跑幂等（行数不翻倍 + fee 覆盖非累加）；hash 校验失败抛错。
  - 覆盖率目标：service 核心 ≥ 60%（命中 CLAUDE.md §8.1）。

## 备注

- **【外部前置风险】真实账单拉取依赖甲方商户配置**：真实 `/v3/bill/fundflowbill` 需甲方商户号 + cert + apiV3Key 就绪（与 PAY-001/101 同一外部前置，对应 D08 README R1）。本卡 DoD 仅认 `gz.pay.client.mode=mock` 全链路；真实账单格式（微信资金账单 CSV 列序 / 手续费列名）以官方文档为准，真实端到端验证不当默认就绪，并行催甲方完成 V1.0 验收 + 提供商户配置。
- **本卡 = doc/11 F4.3 / F9.2 中暂记的「GZ-PAY-101.b 拉账单 ticket」落地**：fee_cent 列早已在表里保留，缺的就是这条灌数据的跑批。回写真源唯一性：fee 不来自支付回调（V3 body 无 fee），不来自固定费率（doc/10 §10 E6），只来自资金账单跑批。
- **与对账中心（D11 GZ-ADMIN-105 / gz_recon_daily）的契约**：本卡只负责"把真实笔费灌进 `gz_pay_transaction.fee_cent`"；按 `business_type` 汇总 / `system_fee_cent` 计算 / 业务线 attribution 在 GZ-ADMIN-105，本卡**不建 gz_recon_* 表、不算汇总**（越界即违 ticket 边界）。
- **跑批时点**：账单 T+1 可用，跑批默认处理"前一业务日"（北京时间）；CRON 建议 `0 30 3 * * ?`（凌晨 3:30，账单已生成）—— 实际任务名 `gzPayFundflowBillJob` + CRON 写进 reports + testing-human 由人在 SnailJob 控制台注册（**不写进迁移**）。
- **§0 自检要点（kevin-coder 强制）**：grep `db/migration/` 目录确认 ① `gz_pay_transaction` 表 + `fee_cent` 列**实际存在**（PAY-101 已落），② `transaction_id` 列存在 —— **不假设上游已建**（gz-ord/gz-gacha 已证空脚手架，PAY 域也以 migration 目录实际表为准）；确认 `ruoyi-gz-pay` pom 有 `ruoyi-common-job`。任一不满足 → STOP 报 Kevin，不自行开始。
- **回调路由不冲突**：本卡是**主动拉账单跑批**，不注册支付/退款 SPI 回调 handler（与 PAY-102 查单补单、PAY-103 退款回调不抢 SPI key，对应 R2）。

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!-- 问题清单写这里，然后 @coder 修 D08/GZ-PAY-104 revision 段 -->
