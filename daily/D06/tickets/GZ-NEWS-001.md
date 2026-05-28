# GZ-NEWS-001 — mp 文章列表 + 详情 + 分类

**优先级**: P0
**复杂度**: M
**关联 PRD**: doc/02-prd.md M6 §用户操作流程 §用户读文章 + §关键字段 § Article
**关联拆解**: doc/02-需求拆解.md §2.5 第 491 行
**关联 mockup**: design/mockup/news-list.html + design/mockup/news-detail.html（视觉参考，V1.0 设计冻结期不强求逐像素；mockup 含点赞 / 收藏 / 评论 toolbar — doc/12 §7 偏差 D7，实施时 V1.0 删评论入口）
**关联 ADR**: —
**依赖**: GZ-SYS-005 ✅(D02)

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§5 资讯发布流**（M6，V1.0）— admin 发布 / mp 拉列表 / 详情访问 / 浏览计数；本 ticket 仅实现 mp 端读路径，admin 发布 CMS 在 GZ-NEWS-003 (D07+)
- **字段表**：doc/11-字段权威表.md **§5.1 `gz_news_article` 文章表** + **§5.2 `gz_news_category` 分类表**（字段权威 — 完整 DDL 来源）+ §1 全局公共字段
- **UI 参考**（设计冻结期降级为视觉参考）：doc/12-UI-权威索引.md **§MP-NEWS-LIST** + **§MP-NEWS-DETAIL** + mockup `news-list.html` / `news-detail.html`

## What

落地 `gz_news_category` + `gz_news_article` 两表；mp 端文章列表（4 分类 tab）+ 详情（富文本 + 视频）；视觉对齐 tokens.md（卡片样式 + 区块标题左侧绿条）。本 ticket 不做 admin 端 CMS（NEWS-003 推到 D07+），仅手工 INSERT 几条 demo 文章用于联调。

## AC（验收标准）

- [ ] **AC 1**：DDL × 3：
  - `V202606031200__GZ-NEWS-001-create-gz_news_category.sql` 严格按 doc/11 §5.2（id / name / sort_no / is_active + 全局公共字段）
  - `V202606031201__GZ-NEWS-001-create-gz_news_article.sql` 严格按 doc/11 §5.1（id / category_id / title / cover_url / content（rich text MEDIUMTEXT）/ video_url / status enum(`draft`/`published`/`offline`) / publish_at / view_count / share_count + 全局公共字段）
  - `V202606031202__GZ-NEWS-001-seed-data.sql` 种子分类 3 条（新品 / 活动 / 攻略 — "全部"前端聚合不入库）+ demo 文章 3-5 条供联调
- [ ] **AC 2**：mp 端 `/pages/news/list` 顶部分类 tab（全部 / 新品 / 活动 / 攻略，4 类硬约束）；列表分页拉 `GET /app/gz/news/article/list?categoryId=&pageNum=&pageSize=`（按 publish_at desc，仅 status=`published`）
- [ ] **AC 3**：mp 端 `/pages/news/detail?id=<id>`：富文本渲染（`rich-text` 标签）+ 视频（如有 video_url 用 `<video>` 组件渲染）+ 顶部分享按钮（占位，NEWS-002 接管）；详情 mount 时调 `POST /app/gz/news/article/{id}/view` view_count +1
- [ ] **AC 4**：富文本输出白名单清洗：后端返回前过滤 `<script>` / `<iframe>` 等危险标签（用 jsoup 白名单 / 或者依赖 admin 端写入时已清洗 — 与 NEWS-003 协调，本 ticket 服务端兜底加一层）
- [ ] **AC 5**：mockup 含的点赞 / 收藏 / 评论底部 toolbar（doc/12 §7 偏差 D7）：评论入口**不做**；点赞 / 收藏 **UI 保留** 但点击 toast"V1.0 不支持"（不实现后端）
- [ ] **AC 6**：i18n 走 `t('news.xxx')`（含分类名 — 走前端 i18n 而不是后端 name 字段；后端 name 字段仅 admin 端展示，mp 端用 i18n key）
- [ ] **AC 7**：单测覆盖：列表分页 / view_count 增量 / 富文本清洗 happy path

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-news/`（脚手架 D01 已建）
  - `controller/applet/GzNewsArticleMpController.java`（mp 路径 `/app/gz/news/article`）
  - `controller/applet/GzNewsCategoryMpController.java`（mp 路径 `/app/gz/news/category`，仅 list 接口）
  - `domain/GzNewsArticle.java` / `GzNewsCategory.java` + vo + bo
  - `mapper/GzNewsArticleMapper.java` / `GzNewsCategoryMapper.java`
  - `service/IGzNewsArticleService.java` + impl + `IGzNewsCategoryService.java` + impl
  - DDL × 3
- **小程序**：`code/main/miniapp/src/`
  - `pages/news/list.vue` + `pages/news/detail.vue`
  - `components/biz/NewsCard.vue`（业务组件）
  - `components/biz/NewsCategoryTab.vue`（分类 tab 业务组件）
  - `api/gz-news.ts`
  - `locales/zh_CN/news.ts`
- **测试**：mvn 单测 + mp 端浏览器 / 微信开发者工具实操

## 备注

### 强约束

1. **分类 4 类固定**（全部 / 新品 / 活动 / 攻略）— V1.0 admin CMS NEWS-003 不开放分类编辑；本 ticket DDL 仅种子 3 条入库（"全部"前端聚合）
2. **status enum 三态**：`draft`（admin 编辑中，mp 不可见） / `published`（mp 可见） / `offline`（下架，mp 不可见）
3. **富文本清洗**：双层保护 — admin 写入时清洗（NEWS-003 实现）+ 本 ticket mp 输出前再清洗（兜底）
4. **video_url 不强收集**：允许为空，列表卡片不显示视频图标
5. **i18n 强制**：分类名走 `t('news.category.xxx')`，不直接读 DB name 字段（避免 V1.0 多语言扩展时改 DB）
6. **menu_id**：本 ticket 不挂 admin 菜单（NEWS-003 才挂，段 8000-8099）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 内容字段用 MEDIUMTEXT 不是 LONGTEXT | 单篇富文本 ≤ 16M 够用，节省存储 |
| D2 | view_count 直接 UPDATE 不走异步队列 | V1.0 流量小（< 1000 DAU），不优化；V1.1 评估是否走 Redis 计数器 |
| D3 | 富文本清洗用 jsoup（ruoyi 已有依赖）| 不引新依赖（CLAUDE.md §6 #8）|
| D4 | 分类前端聚合"全部"tab | DB 不存"全部"伪记录，避免 UNIQUE 冲突 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | rich-text 标签限制大量 HTML 标签（如 video 内嵌） | 视频独立 `<video>` 组件渲染；富文本仅文本 + 图片 + 链接 |
| R2 | view_count 并发 UPDATE 可能丢失（高并发场景）| V1.0 接受；V1.1 流量大时切 Redis INCR |
| R3 | admin CMS（NEWS-003 D07+）未完工 → 本 ticket 联调要的 demo 数据靠手工 INSERT | 种子 DDL 已塞 3-5 条 demo，联调够用 |
| R4 | 富文本配图 URL 是否走 OSS（D02 SYS-005）| NEWS-003 admin 上传时走 OSS；本 ticket 仅读，URL 是什么就渲染什么 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
