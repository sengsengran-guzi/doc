# GZ-USER-104 — 用户确认收货 + 自动签收

**优先级**: P1
**复杂度**: S
**关联 PRD**: doc/02-prd.md M5 §跨境物流 §节点 7 + §业务规则 4.4
**关联拆解**: doc/02-需求拆解.md §3.4 第 891-901 行
**关联 mockup**: design/mockup/order-detail.html（底部"确认收货"按钮 — 旧 mockup 仅布局参考；视觉以 C 系统为准，doc/13）
**关联 ADR**: —（C1 后签收作为 L3 终态见 doc/10 §9 N5/N6）
**依赖**: GZ-USER-103 ✅(D10)

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md **§9** §状态机（in_china_dispatching → delivered 不可回退，除 owner）+ §关键节点 N5（自动签收 cron）+ N6（用户主动确认）+ N8（owner 回退带审计）+ §异常分支 E4（自动签收时用户尚未收到）
- **字段表**：doc/11-字段权威表.md **§A.7 `gz_logistics_status`** §6.3 `gz_ord_order.logistics_status` / `delivered_at` 字段 + §7.4 `gz_gacha_order.logistics_status` / `delivered_at` 字段 + §8.3 `gz_logistics_audit` 审计表（owner 回退走此表）
- **UI 参考**：doc/12 §MP-ORD-DETAIL §页面结构 第 6 项底部 fixed CTA：预购订单 → "确认收货"（仅 logistics_status=in_china_dispatching 显示）。视觉走 C 日漫海报浓墨：Biz* 组件 + var(--c-*)，doc/tokens.md + doc/13；旧 mockup 仅布局参考

## What

后端定时任务：每小时扫"国内派送（`in_china_dispatching`）> 7 天"订单 → 自动签收（`logistics_status = delivered` + 写 `delivered_at`）。mp 端订单详情底部"确认收货"按钮（仅 `in_china_dispatching` 显示）：用户点击立即签收（提前 7 天等待）。**签收后不可回退**（除 owner 后台带审计）。

## AC（验收标准）

- [ ] **AC 1**：后端定时任务 `GzLogisticsAutoConfirmJob`（基于 ruoyi-job xxl-job 或 spring `@Scheduled`）：每小时扫描 `gz_ord_order` + `gz_gacha_order` 两表中 `logistics_status='in_china_dispatching'` 且 `paid_at`（或物流推进时间 `cn_dispatched_at` 字段，D09 应已落）`+ 7 天 < NOW()` 的订单，批量 UPDATE `logistics_status='delivered'` + `delivered_at = NOW()`；写 `gz_logistics_audit`（action=`auto_delivered`，operator_id=0 系统）
- [ ] **AC 2**：mp 端 `POST /app/gz/user/orders/{orderNo}/confirm-receive` 接口：sa-token-app 权限 + `where user_id = current_user_id`；service 层校验 `logistics_status = in_china_dispatching`（否则 400 "订单状态不允许此操作"）→ UPDATE → 写 `gz_logistics_audit`（action=`user_confirmed`，operator_id=current_user_id）
- [ ] **AC 3**：mp 端订单详情底部 CTA "确认收货"按钮：仅 `logisticsStatus === 'in_china_dispatching'` 显示；点击前 confirm modal："确认已收到货物？签收后无法回退"；确认后调 AC 2 接口 → 成功 toast"已签收" + 路由 reload 详情
- [ ] **AC 4**：签收后订单不可再回退（普通用户 / staff 都无入口）；**owner 后台超级权限**回退（doc/10 §9 N8）由 D11+ 的 ADMIN-104（或后续 ticket）实施，本 ticket 不做
- [ ] **AC 5**：定时任务扫描 batch 大小 100 / 次（防长事务）；处理失败的单条不阻塞其他订单（try-catch 单订单粒度，失败写 error log）
- [ ] **AC 6**：定时任务 cron 表达式 `0 0 * * * ?`（每小时整点）；启动配置写在 `application-dev.yml` 不在代码硬编码
- [ ] **AC 7**：i18n 全覆盖（`order.confirm.xxx` / `order.confirm.modal.xxx`）
- [ ] **AC 8**：单测 `GzLogisticsAutoConfirmJobTest`（mock 当前时间 + 造 2 条满 7 天 + 1 条不满 7 天的订单，验只签 2 条）+ `confirmReceive` happy / 状态校验失败两 case

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-user/`
  - `controller/applet/GzUserOrderMpController.java`（USER-101 已建，加 `confirmReceive(orderNo)` 方法）
  - `service/IGzUnifiedOrderService.java` + impl 加 `confirmReceive(orderNo, userId)`
  - `job/GzLogisticsAutoConfirmJob.java`（新建 + `@Scheduled` 或 ruoyi-job 注册）
  - `service/impl/GzLogisticsAuditServiceImpl.java`（D08/D09 应已落，本 ticket 调用其 `logAction()` 写审计）
  - 不落新 DDL（消费 D09 已建表 + D08 已建 `gz_logistics_audit` 表）
- **小程序**：`code/main/miniapp/src/`
  - `pages/me/order-detail.vue`（USER-102 已建，加底部 CTA 按钮 + confirm modal）
  - `api/gz-user.ts` 加 `confirmReceive(orderNo)`
- **测试**：单测 + 联调（造 1 个 `in_china_dispatching` 订单 → mp 端点"确认收货" → 验 `logistics_status=delivered` + 审计记录）

## 备注

### 强约束

1. **签收后不可回退**（owner 例外）：service 层校验 `logistics_status` 必须 `in_china_dispatching` 才允许签收；不允许 `delivered` → `delivered` 重复操作（幂等检查）
2. **审计必写**：所有签收操作（用户 / 系统）都写 `gz_logistics_audit`，operator_id 区分（0=系统 / 真实 userId=用户）
3. **定时任务 batch + 单订单 try-catch**：防 1 条失败拖整批 + 防长事务
4. **接口 `where user_id = ${current_user_id}`**：防越权确认他人订单
5. **不引入审批流 / 二次确认**（V1.1 简化）：用户点按钮即签收（前端 confirm modal 已是二次确认）
6. **包名 `org.dromara.gz.user.*`** + 表前缀 `gz_user_*` / `gz_ord_*` / `gz_gacha_*`（CLAUDE.md §6）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 每小时扫描而非每天 | 7 天的窗口不需要分钟级精度；每小时 cron 数据库压力极小（千级订单） |
| D2 | 自动签收时间计算用 `cn_dispatched_at` 或 `paid_at`（fallback）| 优先用 admin 推进物流到 in_china_dispatching 时的时间戳；D09 ORD/GACHA-104 应已落该字段；否则 fallback paid_at |
| D3 | 审计 operator_id=0 表示系统 | 与人类 userId(>0) 区分；前端展示时映射为"系统自动" |
| D4 | mp 端按钮 confirm modal 二次确认 | 防误点签收；签收后不可逆，需用户明确 |
| D5 | xxl-job 还是 @Scheduled | ruoyi 默认带 xxl-job 接入；如 D08 已配置则用之，否则简化用 `@Scheduled`（ruoyi-admin 已有 `@EnableScheduling`）|

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 7 天自动签收时用户尚未收到 → 抱怨 | doc/10 §9 E4 已 ack；V1.1 不在 C 端提供"我没收到"反馈入口（推 v2）；用户走客服 → owner 后台手动回退 |
| R2 | 定时任务并发跑两次（如分布式部署）| ruoyi-vue-plus 自带分布式锁 / xxl-job 单节点跑；如用 @Scheduled 走 redisson lock 保护（D01 SYS-001 已建 RedissonClient） |
| R3 | D09 `cn_dispatched_at` 字段未落 | §0 自检：`DESC gz_ord_order` 验列存在；缺则在本 ticket 加 DDL `ALTER TABLE` + 自迁移 + 报 Kevin |
| R4 | 时区问题（NOW() vs Java now()） | DB 时区 + JVM 时区均 +08:00（dev-compose.yml + ruoyi-admin/application.yml 已配置），dev 环境一致 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
