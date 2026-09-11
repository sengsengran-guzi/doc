# GZ-RECYCLE-014 — 回收看板「取消顾客单」（爽约手动释放）

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md §M10 回收预约
**关联拆解**: doc/02-需求拆解.md §3.6.5
**关联 mockup**: N/A（admin 走 ruoyi 默认）
**关联 ADR**: doc/_adr/0022-recycle-hour-slot-occupancy.md · ADR-0021 §1（`releaseHold`，被扩展）· ADR-0006（反向打款）
**依赖**: **GZ-RECYCLE-013**（复用 WeekBoard popover）

---

## 必读权威文档

- **业务流**：doc/10-业务流权威图.md §13 回收预约全流程（状态机 + 反向打款分支）
- **字段表**：doc/11-字段权威表.md §12.3 `gz_recycle_appointment` + §12.7 活跃占用集口径
- **UI 参考**：N/A

## What

给回收周看板的**顾客单**格加「取消」动作，让店员能手动释放爽约单占住的小时格。现状 `releaseHold` 只认 `source='manual'`，店员对顾客单**没有任何释放入口**。

## 为什么必须同期做

改小时格后一张 5h 大单爽约 = 当天 5 个格全废；而 prod **SnailJob 根本没部署**（`docker-compose.deploy.yml` 只有 mysql + redis + ruoyi-admin，`SNAIL_JOB_ENABLED` 默认 false → 25 个 `@JobExecutor` 一个都没跑，no_show cron **从来没生效过**）。不做的话甲方上线第一周就会遇到「客人没来但格子锁死一整个下午」，与「一天上更多人」的诉求直接冲突。**本方案不依赖 SnailJob。**

## AC（验收标准）

- [ ] AC1：后端放开 `releaseHold`（或新增 `cancelCustomerAppointment`）接受 `source='mp'` 的单。
- [ ] AC2：**状态白名单严格限 `submitted` / `confirmed_onsite`**。
  ⚠️ 回收是**反向打款**（店家付钱给顾客），`paying` / `paid` / `payout_failed` 有资金动作在途或已完成 → **必须显式拒绝**（复用 4129 `HOLD_RELEASE_NOT_ALLOWED` 或新错误码，msg 要说明「该单已进入打款流程，不能取消」）。
- [ ] AC3：终态**沿用既有取消 / no_show 语义，不新造状态**（对齐 `gz_recycle_status` 字典，避免下游守卫漏认）。
- [ ] AC4：取消后该单退出活跃占用集 → 它覆盖的**全部**小时格立即对外可约（`slot-availability` 与周看板同步变 idle，curl + UI 双断言）。
- [ ] AC5：操作留痕 —— 记录操作人 + 时间（复用 `last_reschedule_by` / `last_reschedule_time` 同款字段或 remark 追加），列表 / 详情可见。
- [ ] AC6：走既有 `gz:recycle:appointment:*` 权限，**不新增 menu、不新增迁移**（若复用 `hold` 权限则在 ticket 报告里写明口径）。
- [ ] AC7：version 乐观锁 affected=0（并发已被别人改状态）→ 返明确错误不静默成功。
- [ ] AC8：前端 `WeekBoard.vue` 顾客单块的 popover 里加「取消」`el-button link danger` + `ElMessageBox.confirm` 二次确认，文案点明「**取消后该时段立即释放，可被他人预约**」。
- [ ] AC9：仅对 `submitted` / `confirmed_onsite` 的顾客单块显示「取消」按钮（前端先挡一道，后端兜底）。
- [ ] AC10：单测覆盖 —— happy（`submitted` 取消成功 + 格释放）· `paid` 被拒 · `paying` 被拒 · `payout_failed` 被拒 · 并发 version 冲突 · 手动占用单走原 `releaseHold` 路径不受影响。
- [ ] AC11：i18n `zh_CN.ts` + `en_US.ts` 同步；模板无硬编码中文；`pnpm type-check` + eslint 通过。
- [ ] AC12：Tier 1B Playwright：周看板选一张 `submitted` 顾客单 → popover 点「取消」→ 确认 → 断言该单覆盖的 N 格全变 `data-cell-kind="idle"` → console 0 error。
- [ ] 纯 admin + 后端 ticket，无 mp AC N。

## Tech

| 文件 | 动作 |
|---|---|
| `ruoyi-gz-recycle/.../service/impl/GzRecycleAppointmentServiceImpl.java` | 放开 / 新增取消方法 + 状态白名单 |
| `ruoyi-gz-recycle/.../mapper/GzRecycleAppointmentMapper.java` | 取消的 `@Update`（version 乐观锁） |
| `ruoyi-gz-recycle/.../controller/GzRecycleAppointmentController.java` | 端点（或复用 `release-hold`） |
| `ruoyi-gz-recycle/.../exception/GzRecycleErrorCode.java` | msg 明确化（如需新码） |
| `plus-ui/src/views/gz-recycle/appointment/components/WeekBoard.vue` | popover 加「取消」 |
| `plus-ui/src/api/gz-recycle/appointment.ts` | 方法 + 类型 |
| `plus-ui/src/lang/{zh_CN,en_US}.ts` | `gzRecycleAppointment` 段 |

## 备注

- 本 ticket **不上 SnailJob 基建**（那是另一个工程，Kevin 2026-06-30 已拍板走路 B）。自动释放留到未来真上 SnailJob 时再说；本 ticket 提供的是「配不配 cron 都能用」的手动兜底。
- 不放开一人一单守卫（4127）—— 取消后顾客自然能再约，不需要额外改动。

---

## §revision（Kevin 节点触发残留人验不过时填，初始空）
