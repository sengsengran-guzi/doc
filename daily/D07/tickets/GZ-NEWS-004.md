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
- **UI 参考**（设计冻结期）：本 ticket 无 UI 改动；admin 端 NEWS-003 已有"定时发布"切换 + 时间选择器表单

## What

后端 ruoyi `sys_job` cron 任务 `gz_news_publish_due_job` 每分钟扫描 `gz_news_article WHERE status='scheduled' AND schedule_publish_time <= now()` → 批量 UPDATE status='published' + 写 publish_time = schedule_publish_time（或 now，业务取前者更符合甲方预期）→ 失败要告警（不能静默）。

## AC（验收标准）

- [ ] **AC 1**：DDL `V202606041030__GZ-NEWS-004-insert-sys_job-publish-due-cron.sql`：
  - INSERT ruoyi `sys_job` 一行：job_name=`gz_news_publish_due_job` / invoke_target=`gzNewsScheduledPublishJob.run()` / cron_expression=`0 * * * * ?`（每分钟第 0 秒）/ misfire_policy=`3`（DO_NOTHING，避免追溯触发批量发布旧 due）/ concurrent=`1`（禁止并发）/ status=`0`（启用）
- [ ] **AC 2**：定时任务 Bean `GzNewsScheduledPublishJob`：
  - 方法 `run()` — 加 `@Component("gzNewsScheduledPublishJob")` + 加 `@TenantIgnore`（如 ruoyi 多租户拦截）或显式遍历租户（V1.0 单租户 '1001' 直接查）
  - 查询：`SELECT id, schedule_publish_time FROM gz_news_article WHERE tenant_id='1001' AND status='scheduled' AND schedule_publish_time <= now() AND del_flag=0`
  - 批量 UPDATE：`UPDATE gz_news_article SET status='published', publish_time=schedule_publish_time, update_time=now() WHERE id IN (...)` — 单事务，乐观锁（如表有 version）
  - 日志：`log.info("gz_news_publish_due_job: published {} articles, ids={}", count, ids)`
  - 单批上限 100 篇（防积压时一次性更新过多）；如查询返回 100 则连续触发下一批，最多 5 批（500 篇）后退出本次执行，等下分钟继续
- [ ] **AC 3**：异常告警（不能静默）：
  - try-catch 包裹查询 / 更新；catch Exception → `log.error("gz_news_publish_due_job failed", e)` + 写 ruoyi `sys_job_log` 失败记录（status=1）
  - V1.0 告警渠道 = 仅日志 + sys_job_log（无短信 / 钉钉 webhook，doc/10 §5 已裁定 V1.0 告警最简）；prod 监控由 ruoyi 自带 `sys_job_log` admin 页面查看
- [ ] **AC 4**：admin 端「定时任务」menu（ruoyi 自带 menu_id=110 系统监控）下 `sys_job` 列表可看到 `gz_news_publish_due_job` + 可手动 trigger 一次 + 可查执行日志 — **本 ticket 不新增 menu**，复用 ruoyi 自带
- [ ] **AC 5**：单测 `GzNewsScheduledPublishJobTest` ≥ 3 个测试方法：
  - happy path（mock mapper 返回 3 篇 due → 验证 update 调用 + publish_time = schedule_publish_time）
  - 无 due 数据时直接返回（mapper 返回空列表 → 不执行 update）
  - 批量上限（mock 返回 100 篇 → 触发第二批；> 500 篇时本次执行最多处理 500 篇）
- [ ] **AC 6**：集成测试（reports 必须贴 raw output）：
  - admin 端 NEWS-003 编辑器新建文章 → 状态 scheduled + schedule_publish_time = now + 2 min
  - 等 2 分钟 + cron 触发 → DB `SELECT status, publish_time FROM gz_news_article WHERE id=?` 返回 published + publish_time
  - mp 端 NEWS-001 列表能看到该文章

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-news/`
  - `job/GzNewsScheduledPublishJob.java`（定时任务 Bean，独立目录 `job/` 与 `controller/` `service/` 平级）
  - `service/IGzNewsArticleService.java` 加 `publishDueArticles(int batchSize): int` 方法（返回本批处理数量）
  - `service/impl/GzNewsArticleServiceImpl.java` 实现
  - `mapper/GzNewsArticleMapper.java` 加 `selectDueScheduled(int limit)` + `batchPublish(List<Long> ids)` 方法
  - DDL × 1（INSERT sys_job）
- **Admin**：本 ticket 不动 admin 前端（复用 ruoyi 自带「系统监控 → 定时任务」页查看 / 手动触发）
- **小程序**：N/A
- **测试**：mvn 单测 + 手动 cron trigger（ruoyi sys_job admin 页点「执行一次」按钮）+ Kevin 创建 due 文章实际等 2 分钟看效果

## 备注

### 强约束

1. **misfire_policy=3 DO_NOTHING**（doc/10 §5 N5 锚定）— 系统重启 / cron 暂停导致错过若干次触发时，**不追溯补跑**；下次正常触发时一次性扫所有 due 即可（避免短时间内大量积压 push）
2. **concurrent=1 禁止并发**（ruoyi `@DisallowConcurrentExecution`）— 防 cron 执行慢时同一时刻两个 instance 同时跑（虽然单批 100 上限不太可能慢，但安全起见）
3. **publish_time 取 schedule_publish_time 而非 now**（业务预期：「我安排 14:00 发，实际就是 14:00 发」，避免 cron 14:00:30 触发显示 14:00:30 不符合预期）— doc/10 §5 N5 已裁定
4. **批量上限 100 / 5 批**（业务保护）— 防止运营误设 1000 篇同时段定时发布 → cron 单次 lock 表过久
5. **不写 admin 端任务管理 UI**（复用 ruoyi 自带 sys_job admin 页）— CLAUDE.md §10 不重复造轮子
6. **本 ticket 不改 NEWS-003 publish API**（NEWS-003 的「立即发布」走 service.publish() 同步路径，本 ticket 仅加异步 due 扫描）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 用 ruoyi `sys_job`（Quartz）而非 Spring `@Scheduled` | ruoyi sys_job 提供 admin 页 + 执行日志 + 手动触发 + 暂停/启用 — 全部开箱即用，零代码 |
| D2 | cron 表达式每分钟（`0 * * * * ?`）| 业务对发布精度要求分级（甲方设的是分钟级时间），每分钟扫描足够 |
| D3 | 单批 100 + 总批 5 | 平衡：单批 100 一次 UPDATE 性能 OK / 总批 5 防 cron 一次执行过久阻塞下分钟触发 |
| D4 | 不接 V1.0 告警渠道 | doc/10 §5 已裁定 V1.0 仅日志 + sys_job_log；V1.1 业务支付涉及钱才加钉钉告警 |
| D5 | publish_time = schedule_publish_time（不取 now）| 业务预期一致性 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | cron 触发时 schedule_publish_time 字段尚未在 D06 NEWS-001 DDL 落地（D07 NEWS-003 ALTER 才补） | §0 自检确认 NEWS-003 DDL 已先跑（Flyway 时间戳排序：NEWS-003 V202606041000 → NEWS-004 V202606041030） |
| R2 | 大量 due 同分钟触发（如运营误设 100 篇同时发布）→ cron 单次跑超 1 分钟 | 单批 100 + 总批 5 上限 + 单事务批量 UPDATE（不是逐条 update）→ 实测应 < 5s |
| R3 | 系统重启 24h+ 导致大量 due 积压 → misfire 后下次跑批量过大 | misfire DO_NOTHING + 单次上限 500 → 多次 cron 周期消化；接受这种边界场景下「积压发布会延迟若干分钟」|
| R4 | 时区问题（schedule_publish_time 用户在小程序看的是 GMT+8，cron 服务器若 UTC 会差 8 小时）| ruoyi 默认 `spring.jackson.time-zone=GMT+8` + MySQL `time_zone='+08:00'` — §0 自检确认 application.yml 配置 |
| R5 | 测试时等真实 2 分钟体验差 | 测试时可临时把 cron 改 `*/10 * * * * ?` 每 10 秒；testing-human 后改回 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
