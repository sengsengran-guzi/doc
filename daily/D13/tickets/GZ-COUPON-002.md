# GZ-COUPON-002 — 拼豆抵扣计算（券锁定/核销/回滚）+ 过期 SnailJob

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md 优惠券域
**关联拆解**: doc/02-需求拆解.md GZ-COUPON-002
**关联 mockup**: N/A（纯后端，无 mp/无 admin 新页）
**关联 ADR**: 无（券态机 + 抵扣口径权威 = doc/11 §11.2/§11.3，钉死）
**依赖**: GZ-COUPON-001（D12，`gz_coupon_template`/`gz_user_coupon` 两表 + 乐观锁模板）+ GZ-BEAN-014（D12，拼豆下单事务 + `gz_bean_booking.coupon_id`/`discount_amount_cent` 字段 + `PindouPayCallbackHandler` onPaid + closePindou）

---

## 必读权威文档（缺一不可 — §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §12（券锁定核销流 + 状态机）
- **字段表**：doc/11-字段权威表.md §11.2（券态机，钉死）+ §11.3（抵扣 + GMV 口径，钉死）+ §3.8（pay_closed 回滚）
- **UI 参考**：N/A（纯后端，AI 终态无人验）

## What

在 D12 COUPON-001（券地基）+ BEAN-014（拼豆下单事务）之上，落地**券态流转 + 抵扣计算**：下单锁券、支付核销、取消/支付关闭回滚、过期回收。本卡只接逻辑，不动两表 DDL。

## AC（验收标准）

- [ ] **AC1 锁券**：拼豆下单事务内 `unused → locked`（防一券多用），写 `gz_bean_booking.coupon_id` + `discount_amount_cent`。接入 `GzBeanBookingServiceImpl.java:799` 的 `TODO(D13-COUPON-002)` hook 位。
- [ ] **AC2 核销**：onPaid（拼豆分支）`locked → used`，写 `used_time` + `related_pay_out_trade_no`（= 正向支付 out_trade_no）。接入拼豆 `onPindouPaid` 核销 hook。
- [ ] **AC3 回滚**：订单取消 / 支付关闭 `pay_closed` → `locked → unused`（解锁）。接入 `GzBeanBookingServiceImpl.java:1015` 的 `TODO(D13-COUPON-002)` hook 位（closePindou，ADR-0007 §1.5）。
- [ ] **AC4 抵扣口径（doc/11 §11.3 钉死）**：实付 = `单笔金额 amount_cent − amount_snapshot_cent`（下限 0，券超额差额不退不找零）；实付 > 0 才建 `gz_pay_transaction(business_type=pindou)`，实付 = 0 走免费单兜底（ADR-0007 §1.4）；**`gz_pay_transaction.amount_cent` = 实付，券面额不计 GMV**。单测断言 `amount_cent = total − discount`。
- [ ] **AC5 过期 SnailJob**：`@Component + @JobExecutor`(name=`gzCouponExpireTask`) 薄壳 + 可单测 service，扫 `status='unused' AND expire_time < NOW()` → `expired`；**`locked` 态不被误伤**（已锁定即在用）。配置键 `gz.coupon.expire.cron`。**禁止 Flyway INSERT sys_job**（SnailJob 非 Quartz）；任务名 + CRON 写进 reports。
- [ ] **AC6 单测 ≥ 80%**：券态各流转边（unused→locked / locked→used / locked→unused 回滚 / locked 防过期误伤 / 一券多用拦截 / 实付下限 0 / 券面额不计 GMV）。

## Tech（端 + 范围）

- **后端领地**：
  - `ruoyi-modules/ruoyi-gz-coupon/`：券态 service（锁定/核销/回滚 + 过期）— 复用 `GzCouponTemplateMapper.increaseIssuedCount` 的「版本 CAS + 条件 UPDATE」模板写条件 UPDATE 防并发。新增 `GzCouponExpireJob`（job 薄壳）+ service。
  - `ruoyi-modules/ruoyi-gz-bean/`：接 3 个 hook 位（submitPaid:799 锁券 / closePindou:1015 回滚 / onPindouPaid 核销）。**用 `ObjectProvider` 惰性注入打断潜在循环依赖**（bean→coupon→? 仿 BEAN-014 对 PindouHandler 的处理）。
  - `ruoyi-gz-coupon/pom.xml`：**加 `ruoyi-common-job` 依赖**（D12 COUPON-001 未加，本卡首引 SnailJob）。
- **DDL**：预计**无表变更**（券态 = `gz_user_coupon.status` UPDATE，字段 D12 已建全）。若确需索引，时间戳用 `V202606210000`+（> 已有 max `202606200200`）。
- **migration 验证**：用 raw SQL 不污染 `flyway_schema_history`（仿 D12），留 Tier 1B 启动 app 触发 Flyway。

## 备注（并行批次纪律 ⭐）

- **本卡与 PAY-105 / RECYCLE-001 第一波并行**。源码领地：你独占 gz-coupon + gz-bean(hook)；PAY-105 改 gz-common；RECYCLE-001 新建 gz-recycle。**不重叠**。
- **编译/单测**：用 `mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-coupon,ruoyi-modules/ruoyi-gz-bean`（**不加 `-am`** — gz-common 走 .m2 现成稳定 jar，因 PAY-105 并行在改 gz-common 源码，`-am` 会读半成品）。
- **不要 `mvn install`**（留主线程全部完工后统一按依赖序 install，再交 Tier 1B）。
- 跨层契约：券面额计算 `_cent` / 业务码 `UC-` / 乐观锁 `version` / `tenant_id` 自动填充。
- **不要 spawn kevin-qa**（子 agent 不能 spawn 孙 agent，Tier 1B 由主线程全完工后统一派）。写完 reports（含 §AI 测试段占位）即返回。

---

## §revision（Kevin 批量人验后填，初始空）
