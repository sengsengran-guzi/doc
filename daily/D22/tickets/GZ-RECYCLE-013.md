# GZ-RECYCLE-013 — 回收 1 小时格前端（mp 表单 + admin 四页）

**优先级**: P0
**复杂度**: XL
**关联 PRD**: doc/02-prd.md §M10 回收预约
**关联拆解**: doc/02-需求拆解.md §3.6.5
**关联 mockup**: N/A（mp 走 c-tokens 清爽风 · admin 走 ruoyi 默认）
**关联 ADR**: doc/_adr/0022-recycle-hour-slot-occupancy.md · ADR-0021 §3（周看板，被修订）
**依赖**: **GZ-RECYCLE-012**（契约必须先敲定，任一条不一致返工面都是整页级）

---

## 必读权威文档

- **业务流**：doc/10-业务流权威图.md §13 回收预约全流程 + 回收看板周视图
- **字段表**：doc/11-字段权威表.md §12（012 已修正版）
- **UI 参考**：mp = 拼豆 `pages/bean/index.vue` 的 `.slot-grid`（同构参照）；admin = N/A（不评判视觉）

## 契约（与 012 对齐，动手前逐条核对）

| # | 项 | 形状 |
|---|---|---|
| 1 | mp 提交 | `POST /app/gz/recycle/appointment/submit` body 的 `timeSlotId` → **`slotStart: "HH:00:00"`**。**不传 `slotEnd`**（时长服务端权威，前端传只会制造前后端不一致的拒单） |
| 2 | mp 可用性 | `GET /slot-availability?storeId&date&qtyBucketCode=` → `{date, spanHours, slots:[{startTime, endTime, label, taken, past, selectable}]}` |
| 3 | admin 可用性 | `GET /system/gz/recycle/appointment/hour-slots?storeId&date&spanHours&excludeAppointmentId=` 同 VO |
| 4 | 周看板 VO | `slots` 列头改 `{startTime, endTime, outOfWindow}`（无 id）；`cells` 改区间块 `{apptDate, slotStart, slotEnd, spanHours, spanStart, kind:'customer'\|'manual', …}`。**`kind='spill'` 退休** |
| 5 | 手动占用 | `POST /manual-hold` body `{storeId, apptDate, slotStarts:[...], remark}` |
| 6 | 改期 | `POST /{id}/reschedule` body `{apptDate, slotStart}` |

## What

mp 回收表单 ③ 区从「命名时段 chip 单选」改为「小时格网格 + 连续 N 格高亮」；admin 回收时段页语义改「营业时间」（整点强校验 + 切格预览）、点数档页改「占用小时数」、周看板改 rowspan 日历块、改期弹窗换 `HourSlotPicker`。

## AC（验收标准）

### A. mp 表单 `pages/recycle/form.vue`

- [ ] AC1：③ 区改 `grid-template-columns: repeat(3, 1fr)` 换行网格（**不横向 scroll** —— 9-12 格 = 3-4 行一屏看完，横滑会藏格），与拼豆 `.slot-grid` 同构。chip 两行制：主行 `09:00 - 10:00`，副行状态（`可选` / `已约满` / `放不下 4 小时`）。
- [ ] AC2：**未选点数档时** ③ 区 `BizStepTitle` 照常显示（三步骨架不塌），内容区渲染「请先选择点数，再选到店时间」。
- [ ] AC3：点数档 / 门店 / 日期任一变化 → 重拉 `getSlotAvailability(storeId, date, qtyBucketCode)` 并**清空 `startSlot`**（span 变了原起点可能放不下）；加载中显示 loading 文案。
- [ ] AC4：拉回后自愈 —— `if (startSlot && !slots.find(s => s.startTime === startSlot && s.selectable)) startSlot = ''`。
- [ ] AC5：**请求竞态保护必须加** —— `let reqSeq = 0`；函数内 `const seq = ++reqSeq`；await 后 `if (seq !== reqSeq) return`。点数档 chip 会被连点，比换日期频繁得多，现有 `loadSlotAvailability` 无保护。
- [ ] AC6：不可选格点击**给 toast 不要静默 return**（现有 `onPickTimeSlot` 是静默的，用户会困惑「为什么 12 点不能点」）。文案按 `taken` / `past` / 放不下分别给。
- [ ] AC7：**「自动占用 9:00-13:00」两层呈现**（甲方明确关心的点）：
  - ① 选中起点后被覆盖的 N 格**全部** `is-on`（视觉上一条带）。计算用**时间过滤不用数组下标**（下标会被午休断档骗）→ `form.logic.ts` 新增纯函数 `addHours(hhmmss, n)` / `coveredStarts(slots, start, span)`
  - ② 网格下方绿底摘要「已选到店时间：09:00 - 13:00（占 4 小时）」
- [ ] AC8：`canSubmitRecycle` 的 `hasTimeSlot` → `hasSlotStart`（同步改 `form.logic.ts` + `form.logic.test.ts` 三处断言）；`onSubmit` payload 改 `{storeId, product, apptDate, slotStart}`。
- [ ] AC9：**视觉纪律** —— 只用 `view/text` + 既有 `Biz*`，不新增 `wd-*`、不新增 Biz 组件；样式 scoped、100% `var(--c-*)`；**选中态用回收绿 `--c-green-soft`/`--c-green`**（不要把拼豆红带进来，两域已有色彩分工）；无 emoji。
- [ ] AC10：顺手删无引用的 `components/biz/BizSlotGrid.vue`（3 档时代化石，全仓仅 `types/components.d.ts` 自动导入声明引用）。

### B. mp `api/gz-recycle.ts`

- [ ] AC11：新增 `RecycleHourSlotVO` + 容器 VO；`RecycleSubmitRequest.timeSlotId` → `slotStart`；**删** `listRecycleTimeSlots()` + `RecycleTimeSlotVO`（全仓仅 test 引用）+ `RecycleQtyRangeVO.occupyNextSlot`；`RECYCLE_ERROR_CODE` 注释更新（4123 换语义）。
- [ ] AC12：**`detail.vue` / `my-list.vue` 零改动** —— 已是 `slotStart-slotEnd` 渲染，老单走 `arrivalSlotText` 优先分支。本次最省的一块，别动。
- [ ] AC13：`api/gz-recycle.test.ts`（`getSlotAvailability` 带 `qtyBucketCode` 的 query 断言 + submit body 断言）+ `form.logic.test.ts`（`hasSlotStart` 改名 + `addHours` / `coveredStarts` 新用例）更新，`pnpm test` 全绿。
- [ ] AC14：mp i18n `locale/recycle.zh-CN.ts` 新增 `slotNeedBucket` / `slotLoading` / `slotAvail` / `slotTooShort` / `slotSpanPrefix` / `hourUnit`，改 `slotEmpty`，**保留** `arrivalMorning` / `arrivalAfternoon`（历史单回显仍在用）。

### C. admin 回收营业时间 `views/gz-recycle/time-slot/index.vue`

- [ ] AC15：`el-time-picker` 加整点强校验 —— **抽 `plus-ui/src/utils/hour-slot.ts` 共享**（照抄 `views/gz-bean/config/index.vue` 已有的 `disabledNonZero` / `isWholeHour` / `validateWindow`；不抽的话回收这边一定慢慢漂）。`format="HH:00"` + `:disabled-minutes` + `:disabled-seconds`，提交前 `validateWindow` 兜底。
- [ ] AC16：结束时间下方加「本窗口将切出 N 个小时格：10:00 / 11:00 …」预览；列表加「小时格」列显示 `N 格`。
- [ ] AC17：`label` 降级为「窗口名（仅后台）」+ hint「小程序按小时格显示时间，不再显示窗口名」；title「回收时段」→「回收营业时间」，`alertDesc` 重写说明整点 / 切格 / 多窗口 = 中间休息断档 / 跨窗口不可连占。

### D. admin 点数档 `views/gz-recycle/qty-range/index.vue`

- [ ] AC18：**删** `occupy_next_slot` 列 + 表单项（**不是隐藏** —— 留一个拨了不生效的开关，店主一定会动然后困惑）。TS 侧 VO 标 `@deprecated` 保留读兼容，表单不再提交该字段。DB 列不删。
- [ ] AC19：`duration_minutes` → UI 层「占用小时数」`el-input-number(1..12)`；提交 `×60`、加载 `ceil(/60)`；非 60 倍数的旧数据挂 warning tag「旧数据 N 分钟，保存后按 M 小时计」（**诚实提示，不静默改数**）；列表显示 `4 小时（240 分钟）`。
- [ ] AC20：`alertDesc` 重写：「配置点数档与占用时长（每 50 点 ≈ 1 小时）。顾客选档后系统从所选起点连占 N 个小时格；跨休息断档的起点不可选。」

### E. admin 周看板 `views/gz-recycle/appointment/components/WeekBoard.vue`

- [ ] AC21：改**周视图 + rowspan 日历块**（不是每格独立渲染 —— 一笔 4h 单渲 4 个格 = 现有 spill 噪音放大 4 倍）。预计算二维 `matrix: (Cell = idle | skip | block{block, rowspan})[][]`（纯函数产物、可单测；`<td>` 没法用 `v-if` 优雅跳格），模板两层 `v-for` + `v-if="cell.type !== 'skip'"` + `:rowspan`。
- [ ] AC22：`rowspan` 按 `slots` 数组下标算，`idxOf(block.slotEnd)` 找不到时退到 `slots.length`，`rowspan = Math.max(1, idxEnd - idxStart)`。
- [ ] AC23：块内容两行紧凑（第一行 `尾号4位 · 点数档`，第二行 `dict-tag 状态` + `09:00-13:00`；手动占用块 `占用 · {remark}`）；**行内按钮移除**改 `el-popover`（trigger=click）承载「详情 / 改期 / 释放」，权限指令原样搬。
- [ ] AC24：idle 保留 click-toggle 多选，另加 **shift+click 同列区间选**；`selectedCount` 文案改「已选 {n} 格（{m} 段）」。
- [ ] AC25：行头只显起点 `09:00`；窗口边界行加粗分隔线 `.is-window-start` 并用 `slot.label` 做分组提示（**这就是保留 label 的价值**）；`outOfWindow=true` 的孤儿列有可辨识标记。
- [ ] AC26：新增顶部图例（顾客单 / 手动占用 / 可选空闲）；**删** `cellKind` 的 `spill` 分支 + `.board-cell--spill` 样式 + i18n `spillHint`/`spillLabel`。
- [ ] AC27：`--row-h: 34px`，12 行总高 ~350px（比现在 3×74px 还紧凑）；`min-width: 780px` + 横向滚动保持；`refreshAfterFailure` / `pruneSelection` 并发自愈逻辑**原样保留**。
- [ ] AC28：每格根节点保留 `data-cell-kind="idle|customer|manual"` 供 E2E 断言（`spill` 值退休）。

### F. admin 两个弹窗

- [ ] AC29：`ManualHoldDialog.vue` 新增纯函数 `mergeRuns(cells)`（按日分组 → 按 slotStart 排序 → **相邻合并**，判定 `prev.slotEnd === cur.slotStart`，跨午休天然不合并）；已选 tag 显示合并后的 run（`08-30 · 09:00-13:00` **一个** tag 而非 4 个）。提交仍按日分组、all-or-nothing + 重入闸原样保留。
- [ ] AC30：新建 `components/HourSlotPicker.vue`（props `{storeId, date, spanHours, excludeAppointmentId?}`），内部调契约 #3，渲染小方块 + `disabled` + `el-tooltip` 说明不可选原因，`v-model` = `slotStart`，`date` 变化重拉。
- [ ] AC31：`RescheduleDialog.vue` 的 `el-select` 整块换成 `HourSlotPicker`；顶部 `el-descriptions` 加一行「本单时长：4 小时」（`spanHours` **前端自算**：顾客单 `ceil(matchedDurationMinutes/60)`，手动占用 `slotEnd-slotStart`，不需要后端多给字段）；选中后底部提示「改期后将占用 09:00 - 13:00」；`allowPastDate` 逻辑原样保留。
- [ ] AC32：目标格已被占时后端返 4122/4123 → 前端**直接 toast 后端 msg、弹窗保持打开**允许改选（不吞错、不关窗、不刷成功态）。

### G. 质量闸

- [ ] AC33：`api/gz-recycle/appointment.ts` 类型同步契约 #3-#6；新增 `getHourSlots`。
- [ ] AC34：plus-ui i18n `zh_CN.ts` + `en_US.ts` **同 key 同步增删**：`gzRecycleTimeSlot`（改 title/alertDesc/colLabel + 新增 colHourCells/sliceHint/ruleWholeHour）· `gzRecycleQtyRange`（改 alertDesc/colDuration + 新增 hours/durationHint/legacyMinutesWarn + **删** colOccupyNext 等 4 个）· `gzRecycleAppointment`（删 spillHint/spillLabel + 新增 legend*/blockRange/rescheduleSpanHint/hourPicker*）
- [ ] AC35：模板内无硬编码中文；`pnpm type-check` + eslint 通过，无 `any`；id 字段 `string`（ID 跨层契约）。
- [ ] AC36：**AC N(a) AI 模拟器可达**（mp ticket 强制）— kevin-qa 用 `node test/e2e/run.mjs` 程序化导航到回收表单 → 选 200 点档 → 断言起点格按 `selectable` 置灰 → 选中后 4 格连续高亮 + 摘要文案 → 提交打真后端。⚠️ **改完必须重跑 `pnpm dev:mp-weixin` 重建 `dist/dev`**（devtools import 的是 `dist/dev` 不是 `dist/build`）。
- [ ] AC37：Tier 1B Playwright：回收营业时间整点校验 + 切格预览 → qty-range 小时数 → WeekBoard rowspan 块 + popover 动作 + shift 区间选 → ManualHoldDialog run 合并 → RescheduleDialog HourSlotPicker → console 0 error。
- [ ] 纯功能 mp ticket（不碰真机微信原生、非新页首版视觉）→ **无 AC N(b)、无人验行**（CLAUDE.md §8.2）。

## Tech

| 文件 | 动作 |
|---|---|
| `miniapp/src/pages/recycle/form.vue` + `form.logic.ts` + `form.logic.test.ts` | ③ 区网格 + 连续高亮 + 竞态 + 纯函数 |
| `miniapp/src/api/gz-recycle.ts` + `.test.ts` | 契约切换（全链路起点） |
| `miniapp/src/locale/recycle.zh-CN.ts` | 文案 |
| `miniapp/src/components/biz/BizSlotGrid.vue` | **删** |
| `plus-ui/src/utils/hour-slot.ts` | **新增**（整点校验三件套，与拼豆共享） |
| `plus-ui/src/views/gz-recycle/time-slot/index.vue` | 营业时间语义 |
| `plus-ui/src/views/gz-recycle/qty-range/index.vue` | 小时数 + 删 occupyNext |
| `plus-ui/src/views/gz-recycle/appointment/components/WeekBoard.vue` | matrix + rowspan（**改动面最大，放最后**） |
| `plus-ui/src/views/gz-recycle/appointment/components/ManualHoldDialog.vue` | mergeRuns |
| `plus-ui/src/views/gz-recycle/appointment/components/RescheduleDialog.vue` | 换 picker |
| `plus-ui/src/views/gz-recycle/appointment/components/HourSlotPicker.vue` | **新增** |
| `plus-ui/src/api/gz-recycle/appointment.ts` | 类型 + `getHourSlots` |
| `plus-ui/src/lang/{zh_CN,en_US}.ts` | 三段 key |

**实施顺序**：admin time-slot/qty-range（无契约依赖，做完甲方就能配营业窗口）→ mp api + logic + 单测（不依赖后端就位）→ mp form.vue 联调 → HourSlotPicker → RescheduleDialog → WeekBoard matrix + ManualHoldDialog

## 备注

- `appointment/index.vue` 传给 WeekBoard 的 props 不变，下方筛选列表不变，详情抽屉已是 `arrivalSlot` 优先 + `slotStart-slotEnd` 回退 → **零改动**。
- admin 不评判视觉（颜色 / 间距 / 位置），只评判功能。

---

## §revision（Kevin 节点触发残留人验不过时填，初始空）
