# GZ-USER-104 — 用户确认收货 + 自动签收（SnailJob）

**优先级**: P1
**复杂度**: S
**关联 PRD**: doc/02-prd.md M5 §跨境物流（C1 简化 2 态 + 终态）+ §业务规则 4.4
**关联拆解**: doc/02-需求拆解.md §3.4（GZ-USER-104 用户确认收货 + 自动签收）
**关联 mockup**: design/mockup/order-detail.html（底部「确认收货」CTA — 旧 mockup 仅布局参考；视觉以 C 系统为准，doc/13）
**关联 ADR**: doc/_adr/0005-cross-border-logistics-2-state.md（C1 物流 2 态 + 终态裁定；L3 `delivered` 终态不可回退口径）
**依赖**: GZ-USER-103 ✅(D10，mp 物流 2 态读取侧)

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§9 跨业务订单聚合 + 跨境物流流**
  - §9 状态机（L3 `delivered` 终态，**仅 owner 后台超级权限可回退 + 写审计**，注释见状态图 note）
  - §9 关键节点 **N5**（系统 cron 扫 `in_china_dispatching > 7 天` → `delivered`）+ **N6**（用户主动确认收货，仅 `in_china_dispatching` 显示「确认收货」→ 立即 `delivered`）+ **N8**（owner 物流回退，本 ticket 不实施）
  - §9 异常分支 **E4**（自动签收时用户尚未收到：V1.1 不在 C 端给「我没收到」入口，走客服 → owner N8 回退）
  - （扭蛋衍生订单签收语义并入 §9；§8 是扭蛋抽奖流，仅作奖品 snapshot 背景，**签收不在 §8**）
- **字段表**：doc/11-字段权威表.md
  - **§6.3 `gz_ord_order`** + **§6.4 物流字段说明**（7 天自动签收 cron 口径：锚 `cn_dispatched_at`，天数走 `sys_config` `gz.delivery.auto_sign_days` 默认 7，推进同事务写 `delivered_time` + `business_status → delivered` + 审计）
  - **§7.4 `gz_gacha_order`**（同名物流字段 `logistics_status` / `cn_dispatched_at` / `delivered_time`，自动签收同口径）
  - **§8.3 `gz_logistics_audit`**（`action_type` ∈ `user_confirmed` / `auto_delivered`；`operator_type` ∈ `user` / `system`；`operator_id` VARCHAR：用户签收 = `gz_user.user_no`，系统 = 字面量 `system`；`from_status` / `to_status` 记物流态变更）
  - 附录 A.7 `gz_logistics_status` 字典（3 项：`in_japan` / `in_china_dispatching` / `delivered`）
- **UI 参考**（mp ticket）：doc/12 §MP-ORD-DETAIL 底部 fixed CTA「确认收货」（仅 `logistics_status=in_china_dispatching` 显示）。视觉走 C 日漫海报浓墨：`src/components/biz/Biz*` + `var(--c-*)` token（doc/tokens.md + doc/13）；旧 mockup 仅布局参考，不逐像素

## What

后端 SnailJob 定时任务每小时扫 `gz_ord_order` + `gz_gacha_order` 两表中 `logistics_status='in_china_dispatching'` 且 `cn_dispatched_at` 超 `gz.delivery.auto_sign_days`（默认 7）天的订单 → 自动签收（`logistics_status='delivered'` + `business_status='delivered'` + 写 `delivered_time` + 审计 `auto_delivered`）。mp 端订单详情底部「确认收货」按钮（仅 `in_china_dispatching` 态显示）：用户点击立即签收（写审计 `user_confirmed`）。`delivered` 为终态不可回退（owner 后台 N8 回退由 D11 ADMIN-104 实施，本卡不做）。

## AC（验收标准）

- [ ] **AC 1**：SnailJob 执行器 `GzLogisticsAutoSignExecutor`（`@Component` + `com.aizuda.snailjob` `@JobExecutor`，薄壳）委托 `IGzLogisticsAutoSignService.autoSign()`。**禁止** Quartz / `@Scheduled` / Flyway INSERT `sys_job`（仓库无 sys_job 表，INSERT 会启动 hard-fail）；`ruoyi-gz-user` 模块 pom 显式加 `ruoyi-common-job` 依赖。任务名 + CRON（`0 0 * * * ?` 每小时整点）写进 reports + testing-human，由人在 SnailJob 控制台注册。
- [ ] **AC 2**：`autoSign()` 扫描两表 `logistics_status='in_china_dispatching' AND cn_dispatched_at IS NOT NULL AND cn_dispatched_at <= NOW() - INTERVAL :days DAY`（`:days` 读 `sys_config` `gz.delivery.auto_sign_days`，默认 7；不在代码硬编码 7）。命中单批 UPDATE：`logistics_status='delivered'` + `business_status='delivered'` + `delivered_time=NOW()`，同事务每单写一条 `gz_logistics_audit`（`action_type='auto_delivered'` / `operator_type='system'` / `operator_id='system'` / `from_status='in_china_dispatching'` / `to_status='delivered'`）。
- [ ] **AC 3**：mp 端 `POST /app/gz/user/orders/{orderNo}/confirm-receive`：sa-token-app 鉴权 + service 层 `where user_id = current_user_id`（防越权他人订单）；校验 `logistics_status='in_china_dispatching'`（否则返业务异常「订单状态不允许此操作」），否则单事务 UPDATE `logistics_status='delivered'` + `business_status='delivered'` + `delivered_time=NOW()` + 写 `gz_logistics_audit`（`action_type='user_confirmed'` / `operator_type='user'` / `operator_id=当前用户 user_no` / `from_status='in_china_dispatching'` / `to_status='delivered'`）。orderNo 前缀（`PREORD` / `GACHA`）路由到对应表。
- [ ] **AC 4**：幂等 / 不可回退 —— 接口与 cron 均仅当 `logistics_status='in_china_dispatching'` 才推进；已 `delivered` 再调返业务异常（不重复写 `delivered_time` / 不重复写审计）；普通用户 / staff 无任何回退入口（owner N8 回退由 D11 ADMIN-104 实施，本卡不做）。
- [ ] **AC 5**：cron 单订单 try-catch 粒度（一单失败不阻塞同批其余，失败写 error log）；分页扫描 batch ≤ 100 / 次防长事务；分布式部署只跑一份（SnailJob 单节点调度 + service 内 `logistics_status` 条件 UPDATE 行级幂等，重复触发不双签）。
- [ ] **AC 6**：mp 端订单详情底部 CTA「确认收货」仅 `logisticsStatus === 'in_china_dispatching'` 显示；点击弹 confirm modal「确认已收到货物？签收后无法回退」；确认调 AC 3 接口 → 成功 toast「已签收」+ reload 详情（CTA 消失、状态变「已签收」）。i18n 全覆盖（`order.confirm.*`），扭蛋订单文案不出现「抽奖/中奖/开奖」（盲盒语义）。
- [ ] **AC 7**：单测 —— `GzLogisticsAutoSignServiceTest`（mock 时钟 + 造 `in_china_dispatching` 满 N 天 ×2 + 不满 N 天 ×1 + `in_japan` ×1 + 已 `delivered` ×1，验仅前 2 条被签且各写 1 条 `auto_delivered` 审计）；`confirmReceive` happy（`in_china_dispatching` → `delivered` + `user_confirmed` 审计）+ 状态非法（`in_japan` 抛异常）+ 越权（他人订单不可签）三 case。
- [ ] **AC 8: Tier 2 入口可达** —— Kevin 从 mp 底部 tab「我的」→「我的订单」→ 点一条 `in_china_dispatching` 态订单进详情（USER-102 已建路径）→ 底部见「确认收货」CTA → 点击签收成功。无需自定义编译模式 / console navigateTo。

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-user/`
  - `controller/applet/GzUserOrderMpController.java`（USER-101 已建，加 `confirmReceive(orderNo)`）
  - `service/IGzLogisticsAutoSignService.java` + `impl/GzLogisticsAutoSignServiceImpl.java`（新建，`autoSign()` 可单测，不依赖 SnailJob 运行时）
  - `job/GzLogisticsAutoSignExecutor.java`（新建，`@Component` + `@JobExecutor`，仅委托 service）
  - 签收审计统一调 `gz_logistics_audit` 写入（D08/D09 物流推进侧已建审计写入逻辑则复用，否则本卡补 `IGzLogisticsAuditService.log(...)`）
  - `pom.xml` 加 `ruoyi-common-job` 依赖（SnailJob 客户端）
  - **不落新 DDL**（消费 D09 已建 `gz_ord_order` / `gz_gacha_order` 物流字段 + D08/D09 已建 `gz_logistics_audit`）；如 §0 自检发现上游字段缺 → **STOP 报 Kevin**，不在本卡补 ALTER
- **小程序**：`code/main/miniapp/src/`
  - `pages/me/order-detail.vue`（USER-102 已建，加底部 `BizFixedCta`「确认收货」+ confirm modal）
  - `api/gz-user.ts` 加 `confirmReceive(orderNo)`
  - i18n `order.confirm.*`（zh_CN / en_US）
- **测试**：单测（AC 7）+ 联调（造 1 个 `in_china_dispatching` 订单 → mp 点「确认收货」→ 验 `logistics_status=delivered` + `business_status=delivered` + `delivered_time` 非空 + `gz_logistics_audit` 一条 `user_confirmed`）

## 备注

### 强约束

1. **时间字段命名钉死**（doc/11 §6.4）：签收时间一律 `delivered_time`、支付时间 `paid_time`、国内派送起算 `cn_dispatched_at`；**禁止** `delivered_at` / `paid_at`。
2. **审计必写且字段对齐 doc/11 §8.3**：`action_type='user_confirmed'`（用户）/ `'auto_delivered'`（系统）；`operator_type` + `operator_id`（用户 = `user_no`，系统 = 字面量 `system`）；`from_status` / `to_status` 记物流态。
3. **天数走 sys_config**：`gz.delivery.auto_sign_days`（默认 7），不在代码硬编码；改天数不改代码。
4. **物流态独立于 business_status 并行**（doc/11 §6.4）：签收同时推进 `logistics_status` 与 `business_status` 到 `delivered`（doc/11 §6.4 cron 口径明确两态同推）。
5. **越权防护**：`confirmReceive` service 层 `where user_id = current_user_id`，不可签他人订单。
6. **不引审批流 / 二次后端确认**（V1.1 简化）：前端 confirm modal 即二次确认；后端单次 UPDATE。
7. **包名 `org.dromara.gz.user.*`**；消费表 `gz_ord_order` / `gz_gacha_order` / `gz_logistics_audit`（CLAUDE.md §6）。

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 调度框架 = **SnailJob**（`@JobExecutor` 薄壳 + 可单测 service）| 仓库无 sys_job 表；Quartz / Flyway INSERT sys_job 会启动 hard-fail；业务逻辑放 service 便于单测，executor 只委托 |
| D2 | 自动签收时钟锚 `cn_dispatched_at`（非 `paid_time` / `create_time`）| 日本段时长不可控，进入国内派送才计 7 天（doc/11 §6.4） |
| D3 | 行级条件 UPDATE 保幂等（`WHERE logistics_status='in_china_dispatching'`）| cron 重复触发 / 用户与 cron 同时推进，仅一方命中条件，天然不双签，无需额外分布式锁 |
| D4 | mp confirm modal 二次确认 | 签收不可逆，防误点；前端拦一道即够，后端不再二次确认 |
| D5 | owner 回退（N8）划归 D11 ADMIN-104 | 本卡只做「进 delivered」侧；回退是 owner 超级权限 + 必填 reason 审计，属物流推进写入侧 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 上游 D09 物流字段（`cn_dispatched_at` / `delivered_time` / `business_status`）未落 | **§0 自检 grep migration 目录确认上游表 + 字段实际存在**（`grep -rl 'gz_ord_order\|gz_gacha_order' .../db/migration/` + `DESC gz_ord_order` 验列），缺 → **STOP 报 Kevin**，本卡不补 ALTER（回 D09 收尾） |
| R2 | `gz_logistics_audit` 表未落 | §0 自检 grep migration 目录确认 `gz_logistics_audit` 迁移文件存在；缺 → STOP 报 Kevin |
| R3 | 7 天自动签收偏早、用户尚未收到 | doc/10 §9 E4 已 ack：V1.1 不给 C 端「我没收到」入口（推 v2）；用户走客服 → owner 后台 N8 回退（D11 ADMIN-104） |
| R4 | 时区（`NOW()` vs JVM now）| DB + JVM 均 +08:00（dev-compose.yml + ruoyi-admin/application.yml 已配），dev 一致；cron 与 `cn_dispatched_at` 同库 `NOW()` 比较更稳 |
| R5 | V1.0 现状 = 已过 AI 测试但未客户验收、未上线 | 本卡纯增量（新 executor + 新接口 + mp CTA），不改 V1.0 已交付路径，对未验收基线无回切影响 |

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
