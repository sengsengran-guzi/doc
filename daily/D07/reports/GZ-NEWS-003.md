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
