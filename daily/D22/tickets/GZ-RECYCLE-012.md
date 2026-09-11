# GZ-RECYCLE-012 — 回收预约改 1 小时格（后端占用模型重写）

**优先级**: P0
**复杂度**: XL
**关联 PRD**: doc/02-prd.md §M10 回收预约
**关联拆解**: doc/02-需求拆解.md §3.6.5
**关联 mockup**: N/A（纯后端）
**关联 ADR**: doc/_adr/0022-recycle-hour-slot-occupancy.md（本 ticket 产出）· ADR-0011（拼豆区间预约，**实现蓝本**）· ADR-0021（手动占用/改期/周看板，被修订）· ADR-0012（不受影响）
**依赖**: 无

---

## 必读权威文档

- **业务流**：doc/10-业务流权威图.md §13 回收预约全流程 + 回收看板周视图
- **字段表**：doc/11-字段权威表.md §12（回收域，⚠️ **§12.2 已严重过期** —— 仍是 3 个「数量桶」`1-25/25-50/50-75`，5 个 `pts-*` 点数档在权威文档中根本不存在；本 ticket 一并修正）+ §3 拼豆（对照实现蓝本）
- **实现蓝本代码**：`GzBeanBookingServiceImpl.sliceWindowsToHourSlots` / `validateAndExpandInterval` / `isWholeHour` / `submitPaid` 逐格加锁段 · `GzBeanBookingMapper.countActiveCoveringSlotForUpdate`
- **UI 参考**：N/A

## What

回收占用单位从「admin 配的命名时段档（每档 1 单）+ `occupy_next_slot` 溢出 1 档」改为「**1 小时格 × N**，N = `CEIL(qty_range.duration_minutes / 60)`」。用户选起始整点，系统自动连占 N 格；放不下（越出营业窗口 / 跨午休 gap / 中间任一格被占）→ 该起始格不可选。防超卖逐字镜像拼豆（逐格升序 `FOR UPDATE` + 区间重叠）。

## 模型一句话

> 占用真源 = `gz_recycle_appointment.[slot_start, slot_end)` 区间（左闭右开、整点）；`gz_recycle_time_slot` 从「到店时段档」改为「**整点营业窗口**」，系统按 1h 切格。

## AC（验收标准）

### A. 迁移（4 个新文件，时间戳 `date +V%Y%m%d%H%M` 实施当下现取，须 > `V202608150951`）

- [ ] AC1：`V<ts1>__GZ-RECYCLE-012-appointment-hour-interval.sql`
  - `ADD INDEX idx_tenant_store_date_interval (tenant_id, store_id, appt_date, slot_start, slot_end)`
  - MODIFY 四列 COMMENT：`slot_start`/`slot_end` 标占用真源，`time_slot_id`/`spill_time_slot_id` 标【已退休 GZ-RECYCLE-012】
  - 存量活跃大单把 spill 档折叠进 `slot_end`（**必须在 AC2 软删 time_slot 之前跑**，要 JOIN 它）
  - 清空 `spill_time_slot_id`（含终态单，单一真源防后人误读）
  - ⚠️ **存量 `slot_end` 不重算**（老单按原档整块占用）。方向只能是过占，**绝不能缩短** —— 缩短 = 那格立即对外放开 = 与顾客实际到店时长物理双占。
- [ ] AC2：`V<ts2>__GZ-RECYCLE-012-time-slot-to-business-window.sql`
  - MODIFY COMMENT：`label`→营业窗口名 / `start_time`,`end_time`→必须整点 / 表注释改「回收营业窗口」
  - 软删旧 3 档（**避开将要写入的 10:00-22:00**）+ 复活可能存在的同窗口软删行（`uk_tenant_store_time` **不含 `del_flag`**，软删行仍占唯一键）
  - 每店 `INSERT` 一条 `'营业时间' 10:00:00-22:00:00`（`NOT EXISTS` 幂等）→ 每店切出 **12 个小时格**
- [ ] AC3：`V<ts3>__GZ-RECYCLE-012-qty-range-hours.sql` — `duration_minutes` COMMENT 升格为占用驱动 + `occupy_next_slot` 标退休置 0 + 时长归一到 60 的整数倍（现有 5 行是 no-op，给后台乱填 90 分钟上保险）
- [ ] AC4：`V<ts4>__GZ-RECYCLE-012-menu-rename.sql` — `sys_menu` 13006 及其 F 节点「回收时段」→「回收营业时间」（**权限 key 不动**）
- [ ] AC5：迁移后真库断言：每店恰 1 条 10-22 窗口且 `enabled=1` · `duration_minutes % 60 = 0` 全表成立 · `spill_time_slot_id` 全表 NULL · `EXPLAIN` 命中 `idx_tenant_store_date_interval`

### B. Mapper

- [ ] AC6：**删** `countActiveHoldingSlotForUpdate` / `countActiveHoldingSlotExcludingForUpdate`（改造后无引用，留着 = 两套口径并存）
- [ ] AC7：新增 `countActiveCoveringHourForUpdate` + `countActiveCoveringHourExcludingForUpdate`，重叠条件 `slot_start < ADDTIME(#{slot},'01:00:00') AND slot_end > #{slot}`，状态集同 `ACTIVE_HOLD_STATUSES`，`FOR UPDATE`。
  「覆盖格 gi」= 区间与 `[gi, gi+1h)` **重叠**，不是 `slot_start` 相等。回收无「提前放座」概念，止界直接 `slot_end`（不需要拼豆的 `COALESCE(actual_end_slot, …)`）。
- [ ] AC8：`reschedule` 的 `@Update` 去掉 `spillTimeSlotId` 参数，改写 `slot_end`，并把两个退休列**显式置 NULL**（存量老单一旦被改期就彻底切到新模型）。

### C. Service 核心

- [ ] AC9：新增 `SLOT_CAPACITY = 1` 常量 + 私有方法 `sliceWindowsToHourCells` / `isWholeHour` / `spanHoursOf` / `coveredHourCells` / `record SlotSpan` / `resolveSpanAndAssertCapacity` / `resolveSpanHoursForExisting`。
- [ ] AC10：`resolveSpanAndAssertCapacity`（取代 `resolveSlotAndAssertCapacity`，submit/manualHold/reschedule 三处共用）：
  ① 切格空 → 4124 ② `slotStart` 非整点 / ∉ cells → 4124 ③ **逐格 `cells.contains()`**（**不能**只判 `slotStart+N ≤ windowEnd` —— 后者会让 12:00 起 3h 的单跨过午休 gap），任一后续格缺 → 4123 ④ **升序**逐格 `FOR UPDATE`（交叠区间锁顺序一致、无死锁），`active >= SLOT_CAPACITY` → 首格 4122 / 后续格 4123 ⑤ 返 `SlotSpan`
- [ ] AC11：`submit`：`spanHours = spanHoursOf(bucket.getDurationMinutes())`；起点走 `resolveSubmitStart`（新契约 `slotStart` 优先，**老包只发 `timeSlotId` → 映射为该窗口 `start_time`** 的过渡 shim）；快照冻结 `snapshot.setSpanHours(spanHours)`；INSERT 写 `slotStart/slotEnd` + 两个退休列 NULL。
- [ ] AC12：新增 **4131 `SLOT_PAST`** 过期守卫（`apptDate == today && slotStart <= now`）。改 12 格后「选今天已过的时间」是高频误操作，不拦就产出必然 no_show 的脏单还白占格。**手动占用 / 改期豁免**（店员回填台账是正常动线，与 4130 现有口径一致）。
- [ ] AC13：Redis 锁 `gz:recycle:lock:slot:{store}:{date}` **保留**，加锁位置在逐格 `FOR UPDATE` 循环之前。注释必须写明：正确性根基是 `FOR UPDATE` + `REPEATABLE_READ`，Redis 只是快速失败优化。
- [ ] AC14：`getSlotAvailability(storeId, date, qtyBucketCode)` —— **必须收 `qtyBucketCode`**（判定「从这格起放得下 N 小时吗」要综合营业窗口连续性/午休不可桥接/今日已过/逐格占用/跨窗口不可连占五条后端知识，前端复刻必然漂移）。`qtyBucketCode` **可选**：缺省 N=1（保匿名 browse-first）；未知 code **降级 N=1 不抛 4107**。实现无锁：一次 `selectList` + 内存展开。
- [ ] AC15：新 VO `RecycleHourSlotVO{startTime, endTime, label, taken, past, selectable}` + 容器 `{date, spanHours, slots[]}`；旧 `RecycleSlotAvailabilityVO` 形状删除；`/time-slots` 端点保留标 `@deprecated`；`GzRecycleQtyRangeVO` 加派生 `spanHours`。

### D. 错误码

- [ ] AC16：4122 msg 改「该时间已被预约，请换个时间」· 4123 常量改名 `SLOT_SPAN_BLOCKED`（**码号 4123 不变**，mp 已有分支按码走）msg 动态化「该点数需连续占用 %d 小时，所选时间放不下，请换个时间或减少点数」· 4124 msg 改「到店时间无效或不在营业时间内」· **新增 4131 `SLOT_PAST`**「该时间已过，请选择之后的时间」

### E. 三处连带 + 时段服务

- [ ] AC17：`manualHold` BO `List<Long> timeSlotIds` → `List<LocalTime> slotStarts`，**入参先 `distinct().sorted()`**（前端多选顺序不可信，乱序会与 submit 死锁），每格 span=1 建一行。
- [ ] AC18：`reschedule` BO `timeSlotId` → `slotStart`。`resolveOccupyNextForReschedule` 重写为 `resolveSpanHoursForExisting`，回退链（延续 D21「**绝不活查点数档表**」铁律）：`source=manual` → 当前宽度；`source=mp` → ① 快照 `spanHours` ② `matched_duration_minutes`（提交时冻结列，老单最可信）③ 当前宽度；最终 `max(…,1)`。单测必须 `verify(qtyRangeService, never()).getEnabledByCode(any())`。
- [ ] AC19：`selectWeekBoard`：`slots` 列头改小时格，**并上本周活跃行覆盖到但不在窗口内的孤儿小时**（存量整档单 / admin 改窗口后）打 `outOfWindow=true` —— 不做并集会出现「实际挡着下单但看板上没这列」，最难排查的一类投诉。`cells` 改区间块 `{apptDate, slotStart, slotEnd, spanHours, kind:'customer'|'manual', spanStart, …}`，`kind='spill'` 随 `spill_time_slot_id` 一起退休。
- [ ] AC20：新增 admin 端点 `GET /system/gz/recycle/appointment/hour-slots?storeId&date&spanHours&excludeAppointmentId`（供改期弹窗）。**`excludeAppointmentId` 必须生效**，否则被改期的单跟自己冲突、相邻起点永远选不了。
- [ ] AC21：`GzRecycleTimeSlotServiceImpl.validateTimeRange` 加整点 + 至少 1 小时校验（否则配 `10:00-13:30` 会静默丢掉残格）；`insertByBo` 加「命中软删同窗口行则复活」分支（`uk_tenant_store_time` 不含 `del_flag`，本次 reseed 大量软删旧行、甲方紧接着就会去调窗口 → **踩中概率高**，不处理会吃 DB 1062 变 500）。

### F. 测试

- [ ] AC22：mock 单测 —— 切格（单窗口 10-22→12 格 / 双窗口跳午休 / 非整点丢残格）· `spanHoursOf`（60→1 / 300→5 / 90→2 / 0→1 / null→1）· `coveredHourCells`（历史非整点 floor/ceil）· submit happy 用 `InOrder` 断言逐格**升序**加锁 · 4122/4123/4124/4131 各一例 · 老包 shim · `getSlotAvailability` 有/无 `qtyBucketCode` · `manualHold` 乱序入参被排序 + 第 2 格 4122 时不继续 INSERT · `reschedule` 四条回退链 · 周看板 spanStart/孤儿列
- [ ] AC23：**新增 `GzRecycleActiveStatusConsistencyTest`** —— 反射读两个新 `@Select` 的注解文本，断言 `ACTIVE_HOLD_STATUSES` 每个值都在 SQL 的 `status IN (…)` 里且**个数相等**；同样守 `USER_ACTIVE_STATUSES`。该常量现在是 **3 份物理拷贝**，这是唯一能机械挡住「加了新状态忘改 SQL」的手段。
- [ ] AC24：**真 DB 并发脚本** `script/bin/recycle-hour-slot-concurrency.sh`（mock 照不出并发，raw output 贴进 report）：
  A 两线程同 (store,date,10:00) N=1 → 恰 1 成功 · **B 交叠 span**（A 提 10:00 N=4，B 提 12:00 N=2）→ 恰 1（证明「重叠」而非「起点相等」判定）· C manual-hold 12:00 与 submit 10:00 N=3 并发 → 恰 1 · D 两单同时改期到同一空格 → 恰 1 · **E 手动 DEL Redis 锁后重跑 A → 仍恰 1**（证明根基是 FOR UPDATE+RR）· G 端到端 manual-hold 12:00 → `slot-availability?qtyBucketCode=pts-100-150` 里 10:00 起也不可选 · H 手插 `10:00-13:00` 老单 → 10/11/12 三格 taken、13:00 起可约
- [ ] AC25：`mvn clean install` + 起真 app 确认 `Started …Application`（改迁移当天必须真起一次）
- [ ] 纯后端 ticket，无 mp AC N。

## Tech

| 文件 | 动作 |
|---|---|
| `ruoyi-admin/.../db/migration/V<ts1..4>__GZ-RECYCLE-012-*.sql` | 新增 4 个 |
| `ruoyi-gz-recycle/.../mapper/GzRecycleAppointmentMapper.java` | 删 2 加 2 改 1 |
| `ruoyi-gz-recycle/.../service/impl/GzRecycleAppointmentServiceImpl.java` | 核心重写（1148 行） |
| `ruoyi-gz-recycle/.../service/impl/GzRecycleTimeSlotServiceImpl.java` | 整点校验 + 软删复活 |
| `ruoyi-gz-recycle/.../exception/GzRecycleErrorCode.java` | 4123 改名 + msg + 新增 4131 |
| `ruoyi-gz-recycle/.../domain/{vo,bo}/` | `RecycleHourSlotVO`（新）· `RecycleSlotAvailabilityVO`（改）· `GzRecycleWeekBoardVO`（改）· 三个 BO 改 |
| `ruoyi-gz-recycle/.../controller/{applet,}/…` | `slot-availability` 加 `qtyBucketCode`；新增 admin `hour-slots` |
| `script/bin/recycle-hour-slot-concurrency.sh` | 新增 |

## 备注

- **不做门店级可配容量**，硬编码 `SLOT_CAPACITY=1`。理由见 ADR-0022「拒绝的替代方案」节：甲方从没要过 >1（3 档→12 格已翻 4 倍）；放 `gz_bean_store` 是错的（回收与拼豆**共用**的门店主数据表）；容量 >1 会连锁破坏周看板「一格一单」cell 模型 / 手动占用语义 / 改期归属判定。后路留在 `if (active >= SLOT_CAPACITY)` 一个表达式里。
- **一人一单守卫（4127）不动** —— 甲方想「一天上更多人」但这是两件事，`USER_ACTIVE_STATUSES` 刻意不含 `paid`/`manual_hold`，改它会连锁影响 `/active` 预检。
- 老包 `timeSlotId` shim 保留至少两周再删（发布顺序：后端+admin 先上 → 小程序紧随）。
- `matched_duration_minutes` 升格为占用宽度的**冻结备份**（参与改期回退链），不再是纯展示列 —— 在 entity 字段注释里写死这条。

---

## §revision（Kevin 节点触发残留人验不过时填，初始空）
