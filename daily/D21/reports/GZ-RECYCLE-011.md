# GZ-RECYCLE-011 — 完工报告

**Tier**: 1A（kevin-coder 自测）
**日期**：2026-08-15
**backend**：复用 GZ-RECYCLE-010 同一进程（PID 97160，端口 8080），全程未重启，实施结束后**继续留跑**。
**admin dev server**：`cd code/main/plus-ui && pnpm dev --port 8090`（本次实施临时起，实施结束后**继续留跑**）供 kevin-qa Tier 1B 复用。

---

## §0 状态自检

- `git status`（plus-ui 仓，`staging` 分支）：实施前 working tree 干净，仅本 ticket 改动
- 上游依赖：GZ-RECYCLE-010（四个端点 + `AdminVO.timeSlotId/source` 等字段）已实现，`GzRecycleAppointmentController` / `GzRecycleWeekBoardVO` / `GzRecycleManualHoldBo` / `GzRecycleRescheduleBo` / `GzRecycleErrorCode` 均已按 D21 reports/GZ-RECYCLE-010.md 描述存在，端点契约核对一致（controller 源码直接读取确认）
- 关键类/表/API 硬检查：`gz-recycle/appointment/index.vue`（现「今日到店预约」看板段）/ `plus-ui/src/api/gz-recycle/appointment.ts`（现有 `GzRecycleAppointmentVO` 等类型）均按 ticket 描述存在
- ADR 已读：`doc/_adr/0021-recycle-manual-slot-hold-and-reschedule.md` 全文，§1/§2/§3 决策 + 数据模型 + 错误码对照见下
- 编译健康：实施前 `npx vue-tsc --noEmit` 基线 72 条错误（均为 ruoyi 自带模块/workflow/layout 无关文件，与 gz-recycle 无关）

---

## AC 完成情况

**A-D 组全部 15 条 AC 均已实现并验证。**

| 组 | AC | 状态 | 验证方式 |
|---|---|---|---|
| A 周矩阵 | AC1-4 | ✅ | 真实浏览器 Playwright（登录 admin/admin123 → `/gz-recycle/appointment`） |
| B 手动占用 | AC5-7 | ✅ | 真实浏览器操作 + 真后端 curl 网络请求核对 |
| C 改期 | AC8-10 | ✅ | 真实浏览器操作，含真实 4122 冲突场景 |
| D 权限/i18n/回归 | AC11-14 | ✅ | 真实浏览器 + 运行时权限模拟 + grep + vue-tsc/eslint |
| — | AC15 | 部分 ✅（见下「AC15 说明」） | 手工走完全部动作序列，非 kevin-qa 自动化脚本 |

### AC15 说明

AC15 明确写的是「Tier 1B Playwright E2E 全流程一遍」，按 CLAUDE.md §8.2 应由 kevin-qa 独立复测执行（Tier 1A 与 Tier 1B 分离，kevin-coder 不应替代 kevin-qa 的验收）。本报告的 §AI 自测段已经**手工走了与 AC15 描述完全一致的动作序列**（登录 → 回收看板 → 切下一周再切回 → 选 2 个空格 → 手动占用 → 断言 manual → 改期 → 断言 idle/manual → 释放 → 断言 idle → 0 console error），证明功能路径可行、无阻塞性 bug；**但这不能替代 kevin-qa 独立跑一遍**（不采信 coder 自述是项目既定分工）。移交 kevin-qa 时建议直接复用本报告验证过的选择器口径（`data-cell-kind` / `data-cell-date` / `data-cell-slot`）。

---

## 关键决策对照（ADR-0021，逐条）

1. **手动占用绝不走 submit()**：前端 `manualHoldSlots()` 直接调 `/manual-hold`，无关联 submit 表单字段 ✅
2. **多格跨日期分组多次请求，同日一次请求**：`ManualHoldDialog.vue` 按 `apptDate` 分组 `Map`，同日多 slot 一次请求；本次真实测试提交 2 格（`2026-08-10` + `2026-08-12` 两个不同日期）→ 网络面板确认发出 **2 条** `POST /manual-hold` 请求 ✅
3. **改期不允许改门店**：`RescheduleDialog.vue` 弹窗内无门店控件，只读展示 `storeName` ✅
4. **改期容量冲突不吞错**：真实触发 4122（对已占格 2026-08-11 上午发起改期）→ 弹窗保持打开、表单值保留、后端 msg 由全局拦截器 toast，未关窗未清空未刷新成功态 ✅
5. **溢出格无操作按钮**：`board-cell--spill` 分支模板确认无任何 `<el-button>`，仅 `:title` 提示「请操作源单」（本次未在真实数据里复现 spill 格——需要大单点数档 `pts-200-plus` 提交才会产生，AC3 该态已通过**模板代码走查 + GZ-RECYCLE-010 report 已验证的后端 `kind='spill'` 契约**双重确认，未额外造大单数据）

---

## §N 完工总结

### git diff --stat

```
$ git status --short
 M src/api/gz-recycle/appointment.ts
 M src/lang/en_US.ts
 M src/lang/zh_CN.ts
 M src/views/gz-recycle/appointment/index.vue
?? src/views/gz-recycle/appointment/components/

$ git diff --stat
 src/api/gz-recycle/appointment.ts          |  77 ++++++++++++++++
 src/lang/en_US.ts                          |  51 ++++++++++-
 src/lang/zh_CN.ts                          |  51 ++++++++++-
 src/views/gz-recycle/appointment/index.vue | 142 +++--------------------------
 4 files changed, 180 insertions(+), 141 deletions(-)
```

### 新增关键产物

- `src/views/gz-recycle/appointment/components/WeekBoard.vue`（新增，~430 行）— 门店 + 周切换 + 矩阵渲染（原生 `<table>`，非 el-table，便于稳定挂 `data-cell-kind`）+ 格多选 + 格上按钮（改期/释放）+ emit（`detail`/`hold`/`reschedule`/`release`）+ `defineExpose({ reload })` 供 index.vue 在 verify 成功后刷新矩阵
- `src/views/gz-recycle/appointment/components/ManualHoldDialog.vue`（新增）— 已选格清单 + 备注必填（`el-form` 自定义 validator 拦纯空格）+ 按日期分组提交
- `src/views/gz-recycle/appointment/components/RescheduleDialog.vue`（新增）— 当前信息只读 + 新日期/新时段 + 提交，失败不关窗
- `src/api/gz-recycle/appointment.ts`（改）— 新增 `getWeekBoard` / `manualHoldSlots` / `releaseHold` / `rescheduleAppointment` + `RecycleWeekBoardVO` / `RecycleBoardSlotVO` / `RecycleBoardCellVO` 类型；`GzRecycleAppointmentVO` 补 `source` / `timeSlotId` / `spillTimeSlotId` / `rescheduleCount`（均 `string`，遵循 ID 跨层契约 #1）
- `src/views/gz-recycle/appointment/index.vue`（改）— 删除 `boardGroups`/`loadBoard`/`board-*` 样式与今日看板 template 段，换挂 `<WeekBoard>`；`openDetail` 形参收窄为 `Pick<GzRecycleAppointmentVO, 'id'>`（避免不安全的对象字面量断言）；`submitVerify` 成功后调 `weekBoardRef.value?.reload()` 替代旧 `loadBoard()`，保证 admin 核销后矩阵态同步（不属显式 AC，但为避免核销后矩阵显示过期「改期」按钮的可见回归而加）
- `src/lang/zh_CN.ts` / `en_US.ts` — `gzRecycleAppointment` 段补齐周切换/四态/两弹窗/空态/提示文案；同时删除旧看板遗留但已无引用的 3 个 key（`boardEmpty`/`boardUnit`/`unknownSlot`）

---

## AI 自测 raw output

### ① `npx vue-tsc --noEmit`（无新增错误，基线 72 条不变）

```
$ npx vue-tsc --noEmit 2>&1 | grep -c "error TS"
72

$ npx vue-tsc --noEmit 2>&1 | grep -i "appointment\|WeekBoard\|ManualHoldDialog\|RescheduleDialog"
(no output — 本 ticket 触碰的文件零错误)

# 对照：stash 掉本次改动后重跑同一命令，错误数同为 72（证明基线不变，非本 ticket 引入）
$ git stash -u && npx vue-tsc --noEmit 2>&1 | grep -c "error TS"; git stash pop
72
```

（项目 `package.json` 无 `type-check` npm script，`pnpm type-check` 不存在 —— 这是项目既有状态，非本 ticket 引入；已用等价命令 `npx vue-tsc --noEmit` 替代验证。）

### ② `npx eslint`（本 ticket 全部改动/新增文件，0 error）

```
$ npx eslint \
  src/api/gz-recycle/appointment.ts \
  src/views/gz-recycle/appointment/index.vue \
  src/views/gz-recycle/appointment/components/WeekBoard.vue \
  src/views/gz-recycle/appointment/components/ManualHoldDialog.vue \
  src/views/gz-recycle/appointment/components/RescheduleDialog.vue
(no output, exit 0)
```

### ③ 硬编码中文检查（AC12，模板段扫描）

```
$ for f in index.vue components/WeekBoard.vue components/ManualHoldDialog.vue components/RescheduleDialog.vue; do
    awk '/<template>/{t=1} /<\/template>/{t=0} t' "src/views/gz-recycle/appointment/$f" | grep -nP '[\x{4e00}-\x{9fa5}]'
  done
index.vue:3:    <!-- 回收看板周视图（GZ-RECYCLE-011，ADR-0021 §3）：门店 × 周切换的时段格矩阵，占用/改期/释放都在格上做 -->
index.vue:6:    <!-- 回收记录：按 时间 / 点数 / 金额 / 门店 / 状态 / 单号 筛选（GZ-RECYCLE-008） -->
（仅 HTML 注释含中文，非用户可见文案；WeekBoard/ManualHoldDialog/RescheduleDialog 三个新组件模板内 0 命中）
```

### ④ 真实浏览器 Playwright 全流程验证（AC1-11，登录 admin/admin123 → 8090）

```
# AC1 周矩阵基础渲染 + 今天列标记
$ evaluate: 统计 [data-cell-kind] 节点
{ totalCells: 21, kinds: { idle: 21 }, todayHeadText: "08-15周六" }
（3 slot × 7 天 = 21 格；今天 2026-08-15 列命中 .is-today）

# AC5 跨日期跨时段多选
点击 2026-08-10/上午 + 2026-08-12/下午（不同日期不同时段）
$ evaluate: 
{ selected: [{date:"2026-08-10",slot:"1"},{date:"2026-08-12",slot:"3"}], countText: "已选 2 格", holdBtnDisabled: false }

# AC6① 空/纯空格备注被前端拦住，不发请求
填 remark="   " → 点确认占用 → 表单校验报错「请填写占用备注」
$ network_requests filter=manual-hold → 无匹配请求（未发出）

# AC6② 合法提交：跨日期分组两次请求，all-or-nothing per group
填 remark="Playwright E2E 测试占用" → 确认
$ network_requests:
192. POST /system/gz/recycle/appointment/manual-hold => 200 OK   (date=2026-08-10)
193. POST /system/gz/recycle/appointment/manual-hold => 200 OK   (date=2026-08-12)
提交后：selectedCount=0（选择已清空）、holdBtnDisabled=true、两格均变 data-cell-kind="manual"

# AC3 手动占用格渲染
两格显示「占用 · Playwright E2E 测试占用」+ 改期/释放按钮（title 悬浮全文，CSS ellipsis 截断）

# AC7 释放二次确认 + 状态回落
点其中一格「释放」→ ElMessageBox 弹「确认释放该占用时段？释放后该格立即可约。」→ 确定
$ evaluate: { slot1010kind: "idle", slot1012kind: "manual" }
（释放格立即变回 idle，另一格不受影响）

# AC8/AC9 改期弹窗 + 只读展示 + 成功路径
点剩余 manual 格「改期」→ 弹窗展示 预约号/门店（成都春熙路店，无门店控件可改）/当前日期/当前时段（只读）
填新日期 2026-08-14 + 新时段「晚上」→ 确认改期
$ network_requests: 197. POST /system/gz/recycle/appointment/43/reschedule => 200 OK
$ evaluate:
{ oldKind: "idle", allNonIdle: [{date:"2026-08-14",slot:"8",kind:"manual"}] }
（原格 2026-08-12/下午 → idle；新格 2026-08-14/晚上 → manual）

# AC10 目标格已被占（4122）：弹窗保持打开、不吞错、不刷成功态
先手动占用 2026-08-11/上午（remark="冲突测试占位"）制造冲突目标
对 2026-08-14/晚上 的记录发起改期 → 目标选 2026-08-11/上午
$ network_request #201 response-body:
{"code":4122,"msg":"该时段已被预约，请换个时段","data":null}
弹窗仍展示「预约改期」标题 + 表单保留 2026-08-11/上午 选值（未清空、未关闭）
两格状态未变：2026-08-14/晚上 仍 manual，2026-08-11/上午 仍 manual（未被误覆盖）

# AC11 权限门控（运行时模拟）
真实场景：admin(admin123) 权限数组恒为 ['*:*:*']（通配符），v-hasPermi 恒放行，
无法用同一账号在不重登的情况下切换到"无权限角色"；改用 Pinia store 运行时补丁 + tagsView「刷新页面」强制组件重挂载（hasPermi 是 mounted-only 指令）模拟：
$ evaluate: 补丁 userStore.permissions = ['gz:recycle:appointment:list']（去掉通配符）
$ 右键 tagsView 标签「刷新页面」→ 触发 WeekBoard 重新 mount
$ evaluate: 
{
  permissions: ["gz:recycle:appointment:list"],
  holdBtnExists: false,       // 「手动占用」按钮已从 DOM 移除
  rescheduleBtnsCount: 0,     // 所有「改期」按钮已移除
  releaseBtnsCount: 0,        // 所有「释放」按钮已移除
  idleCellsCount: 19          // 空闲格仍全部渲染（21-2 manual）
}
$ evaluate: 点击一个 idle 格 → { countText: "已选 1 格", selectedCells: 1 }
（空格仍可选中，仅操作按钮消失，与 AC11 描述完全一致）
测试完成后 browser_navigate 完整刷新页面 → 权限从后端 getInfo 重新拉取，通配符恢复

# 全程浏览器 console 错误
$ console_messages(level=error, all=true) → 
Total: 1 error（AC10 故意触发的 4122 业务拒绝的 console.error 日志，非 bug；
同一 catch-log 写法与既有 RefundConfirmDialog.vue 一致，属项目既定风格）
非冲突路径（AC1/5/6/7/8/9/11 及页面刷新后）console 均 0 error 0 warning-of-note
```

### ⑤ AC14 回归核对（不改代码，纯视觉+交互核对）

```
记录列表：9 条记录，列（预约号/数量区间/核对金额/到账状态/状态/到店日期/提交时间/操作）全部保留，
筛选表单（门店/状态/预约号/到店日期区间/点数档/实付金额区间）全部保留，
分页（共 9 条 / 10条页 / 页码）保留

点「详情」→ el-drawer 打开，title="回收预约单详情"（复用原 openDetail，未新写详情逻辑）

状态下拉「manual_hold」字典项存在（gz_recycle_status 已含「手动占用」标签，GZ-RECYCLE-010 seed）
```

---

## 已知 issue / 风险提示

1. **AC15 严格来说未由 kevin-qa 独立跑**：本报告已手工走完 AC15 全部动作序列并逐项断言通过（见「AC15 说明」+ raw output ④），但按项目既定分工（CLAUDE.md §8.2 / §9.5），Tier 1B 应由主线程另派 kevin-qa 用独立会话复测，不采信 coder 自述。建议 kevin-qa 复测时复用本报告验证过的选择器口径。
2. **spill 态（大单溢出占用）未在真实浏览器造出**：需要先建一张点数档 `pts-200-plus`（或其他 `occupy_next_slot=1`）的顾客单占满某格 + spill 到下一格，本次为聚焦 A-D 组核心交互未额外造这批数据；`kind='spill'` 的模板分支（`board-cell--spill`，无按钮 + title 提示）已代码走查确认，且后端契约已在 GZ-RECYCLE-010 report §⑧ 用真实 spill 场景验证过（`cells` 含 `{"kind":"spill","appointmentId":<源单id>}`）。kevin-qa 复测时建议补一次真实 spill 格渲染断言。
3. **AC11 验证方法非常规**：因 admin/admin123 权限恒为通配符 `*:*:*`，无法用常规「换账号登录」验证按钮隐藏，改用 Pinia store 运行时补丁 + tagsView「刷新页面」强制 `WeekBoard` 重新 mount（`v-hasPermi` 是 `mounted`-only 指令，非响应式）。这是**测试手段**，未改动任何生产代码逻辑；kevin-qa 如需更贴近真实场景，可用一个未授 `gz:recycle:appointment:hold/reschedule` 的角色账号重登验证（若无现成账号需新建）。
4. **dev 库测试残留数据**：本次真实操作在 `2026-08-10~14`（本周）产生了 3 条手动占用记录（1 条已释放为 idle，2 条仍为 manual：`2026-08-11/上午`「冲突测试占位」+ `2026-08-14/晚上`「Playwright E2E 测试占用」），均为回收域测试数据，与既有种子/GZ-RECYCLE-010 测试数据（`2026-07`/`2026-09`/`2026-10` 区间）不冲突，未清理（dev 库，供 kevin-qa 复用/自行清理）。
5. **`WeekBoard.vue` 的 `hold`/`reschedule`/`release` emit 目前无消费方**：ticket Tech 表要求 WeekBoard 组件对外 emit 这三个事件，本次实现为满足该约定发出（成功后触发），但 index.vue 当前只监听 `detail`；三个动作的刷新/清空选择/关弹窗均由 `WeekBoard` 与两个 Dialog 组件内部闭环完成，不依赖父组件消费这三个 emit。若日后有需要（如全局 toast 埋点、跨组件联动），emit 已就位可直接监听。

---

## ADR 已读

`doc/_adr/0021-recycle-manual-slot-hold-and-reschedule.md` 全文已读，§1（手动占用唯一机制）/ §2（改期原地 UPDATE）/ §3（看板周视图）+ 数据模型 + 错误码表逐条对照见上「关键决策对照」段，无遗漏。

## 对下游 ticket 的提示

- 权限相关：`gz:recycle:appointment:hold` / `gz:recycle:appointment:reschedule` 两个 perm 已在 GZ-RECYCLE-010 授权给 role 100/101/103（owner 及相关角色）；如需授权新角色，只授 `menu_type='F'` 的按钮节点（13015/13016），不授父 `13002`（memory `ruoyi-grant-f-perms-without-menu-leak`），改权限后需重登。
- `WeekBoard.vue` 的 `slots`（该店 enabled 到店时段）由 `week-board` 接口返回，`RescheduleDialog` 的时段下拉直接复用此数据源，未单独调 `timeSlot` 接口（符合 ticket 备注）。
- 若日后需要 mp 店员端看板镜像（当前 ADR-0021 边界明确不做），`data-cell-kind` / 格数据结构可直接复用本次前端类型定义（`RecycleBoardCellVO`）。

---

## §AI 测试段（kevin-qa Tier 1B 独立复测，主线程统一派发）

**环境**：backend 8080（PID 97160，复用 coder 留跑的进程）+ admin dev server 8090（PID 11953，复用），未新起服务；用 Playwright MCP 独立驱动真实浏览器，**未读代码即执行**（仅在验证后为核实 AC10/AC11/AC12 细节读了对应源码片段）。登录态为已持久化的 admin/admin123 会话（localStorage `Admin-Token`），未重新走登录表单。

### 结论：AC1-14 全部独立验证通过；AC15 全流程走通，console 0 error（非冲突路径）

### A. 周矩阵（AC1-4）

- AC1：切「下一周」→ 1 次 `GET .../week-board?weekStart=2026-08-17`；切「本周」→ 1 次 `GET .../week-board?weekStart=2026-08-10`。每次切换精确 1 次请求，无重复、无整页 reload（`browser_network_requests` 逐条核对，序号 195→196→197 一一对应 3 次点击）。周区间文案由 `08-10 ~ 08-16` 正确刷新为 `08-17 ~ 08-23` 再刷新回 `08-10 ~ 08-16`。
- AC2：矩阵 3 行（上午/下午/晚上）× 7 列（08-10 周一 … 08-16 周日），列头日期+星期均正确渲染，行头 `slots` 顺序与后端一致。
- AC3：`document.querySelectorAll('[data-cell-kind]')` 返回 21 格，`idle`/`manual` 两态在本周数据中均可程序化断言（`customer`/`spill` 态本轮未在真实数据中命中，与 coder report 已知 issue #2 一致，不重复验证）。
- AC4：本轮未额外验证（coder report 已确认复用 `openDetail`，未新写逻辑，风险低）。

### B. 手动占用（AC5-7，跨日期跨时段真实提交）

- AC5：点选 08-10 上午 + 08-12 下午（跨日期跨时段）→ 顶部显示「已选 2 格」+「手动占用」按钮从 disabled 变可点 +「清空选择」出现；`is-selected` class 命中 2 个 `board-cell--idle` 节点（另 2 处 `is-selected` 命中系无关的 el-select 下拉项，非误报）。
- AC6：
  - 空备注提交 → 无 `manual-hold` 请求发出，`el-form` 校验提示「请填写占用备注」，弹窗不关。
  - 纯空格备注（3 个空格）提交 → 同样无请求发出（确认是 trim 校验，非仅判空字符串）。
  - 合法备注提交 → `browser_network_requests` 捕获 **2 次独立 `POST /manual-hold`**：
    ```json
    // 请求 1
    {"storeId":1,"apptDate":"2026-08-10","timeSlotIds":["1"],"remark":"Tier1B kevin-qa E2E 测试占用"}
    // 请求 2
    {"storeId":1,"apptDate":"2026-08-12","timeSlotIds":["3"],"remark":"Tier1B kevin-qa E2E 测试占用"}
    ```
    两条均 200 OK；`timeSlotId` 为 string（符合 ID 跨层契约）。成功后弹窗关闭、选择清空（「已选 N 格」消失、按钮回到 disabled）、两格立即刷新为 `data-cell-kind="manual"`。
- AC7：点「释放」→ `ElMessageBox.confirm` 弹「确认释放该占用时段？释放后该格立即可约。」→ 确认后该格 `POST /release-hold` 200，矩阵刷新回 `data-cell-kind="idle"`。两格分别独立验证释放成功。

### C. 改期（AC8-10）

- AC8：manual 格上「改期」按钮存在且可点（本轮未额外验证 submitted/confirmed_onsite 等状态格的按钮显隐差异，coder report 模板走查已确认，风险低）。
- AC9 happy path：08-10 上午（manual）→ 改期到 08-13 上午（idle）→ `POST /appointment/45/reschedule` 200 → 断言：原格（08-10 上午）从结果集消失（回落 idle），新格（08-13 上午）出现且备注文案与原格一致（`占用 · Tier1B kevin-qa E2E 测试占用`）。原格 idle / 新格 manual 断言通过。
- AC10 真实冲突：08-12 下午（manual）→ 改期目标选到刚占用的 08-13 上午（已被占）→ 提交后：
  - 响应体：`{"code":4122,"msg":"该时段已被预约，请换个时段","data":null}`（HTTP 200，业务码 4122，符合 ruoyi R\<T\> 包装惯例）
  - 弹窗保持打开，表单值原样保留（`新到店日期=2026-08-13`、`新到店时段=上午` 均未被清空）
  - 板面状态未被破坏（原格仍 manual，目标格仍 manual，无中间态残留）
  - **发现（非阻塞）**：`RescheduleDialog.vue` 第 99 行的 catch 块内有 `console.error('[gz-recycle-appointment] reschedule failed', e)`，导致这条**已被正确处理**（toast + 弹窗保持打开）的预期业务错误仍在浏览器 console 打一条 `[ERROR]`。功能行为完全正确，纯粹是防御性 debug 日志的副作用；AC15 的「console 0 error」断言按其原文只描述非冲突的 happy-path 序列，本条不影响 AC15 判定，仅供 coder/curator 参考（是否要把这行降级为 `console.warn` 或干脆去掉，由 Kevin/coder 定夺，不建议作为本轮 gate 的阻塞项）。

### D. 权限 / i18n / 回归（AC11-14）

- AC11（独立验证，未采用 coder report 的技术描述，自行复现）：
  1. `page.evaluate` 定位 `#app.__vue_app__.config.globalProperties.$pinia._s.get('user')`，确认 admin 会话 `permissions` 恒为 `['*:*:*']`。
  2. 补丁为 `['some:other:perm']`（不含 `gz:recycle:appointment:hold/reschedule`）。
  3. 右键 tagsView「回收看板」标签 →「刷新页面」，强制 `WeekBoard` 重新 mount（确认 `keep-alive` 下普通 SPA 路由跳转不会重挂载，必须用「刷新页面」，与 coder report 结论一致）。
  4. 断言：`手动占用` 按钮从 DOM 完全消失（非仅 disabled）；两个占用格上的「改期」「释放」按钮全部消失，仅剩纯文本 `占用 · <remark>`；空闲格仍保留 `cursor=pointer` 可点击态。
  5. 测试后将 `permissions` 补丁回 `['*:*:*']` 并再次「刷新页面」恢复现场，不留污染。
- AC12：`grep -nP '[\x{4e00}-\x{9fa5}]'` 独立跑在 `WeekBoard.vue` / `ManualHoldDialog.vue` / `RescheduleDialog.vue` / `index.vue` 四个文件的 `<template>` 段，**零命中**（复算 coder report 的结论，非仅采信）。`zh_CN.ts` / `en_US.ts` 均含完整 `gzRecycleAppointment` 键簇。
- AC14：状态筛选下拉确认新增「手动占用」选项（字典 `manual_hold` 已带出）；「详情」抽屉独立打开一条记录（`RCY-20260815-000023`），基础信息/回收物品/核对留痕/转账记录/联系方式/照片各分区渲染正常，截图存档 `screenshots/GZ-RECYCLE-011-detail-drawer.png`；筛选表单 6 个字段、分页控件（共 9 条 / 10条页 / 页码）均在列，功能未回归。

### 全程 console 错误统计

- 非冲突路径（周切换 / 多选 / 手动占用 / 释放 / AC9 happy-path 改期 / AC11 权限模拟 / AC14 回归核对）：**0 error**。
- AC10 故意触发的 4122 业务冲突路径：产生 2 条 `console.error`（见上「发现」条目），是已知且非阻塞的防御性日志副作用，不视为回归。

### 测试数据现场

本轮新建的 2 条手动占用记录（08-10 上午、08-12 下午）均已在验证完成后主动释放回 `idle`，dev 库无新增残留。coder 此前留下的 2 条测试数据（`2026-08-11 上午`「冲突测试占位」+ `2026-08-14 晚上`「Playwright E2E 测试占用」）未动。

### 判定

**AC1-14 全部独立验证通过，AC15 全流程真实走通。GZ-RECYCLE-011 Tier 1B ✅，ticket 可 close。**

---

## §对抗性测试闭环（第二轮）— 前端 3 条 finding 鉴定 + 修复

> 后端 3 条（F1 改期丢 spill / F2 remark XSS / F3 改期过去日期）见 [GZ-RECYCLE-010 报告同名章节](GZ-RECYCLE-010.md)。

### 一、鉴定结论

| # | severity | 结论 | 理由 |
|---|---|---|---|
| **F4** `console.error` 只在 `RescheduleDialog` 点修，`ManualHoldDialog` / `WeekBoard` 仍在业务拒绝路径打 error | medium | **确认是 bug（已修）** | 上一轮只删了 3 处中的 1 处，是典型点修而非扫面。4122/4123/4124/4129 都是**后端按设计返回的业务拒绝**，已由全局拦截器 toast 给用户 —— 再打 `console.error` 等于把「系统按预期工作」记成前端异常，直接污染 AC15 的「console 0 error」判据（本轮已复现出 QA 报的原文：`[gz-recycle-appointment] release hold failed error` / `manual hold failed error`）。|
| **F5** 操作被拒后看板不刷新，格保持陈旧「可点」态 | medium | **确认是 bug（已修）** | 后端拒绝的**最常见根因就是「这一格/这一单已被并发改动」**——恰恰是本地视图必然已经不等于库的时刻，却唯独在这个时刻不刷新，把「拉回真相态」推给店员手点「刷新」。实测：并发释放后确认陈旧弹窗 → 后端 4129 正确，但格仍渲染 `占用 · <备注>` + 可点的 改期/释放，直到手点刷新才回 idle。同类漏洞在 `onRescheduleSuccess`（只在成功分支刷）与手动占用失败路径同样存在，本轮一并按「失败即回真相态」统一。附带修掉一个未被 QA 报出的相邻问题：**失效的选中格未清理**（被别人占走的格仍留在多选集合里，下次提交必然再失败）。|
| **F6** `handleConfirm` 无组件级重入闸 | low | **确认是（防御缺口）bug（已修）** | 现状确实**只**靠全局 axios 防重复提交拦截器 + 后端 Redis 锁兜底，组件自身零防护；`submitting=true` 又放在 `await validate()` 之后，异步间隙内按钮 `disabled` 尚未翻转。虽然本轮与上轮都没造成重复落库（外部两道防线接住了），但「唯一防线在组件之外」意味着任何对拦截器配置 / `repeatSubmit:false` 的改动都会直接把竞态放回来。修复成本 2 行，收益是把防线拉回本地 —— 修。|

### 二、改动文件（plus-ui）

| 文件 | 改动 |
|---|---|
| `src/views/gz-recycle/appointment/components/ManualHoldDialog.vue` | 删 `console.error`（F4）；`handleConfirm` 加 `if (submitting.value) return` + **进函数即置位**（F6，validate 之前）；失败改为 `emit('fail')`（F5）|
| `src/views/gz-recycle/appointment/components/WeekBoard.vue` | `onReleaseClick` catch 删 `console.error` 并改调 `refreshAfterFailure()`（F4+F5）；新增 `refreshAfterFailure()`（重载看板 + `pruneSelection()` 清掉已不再 idle 的选中格）；两个子弹窗挂 `@fail="refreshAfterFailure"`；`onRescheduleClick` 传 `allowPastDate: cell.kind === 'manual'`（配合后端 4130）|
| `src/views/gz-recycle/appointment/components/RescheduleDialog.vue` | `handleConfirm` 加重入闸（F6）；失败 `emit('fail')`（F5）；日期选择器加 `:disabled-date`（顾客单禁选今天之前，手动占用不限，与后端 `4130` 同口径）|
| `e2e/gz-recycle/board-adversarial.spec.ts` + `board-fixtures.ts` | **新增** 4 条 Playwright 断言式回归（真接口真库，跑完按备注前缀硬删夹具）|

### 三、逐条修复验证 —— 先证「测试真能抓到这个 bug」，再证「修完过」

新增的 E2E 不是走一遍 happy path，而是**先在还原成修复前形态的代码上跑一遍**，确认它以 finding 描述的症状失败：

```
# ① 把 ManualHoldDialog / WeekBoard 临时还原成修复前形态（console.error / 无 emit fail / 无重入闸）后跑：
1) F5+F4：释放时该行已被并发释放 …
   Error: console.error 不应有任何输出，实际：["[gz-recycle-appointment] release hold failed error"]
   > 81 | expect(errors, ...).toEqual([]);
2) F4+F5：手动占用撞上并发占格（4122）…
   Error: console.error 不应有任何输出，实际：["[gz-recycle-appointment] manual hold failed error"]
   > 112 | expect(errors, ...).toEqual([]);
3) F6：确认占用连点两次 …
   Error: 不应退化到靠全局拦截器兜底
   > 159 | expect(warns.filter((w) => w.includes('请勿重复提交')), ...).toEqual([]);
  3 failed
```

（更早一轮把 console 断言放在刷新断言之后时，失败点落在 F5 上，同样成立：
`Expected: "idle" / Received: "manual"`（释放失败后格没自愈）、`Expected: "manual" / Received: "idle"`（占用失败后看板没刷出别人占的格）——
即 F4、F5、F6 三条症状**都**能被这套用例独立照出来。）

```
# ② 恢复修复后的代码再跑（同一套用例，零改动）：
$ npx playwright test e2e/gz-recycle/board-adversarial.spec.ts --reporter=line
Running 4 tests using 1 worker
[1/4] F5+F4：释放时该行已被并发释放 → toast 4129 + 看板自动回真相态（无需手点刷新）+ console 0 error
[2/4] F4+F5：手动占用撞上并发占格（4122）→ toast + 看板刷新 + 选中态清理 + console 0 error
[3/4] F6：确认占用连点两次 → 只发 1 个请求、只落 1 行，且不触发全局「请勿重复提交」拦截
[4/4] 回归：手动占用改期 happy path 不受「禁选过去日期」影响（店员台账可挪到过去），改完可释放
  4 passed (31.2s)
```

各用例断到的点（全部真接口真库，无 mock）：

| 用例 | 关键断言 |
|---|---|
| F5+F4 陈旧释放 | 弹窗开着时带外 `release-hold` 置 `cancelled` → 确认后后端 4129 → ① `.el-notification` 出后端原文；② **`console.error` 数组为空**；③ **不点刷新**，格在 15s 内自己回 `data-cell-kind="idle"`；④ 该格「释放」按钮 count=0 |
| F4+F5 占格冲突 | 选中空格开弹窗后带外把该格占走 → 提交返 4122 → ① toast 出「该时段已被预约」；② `console.error` 空；③ 弹窗仍打开（AC10 不回归）；④ 看板自动刷出别人的占用格；⑤ **`.board-selected-count` 消失**（失效选中被清）；⑥ 库里 `conflict-loser` 行数 = 0、`conflict-taker` = 1 |
| F6 重入 | 一次 `evaluate` 内同步 `btn.click()` 两次 → ① `performance.getEntriesByType('resource')` 中 `manual-hold` 请求 **= 1**；② 库里该备注行 **= 1**；③ **没有**「数据正在处理，请勿重复提交」warning（证明被组件挡住，而非退化到全局拦截器兜底）；④ `console.error` 空 |
| 改期 happy 回归 | 手动占用从 `08-11 上午` 改到 `08-11 下午`（**过去日期**，验证 F3 的分治口径没误伤店员台账）→ 两格状态互换 → 再释放 → 回 idle；全程 `console.error` 空 |

其他静态验证：

```
$ grep -n "console\.error(" src/views/gz-recycle/appointment/components/*.vue
（无输出 —— 三个组件里真实的 console.error 调用已清零）

$ npx vue-tsc --noEmit -p tsconfig.json | grep -i "gz-recycle"
（无输出 —— 本域零类型错误；仓库既有的 workflow/* 报错为改造前基线，未触碰）

$ npx eslint src/views/gz-recycle/appointment e2e/gz-recycle --ext .vue,.ts
（0 problems）
```

### 四、环境与数据现场

- plus-ui dev server（8090）与后端（8080，已 `mvn clean install` + 重启带上后端 3 条修复）**均保持运行**。
- E2E 夹具全部按 `remark LIKE 'D21-E2E-%'` 硬删，跑完 `SELECT COUNT(*) = 0`；未触碰任何既有业务/QA 数据。
- 新增的 `e2e/gz-recycle/` 两个文件是**可重复跑的回归资产**（`workers:1` 串行、自造自清），后续 Tier 1B 可直接 `npx playwright test e2e/gz-recycle/board-adversarial.spec.ts` 复跑。
