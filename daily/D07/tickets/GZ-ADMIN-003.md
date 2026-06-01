# GZ-ADMIN-003 — 基础数据看板（非交易指标）

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M7.1 数据看板 + 合同 §2.1 第一期（二）"基础数据看板（用户数、预约数、资讯阅读数等非交易指标）"
**关联拆解**: doc/02-需求拆解.md §2.6 第 578-588 行
**关联 mockup**: design/mockup/admin-dashboard.html（仅布局参考；admin 走 ruoyi/Element Plus 默认审美，不套用 C 系统；仅参考 KPI 卡片字段 + 布局结构。**V1.0 仅显示非交易卡片**，mockup 中 GMV / 订单数 / 抽数等交易类卡片本 ticket 不实装）
**关联 ADR**: —
**依赖**: GZ-ADMIN-001 / 004 ✅ + GZ-SYS-003 ✅ + GZ-BEAN-008 ✅ + GZ-NEWS-001 ✅（数据源齐）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md（无独立看板业务流章节；本 ticket 是聚合查询，不涉业务状态机；但需读 §3 拼豆预约的 booking 状态枚举 + §5 资讯发布的 published 状态枚举，理解"今日新增"/"累计"的过滤口径）
- **字段表**：doc/11-字段权威表.md
  - §2.1 `gz_user`（累计用户 = `COUNT(*)` / 今日新增 = `WHERE DATE(create_time)=CURDATE()`）
  - §3.4 `gz_bean_booking`（累计预约 = `COUNT(*)` / 今日预约 = `WHERE DATE(create_time)=CURDATE()`；**所有 status 都计入**，包括 cancelled / no_show — 业务上"运营关心提交了多少人"而非"实际到店"）
  - §5.1 `gz_news_article.read_count`（资讯累计阅读 = `SUM(read_count)`；今日阅读 V1.0 无独立日表，**裁定 V1.0 不出"今日阅读"指标**或用近似 ≈ 累计差值，见强约束 #4）
  - **本 ticket 新增表 `gz_dashboard_snapshot`**（看板快照，cron 每 5 min 写一行；doc/11 §6/§7 缺口段，本 ticket DDL 落地后补 doc/11 — 见今日特殊约束）
- **UI 参考**：doc/12-UI-权威索引.md §AD-SYS-DASHBOARD — KPI 卡片 + 图表 + 待办（admin 走 ruoyi/Element Plus 默认审美，不套用 C 系统）；**V1.0 仅 KPI 卡片**（5 张：累计用户 / 今日新增用户 / 累计预约 / 今日预约 / 资讯累计阅读），图表 + 待办推 V1.1

## What

admin 端首页数据看板：
1. 5 张 KPI 卡片（标题 + 数值 + 单位 + 「相比昨日 ±N%」副文案 + 末次更新时间）
2. 数据计算 cron 每 5 分钟跑一次 → 写入 `gz_dashboard_snapshot` 快照表 → 前端读最新快照（不直接 COUNT 源表，规避性能 + 锁竞争）
3. 卡片右上角「最近更新：X 分钟前」+ 手动刷新按钮（POST `/system/gz/dashboard/refresh` 触发立即重算）
4. **V1.0 不展示 GMV / 订单 / 抽数 / 退款**（拆解 §2.6 AC 3 + 合同 §2.1 V1.0 范围）— mockup 上这些卡片本 ticket 不实装

## AC（验收标准）

- [ ] **AC 1**：DDL `V202606041100__GZ-ADMIN-003-create-gz_dashboard_snapshot.sql` 落 `gz_dashboard_snapshot` 表：
  - `snapshot_time DATETIME(3) NOT NULL`（快照时间，5 min 粒度）+ IDX
  - `metric_key VARCHAR(64) NOT NULL`（指标 key：`total_users` / `today_new_users` / `total_bookings` / `today_bookings` / `total_news_reads`）
  - `metric_value BIGINT NOT NULL`
  - `tenant_id` + 公共字段（CLAUDE.md §6 #2 #3）
  - UNIQUE `(tenant_id, snapshot_time, metric_key)` — 同一时刻同一 metric 只一行
  - IDX `(tenant_id, metric_key, snapshot_time DESC)`（查最新值用）
- [ ] **AC 2**：**SnailJob 执行器**（**不是** Quartz `sys_job`；仓库无 `sys_job` 表，任何 `INSERT INTO sys_job` 的 Flyway 会启动 hard-fail）。job 在 **SnailJob 控制台** 注册（admin「定时任务」菜单，非 Flyway DDL）— reports 贴注册参数：
  - 任务名称：`GZ-DASHBOARD-SNAPSHOT`
  - 执行器路由（executor_info）：`gzDashboardSnapshotTask`（= `@JobExecutor` name）
  - 触发类型：CRON，表达式 `0 0/5 * * * ?`（每 5 分钟整点触发，容器时区 Asia/Shanghai）
  - 阻塞策略：丢弃（DISCARD，等价旧 Quartz misfire DO_NOTHING + concurrent 禁止）
  - 组：`ruoyi_group`
  - **权威参考样板**：`ruoyi-modules/ruoyi-gz-bean/.../job/GzBeanNoShowMarkJob.java`（GZ-BEAN-009）
- [ ] **AC 3**：SnailJob 执行器 Bean `GzDashboardSnapshotJob`（`@Component @JobExecutor(name="gzDashboardSnapshotTask")` + `public ExecuteResult jobExecute(JobArgs)`，委托 service）— service 计算 5 个 metric 并批量 INSERT：
  - `total_users` = `SELECT COUNT(*) FROM gz_user WHERE tenant_id='1001' AND del_flag=0`
  - `today_new_users` = 同上 + `AND DATE(create_time)=CURDATE()`
  - `total_bookings` = `SELECT COUNT(*) FROM gz_bean_booking_log WHERE tenant_id='1001' AND from_status IS NULL AND to_status='pending'`（用 log 表统计累计创建，因为 booking 表 cancelled 会物理删；doc/11 §3.5 锚定）
  - `today_bookings` = 同上 + `AND DATE(create_time)=CURDATE()`
  - `total_news_reads` = `SELECT COALESCE(SUM(read_count), 0) FROM gz_news_article WHERE tenant_id='1001' AND status='published' AND del_flag=0`
  - 批量 INSERT 一条 snapshot_time = now() 5 行（每个 metric 一行）
- [ ] **AC 4**：admin API：
  - `GET /system/gz/dashboard/latest` → 返回 5 个 metric 最新值 + snapshot_time（按 metric_key group by 取每组 snapshot_time DESC LIMIT 1）
  - `GET /system/gz/dashboard/trend?metricKey=&days=7` → 返回最近 7 天每 5 min 快照（图表数据源，V1.0 前端**不展示**但 API 留接口 V1.1 用）
  - `POST /system/gz/dashboard/refresh` → 立即同步触发一次 job.run()（owner 权限 `gz:dashboard:refresh`）
  - 权限 `gz:dashboard:view`
- [ ] **AC 5**：admin 看板页 `views/index.vue`（替换 plus-ui 默认首页 / 或 `views/dashboard/index.vue` 看 plus-ui 默认路由结构）：
  - 5 张 KPI 卡片（Element Plus `el-card` 默认风格，**不调样式**）
  - 每张卡片：标题（dict / i18n）+ 数值（千分位格式化）+ 「更新于 X 分钟前」时间 + 占位副文案「相比昨日 +N%」（V1.0 简化为 placeholder「-」，趋势计算推 V1.1）
  - 顶部「数据更新于 yyyy-MM-dd HH:mm」+「立即刷新」按钮（loading 1-3 秒）
  - 路由 `/dashboard` + menu_id **300** 挂 ruoyi 自带「数据看板」目录（如已有则复用）
- [ ] **AC 6**：menu_id 插入 — admin 端「数据看板」menu_id **300** + perm `gz:dashboard:view`（DDL 内 INSERT sys_menu + sys_role_menu 给 owner / staff）
- [ ] **AC 7**：单测 `GzDashboardSnapshotJobTest` ≥ 2 个测试方法：
  - happy path（mock 5 个 COUNT mapper 返回固定值 → 验证 batch insert 5 行）
  - 异常处理（mock mapper 抛 SQLException → 不应让 cron 阻塞，log error 后继续）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-common/`（看板属于跨域聚合，放 common 而非 news/bean/user — 否则 module 间互依赖）
  - `controller/GzDashboardController.java`（admin 路径 `/system/gz/dashboard`）
  - `service/IGzDashboardService.java` + `service/impl/GzDashboardServiceImpl.java`
  - `job/GzDashboardSnapshotJob.java`（SnailJob `@JobExecutor` 执行器壳；对齐 `ruoyi-gz-bean/.../job/GzBeanNoShowMarkJob.java`，核心逻辑在 service）
  - `domain/GzDashboardSnapshot.java` + `domain/vo/GzDashboardLatestVO.java`
  - `mapper/GzDashboardSnapshotMapper.java`（写快照）
  - `mapper/GzDashboardMetricMapper.java`（跨表查询 — 5 个 COUNT / SUM 各一个方法）
  - **pom 加 `ruoyi-common-job` 依赖**（gz-common 当前无；如 PAY-001 已先加则复用，§0 自检确认）
  - DDL × 1（snapshot 表 + sys_menu INSERT；**无 sys_job INSERT** — job 走 SnailJob 控制台注册）
- **Admin**：`plus-ui/src/views/dashboard/index.vue`（或 plus-ui 默认首页路径，§0 自检确认）+ `api/gz-common/dashboard.ts`
- **小程序**：N/A
- **测试**：mvn 单测 + 手动触发 refresh + 浏览器看卡片数值

## 备注

### 强约束

1. **V1.0 仅 5 个非交易指标**（拆解 §2.6 AC 3 / 合同 §2.1）— GMV / 订单数 / 抽数 / 退款 / 分成 等 V1.1 才出
2. **不直接 COUNT 源表**（性能 + 锁竞争考虑虽 V1.0 数据量小但养成习惯）— 前端永远读 snapshot 表；snapshot 数据写入由 cron 集中
3. **累计预约用 booking_log 表统计**（doc/11 §3.5 锚定）— 因为 booking 表 cancelled 会物理删（doc/11 §3.4 强约束）、用 booking 表 COUNT 会漏掉取消的；log 表永不删 → 准确反映"运营关心提交了多少人"
4. **今日阅读指标 V1.0 不出**（doc/11 §5.1 read_count 仅累加，无独立日表）— mockup 上若有此卡片就标 placeholder「-」+ tip「V1.1 上线」
5. **手动刷新按钮限流**（同一用户 5 秒内只能点一次，防止并发触发 cron）— 前端 disable button + 后端 RateLimiter（ruoyi 自带注解 `@RateLimiter`）
6. **snapshot 表数据保留 90 天**（业务上趋势查询只看近 7-30 天）— V1.0 不实装清理 cron，V1.1 数据量起来再加（一行 / 5min × 5 metric = 1440 行/天 × 90 天 = 13 万行，体量可控）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | snapshot 表设计为 wide-long 形式（每 metric 一行）而非 wide-wide（每时刻一行 5 列）| 灵活：V1.1 加 metric 不需要 ALTER 表加列；趋势查询 `WHERE metric_key=?` 简单 |
| D2 | 看板模块代码放 gz-common 而非新建 gz-dashboard 模块 | 看板是跨域聚合（user + bean + news），不应反向依赖单个业务模块；放 common 最简洁，避免循环依赖 |
| D3 | 累计预约用 booking_log 而非 booking 表 | doc/11 §3.4 booking 表 cancelled 物理删；log 表永不删，反映真实历史 |
| D4 | trend API 留接口 V1.0 不展示 | 前端实装图表需选型（echarts / chart.js）；V1.1 实装（admin 走 Element Plus 默认审美，不套用 C 系统）|
| D5 | refresh 用同步触发 + 5s 限流 | 同步给用户即时反馈（不用轮询）；限流防误点 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | "今日新增用户" 与微信登录"未注册即落库"口径冲突（SYS-002 落库时 create_time = 首次登录时间，可能用户只登录一次就走，但 V1.0 没有"实名认证"区分注册/匿名）| 接受 — V1.0 统计口径「登录过的微信用户即用户」，doc/10 §1 已裁定；与合同 §2.1 一致 |
| R2 | booking_log 表查"累计预约"是否包含 admin 手动核销 / cron no_show 流转日志（操作类型 admin / cron）→ 数据膨胀 | mapper SQL 加 `AND operator_type='user' AND from_status IS NULL`（仅用户提交首条 pending 日志），过滤掉后续流转 |
| R3 | cron 5 min 间隔与"最近更新 X 分钟前"提示偏差最多 5 min | 接受 — UI 提示「最近更新于 yyyy-MM-dd HH:mm」让用户自行判断；点「立即刷新」即时更新 |
| R4 | doc/11 §6/§7 缺 dashboard_snapshot 章节 | 本 ticket completion 后由 Kevin 周末复盘补 doc/11（CLAUDE.md §9.5 第 1 优先级"改权威蓝图"）|
| R5 | mockup admin-dashboard.html 含交易类卡片但 V1.0 不实装 → 客户演示时可能问 | 6/10 客户演示前预先说明「V1.0 仅非交易指标，符合合同 §2.1」；admin 走 ruoyi/Element Plus 默认审美，不评判视觉 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
