# GZ-RECYCLE-010 — 回收手动占用时段 + 预约改期 + 周看板（后端）

**优先级**: P0
**复杂度**: L
**关联 PRD**: doc/02-prd.md §M10 回收预约
**关联拆解**: doc/02-需求拆解.md §3.6.5 GZ-PAY 反向打款 + GZ-RECYCLE 回收
**关联 mockup**: N/A（设计冻结期 admin 走 ruoyi 默认）
**关联 ADR**: doc/_adr/0021-recycle-manual-slot-hold-and-reschedule.md
**依赖**: —（下游 GZ-RECYCLE-011 依赖本卡）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §13「手动占用时段（H1-H4）」/「预约改期（R1-R5）」/「回收看板（admin 周视图）」/ 异常分支 E9-E11
- **字段表**：doc/11-字段权威表.md **§12.3 `gz_recycle_appointment`**（新增 7 列 + 三列放宽 NULL）+ **§12.7 手动占用时段 + 预约改期口径**（活跃占用集两处拷贝 / 改期三条硬约束 / 权限）+ §10.2 字典 `gz_recycle_status` + §10.3 menu 13000-13099 段
- **ADR**：doc/_adr/0021 §1 / §2 +「关键实现坑位」11 条（**逐条对照，漏一条就是线上事故**）
- **相关代码**：`GzRecycleAppointmentServiceImpl.submit()` ⑤ 容量校验段 / `getSlotAvailability()` / `listStaffByDate()` / `GzRecycleAppointmentMapper.countActiveHoldingSlotForUpdate` / `GzRecycleErrorCode`
- **UI 参考**：N/A（纯后端）

## What

`gz_recycle_appointment` 单表承载第二类记录「手动占用」（`source='manual'` + `status='manual_hold'`），新增 **手动占用（批量多格）/ 释放 / 改期（原地 UPDATE）/ 周看板** 四个 admin 端点，并把 submit 里的时段容量校验抽成公共方法供三处共用。

## AC（验收标准）

### A. 迁移 / 字典 / 权限

- [ ] AC1：新建迁移 `V<ts>__GZ-RECYCLE-010-appointment-manual-hold.sql`（`ts` = `date +%Y%m%d%H%M` 当下真实时间）。应用后 `DESC gz_recycle_appointment` 满足：新增 `source VARCHAR(16) NOT NULL DEFAULT 'mp'` / `reschedule_count INT NOT NULL DEFAULT 0` / `last_reschedule_by VARCHAR(64) NULL` / `last_reschedule_time DATETIME(3) NULL`；`user_id` / `receiver_openid` / `product_snapshot_json` 三列 `Null` 列变为 `YES`（**MODIFY 前先 `SHOW CREATE TABLE` 抄原类型与 COMMENT，不得改宽度/丢注释**）。
- [ ] AC2：存量数据不受影响 —— `SELECT COUNT(*) FROM gz_recycle_appointment WHERE source <> 'mp'` = 0；应用后完整重启一次，Flyway 无 checksum / out-of-order 报错（不得改动任何已应用迁移文件）。
- [ ] AC3：新建迁移 `V<ts>__GZ-RECYCLE-010-menu-dict.sql`：① `sys_dict_data` 增 `gz_recycle_status` 的 `manual_hold` = 「手动占用」（照抄 `V202606230101__GZ-RECYCLE-003-seed-recycle-status-dict.sql` 的 insert 形态与 tenant 口径）；② `sys_menu` 增 13015（`gz:recycle:appointment:hold`）/ 13016（`gz:recycle:appointment:reschedule`），`parent_id=13002`、`menu_type='F'`、`visible='0'`、幂等 DELETE→INSERT（照抄 `V202606230100__GZ-RECYCLE-003-menu-perm.sql`）。
- [ ] AC4：授权面 = `SELECT role_id FROM sys_role_menu WHERE menu_id=13021`（现有「到店核对」权限持有角色）∪ `{100 owner}`，对 13015/13016 各授一遍（`INSERT IGNORE`）。**新建角色行不涉及**；若发现要新建角色，`tenant_id` 必须 `'1001'`（memory `gz-roles-tenant-must-be-1001`）。**menu_id 只用 13015/13016，不得占用其它号**（memory `menu-id-collision`）。

### B. 状态集 / 公共校验

- [ ] AC5：`ACTIVE_HOLD_STATUSES` 加 `manual_hold` —— **两处物理拷贝同步**：`GzRecycleAppointmentServiceImpl` 的 Java 常量 + `GzRecycleAppointmentMapper.countActiveHoldingSlotForUpdate` 的 `@Select` 内联字面量。验收 = `grep -c "manual_hold" ` 在这两个文件里都 ≥ 1，且两处状态集元素完全一致（6 个）。
- [ ] AC6：`USER_ACTIVE_STATUSES`（一人一单 4127）与 `countActiveByUserForUpdate` 的内联集合**均不含** `manual_hold`（显式验证未被"顺手补齐"）。
- [ ] AC7：时段容量校验抽为私有公共方法（如 `resolveSlotAndAssertCapacity(tenantId, storeId, apptDate, timeSlotId, occupyNext, excludeId)`），返回 chosen/spill 档并在冲突时抛 4122/4123/4124；`submit()` / `manualHold()` / `reschedule()` **三处都调它**（grep 调用点 = 3，submit 中原内联校验代码删除而非保留）。`excludeId` 为 null 时走 `countActiveHoldingSlotForUpdate`，非 null 时走新变体（AC12）。

### C. 手动占用 / 释放

- [ ] AC8：`POST /system/gz/recycle/appointment/manual-hold`，perm `gz:recycle:appointment:hold`，`@Log(BusinessType.INSERT)`。Body `{ storeId, apptDate, timeSlotIds: [], remark }`。成功后每个 slotId 落一行：`source='manual'`、`status='manual_hold'`、`user_id` / `receiver_openid` / `product_snapshot_json` / `mobile_snapshot` 均为 NULL、`spill_time_slot_id` 为 NULL、`remark` = 入参、`create_by` = admin 会话用户、`appointment_no` 各行唯一且为 `RCY-` 前缀。
- [ ] AC9：**all-or-nothing** —— 传 3 个 slotId 其中第 2 个已被占，返回 4122，且 `SELECT COUNT(*) FROM gz_recycle_appointment WHERE appt_date=? AND store_id=?` 与调用前**完全一致**（0 行残留）。
- [ ] AC10：`remark` 为空 / 纯空白 → BO `@NotBlank` 参数校验失败（不落库、不占业务码）；`timeSlotIds` 空数组 / 含非本店或 `enabled=0` 的档 → 4124。
- [ ] AC11：`POST /system/gz/recycle/appointment/{id}/release-hold`，perm `gz:recycle:appointment:hold`，`@Log(UPDATE)`。守卫 `source='manual' AND status='manual_hold'`：满足 → `status='cancelled'` + `cancelled_time` 非空，该格 `slot-availability` 立即 `taken=false`；对 `source='mp'` 的顾客单调用 → **4129**；对已 `cancelled` 的手动行再调 → **4129**（不静默成功）。

### D. 改期

- [ ] AC12：新增 mapper 变体 `countActiveHoldingSlotExcludingForUpdate(tenantId, storeId, apptDate, slotId, excludeId)`（`AND id <> #{excludeId}`，其余与原版逐字一致含 `FOR UPDATE`）；改期路径**只**用这个变体。
- [ ] AC13：`POST /system/gz/recycle/appointment/{id}/reschedule`，perm `gz:recycle:appointment:reschedule`，`@Log(UPDATE)`。Body `{ apptDate, timeSlotId }`（**不含 storeId —— 不允许跨门店改期**）。成功后同一行：`id` / `appointment_no` / `user_id` / `product_snapshot_json` / `matched_duration_minutes` **不变**；`appt_date` / `time_slot_id` / `slot_start` / `slot_end` 更新；`reschedule_count` +1；`last_reschedule_by` = admin 用户名；`last_reschedule_time` 非空；`version` +1。
- [ ] AC14：**排除自身不被自己挡**（ADR 坑位 4）—— 造一张大单（点数档 `occupy_next_slot=1`），原占 T1 且 spill 占 T2；改期到 **T2** 必须**成功**（不得返回 4122/4123）。改期后 `time_slot_id` = T2、`spill_time_slot_id` = T3（T2 的下一 enabled 档）。
- [ ] AC15：**spill 按新档重算且允许置 NULL**（ADR 坑位 5）—— 同一张大单改期到该店**最后一个 enabled 档**后，`SELECT spill_time_slot_id` 结果为 `NULL`（不残留旧值）。
- [ ] AC16：状态守卫 —— `confirmed_onsite` / `paying` / `paid` / `cancelled` / `no_show` 的单调改期 → **4128**；`submitted` 顾客单与 `manual_hold` 手动记录可改。UPDATE 的 WHERE 带 `status IN ('submitted','manual_hold') AND version=#{version}`，affected=0 → 4128（不静默成功）。
- [ ] AC17：**核销码改期后仍有效** —— 顾客单改期前 `GET /app/gz/recycle/appointment/{id}/verify-code` 取码，改期后用**同一串 payload** 调 `POST /app/gz/recycle/staff/verify-scan` 仍能定位到该单（不报 4104/4112）。
- [ ] AC18：并发 —— 两线程同时把两张不同单改期到同一空格，**只有一条成功**，另一条 4122（**真 DB 双线程，mock 照不出**）。锁只抢目标 `gz:recycle:lock:slot:{storeId}:{新date}`，旧格不加锁。

### E. 隔离性（手动记录不得污染既有链路）

- [ ] AC19：**不触发一人一单** —— 连建 5 条手动占用全部成功（不报 4127）；此后真实顾客用户仍能正常提交 1 单，且其第 2 单仍被 4127 挡（守卫口径未被污染）。
- [ ] AC20：**挡 mp 下单** —— 手动占用 (S, D, T) 后：① `GET /app/gz/recycle/appointment/slot-availability?storeId=S&date=D` 中 T 档 `taken=true`；② mp `submit` 同格返回 **4122**。**真 DB 连续两步集成**。
- [ ] AC21：**不进核对 / 打款 / no_show** —— 对手动记录 ① `POST /system/gz/recycle/appointment/{id}/verify` → 4105；② `selectSyncablePayoutIds` 扫不到（该 id 不在返回列表）；③ 把其 `appt_date` 改成昨天后跑 `markExpiredNoShow()`，`status` 仍为 `manual_hold`（未被标 no_show）。
- [ ] AC22：**admin 记录列表默认排除手动记录** —— `GET /system/gz/recycle/appointment/list` 默认不含 `source='manual'` 行；`GET .../list?status=manual_hold` 时返回手动行（状态筛选是唯一入口）。
- [ ] AC23：**mp 店员当日列表排除手动记录** —— `listStaffByDate` 加 `source <> 'manual'` 条件，`GET /app/gz/recycle/staff/appointments?date=` 不返回手动行（**mp 端零代码改动**）。

### F. 周看板

- [ ] AC24：`GET /system/gz/recycle/appointment/week-board?storeId=&weekStart=`，perm `gz:recycle:appointment:list`。`weekStart` 后端归一到**该日期所在周的周一**（传周三也返回周一起 7 天）。返回 `{ storeId, weekStart, weekEnd, slots: [{id,label,startTime,endTime}], cells: [...] }`，`slots` = 该店 `enabled` 档按 admin 配置顺序（与 `listEnabledByStore` 同源）。
- [ ] AC25：`cells` **只返被占格**（空闲格由前端补），每个 cell 含 `apptDate` / `timeSlotId` / `kind`（`customer` | `manual` | `spill`）/ `appointmentId` / `appointmentNo` / `status` / `source` / `mobileSnapshot` / `qtyBucketLabel` / `remark`；`kind='spill'` 的格带源单 `appointmentId`（前端据此禁操作）。「未完成预订」口径 = `ACTIVE_HOLD_STATUSES`（与防超卖同源，AC5）。
- [ ] AC26：一次查询取整周（**不得按 7×N 档循环单查**）—— 一条 `appt_date BETWEEN weekStart AND weekEnd` 的批量查询后在内存分格。

### G. 测试

- [ ] AC27：`mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-recycle -am` 全绿；新增 `manualHold` / `releaseHold` / `reschedule` 各 1 条 happy + 2-3 条 error path 单测（4122 / 4124 / 4128 / 4129 / `@NotBlank`）。
- [ ] AC28：AC18 / AC20 / AC14 / AC15 属**真 DB 断言**（mock 照不出），在 reports 里贴真库 raw output（SQL 查询结果 + curl 响应）。
- [ ] 纯后端 ticket，无 mp AC N（CLAUDE.md §8.2）。

## Tech（端 + 范围）

**后端** `code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-recycle/src/main/java/org/dromara/gz/recycle/`：

| 文件 | 动作 |
|---|---|
| `domain/entity/GzRecycleAppointment.java` | 加 `source` / `rescheduleCount` / `lastRescheduleBy` / `lastRescheduleTime` |
| `domain/bo/GzRecycleManualHoldBo.java` | **新增**：`storeId` `@NotNull` / `apptDate` `@NotNull` / `timeSlotIds` `@NotEmpty` / `remark` `@NotBlank @Size(max=500)` |
| `domain/bo/GzRecycleRescheduleBo.java` | **新增**：`apptDate` `@NotNull` / `timeSlotId` `@NotNull`（无 storeId） |
| `domain/vo/GzRecycleWeekBoardVO.java` | **新增**：`slots` + `cells` 内部类（AC24/AC25 契约） |
| `domain/vo/GzRecycleAppointmentAdminVO.java` | 加 `source` / `timeSlotId` / `spillTimeSlotId` / `rescheduleCount`（现无 timeSlotId，看板与改期弹窗要用） |
| `domain/bo/GzRecycleAppointmentQueryBo.java` | 加 `source`（AC22 默认过滤用） |
| `mapper/GzRecycleAppointmentMapper.java` | `countActiveHoldingSlotForUpdate` 内联状态集加 `manual_hold`；**新增** `countActiveHoldingSlotExcludingForUpdate`；**新增** 手写 `@Update int reschedule(...)`（version 守卫 + 审计三列 + spill 可置 NULL） |
| `service/IGzRecycleAppointmentService.java` + `impl/GzRecycleAppointmentServiceImpl.java` | `ACTIVE_HOLD_STATUSES` 加值；新增 `STATUS_MANUAL_HOLD` / `SOURCE_MP` / `SOURCE_MANUAL` 常量；抽 `resolveSlotAndAssertCapacity`；新增 `manualHold` / `releaseHold` / `reschedule` / `selectWeekBoard`；`listStaffByDate` 与 `selectAdminPage` 加 source 过滤 |
| `exception/GzRecycleErrorCode.java` | 加 `RESCHEDULE_NOT_ALLOWED=4128` / `HOLD_RELEASE_NOT_ALLOWED=4129` |
| `controller/GzRecycleAppointmentController.java` | 加 4 个端点（manual-hold / {id}/release-hold / {id}/reschedule / week-board） |
| `src/test/java/.../GzRecycleAppointmentServiceImplTest.java` 或新测试类 | AC27 |

**DDL**：`code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/`
- `V<ts>__GZ-RECYCLE-010-appointment-manual-hold.sql`
- `V<ts>__GZ-RECYCLE-010-menu-dict.sql`

**事务 / 锁范式**（照抄 `submit()`）：`@Transactional(rollbackFor=Exception.class, isolation=Isolation.REPEATABLE_READ)` + `gz:recycle:lock:slot:{storeId}:{date}` Redis 锁（`tryAcquireRedisLock` + `registerLockReleaseOnTxEnd`，抢不到 → 4126）+ `FOR UPDATE`。手动占用多格跨日期时按 `(store,date)` 分组抢锁，锁按 date 升序获取避免死锁。

**改后必跑**：`mvn clean install -DskipTests -pl ruoyi-modules/ruoyi-gz-recycle -am` 再重启（memory `mvn-clean-install-required`；非 clean 的 install 既不重打 jar 也不重编译测试）。

## 备注

- **`@Version` 实体坑**：改期禁止用 `insert/selectById` 后 `updateById` 补字段（内存 version 不同步 → 静默不落库，memory `version-entity-insert-then-updatebyid-noop`）。改期一律走手写 `@Update`；手动占用一次 `insert` 配齐字段（先 `setTenantId` / `setSource` / `setStatus` 再 insert）。
- **绝不给手动记录填占位 user_id / receiver_openid**（会撞一人一单 4127、污染 mp「我的回收」、给打款留脏 openid，ADR §1）。
- **不动 `verifyAndPayout` 的 `status='submitted'` 守卫**，不动 `gz.recycle.auto_payout.enabled` 默认关。
- **不动 `gz_recycle_time_slot.enabled` 全局开关语义**（门店级永久开关，与单日单格占用串联生效）。
- `RecycleEntityRegistry`（gz-common 回收站注册表）当前**未注册** `gz_recycle_appointment`，本次列变更无跨模块耦合（memory `recycle-registry-cross-module-column-coupling` 已核）。
- **AC23 是对 ADR 坑位 7 的收敛**：ADR 原写「mp 店员列表按 source 渲染成占用条目」，本批 Kevin 定不做 mp 改动 → 改为后端过滤（doc/11 §12.7「下游影响」已同步）。若日后店员反馈"看板占了但 mp 看不到"，再开 mp ticket 做渲染。
- 手动占用记录**不计任何金额口径**（不进 GMV、不进对账、不进 4% 分成），`final_amount_cent` / `out_payout_no` 恒 NULL。

---

## §revision（Kevin 节点触发残留人验不过时填，初始空）
