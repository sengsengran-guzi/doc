# D06 — Progress

> 会员中心收尾 + 资讯 C 端日。6 ticket 全部 AI Tier 1A ✅ + 主线程权威复核全绿。
> 6 个均 mp ticket → 进「人验」列累积，**留 D07 后批量人验**（Kevin 口径，CLAUDE.md §8.2 Tier 2 异步批量，不每日跑）。
> ⚠️ kevin-qa 未独立 spawn（subagent 嵌套限制）：Tier 1B 由 coder 代跑 + 主线程独立核对（契约回归 / 可达性 / 全量重跑），见下「Tier 1B 说明」。

---

| Ticket | 标题 | AI Tier 1A | AI Tier 1B | testing-human | revision | 状态 |
|---|---|---|---|---|---|---|
| GZ-USER-001 | mp 会员中心首页 | ✅ build+vitest(MeHeader 8) | ✅ 全量 103 回归 + 可达性 | ⬜ 待批量人验（九宫格 5 入口跳转） | 0 | ✅ AI done，进人验列 |
| GZ-USER-002 | mp 个人资料编辑 | ✅ mvn+单测 6 + DDL 导入 | ✅ 契约对齐 + 可达性 | ⬜ 待批量人验（昵称/头像/手机号落库） | 0 | ✅ AI done，进人验列 |
| GZ-USER-003 | mp 地址簿 CRUD | ✅ mvn+单测 9（越权+默认唯一性） | ✅ 6 端点契约 + 可达性 | ⬜ 待批量人验（增/改/删/设默认） | 0 | ✅ AI done，进人验列 |
| GZ-USER-004 | mp 我的订单 tab 占位 | ✅ build+vitest（不调 API 静态保证） | ✅ 契约 VO 真源 + 可达性 | ⬜ 待批量人验（3 子 tab 占位文案） | 0 | ✅ AI done，进人验列 |
| GZ-NEWS-001 | mp 文章列表+详情+分类+首页接真数据 | ✅ mvn+单测 19 + DDL 导入(5 文章/4 类) | ✅ 全量 103 回归 + 全链路可达 | ⬜ 待批量人验（4+全部 tab/富文本/视频/首页卡） | 0 | ✅ AI done，进人验列 |
| GZ-NEWS-002 | mp 文章分享 | ✅ build+vitest（纯 mp，后端 0 改） | ✅ 全量 103 回归 + 可达性 | ⬜ 待批量人验（分享给朋友/朋友圈/计数+1） | 0 | ✅ AI done，进人验列 |

**状态枚举**：pending / in-progress / ai-testing / human-testing / revision-X / ✅ done / 🚫 blocked

---

## 主线程权威复核（DoD gate，两 track 集成后亲跑）

| 项 | 命令 | 结果 |
|---|---|---|
| 后端编译/install | `mvn install -pl ruoyi-gz-user,ruoyi-gz-news -am` | **BUILD SUCCESS**（gz-common/user/news 全 SUCCESS）✅ |
| 后端单测 | `mvn test -pl gz-user,gz-news` | **34/34**（user 15 = Profile 6 + Address 9；news 19 = Article 13 + HtmlSanitizer XSS 6）✅ |
| mp 类型检查 | `pnpm type-check` | D06 **零新增 TS 错**；仅 2 个 pre-existing 历史债（见下）✅ |
| mp 单测 | `pnpm vitest run` | **15 文件 / 103 测试全过**（零回归）✅ |
| mp 构建 | `pnpm build:mp-weixin` | ✅ 产物绿；app.json 自动注册 **6 me 页 + 3 news 页**，tabBar 正确 3-tab（验证「definePage 自动生成、不手改 pages.json」）|
| 契约回归 | 后端 controller 路由 vs mp api/*.ts | **100% 对齐**：gz-user(profile PUT + address 6 端点) / gz-news(list/{id}/view/share)；`orders/list` 后端故意未实现（USER-004 V1.0 占位，orders.vue 不 import 静态保证不调）✅ |
| 可达性（Tier 2 前置） | navigateTo grep | 我的 tab → 5 me 页（含「我的预约」→ `/pages/bean/my-list` 正确）；首页资讯卡 → list → detail → 分享；news/index 重定向兜底防死链。**无需临时入口** ✅ |

---

## Tier 1B 说明（kevin-qa 未独立 spawn — 已等效覆盖）

- **原因**：kevin-coder 在 subagent 内，Agent 工具不可用 → 无法 spawn kevin-qa（嵌套限制）。
- **覆盖方式**：① coder 代跑 Tier 1B（mp vitest 全量 / 后端单测 / 契约 / 可达性 grep / DDL 导入验证）；② 主线程独立复核（上表，契约回归 + 可达性 + 全量重跑 + 集成构建）。
- **未补派全量 kevin-qa 的判断**：D06 = 纯 mp + 后端单测，**零 admin / 零 Playwright E2E 面**；dev 后端离线 → kevin-qa 无法加跑 live API / 集成，只会冗余重跑已跑项。**如 Kevin 要正式独立 qa pass，可随时补派**。

---

## 需 Kevin 手工跑的 DDL（⚠️ Flyway 未接入 — dev MySQL 已导入验证，prod/其他环境需手工跑）

1. `V202606031000__GZ-USER-002-create-gz_user_audit_log.sql`
2. `V202606031100__GZ-USER-003-create-gz_user_address.sql`
3. `V202606031200__GZ-NEWS-001-create-gz_news_article.sql`
4. `V202606031201__GZ-NEWS-001-seed-data.sql`（含 sys_dict `gz_news_category` 4 类 + 5 篇 demo 文章）

均在 `code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/`。
**跑完 #4 后必须 flush Redis 字典缓存**（ruoyi NullValue 缓存，否则 `gz_news_category` 查空被缓存 1h）。

---

## 复盘动作（§9.5 priority-1 改权威蓝图，已落）

- **doc/11 §5.1** 补 `cover_url VARCHAR(512)` 行（mp 渲染真源 + 分享封面，免 join gz_file_object）；厘清 `cover_file_id` = admin 上传链路(NEWS-003)关联，V1.0 可空。
- **doc/11 §5.2** 补「mp 端分类 tab = 5 个」：`全部`(前端聚合,code 空) + 4 真实 code(new_product/activity/guide/announcement)，消除 ticket 卡「4 类(全部/新品/活动/攻略)」歧义（漏了「公告」、误把全部算进 4）。

---

## 阻塞 / 风险

- **dev 后端当前离线**：API curl 烟雾测试待全栈起后端补（curl 命令已在两 track reports 备好；DB 层已 dev MySQL 验证）。不阻塞 D06 收官。
- **2 个 pre-existing 类型债**（非 D06 引入，build 不阻塞，type-check exit 1）：`BizCustomerServiceFab.vue:92`（SYS-004）/ `pages/login/index.vue:35`（SYS-002）。建议开独立小 ticket 清。
- **gz-user pom 加 `spring-boot-starter-test`**（必要基建，对齐 gz-bean，新模块原无测试依赖导致 test 编译失败）。留痕。

## 给 D07 的提示

- **NEWS-003 admin CMS**：`gz_news_article` 已落 doc/11 §5.1 全字段（status 4 态 / schedule_publish_time / content_html / video_urls / share_count / cover_url + cover_file_id 双字段）→ **D07 不重复落表，按需 ALTER**；分类字典 `gz_news_category` 已种 4 类（admin 用 useDict 回显）；上线前删 `ART-20260603-%` demo 文章。
- **ADMIN-003 看板**：会员表 / 预约表 / 资讯阅读计数(read_count)已就位，数据源齐。

## 已挪到明日的 ticket

无。D06 6 ticket 全部实现完成。**下一步进 D07（V1.0 收官：资讯 CMS + 看板 + 支付通道 + 集成回归）。**
