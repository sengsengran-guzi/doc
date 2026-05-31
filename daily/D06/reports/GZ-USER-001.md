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
