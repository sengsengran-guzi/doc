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
# GZ-NEWS-002 完工报告 — mp 文章分享（微信好友 / 朋友圈）

> 资讯 C 端 track 第 2 张卡（串行，依赖 NEWS-001 详情页 onShareAppMessage 钩子）。
> **纯 mp 卡 — 后端 0 改动**（share 链路 NEWS-001 已全部备好）。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A — 项目非 git repo（不阻塞） |
| 上游依赖 merge | ✅ GZ-NEWS-001 已完工（detail.vue / 后端 share 接口 / api reportNewsShare / share_count 字段全就位） |
| 关键类/表存在 | ✅ 后端 `POST /{id}/share` + `increaseShareCount` + mapper `incrementShareCount` 原子 UPDATE + `gz_news_article.share_count` 字段 全已在 NEWS-001 落地（grep 确认） |
| 编译通过 | ✅ 后端 0 改动（无需 mvn）；mp type-check detail.vue 零新增错 + build:mp-weixin DONE |
| ADR 已读 | 无相关 ADR |
| 权威蓝图引用 | ✅ doc/10 §5 §分享分支 N9/N10 / doc/11 §5.1 share_count / doc/12 §MP-NEWS-DETAIL 分享按钮 |

### 权威蓝图关键约束摘录

- **doc/10 §5 N9/N10**：N9 分享好友 `onShareAppMessage` 返回自定义卡片；N10 分享朋友圈 `onShareTimeline`
- **doc/11 §5.1**：`share_count` BIGINT 增量字段（埋点，**不给 mp 用户看**）—— NEWS-001 已落
- **doc/12 §MP-NEWS-DETAIL 组件映射**：分享 → 小程序原生 onShareAppMessage + onShareTimeline
- **ticket 强约束**：①朋友圈 onShareTimeline 只能右上「…」菜单触发，前端按钮 UI 仅引导 ②onShareAppMessage 必须用户主动触发（open-type=share / 右上菜单），代码内不能脚本调用 ③分享封面用 OSS 已有图，不动态绘制 canvas ④share_count 不暴露 C 端

## 实现摘要

### 改动文件（mp 1 个 + 0 后端）

- `pages/news/detail.vue`（**改**：加分享钩子 + 分享按钮 + 计数埋点）
  - import 加 `onShareAppMessage, onShareTimeline`（@dcloudio/uni-app）+ `reportNewsShare`（api）
  - `onShareAppMessage()` 钩子（AC1）：返回 `{ title: 文章 title, path: /pages/news/detail?id=<id>&from=share, imageUrl: cover_url }`
  - `onShareTimeline()` 钩子（AC2）：返回 `{ title, query: id=<id>&from=timeline, imageUrl: cover_url }`
  - 底部 toolbar：`<button open-type="share">`「分享给朋友」（AC3，原生主动触发）+「分享到朋友圈」按钮（弹引导弹窗，微信限制不能脚本触发系统菜单）
  - `reportShareOnce()`（AC4 + AC7 防刷）：分享触发即上报 `POST /{id}/share` → share_count +1；本地去重守卫（同会话同文章只 +1，失败回滚可重试）
  - onLoad 加 `uni.showShareMenu({ menus: ['shareAppMessage','shareTimeline'] })`（启用右上「…」菜单分享入口）
  - `from=share|timeline` 落地埋点（AC5）：NEWS-001 onLoad 已半成，本卡复用（console.info `article_share_landing`）

**后端 0 改动**：NEWS-001 已落 share 全链路（DDL share_count / mapper incrementShareCount / service increaseShareCount / controller POST /{id}/share / api reportNewsShare）。本卡仅 mp 接钩子。

**i18n**：`news.share.*` 段（toFriend / toTimeline / timelineGuideTitle / timelineGuideContent / timelineGuideConfirm / defaultSummary）NEWS-001 已在 news.zh-CN.ts 备好（AC6）。

### 分享卡片字段（AC1/AC2）

| 字段 | onShareAppMessage（好友） | onShareTimeline（朋友圈） |
|---|---|---|
| title | 文章 title（兜底 defaultSummary） | 同 |
| path / query | `path=/pages/news/detail?id=<id>&from=share` | `query=id=<id>&from=timeline` |
| imageUrl | cover_url（OSS 已有图，无则空 → 微信默认截图） | 同 |

封面走 `detail.coverUrl`（OSS URL，强约束 #3：不动态绘制 canvas）。

## AI 自测（Tier 1A）

### mp type-check（detail.vue 零新增 TS 错）
```
$ pnpm type-check
# 仅 2 个 pre-existing 历史债（非本卡）：
#   BizCustomerServiceFab.vue（SYS-004）/ login/index.vue（SYS-002）
$ pnpm type-check 2>&1 | grep -i "news/detail"
# → ✅ detail.vue 零 TS 错误
```

### mp build:mp-weixin（DONE + 分享钩子编进 dist）
```
$ pnpm build:mp-weixin
DONE  Build complete.   (EXIT 0)

# detail.wxml 含分享按钮：
$ grep -o 'open-type="share"|share-btn--friend|share-btn--timeline' dist/build/mp-weixin/pages/news/detail.wxml
  open-type="share"   share-btn--friend   share-btn--timeline

# detail.js 含分享钩子 + 埋点：
$ grep -o 'onShareAppMessage|onShareTimeline|showShareMenu|reportNewsShare|from=share|from=timeline|article_share_landing' dist/.../detail.js
  onShareAppMessage  onShareTimeline  showShareMenu  reportNewsShare  from=share  from=timeline  article_share_landing
```

### mp vitest（share api happy path 覆盖）
```
$ pnpm vitest run src/api/gz-news.test.ts src/locale/news.zh-CN.test.ts
 ✓ src/api/gz-news.test.ts (6 tests)        # 含 reportNewsShare 透传 POST /{id}/share
 ✓ src/locale/news.zh-CN.test.ts (4 tests)  # 含 news.share.toFriend 映射
 Tests  10 passed (10)
```
AC7（share_count 增量 happy path）：后端 `increaseShareCount_transitive` 单测（NEWS-001 已写）+ mp `reportNewsShare` api 单测双覆盖。防刷（同会话去重）= mp 内存级守卫 reportShareOnce（V1.0 简单实现，V1.1 后端 Redis 防刷）。

### 后端 share 链路烟雾测试（dev 后端离线 — 待全栈验，命令已备）
```bash
# 分享计数 +1（匿名，无需 token）
curl -s -X POST "http://localhost:8080/app/gz/news/article/1/share"   # 期望 code:200
# DB 验证：share_count 由 12 → 13
docker exec -i sensenran-dev-mysql mysql -uroot -proot ry-vue -e \
  "SELECT article_no, share_count FROM gz_news_article WHERE id=1;"   # 期望 share_count +1
# 详情 VO 不含 share_count（AC 强约束 #4）
curl -s "http://localhost:8080/app/gz/news/article/1" | jq '.data | has("shareCount")'  # 期望 false
```

## 需 Kevin / 全栈手工跑的 DDL 清单

**本卡无 DDL**（share_count 字段在 NEWS-001 `V202606031200__GZ-NEWS-001-create-gz_news_article.sql` 已落）。

## 风险提示 / 已知 issue

- **R1（朋友圈引导 UX）**：mp 无法脚本触发系统「分享到朋友圈」菜单 → 朋友圈按钮点击弹引导弹窗「请点击右上角…菜单 → 分享到朋友圈」（i18n 已备）。微信硬限制，符合 ticket 强约束 #1。
- **R2（分享卡片图低端机）**：cover_url 走 OSS 已有图（不绘 canvas，强约束 #3），无图时 imageUrl 空 → 微信用页面默认截图兜底。
- **R3（防刷本地级）**：reportShareOnce 是 mp 内存守卫（页面卸载即失效），同一用户多次进详情仍可各 +1。V1.0 接受（流量小）；V1.1 后端 Redis 防刷（ticket D3 已规划）。
- **R4（真机验证项）**：onShareAppMessage / onShareTimeline 卡片实际渲染（封面 + 标题）+ 朋友圈右上菜单触发 → 需 Kevin 真机批量人验（vitest/build 无法验微信原生分享卡片渲染）。

## 对下游 ticket 的提示

- **给 GZ-NEWS-003（D07 admin 资讯 CMS）**：admin 端可加「分享量」列展示 `share_count`（mp 端不可见，admin 可见，doc/11 §5.1）。share_count 已在 gz_news_article 表，admin 直接 SELECT 即可，无需新增字段。
- **给 V1.1 防刷优化**：如需用户级分享行为分析，再单独建埋点表（doc/11 §5 / ticket D2：V1.0 用增量字段不建表，V1.1 评估）。
- **分享落地参数 `from=share|timeline`**：已在 detail onLoad 上报 `article_share_landing` log（V1.0 仅 log）。V1.1 如需转化分析，把 log 改为入业务埋点表。

## §AI 测试段（Tier 1B）

> 本环境未暴露 Agent/Task 工具，无法 spawn kevin-qa。按协议自跑 Tier 1B 等价检查。
> 纯 mp 卡，无 admin → 无 Playwright E2E 项。

### Tier 1B-1：mp 全量 vitest 回归（零回归）
```
$ pnpm vitest run
 Test Files  15 passed (15)
      Tests  103 passed (103)
# NEWS-002 改动（detail.vue）未破坏任何既有测试
```

### Tier 1B-2：分享钩子编进产物（dist 验证）
```
detail.wxml: open-type="share" + share-btn--friend + share-btn--timeline  ✅
detail.js:   onShareAppMessage + onShareTimeline + showShareMenu + reportNewsShare + from=share/timeline + article_share_landing  ✅
```

### Tier 1B-3：Tier 2 可达性（分享在详情页内，从首页 tab 全链路可达）
```
分享好友按钮 detail.vue:278 <button open-type="share">  ✅
分享朋友圈引导 detail.vue:282 @tap=onTimelineGuide  ✅
分享钩子 detail.vue:137 onShareAppMessage / :149 onShareTimeline  ✅
临时入口：无（分享在详情页内，详情从首页 tab → list/资讯卡 可达，无需临时入口）  ✅
```
**结论**：Kevin 批量人验路径 = 首页 tab → 资讯列表 → 文章详情 → 右上「…」菜单 / 底部「分享给朋友」按钮触发分享卡片 +「分享到朋友圈」按钮弹引导。✅ 可达。

### Tier 1B 结论：✅ 全绿（mp vitest 103 全过 / 分享钩子编进 dist / 可达性 OK / admin 无）

> ⚠️ **微信原生分享卡片实际渲染**（封面图 + 标题在好友/朋友圈卡片的视觉）+ 真机右上菜单触发 → 留 Kevin 真机批量人验（AI vitest/build 无法验微信原生分享 UI）。

## §revision（Kevin testing-human 后填，初始空）

（空）
# GZ-USER-001 完工报告 — mp 会员中心首页

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | ✅（miniapp/src 是独立 git repo，staging 分支；本 track 改动隔离于 me/* + gz-user.ts + Biz 组件，未碰 NEWS 域） |
| 上游依赖 merge | ✅ GZ-SYS-002(D02) 微信登录 + useAuth / useNavGuard 已就位 |
| 关键类/表存在 | ✅ getMe() 已在 api/gz-user.ts；gz_user 表 D02 已落 |
| 编译通过 | ✅ type-check 零新增 TS 错；build:mp-weixin 产物绿 |
| ADR 已读 | 无相关 ADR（doc/_adr 空） |

**权威蓝图引用摘录**：
- doc/10 §4 会员中心占位流 N1：进入会员中心首页渲染头像/昵称/功能区入口
- doc/11 §2.1 gz_user：本 ticket 仅读 avatar_url / nickname（不动 schema）
- doc/12 §7 偏差 D4：等级 LV / 签到 / 邀请 / 优惠券全删；保留收藏 UI 占位（数字 0）

**主线程纠偏已落实**：
- 「我的预约」入口跳 `/pages/bean/my-list`（D05 BEAN-006 实际路由，非旧假设 me/bookings/list）
- me/index.vue 重建（非新建）：删除 D03 脚手架硬编码占位数组，用 Biz* + i18n + getMe() 真实数据
- 不手改 pages.json（definePage 宏自动生成，已验证 app.json 含 6 个 me 页路由）

## 实现摘要

改动/新增文件：
- `pages/me/index.vue`（重建：MeHeader + MeGrid + getMe 真实头像/昵称 + 九宫格真实入口 + 保留 useNavGuard）
- `pages/me/about.vue`（新增：关于页 — 版本号 + 备案 + 协议链接，AC 3.5）
- `components/biz/MeHeader.vue`（新增：头部两态业务组件，未登录/已登录）
- `components/biz/MeGrid.vue`（新增：九宫格业务组件，含客服 open-type="contact"）
- `components/biz/MeHeader.test.ts`（新增：vitest 8 例）
- `locale/user.zh-CN.ts`（新增：4 张卡共用 i18n，含 home 段）

九宫格入口（AC 3）：我的订单→/pages/me/orders ｜ 我的预约→/pages/bean/my-list ｜ 地址簿→/pages/me/address/list ｜ 客服→`<button open-type="contact">` ｜ 关于→/pages/me/about。
头部已登录态点击 → /pages/me/profile（USER-002 入口）。

## AI 自测

### 编译（type-check + build）
```
$ pnpm type-check
src/components/biz/BizCustomerServiceFab.vue(92,5): error TS2322  ← pre-existing 历史债（非本 track）
src/pages/login/index.vue(35,50): error TS2339                    ← pre-existing 历史债（非本 track）
（本 track 零新增 TS 错）

$ pnpm build:mp-weixin → 产物生成于 dist/build/mp-weixin/
$ grep "pages/me/" dist/build/mp-weixin/app.json
pages/me/about / pages/me/index / pages/me/orders / pages/me/profile
pages/me/address/edit / pages/me/address/list
（definePage 宏自动注册 6 页路由，未手改 pages.json）
```

### 单测（vitest MeHeader 两态）
```
$ pnpm vitest run src/components/biz/MeHeader.test.ts
 ✓ src/components/biz/MeHeader.test.ts (8 tests) 18ms
   - 未登录 → 「点击登录」+ emit(login)
   - 已登录有昵称 → 真实昵称 / 无昵称 → 回退「微信用户」
   - 已登录点击头部 emit(edit)（进资料编辑）
   - 有头像 → image / 无头像 → 占位 emoji
   - 收藏占位数字硬编码 0（doc/12 §7 D4）
 Test Files  1 passed (1)   Tests  8 passed (8)
```

### 可达性验证（Tier 2）
```
$ grep -nE "pages/me/orders|bean/my-list|me/address/list|me/about|me/profile" pages/me/index.vue
59: orders: '/pages/me/orders'
60: bookings: '/pages/bean/my-list'
61: address: '/pages/me/address/list'
62: about: '/pages/me/about'
93: uni.navigateTo({ url: '/pages/me/profile' })
本页 = 已上线「我的」tab → Kevin 直接点底部 tab 进入，无需临时入口
```

## 风险提示 / 已知 issue

- getMe() 返回的 GzUserMeVO.id 类型声明为 string，但后端 common 的 GzUserVO.id 未加 ToStringSerializer（D02 遗留）→ 实际返 number。小用户量（<2^53）安全；本 ticket 沿用 D02 既有行为不引入分叉。新建的 GzUserAddressVO / GzUserAuditLogVO 已显式加 ToStringSerializer（跨层契约 #1）。
- 待 Kevin 批量人验关注（mp）：① 「我的」tab 头像/昵称登录前后切换 ② 九宫格 5 入口跳转有效（预约→/pages/bean/my-list）③ 客服 open-type=contact 拉起微信会话 ④ 关于页版本号/链接显示。

## 对下游 ticket 的提示

- USER-002 profile 入口 = 已登录态点击会员中心头部（MeHeader emit edit）；USER-002 已实施此入口。
- USER-004 orders 页 / USER-003 address 页路由已在 USER-001 ROUTE_MAP 配好，本 track 一起实现，整体可达。
- 无临时入口需下游清理（本 track 全部从已上线 tab 可达）。

## §AI 测试段（Tier 1B — kevin-coder 代跑，见说明）

> ⚠️ **kevin-qa 无法 spawn**（本实施在 subagent 内，Agent 工具不可用）→ Tier 1B 等效检查由 kevin-coder 代跑。
> 主线程可决定是否补派 kevin-qa 复核。本 track 为 mp + 后端（admin 0 改动 → 无 Playwright admin E2E）。

### mp vitest 全量回归
```
$ pnpm vitest run
 ✓ src/components/biz/MeHeader.test.ts (8 tests)
 ✓ src/components/biz/OrderListEmpty.test.ts (1 test)
 ✓ (其余 13 文件无回归)
 Test Files  15 passed (15)   Tests  103 passed (103)
```

### mp type-check
```
本 track 零新增 TS 错；仅 2 个 pre-existing 历史债（BizCustomerServiceFab.vue:92 / login/index.vue:35）
```

### Tier 2 可达性
```
本页 = 已上线「我的」tab（useNavGuard('me')）→ Kevin 点底部 tab 直达
九宫格 5 入口 + 头部 edit→profile 跳转 grep 全部命中真实路由
无临时入口残留（grep Tier2-entry-temp = 空）
```

**Tier 1B 结论：USER-001 ✅**（mp vitest + type-check + 可达性全绿）
# GZ-USER-002 完工报告 — mp 个人资料编辑

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | ✅ 改动隔离于 gz-user 后端模块 + me/profile + AvatarUpload + user.zh-CN |
| 上游依赖 merge | ✅ GZ-SYS-002(D02 登录) + GZ-SYS-005(D02 文件上传 uploadFile) 已就位 |
| 关键类/表存在 | ✅ gz_user 表 D02 已落；gz_user_audit_log 本 ticket 落 DDL；bind-mobile 端点 D02 已存在 |
| 编译通过 | ✅ mvn install gz-user BUILD SUCCESS；type-check 零新增；build 绿 |
| ADR 已读 | 无相关 ADR |

**权威蓝图引用摘录**：
- doc/10 §4.N2：编辑个人资料 → 更新 gz_user + 写 gz_user_audit_log
- doc/11 §2.1 gz_user：写 nickname / avatar_url / gender（手机号走 bind-mobile）
- doc/11 §2.3 gz_user_audit_log：本 ticket 落表（V1.0 实装 update_nickname/avatar/gender/mobile）
- doc/11 §2.5 F2.5：V1.0 实现 update_mobile / update_nickname（拼豆强收集可追溯）

**R6 冒烟（改 useAuth 前）**：本 ticket **未改 useAuth**（手机号复用现有 bindMobile，登录复用现有 loginWithWechat）→ R6 不触发，拼豆登录链路零影响。

**关键架构决策**：
- profile 编辑放 gz-user 模块新建 `GzUserProfileService`（跨模块注入 common 的 GzUserMapper 操作 gz_user 表 + 本模块 GzUserAuditLogMapper 写审计）。**不改 common 的 IGzUserService**（保持其「admin 只读 + 登录 UPSERT」语义纯净；C 端用户改自己资料是独立合法场景，doc/10 §4.N2）。
- **手机号编辑复用现有 bind-mobile，不写 decode-phone 端点**：微信新版 getPhoneNumber 直接返明文 phoneNumber（D02 UserBindMobileController 已实现），无需 session_key 解码。任务卡 AC 3 的 decode-phone 端点是基于旧 encryptedData 链路的假设，仓库实际已简化 → 复用更对。
- audit 写入在 Service 层 @Transactional（profile 写失败时 audit 回滚，原子）。

## 实现摘要

后端新增（org.dromara.gz.user）：
- `domain/entity/GzUserAuditLog.java` + `domain/vo/GzUserAuditLogVO.java`（id/userId 加 ToStringSerializer）+ `mapper/GzUserAuditLogMapper.java`
- `domain/bo/UserProfileUpdateBo.java`（nickname ≤32 / avatarUrl / gender 校验）
- `service/IGzUserProfileService.java` + `service/impl/GzUserProfileServiceImpl.java`（变化字段逐条写审计）
- `controller/applet/GzUserProfileMpController.java`（PUT /app/gz/user/profile）
- DDL `V202606031000__GZ-USER-002-create-gz_user_audit_log.sql`
- pom.xml 加 spring-boot-starter-test（gz-user 新模块原无测试依赖）

mp 新增/改动：
- `pages/me/profile.vue`（头像/昵称/性别/手机号表单 + 一键拉取微信资料 + 保存同步 store）
- `components/biz/AvatarUpload.vue`（chooseImage + OSS uploadFile，usageType=user_avatar）
- `api/gz-user.ts` 加 updateProfile() + UserProfileUpdateRequest
- `components/biz/MeHeader.vue` 加 edit emit（已登录点头部进编辑）

## AI 自测

### 编译 + install
```
$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-user -am -q
BUILD SUCCESS（gz-user 模块 jar 装入本地仓库）
```

### 单测（GzUserProfileServiceImplTest）
```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-user
[INFO] Running org.dromara.gz.user.service.impl.GzUserProfileServiceImplTest
[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0
   - 改昵称 → UPDATE + 写 1 条 update_nickname 审计（验 before/after/userId/ip）
   - 昵称+头像+性别全改 → 写 3 条审计
   - 传相同值 → 不 UPDATE 不写审计
   - 仅传昵称（头像/性别 null）→ 只动昵称
   - 用户不存在 / userId null → ServiceException
[INFO] BUILD SUCCESS
```

### DB 验证（dev MySQL 在线，手工导入 DDL）
```
$ docker exec -i sensenran-dev-mysql mysql -uroot -proot ry-vue < V202606031000__...audit_log.sql
$ DESC gz_user_audit_log;
id bigint unsigned PRI auto_increment / user_id NOT NULL / action_type varchar(32) NOT NULL
before_value / after_value varchar(255) / ip varchar(64)
tenant_id varchar(20) NOT NULL DEFAULT '1001' / del_flag char(1) NOT NULL DEFAULT '0'
索引 idx_tenant_user / idx_tenant_action_type ✅
```

### API 烟雾（后端未在线，curl 命令备用，待全栈起来验）
```bash
# 期望：200 + 返回更新后 GzUserVO + DB gz_user_audit_log 多 1 条
curl -X PUT http://localhost:8080/app/gz/user/profile \
  -H "Authorization: Bearer <sa-token>" -H "clientid: <mp-clientid>" \
  -H "Content-Type: application/json" \
  -d '{"nickname":"阿喵","gender":1}'
```

## 风险提示 / 已知 issue

- R1（session_key 过期）：手机号编辑走 bind-mobile，微信新版直接返明文 phoneNumber 无需 session_key 解码 → 不存在解码失败。若 sa-token 业务 token 过期 → http.ts 拦截器 401 自动跳登录（已有兜底）。
- 一键拉取微信资料用 uni.getUserProfile（微信 2022 后限制：用户主动触发 + 部分基础库返默认昵称/灰头像）；拒授权时静默不阻塞（已处理）。
- 待 Kevin 批量人验关注（mp）：① 改昵称保存后落库（gz_user_audit_log +1）② 头像上传 OSS 成功 ③ getPhoneNumber 授权后手机号回填 ④ 一键拉取微信资料覆盖表单（不入库，需点保存）⑤ 保存后返回 + 会员中心头像/昵称同步。

## 对下游 ticket 的提示

- gz_user_audit_log 表已落，V1.0 admin 用户详情看审计（后续 admin ticket）可直接用 GzUserAuditLogVO + GzUserAuditLogMapper。
- DDL 需 Kevin 手工跑：`V202606031000__GZ-USER-002-create-gz_user_audit_log.sql`（dev 已导入验证）。

## §AI 测试段（Tier 1B — kevin-coder 代跑，见说明）

> ⚠️ kevin-qa 无法 spawn（subagent 内 Agent 工具不可用）→ Tier 1B 等效检查由 kevin-coder 代跑。主线程可决定是否补派复核。

### 后端单测
```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-user
GzUserProfileServiceImplTest: Tests run: 6, Failures: 0, Errors: 0 ✅
BUILD SUCCESS
```

### API 契约回归（mp ↔ 后端路径核对）
```
mp updateProfile PUT /app/gz/user/profile ↔ 后端 @PutMapping /app/gz/user/profile ✅
（手机号编辑复用 bind-mobile，D02 已存在端点，未新写 decode-phone）
```

### mp vitest + type-check
```
vitest 全量 103 passed（含 MeHeader 8）；type-check 零新增 TS 错
```

### Tier 2 可达性
```
profile 入口 = 会员中心头部已登录态点击（MeHeader emit edit → /pages/me/profile）
从已上线「我的」tab 可达，无需临时入口
```

**Tier 1B 结论：USER-002 ✅**（后端单测 6/6 + 契约对齐 + DDL 已导入验证 + 可达性全绿）
# GZ-USER-003 完工报告 — mp 地址簿 CRUD

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | ✅ 改动隔离于 gz-user 后端 + me/address + AddressCard + user.zh-CN |
| 上游依赖 merge | ✅ GZ-SYS-002(D02 登录) 已就位 |
| 关键类/表存在 | ✅ gz_user_address 本 ticket 落 DDL；gz_user 表已存在（FK 引用） |
| 编译通过 | ✅ mvn install BUILD SUCCESS；type-check 零新增；build 绿 |
| ADR 已读 | 无相关 ADR |

**权威蓝图引用摘录**：
- doc/10 §4.N3-N7：地址簿 list/新增/编辑/软删/设默认；默认地址状态机（旧默认自动取消）
- doc/11 §2.2 gz_user_address：完整字段 + 索引 idx_tenant_user / idx_tenant_user_default + 业务规则（单用户≤20，默认≤1 业务层兜底）

**关键决策（R2 — 省市区联动零新依赖）**：
- mp 端用 **uni-app 原生 `<picker mode="region">`**（自带全国省市区数据）→ **不引** wot-design-uni 城市集 / area-data（CLAUDE.md §6 #8 不引未澄清依赖；R2 直接缓解，无需报 Kevin 决策）。
- 默认地址唯一性：业务层事务兜底（resetOthersDefault 先把该用户其他 is_default=0 再 set 目标=1），**不依赖 DB 偏函数索引**（doc/11 §2.2 + 任务卡 D1）。
- 越权防护：所有写操作先校验 address.userId == 当前 userId（防改他人地址）。
- 软删（del_flag='2'，@TableLogic）+ list 自动过滤。

## 实现摘要

后端新增（org.dromara.gz.user）：
- `domain/entity/GzUserAddress.java` + `domain/vo/GzUserAddressVO.java`（id 加 ToStringSerializer）+ `domain/bo/GzUserAddressBo.java`（收件人/手机号 regex/省市区/详情校验）
- `mapper/GzUserAddressMapper.java`
- `service/IGzUserAddressService.java` + `service/impl/GzUserAddressServiceImpl.java`
- `controller/applet/GzUserAddressMpController.java`（GET /list, GET /{id}, POST, PUT, DELETE /{id}, POST /{id}/default）
- DDL `V202606031100__GZ-USER-003-create-gz_user_address.sql`

mp 新增：
- `pages/me/address/list.vue`（列表默认置顶 + 空态 + 删除二次确认 + 设默认）
- `pages/me/address/edit.vue`（收件人/手机号/region picker/详情/标签/默认 switch/智能粘贴）
- `components/biz/AddressCard.vue`
- `api/gz-user.ts` 加 getAddressList/getAddress/saveAddress/deleteAddress/setDefaultAddress + UserAddressVO/UserAddressSaveRequest

## AI 自测

### 编译 + install
```
$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-user -am -q
BUILD SUCCESS
```

### 单测（GzUserAddressServiceImplTest，含 TableInfoHelper 初始化）
```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-user
[INFO] Running org.dromara.gz.user.service.impl.GzUserAddressServiceImplTest
[INFO] Tests run: 9, Failures: 0, Errors: 0, Skipped: 0
   - 新建默认地址 → reset 其他(update null+wrapper) + insert
   - 新建非默认 → 不 reset
   - 编辑/设默认/软删他人地址 → ServiceException（越权防护）
   - 切换默认 → reset 其他 + set 当前
   - 软删本人 → deleteById
   - getByIdForUser 他人 → null（不暴露存在性）
[INFO] BUILD SUCCESS
```
> 注：纯 mock 单测下 LambdaUpdateWrapper.eq(GzUserAddress::getXxx) 需 mybatis-plus TableInfo 缓存，
> @BeforeAll 用最小 Configuration 注册一次（不连库）。

### DB 验证（dev MySQL 在线，手工导入）
```
$ docker exec -i sensenran-dev-mysql mysql -uroot -proot ry-vue < V202606031100__...address.sql
$ SHOW INDEX FROM gz_user_address;
PRIMARY(id) / idx_tenant_user(tenant_id,user_id) / idx_tenant_user_default(tenant_id,user_id,is_default) ✅
$ SELECT COLUMN_DEFAULT FROM information_schema.COLUMNS WHERE TABLE_NAME='gz_user_address';
tenant_id DEFAULT '1001' / del_flag DEFAULT '0' / is_default DEFAULT 0 ✅
```

### API 烟雾（后端未在线，curl 备用，待全栈起来验）
```bash
# 新建默认地址 → 200，再建另一条默认 → 上一条 is_default 自动置 0
curl -X POST http://localhost:8080/app/gz/user/address \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"recipientName":"张三","mobile":"13800138000","province":"四川省","city":"成都市","district":"锦江区","detail":"春熙路1号","isDefault":1}'
```

## 风险提示 / 已知 issue

- 智能粘贴（AC 6）：uni.chooseAddress 在部分基础库/未配置时不可用 → 降级 toast「请手动填写」（doc/12 §7 D9 妥协方案，已处理）。
- R1（region picker 编码）：uni 原生 region picker 只返中文文本（province/city/district），不返国标编码。V1.0 仅收集展示足够；V1.1 真实下单调微信寄送如需编码 → 评估补编码字段（不 break 现有 schema，加可选列）。
- R2（设默认并发）：业务层事务 reset+set；V1.0 并发量小可接受（未加 SELECT FOR UPDATE 行锁，doc/11 §2.2 业务量评估后可接受）。
- 待 Kevin 批量人验关注（mp）：① 新建/编辑/删除地址 ② 省市区 picker 联动 ③ 设默认后旧默认自动取消（默认唯一）④ 删除二次确认 ⑤ 空态占位。

## 对下游 ticket 的提示

- DDL 需 Kevin 手工跑：`V202606031100__GZ-USER-003-create-gz_user_address.sql`（dev 已导入验证）。
- V1.1 预定下单（GZ-ORD）引用地址：用 GzUserAddressVO，地址软删保证历史引用不断（del_flag）。

## §AI 测试段（Tier 1B — kevin-coder 代跑，见说明）

> ⚠️ kevin-qa 无法 spawn（subagent 内 Agent 工具不可用）→ Tier 1B 等效检查由 kevin-coder 代跑。主线程可决定是否补派复核。

### 后端单测
```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-user
GzUserAddressServiceImplTest: Tests run: 9, Failures: 0, Errors: 0 ✅
（覆盖新建默认/切换默认/软删/越权防护，默认地址唯一性事务兜底）
BUILD SUCCESS
```

### API 契约回归（mp ↔ 后端 6 端点全核对）
```
GET /address/list ↔ @GetMapping("/list") ✅
GET /address/{id} ↔ @GetMapping("/{id}") ✅
POST/PUT /address ↔ @PostMapping + @PutMapping ✅
DELETE /address/{id} ↔ @DeleteMapping("/{id}") ✅
POST /address/{id}/default ↔ @PostMapping("/{id}/default") ✅
```

### mp vitest + type-check
```
vitest 全量 103 passed；type-check 零新增 TS 错
省市区联动用 uni 原生 region picker（零新依赖，R2 已解）
```

### Tier 2 可达性
```
会员中心九宫格「地址簿」→ /pages/me/address/list（USER-001 ROUTE_MAP 已配）→ 从已上线 tab 可达
```

**Tier 1B 结论：USER-003 ✅**（后端单测 9/9 + 契约 6 端点对齐 + DDL 已导入验证 + 可达性全绿）
# GZ-USER-004 完工报告 — mp 我的订单 tab 占位结构

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | ✅ 改动隔离于 me/orders + OrderListEmpty + api/types/order + gz-user.ts |
| 上游依赖 merge | ✅ GZ-USER-001（会员中心首页，九宫格「我的订单」入口）已实现 |
| 关键类/表存在 | ✅ 本 ticket 不动后端、不调 API（V1.0 占位） |
| 编译通过 | ✅ type-check 零新增；build 绿；vitest 通过 |
| ADR 已读 | 无相关 ADR |

**权威蓝图引用摘录**：
- doc/10 §4.N8：进入「我的订单」tab，V1.0 全部 tab 显示「暂无订单，敬请期待 V1.1」占位；预约不混入
- 合同 §2.1 第一期：订单聚合 tab 仅占位结构，业务线 A/B 订单数据待 V1.1 接入
- doc/12 §7 偏差 D3：mockup 4 tab（含拼豆）→ 按 PRD 删拼豆 tab，仅 全部/扭蛋/预购 3 tab

## 实现摘要

mp 新增/改动：
- `pages/me/orders.vue`（3 tab：全部/扭蛋/预购，纯前端切换，**不调任何 API**，占位空态）
- `components/biz/OrderListEmpty.vue`（空状态业务组件）
- `components/biz/OrderListEmpty.test.ts`（vitest 占位文案验证）
- `api/types/order.ts`（新增：OrderListVO 契约 VO 真源 — AC 5）
- `api/gz-user.ts` 加 getOrderList() 声明（V1.0 仅声明不实现，re-export OrderListVO）
- `locale/user.zh-CN.ts` 加 orders 段

**契约 VO 定齐（AC 5，V1.1 接入合同）**：
```ts
interface OrderListVO {
  orderId: string          // 业务码不暴露 id（跨层契约 #2）
  type: 'gacha' | 'preorder'
  amount: number; status: string; createdAt: string
  coverUrl?: string; title?: string
}
```
V1.1 直接复用，不允许 break 现有字段（只可加可选字段）。

**强约束落实**：
- 预约不混入订单 tab（独立「我的预约」入口走 BEAN-006 /pages/bean/my-list，USER-001 九宫格已暴露）
- 3 tab 删拼豆（doc/12 §7 D3）
- getOrderList 仅声明 TS 签名，V1.0 不调（避免后端误以为已接入）

## AI 自测

### 编译（type-check + build）
```
$ pnpm type-check → 本 track 零新增 TS 错（仅 2 个 pre-existing 历史债）
$ pnpm build:mp-weixin → dist 含 pages/me/orders.{js,json,wxml,wxss}
$ grep "pages/me/orders" dist/build/mp-weixin/app.json → pages/me/orders ✅
```

### 单测（vitest）
```
$ pnpm vitest run src/components/biz/OrderListEmpty.test.ts
 ✓ src/components/biz/OrderListEmpty.test.ts (1 test) 7ms
   - 渲染「暂无订单，敬请期待 V1.1」占位文案
```
> tab 切换交互（AC 7）：orders.vue 不 import getOrderList → 静态保证「不调 API」；
> 3 tab 切换纯 ref 状态，无网络。真机交互留 Kevin 批量人验。

### 可达性（Tier 2）
```
USER-001 九宫格「我的订单」→ ROUTE_MAP.orders='/pages/me/orders' ✅
本页从已上线「我的」tab 点九宫格可达，无需临时入口
```

## 风险提示 / 已知 issue

- R5（V1.1 接入契约不一致）：OrderListVO 已留 type/status 两个泛字段；V1.1 如需物流号/退款状态 → 加可选字段（不 break 现有契约）。契约真源在 api/types/order.ts 单点维护。
- R2（用户疑惑「为什么没拼豆」）：占位文案 + 「我的预约」入口在 USER-001 九宫格独立暴露，UX 路径清晰。
- 待 Kevin 批量人验关注（mp）：① 订单 tab 3 子 tab 切换 ② 三个 tab 全显示「暂无订单，敬请期待 V1.1」占位。

## 对下游 ticket 的提示

- V1.1 GZ-ORD/GZ-GACHA 接入：实现后端 `/app/gz/user/orders/list?type=` → orders.vue 按 activeTab 调 getOrderList（当前注释已标接入点）→ OrderListVO 直接复用零改字段。

## §AI 测试段（Tier 1B — kevin-coder 代跑，见说明）

> ⚠️ kevin-qa 无法 spawn（subagent 内 Agent 工具不可用）→ Tier 1B 等效检查由 kevin-coder 代跑。主线程可决定是否补派复核。

### mp vitest
```
$ pnpm vitest run src/components/biz/OrderListEmpty.test.ts
 ✓ OrderListEmpty.test.ts (1 test) — 「暂无订单，敬请期待 V1.1」占位
全量 103 passed（无回归）
```

### type-check
```
本 track 零新增 TS 错；OrderListVO 契约 VO 在 api/types/order.ts 类型校验通过
```

### 契约层（V1.1 接入合同）
```
getOrderList GET /app/gz/user/orders/list（V1.0 仅声明不实现）
OrderListVO { orderId, type, amount, status, createdAt, coverUrl?, title? } 已定齐
orders.vue 不 import getOrderList → 静态保证「不调 API」（AC 3/AC 4）
```

### Tier 2 可达性
```
会员中心九宫格「我的订单」→ /pages/me/orders（USER-001 ROUTE_MAP 已配）→ 从已上线 tab 可达
```

**Tier 1B 结论：USER-004 ✅**（vitest + type-check + 契约定齐 + 不调 API 静态保证 + 可达性全绿）
