# D06（Kevin 口径 d5）— 会员中心收尾 + 资讯 C 端

> 日期：2026-06-03（周三）
> 阶段：V1.0 实施期 day 5
> 上一日：[D05](../D05/README.md) ｜ 下一日：[D07](../D07/README.md)

---

## 今日目标

- **主线 1**（会员中心 4 ticket）：mp 端「我的」tab 一次性把首页 + 个人资料编辑 + 地址簿 CRUD + 订单 tab 占位四件套全部立起（GZ-USER-001/002/003/004）
- **主线 2**（资讯 C 端 2 ticket）：mp 端资讯主路径 = 文章列表（4 分类 tab）+ 详情（富文本/视频）+ 微信分享（GZ-NEWS-001/002）
- **主线 2.5**（首页接真数据，随 NEWS-001 收尾，不单开 ticket）：首页 `pages/index/index.vue` 已存在（脚手架期已建好的 C 系统报头 + 拼豆 hero + 资讯卡 + 扭蛋/预购 teaser），但**资讯区现在是硬编码占位**。NEWS-001 落地资讯列表接口后，把首页资讯区接真实 `GET /app/gz/news/article/list`（取前 3 条按热度/时间），首页「更多资讯」跳资讯列表页。算 NEWS-001 的一条 AC。

**完工后 mp 端 C 端主体功能（首页 / 拼豆 / 我的 / 资讯）全部 functionally complete**（拼豆 D05 已闭环；订单 tab 是 V1.1 占位）。剩余 V1.0 任务只剩 **D07 后台收官**（资讯 CMS + 数据看板 + 支付通道 + V1.0 集成回归）。即 **D06 末 = C 端可整体走查；D07 末 = V1.0 30 ticket 全闭环**（Kevin 在 D07 后做一次批量人验，见 §人验口径）。

## Ticket 清单（6 个，按依赖图）

| Ticket | 标题 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|
| GZ-USER-001 | mp 会员中心首页 | S | GZ-SYS-002 ✅(D02) | pending |
| GZ-USER-002 | mp 个人资料编辑 | S | GZ-SYS-002 ✅(D02) + GZ-SYS-005 ✅(D02) | pending |
| GZ-USER-003 | mp 地址簿 CRUD | S | GZ-SYS-002 ✅(D02) | pending |
| GZ-USER-004 | mp 我的订单 tab 占位结构 | S | GZ-USER-001 | pending |
| GZ-NEWS-001 | mp 文章列表 + 详情 + 分类 | M | GZ-SYS-005 ✅(D02) | pending |
| GZ-NEWS-002 | mp 文章分享 | S | GZ-NEWS-001 | pending |

详见 `tickets/<TICKET-ID>.md`（任务卡）+ `reports/<TICKET-ID>.md`（完工后）。

**依赖说明**：
- **第一波串行起点**：GZ-USER-001（会员中心首页骨架，是 USER-004 的 tab 容器）
- **第一波并行**：GZ-USER-001 ✅ 后，USER-002 / USER-003 / USER-004 三个 ticket 互不依赖，可并行 spawn 3 个 subagent
- **第二波串行**：GZ-NEWS-001（列表 + 详情）→ GZ-NEWS-002（分享，依赖详情页 onShareAppMessage 钩子）
- 两波之间互不阻塞，可同时进行（USER 4 ticket 跑后端 + mp，NEWS 2 ticket 也跑后端 + mp，互无 schema/包冲突）

## 派单方式

**整日触发**（推荐）：
```
开始 d5
```

**单 ticket 触发**（局部 revision / 重做）：
```
@coder 做 D06/GZ-USER-002
```

主线程动作：
1. 读 D06/README.md（本文件）+ 依赖图
2. **第一波**：先派 GZ-USER-001（独立先跑）→ ✅ 后并行 spawn USER-002 / USER-003 / USER-004
3. **第二波**：同时（或第一波启动后）串行 spawn NEWS-001 → NEWS-002
4. 6 个 ticket AI Tier 1A+1B 全 ✅ → ticket close（mp 6 个全进 progress.md「人验」列）→ 日终 closing（写 summary，**不 commit**）。**Kevin 人验不在本日**——D05/D06 的 mp ticket 累积，D07 完工后一次性批量人验（见 §人验口径）

## 今日特殊约束

- **C 设计系统纪律**（CLAUDE.md §7.5）：mp 端 6 个 ticket 全部走 C 日漫海报浓墨 —— 页面用 Biz* 原子组件（标签→BizTag / 按钮→BizButton / 卡片→BizPanel / 列表项→BizPanel，不直接撒 wd-*）+ var(--c-*) token，主 CTA = var(--c-red)，不硬编码 hex（doc/tokens.md + doc/13），**不强求 mockup 逐像素还原**。已切 C 系统，视觉以 doc/tokens.md + doc/13 为准；Kevin testing-human 阶段 mp 视觉遵循 C 设计系统（粗墨边 / 硬投影 / 朱红主色 / 网点 / 报头风），不纠结逐像素
- **mockup 缺口处理**（doc/12 §5.1 排 3 + §7 偏差）：
  - `me-profile.html` mockup 当前已存在于 design/mockup/（doc/12 §5.1 排 3 标"待新画"是历史记录），USER-002 直接参考该文件
  - me-home mockup 含 PRD 外内容（等级 LV3 / 签到 / 邀请好友 — doc/12 §7 偏差 D4）：实施时按 PRD 删，保留收藏 UI 占位（数字 0）
  - order-list mockup 含 4 tab 含拼豆 — doc/12 §7 偏差 D3：USER-004 按 PRD 删拼豆 tab，仅保留 3 tab（全部 / 扭蛋 / 预购）
  - news-detail mockup 含点赞/收藏/评论底部 toolbar — doc/12 §7 偏差 D7：NEWS-001 实施时 V1.0 删评论入口，保留点赞 / 收藏 UI 占位
- **i18n 强制**：6 个 ticket 全部 mp 端字符串走 `t('user.xxx')` / `t('news.xxx')` + zh-CN 默认；不允许硬编码中文
- **路径前缀约定**（CLAUDE.md §6）：mp 端全部 `/app/gz/user/...` / `/app/gz/news/...`（走 sa-token mp-client）
- **USER-004 业务边界**（合同 §2.1 第一期 + PRD M5）：
  - 订单 tab 3 个子 tab（全部 / 扭蛋 / 预购）全部占位文案「暂无订单，敬请期待 V1.1」
  - **预约数据不混在订单 tab**（独立"我的预约"入口走 GZ-BEAN-006，D05 已完工）
  - 数据契约层预留订单聚合接口 `/app/gz/user/orders/list?type=...`，V1.1 直接接入
- **NEWS-001 分类硬约束**：4 类固定（全部 / 新品 / 活动 / 攻略），admin 端可在 v2 扩；V1.0 分类表只允许这 4 条记录（DDL 种子数据），UI 显示「全部」tab 不入库（前端聚合）
- **NEWS-002 朋友圈分享**：必须用小程序原生 `onShareTimeline()` 钩子（微信限制），自定义分享卡片走 `onShareAppMessage()`；分享数计数表如 doc/11 §5 未列则 NEWS-002 ticket 内确认 schema 后写 DDL（建议增量字段 `gz_news_article.share_count` 而不是单独表，减少 V1.0 表数量）
- **menu_id**：USER 域 7000-7099 / NEWS 域 8000-8099（CLAUDE.md §6 #6）；本日 admin 端 0 改动，但 NEWS-001 落 DDL 时种子分类数据不挂菜单（admin CMS 在 GZ-NEWS-003 D07 才挂）
- **§人验口径（本批 D05+D06+D07 统一批量人验，放 D07 后）**：Kevin 明确**本批 mp 人验集中在 D07 完工后跑一次**（CLAUDE.md §8.2 Tier 2 异步批量，不每日跑）。所以本日 6 个 ticket 只走 AI Tier 1A+1B gate → 全 ✅ 即 close 解锁下游 + 进 progress.md 人验列；**不在 D06 单独打断 Kevin 做人验**。AI 测试 ❌ → 闭环回 coder 修，不惊动 Kevin
- **不要 commit**：D05/D06/D07 全部 AI ✅ + Kevin D07 后批量人验通过后，再统一 commit（注意项目当前非 git repo，commit 前需先 `git init`）

## 与昨日 reports 对账（D05）

D05 已完工（拼豆收尾 — 详情 / 预约列表 / 取消 / 核销 / admin / 首页），本日依赖的实际产物：
- ✅ GZ-BEAN-006「我的预约」列表页**实际路由 = `/pages/bean/my-list`**（不是早期假设的 `/pages/me/bookings/list`）→ 本日 USER-001 会员中心九宫格「我的预约」入口 `uni.navigateTo('/pages/bean/my-list')`，**别再用旧路由**
- ✅ 拼豆首页 `/pages/bean/index`（BEAN-010）已是「拼豆」tab 落地页；首页 `pages/index/index.vue` 的拼豆 hero 跳它（已接）
- ✅ GZ-SYS-005 文件上传服务 D02 已就位（dev MinIO / prod 切腾讯云 COS，合同附件二）→ USER-002 头像上传 + NEWS-001 富文本配图直接复用现有上传封装
- ⚠️ D05 经验：D04 曾"超额交付"（后端接口比 ticket 卡假设的更全），**本日 coder §0 自检务必先核实 gz-user / gz-news 后端是否已有现成 controller/service**（D02/D03 可能已搭了部分），避免重复造或找不存在的类

## 完成判定（DoD）

> 本日 DoD = **AI 侧全绿即收官**；下面的 testing-human 项由 coder 预填进 `testing-human.md`，**留给 D07 后 Kevin 批量人验**勾（不在 D06 当天跑）。

- [ ] 6 个 ticket 任务卡 §revision 段空（无未闭环问题）
- [ ] 6 个 reports/<T>.md 写完（含 §0 自检 + §N 完工 + ≥ 3 个代码 block 自测 raw output）
- [ ] mvn install + plus-ui build:prod + miniapp dev:mp-weixin 三端全绿
- [ ] 6 个 ticket AI Tier 1A+1B 全 ✅ → close + 进 progress.md 人验列
- [ ] 首页资讯区已接真实接口（NEWS-001 AC，不再硬编码占位）
- [ ] cat reports/*.md > summary.md 已生成
- [ ] **testing-human.md 已预填**（不勾）以下供 D07 后批量人验：
  - mp「我的」tab 头像 / 昵称 / 九宫格入口全部跳转有效（「我的预约」→ `/pages/bean/my-list`）
  - 个人资料：昵称 / 头像 / 手机号编辑保存后落库（gz_user_audit_log 多 1 条记录）
  - 地址簿：新建 + 编辑 + 删除 + 设为默认；默认地址唯一（再设另一条 → 上一条自动取消默认）
  - 订单 tab 3 子 tab 全部显示「暂无订单，敬请期待 V1.1」占位
  - 资讯列表 4 分类 tab 切换正常；详情富文本 + 视频可播；首页资讯卡显示真实文章
  - 资讯详情「分享给朋友」+「分享到朋友圈」两按钮可触发；分享计数 +1

## 已知风险

| # | 风险 | 缓解 |
|---|---|---|
| R1 | USER-002 手机号编辑触发 `wx.getPhoneNumber` 需 session_key 解码（D02 SYS-002 已落库）— 若 session_key 过期（微信 7 天 TTL）→ 解码失败 | USER-002 实施时检测 session_key 过期 → 引导用户重新登录（弹「登录已过期，请重新授权」+ 自动调 useAuth re-login）；不强求当前 ticket 完美处理边界 |
| R2 | USER-003 地址 CRUD 在 mp 端 UI 复杂（省市区联动）→ wot-design-uni `wd-picker` 城市数据集是否够用 | 优先用 wot-design-uni 内置城市数据；如不全 → 先报 Kevin 决策是否引入 `area-data` 库（CLAUDE.md §6 #8 不引未澄清依赖） |
| R3 | NEWS-001 富文本渲染 mp 端用 `rich-text` 标签限制大量 HTML 标签（如 video / iframe）| 视频用微信原生 `<video>` 组件或外链 H5 跳转；admin 端富文本输出走白名单清洗，禁止注入危险标签 |
| R4 | NEWS-002 朋友圈分享卡片图低端机生成慢 / 失真 | 用 OSS 已有图作为分享封面（不动态绘制 canvas）；标题 + 摘要走文本 |
| R5 | USER-004 占位 tab 在 V1.1 真接入时如果数据契约不一致 → 大改 | 本日定接口 schema：`OrderListVO { orderId, type, amount, status, createdAt }`，V1.1 直接接入；任务卡里写明 V1.1 onboarding 提示 |
| R6 | mp 端 6 个 ticket 同日大量改动可能引入回归（如 D02 useAuth composable 被 USER-002 改后 D04/D05 拼豆登录受影响）| AI 自测覆盖：USER-002 改 useAuth 前先跑一遍拼豆登录冒烟（mvn 集成测试 / mp 端 vitest）|

---

## 日终 closing 命令

```bash
cd doc/daily/D06
cat reports/*.md > summary.md
# 本批不 commit：等 D07 完工 + Kevin 批量人验通过后，D05+D06+D07 一起 commit（commit 前先 git init）
# D07/README.md 已就位（资讯 CMS + 看板 + 支付通道 + V1.0 集成回归）→ 直接「开始 d6」进 D07
```
