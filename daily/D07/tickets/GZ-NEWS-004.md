# GZ-NEWS-004 — 资讯定时发布 cron

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M6 §用户操作流程 §甲方发文章 步骤 4 + §关键字段（定时发布时间）
**关联拆解**: doc/02-需求拆解.md §2.5 第 534-545 行
**关联 mockup**: design/mockup/admin-news.html（编辑器内"定时发布"切换 — NEWS-003 已实装表单字段，本 ticket 仅实现后端 cron）
**关联 ADR**: —
**依赖**: GZ-NEWS-003 ✅（同日先完工）— schedule_publish_time 字段 + scheduled 状态枚举落地

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§5 资讯发布流 §定时发布分支**（§N4 publish_time / §N5 schedule_publish_time 字段口径 + 每分钟 cron 扫描的状态流转 scheduled → published）
- **字段表**：doc/11-字段权威表.md §5.1 `gz_news_article`（`status='scheduled'` / `schedule_publish_time` / `publish_time` 字段 + IDX `(tenant_id, schedule_publish_time) WHERE status='scheduled'` 索引利用）+ 附录 A.4 状态枚举
- **UI 参考**：本 ticket 无 UI 改动；admin 端 NEWS-003 已有"定时发布"切换 + 时间选择器表单（admin 走 ruoyi/Element Plus 默认审美，不套用 C 系统）

## What

后端 **SnailJob** 注解式执行器 `gzNewsScheduledPublishTask` 每分钟扫描 `gz_news_article WHERE status='scheduled' AND schedule_publish_time <= now()` → 批量 UPDATE status='published' + 写 publish_time = schedule_publish_time（或 now，业务取前者更符合甲方预期）→ 失败要告警（不能静默）。

> ⚠️ **调度框架 = SnailJob（com.aizuda），不是 Quartz `sys_job`**。RuoYi-Vue-Plus 5.5.x 已用 SnailJob（`sj_*` 表 + `@JobExecutor`），**仓库无 `sys_job` 表** —— 任何 `INSERT INTO sys_job` 的 Flyway 迁移会在启动时 hard-fail 拖垮整个 app。job 名 / cron 表达式 / 路由 / 阻塞策略在 **SnailJob 服务端控制台**（admin「定时任务」菜单，`sj_job` 表）配置，**不走 Flyway DDL 注册**。**权威参考样板**：`ruoyi-modules/ruoyi-gz-bean/src/main/java/org/dromara/gz/bean/job/GzBeanNoShowMarkJob.java`（GZ-BEAN-009，D05 已落，javadoc 详述本约束）。

## AC（验收标准）

- [ ] **AC 1**：**无 Flyway DDL**（本 ticket 不建表、不 INSERT 任何调度表）。schedule 字段 + `scheduled` 状态枚举由 NEWS-003 DDL 已落地；job 注册在 SnailJob 控制台手工配置（见 AC 4）。reports 写明：① 已确认仓库无 `sys_job` 表（`grep sys_job script/sql ✗`）② SnailJob 控制台注册参数表
- [ ] **AC 2**：SnailJob 执行器 Bean `GzNewsScheduledPublishJob`（对齐 `GzBeanNoShowMarkJob` 样板）：
  - 类注解 `@Component @RequiredArgsConstructor @JobExecutor(name = "gzNewsScheduledPublishTask")`
  - 方法签名 `public ExecuteResult jobExecute(JobArgs jobArgs)`（**不是** `run()`）；委托 `IGzNewsArticleService.publishDueArticles(batchSize)`；用 `SnailJobLog.REMOTE.info/error` 写远程日志（落 `sj_job_log_message`）
  - service 查询：`SELECT id, schedule_publish_time FROM gz_news_article WHERE tenant_id='1001' AND status='scheduled' AND schedule_publish_time <= now() AND del_flag=0`（V1.0 单租户 '1001'，无需遍历租户）
  - 批量 UPDATE：`UPDATE gz_news_article SET status='published', publish_time=schedule_publish_time, update_time=now() WHERE id IN (...)` — 单事务，乐观锁（如表有 version）
  - 单批上限 100 篇（防积压时一次性更新过多）；如查询返回 100 则连续触发下一批，最多 5 批（500 篇）后退出本次执行，等下分钟继续
- [ ] **AC 3**：异常告警（不能静默）：
  - try-catch 包裹查询 / 更新；catch Exception → `SnailJobLog.REMOTE.error(...)` + 返回 `ExecuteResult.failure(msg)`（触发 SnailJob 告警通道 + 标记批次异常，落 `sj_job_log_message` / `sj_job_task_batch`）；失败数 > 0 时同样返回 failure
  - V1.0 告警渠道 = SnailJob 远程日志 + 控制台批次状态（无短信 / 钉钉 webhook，doc/10 §5 已裁定 V1.0 告警最简）；prod 监控由 SnailJob 控制台执行日志查看
- [ ] **AC 4**：**SnailJob 控制台注册**（admin「定时任务」菜单，非新增 menu）— reports 贴注册参数：
  - 任务名称：`GZ-NEWS-PUBLISH-DUE`
  - 执行器路由（executor_info）：`gzNewsScheduledPublishTask`（= 本类 `@JobExecutor` name）
  - 触发类型：CRON，表达式 `0 * * * * ?`（每分钟第 0 秒，容器时区 Asia/Shanghai）
  - 阻塞策略：丢弃（DISCARD，上次未跑完不叠加，等价旧 Quartz misfire DO_NOTHING + concurrent 禁止）
  - 组：`ruoyi_group`
- [ ] **AC 5**：单测 `GzNewsArticleServiceImplTest`（针对 `publishDueArticles`，脱离 SnailJob server 直测 service 方法）≥ 3 个测试方法：
  - happy path（mock mapper 返回 3 篇 due → 验证 update 调用 + publish_time = schedule_publish_time）
  - 无 due 数据时直接返回（mapper 返回空列表 → 不执行 update）
  - 批量上限（mock 返回 100 篇 → 触发第二批；> 500 篇时本次执行最多处理 500 篇）
- [ ] **AC 6**：集成测试（reports 必须贴 raw output）：
  - admin 端 NEWS-003 编辑器新建文章 → 状态 scheduled + schedule_publish_time = now + 2 min
  - SnailJob 控制台手动「执行一次」`GZ-NEWS-PUBLISH-DUE` 或等 cron 触发 → DB `SELECT status, publish_time FROM gz_news_article WHERE id=?` 返回 published + publish_time
  - mp 端 NEWS-001 列表能看到该文章

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-news/`
  - `job/GzNewsScheduledPublishJob.java`（SnailJob `@JobExecutor` 执行器壳，独立目录 `job/` 与 `controller/` `service/` 平级；对齐 `ruoyi-gz-bean/.../job/GzBeanNoShowMarkJob.java`）
  - `service/IGzNewsArticleService.java` 加 `publishDueArticles(int batchSize): int` 方法（返回本批处理数量；核心可测逻辑全在 service，job 类只是触发壳）
  - `service/impl/GzNewsArticleServiceImpl.java` 实现
  - `mapper/GzNewsArticleMapper.java` 加 `selectDueScheduled(int limit)` + `batchPublish(List<Long> ids)` 方法
  - **pom 加 `ruoyi-common-job` 依赖**（gz-news 当前无；对齐 gz-bean pom：`<artifactId>ruoyi-common-job</artifactId>` 即可，groupId 继承）
  - **无 Flyway DDL**（job 注册走 SnailJob 控制台，见 AC 4）
- **Admin**：本 ticket 不动 admin 前端（复用 SnailJob「定时任务」控制台查看 / 手动触发）
- **小程序**：N/A
- **测试**：mvn 单测（直测 service.publishDueArticles）+ SnailJob 控制台手动触发 + Kevin 创建 due 文章实际等 2 分钟看效果

## 备注

### 强约束

1. **阻塞策略 DISCARD（丢弃）**（SnailJob 控制台配置，等价旧 Quartz misfire DO_NOTHING）— 系统重启 / 任务暂停导致错过若干次触发时，**不追溯补跑**；下次正常触发时一次性扫所有 due 即可（避免短时间内大量积压 push）
2. **禁止并发**（SnailJob 阻塞策略 DISCARD 已含「上次未跑完不叠加」）— 防执行慢时同一时刻两个 instance 同时跑（虽然单批 100 上限不太可能慢，但安全起见）
3. **publish_time 取 schedule_publish_time 而非 now**（业务预期：「我安排 14:00 发，实际就是 14:00 发」，避免 cron 14:00:30 触发显示 14:00:30 不符合预期）— doc/10 §5 N5 已裁定
4. **批量上限 100 / 5 批**（业务保护）— 防止运营误设 1000 篇同时段定时发布 → cron 单次 lock 表过久
5. **不写 admin 端任务管理 UI**（复用 ruoyi 自带 sys_job admin 页）— CLAUDE.md §10 不重复造轮子
6. **本 ticket 不改 NEWS-003 publish API**（NEWS-003 的「立即发布」走 service.publish() 同步路径，本 ticket 仅加异步 due 扫描）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 用 **SnailJob**（`@JobExecutor`）而非 Spring `@Scheduled` | RuoYi-Vue-Plus 5.5.x 内置 SnailJob，提供控制台 + 执行日志 + 手动触发 + 暂停/启用 — 全部开箱即用；仓库无 Quartz `sys_job` 表 |
| D2 | cron 表达式每分钟（`0 * * * * ?`）| 业务对发布精度要求分级（甲方设的是分钟级时间），每分钟扫描足够 |
| D3 | 单批 100 + 总批 5 | 平衡：单批 100 一次 UPDATE 性能 OK / 总批 5 防 cron 一次执行过久阻塞下分钟触发 |
| D4 | 不接 V1.0 告警渠道 | doc/10 §5 已裁定 V1.0 仅日志 + sys_job_log；V1.1 业务支付涉及钱才加钉钉告警 |
| D5 | publish_time = schedule_publish_time（不取 now）| 业务预期一致性 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 执行器触发时 schedule_publish_time 字段尚未在 D06 NEWS-001 DDL 落地（D07 NEWS-003 ALTER 才补） | §0 自检确认 NEWS-003 已先 merge（schedule_publish_time + scheduled 枚举落地）；本 ticket 串行在 NEWS-003 之后 |
| R2 | 大量 due 同分钟触发（如运营误设 100 篇同时发布）→ cron 单次跑超 1 分钟 | 单批 100 + 总批 5 上限 + 单事务批量 UPDATE（不是逐条 update）→ 实测应 < 5s |
| R3 | 系统重启 24h+ 导致大量 due 积压 → misfire 后下次跑批量过大 | misfire DO_NOTHING + 单次上限 500 → 多次 cron 周期消化；接受这种边界场景下「积压发布会延迟若干分钟」|
| R4 | 时区问题（schedule_publish_time 用户在小程序看的是 GMT+8，cron 服务器若 UTC 会差 8 小时）| ruoyi 默认 `spring.jackson.time-zone=GMT+8` + MySQL `time_zone='+08:00'` — §0 自检确认 application.yml 配置 |
| R5 | 测试时等真实 2 分钟体验差 | 测试时可临时把 cron 改 `*/10 * * * * ?` 每 10 秒；testing-human 后改回 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
