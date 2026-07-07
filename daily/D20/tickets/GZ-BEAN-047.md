# GZ-BEAN-047 — 排位：待核销单提前分座（激活 reserved 看板态）

**优先级**: P0
**复杂度**: M
**关联 ADR**: doc/_adr/0018-pindou-group-booking-preassign-closure-rework.md §2
**依赖**: —

---

## 必读权威文档

- **业务流**：doc/10-业务流权威图.md（拼豆看板 / 核销子流程）
- **字段表**：doc/11-字段权威表.md §gz_bean_booking（seat_id / status / verify_time / actual_end_slot）
- **ADR**：doc/_adr/0018 §2（排位 = 提前写 seat_id，激活休眠 reserved）
- **相关代码**：`GzBeanBookingServiceImpl.verify()` / `selectPendingAssignList()` / `selectBoard()` / `GzBeanNoShowMarkJob` / 现场分座的物理占用互斥查询（`selectSeatOccupiedNowForUpdate/Ids`）

## What

新增「排位」= 给已付款待核销单（pending + paid + seat_id 为空）提前写 `seat_id`、状态仍 pending，激活看板 `reserved` 态；反向「取消排位」清 seat_id。物理占用互斥校验从「只数 used」扩到「也数 reserved（pending + 已排位）」；no_show cron 过期时一并清 seat_id。

## AC（验收标准）

- [ ] AC1：`POST /system/gz/bean/booking/pre-assign`（bookingId, seatId）——校验单 pending+paid+未核销、座属同店、桌型匹配（复用 SEAT_TYPE_MISMATCH）、座启用；写 seat_id、status 保持 pending、verify_time 保持 NULL。成功后该单从「未排位客人」列表消失（`selectPendingAssignList` 现有 `seat_id IS NULL` 过滤天然生效）。
- [ ] AC2：`POST /system/gz/bean/booking/unassign`（bookingId）——仅对 reserved（pending + seat_id 非空 + 未核销）单，清 seat_id 回列表。已核销（used）单拒绝（复用 4017 之类非法状态码）。
- [ ] AC3：占用互斥——排位到某座时，若该座已被**另一活跃单**（used **或** reserved）在**区间重叠**占用 → 拒绝（复用 SEAT_TAKEN=4002）。含 reserved 是本 ticket 重点：两条 pending 单不能排到同座且时段重叠。
- [ ] AC4：核销走已排座——对已 reserved（已排位）单核销时用其**自身 seat_id**、不要求再传座；`verify(bookingId, seatId)` 兼容传入已排座即通过（座一致校验）。
- [ ] AC5：no_show cron（`GzBeanNoShowMarkJob` / 本地 scheduler）标记过期单为 no_show 时，**一并清 seat_id**（否则排了没来的座永卡 reserved）。
- [ ] AC6：并发——两请求同时排位到同一空座重叠区间，只有一个成功（悲观锁 / 区间互斥，与现场分座同机制）。集成测试连续两单验证（mock 照不出）。

## Tech

- **后端**：`ruoyi-modules/ruoyi-gz-bean/`
  - `IGzBeanBookingService` + `impl`：新增 `preAssignSeat(bookingId, seatId, operator)` / `unassignSeat(bookingId, operator)`；扩展占用互斥查询把 reserved（pending + seat_id 非空 + 未核销 + 区间覆盖）纳入占用集。
  - `GzBeanBookingController`：两个新端点，`@SaCheckPermission("gz:bean:booking:verify")`。
  - `GzBeanNoShowMarkJob` / `GzLocalBeanScheduler`：no_show 更新语句加 `seat_id = NULL`。
  - 无新 DDL、无新 menu。
- **测试**：service 单测 happy + 2-3 error path；并发扣座集成（真 DB 连续两单重叠）。

## 备注

- 改 gz-bean 模块后必须 `mvn clean install`（memory `mvn-clean-install-required`）+ restart。
- 占用止界口径沿用 `COALESCE(actual_end_slot, slot_end)`，任何写路径不得外延（memory `board-release-actualendslot-clamp-slotend`）。

---

## §revision（初始空）
