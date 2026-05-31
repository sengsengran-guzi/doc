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
