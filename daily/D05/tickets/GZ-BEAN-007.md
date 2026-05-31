# GZ-BEAN-007 — mp 取消预约（二次确认 + cancelled）

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M4 §取消预约 + §业务规则
**关联拆解**: doc/02-需求拆解.md §2.3 第 370 行
**关联 mockup**: design/mockup/booking-list.html（仅布局参考；视觉以 C 设计系统为准，doc/13。列表项操作按钮 + 二次确认弹窗）
**关联 ADR**: —
**依赖**: GZ-BEAN-006

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md **§3 拼豆预约全流程** §关键节点 N9 / N12（用户取消） + §状态机 pending → cancelled + §异常分支 E7（核销码被扫后已 cancelled 的拒绝逻辑）
- **字段表**：doc/11-字段权威表.md **§3.4 `gz_bean_booking`**（status / cancel_time / cancel_reason 字段） + §3.5 `gz_bean_booking_log`（取消动作写一条 log）
- **UI 参考**：doc/12 §MP-BEAN-LIST 操作区 + BEAN-005 详情页底部 CTA（视觉以 C 设计系统为准，doc/13）

## What

用户在 BEAN-005 详情页 / BEAN-006 列表卡片点「取消预约」 → 二次确认弹窗 → 确认后调取消接口 → 后端将 status 从 pending 改为 cancelled + 写 booking_log + 核销码作废（核销时会校验 status）。used / no_show 状态不可取消。

## AC（验收标准）

- [x] **AC 1**：mp 端「取消预约」按钮点击 → 二次确认弹窗（`uni.showModal`，文案：「确定取消预约？取消后该时段座位将释放给他人」，cancel + confirm 两按钮）
- [x] **AC 2**：确认后调 `POST /app/gz/bean/booking/{id}/cancel`（V1.0 不收 cancelReason，接口预留）
- [x] **AC 3**：后端 service（D04 已实现，本 ticket 不改）：事务 + 状态守卫（status=pending，非 pending → ServiceException code=4008） + 本人校验 + UPDATE cancelled + cancelledTime + booking_log(operator_type=user) + dedup_token 释放座位
- [x] **AC 4**：成功后 mp 端 `uni.showToast`「取消成功」 + 自动刷新当前页（详情页 → 重拉 detail，状态变 cancelled + QR 灰显由 isInactive 驱动；列表页 → 重拉 listMyBookings 本地重分组，卡片移到「已取消」tab）
- [x] **AC 5**：失败 case：used / no_show 已是终态 → 后端返 4008，message「预约状态不允许此操作（当前状态：xxx）」由 http.ts 全局 toast 弹出；payload 透出 code 时本地兜底「该预约已核销 / 已过期，不可取消」
- [x] **AC 6**：i18n 全覆盖（`bean.cancel.*`）；后端 service 单测（happy + 非 pending 拒绝）D04 已覆盖；mp 端 cancel.logic 纯逻辑单测 11 个用例
- [x] **AC 7**：Tier 2 可达 — Kevin 从拼豆 tab → 首页「我的预约」→ my-list pending 卡片「取消」/ 点入 detail「取消预约」即触发（入口天然可达，无需临时入口）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-bean/`
  - `controller/applet/GzBeanBookingMpController.java` 加 `cancel(id, dto)` 方法
  - `service/IGzBeanBookingService.java` + impl 加 `cancel(bookingId, userId, reason)`（含 SELECT FOR UPDATE + 状态校验 + booking_log 写入，事务）
  - 不落新 DDL（cancel_time / cancel_reason 字段在 BEAN-004 DDL 已含；booking_log 表在 BEAN-004 DDL 已含）
- **小程序**：
  - `pages/bean/detail.vue`（BEAN-005 已建）补「取消预约」按钮 click handler
  - `pages/bean/my-list.vue`（BEAN-006 已建）pending tab 卡片的「取消」按钮 click handler
  - `api/gz-bean.ts` 加 `cancelBooking(id, reason?)`
- **测试**：mp 端取消一条 pending → 看状态变 cancelled + booking_log 多一条；取消一条已 used 的 → 应拒绝

## 备注

### 强约束

1. **事务 + SELECT FOR UPDATE** 防并发（用户点取消瞬间店员扫码核销 — 谁先锁谁赢，doc/10 §3 §并发控制）
2. **必须写 booking_log**（doc/11 §3.5 — 拼豆所有状态变更必须有 log，给客服 / 对账查证用）
3. **V1.0 不限制取消时间**（合同 §2.3 + doc/02 §2.3 第 376 行 AC 4：v2 候选）；任务卡里写 TODO「v2 候选：取消截止时间 + 黑名单」即可，不实现
4. **核销码作废 = status 改 cancelled 即可**（BEAN-008 核销时会校验 status = pending 才放行，doc/10 §3 §异常分支 E7）

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 用户在店员扫码瞬间点取消 → 状态竞态 | SELECT FOR UPDATE + 事务；谁先锁谁赢，后到的拒绝 |
| R2 | 取消接口被恶意刷（已 cancelled 的反复调） | 后端 status != pending → 直接 409；不计入业务损失 |

---

## §revision（Kevin testing-human 后填，初始空）
