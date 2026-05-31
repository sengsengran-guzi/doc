# GZ-NEWS-002 — mp 文章分享（微信好友 / 朋友圈）

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M6 §用户操作流程 步骤 4
**关联拆解**: doc/02-需求拆解.md §2.5 第 505 行
**关联 mockup**: design/mockup/news-detail.html（顶部分享按钮 — 仅布局参考；视觉以 C 设计系统为准，doc/13）
**关联 ADR**: —
**依赖**: GZ-NEWS-001

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§5 资讯发布流** §分享分支（分享卡片字段 / 朋友圈限制 / 分享计数埋点）
- **字段表**：doc/11-字段权威表.md **§5.1 `gz_news_article`**（增量字段 `share_count` 本 ticket 写，如 NEWS-001 已落则复用）
- **UI 参考**（视觉走 C 日漫海报浓墨：页面用 Biz* 组件 + var(--c-*)，见 doc/tokens.md + doc/13；旧 mockup 仅作布局参考，以 c-tokens.scss 的 rpx 为准）：doc/12-UI-权威索引.md **§MP-NEWS-DETAIL** + mockup `news-detail.html` 顶部分享按钮

## What

用户从文章详情分享到微信（好友 / 朋友圈）；自定义分享卡片（封面 + 标题 + 摘要）；朋友圈走小程序原生 `onShareTimeline`；分享数计数（埋点，不展示给 C 端）。

## AC（验收标准）

- [ ] **AC 1**：mp 端 `/pages/news/detail` 加 `onShareAppMessage()` 钩子返回自定义分享卡片：
  - title: 文章 title
  - path: `/pages/news/detail?id=<articleId>&from=share`
  - imageUrl: 文章 cover_url（OSS URL，无则走默认占位图）
- [ ] **AC 2**：加 `onShareTimeline()` 钩子返回朋友圈分享配置：
  - title: 文章 title
  - query: `id=<articleId>&from=timeline`
  - imageUrl: cover_url
- [ ] **AC 3**：顶部分享按钮（UI 上 2 个按钮：分享给朋友 + 分享到朋友圈）—— 微信限制 `onShareAppMessage` 必须用户主动触发，按钮用 `<button open-type="share">` 触发好友分享；朋友圈分享走右上"…"系统菜单（mp 限制，不能脚本触发）→ 朋友圈按钮 UI 实际是引导用户去右上菜单（提示弹窗）
- [ ] **AC 4**：分享计数（埋点）：用户成功分享后（onShareAppMessage 触发即视为"分享尝试"）调 `POST /app/gz/news/article/{id}/share` → `UPDATE gz_news_article SET share_count = share_count + 1`；count 字段不暴露给 C 端
- [ ] **AC 5**：分享后落地页（path 带 `from=share|timeline`）→ NEWS-001 detail 页 mount 时如有 `from` 参数则上报埋点 `article_share_landing`（V1.0 仅 log，不入业务表）
- [ ] **AC 6**：i18n 走 `t('news.share.xxx')`（朋友圈引导弹窗文案）
- [ ] **AC 7**：单测覆盖：share_count 增量接口 happy path + 防刷（同一 user 同一 article 5 分钟内多次分享只 +1，可选）

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-news/`
  - 在 `GzNewsArticleMpController.java` 加 `POST /share` 接口
  - 在 `GzNewsArticleServiceImpl.java` 加 `incrementShareCount(articleId)` 方法
  - DDL：**本 ticket 不写 DDL**（share_count 字段在 NEWS-001 已落）
- **小程序**：`code/main/miniapp/src/`
  - `pages/news/detail.vue` 加 `onShareAppMessage` / `onShareTimeline` 钩子 + 顶部分享按钮 UI
  - `api/gz-news.ts` 加 `incrementShareCount(articleId)`
  - `locales/zh_CN/news.ts` 加 share 段
- **测试**：mvn 单测 + mp 端微信开发者工具实操（触发分享菜单 → 检查卡片内容）

## 备注

### 强约束

1. **朋友圈分享微信限制**：`onShareTimeline` 必须用户从右上"…"菜单触发，**前端按钮 UI 仅引导**（无法脚本触发系统菜单）
2. **`onShareAppMessage` 必须用户主动触发**：`<button open-type="share">` 或右上菜单；前端代码内不能脚本调用
3. **分享封面用 OSS 已有图不动态绘制 canvas**（合同 §2.1 V1.0 范围 + 性能考量）
4. **share_count 不暴露给 C 端**：后端 VO 不返回该字段；仅 admin 端可见（NEWS-003 D07+ 落地）
5. **i18n 强制**：朋友圈按钮引导弹窗 + 分享文案走 `t('news.share.xxx')`

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 朋友圈走原生 onShareTimeline 不做生成图分享 | 合同 V1.0 范围 + 实现成本低；动态图分享延后到 v2 |
| D2 | share_count 入 gz_news_article 增量字段而非单独埋点表 | 减少 V1.0 表数量；后续如需分析用户级分享行为再单独建埋点表 |
| D3 | 防刷可选 | V1.0 流量小，先简单实现；V1.1 流量上来再加 Redis 防刷 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 用户可能不知道朋友圈分享要从右上菜单 → UX 困惑 | 朋友圈按钮点击弹引导提示「请点击右上角…菜单 → 分享到朋友圈」 |
| R2 | 分享卡片图片低端机渲染慢 / OSS 图过大 | cover_url 必须走 OSS + 已压缩；超过 200KB 的图 admin 端 NEWS-003 上传时强制压缩 |
| R3 | 分享带参 `from=share|timeline` 是否真到落地页 | 微信 mp 路径参数原生支持，AC 5 验收 from 参数能读到即可 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
