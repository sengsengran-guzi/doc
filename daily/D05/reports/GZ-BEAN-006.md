# GZ-BEAN-006 完工报告 — mp 我的预约列表（4 状态 tab）

纯 mp 前端 ticket（后端 `/app/gz/bean/booking/my` + mp API `listMyBookings` 均 BEAN-004/005 已就绪，本 ticket 不动后端 / 不动 API 层）。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（项目非 git repo，按主线程指示跳过） |
| 上游依赖 BEAN-005 merge | ✅ `BizStatusTag.vue` / `BizQrCode.vue` / `detail.vue` 已就位；`GzBeanBookingVO.storeName` 已批量填充（无 N+1） |
| 关键 API 存在 | ✅ `listMyBookings(status?)` 已封装于 `src/api/gz-bean.ts:268`（本 ticket 不改 API 层） |
| my-list.vue 待建 | ✅ `src/pages/bean/my-list.vue` 改前不存在 |
| 遗留临时入口扫描 | ✅ `grep Tier2-entry-temp src/` 无命中（入口已天然就绪，无需加临时入口） |
| 编译基线 | ✅ `build:mp-weixin` 改前可编译（pid 70230） |
| ADR 已读 | 无相关（任务卡关联 ADR 为 —） |
| 权威蓝图引用 | ✅ doc/10 §3 状态机 4 状态 / doc/11 §3.4 §A.3 状态字典 / doc/12 MP-BEAN-LIST |

**关键蓝图约束摘录**：
- doc/11 §A.3：`gz_bean_booking_status` 4 状态编码 `pending / used / cancelled / no_show`（mockup 仅 3 状态视觉，PRD/裁定为 4 状态，no_show 用弱墨灰 tag — 已由 `BizStatusTag` tone-muted 承载）。
- doc/10 §3 §N8：列表入口来自拼豆首页「我的预约」+ 提交成功页「查看我的预约」。
- R2（任务卡风险）：列表缩略图**不渲真二维码**（20 条 × canvas 卡顿），改静态 icon；真码仅详情页。

## 实现摘要

**改动 / 新增文件**（4 个，全 mp，不触碰 plus-ui / gz-bean 后端 / gz-common / detail.vue / index.vue）：

| 文件 | 行数 | 说明 |
|---|---|---|
| `src/pages/bean/my-list.vue` | 390 | 新建。列表页：4 状态分类条 + scroll-view 列表 + 加载/错误/空三态 |
| `src/pages/bean/my-list.logic.ts` | 77 | 新建。纯逻辑（tab 定义 / filterByStatus / showCancelButton / formatSlot），与 uniapp 运行时解耦便于单测 |
| `src/pages/bean/my-list.logic.test.ts` | 137 | 新建。vitest 单测 16 例 |
| `src/locale/bean.zh-CN.ts` | +50（append `beanListZhCN` + t() 分支） | 追加 `bean.list.*` 文案，未覆盖既有 bean.detail |

**路由注册**：`my-list.vue` 顶部 `<route lang="json">` 块 → uni-pages 插件 build 时自动合并进 `pages.json`（与 detail.vue 同款，**未手改 pages.json**）。已验证 `pages.json:49` 含 `pages/bean/my-list`、`dist/build/mp-weixin/app.json` 路由含该页。

**数据流（拉全量本地分组）**：`onShow` 调一次 `listMyBookings()`（不带 status）拉当前用户全量预约（后端按 sa-token userId 过滤 + sessDate/slotStart 倒序 + 批量填 storeName），切 tab 时本地 `filterByStatus` 过滤，**不重打接口**。V1.0 单店量小（全量 < 几十条），切 tab 无网络抖动最顺。用 `onShow`（非 onLoad）便于 BEAN-007 取消后返回自动刷新。

**AC 落地**：
- AC1 ✅ 顶部 4 状态横向分类条（朱红选中态 `var(--c-red)` 填充白字，Biz* + view 原语不撒 wd-*）+ scroll-view 列表，默认 active「待核销」(pending, DEFAULT_TAB_INDEX=0)。
- AC2 ⚠️ 分页降级为非分页（后端 `/my` 即非分页，单店量小够用 — 与主线程指示一致，不新建 `/my-list` 分页接口）。按当前 userId 过滤 + 倒序由后端 `selectMyMpList` 保证。
- AC3 ✅ 卡片：门店名（VO.storeName）+ 日期·时段 + 座位编号 + `BizStatusTag` + 静态盲盒 icon 缩略图（R2，非真码）；点击跳 `/pages/bean/detail?id={id}`。
- AC4 ✅ pending tab 卡片右下角渲染「取消预约」按钮（`@tap.stop` 阻止冒泡到卡片跳转），**仅占位 toast，handler 标注 `TODO by GZ-BEAN-007`**；其他 3 tab 不渲染（`showCancelButton` 仅 pending true）。
- AC5 ✅ nav 区右上「+ 新建」→ `/pages/bean/index`（拼豆首页落地页流，比直接 select 更顺，符合 doc/12 落地页流向）。
- AC6 ✅ 空状态：当前 tab 无数据 → 插画 emoji + 「暂无 XX 预约」（按 tab 区分文案）+「立即预约」CTA → `/pages/bean/index`。
- AC7 ✅ i18n 全覆盖 `bean.list.*`；状态文案本地 i18n 映射 4 状态（mp 端不拉后端字典 — 字典归 BEAN-008 给 admin）。
- AC Tier2 ✅ 见下「Tier 2 可达性」。

## AI 自测

### 编译（build:mp-weixin + 路由自动注册验证）
```
DONE  Build complete.
Run method: open Weixin Mini Program Devtools, import dist/build/mp-weixin run.

=== pages.json 是否含 my-list ===
49:      "path": "pages/bean/my-list",
--- dist 产物 ---
my-list.js / my-list.json / my-list.wxml / my-list.wxss / my-list.logic.js / my-list-vendor.js
--- dist app.json 路由 ---
pages/bean/my-list
```
（仅有 `<route/> 已废弃` 警告，与 confirm/detail/success 全 bean 页一致，是项目既定模式，非本 ticket 回归。）

### 单测（vitest — 纯逻辑 16 例）
```
 ✓ src/pages/bean/my-list.logic.test.ts (16 tests) 3ms

 Test Files  1 passed (1)
      Tests  16 passed (16)
```
覆盖：BEAN_LIST_TABS 4 状态顺序固定 + 默认 pending / filterByStatus 分组保序 + 空集 / showCancelButton 仅 pending true / formatSlot 拼接 + 空值容错。

### 全量回归（确认未破坏其他模块）
```
 Test Files  10 passed (10)
      Tests  73 passed (73)
   Duration  1.13s
```
（含本 ticket 新增 16 例；customer-service stderr 是该测试自身 error-path 预期日志，非失败。）

### 类型检查（vue-tsc，本 ticket 文件零错误）
```
src/components/biz/BizCustomerServiceFab.vue(92,5): error TS2322 ...   ← 上游既存，非本 ticket
src/components/biz/BizQrCode.vue(94,13): error TS2578 ...              ← 上游既存（BEAN-005），非本 ticket
src/pages/login/index.vue(35,50): error TS2339 ...                    ← 上游既存（SYS-002），非本 ticket
```
本 ticket 4 个文件（my-list.vue / my-list.logic.ts / my-list.logic.test.ts / bean.zh-CN.ts）**零 TS 报错**。上述 3 个 pre-existing 错误不属本 ticket scope，未触碰（纪律：不重构未要求代码），列入风险提示。

## 风险提示 / 已知 issue

- **R-A（pre-existing TS 错误，非本 ticket 引入）**：`vue-tsc --noEmit` 在 BizCustomerServiceFab.vue:92 / BizQrCode.vue:94 / login/index.vue:35 报 3 个错误，均为上游 ticket（SYS-002 / BEAN-005 / SYS-004）遗留。`build:mp-weixin` 不阻塞（运行时 OK），但 `pnpm type-check` 当前整体 exit 1。建议 Kevin 安排一个独立小 ticket 清这 3 个类型债（不应混进 BEAN-006）。
- **R-B（分页降级，已与主线程对齐）**：AC2 原写分页接口 `/my-list?pageNum&pageSize`，实际降级为非分页（复用既存 `/my`）。V1.0 单店量小够用；若后续单用户预约量大（V1.1 多店），需补分页或前端虚拟列表。
- 待 Kevin 批量人验关注（mp 端）：见下「人验要点」。

## Tier 2 可达性（CLAUDE.md §8.3）

- **入口天然就绪，无需加临时入口**：BEAN-010 拼豆首页 `index.vue:43-48` 的「我的预约」次级入口已 `uni.navigateTo('/pages/bean/my-list')`（已上线）。本 ticket 注册该路由后即可达。
- 闭环路径：拼豆 tab（首页）→「我的预约」→ 本列表页 →（点卡片）详情页 / （+新建 / 空状态 CTA）→ 拼豆首页。success.vue「查看我的预约」也指向本页。
- 已验证：`pages.json` + `dist app.json` 均含 `pages/bean/my-list`，路由活。

## 对下游 ticket 的提示

**给 GZ-BEAN-007（取消预约逻辑）**：本 ticket 留了 **2 处取消按钮占位**，都标注了 `TODO: ... by GZ-BEAN-007`：
1. **本页列表卡片**：`src/pages/bean/my-list.vue` 的 `onCancel(booking)` 函数（仅 toast 占位，未调 `cancelBooking`）。pending 卡片右下角按钮 `@tap.stop` 已防冒泡。BEAN-007 实现：二次确认弹窗 → 调 `cancelBooking(booking.id)` → 成功后重新 `load()` 刷新列表（本页已用 `onShow` 拉数据，BEAN-007 也可走「返回本页自动 onShow 刷新」省去手动 reload）。
2. **详情页**：`src/pages/bean/detail.vue` 的 `onCancel()`（BEAN-005 已留，同样 toast 占位）。
- BEAN-007 实施时 §0 自检 grep `by GZ-BEAN-007` 可定位这 2 处。
- 注意 `showCancelButton(status)` / `isCancelable` 已收口「仅 pending 可取消」的 UI 判定，BEAN-007 后端也应校验 status=pending 才允许取消（防越权取消 used/cancelled）。

**给 GZ-BEAN-008（后端 + admin 状态字典）**：mp 端 4 状态文案走本地 i18n（`bean.list.tab*` + `bean.detail.status.*`），未依赖后端字典 `gz_bean_booking_status`。两边 dict_label 须保持同口径（待核销/已核销/已取消/已过期），doc/11 §A.3 已定。

## 人验要点（Tier 2 批量人验，mp 端）

- [ ] 拼豆 tab →「我的预约」可进入列表页（Tier2 可达）
- [ ] 4 个 tab 可切换，选中态朱红填充；默认进来停在「待核销」
- [ ] 有 pending 预约时卡片右下角显示「取消预约」按钮，点击仅提示（暂不真取消，BEAN-007 接）；其他 3 tab 卡片无该按钮
- [ ] 点卡片跳详情页正确（id 透传）
- [ ] 某 tab 无数据时显示空状态 +「立即预约」可跳回拼豆首页
- [ ] 「+新建」可跳回拼豆首页

## §AI 测试段（kevin-qa 完工后追加）

（占位，kevin-qa spawn 完成后追写到此）
