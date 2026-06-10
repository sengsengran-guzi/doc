# GZ-SYS-010 完工报告 — tabbar 重构（去首页 → 拼豆/回收/我的 3 tab）

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（本仓库非 git repo，env 已声明 Is directory a git repo: No）|
| 上游依赖 merge | ✅ RECYCLE-002 `/pages/recycle/form` 存在；BEAN-015 拼豆付费页 `pages/bean/index` 存在；GACHA-102 `pages/gacha/index` 真列表存在 |
| 关键页/图标存在 | ✅ recycle/form / news/index / gacha/index / me/index 全在；tabbar 图标 bean/me 在，recycle 占位本卡新建 |
| type-check | ✅ 0 error |
| 关联 ADR | 无（纯导航重构，任务卡 ADR 段 = -） |
| 必读权威文档 | ✅ doc/12 §4.0（3 tab 表）+ CLAUDE.md §7.5（去首页指向 bean / 资讯·扭蛋迁我的 / 选中朱红）|

### Tier2-entry-temp grep（BEFORE → AFTER）

**BEFORE**（7 处命中）:
```
src/pages/gacha/index.vue:85   GZ-GACHA-106
src/pages/gacha/index.vue:115  GZ-GACHA-106
src/pages/gacha/index.vue:174  GZ-GACHA-106
src/pages/gacha/history.vue:14 （注释引用说明，非真 marker）
src/pages/index/index.vue:111  GZ-RECYCLE-002, remove when GZ-SYS-010 merged  ← 本卡清
src/pages/index/index.vue:181  GZ-PAY-001                                       ← 本卡清
src/pages/index/index.vue:393  GZ-PAY-001（样式）                               ← 本卡清
```

**AFTER**（剩 GACHA-106 共 3 处 + 1 注释引用，全部有意保留给 GACHA-111）:
```
src/pages/gacha/index.vue:85   GZ-GACHA-106  ← 留 GACHA-111 清（有意分工）
src/pages/gacha/index.vue:115  GZ-GACHA-106  ← 留 GACHA-111 清
src/pages/gacha/index.vue:174  GZ-GACHA-106  ← 留 GACHA-111 清
src/pages/gacha/history.vue:14 （注释引用说明，非可执行 marker）
```
→ index.vue 的 GZ-RECYCLE-002 + GZ-PAY-001（3 处）已随首页整页下线消失 = **用真入口替换**（回收升 tab2 真入口 / 资讯·扭蛋迁「我的」入口卡）。

## 实现摘要

### 改动文件（实质改动，排除 build 自动重生成的 manifest.json / async-*.d.ts / auto-import.d.ts）

| 文件 | 改动 |
|---|---|
| `src/tabbar/config.ts` | nativeTabbarList 3 tab：拼豆/回收/我的（去首页）+ 文档头重写 |
| `src/pages.json` | tabBar.list 3 tab + pages 首项 bean(type:home) + index 降 type:page（uni-pages build 时已验证一致重生成）|
| `src/static/tabbar/recycle.png` + `recycleHL.png` | 新增（占位，复用 home 图，designer 待补 C 风图标）|
| `src/pages/bean/index.vue` | definePage 加 `type: 'home'`（启动落地拼豆 tab）|
| `src/pages/index/index.vue` | **整页下线**重写为 redirect 兜底页（onLoad → reLaunch bean）；删 masthead/banner/入口格/资讯/teaser/全部临时入口 |
| `src/pages/me/index.vue` | 九宫格加「回收记录」入口；新增「发现」区（资讯 + 扭蛋入口卡）|
| `src/locale/user.zh-CN.ts` | 加 entryRecycleRecords / discoverSection* / entryNews / entryGacha |
| `src/composables/useNavGuard.ts` | GuardedTab 扩 `'recycle'`；取消/fail 兜底跳 bean（不再跳已下线 index）|
| `src/locale/common.zh-CN.ts` | 加 nav-guard.modalContentRecycle |
| `src/pages/recycle/form.vue` | 加 useNavGuard('recycle')（回收升 tab → 路由守卫）|
| `src/pages/login/index.vue` | 3 处 reLaunch + 1 switchTab：index → bean（启动落地）|
| `src/components/biz/ComingSoonV11.vue` | goHome switchTab index → bean |
| `src/pages/pay/result.vue` | goHome switchTab index → bean |
| `src/pages/ord/pay-result.vue` | fallback switchTab index → bean |
| `src/pages/gacha/history.vue` / `me/order-detail.vue` / `me/collection.vue` / `me/staff-orders/detail.vue` | navigateBack fail fallback switchTab index → bean |
| `src/types/uni-pages.d.ts` | SwitchTabOptions 改 3 tab（@ts-nocheck 自动生成，build 已重生成一致）|
| `src/pages/recycle/staff-verify.vue` | **基线修**：抽 previewSubmitImage 出 setup（修 RECYCLE-003 遗留的模板内联 `uni.previewImage` 触发 vue-tsc 推断失败，阻塞 type-check）|

### tabbar config before → after

```
before: [首页 home → pages/index/index]  [拼豆 bean → pages/bean/index]  [我的 me → pages/me/index]
after:  [拼豆 bean → pages/bean/index]   [回收 recycle → pages/recycle/form] [我的 me → pages/me/index]
```
color `#5C5249` / selectedColor `#E73E2A`（朱红）/ bg `#FFFCF4` 不变。启动落地 = bean（type:home）。

### 首页下线处理（内容去向）

| 原首页内容 | 去向 |
|---|---|
| masthead 报头气质（谷子号外/EXTRA）| 丢弃（拼豆 tab 是落地页，自带业务 UI；报头装饰非业务必需）|
| BizHomeBanner（admin 可配轮播）| 丢弃（V1.2 落地拼豆 tab 直接进业务，banner 不下沉）|
| 入口格（拼豆/回收/资讯/扭蛋）| 拼豆=tab1 / 回收=tab2 / 资讯·扭蛋=「我的」入口卡，全部升级真入口 |
| 最新资讯 3 条（listNewsArticles）| 丢弃列表展示；资讯入口走「我的」发现区 → /pages/news/list（完整列表）|
| 扭蛋 teaser | 升「我的」发现区扭蛋入口卡 → /pages/gacha/index（真列表）|
| GZ-PAY-001 dev 入口（支付通道测试）| 随首页下线丢弃（见下「残留 marker 说明」）|

`pages/index/index.vue` **保留为非 tab redirect 兜底页**（不删除）：理由 = 历史多处 switchTab/reLaunch + uni-pages 已注册路由 + 基础设施引用（pages-config HOME_PAGE / App.ku.vue）。onLoad 即 reLaunch bean，杜绝死页。本卡已把主要 fallback 直接改指 bean，本页是双保险。

## AI 自测

### type-check（0 error）
```
> vue-tsc --noEmit
（无输出 = 0 error）
```
（首跑曾报 staff-verify.vue:247 基线 error — RECYCLE-003 模板内联 uni.previewImage 触发 vue-tsc 推断失败，非本卡引入；已抽 previewSubmitImage 出 setup 修净）

### vitest（374 passed / 40 files）
```
 Test Files  40 passed (40)
      Tests  374 passed (374)
   Duration  3.39s
```
（stderr 的 customer-service warn 是该测试故意覆盖兜底分支，非失败）

### build:mp-weixin（DONE Build complete）+ app.json 验证
```
DONE  Build complete.
Run method: open Weixin Mini Program Devtools, import dist/build/mp-weixin run.
```
dist/build/mp-weixin/app.json 关键字段：
```json
"pages": ["pages/bean/index", ...]          // ← 启动页 = 拼豆（数组第一项）
"tabBar": {
  "selectedColor": "#E73E2A",                // ← 朱红
  "list": [
    { "pagePath": "pages/bean/index",   "text": "拼豆" },   // tab1
    { "pagePath": "pages/recycle/form", "text": "回收" },   // tab2（recycle 占位图标）
    { "pagePath": "pages/me/index",     "text": "我的" }    // tab3
  ]
}
```
- ✅ tabBar list = 3 项，无指向 pages/index/index 的死页
- ✅ 启动页 = pages/bean/index（拼豆落地）
- ✅ recycle.png/recycleHL.png 已进 dist/build/mp-weixin/static/tabbar/
- build 尾部唤 devtools cli（memory 记录的假挂起）已 pkill，dist 已生成（exit 0）

## 风险提示 / 已知 issue

- **回收 tab 图标为占位**（复用 home 图）→ designer 待补「回收 tab C 风粗墨描边图标」（已在 config.ts 注释 + tabbar 文档头标注）。同名 drop-in 替换 recycle.png/recycleHL.png 即可，无需改代码。
- **useNavGuard 取消语义变更**：去首页后 3 tab 全需登录，无「不守的首页」可退。新逻辑 = 取消时 toast「已切换为浏览模式」+ 仅非落地 tab 回退拼豆 tab（落地 tab 即 bean，取消停留当前，避免反复弹窗死循环）。
- `pages/me/staff-orders/index.vue` 仍有一处 `switchTab('/pages/index/index')`？— 已全 grep 确认无残留可执行跳转（仅 index.vue 自身文档注释含字面量，无运行时跳转）。

## 残留 marker 说明（有意分工）

- `gacha/index.vue` 的 **GZ-GACHA-106 marker（3 处）+ goHistory 临时入口「我开过的」** → **本卡先不动，留 GACHA-111 清**。
  - 理由：扭蛋开盒历史「我开过的」的业务主线真入口（会员中心扭蛋历史/图鉴接通）由 GACHA-111 做端到端做活回归时建立 + 清 marker。本卡只在「我的」建扭蛋入口卡（跳 gacha 列表占位），不接通历史页真入口 → 此 marker 此刻不能裸删（否则历史页不可达）。
- **GZ-PAY-001 marker** 随首页整页下线消失（marker 在原 index.vue:181/393）。pay/test + pay/result 页保留（不删），但**不再有 mp 入口**（dev 测试入口随首页丢弃；业务支付真入口由 V1.1 GZ-PAY-101 接业务时建）。原 marker 的「清理者」语义已自然达成（首页没了 = 临时入口没了）。Kevin 如需测 pay/test 可临时自定义编译模式（V1.0 已验过支付通道，V1.2 非验证项）。

## 对下游 GACHA-111 的提示

- **扭蛋入口卡已建在 `me/index.vue`「发现」区** → 跳 `/pages/gacha/index`（扭蛋列表，已做活）。Kevin 从「我的」tab 点「扭蛋机」入口卡 1 次可达列表。
- **「我开过的」开盒历史真入口未建**（仍靠 gacha/index.vue 的 GZ-GACHA-106 临时 chip「我开过的 →」）→ **GACHA-111 负责**：接通会员中心/图鉴的扭蛋历史真入口（建议在「我的」图鉴入口或扭蛋列表内做活）→ 然后清 gacha/index.vue 的 GZ-GACHA-106 marker（3 处：line 85 注释 + 115 模板 chip + 174 样式）+ goHistory 函数 + 模板 filter-chip--history。
- §0 自检时 grep `Tier2-entry-temp` 会命中这 3 处 = 你的清理目标。

## Tier 2 可达性验证（AC 6）

- 打开小程序 → 启动落地 **拼豆 tab**（app.json pages[0] = bean）；底部见 3 tab。
- 回收：底部 tab2「回收」直达 `/pages/recycle/form`（N=0，tab 直点）。
- 拼豆：底部 tab1「拼豆」直达 / 启动即在（N=0）。
- 资讯：「我的」tab → 发现区「谷子号外」入口卡 → /pages/news/list（N=2，tab+卡）。
- 扭蛋：「我的」tab → 发现区「扭蛋机」入口卡 → /pages/gacha/index（N=2）。
- 回收记录：「我的」tab → 九宫格「回收记录」→ /pages/recycle/my-list（N=2）。
- 全部从已有 tab 1-2 次可达，无需自定义编译模式 / console 跳转。

## §AI 测试段（kevin-qa 完工后追加）

（占位 — 本卡纯 mp 导航重构，Tier 1B 由主线程统一派 kevin-qa：mp vitest 已全过 374/374，admin/后端无涉及。可达性 + 启动落地 bean 由 build app.json 已验证。）
