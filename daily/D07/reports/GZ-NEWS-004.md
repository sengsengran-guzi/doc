# GZ-NEWS-004 完工报告 — 资讯定时发布 cron（SnailJob）

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A — 项目根非 git 仓库（`fatal: not a git repository`），文件系统直改 |
| 上游依赖 merge | ✅ NEWS-003 已落：`schedule_publish_time DATETIME(3)` + `idx_schedule` + status 含 `scheduled` + `STATUS_SCHEDULED` 常量 + `schedule(id, due)` 流转（draft→scheduled，校验 >now） |
| 关键表/字段存在 | ✅ `GzNewsArticle` entity 字段 `schedulePublishTime`/`publishTime`/`status`（LocalDateTime）已就绪；mapper 注解式 `@Update` 风格确认 |
| 编译 + 单测 | ✅ `mvn test -pl ruoyi-gz-news`：48 passed / BUILD SUCCESS |
| ADR 已读 | 本 ticket 无关联 ADR（任务卡「关联 ADR: —」）；调度框架决策已由 GZ-BEAN-009 在 doc/10 §3 裁定，复用 |
| **AC1 仓库无 sys_job 确认** | ✅ MySQL 基线 SQL（`ry_vue_5.X.sql`/`ry_job.sql`/`ry_workflow.sql`）`grep sys_job ✗`；调度走 SnailJob `sj_*`（`ry_job.sql` 含 `sj_job`）。本 ticket **无 Flyway DDL** |
| 时区（R4） | ruoyi 默认 `spring.jackson.time-zone=GMT+8`；`now()` 由 MySQL 容器时区 Asia/Shanghai 求值，与 `schedule_publish_time`（admin 写入同时区）对齐 |

### 关键自检发现

1. **批量 UPDATE 口径以任务卡为准**（非 NEWS-003 报告 line 105 的「逐条 publish(id)」建议）：任务卡明确要求单事务批量 UPDATE 避免 N 次事务（R2 性能保护）。故新建 mapper `batchPublishScheduled`（单条 `UPDATE ... WHERE id IN (...)`），**不**循环调 `publish(id)`。
2. **`del_flag` 用 `'0'`/`'2'`**（@TableLogic），mapper 注解式自定义 SQL 沿用现有 `incrementReadCount` 约定显式写 `del_flag='0'`；`tenant_id` 由 `TenantLineInnerInterceptor` 对注解 SQL 自动 append（V1.0 单租户 '1001'）。
3. **publish_time = schedule_publish_time**（列对列赋值，强约束 #3），非 `now()` —— mapper `SET publish_time = schedule_publish_time`。

## 实现摘要

git diff --stat（手工对账，5 文件）：
```
ruoyi-gz-news/pom.xml                                       +6   （加 ruoyi-common-job 依赖）
.../news/mapper/GzNewsArticleMapper.java                    +44  （selectDueScheduledIds + batchPublishScheduled）
.../news/service/IGzNewsArticleService.java                 +28  （publishDueArticles 接口 + javadoc）
.../news/service/impl/GzNewsArticleServiceImpl.java         +58  （publishDueArticles 实现 + 2 常量 + batchPublishOneRound）
.../news/job/GzNewsScheduledPublishJob.java                 +63  （SnailJob 执行器壳，新文件）
.../news/service/impl/GzNewsArticleServiceImplTest.java     +75  （5 个 cron 单测）
```

新增关键产物：
- **`job/GzNewsScheduledPublishJob.java`**（新）— SnailJob `@JobExecutor(name="gzNewsScheduledPublishTask")` 触发壳，方法 `jobExecute(JobArgs)` 返 `ExecuteResult`，对齐 `GzBeanNoShowMarkJob` 样板；try-catch → `SnailJobLog.REMOTE.error` + `ExecuteResult.failure`
- **`mapper.selectDueScheduledIds(int limit)`**（新）— `@Select` 投影 id，`status='scheduled' AND schedule_publish_time<=now() AND del_flag='0' ORDER BY schedule_publish_time ASC LIMIT #{limit}`（FIFO 消化积压）
- **`mapper.batchPublishScheduled(List<Long> ids)`**（新）— `@Update <script>` 单条批量，`SET status='published', publish_time=schedule_publish_time, update_time=now()`，WHERE 二次校验 `status='scheduled' AND schedule_publish_time<=now()`（幂等 + 并发安全）
- **`service.publishDueArticles(int batchSize)`**（新）— 循环最多 5 批，单批截断 ≤100；首批空 / 不足 limit 提前退出；累计返回发布数；异常向上抛由 job 壳处理

## AI 自测（Tier 1A）

### 编译 + 单测（模块内，未跑 -am 避免与并行 ADMIN-003 冲突 gz-common）
```
[INFO] Tests run: 27, Failures: 0, Errors: 0, Skipped: 0 -- GzNewsArticleServiceImplTest（22 原有 + 5 新 cron）
[INFO] Tests run: 6,  Failures: 0, Errors: 0, Skipped: 0 -- NewsHtmlSanitizerTest
[INFO] Tests run: 15, Failures: 0, Errors: 0, Skipped: 0 -- HtmlSanitizerTest
[INFO] Results: Tests run: 48, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

5 个新 cron 单测覆盖（AC5 ≥3）：
- `publishDueArticles_happy3` — 3 篇 due → 批量 UPDATE 调 1 次 + 返回 3 + **never updateById**（证不逐条流转）+ 首批<limit 不续扫
- `publishDueArticles_empty` — 扫描空 → never batchPublishScheduled，返回 0
- `publishDueArticles_multiRound` — 首批满 100 续扫 / 次批 2 篇停 → 累计 102，扫描 2 次
- `publishDueArticles_maxRoundsCap` — 持续满批 → 5 批后退出（积压保护，封顶 500，不无限循环）
- `publishDueArticles_invalidBatchSize` — batchSize 0/-1 → ServiceException + never 触达 mapper（不静默）

### cron 行为 raw 日志（单测运行时 service log，证批次逻辑）
```
[gz-news-cron] publish-due round=1 scanned=3 published=3
[gz-news-cron] publish-due done totalPublished=3
---
[gz-news-cron] publish-due round=1 scanned=100 published=100
[gz-news-cron] publish-due round=2 scanned=2 published=2
[gz-news-cron] publish-due done totalPublished=102
---
[gz-news-cron] publish-due round=1..5 scanned=100 published=100  (×5)
[gz-news-cron] publish-due done totalPublished=500   ← 5 批封顶，未越界
```

### pom 依赖确认
```
$ grep -nA1 ruoyi-common-job ruoyi-gz-news/pom.xml
            <artifactId>ruoyi-common-job</artifactId>
        </dependency>
```
✅ 已加（对齐 gz-bean，groupId org.dromara 继承）。

## SnailJob 控制台注册参数（AC4，手工在 admin「定时任务」菜单注册，非 Flyway）

| 项 | 值 |
|---|---|
| 任务名称 | `GZ-NEWS-PUBLISH-DUE` |
| 执行器路由（executor_info） | `gzNewsScheduledPublishTask`（= 本类 `@JobExecutor` name） |
| 触发类型 / CRON | CRON，`0 * * * * ?`（每分钟第 0 秒，容器时区 Asia/Shanghai） |
| 阻塞策略 | 丢弃（DISCARD）— 上次未跑完不叠加，等价旧 Quartz misfire DO_NOTHING + 禁并发 |
| 组 | `ruoyi_group` |

> **无 Flyway DDL**：本 ticket 不建表、不 INSERT 任何调度表。schedule 字段 + `scheduled` 枚举由 NEWS-001/003 已落；job 注册纯控制台手工配。**绝不 INSERT sys_job**（仓库无该表，会启动 hard-fail）。

## 风险提示 / 已知 issue

- **R1 集成测试（AC6）未跑端到端**：后端 dev 未启动（避免与并行 ADMIN-003 抢 gz-common 重建 + restart），单条批量 UPDATE 的真实 SQL（`<script>` foreach IN + 列对列 publish_time=schedule_publish_time + 拦截器 append tenant）未在真 MySQL 执行验证。留主线程统一 `mvn install -am` + restart 后，或 Kevin 在 SnailJob 控制台「执行一次」`GZ-NEWS-PUBLISH-DUE` 验证（建一篇 due+2min 文章 → 触发 → `SELECT status, publish_time` = published + due 时间）。
- **R2 SnailJob 控制台注册需手工**：执行器壳 + 路由名已就绪，但 `sj_job` 记录需在控制台手工建（参数见上表）。未注册前 cron 不触发（与 BEAN-009 同模式，testing-human 时一并注册）。
- **R3 `batchPublishOneRound` self-invocation 事务语义**：`publishDueArticles` 同类调 `batchPublishOneRound` 不走 Spring 代理，`@Transactional` 实际不生效；但每批是**单条** UPDATE，底层自动提交天然原子，符合「单批单事务」语义。注解为边界声明 + 未来拆批内多语句的占位（已在 javadoc 注明，非缺陷）。
- **R4 时区**：依赖 MySQL 容器 `time_zone=+08:00` 与 admin 写入 `schedule_publish_time` 同时区。dev/prod 部署确认容器 TZ=Asia/Shanghai（ruoyi docker-compose 默认已配）。

## 对下游 ticket 的提示

- 本 ticket 是 GZ-NEWS 域 V1.0 收官，无后续 gz-news ticket 依赖。
- SnailJob 执行器注册清单（控制台）此波累计：`gzBeanNoShowMarkTask`（BEAN-009）+ `gzNewsScheduledPublishTask`（本 ticket）。部署 staging/prod 时一并在 SnailJob 控制台注册两个 cron。

## Tier 2 可达性

- 本 ticket **纯后端**（Tech 段无 `miniapp/` 路径，AC 无微信原生能力，admin 复用 SnailJob 控制台无新 menu）→ 按 CLAUDE.md §8.2 例外：**仅 Tier 1A，AI ✅ 即终态 close，无 mp 人验、无临时入口需求**。

## §AI 测试段（kevin-qa 完工后追加）

> 注：本环境 Agent 工具受嵌套限制，未 spawn kevin-qa（任务卡明示「不要尝试 spawn kevin-qa」）。
> 本 ticket 纯后端，Tier 1B 集成测试（SnailJob 控制台触发 → DB 状态流转）留主线程统一 `mvn install -am` + restart 后由 Kevin / kevin-qa 跑（见 R1）。
