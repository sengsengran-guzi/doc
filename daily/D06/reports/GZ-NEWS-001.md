# GZ-NEWS-001 完工报告 — mp 文章列表 + 详情 + 分类 + 首页接真数据

> 资讯 C 端 track 第 1 张卡。串行：本卡 ✅ → GZ-NEWS-002（分享）。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A — 项目非 git repo（README §72：commit 前需先 git init），git 自检不适用，不阻塞 |
| 上游依赖 merge | ✅ GZ-SYS-005 文件上传 D02 已就位（本卡仅读 cover_url 字符串，未直接依赖上传链路） |
| 关键类/表存在 | ✅ gz-news 后端原只有 NewsHelloController（D01 脚手架），从零搭；表手工导入 dev MySQL 已验 |
| 编译通过 | ✅ baseline mvn compile EXIT=0 → 改动后 compile + test + install 全绿 |
| ADR 已读 | 无相关 ADR（doc/_adr 空） |
| 权威蓝图引用 | ✅ 已读 doc/10 §5 资讯发布流 / doc/11 §5.1+§5.2 字段表 / doc/12 §MP-NEWS-LIST+DETAIL / 附录 A.4 状态机 |

### 权威蓝图关键约束摘录（§0 必读）

- **doc/11 §5.1**（字段权威）：`article_no` / `title` / `summary` / `category_code`（VARCHAR，走 sys_dict）/ `cover_file_id` / `content_html`(MEDIUMTEXT) / `video_urls`(逗号分隔) / `status`(4 态) / `publish_time` / `read_count` / `share_count` / `is_pinned` / `sort_no`
- **doc/11 §5.2**（关键裁定）：**不建独立 `gz_news_category` 表**，`category_code` 走 `sys_dict_data` dict_type=`gz_news_category`；v2 才建独立表
- **doc/10 §5 状态机 / 附录 A.4**：`draft` / `scheduled` / `published` / `offline`（4 态，非 ticket 卡假设的 3 态）
- **doc/10 §1 Q1.3 / N7**：资讯属「仅浏览模式可看」页 → mp 读接口**匿名可访问**（browse_only 也能看）
- **doc/12 §7 偏差 D7**：mockup 含点赞/收藏/评论 toolbar → V1.0 删评论入口，点赞/收藏保留 UI 占位

## ⚠️ ticket 卡假设 vs doc/11 权威 偏差处理（按 CLAUDE.md §9.5 — doc/11 字段层权威优先）

ticket NEWS-001 AC1 的字段命名假设**已过时**，本卡一律按 doc/11 §5.1/§5.2 权威实现：

| ticket 卡 AC1 假设 | doc/11 §5.1/§5.2 权威（采用） | 处理 |
|---|---|---|
| `category_id` + 建独立 `gz_news_category` 表 + 种子 3 条 | `category_code`（VARCHAR）走 `sys_dict_data`，**不建 category 表**（§5.2 裁定） | 种子改为写 sys_dict（4 类 new_product/activity/guide/announcement），不建表 |
| `content`（rich text） | `content_html`（MEDIUMTEXT） | 按权威 |
| `video_url`（单数） | `video_urls`（逗号分隔，≤ 5 个） | 按权威，VO 拆 List |
| `status enum(draft/published/offline)` 3 态 | `status` 4 态（含 `scheduled`） | 按权威 4 态（scheduled 给 NEWS-004 定时发布用） |
| `publish_at` / `view_count` | `publish_time` / `read_count` | 按权威 |
| `cover_url` | `cover_file_id`（FK→file_object） | **两者并存**：见下方决策 |

**cover 字段决策**（已落 reports）：doc/11 用 `cover_file_id`（FK→gz_file_object，admin 上传链路 NEWS-003 才建）。V1.0 mp 仅读 + 无 admin 上传 + 分享卡需直接可渲染 URL（NEWS-002 imageUrl / 主线程纠偏 #6 用 OSS 已有图）→ 本表**同时落 `cover_url VARCHAR(512)`（mp 渲染真源，demo 种子直填）+ `cover_file_id`（预留 admin 关联）**。NEWS-003 admin 上传后写 cover_file_id 并回填 cover_url。

**对 doc/11 的反馈建议**（主线程转 product 决策，不在本卡改源头 doc）：doc/11 §5.1 是否补 `cover_url` 字段说明 + 明确「全部」tab 分类前端聚合走 i18n。

## 实现摘要

### 改动文件（git diff --stat 等价）

**后端（新建 7 Java + 2 DDL + pom 加 test 依赖）**
- `domain/entity/GzNewsArticle.java`（entity，extends TenantEntity，@TableLogic）
- `domain/vo/GzNewsArticleListVO.java`（列表项，Long id @JsonSerialize ToString，不含正文/share_count）
- `domain/vo/GzNewsArticleDetailVO.java`（详情，含清洗后正文 + videoUrls List，不含 share_count）
- `mapper/GzNewsArticleMapper.java`（BaseMapperPlus + @Update incrementReadCount/ShareCount 原子 UPDATE）
- `service/IGzNewsArticleService.java` + `service/impl/GzNewsArticleServiceImpl.java`
- `service/internal/NewsHtmlSanitizer.java`（富文本白名单兜底清洗，AC4/R3）
- `controller/applet/GzNewsArticleMpController.java`（@SaIgnore 匿名读，4 端点）
- `pom.xml` 加 `spring-boot-starter-test`(test scope，与 gz-bean 同款)
- DDL：`V202606031200__GZ-NEWS-001-create-gz_news_article.sql` + `V202606031201__GZ-NEWS-001-seed-data.sql`
- 测试：`GzNewsArticleServiceImplTest`(13) + `NewsHtmlSanitizerTest`(6)

**mp（新建 4 + 改 1 + 测 2）**
- `api/gz-news.ts`（list/detail/view/share 4 函数 + TS 类型，id 全 string）
- `locale/news.zh-CN.ts`（自包含 t() + categoryLabel，分类走前端 i18n）
- `components/biz/BizNewsCard.vue`（列表项卡，C 系统）
- `components/biz/BizNewsCategoryTab.vue`（分类 tab，选中朱红）
- `pages/news/list.vue`（列表页：4 分类 tab + 分页 + 头条大卡 + 触底加载）
- `pages/news/detail.vue`（详情页：rich-text + 视频 + 底部互动条占位 + 返回列表卡）
- `pages/news/index.vue`（**改**：D03 脚手架 → 薄重定向到 /pages/news/list，见下）
- `pages/index/index.vue`（**改**：AC8 首页资讯区接真接口，仅改资讯区）
- 测试：`gz-news.test.ts`(6) + `news.zh-CN.test.ts`(4)

### news/index.vue 处理方式

D03 脚手架占位页（硬编码假数据 `['全部','入荷预告','活动','补货','攻略']` 5 类旧分类）→ **改为薄重定向页**：`onLoad` 即 `uni.redirectTo('/pages/news/list')`。不删除（uni-pages 已注册过该路由，删除需清潜在引用）；薄重定向零维护、防死链、不与新 list 页冲突。所有资讯入口（首页「更多资讯」/ 入口格「资讯」/ 首页资讯卡）已统一指向 `/pages/news/list` 或 detail。

### 首页 AC8 接通情况

✅ **已接通，无残留 mock news 数组**：
- `pages/index/index.vue` 删除硬编码 `const news = [...]` 占位，改为 `const news = ref<NewsArticleListItemVO[]>([])` + `onShow` 调 `listNewsArticles({ pageNum:1, pageSize:3 })` 拉最新 3 条 published
- 渲染真实 title / 分类（categoryLabel i18n）/ 时间+阅读量 / 封面（有 coverUrl 渲 image，无则 tint+MOCK）
- 「更多资讯 →」跳 `/pages/news/list`；卡片点击跳 `/pages/news/detail?id=`
- `pnpm build:mp-weixin` 绿（见下）；grep 确认无残留 mock news 数组

## AI 自测（Tier 1A）

### 后端编译 + install
```
$ mvn compile -pl ruoyi-modules/ruoyi-gz-news -am -q        # baseline & 改后
EXIT=0
$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-news -am
[INFO] BUILD SUCCESS
```

### 后端单测（19 个全绿）
```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-news
[INFO] Tests run: 13, Failures: 0, Errors: 0, Skipped: 0  -- GzNewsArticleServiceImplTest
[INFO] Tests run:  6, Failures: 0, Errors: 0, Skipped: 0  -- NewsHtmlSanitizerTest
[INFO] Tests run: 19, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
覆盖 AC7：列表分页透传 + entity→VO（hasVideo 派生）/ 详情仅 published 可见 / 富文本兜底清洗（剥 script/iframe/on*/javascript:）/ read_count·share_count 原子 UPDATE + null safety / summary 空兜底截 80 字。

### DDL 手工导入 + DB 验证（dev docker MySQL :3307 ry-vue）
```
$ docker exec -i sensenran-dev-mysql mysql -uroot -proot ry-vue < V202606031200__...create-gz_news_article.sql  # 建表 OK
$ docker exec -i sensenran-dev-mysql mysql -uroot -proot ry-vue < V202606031201__...seed-data.sql              # 种子 OK

mysql> SELECT COUNT(*) FROM gz_news_article;                         -> 5
mysql> SELECT COUNT(*) FROM gz_news_article WHERE status='published'; -> 5
mysql> SELECT article_no, category_code, status, is_pinned, read_count FROM gz_news_article ORDER BY is_pinned DESC, publish_time DESC;
  ART-20260603-000001  new_product   published  1  999   ← 置顶头条
  ART-20260603-000002  activity      published  0  612
  ART-20260603-000003  new_product   published  0  388
  ART-20260603-000004  guide         published  0  256
  ART-20260603-000005  announcement  published  0  178
mysql> SELECT dict_value, dict_label FROM sys_dict_data WHERE dict_type='gz_news_category' ORDER BY dict_sort;
  new_product 新品 / activity 活动 / guide 攻略 / announcement 公告  ← 字典 4 类入库
mysql> SELECT tenant_id FROM gz_news_article LIMIT 1;                 -> 1001  ← INSERT 未显式赋，DEFAULT '1001' 生效（CLAUDE.md §6 #3 合规）
```

### mp type-check（news 文件零新增 TS 错）
```
$ pnpm type-check
# 3 个错误全在其他 track（非本卡）：
#   BizCustomerServiceFab.vue（SYS-004 历史债）
#   login/index.vue（SYS-002 历史债）
#   MeHeader.test.ts（USER track 并行开发中，非本卡）
$ pnpm type-check 2>&1 | grep -iE "gz-news|news/|news.zh|BizNews|pages/index"
# → 无匹配（本卡所有 news + 首页改动文件 零 TS 错误）
```

### mp vitest（news 10 个全绿）
```
$ pnpm vitest run src/api/gz-news.test.ts src/locale/news.zh-CN.test.ts
 ✓ src/locale/news.zh-CN.test.ts (4 tests)
 ✓ src/api/gz-news.test.ts (6 tests)
 Test Files  2 passed (2)
      Tests  10 passed (10)
```

### mp build:mp-weixin
```
$ pnpm build:mp-weixin
DONE  Build complete.   (EXIT 0)
# 3 个 news 页面已编进 dist：dist/build/mp-weixin/pages/news/{list,detail,index}.{js,json,wxml,wxss}
# app.json 已注册：pages/news/list / pages/news/detail / pages/news/index
# 首页无残留 mock：grep 旧硬编码标题「新月祭…」于 dist/pages/index → 无匹配（AC8 真接通）
# 警告仅：bean 页面 <route/> 废弃（非 news，本卡 news 全用 definePage()）+ unocss carbon 图标加载（pre-existing，非本卡）
```

### API 烟雾测试（dev 后端离线 — 待全栈验，curl 命令已备）
dev 后端当前未启动（HTTP 000）。后端起来后跑（匿名，无需 token）：
```bash
# 列表（最新 3 条 published）
curl -s "http://localhost:8080/app/gz/news/article/list?pageNum=1&pageSize=3" | jq
# 期望: { code:200, rows:[3 条，ART-...000001 置顶在首], total:5 }

# 分类过滤（活动）
curl -s "http://localhost:8080/app/gz/news/article/list?categoryId=activity&pageNum=1&pageSize=10" | jq '.rows | length'
# 期望: 1（ART-...000002）

# 详情（富文本已清洗）
curl -s "http://localhost:8080/app/gz/news/article/1" | jq '.data | {title, categoryCode, videoUrls, contentHtml}'
# 期望: code=200，contentHtml 无 <script>/<iframe>，无 share_count 字段

# 阅读量 +1
curl -s -X POST "http://localhost:8080/app/gz/news/article/1/view"   # 期望 code:200，DB read_count 1000

# 非 published 详情 → 404 语义
curl -s "http://localhost:8080/app/gz/news/article/99999" | jq '.code'  # 期望 404
```

## 需 Kevin / 全栈手工跑的 DDL 清单（⚠️ Flyway 未接入，手工导入）

> 本卡已在 dev docker MySQL（sensenran-dev-mysql :3307 ry-vue）手工导入并验证通过。其他环境 / 重建库时需手工执行（顺序）：

1. `code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/V202606031200__GZ-NEWS-001-create-gz_news_article.sql` — 建表 gz_news_article
2. `code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/V202606031201__GZ-NEWS-001-seed-data.sql` — sys_dict gz_news_category 4 类 + demo 文章 5 条

**跑完种子后需 flush Redis 字典缓存**（CLAUDE.md §5：ruoyi NullValue 缓存 dict_type 查空结果）：否则 admin/后端首次读 `gz_news_category` 字典可能命中空缓存。

## 风险提示 / 已知 issue

- **R1（富文本清洗用 hutool 非 jsoup）**：ticket 决策 D3 写 jsoup，但 jsoup 不在工程 .m2（未引依赖）。改用 ruoyi 全栈已带的 `cn.hutool.http.HtmlUtil`（removeHtmlTag + 正则剥 on* 事件 / javascript: 伪协议）做等价 denylist 清洗，**不引新依赖**（CLAUDE.md §6 #8 合规）。已加 6 个清洗单测覆盖。admin 端 NEWS-003 写入时白名单清洗仍按需用 jsoup/hutool，本卡是 mp 输出兜底层。
- **R2（read_count 并发）**：V1.0 接受丢失（doc/11 §5.1 R2），用原子 `UPDATE ... SET read_count=read_count+1` 不读改写；V1.1 流量大时切 Redis INCR。
- **R3（cover demo 用 picsum 占位图）**：种子 cover_url 用 `picsum.photos` 占位渐变图（dev 联调可见图，需联网）；上线 NEWS-003 admin 上传换 OSS。低端机 / 无网时降级 tint+MOCK（前端已处理 coverUrl 空分支）。
- **R4（分页结构）**：list 接口返 ruoyi TableDataInfo（{rows,total}），http 封装已识别 rows+total 分页结构直返整对象（非 unwrap data），api 层 NewsPageResult 类型对齐。

## 对下游 ticket 的提示

### 给 GZ-NEWS-002（分享，本 track 下一张，串行）
- detail.vue 已预留 share 结构：底部 toolbar 有「分享」按钮（当前占位 toast）+ onLoad 已读 `from=share|timeline` 埋点 log（NEWS-002 AC5 已半成）+ `articleId` ref 已存。NEWS-002 只需：①把占位 toast 换成 `onShareAppMessage()` / `onShareTimeline()` 钩子 + `<button open-type="share">` ②朋友圈按钮弹引导（i18n `news.share.*` 已备）③调 `reportNewsShare(id)`（api 已实现）。
- `share_count` 字段已在 gz_news_article 表落 + mapper `incrementShareCount` 原子 UPDATE 已实现 + service `increaseShareCount` 已实现 + controller `POST /{id}/share` 已实现 + api `reportNewsShare` 已实现 → **NEWS-002 后端 0 改动，纯 mp 接钩子**。
- i18n `news.share.*` 段（toFriend/toTimeline/timelineGuide*/defaultSummary）已在 news.zh-CN.ts 备好。

### 给 GZ-NEWS-003 / 004（D07 admin 资讯 CMS + 定时发布）的 schema 提示
- **gz_news_article 已落全字段**（doc/11 §5.1 全集）：article_no / title / summary / category_code / cover_url / cover_file_id / content_html / video_urls / status(draft/scheduled/published/offline) / publish_time / schedule_publish_time / read_count / share_count / is_pinned / sort_no + 公共字段。**D07 不重复落表，按需 ALTER**。
- **status 4 态已就位**：scheduled / schedule_publish_time 字段已落 + 已建索引 idx_schedule(tenant_id, schedule_publish_time) → NEWS-004 定时发布 cron 直接用，无需加字段。
- **分类字典已种**：sys_dict gz_news_category 4 类（new_product/activity/guide/announcement）。NEWS-003 admin 编辑文章分类下拉用 `useDict('gz_news_category')`。⚠️ mp 端分类名走前端 i18n（不读 dict_label）— admin 改 dict_label 不影响 mp。
- **cover 双字段**：admin 上传封面后写 `cover_file_id`（FK→gz_file_object）+ 回填 `cover_url`（mp 渲染真源）。或仅写 cover_url。
- **富文本写入清洗**：NEWS-003 admin 写入时建议用白名单清洗（与本卡 NewsHtmlSanitizer 同语义，或更严格的 jsoup 白名单）。mp 输出兜底层已在本卡 service 加。
- **menu_id 段**：NEWS 域 8000-8099（本卡未挂菜单，admin CMS 菜单在 NEWS-003 挂）。
- **demo 文章清理**：上线前删 `article_no LIKE 'ART-20260603-%'` 的 5 条 demo（picsum 占位图）。

## §AI 测试段（Tier 1B）

> 本环境未暴露 Agent/Task 工具（kevin-coder 无 Playwright），无法 spawn kevin-qa 子代理。
> 按协议「kevin-coder 无法 spawn 时自行跑 Tier 1B 等价检查」执行：mp 全量 vitest 回归 + Tier 2 可达性 grep。
> 本卡纯 mp + 后端读接口，无 admin 端 → 无 Playwright admin E2E 项。

### Tier 1B-1：mp 全量 vitest 回归（确认 news 改动零回归）
```
$ pnpm vitest run
 Test Files  15 passed (15)
      Tests  103 passed (103)
# news 新增 10 个（gz-news.test 6 + news.zh-CN.test 4）全绿；既有 93 个全绿，无回归
```

### Tier 1B-2：Tier 2 可达性链 grep（全链路从首页 tab 天然可达 — 无需临时入口）
```
[1] 首页 → 资讯列表：index.vue:110 入口格「资讯」url=/pages/news/list + :126「更多资讯」goPage('/pages/news/list')  ✅
[2] 首页资讯卡 → 详情：index.vue:58 goNewsDetail → /pages/news/detail?id=  ✅
[3] 列表 → 详情：  list.vue:134 navigateTo /pages/news/detail?id=  ✅
[4] 详情 → 返回列表（回流卡 + 错误态回流）：detail.vue:106/123/182 backToList → navigateBack / redirectTo /pages/news/list  ✅
[5] 临时入口：grep Tier2-entry-temp → 无（首页 tab 是现成入口，全链路可达，不需要加临时入口）  ✅
```
**结论**：Kevin 批量人验路径 = 首页 tab →（入口格「资讯」或「更多资讯」）→ 资讯列表 → 点任一文章 → 详情 → 富文本/视频 + 返回列表卡。N=2 步即达列表。✅ 满足 ticket Tier 2 可达 AC。

### Tier 1B 结论：✅ 全绿
- mp vitest 回归：15 files / 103 tests 全过
- Tier 2 可达性：首页 tab 全链路天然可达，无临时入口
- admin E2E：N/A（本卡无 admin 端）
- 后端集成：本卡后端单测 19 全过（Tier 1A）+ DDL/DB 已 dev 验；API curl 待全栈起后端验（命令已备）

## §revision（Kevin testing-human 后填，初始空）

（空）
