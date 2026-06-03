# GZ-PAY-102 — 主动查单 + 补单（SnailJob 扫 pending → V3 查单 → 走回调同一幂等路径补单）

**优先级**: P1
**复杂度**: S
**关联 PRD**: doc/02-prd.md M1 §微信支付 §异常分支（回调丢失 / 延迟）
**关联拆解**: doc/02-需求拆解.md §3.1 GZ-PAY-102
**关联 mockup**: N/A（纯后端定时任务，无 UI）
**关联 ADR**: N/A
**依赖**: GZ-PAY-101（业务统一支付服务：统一订单号 / SPI 回调路由 / 回调幂等路径，**必须 close 后再起**）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§6 业务支付流（V1.1）**
  - §6 状态机：`created → pending → paid`，以及 `pending → timeout`（5 分钟未支付自动 close）/ `pending → closed`（业务侧主动关单）
  - §6.N7「主动查单兜底」（扫所有 pending > 5 min 的 `gz_pay_transaction`）
  - §6.E3「主动查单查到 paid 但本地是 pending（微信回调丢失）→ 主动 paid + 业务回调，用户无感」
- **字段表**：doc/11-字段权威表.md
  - §4.2 `gz_pay_transaction`（`status` / `out_trade_no` / `transaction_id` / `paid_time` / `expire_time` / `closed_time` / `version` 乐观锁；status 枚举 = `created/pending/paid/timeout/closed/failed/refunding/refunded`）
  - §4.3 `gz_pay_callback_log`（纯审计表，`callback_type='payment'` / `process_status` / `raw_body`；**永不结构变更**）
- **UI 参考**：N/A（纯后端，无 mp / admin 页面）

## What

后端定时任务（SnailJob）每分钟扫描 `gz_pay_transaction` 中 `status='pending'` 且超 5 分钟未到终态的交易，逐条调微信支付 V3 查单 API（`IWechatPayClient`），微信侧已 `SUCCESS` 则走**与回调完全相同的幂等补单路径**（复用 GZ-PAY-101 的 SPI 路由 + `SELECT ... FOR UPDATE` 幂等），确保用户支付成功但微信回调丢失 / 延迟时本地交易能自愈到 `paid` 并触发业务出单。

## AC（验收标准）

- [ ] **AC 1**：SnailJob 执行器 `PayOrderQueryJobExecutor`（`@Component` + `com.aizuda` `@JobExecutor(name="payOrderQueryJob")` 薄壳，**禁 Quartz / 禁 Flyway INSERT sys_job**），调用可单测 service `IPayOrderQueryService.scanAndReconcile()`。任务名 + CRON（建议 `0 */1 * * * ?` 每分钟）写进 reports + testing-human.md，**由人在 SnailJob 控制台注册**（不写进迁移、不写进代码硬编码注册）。
- [ ] **AC 2**：扫描条件可测试 —— `SELECT * FROM gz_pay_transaction WHERE tenant_id='1001' AND status='pending' AND create_time < NOW() - INTERVAL 5 MINUTE AND create_time > NOW() - INTERVAL 24 HOUR LIMIT 100`（24h 窗口 + LIMIT 100 防雪崩，字段名以 doc/11 §1 公共字段 `create_time` 为准）。单测断言 SQL/Wrapper 仅命中此区间。
- [ ] **AC 3**：每条 pending 交易调 `IWechatPayClient` 的 V3 查单 API（按 `out_trade_no` 查），解析 `trade_state`。mock 模式（`gz.pay.client.mode=mock`）下 `MockWechatPayClient` 返回可配置 `trade_state`，单测据此覆盖各分支。
- [ ] **AC 4**：`trade_state=SUCCESS` → **走 GZ-PAY-101 的回调同一幂等补单路径**：`SELECT ... FOR UPDATE` 锁定该 `gz_pay_transaction` 行 → 当前 `status='pending'` 才推进 `paid`（写 `transaction_id` / `paid_time`）→ 按 `business_type` 经 SPI（`PayCallbackHandler`）路由到对应业务 handler（预购 → ORD 出单）→ 同事务内写一条 `gz_pay_callback_log`（`callback_type='payment'`，`raw_body` = V3 查单返回报文，`process_status='processed'`）。**不另写一套 paid 状态变更逻辑**。
- [ ] **AC 5**：幂等 —— 已是终态（`paid` / `refunding` / `refunded` / `closed` / `timeout`）的交易，查到 SUCCESS 也不二次推进、不二次调 handler（`SELECT FOR UPDATE` 后状态判定直接跳过）。单测：同一笔连跑两轮 `scanAndReconcile()`，业务 handler 仅被调一次。
- [ ] **AC 6**：`trade_state` 为 `NOTPAY` / `USERPAYING` → 跳过不处理，保持 `pending`，等下一轮（单测断言状态未变、handler 未被调）。
- [ ] **AC 7**：`trade_state` 为 `CLOSED` / `PAYERROR` / `REVOKED` → 推进 `gz_pay_transaction.status='closed'`（CLOSED/REVOKED）或 `'failed'`（PAYERROR），写 `closed_time`（CLOSED/REVOKED 场景）。状态值严格取 doc/11 §4.2 枚举，**不新造状态值**。
- [ ] **AC 8**：超 30 分钟仍 `pending` 且查得 `NOTPAY`（用户始终未付）→ 调微信 V3 关单 API（`IWechatPayClient` close order）+ 推进 `status='timeout'` + 写 `closed_time`，防止用户事后偷付造成本地与微信不一致。mock 模式下 `MockWechatPayClient` 关单返回成功。
- [ ] **AC 9**：单测覆盖（`-DskipTests=false`，≥ 4 个测试方法）：
  - mock 返回 `SUCCESS` → 交易推进 `paid` + 业务 handler 被调一次；
  - 同笔重复扫 → handler 仅调一次（幂等）；
  - mock 返回 `NOTPAY` 且 < 30min → 状态保持 `pending`、handler 未调；
  - mock 返回 `NOTPAY` 且 > 30min → 调关单 + 推进 `timeout`；
  - mock 返回 `CLOSED` → 推进 `closed`。
- [ ] **AC 10**：本 ticket **不新建表 / 不新建枚举 / 不加列**（补单复用既有 `gz_pay_transaction` + `gz_pay_callback_log`，幂等路径复用 PAY-101）。**无 DDL 迁移**。如实现中确证需 schema 变更（例如给 `gz_pay_transaction` 加查单计数等可观测列）→ STOP 报 Kevin，新建 `V<yyyyMMddHHmm>__GZ-PAY-102-<desc>.sql`（时间戳必须 > `V202606051200`，且已应用迁移不可改），不得编辑 PAY-001/PAY-101 已有迁移。

> 纯后端 ticket：**跳过 Tier 2 入口可达 AC**（无 mp 端 / 无 admin 端页面，CLAUDE.md §8.2）。

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/`（pay 域，包名 `org.dromara.gz.pay.{service,job}`）
  - `job/PayOrderQueryJobExecutor.java`：`@Component` + `@JobExecutor(name="payOrderQueryJob")` 薄壳，仅调 `IPayOrderQueryService.scanAndReconcile()`，不放业务逻辑。
  - `service/IPayOrderQueryService.java` + `service/impl/PayOrderQueryServiceImpl.java`：扫 pending → 调 `IWechatPayClient` 查单 → 分发到补单 / 关单逻辑。
  - **复用 GZ-PAY-101**：回调幂等补单路径（`SELECT FOR UPDATE` + 状态判定 + SPI `PayCallbackHandler` 路由）、`IWechatPayClient`（`WechatPayV3ClientImpl` / `MockWechatPayClient`）、统一订单号 / `gz_pay_transaction` / `gz_pay_callback_log` mapper。**禁止**另写一套 paid 状态机或新建回调入口。
  - **依赖**：`ruoyi-gz-common` 已在调度场景使用 SnailJob 则无需改 pom；若编译缺 `@JobExecutor` → §0 自检确认 pom 含 `ruoyi-common-job` 依赖后 `mvn install -pl ruoyi-modules/ruoyi-gz-common -am`。
- **Admin**：N/A（运维查 `gz_pay_callback_log` 中 `callback_type='payment'` 且 `raw_body` 来源为查单报文的记录即可，无新页面）。
- **小程序**：N/A。
- **测试**：`mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -am`；dev 用 `gz.pay.client.mode=mock` 构造 pending 交易（INSERT 一条 `create_time = NOW() - INTERVAL 10 MINUTE`、`status='pending'`）→ 手动调一次 `scanAndReconcile()` 或触发 SnailJob → 验证推进 `paid` + 业务 handler 出单。

## 备注

### 强约束

1. **复用 PAY-101 回调幂等路径单点维护**：补单与被动回调走同一段「`SELECT FOR UPDATE` + 状态判定 + SPI 路由」代码，绝不允许 PAY-102 再写一套 paid 推进逻辑（双写必然脱钩）。
2. **调度 = SnailJob**（`@Component` + `@JobExecutor`），仓库**无 sys_job 表**。**禁止** Quartz / `org.quartz` / Flyway `INSERT sys_job`（启动 hard-fail）。任务名 `payOrderQueryJob` + CRON `0 */1 * * * ?` 由人工在 SnailJob 控制台注册（写进 testing-human.md 待注册清单）。
3. **限流 100 / 轮 + 24h 窗口**：单轮 LIMIT 100 控制在微信 API 配额内；超 24h 的老 pending 不再查单（用户已离场），由 AC 8 的 30min 关单逻辑兜底关掉，不会无限堆积。
4. **状态值锚定 doc/11 §4.2 枚举**：补单 `paid`；用户超时未付 `timeout`；微信侧 CLOSED/REVOKED → `closed`；PAYERROR → `failed`。**不新造** `success` / `error` / `expired` 等别名。
5. **business_type 分流真源在 `gz_pay_transaction`**：补单路由按 `gz_pay_transaction.business_type`（`preorder` / `gacha` / `test`）经 SPI 分发，与回调一致；不读业务订单表分流列（业务订单表无 `business_line` / `biz_line`）。
6. **金额单位 `_cent`**：本 ticket 不改金额，仅引用 `amount_cent`；任何日志/断言用分，不用 `_fen`。

### 推进姿态（Kevin 决策 1 = Mock 全链路自测）

- 本 ticket DoD 以 `gz.pay.client.mode=mock`（`MockWechatPayClient` 可配置返回 `trade_state`）的全链路自测为准。
- **真实微信支付商户号 / V3 查单 API 端到端 = 外部前置风险**（甲方挂号 + cert + apiV3Key 就绪滞后）—— 不当默认就绪，仅在 mock 下验证查单/关单/补单逻辑正确，真实端到端列入外部前置项。

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 每分钟扫一次（非 30s）| V1.1 流量小，1 分钟粒度足够；过密浪费微信 V3 查单配额 |
| D2 | 单轮 LIMIT 100 | 单次跑控制在 30s 内（每条查单约 200ms），避免雪崩与执行器超时 |
| D3 | 走 SnailJob 不引新调度框架 | 全仓统一 SnailJob，无 sys_job 表；Quartz/Flyway INSERT 会 hard-fail |
| D4 | 补单复用回调幂等路径（不另写）| 单点维护 paid 推进 + SPI 路由，杜绝主动/被动两套逻辑脱钩 |
| D5 | 不加 `source` 列区分主动/被动 | doc/11 §4.3 `gz_pay_callback_log` 是纯审计表禁结构变更；区分靠 `raw_body` 来源（查单报文 vs 通知报文），无需新列 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | **§0 自检若假设上游表已建 → 翻车**。gz-ord/gz-gacha 为空脚手架，本日 PAY-101 才落 `business_type` 等扩展 | §0 自检 **grep migration 目录确认上游表实际存在**（`ls db/migration/` 见 `V202606041200__GZ-PAY-001-...transaction...` + PAY-101 当日扩展迁移；`mvn` 反查 `gz_pay_transaction` 字段），不假设；PAY-101 未 close 前 STOP 不起本卡 |
| R2 | 补单触发业务 handler 内部异常 → 交易停 `pending` 永不自愈 | handler 异常落 `gz_pay_callback_log.process_status='failed'` + `process_error` + 整事务回滚（保持 pending），下一轮再扫重试；连续失败写日志告警，运维介入 |
| R3 | 微信 V3 查单 API 限流 | LIMIT 100/分钟 + V1.1 估算约 200 单/天，远低于配额；超 24h 老单不查 |
| R4 | 与 PAY-104（对账批）/ PAY-103（退款）同注册 SPI handler / 路由 key → 撞 key | 三者落地后串行 review 一次 SPI 路由表；本卡复用 PAY-101 既有 `payment` SPI key，不新增路由 key |

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
