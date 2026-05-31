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
