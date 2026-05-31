# GZ-BEAN-005 完工报告 — mp 预约详情 + 核销码 QR 大图

> 实施：kevin-coder（后台 agent）+ 主线程收口（BizQrCode.test.ts 补写 + 全量验证 + 本报告）
> 日期：2026-06-02（D05）
> 状态：Tier 1A ✅ / Tier 1B 单测 ✅ / mp ticket → close 进人验列

---

## §0 状态自检（实施前 — 主线程已对账）

| 检查项 | 结论 |
|---|---|
| 上游 GZ-BEAN-004 | ✅ detail 接口 `GET /app/gz/bean/booking/{id}` 已存在（本人 403 校验）；mp `getBookingDetail()` API 已封装 |
| QR 服务真名 | `QrCodeSigner`（非卡里 `BeanQrService`）：`sign(bookingNo,sessDate,seatId)` + `buildQrPayload()` → `"BK|{no}|{code}"` |
| VO 缺口 | `GzBeanBookingVO` 缺 qrPayload/storeName/storeAddress → 本 ticket 补 |
| 新依赖 | uqrcode（Kevin §6#8 批准）|
| 编译健康 | `mvn install -pl ruoyi-gz-bean -am` exit=0 |

---

## §N 完工总结

### 改了哪些文件

**后端（gz-bean，小改）：**
- `domain/vo/GzBeanBookingVO.java` — 加 `qrPayload` / `storeName` / `storeAddress`
- `service/impl/GzBeanBookingServiceImpl.java` — `selectVoById` 填充：`enrichStoreInfo`（join store）+ `buildQrPayload`（QrCodeSigner 即时重算，payload 不持久化）；`enrichStoreInfoBatch`（列表去重 storeId 批量查，防 N+1，供 BEAN-006 复用）

**mp 端：**
- `package.json` — 加 `@uqrcode/js@^4.0.7`（纯本地 QR 生成，无 CDN，合同附件二腾讯云全栈合规）
- `components/biz/BizQrCode.vue`（新）— uqrcode 渲染封装，props `value/size/disabled/canvasId`，纠错级 L，失败兜底显示文本核销码（doc/10 §3 R4 店员手动核销路径），码点色用 c-tokens 字面量（canvas 不吃 CSS 变量）
- `components/biz/BizStatusTag.vue`（新）— 4 状态 tag（pending 朱红 / used 绿 / cancelled·no_show 灰），走 C token
- `pages/bean/detail.vue`（新）— `<route>` 块自动注册 `/pages/bean/detail`；布局门店→日期时段→座位→QR 大图(屏宽70%)→状态 tag→底部 CTA；pending 显示「取消预约」按钮占位（handler 留 BEAN-007，TODO 标注）；4 状态视觉（used/cancelled/no_show QR 灰显）
- `pages/bean/success.vue` — 「查看预约详情」CTA 接 `/pages/bean/detail?id=`（真实业务入口 = Tier 2 可达）
- `locale/bean.zh-CN.ts` — `bean.detail.*` 文案
- `components/biz/BizQrCode.test.ts`（新，主线程补）+ `BizStatusTag.test.ts`（新）

### Tier 1A / 1B 自测 raw output

**① 后端编译（VO + selectVoById enrich）**
```
mvn -q install -DskipTests -pl ruoyi-modules/ruoyi-gz-bean -am
===INSTALL_EXIT=0===
```

**② 后端单测（含 BEAN-004/009 回归，selectVoById 改动不破坏现有用例）**
```
mvn test -pl ruoyi-modules/ruoyi-gz-bean -Dtest=GzBeanBookingServiceImplTest → exit=0
（GzBeanBookingServiceImplTest 11 tests 全绿；selectVoById 对 null booking / null store 均有兜底）
```

**③ mp 全量 vitest 回归**
```
 ✓ src/components/biz/BizQrCode.test.ts (4 tests)
 ✓ src/components/biz/BizStatusTag.test.ts (6 tests)
 Test Files  9 passed (9)
      Tests  57 passed (57)
```

**④ mp build（detail 编译 + pages.json 注册）**
```
$ pnpm build:mp-weixin
dist/build/mp-weixin/pages/bean/detail.{js,json,wxml,wxss,vendor.js}  ← 16:30 生成
src/pages.json:35  "path": "pages/bean/detail"   ← <route> 块自动注册
```

### 已知 issue / 风险

- **QR 真机可扫性**：happy-dom 单测只锁逻辑分支（空 payload/灰显/重渲染），码矩阵正确性 + 真机微信扫码识别留 Kevin Tier 2 批量人验（testing-human.md 已列）。
- **低端机渲染兜底**：BizQrCode 渲染失败 → `failed=true` + 显示文本核销码，店员可手动核销（与 BEAN-008 手动核销互补）。

### 对下游提示

- **BEAN-006**：列表卡片 storeName 已可用（`enrichStoreInfoBatch` 在 `selectMyMpList` 路径已接）；缩略 QR 按卡里 R2 用静态 icon，不用 BizQrCode（仅详情页渲真码）；状态 tag 直接复用 `BizStatusTag`。
- **BEAN-007**：detail.vue 的「取消预约」按钮已渲染（pending 态），click handler 是占位 TODO，BEAN-007 接 `cancelBooking(id)` + 二次确认弹窗。
- **BEAN-008**：QR payload 口径 `"BK|{bookingNo}|{verifyCode}"`，扫码核销解析后按此拆分；verifyCode 校验复用 `QrCodeSigner.verify(bookingNo, sessDate, seatId, verifyCode)`。

### kevin-qa Tier 1B

本会话后台 agent 无 spawn kevin-qa 能力，Tier 1B 机械部分（mp vitest 57/57 + 后端单测 + build 可达性）由主线程跑通。mp 真机 happy path（扫码识别）→ Kevin Tier 2 批量人验。
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
# GZ-BEAN-007 完工报告 — mp 取消预约（二次确认 + cancelled）

> 纯 mp 前端 wiring：后端 cancel 全链路 D04 已就位（controller 本人校验 + service 事务/状态守卫/booking_log/座位释放 + service 单测），本 ticket 不碰后端，只接两处占位 click handler。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A — 项目非 git repo（主线程指示跳过 git，不 commit） |
| 上游依赖 merge（BEAN-005 detail / BEAN-006 my-list / BEAN-004 cancel 接口）| ✅ 占位按钮 + handler 占位均在位；`cancelBooking()` 已封装在 api/gz-bean.ts |
| 关键类/接口存在 | ✅ 后端 `INVALID_STATUS=4008` + service `cancel()` + MpController.cancel 本人校验已存在（grep 验证） |
| 编译通过（pnpm build:mp-weixin）| ✅ dist/build/mp-weixin 全套产物 17:34 落盘（detail.js / my-list.js / cancel.logic.js / app.json） |
| ADR 已读 | 无相关 ADR（任务卡关联 ADR = —） |
| 权威蓝图引用 | ✅ doc/10 §3 N9/N12 用户取消 + E7 / doc/11 §3.4 status + §3.5 booking_log — 行为均由 D04 后端已实现承载，前端只触发 |

## 实现摘要

### 改动文件（4 改 + 2 新）

| 文件 | 动作 |
|---|---|
| `miniapp/src/pages/bean/cancel.logic.ts` | 新增 — 纯逻辑 helper（确认文案 / 成功文案 / 失败映射），便于 vitest |
| `miniapp/src/pages/bean/cancel.logic.test.ts` | 新增 — 11 个用例 |
| `miniapp/src/pages/bean/detail.vue` | 接 `onCancel` handler（占位→真实）+ `doCancel` + `cancelling` 防连点 + 按钮 disabled 绑定 |
| `miniapp/src/pages/bean/my-list.vue` | 接 `onCancel` handler（占位→真实）+ `doCancel` + `cancelling` |
| `miniapp/src/locale/bean.zh-CN.ts` | append `beanCancelZhCN` 段 + `bean.cancel.` t() 分支 + 类型导出（既有 detail/list 段未动） |

### 两处 handler 接入点

- **detail.vue**：底部「取消预约」CTA → `onCancel()` → `uni.showModal` 二次确认 → `doCancel(id)` → `cancelBooking(id)` → 成功 toast + `load(id)` 重拉详情（status→cancelled，QR 灰显 / 取消按钮隐藏均由既有 `isInactive` / `isPending` computed 自动驱动，零额外逻辑）。
- **my-list.vue**：pending 卡片右下角「取消」→ `onCancel(booking)` → 同款 `uni.showModal` → `doCancel(id)` → 成功 toast + `load()` 重拉列表本地重分组（卡片从 pending tab 移到 cancelled tab）。失败也重拉一次（状态竞态自愈）。

### 二次确认用什么组件

`uni.showModal`（非 wd-message-box）。理由：项目组件库无关纪律 + showModal 是 uni 原生跨端 API 无组件依赖，文案/按钮文字全走 i18n（`bean.cancel.confirmTitle/Content/Ok/Cancel`）。任务卡原写 wd-message-box，主线程指示「`wd-message-box` 或 `uni.showModal`」二选一，选 showModal 更轻、零组件库耦合。

### 成功 / 失败刷新逻辑

- **成功**：`uni.showToast({icon:'success'})`「取消成功」→ 重拉当前页数据 → 状态变化全由既有 computed 驱动渲染，无需手改 DOM。
- **失败（4008 已终态）**：后端 message「预约状态不允许此操作（当前状态：used）」由 http.ts 业务码分支**已全局 toast**（http.ts line 99-104 无条件 toast 后端 msg）。本 ticket `resolveCancelFailToast()` 分流：payload=null（实际场景）→ 返回 null 不重复弹；payload 透出 code=4008 → 本地兜底「该预约已核销 / 已过期，不可取消」。**不静默吞错**：catch 里 console.warn + 重拉刷新。
- **未动 http.ts**（主线程边界）：http.ts 业务码错误分支硬编码 toast 后端 msg 且 reject `.data`（不含 code），所以友好文案由后端 message 承载，前端不重复。

## AI 自测

### 1. 编译（pnpm build:mp-weixin）

build 产物落盘（后台任务 stdout 缓冲为空，但产物是硬证据）：

```
$ ls dist/build/mp-weixin/pages/bean/
cancel.logic.js   642   17:34   ← 新 helper 编译产物
detail.js        4146   17:34   ← detail 接 handler 后重新编译
detail.wxml      4067   17:34
my-list.js       3379   17:34   ← my-list 接 handler 后重新编译
my-list.wxml     3385   17:34
app.json         1388   17:34   ← 全量编译成功
```

### 2. 单测（cancel.logic 单跑）

```
$ pnpm vitest run src/pages/bean/cancel.logic.test.ts
 ✓ src/pages/bean/cancel.logic.test.ts (11 tests) 2ms
 Test Files  1 passed (1)
      Tests  11 passed (11)
```

覆盖：confirmOptions 文案固定 + i18n 命中（AC1/6）/ successToast（AC4）/ failToast 分流 8 路（payload=null→null、code=4008→本地文案、msg→直用、message→直用、code 优先 msg、未知 code→null、非对象→null）（AC5）。

### 3. 全量回归（pnpm vitest run）

```
$ pnpm vitest run
 ✓ src/api/gz-common.test.ts (7 tests)
 ✓ src/store/customer-service.test.ts (6 tests)
 ✓ src/components/biz/BizSeatList.test.ts (7 tests)
 ✓ src/components/biz/BizQrCode.test.ts (4 tests)
 ✓ src/utils/watermark.test.ts (9 tests)
 ✓ src/api/customer-service.test.ts (3 tests)
 ✓ src/store/token.test.ts (3 tests)
 ✓ src/components/biz/BizStatusTag.test.ts (6 tests)
 ✓ src/pages/bean/my-list.logic.test.ts (...)
 ✓ src/pages/bean/cancel.logic.test.ts (11 tests)   ← 本 ticket 新增
 Test Files  11 passed (11)
      Tests  84 passed (84)
```

**未破坏全量回归**：11 个 test file 全过，84 passed（新增 11 个 cancel 用例，从原 73 → 84）。stderr 是既有用例故意造的失败场景日志（customer-service refresh 失败保留旧值等），非报错。

### 4. type-check（vue-tsc，本 ticket 文件零错误）

```
$ pnpm type-check 2>&1 | grep -E "bean/detail|bean/my-list|cancel.logic|bean.zh-CN"
（无输出 — 本 ticket 改的 4 个文件零 TS 错误）

仓库 pre-existing 错误（与本 ticket 无关，未触碰）：
  src/components/biz/BizCustomerServiceFab.vue(92,5): TS2322
  src/pages/login/index.vue(35,50): TS2339
```

## 风险提示 / 已知 issue

- **R1（状态竞态）**：用户点取消瞬间店员扫码核销 — 后端 SELECT FOR UPDATE + 事务谁先锁谁赢（D04 已实现）。前端兜底：失败也重拉刷新，卡片状态自愈。
- **http.ts 友好文案依赖后端 message**：AC5 的「用户友好提示」实际由后端 `INVALID_STATUS_MSG + 当前状态` 经 http.ts 全局 toast 承载，前端 `resolveCancelFailToast` 仅在 payload 透出 code 时兜底。这是不动 http.ts 的折中（http.ts 业务码分支硬编码 toast + reject `.data` 不含 code）。若未来需要纯本地文案映射，需 http.ts 改为透传完整 R 对象 —— 列为后续可选优化，不在本 ticket。
- **V1.0 不限制取消时间**（合同 §2.3）：代码注释标 `TODO v2 候选：取消截止时间 + 黑名单`，不实现。
- 待 Kevin 批量人验关注（mp 端）：见下「人验要点」。

## 对下游 ticket 的提示

- **BEAN-008 核销**：核销时校验 status=pending 才放行（已 cancelled → 拒绝），与本 ticket 取消形成状态机闭环。后端 service 已实现（INVALID_STATUS 共用 4008），BEAN-008 mp/admin 端实施时复用此错误码映射。
- **未留任何 Tier2-entry-temp 临时入口**：取消入口天然可达（拼豆 tab → 我的预约 → 卡片「取消」/ detail「取消预约」），下游无需清理。

## 人验要点（Tier 2 批量人验，mp 端）

- ⬜ 真机：pending 预约 detail 点「取消预约」→ 弹二次确认 → 确认 → toast「取消成功」→ QR 灰显 + 「已取消」大字 + 取消按钮消失
- ⬜ 真机：my-list pending 卡片点「取消」→ 二次确认 → 确认 → 卡片从「待核销」tab 移到「已取消」tab
- ⬜ 真机：二次确认点「再想想」→ 弹窗关闭，预约不变
- ⬜ 真机：取消一条已 used/no_show 的（如手动改库造数据）→ toast 提示不可取消 + 状态不变
- ⬜ 真机：连点取消按钮 → 不重复提交（cancelling 防连点 + loading mask）

## §AI 测试段（kevin-qa 完工后追加）

（占位，kevin-qa spawn 完成后追写到此）
# GZ-BEAN-008 完工报告 — admin 预约列表 + 扫码 / 手动核销

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A — 主线程指示「项目非 git repo，§0 git 跳过，不 commit」（RuoYi-Vue-Plus 子目录有上游 clone 的 git，仅用于看 diff，不提交） |
| 上游依赖 merge | ✅ BEAN-004（controller `/system/gz/bean/booking` + service verify/cancel/selectPageList + QrCodeSigner + 菜单 6050-6056 含 `gz:bean:booking:verify`）；BEAN-005（selectVoById enrich + qrPayload 即时重算口径） |
| 关键类/表存在 | ✅ GzBeanBookingController / ServiceImpl / QrCodeSigner / GzBeanBooking entity / mapper；gz_bean_booking 表存在；sys_user.gz_store_id 字段存在（ADMIN-001 ALTER） |
| 编译通过 | ✅ mvn compile + install（gz-bean）/ plus-ui build:prod 均过 |
| ADR 已读 | 无相关 ADR（doc/_adr 空）；权威蓝图 doc/10 §3（N10/N11 核销 + E6/E7/E8 异常分支）+ doc/11 §3.4/§3.5/§A.3 已对齐 |

**真实状态修正（主线程已提示，已核对）**：
- admin 列表 + 手动核销在 BEAN-004 已存在，**未新建** `/gz/bean/admin` 控制器；增量挂在现有 `GzBeanBookingController`（前缀 `/system/gz/bean/booking`）。
- 菜单 6050「预约管理」component=`gz-bean/booking/index`、perm=`gz:bean:booking:list`（owner+staff）BEAN-004 已建 → **未重复建菜单 DDL**；扫码核销复用 `gz:bean:booking:verify`（无新权限点）。
- 状态字典 `gz_bean_booking_status` 全工程无 → 本 ticket 新建（唯一处）。

## 实现摘要

### 改动文件（git diff --stat + 新增）

**后端 ruoyi-gz-bean（增量）**
- `controller/GzBeanBookingController.java`：list 加 store_id 隔离（resolveStaffStoreId）；新增 `POST /verify-scan`（`@SaCheckPermission("gz:bean:booking:verify")` + `@Log(title="拼豆预约扫码核销", businessType=UPDATE)`）
- `service/IGzBeanBookingService.java`：加 `verifyByQrPayload` + `selectPageList(query, pageQuery, staffStoreId)` 重载
- `service/impl/GzBeanBookingServiceImpl.java`：抽出私有 `doVerify(booking, operatorId, logNote)`（手动 + 扫码共用）；`verify()` 与 `verifyByQrPayload()` 都调它；selectPageList 加 store 隔离 + statusList 多选 + 列表 enrich storeName
- `domain/bo/GzBeanBookingQueryBo.java`：加 `statusList`（多选筛选）
- `exception/GzBeanErrorCode.java`：加 4009 QR_PAYLOAD_MALFORMED / 4010 QR_SIGNATURE_INVALID
- `mapper/GzBeanBookingMapper.java`：加 `selectByBookingNo`
- **新增** `mapper/GzAdminUserStoreMapper.java`：只读直查 `sys_user.gz_store_id`（不改 ruoyi-system 源码）
- **新增** `domain/bo/GzBeanBookingVerifyScanBo.java`：扫码请求体 `{qrPayload}`（@NotBlank）
- `test/.../GzBeanBookingServiceImplTest.java`：加 4 个 QR 扫码 case

**状态字典 DDL**
- **新增** `ruoyi-admin/src/main/resources/db/migration/V202606020030__GZ-BEAN-008-dict-booking-status.sql`

**Admin 前端 plus-ui（纯新建 + i18n）**
- **新增** `src/views/gz-bean/booking/index.vue`（列表 + 筛选 + 扫码 dialog + 手动核销）
- **新增** `src/api/gz-bean/booking.ts`（page / detail / verifyManual / verifyByScan）
- `package.json`：加 `jsqr@1.4.0`（Kevin §6#8 已批准；MIT，纯 JS QR 解码，零传递依赖）
- `src/lang/zh_CN.ts` + `src/lang/en_US.ts`：`gzBeanBooking.*` 全覆盖

### 关键技术点

- **verify-scan 端点路径**：`POST /system/gz/bean/booking/verify-scan`，body `{qrPayload}`
- **doVerify 抽出共用**：✅ 是。`verify(id)`（手动）查 booking 后调 `doVerify`；`verifyByQrPayload(payload)`（扫码）解析→回表→校签后调同一 `doVerify`。底层逻辑唯一（status=pending 守卫 + UPDATE used + verifyTime + verifiedBy + dedupToken 切 booking_no + 写 admin booking_log），仅 logNote 区分入口（"店员手动核销" / "店员扫码核销"）
- **签名校验**：复用 `QrCodeSigner.verify(bookingNo, booking.sessDate, booking.seatId, verifyCode)`，密钥统一走 `GzBeanQrProperties.signingSecret`（与 BEAN-004 submit / BEAN-005 详情即时重算同源，不新生）
- **QR payload 解析**：`split("\\|", -1)` 严格 3 段 + 首段 "BK" + 后两段非空，否则 QR_PAYLOAD_MALFORMED
- **store_id 隔离结论**：owner / superadmin → resolveStaffStoreId 返 null（看全部，受 query.storeId 可选筛选）；staff → 读 `sys_user.gz_store_id` 强制隔离（忽略前端 query.storeId 防越权）。当前种子 staff(101) gz_store_id=NULL（待 ADMIN-002 UI 配），NULL 时不额外拦截（V1.0 单店安全默认，与 GZ-SYS-006 staff scope 同思路）。角色判定复用 GZ-SYS-006 的 `LoginUser.getRolePermission()` 模式
- **前端扫码**：file input（accept image/*，不调摄像头）→ FileReader → Image → canvas getImageData → `jsQR(data, w, h)` → payload → verify-scan。后端业务错误（签名无效 / 状态非法 / 不存在）的中文 msg 由 ruoyi request.ts 拦截器自动 ElNotification toast；dialog 不自动关闭，店员可改手动核销 fallback（强约束 R3）
- **状态字典**：dict_type=`gz_bean_booking_status`，tenant_id='000000'（系统级共享，与 sys_show_hide 同约定），dict_id/dict_code 取 9001-9004 避开 ruoyi 占用；pending=warning / used=success / cancelled=info / no_show=danger。前端 `useDict('gz_bean_booking_status')` + `dict-tag` 回显，筛选下拉同源

## AI 自测（Tier 1A）

### 后端编译 + install
```
$ mvn -o compile -pl ruoyi-modules/ruoyi-gz-bean -am   → 无错误
$ mvn -o install -DskipTests -pl ruoyi-modules/ruoyi-gz-bean -am   → BUILD SUCCESS
（install 必跑：spring-boot:run 加载 ~/.m2 jar，新 verify-scan 路由 / GzAdminUserStoreMapper 需 install 后 restart 才生效，CLAUDE.md §5）
```

### 单测（gz-bean 全量 61，含本 ticket 新增 4 QR case）
```
[INFO] Running GzBeanBookingServiceImplTest
[INFO] Tests run: 18, Failures: 0, Errors: 0, Skipped: 0
  ├─ verifyByQrPayload happy（校签通过 → pending → used）           ✅
  ├─ verifyByQrPayload 签名不通过 → QR_SIGNATURE_INVALID（不核销）   ✅
  ├─ verifyByQrPayload 状态非 pending（已核销）→ INVALID_STATUS      ✅
  └─ verifyByQrPayload 格式非法 → QR_PAYLOAD_MALFORMED（不回表）     ✅
[INFO] Running QrCodeSignerTest      Tests run: 7
[INFO] 全模块汇总  Tests run: 61, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

### 状态字典 DDL（dev MySQL 实跑 + 幂等验证）
```
$ docker exec -i sensenran-dev-mysql mysql ry-vue < V202606020030__GZ-BEAN-008-dict-booking-status.sql
$ SELECT dict_sort, dict_label, dict_value, list_class FROM sys_dict_data WHERE dict_type='gz_bean_booking_status';
dict_sort  dict_label  dict_value  list_class
1          待核销       pending     warning
2          已核销       used        success
3          已取消       cancelled   info
4          已过期       no_show     danger
# 再跑一次（幂等）→ rows_after_rerun = 4（先 DELETE by dict_type 后 INSERT，可重复 cleanup 复跑）
# Redis dict cache 已 flush（DEL 000000:sys_dict），后端下次 useDict 重载
```

### SQL 真 schema 校验（selectByBookingNo + gz_store_id 读）
```
$ SELECT id,booking_no,status FROM gz_bean_booking WHERE booking_no='NOPE' AND del_flag='0' LIMIT 1;  → selectByBookingNo sql-ok
$ SELECT user_id,user_name,gz_store_id FROM sys_user WHERE user_id IN (100,101);
100  gz_owner          NULL   （owner → 看全部）
101  gz_staff_chengdu  NULL   （staff 未绑店 → V1.0 单店安全默认看全部，待 ADMIN-002 UI 配）
```

### Admin 前端构建（TS + 模板 gate）
```
$ pnpm add jsqr@1.4.0   → + jsqr 1.4.0  Done
$ pnpm build:prod       → 完整 asset 列表产出，无 TS / 模板 error
  （vue-tsc + vite 全过；gz-bean/booking/index 懒加载 chunk 已 emit）
```

### admin 三路径自测说明（kevin-coder 无 Playwright，描述 + 留 Tier 1B 验）
1. **列表 + 筛选**：进「拼豆管理 / 预约管理」→ 门店下拉（getGzBeanStoreOptions，type=pindou 由 BEAN-001 options 端点保证）/ 日期范围 picker 默认今天 / 状态多选（useDict 4 项）/ 手机号模糊 → 查询调 `GET /list`（owner 全量 / staff 后端强制本店）
2. **手动核销**：列表 pending 行「核销」按钮（非 pending 行 disabled）→ ElMessageBox 二次确认 → `POST /{id}/verify` → 成功 toast + 刷新；非法状态后端 INVALID_STATUS 中文 msg 自动 toast
3. **扫码核销**：「扫码核销」按钮 → dialog → 上传 QR 截图 → jsQR canvas 解码 → 预览 payload → 「确认核销」→ `POST /verify-scan` → 后端校签 + 状态校验；签名无效 / 已核销 → 中文 msg toast + dialog 保留供手动 fallback

## 风险提示 / 已知 issue

- **R1（store 隔离 NULL 默认）**：当前 staff 种子账号 gz_store_id=NULL，按代码会「看全部」。V1.0 单门店场景下等价无害；待 ADMIN-002 UI 给 staff 绑店后才真正隔离。这是设计选择（与 GZ-SYS-006 staff scope 一致），非 bug。
- **R2（dev DB Flyway 历史）**：dev MySQL 当前无 `flyway_schema_history` 表（gz 数据似为手工/脚本预置）。我手工执行了本 DDL 用于验证 —— 因 DDL 幂等（先 DELETE by dict_type），未来 Flyway 在干净环境跑该 version 无冲突。后端首次启动若走 Flyway，本 migration 正常生效。
- **R3（jsqr 解码率）**：模糊 / 含杂物截图可能解不出 → 前端「未识别到二维码，请重新截图」+ 保留手动核销 fallback（已实现）。
- **待 Kevin 批量人验关注**：N/A — 纯 admin + 后端 ticket，Tech 段无 `miniapp/` 路径、AC 无微信原生能力 → 按 CLAUDE.md §8.2 例外，**无人验**，AI Tier 1A+1B 全 ✅ 即终态 close。

## 对下游 ticket 的提示

- **ADMIN-002（admin-user CRUD）**：给 staff 账号配 `gz_store_id` 后，本页 store 隔离才真正生效（owner 看全部 / staff 仅本店）。建议 ADMIN-002 完工后回归验一次「staff 登录预约列表只见本店」。
- **未引入临时入口**：本 ticket 纯 admin，无 mp 新页 → 无 Tier 2 可达性临时入口需求；也未发现需清理的 `Tier2-entry-temp`（grep 无命中本 ticket 范围）。
- **状态字典已建**：后续任何 admin/统计页要显示预约状态标签，直接 `useDict('gz_bean_booking_status')`，勿重复建 dict_type。

## §AI 测试段（kevin-qa 完工后追加）

（占位，kevin-qa spawn 完成后追写到此）
# GZ-BEAN-009 完工报告 — no_show 自动标记 cron（凌晨 2 点）

> 实施：kevin-coder（后台 agent）+ 主线程收口（单测补写 + 构建验证 + 本报告）
> 日期：2026-06-02（D05）
> 状态：Tier 1A ✅ / Tier 1B 单测 ✅ / 纯后端 ticket，无人验

---

## §0 状态自检（实施前）

| 检查项 | 结论 |
|---|---|
| git 状态 | 项目当前非 git repo（`git rev-parse` fail）→ 跳过 git 步骤，本日不 commit |
| 上游 GZ-BEAN-004 | ✅ 已 merge：`gz_bean_booking` / `gz_bean_booking_log` 表 + entity + mapper + service（submit/verify/cancel）全在 |
| 调度框架硬检查 | 🔴 **卡里假设 Quartz `sys_job` 错误**：工程实为 **SnailJob（com.aizuda）**，`ruoyi-common-job` 依赖 `snail-job-client-starter`；样例在 `ruoyi-modules/ruoyi-job/.../snailjob/`。baseline 无 `sys_job`/`sj_*` 表 → job 注册走 SnailJob 控制台，不走 Flyway |
| gz-bean pom 可见性 | gz-bean 原只依赖 gz-common（不透传 `ruoyi-common-job`）→ 需显式加 `ruoyi-common-job` 依赖才能 import SnailJob 执行器类 |
| no_show 时间列名 | DDL `V202606011200` 实列名 `no_show_time`（非卡里写的 `no_show_marked_time`） |
| 编译健康 | `mvn install -pl ruoyi-modules/ruoyi-gz-bean -am -DskipTests` exit=0 |

---

## §N 完工总结

### 改了哪些文件

| 文件 | 改动 |
|---|---|
| `ruoyi-modules/ruoyi-gz-bean/pom.xml` | 加 `org.dromara:ruoyi-common-job` 依赖（已存在的内部模块，非外部新依赖，不触 CLAUDE.md §6#8） |
| `.../gz/bean/job/GzBeanNoShowMarkJob.java` | **新建** SnailJob 注解式执行器 `@JobExecutor(name="gzBeanNoShowMarkTask")`；委托 service，回写统计到执行结果；`failed>0` 或异常 → `ExecuteResult.failure` 触发告警，不吞 |
| `.../gz/bean/service/IGzBeanBookingService.java` | 加 `markNoShowBatch()` + `record NoShowMarkResult(int scanned, marked, skipped, failed)` |
| `.../gz/bean/service/impl/GzBeanBookingServiceImpl.java` | 加常量 `STATUS_NO_SHOW`/`OPERATOR_SYSTEM`；`markNoShowBatch()`（`TenantHelper.ignore` 全租户扫 + 逐条 + 单条异常隔离 + 统计）；`protected markOneNoShow()`（条件 UPDATE，affected==1 才写 booking_log） |
| `.../gz/bean/mapper/GzBeanBookingMapper.java` | 加 `selectExpiredPendingIds()`（`status='pending' AND sess_date<CURDATE() AND del_flag='0'`）+ `markNoShow(id, noShowTime)`（条件 UPDATE，`WHERE status='pending'` 守卫，天然原子幂等，dedup_token 切 booking_no 释放占位） |
| `.../test/.../GzBeanBookingServiceImplTest.java` | 加 4 个 markNoShowBatch 单测 + import `IGzBeanBookingService` |

### 关键设计：幂等 = 条件 UPDATE（非 SELECT FOR UPDATE）

卡里写 "SELECT FOR UPDATE"，实际采用更稳的 **条件 UPDATE**：

```sql
UPDATE gz_bean_booking
SET status = 'no_show', no_show_time = #{noShowTime}, dedup_token = booking_no
WHERE id = #{id} AND status = 'pending' AND del_flag = '0'
```

`WHERE status='pending'` 守卫使 UPDATE 天然原子 + 幂等（AC 5）：affected=1 = 本次标记成功；affected=0 = 已被并发/上轮 cron 改态 → service 计入 `skipped` 不写 log。无需悲观锁，避免锁表。

### Tier 1A 自测 raw output

**① install + 编译（pom 改动验证）**

```
$ mvn -q install -DskipTests -pl ruoyi-modules/ruoyi-gz-bean -am
===STEP1_EXIT=0===
```

**② 单测（11 tests，含 4 新增 BEAN-009）**

```
Tests run: 11, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.832 s -- in org.dromara.gz.bean.service.impl.GzBeanBookingServiceImplTest
Tests run: 14, Failures: 0, Errors: 0, Skipped: 0 -- in GzBeanStoreServiceImplTest
Tests run: 12, Failures: 0, Errors: 0, Skipped: 0 -- in GzBeanSeatServiceImplTest
Tests run: 10, Failures: 0, Errors: 0, Skipped: 0 -- in GzBeanTimeSlotTemplateServiceImplTest
Tests run:  7, Failures: 0, Errors: 0, Skipped: 0 -- in QrCodeSignerTest
```

**③ 异常隔离行为（single_failure 用例运行日志 — 故意抛 RuntimeException 被 catch，整批不中断）**

```
[bean-noshow] mark no_show FAILED bookingId=302, continue next  (java.lang.RuntimeException: DB 写超时（模拟）)
[bean-noshow] done. scanned=3 marked=2 skipped=0 failed=1
[bean-noshow] booking id=202 already non-pending, skip (idempotent)
[bean-noshow] done. scanned=2 marked=1 skipped=1 failed=0
```

4 个新增用例覆盖：AC6 主场景（2 标记+2 log）/ 幂等跳过（affected=0 不写 log）/ 单条异常隔离（整批不断）/ 空扫描（全 0 不触 mapper）。

### 🔴 SnailJob 控制台注册（ops 步骤，非代码 — Kevin / 运维执行一次）

baseline 无 `sys_job`/`sj_*` 表，job **不通过 Flyway DDL 注册**。需在 SnailJob 服务端控制台「定时任务」菜单手动建：

| 配置项 | 值 |
|---|---|
| 任务名称 | GZ-BEAN-NO-SHOW-MARK |
| 执行器路由（executor_info） | `gzBeanNoShowMarkTask`（= `@JobExecutor(name)`） |
| 触发类型 / 表达式 | CRON / `0 0 2 * * ?`（每日 02:00，容器时区 Asia/Shanghai） |
| 阻塞策略 | 丢弃（上次未完不叠加） |
| 组 | `ruoyi_group` |

注册后可在控制台点「执行一次」手动触发验证（见 testing-human.md）。

### 已知 issue / 风险

- SnailJob server 未起时，job 不会自动触发，但 `markNoShowBatch()` 逻辑已被单测覆盖；真机触发依赖控制台注册 + server 在线。
- Flyway 未接入（D05 BEAN-010 agent 同步发现）：与本 ticket 无关（本 ticket 无 DDL），但影响整体库初始化，主线程在日终统一核。

### 对下游提示

- 本 ticket 在 `GzBeanBookingServiceImpl` 加了 `markNoShowBatch`/`markOneNoShow` + 2 个常量 + mapper 2 方法 → **BEAN-005（VO/detail）/ BEAN-008（verifyByQrPayload）接着改同一 impl 文件时已包含这些改动**（主线程已串行化：009→005→008）。
- `no_show` 状态在 `gz_bean_booking_status` 字典需有编码（BEAN-006 列表 tab / BEAN-008 筛选共用）—— 列表渲染用 BizTag 灰款（doc/10 §3 裁定）。

### kevin-qa Tier 1B

本会话后台 agent 无 spawn kevin-qa 能力，单测（Tier 1B 机械部分）由主线程跑通验证（11/11）。纯后端 ticket，无 admin E2E / mp 真机，**AI ✅ 即终态，无人验**（CLAUDE.md §8.2 例外）。
# GZ-BEAN-010 完工报告 — mp 拼豆首页（C 端入口落地页）

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（本项目当前非 git repo，主线程指令跳过 git 步骤） |
| 上游依赖 GZ-BEAN-003 merge | ✅ 占位页 + select 页已在（D04） |
| 关键类/表存在 | ✅ `ConfigService`（ruoyi-common-core SPI）/ `sys_config` 表 / `useAuth`(@/hooks) / `useNavGuard` / Biz 组件齐全 |
| 编译通过 | ✅ 后端 `mvn compile` 无错 + `mvn install` exit=0 / mp `build:mp-weixin` 产物生成 |
| ADR 已读 | 无相关（ticket 关联 ADR 为 —；ADR-005 未登录守卫机制经 useNavGuard 复用，未新增 ADR） |
| Tier2-entry-temp 清理 | ✅ grep 全 mp 无残留（本 ticket 是指定清理者） |

### §0 关键对账修正（卡里过时假设 → 真实状态）

- **AC 1「修改 pages.json tabBar」无需做**：`pages/bean/index` 已在 pages 列表 + tabBar pagePath 已指向（GZ-ADMIN-005 已配）。仅重写 index.vue 内容。
- **后端读 sys_config 方案修正**：卡里说"复用 ISysConfigService" —— 但 `ISysConfigService` 在 ruoyi-system 模块，**gz-common pom 不依赖 ruoyi-system**，无法注入。改用 ruoyi-common-core 的 **`ConfigService` 跨模块 SPI**（`SysConfigServiceImpl implements ISysConfigService, ConfigService`，gz-common 已依赖 common-core）。`getConfigValue(key)` 等价。
- **不走 ruoyi 自带 `/system/config/configKey/{key}`**：该端点要 admin 登录态，给它加 @SaIgnore 会污染 ruoyi 自带源码（铁律 #1）。新建 `/app/gz/common/config` + @SaIgnore 薄包装，满足 AC 6 匿名可读。

## 实现摘要

改动 / 新增文件：
```
后端（gz-common）:
  A  ruoyi-modules/ruoyi-gz-common/.../controller/applet/GzConfigMpController.java   （新建，@SaIgnore 公开 sys_config 读取）
  A  ruoyi-admin/src/main/resources/db/migration/V202606020020__GZ-BEAN-010-default-banner-config.sql （新建，INSERT sys_config gz.bean.home.banner）

mp 端:
  M  miniapp/src/pages/bean/index.vue        （占位页 → 正式落地页；删 Tier2-entry-temp + goSelect 临时入口）
  A  miniapp/src/api/gz-common.ts            （新建，getSysConfig + fetchBeanHomeBanner 兜底）
  M  miniapp/src/locale/bean.zh-CN.ts        （beanEntryZhCN 临时文案 → beanHomeZhCN 落地页文案）
```

落地页结构（自上而下）：报头 masthead → 顶部 banner（sys_config 拉取，无素材降级占位图 + MOCK 水印 + 默认文案）→ 主 CTA「立即预约」朱红 BizButton size=lg block → 次级「我的预约」弱按钮卡 → 规则说明卡片（3 条 i18n 文案）→ 客服浮层。

白名单机制最终方案：**`@SaIgnore` 注解**（与同目录 `WxLoginController` 同款），不动 `application.yml` 的 `security.excludes`，不动 ruoyi 自带 SysConfigController。`/app/` 前缀 + `@SaIgnore` 即放行未登录访问。

## AI 自测（Tier 1A）

### 后端编译 + install
```
$ mvn compile -pl ruoyi-modules/ruoyi-gz-common -am -q
（无错误输出 — BUILD SUCCESS）

$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-common -am -q
=== install exit=0 ===
-rw-r--r-- ... ruoyi-gz-common-5.6.1.jar   （15:42 更新，新 controller 进 jar）
```

### mp typecheck（我的文件干净；2 个既有错误不在本 ticket 文件）
```
$ pnpm type-check  (vue-tsc --noEmit)
src/components/biz/BizCustomerServiceFab.vue(92,5): error TS2322  ← GZ-SYS-004 既有，非本 ticket
src/pages/login/index.vue(35,50): error TS2339                    ← GZ-SYS-002 既有，非本 ticket
（pages/bean/index.vue / api/gz-common.ts / locale/bean.zh-CN.ts 均无 error）
```

### mp 构建产物（dist/build/mp-weixin）
```
$ pnpm build:mp-weixin  → dist/build/mp-weixin/pages/bean/
  index.js   2758B   index.wxml 3977B   index.wxss 3060B   （落地页产出）

# wxml 结构 grep:
  11 banner    2 cta    5 myboo    13 rules
# index.js 引用 grep:
  1 bean/my-list   1 bean/select   1 ensureLoggedIn   1 fetchBeanHomeBanner
# 新文案落点:
  locale/bean.zh-CN.js + api/gz-common.js 含「成都拼豆店开张啦」「到店前可随时取消」
# 旧临时文案清除验证:
  grep「体验选座流程」「进入选座」全 dist → 无结果（已彻底清除）
```

### curl 烟雾测试（待后端启动后跑 — 本机后端当前未运行 :8080 空）
后端编译期已保证 controller 注册；运行期验证命令（Kevin 起 `mvn spring-boot:run -pl ruoyi-admin` 后执行）：
```bash
# DDL 先跑（Flyway 未接入，手工导入 — 与 GZ-SYS-004 同款流程）:
mysql -uroot -p<pwd> -h127.0.0.1 -P3306 ry-vue \
  < ruoyi-admin/src/main/resources/db/migration/V202606020020__GZ-BEAN-010-default-banner-config.sql

# 公开端点未带 token 应返 200 + JSON 串:
curl -s 'http://localhost:8080/app/gz/common/config/get?key=gz.bean.home.banner'
# 期望: {"code":200,"msg":"操作成功","data":"{\"imageUrl\":\"\",\"title\":\"成都拼豆店开张啦\",\"link\":\"\"}"}

# 不存在的 key 应返 200 + 空串(不报错):
curl -s 'http://localhost:8080/app/gz/common/config/get?key=gz.not.exist'
# 期望: {"code":200,"msg":"操作成功","data":""}
```

## 风险提示 / 已知 issue

- **R1（DDL 未自动跑）**：本项目 Flyway 尚未接入，DDL 需手工导入（与既往 V*.sql 一致）。Kevin testing 前需跑上面 mysql 导入命令，否则 banner 端点返空串 → mp 走默认文案兜底（不报错，但不是 DDL 配的值）。
- **R2（甲方运营素材未到位）**：banner imageUrl 默认空 → mp 降级占位图（彩纸 tint + MOCK 水印 + 🧩 emoji + 默认文案）。素材到位后 admin 改 sys_config 一行即生效，零代码变更。
- **R3（my-list 路由同日 BEAN-006 建）**：「我的预约」navigateTo `/pages/bean/my-list`，该路由本日晚些由 BEAN-006 注册到 pages.json。BEAN-006 merge 前点该入口会 navigateTo fail（toast 网络错误）。我**未动 pages.json**（避免与 BEAN-006 并行注册冲突）。
- **后端 2 个既有 typecheck 错误**（BizCustomerServiceFab / login）非本 ticket 引入，不阻塞本 ticket 产物构建。

## 待 Kevin 批量人验关注（mp 端）

- 拼豆 tab 落地页 happy path（已登录）：tab 切「拼豆」→ 看到 banner 占位 + 主 CTA →「立即预约」跳选座页。
- AC 6 未登录：useNavGuard 在 onShow 拦截弹「登录后才能预约拼豆」（GZ-ADMIN-005 已定守卫）；点 CTA 也走 ensureLoggedIn 二次兜底。
- banner 占位图视觉（C 设计系统遵循度：粗墨边 + 网点 + MOCK 水印）。
- 规则卡 3 条文案语感。

## 对下游 ticket 的提示

- **GZ-BEAN-006（我的预约列表，同日）**：① 需在 pages.json 注册 `pages/bean/my-list` 路由（本 ticket 未动 pages.json）；② 本落地页「我的预约」入口已 navigateTo `/pages/bean/my-list`，BEAN-006 建好即天然可达，无需再加入口。
- **运营/admin 侧**：banner 配置 key = `gz.bean.home.banner`，value 是 JSON `{imageUrl,title,link}`。若后续做 admin banner 配置页，复用该 key。
- **其它需匿名读 sys_config 的 mp 落地页**：直接复用 `GET /app/gz/common/config/get?key=` + mp `getSysConfig(key)`，已是通用公开端点。

## §AI 测试段（Tier 1B）

> 说明：本 ticket **无 admin 端**（纯后端公开端点 + mp 落地页），故无 Playwright admin E2E。
> Tier 1B 的 mp vitest unit + API 契约回归 + 可达性检查由 kevin-coder 代行（当前会话工具集无独立 spawn kevin-qa 能力）。
> 真机 wx 原生调用（守卫弹窗 / getUserProfile / 真机渲染）按规约跳给 Kevin 批量人验。

### vitest unit（新 banner 兜底链路 + API 契约回归）
```
$ pnpm test src/api/gz-common.test.ts src/api/gz-bean.test.ts src/api/customer-service.test.ts

 ✓ src/api/gz-common.test.ts (7 tests) 6ms
 ✓ src/api/customer-service.test.ts (3 tests) 7ms
 ✓ src/api/gz-bean.test.ts (12 tests) 3ms

 Test Files  3 passed (3)
      Tests  22 passed (22)
```
（gz-common.test.ts 新增 7 用例覆盖：query 透传 / 正常 JSON 解析 / 空串兜底 / 非法 JSON 兜底 / 缺字段独立兜底 / http 抛错兜底 / BEAN_HOME_BANNER 常量 key。stderr 的 Error 是用例**故意触发**的兜底路径 console.warn，非失败。）

### API 契约回归（既有 mp api 测试无破坏）
```
$ pnpm test src/api/gz-bean.test.ts
 ✓ src/api/gz-bean.test.ts (12 tests) 3ms
 Test Files  1 passed (1)
      Tests  12 passed (12)
```

### Tier 2 可达性检查（CLAUDE.md §8.3）
```
$ grep -rn "Tier2-entry-temp|bean.entry|tempEntry|goSelect" src/   → 无残留（exit 1）
  ✅ GZ-BEAN-003 临时入口已被本 ticket 清理（用真落地页 CTA 替换，可达路径不断）

可达路径（已验证产物含目标路由）:
  拼豆 tab → /pages/bean/index（落地页本身，N=0 直达，tabBar 已配）
  「立即预约」→ /pages/bean/select（已存在，N=1 可达，index.js 含该 navigateTo）
  「我的预约」→ /pages/bean/my-list（index.js 含该 navigateTo；BEAN-006 注册路由后 N=1 可达）
```

### 后端契约自检（@SaIgnore 公开 + ConfigService SPI）
```
GzConfigMpController:
  @SaIgnore + @RequestMapping("/app/gz/common/config") + GET /get?key=
  注入 org.dromara.common.core.service.ConfigService（gz-common 已依赖 common-core）
  mvn compile + install 均通过（见 Tier 1A）
未带 token 访问验证 → 待后端启动后 curl（命令见 Tier 1A §curl 段；编译期已保证路由注册）
```

### Tier 1B 结论
- mp vitest unit + API 契约回归：✅ 22/22 通过
- Tier 2 可达性：✅ 临时入口已清理 + 3 条路径产物验证
- 后端公开端点契约：✅ @SaIgnore + ConfigService 编译期保证
- 待 Kevin 批量人验（真机）：未登录守卫弹窗交互 / banner 占位视觉 / CTA 跳转真机走通
