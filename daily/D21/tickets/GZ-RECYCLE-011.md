# GZ-RECYCLE-011 — 回收看板周视图矩阵 + 手动占用 / 改期弹窗（admin）

**优先级**: P0
**复杂度**: L
**关联 PRD**: doc/02-prd.md §M10 回收预约
**关联拆解**: doc/02-需求拆解.md §3.6.5 GZ-PAY 反向打款 + GZ-RECYCLE 回收
**关联 mockup**: N/A（设计冻结期 admin 走 ruoyi/Element Plus 默认审美，**不引 mockup、不调样式**）
**关联 ADR**: doc/_adr/0021-recycle-manual-slot-hold-and-reschedule.md §3
**依赖**: **GZ-RECYCLE-010**（四个端点 + `AdminVO.timeSlotId/source` 必须先 merge）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §13「回收看板（admin 周视图）」（格四态表 + 可做的动作）+「手动占用时段 H1-H4」+「预约改期 R1-R5」
- **字段表**：doc/11-字段权威表.md §12.7（活跃占用集口径 / 权限 13015-13016 / 错误码）+ §12.3 `gz_recycle_appointment`
- **ADR**：doc/_adr/0021 §3
- **相关代码**：`plus-ui/src/views/gz-recycle/appointment/index.vue`（现「今日到店预约」看板段 = template 第 3-32 行 + `boardGroups` / `loadBoard`）
- **UI 参考**：N/A（admin 不评判视觉，只评判功能）

## What

把 `gz-recycle/appointment/index.vue` 顶部的「今日到店预约」看板换成**周矩阵**（列 = 周一至周日，行 = 该店 enabled 到店时段），格四态渲染；空格可多选后一次性「手动占用」（备注必填），手动占用格可「改期 / 释放」，`submitted` 顾客单格可「改期」。页面下方「回收记录」列表 / 详情 drawer / 核销弹窗**原样保留不动**。

## AC（验收标准）

### A. 周矩阵

- [ ] AC1：页头筛选 = 门店下拉（沿用现有 `storeOptions`，默认第一个门店）+ 周切换（`上一周` / `本周` / `下一周` + 显示当前周区间 `MM-DD ~ MM-DD`），默认本周。切门店 / 切周各触发一次 `week-board` 请求（**不重复请求、不整页 reload**）。
- [ ] AC2：矩阵行 = 后端返回的 `slots` 顺序（该店 `enabled` 档，与「回收配置 → 回收时段」配置顺序一致），行头显示 `label`（`HH:mm-HH:mm`）；列头显示日期 + 星期（今天列有可辨识标记）。该店无 enabled 时段时显示空态文案，不报错。
- [ ] AC3：格四态可程序化断言（每格根节点带 `data-cell-kind="idle|customer|manual|spill"`）：
  - **空闲** → 空白可选格
  - **顾客单** → 手机尾号（`mobileSnapshot` 后 4 位）+ 点数档 `qtyBucketLabel` + `<dict-tag :options="gz_recycle_status">`
  - **手动占用** → 「占用 · {remark}」（备注过长省略 + title 悬浮全文）
  - **溢出占用** → 标注所属单号 `appointmentNo`，**无任何操作按钮**（提示"请操作源单"）
- [ ] AC4：点格进详情 —— 顾客单格点击复用现有 `openDetail(row)` drawer（不新写详情）。

### B. 手动占用

- [ ] AC5：空闲格可**多选**（点击切换选中态，选中有可辨识 class），支持**跨日期跨时段**多选（同一门店内）；顶部实时显示「已选 N 格」+「手动占用」按钮（N=0 时 disabled）+「清空选择」。
- [ ] AC6：点「手动占用」弹窗，列出已选格清单（日期 + 时段）+ **备注必填**（`el-form` rule `required`，空 / 纯空格提交被前端拦住且不发请求）。确认 → 调 `manual-hold`（一次请求带全部 `timeSlotIds`；跨日期时按日期分组多次请求，任一失败即停并提示）→ 成功 toast + 刷新矩阵 + 清空选择 + 关弹窗。
- [ ] AC7：手动占用格上「释放」按钮 → `ElMessageBox.confirm` 二次确认 → 调 `release-hold` → 刷新后该格变 `data-cell-kind="idle"`。

### C. 改期

- [ ] AC8：`submitted` 顾客单格 + 手动占用格显示「改期」按钮；**`confirmed_onsite` / `paying` / `paid` / `cancelled` / `no_show` 的格不显示改期按钮**（前端先挡一道，后端 4128 兜底）。
- [ ] AC9：改期弹窗 = 只读展示当前（门店 / 日期 / 时段 / 单号）+ 选新日期（`el-date-picker`）+ 选新时段（`el-select`，只列该店 enabled 档）。**门店不可改**（弹窗内无门店控件）。确认 → 调 `reschedule` → 成功 toast + 刷新矩阵 + 关弹窗。
- [ ] AC10：目标格已被占时后端返 4122/4123，前端**直接 toast 后端 msg**、**弹窗保持打开**允许改选（不吞错、不关窗、不刷成功态）。4124 / 4128 / 4129 同样直出后端 msg。

### D. 权限 / i18n / 回归

- [ ] AC11：手动占用按钮 + 释放按钮 `v-hasPermi="['gz:recycle:appointment:hold']"`；改期按钮 `v-hasPermi="['gz:recycle:appointment:reschedule']"`。用未授这两个权限的角色登录，矩阵可见但三个按钮不渲染（空格仍可选但「手动占用」按钮不出现）。
- [ ] AC12：新增可见文案全部走 `t('gzRecycleAppointment.xxx')`，`src/lang/zh_CN.ts` + `en_US.ts` 同步补齐；`grep -nP '[\x{4e00}-\x{9fa5}]' ` 新增/修改的 vue 文件 → 模板内无硬编码中文（CLAUDE.md §6 #9）。
- [ ] AC13：`pnpm type-check` + eslint 通过，无 `any`（后端 VO 对应 TS interface 写在 `api/gz-recycle/appointment.ts`，id 字段 `string`，遵循 ID 跨层契约 #1）。
- [ ] AC14：**下方回收记录不回归** —— 筛选（门店 / 日期区间 / 状态 / 点数档 / 金额 / 单号）+ 分页 + 详情 drawer + 核销弹窗 + 失败重试按钮功能与改造前一致；状态下拉多出「手动占用」选项（字典自动带出），选中后列表显示手动记录行（配合 010 AC22）。
- [ ] AC15：Tier 1B Playwright E2E 全流程一遍：登录 → 回收看板 → 切下一周再切回 → 选 2 个空格 → 手动占用（填备注）→ 断言 2 格变 `data-cell-kind="manual"` → 对其中一格改期到另一空格 → 断言原格 idle / 新格 manual → 释放 → 断言变 idle → 浏览器 console **0 error**。
- [ ] 纯 admin ticket，无 mp AC N（CLAUDE.md §8.2）。

## Tech（端 + 范围）

**判定：改造现有页面，不新建页面**（menu 13002 已指向 `gz-recycle/appointment/index`，新建页面要动菜单路由、且下方回收记录与看板本就是同一使用场景）。但**矩阵与两个弹窗抽成子组件**，避免 index.vue 从 686 行膨胀到 1000+（沿用项目既有 `views/<域>/<page>/components/` 约定，参考 `gz-ord/orders/components/`、`gz-news/article/components/`）。

| 文件 | 动作 |
|---|---|
| `plus-ui/src/views/gz-recycle/appointment/index.vue` | 删除 `boardGroups` / `loadBoard` / `board-*` 样式与今日看板 template 段（第 3-32 行），换挂 `<WeekBoard>`；保留记录列表 / drawer / 核销弹窗；持有门店与周状态 |
| `plus-ui/src/views/gz-recycle/appointment/components/WeekBoard.vue` | **新增**：门店 + 周切换 + 矩阵渲染 + 格多选 + 格上按钮 + emit（`detail` / `hold` / `reschedule` / `release`） |
| `plus-ui/src/views/gz-recycle/appointment/components/ManualHoldDialog.vue` | **新增**：已选格清单 + 备注必填 + 提交 |
| `plus-ui/src/views/gz-recycle/appointment/components/RescheduleDialog.vue` | **新增**：当前只读 + 新日期 + 新时段 + 提交 |
| `plus-ui/src/api/gz-recycle/appointment.ts` | 新增 `getWeekBoard` / `manualHoldSlots` / `releaseHold` / `rescheduleAppointment` + `RecycleWeekBoardVO` / `RecycleBoardCellVO` 类型；`GzRecycleAppointmentVO` 补 `source` / `timeSlotId` / `spillTimeSlotId` / `rescheduleCount` |
| `plus-ui/src/lang/zh_CN.ts` / `en_US.ts` | `gzRecycleAppointment` 段补 key（周切换 / 四态 / 弹窗 / 按钮 / 空态） |

- 时段下拉数据源：复用 `week-board` 返回的 `slots`（不再单独调 timeSlot 接口）。
- 字典：`gz_recycle_status` 已在页面 `useDict` 中，`manual_hold` 由 010 seed 后自动带出（**若看不到新字典项，`docker exec sensenran-dev-redis redis-cli -a ruoyi123 --no-auth-warning FLUSHDB` 清 ruoyi 字典缓存**，memory `dev-infra-run-recipe`）。

## 备注

- **admin 不评判视觉**（颜色 / 间距 / 位置），只评判功能；矩阵用 `el-table` 或原生 grid 均可，以能稳定挂 `data-cell-kind` 供 E2E 断言为准。
- 无新 DDL、无新 menu（13015/13016 由 010 建）。
- 后端错误码 msg 已是可直接展示的中文，前端**不要二次包装文案**。
- 不做 mp 店员端看板镜像（ADR-0021 边界）。

---

## §revision（Kevin 节点触发残留人验不过时填，初始空）
