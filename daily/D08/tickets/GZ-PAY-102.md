# GZ-PAY-102 — 主动查单 + 补单

**优先级**: P1
**复杂度**: S
**关联 PRD**: doc/02-prd.md M1 §微信支付 §异常分支
**关联拆解**: doc/02-需求拆解.md §3.1 第 642-652 行
**关联 mockup**: —（纯后端逻辑）
**关联 ADR**: —
**依赖**: GZ-PAY-101

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §2 微信支付通道接入流 §异常分支（回调延迟 / 回调丢失场景）+ §6 V1.1 演进流（PAY-101 同日新增的 §6.1）
- **字段表**：doc/11-字段权威表.md
  - §4.1 gz_pay_order（pending 状态识别 + paid_at 字段）
  - §4.5 支付状态字段口径（pending → paid 唯一允许通过查单触发的状态变更）
- **UI 参考**：N/A（纯后端 cron）

## What

微信回调失败 / 延迟（5+ 分钟）时，后端定时任务每分钟扫描 pending 超 5 分钟的支付订单，主动调微信 `orderquery` API 查实际状态：

- 微信侧已 paid → 模拟一次完整回调流程（复用 PAY-101 回调处理器）→ 更新订单 + 触发业务 handler
- 微信侧仍 NOTPAY / CLOSED → 不动；继续等下一轮扫描（超 30min 仍 NOTPAY 则关闭订单 status='closed'）

确保用户支付成功但前端断网 / 微信回调失败时，重进订单页能看到 paid 状态。

## AC（验收标准）

- [ ] **AC 1**：cron job `PayOrderQueryJob`（ruoyi 内置 Quartz）每 1 分钟跑：
  - `SELECT * FROM gz_pay_order WHERE status='pending' AND created_at < NOW() - INTERVAL 5 MINUTE AND created_at > NOW() - INTERVAL 24 HOUR LIMIT 100`（限流 100 防雪崩）
  - 每条调微信 `pay/orderquery` API（带 out_trade_no）
- [ ] **AC 2**：微信返回 `trade_state=SUCCESS`：
  - 走 PAY-101 同款幂等流程（`SELECT FOR UPDATE` + 当前 status pending 才更新 + 调业务 handler）
  - 写 gz_pay_callback_log 标记 source='active_query'（区分被动回调）
- [ ] **AC 3**：微信返回 `trade_state=NOTPAY` 或 `USERPAYING`：跳过不处理
- [ ] **AC 4**：微信返回 `trade_state=CLOSED` 或 `PAYERROR`：UPDATE gz_pay_order.status='failed' + reason 字段
- [ ] **AC 5**：超过 30 分钟仍 pending → 主动调微信 `closeorder` 关闭 + UPDATE status='closed'（防止用户事后偷偷支付）
- [ ] **AC 6**：单测覆盖：
  - mock 微信返回 SUCCESS → 业务 handler 被调
  - mock 同 transaction_id 重复跑 → handler 仅调一次（依赖 PAY-101 幂等）
  - mock 返回 NOTPAY → 不更新状态
  - 共 ≥ 3 个测试方法
- [ ] **AC 7**：admin 端**不需要新页面**（运维查 gz_pay_callback_log.source='active_query' 数量即可）

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/pay/`
  - `job/PayOrderQueryJob.java`（Quartz job，cron `0 * * * * ?` 每分钟）
  - `service/IPayOrderQueryService.java` + `service/impl/PayOrderQueryServiceImpl.java`
  - 复用 PAY-101 的 `IPayOrderService` + `WxPayCallbackHandler` 注册中心 + `WxPaySignValidator`
  - 不新建表 / 不新建枚举 — gz_pay_callback_log 加 `source ENUM('passive_callback','active_query') NOT NULL DEFAULT 'passive_callback'` 字段（PAY-101 DDL 里加，本 ticket 跑 ALTER migration）
- **小程序**：N/A
- **测试**：mvn 单测 + dev 环境手动构造 pending 订单（INSERT 一条 created_at = NOW() - 10 MINUTE）+ Postman mock 微信查单返回

## 备注

### 强约束

1. **必须复用 PAY-101 回调 handler**（不允许另写一套 paid 状态变更逻辑 — 单点维护）
2. **限流 100/分钟**（防雪崩 / 防微信 API 限流）— 如果 pending 订单超 100 条堆积说明回调链路出问题，告警
3. **24 小时窗口**（`created_at > NOW() - 24h`）— 太老的订单不查（用户已离开场景，关闭即可）
4. **30 分钟主动 closeorder** — 防止用户事后偷偷支付造成异常状态
5. **source 字段** — 运维区分主动查单 vs 被动回调比例（监控指标）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 每分钟扫一次（不是每 30s 或更密） | V1.1 流量小，1 分钟粒度足够；过密浪费微信 API 配额 |
| D2 | 限流 100 条 | 单次 cron 跑完控制在 30s 内（每条查单约 200ms） |
| D3 | 走 ruoyi 内置 Quartz 不引新调度框架 | V1.0 已用 Quartz 跑 BEAN no_show cron，统一栈 |
| D4 | source 字段加在 gz_pay_callback_log（不是 gz_pay_order） | 单条订单可能多次查单（首次 NOTPAY → 后续 SUCCESS），log 表多条 source 区分 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 主动查单触发 handler 时 handler 业务逻辑异常 → 订单永远停在 pending | handler 异常落 log + 监控告警；运维介入手动修 |
| R2 | 微信 orderquery API 限流（5000 次/天） | 限流 100/分钟 + 业务量按 V1.1 估算约 200 单/天 → 远低于限额 |
| R3 | 跨日订单（created_at 接近 24h 边界）查不到 → 状态停 pending | AC 5 兜底 — 超 30min 必关闭，不会跨日 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
