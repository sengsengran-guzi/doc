# GZ-NEWS-003 — 后台资讯 CMS（富文本编辑）

**优先级**: P0
**复杂度**: M
**关联 PRD**: doc/02-prd.md M6 §关键页面（后台）+ M7.6 资讯管理
**关联拆解**: doc/02-需求拆解.md §2.5 第 519-530 行
**关联 mockup**: design/mockup/admin-news.html（编辑器形态 — 仅布局参考；admin 走 ruoyi/Element Plus 默认审美，不套用 C 系统；列表形态 mockup 缺口，admin 列表直接用 plus-ui BizTable 默认）
**关联 ADR**: —（如富文本编辑器选型有分歧可新建 ADR-0002）
**依赖**: GZ-SYS-005 ✅(D02) ｜ NEWS-001/002（D06 完工，gz_news_article 基础字段已落）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§5 资讯发布流（M6，V1.0）全文**，特别是：
  - §状态机（draft → scheduled → published → offline → published 5 态完整定义）
  - §关键节点 步骤 1-5（甲方运营 admin 端创建 → 编辑 → 立即发布 / 定时发布）
  - §异常分支（富文本 XSS / 外站链接 / 图片体积超限）
- **字段表**：doc/11-字段权威表.md **§5.1 `gz_news_article`**（NEWS-001 已落基础，本 ticket 按需 ALTER 补 CMS 编辑字段）+ §5.3 `gz_file_object`（封面 / 内嵌图 file_id 关联）+ 附录 A.4（状态枚举）+ 附录 A.11（分类字典）
- **UI 参考**：
  - admin ticket：doc/12-UI-权威索引.md §AD-NEWS-LIST-EDIT — 列表 + 富文本编辑 + 定时发布；admin 走 ruoyi/Element Plus 默认审美（不套用 C 系统），**仅参考字段 / 表单结构**；列表态走 plus-ui BizTable 默认
  - mp ticket：N/A（本 ticket 仅 admin，mp 渲染在 NEWS-002 D06 已完工）

## What

admin 端落「资讯管理」模块：
1. 文章列表：分页 + 筛选（分类 / 状态 / 标题模糊）+ 列展示（标题 / 分类 tag / 状态 tag / 发布时间 / 阅读量 / 操作）
2. 新建 / 编辑文章：富文本编辑器（标题 / 摘要 / 封面图 / 分类 / 正文 HTML / 视频 URL / 定时发布时间 / 置顶 / 排序）
3. 状态切换：draft → published（立即发布）/ scheduled（定时发布，NEWS-004 cron 处理）/ offline（下架）/ offline → published（重新上架）
4. 富文本节点白名单 + XSS 过滤（jsoup Safelist），落库前过滤一次，不存原始未过滤 HTML

## AC（验收标准）

- [ ] **AC 1**：DDL `V202606041000__GZ-NEWS-003-alter-gz_news_article-cms-fields.sql` — 按 doc/11 §5.1 与 NEWS-001 已落字段对账，ALTER 补缺：`schedule_publish_time DATETIME(3) NULL` + idx / `content_html MEDIUMTEXT NOT NULL` / `video_urls VARCHAR(1024) NULL` / `is_pinned TINYINT NOT NULL DEFAULT 0` + idx / `sort_no INT NOT NULL DEFAULT 0`（如 NEWS-001 已落则跳过该字段，§0 自检确认）；status enum 扩展至 5 态（含 `scheduled`）
- [ ] **AC 2**：admin 端 RESTful API（路径 `/system/gz/news/article` + sa-token user 权限 `gz:news:article:list/add/edit/delete/publish/offline`）：
  - `GET /list`（分页 + 筛选）/ `GET /{id}` / `POST /` / `PUT /` / `DELETE /{id}`（逻辑删 status='offline' + del_flag=1，物理删仅 staff 上 owner 权限可）
  - `POST /publish/{id}`（draft → published，写 publish_time = now）
  - `POST /schedule/{id}`（draft → scheduled，写 schedule_publish_time，校验 > now）
  - `POST /offline/{id}`（published → offline）
  - 写操作加 `@Log(title="资讯文章", businessType=...)`
- [ ] **AC 3**：富文本编辑器 — admin 编辑页 `views/gz-news/article/edit.vue` 集成 wangEditor v5（如 plus-ui 已集成其他编辑器则复用，**不引新依赖优先**）：
  - 工具栏：标题 / 加粗 / 斜体 / 列表 / 引用 / 链接 / 图片 / 视频 / 分割线 / 清除格式
  - 图片上传走 SYS-005 `/system/gz/file/upload` API，sceneTag=`news_inline`，返回 file_id → 编辑器插入 `<img src="${signed_url}" data-file-id="${fileId}">`
  - 视频 URL 块（不支持上传视频文件，仅录入 URL）
  - 字数 / 阅读时长实时统计
- [ ] **AC 4**：**XSS 白名单过滤**（落库前服务层强制）：
  - 用 jsoup `Safelist.relaxed()` 作为基准白名单
  - 额外去除 `<script>` / `<iframe>` / `<object>` / `<embed>` / `<form>` / 所有 `on*` 事件属性 / `javascript:` 协议链接
  - 外站 `<a href>` 限制：白名单域名（甲方公司域 + 微信生态域）以外的 href → 转 text 或加 `rel="nofollow noopener"`
  - 服务层 `GzNewsArticleServiceImpl.sanitizeHtml(rawHtml)` 单元，单测覆盖至少 5 个 XSS payload（含 `<script>alert(1)</script>` / `<img onerror=alert(1)>` / `<a href="javascript:void(0)">` / `<iframe src=...>` / `<svg onload=alert(1)>`）
- [ ] **AC 5**：admin 列表页 `views/gz-news/article/list.vue` — plus-ui BizTable 默认风格：
  - 列：标题 / 分类（dict tag）/ 状态（dict tag）/ 发布时间 / 阅读量 / 操作（编辑 / 发布 / 下架 / 删除）
  - 筛选：分类 select / 状态 select / 标题 input / 时间范围
  - 工具栏：「新建文章」按钮 → 跳 edit.vue
  - 置顶项行高亮（is_pinned=1 → 行加 `el-tag` 红角标 + 排序优先）
- [ ] **AC 6**：menu_id 插入 — admin 端「资讯管理 → 文章列表」menu_id **8001** + perms `gz:news:article:{list,add,edit,delete,publish,offline}`（DDL 内 INSERT sys_menu + sys_role_menu 给 owner / staff 角色）
- [ ] **AC 7**：单测 `GzNewsArticleServiceImplTest` ≥ 4 个测试方法：
  - happy path（新建文章，draft 状态）
  - publish 流转（draft → published，publish_time 自动填）
  - sanitizeHtml XSS 拦截（参数化 5 个 payload）
  - schedule 状态校验（schedule_publish_time ≤ now → 抛业务异常）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-news/`
  - `controller/GzNewsArticleController.java`（admin 路径 `/system/gz/news/article`）
  - `service/IGzNewsArticleService.java` + `service/impl/GzNewsArticleServiceImpl.java`（业务核心 + sanitizeHtml）
  - `service/internal/HtmlSanitizer.java`（jsoup 封装，独立 Bean 便于 mock + 测试）
  - `domain/GzNewsArticle.java` + `domain/bo/GzNewsArticleBo.java` + `domain/vo/GzNewsArticleVO.java`
  - `mapper/GzNewsArticleMapper.java`（如 NEWS-001 已建则复用，本 ticket 仅新增 admin 端查询方法）
  - DDL × 1（ALTER）
  - pom 加 `org.jsoup:jsoup:1.17.2`（如已传递依赖于 ruoyi 则跳过；§0 自检 `mvn dependency:tree` 确认）
- **Admin**：`plus-ui/src/views/gz-news/article/`
  - `list.vue`（BizTable 默认）
  - `edit.vue`（富文本编辑器集成 + 表单 + 状态切换按钮）
  - `api/gz-news/article.ts`（CRUD + publish/schedule/offline 接口封装）
  - 编辑器组件：优先复用 plus-ui 已集成的；如无则 `pnpm add @wangeditor/editor @wangeditor/editor-for-vue@next`（写 ADR-0002 记录选型）
- **小程序**：本 ticket 不动 mp 端（NEWS-001/002 D06 已完工，本 ticket 数据流向 mp）
- **测试**：mvn 单测 + admin 浏览器实操（新建 / 编辑 / 发布 / 下架 / XSS payload 粘贴）

## 备注

### 强约束

1. **富文本落库前必过 sanitizeHtml**（不存原始未过滤 HTML，doc/11 §5.1 `content_html` 字段备注权威）
2. **图片必走 SYS-005 上传**（不允许 base64 内嵌大图 / 不允许第三方外链图片直接 `<img src>` — 编辑器粘贴外链图自动 reject + toast）
3. **status 枚举严格 5 态**（draft / scheduled / published / offline；附录 A.4 锚定）；不允许直接 DB 更新跳态（必须走 service 方法）
4. **逻辑删 ≠ offline**：offline 是业务下架（mp 不显示但 admin 可重新上架）；DELETE 走 ruoyi del_flag（数据保留但 admin 列表过滤）
5. **置顶 + 排序联合**：mp 端 NEWS-001 列表查询时 `ORDER BY is_pinned DESC, sort_no DESC, publish_time DESC`（与 D06 NEWS-001 mapper 对齐，§0 自检确认）
6. **schedule_publish_time 必须 > now**（业务校验，前后端双 check；定时发布 cron 在 NEWS-004 实现）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 富文本编辑器优先复用 plus-ui 已集成的；备选 wangEditor v5 | 不引未澄清新依赖（CLAUDE.md §6 #8）；wangEditor v5 中文文档 + 体积合理 + 与 Element Plus 风格协调 |
| D2 | sanitizeHtml 用 jsoup `Safelist.relaxed()` + 额外规则 | jsoup 是业界标准 HTML 清洗库，relaxed 模式保留常用富文本节点（h1-h6 / table / a / img），额外规则去除已知危险节点 |
| D3 | content_html 用 MEDIUMTEXT（16MB）| 一般文章 < 100KB 足够；预留视频说明长正文场景 |
| D4 | 不存原始未过滤 HTML | 简化模型；若需保留原始历史可后续加 `gz_news_article_revision` 表（v2 候选）|
| D5 | 图片 file_id 关联存在 content_html 的 `data-file-id` 属性中 | 后续清理孤儿文件 cron（v2）可正则提取 file_id 反查 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 编辑器组件未在 plus-ui 集成 → 需引 wangEditor 新依赖 | 走 ADR-0002 决策；wangEditor v5 在主流 Vue3 后台体系（包括 ruoyi 社区方案）广泛使用，引入风险低 |
| R2 | XSS 白名单过严 → 正常排版（如 inline style）被剥离 | 与 Kevin 确认白名单粒度；初版严格，后续按运营反馈放宽（业务运营人员可信，主要防外部投稿） |
| R3 | 富文本编辑器粘贴 Word / 网页内容 → 大量冗余 inline style | wangEditor 自带"粘贴纯净化"开关，默认开启；运营复制 Word 时弹提示「建议清除格式」|
| R4 | 阅读量 read_count V1.0 不防刷（doc/11 §5.1 备注）| 接受 — 运营自己刷不影响业务；防刷 v2 候选 |
| R5 | mockup admin-news.html 仅编辑器形态，列表形态缺口 | 列表用 plus-ui BizTable 默认形态（doc/12 §AD-NEWS-LIST-EDIT 已裁定接受）；admin 走 ruoyi/Element Plus 默认审美，若客户不满意再加列表 mockup |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
