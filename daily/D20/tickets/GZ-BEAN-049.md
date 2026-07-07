# GZ-BEAN-049 — 关闭重做（后端）：按桌型数量关闭 + 临时/每周循环 + 退休 seat_closure

**优先级**: P1
**复杂度**: M
**关联 ADR**: doc/_adr/0018-pindou-group-booking-preassign-closure-rework.md §3
**依赖**: —

---

## 必读权威文档

- **业务流**：doc/10-业务流权威图.md（拼豆下单余量 / 关闭子流程）
- **字段表**：doc/11-字段权威表.md §gz_bean_slot_quota_close §gz_bean_seat_closure
- **ADR**：doc/_adr/0018 §3
- **相关代码**：`GzBeanSlotQuotaClose*`（entity/mapper/service/controller）/ `GzBeanSeatClosure*` / 配额可用量查询 `selectTypeSlotAvailability`（消费两套关闭的地方）

## What

关闭统一到「按桌型 × 时段 × 关闭数量」模型：`gz_bean_slot_quota_close` 加 `weekday`（可空）+ `sess_date` 改可空，支持临时（填日期）/ 每周循环（填 weekday）；新增「某时段各小时预约数预览」+「按时间段批量关闭」接口；**配额可用量查询停止消费 `seat_closure`**（按座位那套退休）。

## AC（验收标准）

- [ ] AC1：DDL（Flyway，时间戳 = `date +V%Y%m%d%H%M` 当下真实时间）——`gz_bean_slot_quota_close` 加 `weekday TINYINT NULL`、`sess_date` 改 NULL 允许；append-only 新文件。
- [ ] AC2：预览接口 `GET /system/gz/bean/slot-quota-close/occupancy`（storeId, seatTypeConfigId, sessDate, slotStart, slotEnd）→ 返回区间内**各 1h 格**的 {booked(活跃单数) / cap(配置总量) / closed(已关数)}。
- [ ] AC3：批量关闭 `POST /system/gz/bean/slot-quota-close/batch`（storeId, seatTypeConfigId, 时段[start,end), closeCount N, 循环模式：sessDate **或** weekday）→ 对区间每个 1h 格 upsert closeCount=N（覆盖不累加，沿用现有 upsert 语义）。
- [ ] AC4：配额可用量 = cap − 活跃单 − closeCount；closeCount 汇总判定改为 `(sess_date = 当天) OR (weekday = 当天ISO星期)`；**移除对 `gz_bean_seat_closure` 的消费**（下单余量 / 排位 / 核销均不再查它）。
- [ ] AC5：与 047 排位/核销一致——关闭数量减少的是**配额可用量**（顾客可约数），不针对具体物理座；排位/核销物理座不受 closeCount 直接影响（座位坏了用 seat.enabled）。
- [ ] AC6：单测——预览各小时计数正确；批量关闭区间 upsert 正确；循环 weekday 命中判定正确。

## Tech

- **后端**：`GzBeanSlotQuotaClose` 加字段；mapper 加预览聚合查询 + 批量 upsert；配额查询移除 seat_closure 分支。
- Flyway 迁移新文件（memory `flyway-wired` append-only 铁律）；改 gz-bean 后 `mvn clean install`。
- 无新 menu（复用现有关闭权限）。

## 备注

- `seat_closure` 表按 append-only 保留不删，仅停止消费 + 050 下线其页/menu。
- DDL 时间戳务必用当下真实时间（memory `flyway-wired` / `deploy-pipeline-autocommit-and-flyway-order`）。

---

## §revision（初始空）
