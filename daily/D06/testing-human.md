# D06 — Testing-human（Kevin 批量人验，**留 D07 后跑**）

> ⚠️ **本清单不在 D06 当天勾**。按 Kevin 口径，D05+D06+D07 全部 mp ticket 的人验集中在 **D07 完工后一次性批量跑**（CLAUDE.md §8.2 Tier 2 异步批量）。
> 只做 AI 干不了的活：微信开发者工具真机 UI / 微信原生能力 / 产品 sense / C 设计系统主观遵循度。
> 命令式可断言为真假的（mvn / curl / vitest / mysql count）AI 已在 reports/*.md 贴 raw output，这里不重复。
> AI 侧状态：6 ticket 全 ✅（Tier 1A + 代跑 Tier 1B + 主线程权威复核全绿，见 progress.md）。

---

## 0. 环境

- 后端：`cd code/main/RuoYi-Vue-Plus && mvn spring-boot:run -pl ruoyi-admin`（先手工跑 progress.md 列的 4 个 DDL + flush Redis 字典缓存）
- 小程序：`cd code/main/miniapp && pnpm dev:mp-weixin` → 微信开发者工具打开 `dist/dev/mp-weixin`
- 登录态：先走微信登录（SYS-002）拿到 token

---

## 1. ticket 验收清单（6 个，全 mp）

### GZ-USER-001 — mp 会员中心首页（「我的」tab）
- [ ] 「我的」tab 头像 / 昵称显示（已登录 → 真实 getMe 数据；未登录 → 「点击登录」占位，点击触发 useAuth）
- [ ] 资产条占位（钱包「—」/ 优惠券 0 / 谷币 0 / 收藏 0），无等级/签到/邀请好友（按 PRD 删，doc/12 §7 偏差 D4）
- [ ] 九宫格入口跳转全部有效：我的订单→`/pages/me/orders`、**我的预约→`/pages/bean/my-list`**（D05 实际路由，重点验）、地址簿→`/pages/me/address/list`、关于→`/pages/me/about`
- [ ] 关于页：版本号 + 合规备案 + 服务协议链接显示
- [ ] C 设计系统遵循（报头风 / 粗墨边 / 硬投影 / 朱红选中）

### GZ-USER-002 — mp 个人资料编辑
- [ ] 进 `/pages/me/profile`，昵称 input / 头像点击上传 / 手机号编辑
- [ ] **头像上传**（微信原生 chooseAvatar / chooseImage → OSS）→ 保存后头像更新（真机能力）
- [ ] **手机号编辑**（wx.getPhoneNumber 或 bind-mobile 链路）→ 保存落库（真机能力）
- [ ] 保存后落库：`SELECT * FROM gz_user_audit_log ORDER BY id DESC LIMIT 1`（应多 1 条审计记录）
- [ ] 改 useAuth 后**拼豆登录冒烟**：退登 → 重登 → 进拼豆预约登录态正常（R6 回归）

### GZ-USER-003 — mp 地址簿 CRUD
- [ ] `/pages/me/address/list` 列表（默认地址置顶 + 普通地址）
- [ ] 新增：右上「新增」→ edit 页 → 收件人 + 手机号 + **省市区联动 picker**（uni 原生 region picker）+ 详细地址 → 保存
- [ ] 编辑 / 删除（软删）
- [ ] **设为默认唯一性**：A 设默认 → 再把 B 设默认 → A 自动取消默认（事务内 reset，重点验）
- [ ] 越权防护：只能看/改自己的地址（AI 已单测覆盖，真机抽验）

### GZ-USER-004 — mp 我的订单 tab 占位
- [ ] `/pages/me/orders` 3 子 tab = 全部 / 扭蛋 / 预购，**无拼豆 tab**（doc/12 §7 偏差 D3）
- [ ] 3 子 tab 全部显示占位「暂无订单，敬请期待 V1.1」，不发任何请求
- [ ] 预约数据**不混在这里**（独立「我的预约」走 USER-001 九宫格 → bean/my-list）

### GZ-NEWS-001 — mp 文章列表 + 详情 + 分类 + 首页接真数据
- [ ] `/pages/news/list` 顶部分类 tab = **全部 + 新品 + 活动 + 攻略 + 公告（5 个）**，切换分页正常（仅 published，按 publish_time desc）
- [ ] 详情 `/pages/news/detail?id=` 富文本渲染 + 视频（有 video 时原生 `<video>` 可播）
- [ ] 阅读量 +1（进详情 → DB `read_count` 自增）
- [ ] **首页资讯卡显示真实文章**（首页 onShow 拉 list?pageSize=3 最新 3 条；「更多资讯」→ list；点卡 → detail）— 重点验「无残留 mock」
- [ ] 详情底部无评论入口（V1.0 删，doc/12 §7 偏差 D7），保留点赞/收藏 UI 占位（点 toast「敬请期待」）

### GZ-NEWS-002 — mp 文章分享
- [ ] 详情页「分享给朋友」（onShareAppMessage 自定义卡片：标题 + 摘要 + 封面）→ 转发卡正常（真机）
- [ ] 「分享到朋友圈」（onShareTimeline，需右上「…」菜单 → 引导弹窗）→ 朋友圈卡正常（真机）
- [ ] 分享后计数 +1：DB `gz_news_article.share_count` 自增（埋点，mp 用户不可见）

---

## 2. 跨 ticket 联调

- [ ] 微信登录 → 我的 tab 显示真实头像/昵称 → 进个人资料编辑保存 → 返回我的 tab 数据已更新
- [ ] 我的 tab 九宫格「我的预约」→ bean/my-list（D05 列表）→ 详情 → 整条会员中心 ↔ 拼豆链路通
- [ ] 首页资讯卡 → 资讯列表 → 详情 → 分享，整条资讯链路通

---

## 3. 视觉 / 文案 review（C 设计系统遵循度，仅 mp）

- [ ] me / news 各页遵循 C 系统（粗墨边 / 硬投影 / 朱红主色 / 网点 / 报头风），以 doc/tokens.md + doc/13 为准，不纠结逐像素
- [ ] 主 CTA / 选中态 / 价格用 `var(--c-red)`；页面不硬编码 hex；用 Biz* 组件不裸撒 wd-*
- [ ] i18n：可见中文无硬编码漏网（走 t('user.xxx') / t('news.xxx')）；emoji 没乱用；文案无机翻味

---

## 判定回填

- ✅ OK → progress.md「人验」列标 ✅
- ❌ NOT OK → 在 `tickets/<TICKET>.md` 的 `§revision` 段写「问题 N：现象 / 期望」→ `@coder 修 D06/<T> revision 段` → 下轮再验
