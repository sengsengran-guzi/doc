# GZ-NEWS-003 完工报告 — 后台资讯 CMS（富文本编辑）

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A — 项目根非 git 仓库（`fatal: not a git repository`），文件系统直改 |
| 上游依赖 merge | ✅ NEWS-001/002（D06）已落：entity / mapper / service(mp) / DDL `V202606031200` + seed；SYS-005 文件上传 `/system/gz/file/upload` 存在 |
| 关键表存在 | ✅ `gz_news_article` 在 dev DB 已建（NEWS-001），且 AC1 全部 CMS 字段已落（见下） |
| 编译通过 | ✅ `mvn compile -pl ruoyi-gz-news` 干净 |
| 单测通过 | ✅ 43 passed（22 service + 6 NewsHtmlSanitizer + 15 HtmlSanitizer） |
| ADR 已读 | 0001 已读；本 ticket 编辑器复用 quill 无选型分歧，**不写 ADR-0002**（理由见下） |
| jsoup 可用 | ✅ 已拉到 `.m2`（1.17.2，dev 在线） |
| 权威蓝图 | ✅ doc/10 §5 状态机/N1-N12/E1-E4 + 附录 A.4/A.11 + doc/11 §5.1（NEWS-001 DDL 注释已引）已读 |

### 关键自检发现（影响实现范围）

1. **AC1 字段已全部落地**：NEWS-001 建表（`V202606031200`）已含 `schedule_publish_time DATETIME(3)` + `idx_schedule` / `content_html MEDIUMTEXT NOT NULL` / `video_urls VARCHAR(1024)` / `is_pinned TINYINT DEFAULT 0` / `sort_no INT DEFAULT 0` / status 4 态（含 `scheduled`）。→ 本 ticket AC1 DDL = **幂等空操作**（dev 实测 0 列新增），真实工作量在 admin Controller/Service/页面 + XSS 清洗 + menu。
2. **编辑器已集成**：plus-ui 已带 `@vueup/vue-quill` + `quill` + `src/components/Editor/index.vue`（ruoyi 自带）。按 CLAUDE.md §6 #8（优先用已有、不引新依赖）+ ticket D1 → **复用 quill，不引 wangEditor，不写 ADR**。
3. **XSS 双层**：保留 NEWS-001 的 `NewsHtmlSanitizer`（hutool denylist，mp 输出兜底，**不动**）；新建 `HtmlSanitizer`（jsoup `Safelist.relaxed()` allowlist，admin 写入清洗，落库前强制）。

## 实现摘要

**后端 `ruoyi-modules/ruoyi-gz-news/`**
- `pom.xml` — 加 `org.jsoup:jsoup:1.17.2`
- `controller/GzNewsArticleController.java`（新）— admin `/system/gz/news/article`，list/get/add/edit/delete + publish/schedule/offline，全 `@SaCheckPermission` + `@Log`
- `service/IGzNewsArticleService.java`（扩）— 加 8 个 admin CMS 方法
- `service/impl/GzNewsArticleServiceImpl.java`（扩）— admin CMS + 状态机流转 + article_no 生成 + 分类/视频校验；注入 `HtmlSanitizer`
- `service/internal/HtmlSanitizer.java`（新）— jsoup 白名单写入清洗 + 外链 nofollow noopener + img[data-file-id] 放行
- `domain/bo/GzNewsArticleBo.java`（新）+ `domain/bo/GzNewsArticleQueryBo.java`（新）+ `domain/vo/GzNewsArticleAdminVO.java`（新）
- 测试：`HtmlSanitizerTest.java`（新，15 个含 10 参数化 XSS）+ `GzNewsArticleServiceImplTest.java`（扩，+10 admin 方法）

**DDL `ruoyi-admin/.../db/migration/`**
- `V202606041000__GZ-NEWS-003-alter-gz_news_article-cms-fields.sql`（幂等补缺存储过程，dev 实测 no-op）
- `V202606041001__GZ-NEWS-003-menu.sql`（menu 8000-8007 + owner=100 全授 / staff=101 授 7 不含删除）

**Admin `plus-ui/`**
- `src/api/gz-news/article.ts`（新）— CRUD + publish/schedule/offline，id 全 string
- `src/views/gz-news/article/index.vue`（新）— BizTable 列表 + 富文本编辑弹窗 + 状态流转 + 定时发布弹窗 + 字数/阅读时长统计 + 置顶行高亮
- `src/views/gz-news/article/components/NewsEditor.vue`（新）— quill 包装，图片走 SYS-005 `usageType=news_inline` + 插入 `data-file-id`
- `src/lang/zh_CN.ts` / `en_US.ts` — 加 `gzNewsArticle` i18n block

## AI 自测（Tier 1A）

### 编译 + 单测（mvn，模块内，未跑 -am 避免与并行 PAY-001 冲突 gz-common）
```
[INFO] Running org.dromara.gz.news.service.impl.GzNewsArticleServiceImplTest
[gz-news-admin] INSERT id=10 articleNo=ART-20260531-000001 title=新品入荷预告 status=draft
[gz-news-admin] PUBLISH id=5 (draft → published)
[gz-news-admin] PUBLISH id=6 (offline → published)
[gz-news-admin] SCHEDULE id=7 due=2026-06-01T00:54:15.103702
[gz-news-admin] OFFLINE id=9
[INFO] Tests run: 22, Failures: 0, Errors: 0, Skipped: 0 -- GzNewsArticleServiceImplTest
[INFO] Tests run: 6,  Failures: 0, Errors: 0, Skipped: 0 -- NewsHtmlSanitizerTest
[INFO] Tests run: 15, Failures: 0, Errors: 0, Skipped: 0 -- HtmlSanitizerTest（10 参数化 XSS payload）
[INFO] Results: Tests run: 43, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
XSS 单测覆盖（AC4 ≥5）：`<script>` / `<img onerror>` / `<a href=javascript:>` / `<iframe>` / `<svg onload>` / `<object>` / `<embed>` / `<form>` / `<body onload>` / `<a href=vbscript:>`（共 10）。

### DDL 验证（dev MySQL ry-vue 实跑）
```
=== AC1 ALTER 迁移（幂等 no-op 期望）===
cols before = 23 → 运行 V202606041000 (exit 0) → cols after = 23  ✅ 无新增（NEWS-001 已落齐）

=== menu 迁移 V202606041001 (exit 0) ===
menu_id  menu_name  parent_id  menu_type  perms
8000     资讯管理     5000       M
8001     文章列表     8000       C          gz:news:article:list
8002     文章查询     8001       F          gz:news:article:list
8003     文章新建     8001       F          gz:news:article:add
8004     文章编辑     8001       F          gz:news:article:edit
8005     文章删除     8001       F          gz:news:article:delete
8006     文章发布     8001       F          gz:news:article:publish
8007     文章下架     8001       F          gz:news:article:offline
role_menu: 100(owner)=8  101(staff)=7（不含 8005 删除）  ✅
再次运行（幂等）→ 仍 8 menus / 100=8 / 101=7，无重复  ✅
```

### Admin 前端类型检查（vue-tsc --noEmit）
```bash
node_modules/.bin/vue-tsc --noEmit -p tsconfig.json | grep -iE "gz-news|NewsEditor|article"
# 输出：空 — 本 ticket 3 个新文件（api/article.ts / views/article/index.vue / NewsEditor.vue）零类型错误
# 仓库基线另有 72 个预存 TS 噪音（DictTag/layout/store/oper-log 等，与本 ticket 无关）
```

### Redis 缓存
```
docker exec sensenran-dev-redis redis-cli ... FLUSHDB → OK
（清菜单/字典缓存；sa-token 会话需重登）
```

## 风险提示 / 已知 issue

- **R1 编辑器选型**：复用 plus-ui 现成 quill，未引 wangEditor → 无新依赖风险。quill 工具栏对齐 AC3（标题/加粗/斜体/列表/引用/链接/图片/视频/对齐/清除格式）；quill 无内置「分割线」blot，用「清除格式」覆盖，正文分隔靠空行/标题。
- **R2 data-file-id 保留链路**：编辑器插入 `<img data-file-id>` → 后端 `HtmlSanitizer` 已 `addAttributes("img","data-file-id")` 放行（单测 `keepsImgDataFileId` 验证）。但 quill 对自定义 img 属性的回填渲染依赖浏览器，已在 `handleUploadSuccess` 用 `setAttribute` 补 + 同步 innerHTML，**需 Kevin/主线程在浏览器实操确认 data-file-id 落库**（vue-tsc/单测无法覆盖 DOM 行为）。
- **R3 外链白名单占位**：`TRUSTED_HOST_SUFFIXES` 含 `guziyuzhou.com`（甲方域占位）+ 微信生态域。甲方正式域确定后需补此常量（doc/10 §5.E1）。
- **R4 手动 DDL 未入 Flyway history**：我手动在 dev 跑了 2 个迁移验证（未走 Flyway）→ `flyway_schema_history` 未记录 → 下次 app 启动 Flyway 会再跑一次。两文件均幂等 → 安全。
- **R5 live API curl / admin 浏览器实操未跑**：后端 dev 未启动（避免与并行 PAY-001 抢 gz-common 重建 + restart）→ Controller 路由 / `@SaCheckPermission` / 富文本上传链路的端到端验证留主线程收尾 gate（`mvn install -am` + restart 后）或 Kevin Tier 1B/2。

## 对下游 NEWS-004 的提示（字段就绪确认）

- ✅ **`schedule_publish_time DATETIME(3) NULL` 已就绪**（NEWS-001 已落，AC1 已对账确认）+ `idx_schedule (tenant_id, schedule_publish_time)` 索引已就绪。
- ✅ **status 枚举已扩展含 `scheduled`**（NEWS-001 DDL 已含，service `STATUS_SCHEDULED` 常量 + 流转方法 `schedule()` 已落）。
- ✅ **`schedule(id, schedulePublishTime)` 流转已落地**：draft → scheduled，校验 `> now`（强约束 #6）。NEWS-004 cron 实现 `scheduled + schedule_publish_time <= now → published` 时，可直接复用 `IGzNewsArticleService.publish(id)`（已实现 scheduled → published 流转：publish() 允许 draft/offline/scheduled 入态，发布后清 schedule_publish_time）。
- ⚠️ NEWS-004 cron executor 用 SnailJob（见 memory：调度是 SnailJob 非 Quartz；业务模块写 executor 要加 `ruoyi-common-job` 依赖）。
- ⚠️ NEWS-004 cron 流转建议**幂等**（doc/10 §5.E4：任务幂等可重跑）：扫 scheduled 时按 id 逐条调 publish()，publish() 内已校验状态，重复触发安全。

## Tier 2 可达性

- 本 ticket **纯 admin**（Tech 段无 `miniapp/` 路径，AC 无微信原生能力）→ 按 CLAUDE.md §8.2 例外判定：**仅 Tier 1A + 1B，AI ✅ 即终态 close，无 mp 人验、无临时入口需求**。
- admin 入口：登录后台 → 谷子业务 → 资讯管理 → 文章列表（menu 8000→8001 已落，owner/staff 可见）。

## §AI 测试段（kevin-qa 完工后追加）

> 注：本环境 Agent 工具不可用（subagent 嵌套限制），未 spawn kevin-qa。
> Tier 1B（admin Playwright E2E：登录 → 资讯管理 → 新建/编辑/发布/定时/下架/删除 + XSS payload 粘贴 + 图片上传 data-file-id 落库 + perm 权限）留主线程收尾 gate 统一 `mvn install -am` + restart 后，由 kevin-qa 或 Kevin 跑。
> （占位，待追写）
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
# GZ-ADMIN-003 完工报告 — 基础数据看板（非交易指标）

> 后端 + DDL + SnailJob 执行器 + 单测由 kevin-coder 实现；前端看板页 / API / i18n + 本报告由主线程收尾（coder 子 agent 在 plus-ui 前端阶段被中断）。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A — 项目根非 git 仓库，文件系统直改 |
| 上游依赖 merge | ✅ 数据源齐：`gz_user`（SYS-003）/ `gz_bean_booking_log`（BEAN-004）/ `gz_news_article`（NEWS-001）均已落地 |
| 关键表/字段存在 | ✅ `gz_bean_booking_log` 实有 `from_status`(NULL首插)/`to_status`/`operator_type`(user/admin/system)/`tenant_id`/`create_time`/`del_flag CHAR(1)`；`gz_user` 有 `del_flag`（0=正常/2=删）—— 看板 mapper SQL 全字段命中，无运行期缺列风险 |
| 编译 + 单测 | ✅ `mvn test -pl ruoyi-gz-common`：`GzDashboardServiceImplTest` 4 passed；集成 `-am` 后 gz-common 全模块 36 passed / BUILD SUCCESS |
| ADR 已读 | 本 ticket 无关联 ADR；调度框架决策复用 GZ-BEAN-009（SnailJob） |
| **仓库无 sys_job 确认** | ✅ `grep sys_job script/sql ✗`；调度走 SnailJob `sj_*`。DDL **不含任何 sys_job INSERT**（仓库无该表，INSERT 会启动 hard-fail） |

### 关键自检发现

1. **累计/今日预约用 `gz_bean_booking_log`**（非 booking 表）：booking 表 cancelled 物理删（doc/11 §3.4），log 表永不删 → 用 `from_status IS NULL AND to_status='pending' AND operator_type='user'` 仅数用户提交首条 pending 日志，排除后续 admin/system 流转日志膨胀（ticket R2）。字段已与真实 DDL 对账一致。
2. **看板放 `gz-common`**（决策 D2）：跨域聚合（user+bean+news），反向依赖单业务模块会循环依赖。mapper 直接 `@Select` 物理表名，不依赖各模块 entity。
3. **cron 上下文租户**：service 用 `TenantHelper.ignore(...)` 包裹 + SQL 显式传 `tenant_id='1001'`（V1.0），不依赖多租户拦截器对 raw 跨表 SQL 的注入行为（与 BEAN-009 / PAY-001 cron 同思路）。
4. **wide-long 快照表**（决策 D1）：每 metric 一行，V1.1 加 metric 不需 ALTER；`UNIQUE(tenant_id, snapshot_time, metric_key)` + `IDX(tenant_id, metric_key, snapshot_time DESC)` 查最新。

## 实现摘要

新增产物（后端 `ruoyi-gz-common/.../dashboard/` 包 — 与 PAY-001 的 `pay/` 包平级隔离，零文件冲突）：
```
controller/GzDashboardController.java            admin /system/gz/dashboard（latest/trend/refresh）
service/IGzDashboardService.java + impl          takeSnapshot / getLatest / getTrend（核心可测逻辑）
job/GzDashboardSnapshotJob.java                  SnailJob @JobExecutor 触发壳（对齐 GzBeanNoShowMarkJob）
mapper/GzDashboardMetricMapper.java              5 个 COUNT/SUM 跨表只读聚合
mapper/GzDashboardSnapshotMapper.java            快照写入 / 查最新 / 查趋势
domain/entity/GzDashboardSnapshot.java           快照实体
domain/vo/GzDashboardLatestVO.java               latest 返回（snapshotTime + metrics[{metricKey,title,value}]）
domain/vo/GzDashboardTrendVO.java                trend 返回
enums/DashboardMetric.java                       5 指标枚举（metricKey + title）
src/test/.../GzDashboardServiceImplTest.java     单测 4
```
DDL（1 文件）：`V202606041100__GZ-ADMIN-003-create-gz_dashboard_snapshot.sql` — 建 `gz_dashboard_snapshot` 表 + INSERT `sys_menu`(300 数据看板/301 立即刷新) + `sys_role_menu`(owner 100→view+refresh / staff 101→view)。**无 sys_job**。

前端（主线程收尾）：
```
plus-ui/src/api/gz-common/dashboard.ts           getDashboardLatest / getDashboardTrend / refreshDashboard（契约对齐 controller + VO）
plus-ui/src/views/dashboard/index.vue            5 张 el-card KPI（千分位）+「更新于 X」+「立即刷新」（loading + 前端 5s disable 对齐后端 @RateLimiter）
plus-ui/src/lang/zh_CN.ts / en_US.ts             gzDashboard i18n block（5 指标标题 + 卡片文案，默认 zh-CN 不混 emoji）
```
路由：menu component `dashboard/index` → `views/dashboard/index.vue`，路由 `/dashboard`（不动 ruoyi 默认 `/index`）。

## AI 自测（Tier 1A）+ 主线程集成 gate

### gz-common 单测（dashboard 4 + 集成全模块 36）
```
[INFO] Tests run: 4, Failures: 0, Errors: 0, Skipped: 0 -- org.dromara.gz.common.dashboard.service.GzDashboardServiceImplTest
... 集成 mvn install -am 后 gz-common 全模块：
[INFO] dashboard 4 + pay 6 + gzUser 8 + gzFile 9 + WxLogin 4 + WxMockLogin 5 = 36 passed
[INFO] BUILD SUCCESS  ·  ruoyi-gz-common-5.6.1.jar installed @ 07:35
```
4 单测覆盖（AC7 ≥2）：happy（mock 5 COUNT → batch insert 5 行 / snapshot_time 同批一致）+ 异常处理（mock mapper 抛 → takeSnapshot catch 不外抛，返回 success=false，cron 不阻塞 / refresh 不抛 500）+ getLatest 空快照（snapshotTime=null + 空 metrics）+ getLatest 正常聚合。

### booking_log 字段对账（防 mock 单测掩盖运行期缺列）
```
gz_bean_booking_log:  from_status VARCHAR(16) NULL / to_status VARCHAR(16) NOT NULL
                      operator_type VARCHAR(16) NOT NULL / tenant_id / create_time DATETIME
                      del_flag CHAR(1) NOT NULL DEFAULT '0'        ← mapper del_flag='0' 命中 ✅
gz_user:              del_flag CHAR(1) NOT NULL DEFAULT '0'        ← mapper del_flag='0' 命中 ✅
```

### 前端集成（主线程）
```
plus-ui build:prod        ✅ dist 产出（vue-quill / dashboard chunk 均在）
vue-tsc 我的 dashboard 文件   0 新增 TS 错（总错数 72 = D07 前 baseline，无新增）
```

## SnailJob 控制台注册参数（手工在 admin「定时任务」菜单注册，非 Flyway）

| 项 | 值 |
|---|---|
| 任务名称 | `GZ-DASHBOARD-SNAPSHOT` |
| 执行器路由（executor_info） | `gzDashboardSnapshotTask`（= `@JobExecutor` name） |
| 触发类型 / CRON | CRON，`0 0/5 * * * ?`（每 5 分钟整点，容器时区 Asia/Shanghai） |
| 阻塞策略 | 丢弃（DISCARD） |
| 组 | `ruoyi_group` |

> 注册前 cron 不触发 → snapshot 表空 → 前端显示「暂无快照数据」（已做空态兜底）。首次注册后「执行一次」即可写第一批快照。

## 风险提示 / 已知 issue

- **R1 端到端未跑**：后端 dev 未启动，refresh API → service.takeSnapshot → 5 个跨表 SQL 真实执行 + snapshot 落库未在真 MySQL 验证（单测 mock mapper）。留 Kevin V1.0 端到端回归（README §B 第 6 项：刷新 → 看到本次新增用户1/预约1/阅读1）或 SnailJob 控制台「执行一次」后查 `gz_dashboard_snapshot`。
- **R2 SnailJob 控制台注册需手工**（同 BEAN-009 / NEWS-004）：此波累计待注册 cron = `gzBeanNoShowMarkTask` / `gzNewsScheduledPublishTask` / `gzPayExpireOrderTask` / `gzDashboardSnapshotTask`。
- **R3 趋势 API 留接口不展示**（决策 D4）：`GET /trend` 已实现，前端 V1.0 不渲染图表（echarts 选型推 V1.1）。
- **R4 doc/11 缺 dashboard_snapshot 章节**：本 ticket DDL 落地后由周末复盘补 doc/11（CLAUDE.md §9.5 第 1 优先级）。

## Tier 2 可达性

- 本 ticket **纯 admin**（Tech 段无 `miniapp/` 路径，AC 无微信原生能力）→ 按 CLAUDE.md §8.2 例外：仅 Tier 1A + 1B，AI ✅ 即终态 close，**无 mp 人验、无临时入口**。
- admin 可达：登录 admin → 菜单「数据看板」(menu 300) → `/dashboard` 看 5 KPI 卡 + 立即刷新。

## §AI 测试段（Tier 1B）

> 本环境 Agent 受嵌套限制未独立 spawn kevin-qa。Tier 1B admin Playwright E2E（登录 → 看板页 → 5 卡渲染 → 立即刷新 loading + 5s 防抖 + 数值更新 + perm gz:dashboard:view/refresh）需后端起 + plus-ui dev 后跑，留主线程收尾 gate / Kevin V1.0 端到端一并覆盖。后端集成 + 前端 build 已绿（见上）。
# GZ-PAY-001 完工报告 — 微信支付 V3 通道 HelloWorld

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git 状态 | N/A（项目无 git 仓库，`git rev-parse` 全层级 not a git repository）— 不阻塞 |
| 上游依赖（GZ-SYS-001 云服务 + 商户号申请） | ✅ SYS-001 已 merge；商户号 5/29 启动申请未下证 → 确定走 mock 降级（AC 9 / ADR-0003） |
| 关键类/表存在 | ✅ gz-common 现有结构已读（GzUser/wechat/job/LogRetentionJob）；gz_pay_* 三表本 ticket 新建 |
| 权威蓝图引用完整性 | ✅ 任务卡引 doc/10 §2 + doc/11 §4.1/4.2/4.3 + doc/12 §MP-PAY-RESULT，均已 Read 并摘录关键约束 |
| 编译健康（gz-common 基线） | ✅ `mvn compile -pl ruoyi-modules/ruoyi-gz-common` 通过（52 个 pay 类 + SDK 真实实现一并编译） |
| ADR 已读/已写 | ✅ 新建 doc/_adr/0003-wechat-pay-channel-mock-degradation.md |
| SnailJob（非 Quartz）| ✅ 读 GzBeanNoShowMarkJob 样板；DDL 无 sys_job INSERT；job 走控制台注册 |
| SDK 依赖冲突 | ✅ `mvn dependency:tree` 确认仓库内无其他 wxpay 包 → wechatpay-java:0.2.17 无冲突 |

**权威蓝图关键约束摘录**：
- doc/11 §4.2：`out_trade_no` 格式 `<域>-yyyyMMdd-6位序号`（test 单 `TEST-` 前缀）；`transaction_id` UNIQUE WHERE NOT NULL（MySQL 唯一索引多 NULL 并存等价此语义）；`version` 乐观锁；状态 created/pending/paid/timeout/closed/failed（V1.0 前 6 态）。
- doc/10 §2：N1 admin 触发 → N2 统一下单 → N3 prepay_id → N6 回调 → N7 验签+幂等 → N8 入流水；E2 验签失败拒收+告警；E3 重复回调幂等；E5 5min 超时 timeout。
- 合同 §2.1 V1.0 仅通道调通不接业务；§2.3 商户号挂甲方主体（Kevin 核对 STOP 闸口）。

## 实现摘要

**改动文件**（新建 31 后端 java + 1 DDL + 4 admin + 3 mp + 1 ADR；改 6 配置/i18n/入口）：

- **后端（ruoyi-gz-common，独占）** 31 个 java：
  - entity ×3 `GzPayChannel/GzPayTransaction/GzPayCallbackLog`；VO ×4；BO ×2；enums ×2（PayStatus/PayBusinessType）
  - mapper ×3（GzPayTransactionMapper 含乐观锁 markPaid / markTimeout / selectExpiredPendingIds / selectMaxDailySeq）
  - service：IGzPayTransactionService + impl（统一下单 + 回调验签幂等 + 超时关单）/ IGzPayChannelService + impl（只读脱敏）
  - internal：IWechatPayClient 抽象 + MockWechatPayClient + WechatPayV3ClientImpl（官方 SDK 真实实现）+ PayOrderNoGenerator + WechatPayVerifyException
  - config：WechatPayProperties（profile 切换）
  - controller ×5：channel（admin 只读）/ transaction（admin 列表+详情+回调日志）/ test（admin 测试工具+mock 模拟回调）/ applet/GzPayMpController（mp 轮询，@SaCheckLogin）/ external/WechatPayNotifyController（**/api/pay/v3/notify，@SaIgnore，验签失败 401+审计**）
  - job：GzPayExpireOrderJob（SnailJob @JobExecutor，触发壳）
  - test：GzPayTransactionServiceImplTest（5 AC + 1 = 6 方法）
- **DDL**：`V202606041200__GZ-PAY-001-...sql`（三表 + sys_menu 5100-5105 + INSERT wechat_pay_v3 默认行；**无 sys_job**）
- **admin（plus-ui/gz-pay）**：api/gz-pay/index.ts + channel/index.vue + transaction/list.vue（含详情 dialog + 回调日志）+ test/index.vue + i18n zh+en `gzPay` 段
- **mp（miniapp）**：api/gz-pay.ts + pages/pay/test.vue + pages/pay/result.vue（三态 + 轮询 + 回流卡片）+ pages/index/index.vue 临时入口（Tier2-entry-temp）
- **配置**：pom.xml（+ruoyi-common-job + wechatpay-java:0.2.17）/ application-dev.yml（gz.pay.client-mode=mock）/ application-prod.yml（env var 占位符 + client-mode=${...:mock}）

## AI 自测（Tier 1A）

### 1. 后端编译 + 单测（mock 全链路，AC 10）

```
[INFO] Running org.dromara.gz.common.pay.service.GzPayTransactionServiceImplTest
[gz-pay] 超时关单完成：扫描 2 / 关单 1 / 跳过 1
[gz-pay] 重复回调（已 paid）out_trade_no=TEST-20260604-000001
[gz-pay] 乐观锁冲突视为重复回调 out_trade_no=TEST-20260604-000001
[gz-pay] 回调处理成功 out_trade_no=TEST-20260604-000001 → paid transaction_id=wx_txn_1
[gz-pay] 测试单创建 out_trade_no=TEST-20260604-000001 amount=1 prepay_id=mock_prepay_TEST-20260604-000001
[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0 -- in GzPayTransactionServiceImplTest

全模块（含 login/user/file 既有测试，无回归）：
[INFO] Tests run: 32, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

5 个 AC 测试方法（+1 happy path 拆分 = 6）全绿：happy path 下单→pending / happy path 回调→paid / 重复回调 duplicated / 验签失败透传异常 / 乐观锁冲突 affected=0 视重复 / 超时关单扫描统计。

### 2. SDK 依赖树（AC 3，无冲突）

```
+- com.github.wechatpay-apiv3:wechatpay-java:jar:0.2.17:compile
|  +- com.github.wechatpay-apiv3:wechatpay-java-core:jar:0.2.17:compile
|  +- com.google.code.gson:gson:jar:2.13.2:runtime
|  +- org.bouncycastle:bcpkix-jdk18on:jar:1.83:compile
|  |  \- org.bouncycastle:bcprov-jdk18on:jar:1.83:compile
|  +- com.squareup.okhttp3:okhttp:jar:4.10.0:runtime
|  \- com.fasterxml.jackson.core:jackson-databind:jar:2.21.2:compile
```
仓库内 grep 全 pom 无任何 wxpay 包 → 无版本冲突。gson/okhttp/bouncycastle 仅 SDK 自用，ruoyi 无引用。

### 3. admin（plus-ui）gz-pay typecheck

```
$ npx vue-tsc --noEmit -p tsconfig.json | grep -E "views/gz-pay|api/gz-pay" | wc -l
0
```
（其余 ruoyi base 既有 TS 噪声 DictTag/Process/layout/store 与本 ticket 无关，未触碰）

### 4. mp（miniapp）build + typecheck

```
$ pnpm type-check | grep -E "pages/pay|api/gz-pay" | wc -l
0
$ pnpm build:mp-weixin   # exit 0
$ ls dist/build/mp-weixin/pages/pay/
result.wxml  result.wxss  result.js  test.wxml  test.wxss  test.js   # 06:57 fresh
$ grep -o "pages/pay/[a-z]*" dist/build/mp-weixin/app.json | sort -u
pages/pay/result
pages/pay/test                # definePage/<route> 宏自动注册
```

### 5. 回调验签压测（AC 11）— 离线说明

后端 dev 未在本机起（与 NEWS-003 并行，避免 install -am 撞 ~/.m2）。验签失败 → 401 + callback_log failed 的链路由 **单测「验签失败：parser throw → 透传异常」** + WechatPayNotifyController 代码路径覆盖（catch WechatPayVerifyException → writeFailedLog + ResponseEntity 401）。真实 curl 错误签名压测（期望 401 + callback_log process_status='failed' raw output）列入 **buffer 期真实通道补打**（需后端起 + 真实/mock notify endpoint）。

## SnailJob 控制台注册（AC 8，手工，无 sys_job DDL）

| 项 | 值 |
|---|---|
| 任务名称 | GZ-PAY-EXPIRE-ORDER |
| 执行器路由 executor_info | `gzPayExpireOrderTask`（= @JobExecutor name） |
| 触发类型 | CRON `0 0/5 * * * ?`（每 5 分钟，Asia/Shanghai） |
| 阻塞策略 | DISCARD（丢弃） |
| 组 | ruoyi_group |

核心逻辑在 `IGzPayTransactionService.expireTimeoutOrders()`（已单测覆盖），job 类仅触发壳。

## 风险提示 / 已知 issue

- **R1 商户号未下证（确定降级）**：走 mock + ADR-0003 记录补打时机，不阻塞 V1.0 收官。
- **WechatPayV3ClientImpl 已写未联调**：buffer 期 staging real profile 跑真实单可能暴露 SDK 5 参一致性细节（buildPayParams vs createJsapiOrder），届时调通，不影响 mock 单测。
- **回调多租户**：notify 无登录态 → TenantHelper.ignore 包裹，V1.0 单租户 '1001' 安全；多租户开放后需带 mch_id → tenant 映射。
- **待 Kevin 批量人验关注（mp 端）**：pay/test 发起测试单 → mock 模拟回调 → result 三态 + 回流卡片 happy path（临时入口从首页可达）。

## 对下游 ticket 的提示

- **ADMIN-003（Wave 2，串行在本 ticket 后，也动 gz-common）**：gz-common pom 已加好 `ruoyi-common-job`（你复用，无需再加）+ `wechatpay-java:0.2.17`。pom 留干净可用。
- **GZ-PAY-101（V1.1 业务支付接入）**：service 层 `createTransaction` 抽象已留（PayOrderNoGenerator 按 business_type 自动出前缀 PREORD/GACHA）；business_type=preorder/gacha 直接复用三表 + 验签 + 幂等 + 超时关单。**清理本 ticket 临时入口**：`pages/index/index.vue` 有 `TODO(Tier2-entry-temp): GZ-PAY-001, remove when GZ-PAY-101 merged` —— 实施时 grep `Tier2-entry-temp` 找到并清理（用业务支付真入口替换）。
- **buffer 期补打（pending，需 Kevin 介入）**：① 商户号下证当日 Kevin 核对主体（STOP 闸口，挂成都谷子宇宙贸易有限公司）；② 注入 env var + staging 切 real；③ 真实 0.01 元端到端单 + curl 验签压测 raw output 追加本 reports。详 ADR-0003 §2。

## §AI 测试段（kevin-qa Tier 1B）

**本 ticket 未在子 agent 内 spawn kevin-qa（嵌套限制，kevin-coder.md 已说明）。** Tier 1B 由主线程收尾 gate 统一调度：
- admin Playwright E2E：登录 owner → 支付管理菜单 → 通道配置（只读列表）/ 支付订单列表 / 测试工具页发起测试单 + 模拟回调 → 订单变 paid。
- 后端集成：notify endpoint 错误签名 → 401 + callback_log failed（需后端起，主线程 install -am 后跑）。
- mp vitest：pay/result 三态 + 轮询逻辑 unit（如需补 .test.ts）。
- mp 可达性：grep `pages/index/index.vue` 含 `Tier2-entry-temp: GZ-PAY-001` 临时入口 → Kevin 批量人验从首页可点到 pay/test ✅。

**close 口径**：Tier 1A 全 ✅（编译 / 6 单测 / 依赖树无冲突 / admin typecheck 0 / mp build+typecheck 0）。mp ticket → 进 progress.md 人验列待 Kevin 批量人验（happy path + 临时入口可达）。真实通道单 = buffer 期 pending（外部资质）。

---

# ⭐ V1.0 收官

**V1.0 30 ticket 全部闭环**（D01-D07）。本日 4 ticket（NEWS-003 资讯 CMS / NEWS-004 定时发布 cron / ADMIN-003 数据看板 / PAY-001 支付通道 HelloWorld）AI Tier 1A + 主线程集成 gate 全绿：后端 84 单测 BUILD SUCCESS、plus-ui build:prod 绿、miniapp build:mp-weixin 绿。

合同 §2.2 硬期限 **2026-06-15** —— V1.0 提前达成。6/05-6/15 buffer 期：staging 部署 / mp 视觉走查（C 日漫海报浓墨）/ 客户演示 / PAY-001 真实 0.01 元单补打（商户号到位后，ADR-0003）/ V1.0 端到端回归 + 批量人验。6/16 D08 起进 V1.1（27 ticket）。

**收官待办（非阻塞，部署/外部资质侧）**：
1. SnailJob 控制台注册 4 个 cron：gzBeanNoShowMarkTask / gzNewsScheduledPublishTask / gzDashboardSnapshotTask / gzPayExpireOrderTask
2. PAY-001 真实通道：商户号下证 → 核对主体 → 真单 + 验签压测
3. V1.0 端到端回归 + D05+D06+D07 mp 批量人验 → 全过后统一 git init + commit
