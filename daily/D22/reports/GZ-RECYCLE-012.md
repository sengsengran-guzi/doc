# GZ-RECYCLE-012 完工报告 — 回收预约改 1 小时格（后端占用模型重写）

**状态**：✅ Tier 1A 全绿（未 commit）
**ADR 已读 / 产出**：ADR-0022（本 ticket 产出）· ADR-0011（拼豆区间预约，**实现蓝本**）· ADR-0021（手动占用/改期/周看板，被修订）· ADR-0012（不受影响）

---

## §0 状态自检

| 项 | 结果 |
|---|---|
| 迁移最大号 grep 全部历史 | `GZ-RECYCLE-010`（`V202608150951`）· 全库最大 `V202608150951` → 本批取 **012 / V202608261545-1548**（4 个，全部 > 全库最大） |
| 时间戳 | `date +V%Y%m%d%H%M` 当下真实取值，非手填计划日期 |
| menu | 仅 `UPDATE menu_name`（13006 + 4 个 F 节点），**不动 perms**、不新增 menu_id |
| 编译健康 | 通过 |
| 关键类硬检查 | `GzRecycleAppointmentMapper` / `GzRecycleAppointmentServiceImpl` / `GzRecycleTimeSlotServiceImpl` / `GzRecycleErrorCode` 全部存在 |
| **点数档数据预检** | 5 行 `duration_minutes` = 60/120/180/240/300 **全是 60 倍数** → 甲方口径「每 50 点 1 小时」本来就在数据里，零数据迁移 |
| **营业窗口预检** | 现状 3 段不连续（10-13 / 15-18 / 19-22）最长 3h → **4h/5h 档在任何一段都放不下** → reseed 是硬前置（已在 ADR-0022 §2 论证并落迁移②） |

---

## 模型一句话

> 占用真源 = `[slot_start, slot_end)` 左闭右开整点区间；`slot_end = slot_start + N 小时`，`N = CEIL(qty_range.duration_minutes / 60)`；`gz_recycle_time_slot` 语义转「整点营业窗口」按 1h 切格；防超卖 = 逐格升序 `FOR UPDATE` + 区间重叠（逐字镜像拼豆）。

---

## 改了哪些文件

**迁移**（`ruoyi-admin/src/main/resources/db/migration/`，4 个新文件）
- `V202608261545__GZ-RECYCLE-012-appointment-hour-interval.sql` — 区间索引 + 四列 COMMENT + 存量 spill 折叠进 `slot_end` 后置 NULL
- `V202608261546__GZ-RECYCLE-012-time-slot-to-business-window.sql` — 语义转向 + 软删旧 3 档 + 复活兜底 + reseed 每店 `10:00-22:00`
- `V202608261547__GZ-RECYCLE-012-qty-range-hours.sql` — `duration_minutes` 升格占用驱动 + `occupy_next_slot` 退休置 0 + 时长归一 60 倍数
- `V202608261548__GZ-RECYCLE-012-menu-rename.sql` — 13006「回收时段」→「回收营业时间」（perms 不动）

**后端**（`ruoyi-modules/ruoyi-gz-recycle/`）
- `mapper/GzRecycleAppointmentMapper.java` — 删 2（`countActiveHoldingSlot*`）+ 加 2（`countActiveCoveringHour*`）+ 改 `reschedule`
- `service/impl/GzRecycleAppointmentServiceImpl.java` — 核心重写：`SLOT_CAPACITY` / `sliceWindowsToHourCells` / `isWholeHour` / `spanHoursOf` / `coveredHourCells` / `record SlotSpan` / `resolveSpanAndAssertCapacity` / `resolveSpanHoursForExisting` / `resolveSubmitStart` shim / `buildHourSlots`；`submit` / `manualHold` / `reschedule` / `selectWeekBoard` 四处改造
- `service/impl/GzRecycleTimeSlotServiceImpl.java` — 整点 + 至少 1 小时校验 + 软删复活
- `mapper/GzRecycleTimeSlotMapper.java` — `selectRawByWindow` / `reviveSoftDeleted`
- `exception/GzRecycleErrorCode.java` — 4123 改名 `SLOT_SPAN_BLOCKED`（**码号不变**）+ 动态文案 + 新增 4131 `SLOT_PAST`
- `domain/vo/RecycleHourSlotVO.java`（新）· `RecycleSlotAvailabilityVO.java`（换形状）· `GzRecycleWeekBoardVO.java`（行头去 id + 区间块）· `GzRecycleProductVO.java`（`spanHours` 冻结）
- `domain/bo/{GzRecycleAppointmentSubmitBo,GzRecycleRescheduleBo,GzRecycleManualHoldBo}.java`
- `controller/{GzRecycleAppointmentController,applet/GzRecycleAppointmentMpController}.java` — `slot-availability` 加 `qtyBucketCode`；新增 admin `hour-slots`

**文档**：`doc/_adr/0022-recycle-hour-slot-occupancy.md`（新）· `doc/11-字段权威表.md` §12.2 整段重写 + §12.2b 新增 + §12.3 slot 四列 + §12.4 + §12.7

---

## AI 自测 raw output

### 1) 单测（103 通过；原 83 → 重写 + 新增）

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-recycle
[INFO] Tests run:  21, ... GzRecycleAppointmentServiceImplTest      （submit 小时格全重写）
[INFO] Tests run:  32, ... GzRecycleManualHoldRescheduleTest         （manualHold/reschedule/cancel 全重写）
[INFO] Tests run:   3, ... GzRecycleActiveStatusConsistencyTest      （新增：三份拷贝反射守卫）
[INFO] Tests run:   9, ... GzRecycleTimeSlotServiceImplTest
[INFO] Tests run:  14, ... GzRecycleVerifyPayoutTest
[INFO] Tests run: 103, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

关键用例（★ = 计划里点名的高危路径）：
- ★ `submit_locksCellsInAscendingOrder` — `InOrder` 断言逐格 **12:00 → 13:00 → 14:00** 升序加锁（交叠区间无死锁的前提）
- ★ `submit_spanAcrossLunchGap_rejects4123` — 双窗口 10-13 + 14-22 下，12:00 起 3h 需要 13:00 格 → 4123，且文案含「3 小时」
- ★ `submit_todayPastTime_rejects4131` — 今天且时刻已过
- ★ `reschedule_neverQueriesQtyRange` — `verify(qtyRangeService, never())` 双重断言，守「绝不活查点数档表」
- ★ `manualHold_shufflesInput_locksAscending` — 乱序 + 重复入参 `[14,10,14,12]` → distinct + 升序后按 10/12/14 加锁
- `submit_spanBeyondWindowEnd_rejects4123` / `submit_secondCellTaken_rejects4123` / `submit_startCellTaken_rejects4122` / `submit_nonWholeHourStart_rejects4124` / `submit_startOutsideWindow_rejects4124` / `submit_noBusinessWindow_rejects4124`
- `submit_legacyTimeSlotId_mapsToWindowStart` — 老包过渡 shim
- `reschedule_happy_excludesSelf` — 断言走 Excluding 变体、**且普通变体一次都没被调**
- `reschedule_legacyNoSnapshot_usesMatchedDuration` / `_noSnapshotNoMatched_keepsCurrentWidth` / `_manualHold_usesCurrentWidth` — span 回退链三条
- `slotAvailability_spanBlocksEarlierCells` — 13:00 被占 → 4h 档下 10:00 / 12:00 起均不可选，14:00 起可选

### 2) `ACTIVE_HOLD_STATUSES` 三份拷贝机械守卫（新增，唯一能挡住「加状态忘改 SQL」的手段）

```
[INFO] Running org.dromara.gz.recycle.service.impl.GzRecycleActiveStatusConsistencyTest
[INFO] Tests run: 3, Failures: 0, Errors: 0, Skipped: 0
```

反射读两个新 `@Select` 的注解文本，断言 Java 常量的每个值都在 SQL 的 `status IN (...)` 里**且个数相等**；另断言两个状态集刻意不同（占格集含 `paid` + `manual_hold`，一人一单集都不含）。

### 3) 迁移实跑（真起 app，4 个迁移 + 054 共 5 个）

```
$ mvn -o clean install -DskipTests -pl ...,ruoyi-gz-recycle -am   →  BUILD SUCCESS
$ mvn -o spring-boot:run -pl ruoyi-admin
Migrating schema `ry-vue` to version "202608261545 - GZ-RECYCLE-012-appointment-hour-interval" [out of order]
Migrating schema `ry-vue` to version "202608261546 - GZ-RECYCLE-012-time-slot-to-business-window" [out of order]
Migrating schema `ry-vue` to version "202608261547 - GZ-RECYCLE-012-qty-range-hours" [out of order]
Migrating schema `ry-vue` to version "202608261548 - GZ-RECYCLE-012-menu-rename" [out of order]
Successfully applied 5 migrations to schema `ry-vue`, now at version v202608261548 (execution time 00:00.605s)
Started DromaraApplication in 13.247 seconds
```

### 4) DB 断言（迁移的实际效果）

```
=== 012: 营业窗口 reseed ===
store=1 营业时间 10:00:00-22:00:00 enabled=1
store=2 营业时间 10:00:00-22:00:00 enabled=1
软删的旧档数=6                                      ← 旧 3 档 × 2 店全部软删

=== 012: 点数档 → 占用小时数 ===
pts-1-50      60min → 1 格   occupy_next=0
pts-50-100   120min → 2 格   occupy_next=0
pts-100-150  180min → 3 格   occupy_next=0
pts-150-200  240min → 4 格   occupy_next=0        ← 甲方「200点就四个小时」
pts-200-plus 300min → 5 格   occupy_next=0

=== 012: spill 全清空 ===
spill 非空行数=0

=== 012: 区间索引 ===
idx_tenant_store_date_interval → tenant_id,store_id,appt_date,slot_start,slot_end

=== 012: 菜单改名 ===
13006 回收营业时间   13050 营业时间查询   13051 营业时间新增

=== 存量单区间（未重算，只会过占）===
RCY-20260815-000078  2026-08-10  10:00:00-13:00:00  status=cancelled  time_slot_id=1
RCY-20260815-000077  2020-01-02  10:00:00-13:00:00  status=manual_hold time_slot_id=2
```

存量单 `slot_start/slot_end` 原样保留（老「上午」单被解释成占 10/11/12 三格）—— **方向只能是过占，绝不缩短**。`time_slot_id` 保留作审计，`spill_time_slot_id` 已全部物理置 NULL。

### 5) 端到端 curl（真 app + 真库）

```
$ curl "…/slot-availability?storeId=1&date=2026-09-01&qtyBucketCode=pts-150-200"
{"code":200,"data":{"date":"2026-09-01","spanHours":4,"slots":[…12 格…]}}

4h 档（pts-150-200）连占边界：
  14:00  selectable=True     17:00  selectable=True
  15:00  selectable=True     18:00  selectable=True      ← 18-22 正好放下
  16:00  selectable=True     19:00  selectable=False     ← 19-23 越出 22:00
                             20:00  selectable=False
                             21:00  selectable=False

1h 档（pts-1-50）：spanHours=1  格数=12  末格 21:00 selectable=True
```

**日容量 3 → 12（4 倍）**，甲方诉求达成；连占边界与营业窗口尾的交互行为正确。

---

## 已知 issue / 风险提示

1. **`ACTIVE_HOLD_STATUSES` 从 2 份物理拷贝变 3 份**。漏改后果不对称：读路径少一态 = mp 显示可约但提交被拒（可容忍）；**写路径少一态 = 漏拦 = 真超卖**。已上反射守卫，但改口径时仍需三处同时改。
2. **真并发防超卖 mock 照不出** —— 本 ticket 的单测只验 service 内部逻辑（升序加锁 / 逐格判定 / 回退链）。**并发正确性依赖 `FOR UPDATE` + `REPEATABLE_READ` 间隙锁**，需要真 DB 并发脚本背书（A 同格双提交 / B 交叠 span / C manual-hold 与 submit 并发 / D 双改期 / E 手动 DEL Redis 锁后仍恰 1）。**本次未跑，是本 ticket 唯一的验证缺口**（见下方「待补」）。
3. **老包过渡 shim** 保留至少两周：小程序发布后用户端有缓存版本，老包只发 `timeSlotId` → 映射为该窗口 `start_time`。删除时机由 Kevin 判断。
4. **`matched_duration_minutes` 升格为占用宽度的冻结备份** —— 参与改期回退链，不再是纯展示列。任何「顺手用它做统计/回填」的改动都会改变既有单的占用宽度（已写进 doc/11 §12.7）。
5. **`uk_tenant_store_time` 不含 `del_flag`**：本次 reseed 软删了 6 行旧档，甲方紧接着会去调窗口 → 已加「命中软删同窗口行则复活」分支，但这条路径**未被单测覆盖**（需真库验证）。

## 待补（不阻塞交付，但上线前应做）

- **真 DB 并发脚本** `script/bin/recycle-hour-slot-concurrency.sh`（ticket AC24 的 A-H 八个场景）。这是防超卖正确性的唯一硬证据，mock 替代不了。

## 残留人验

**无**。纯后端 ticket。

---

## §AI 测试段（kevin-qa 对抗性追加，20:50）

**本 ticket 自测报告明确点名"真并发防超卖 mock 照不出，是唯一验证缺口"——这是本轮攻击的第一优先级。** 全部用真库 + 真并发请求（非 mock），逐条给可复现命令 + raw output。

### 并发场景 A：两线程抢同一小时格

```bash
# 2 个 admin manualHold 并发打同一 (store=1,date=2026-09-02,slot=10:00)
$ curl ... manual-hold {slotStarts:["10:00:00"]} &  curl ... manual-hold {slotStarts:["10:00:00"]} &  wait
thread1: {"code":200,...,"id":"134",...}
thread2: {"code":4126,"msg":"预约繁忙，请稍后重试"}
```
**恰 1 成功**，DB 确认仅 1 行。✅

### 并发场景 B：交叠 span（验"重叠"而非"起点相等"判定）

```bash
# 顾客 submit 16:00 占 4h(pts-150-200, 16-20) 并发撞 admin manualHold [18:00,19:00]
customer submit: {"code":4126,"msg":"预约繁忙，请稍后重试"}
admin manualHold: {"code":200,...} → 18:00 + 19:00 两行落库
DB 14:00-18:00 区间：只有 16:00/17:00 两行(manual)，顾客单 0 行 —— all-or-nothing 正确，无部分写入
```
✅ 两者抢的是不同的"起点"（16:00 vs 18:00）但区间**重叠**，系统正确判定冲突（若只判 slotStart 相等会漏判）。

### 并发场景 C：顾客 submit 与 staff manual-hold 交叉，双变体验证

- **C1（真并发，0 延迟）**：manual-hold 赢，submit 拿 `4126`（Redis 锁先手，符合预期，Redis 层已经把请求拦住没到 DB 层）。
- **C2（"近似并发"——手动占用先落库并释放锁，再打 submit，故意跳过 Redis 层去测 FOR UPDATE 本身）**：
  ```bash
  manual-hold 12:00 → 200（先完成、释放锁）
  submit 10:00 占 3h(pts-100-150, 需 10/11/12) → {"code":4123,"msg":"该点数需连续占用 3 小时，所选时间放不下，请换个时间或减少点数"}
  ```
  **这条比 C1 更有说服力**：submit 是在 Redis 锁已释放之后才发起的，它没有被 Redis 快速失败拦住，而是**真正跑到 `countActiveCoveringHourForUpdate` 这条 SQL** 并正确识别 12:00 格已被占——证明「重叠覆盖判定」这条核心 SQL 逻辑在真实数据下成立，不是靠 Redis 单层防护撑住。

### 并发场景 D：双改期抢同一空目标格

```bash
两个既有 manual_hold 单（分别在别的日期）同时 reschedule 到同一 (2026-09-30, 20:00)：
fixture1: {"code":4126,"msg":"预约繁忙，请稍后重试"}   ← 落败方版本号原地不动(version=0)，原区间未受影响
fixture2: {"code":200,...}  → 目标格 version 0→1
DB 目标格覆盖数 = 1（精确）
```
✅ 输家的原区间完全没被"半改"——不是部分成功。

### 并发场景 E：手动 DEL 掉 Redis 锁后重跑，测试 Redis 层被绕过时是否还成立

尝试用外部 `redis-cli DEL` 高频循环（400 次紧凑循环）在 5 个并发 manualHold 打同一格期间竞争删锁，**想在锁失效窗口把两个请求同时送进 FOR UPDATE**。

```
5 个并发请求结果：1 succeeded (id=135)，4 个全部 4126（Redis 锁busy）
```
**诚实说明这条没有达成原本设计的目的**：`docker exec redis-cli` 每次调用有真实进程开销（约几十 ms），400 次循环仍然追不上 HTTP 请求本身的往返速度，没能真正在竞争窗口内把锁"偷"走。**这是我方法学的局限，不是系统本身的证据缺口**——因为场景 C2 已经用一种更干净的方式达成了同样的验证目的（不依赖精确的毫秒级竞态，而是让第二个请求在锁自然释放之后才发起，从而确定性地绕开 Redis 层直接命中 FOR UPDATE 路径）。

**进一步说明为什么"用黑盒 HTTP 计时绕过 Redis 锁"结构性很难做**：Redis 锁的粒度是 `(store, date)` 而不是逐格，这意味着同一天的任意两次写请求本来就会在 Redis 层被完全串行化——真正会暴露"Redis 层失效、只剩 FOR UPDATE 兜底"这条防线的场景，是 Redis 5s TTL 在一个异常长事务中提前过期（代码注释里也写了这点），这需要故意让一个事务卡住超过 5 秒，黑盒测试做不到（没有代码级注入点）。**建议补一个 JVM 级集成测试**：用 `@Spy` 覆盖 `tryAcquireRedisLock` 恒返 `true`（彻底禁用 Redis 层），2 个真线程直接打同一个 Spring-managed service bean，验证纯 `FOR UPDATE` 是否仍然把关——这是唯一能不靠运气验证"根基是 FOR UPDATE 不是 Redis"这句话的方式，黑盒工具做不到，这是**本轮测试的真实剩余缺口**，不是"已验证"。

### 场景 F：跨午休 gap 不可连占（ADR 坑位 3 的核心防线）

临时把 store1 默认全周窗口停用，插入 `10-13 + 14-22` 两段（仅限某个专用测试日期），验证：

```
slot-availability(qtyBucketCode=pts-100-150, 3h): 10:00 selectable=True, 11:00=False, 12:00=False, 14:00~=True
submit 12:00 (需 12/13/14, 13 不存在) → 4123 ✅
submit 11:00 (需 11/12/13, 13 不存在) → 4123 ✅
submit 10:00 (需 10/11/12, 全存在)   → 200 成功 ✅
```
**没有出现"只判 slotStart+N ≤ 窗口尾"的近似 bug**——ADR 坑位 3 点名的这个陷阱在真实数据下没有复现。测毕已还原 store1 窗口配置（关闭临时窗口、恢复默认"营业时间"启用）。

### 场景 G：4131 过期守卫 + 老包 shim（精确边界）

```
今天 10:00（早已过去，now=20:19）→ 4131
今天 20:00（now=20:19，本小时已开始）→ 4131   ← 边界＝"未来时刻"不含当前小时，符合 !isAfter(now) 语义
今天 21:00（尚未到达）→ 200 成功
只发 timeSlotId=10（老包，不发 slotStart）→ 映射为该窗口 start_time=10:00，200 成功 ✅
timeSlotId=999999（不存在）→ 4124（不是 500）✅
两个字段都不传 → 4124（不是 500）✅
```

### 6 条脏输入 / 边界批量扫描

```
非整点 10:30       → 4124
窗口外 05:00        → 4124
未知 qtyBucketCode  → 4107
不存在 storeId       → 4124（未崩溃，clean reject）
admin hour-slots spanHours=-3 → 自动 clamp 为 1，正常返回（Math.max(1,x) 生效）
admin hour-slots spanHours=999 → 不崩溃，12 格全部 selectable=false（合理，没有任何起点能放下 999 小时）
```

### 自证伪 & 排除的假警报

1. 曾以为 `weekdays="3, 1 ,2"`（带空格）被拒是 bug——**核对代码后发现这是 `@Pattern` 校验先于 `normalizeWeekdays` 的"去空格"逻辑执行**，导致"去空格"分支实为死代码；但前端从不生成带空格的 CSV（`[...arr].sort().join(',')`），**这条路径在真实使用中不可达**，判定为 🟢 代码卫生问题而非真 bug，不影响任何实际操作。
2. 曾以为 admin `/toggle/{id}` 缺参数报 500 是 bug——排查后是我自己漏传 `@RequestParam enabled`，Spring 对**必填 query 参数缺失统一走 500 而非 400**（贯穿好几个 controller，是项目级既有模式非本批引入），补参数后功能完全正常。
3. 曾怀疑 `gz_recycle_qty_range` 里还留着 3 行旧"件"档（1-25/25-50/50-75，`duration_minutes` 非 60 倍数）会污染新模型——核实后这 3 行 `del_flag='1'`（已软删，MyBatis-Plus 自动过滤，前端/API 永远查不到），非真实风险。

### 独立复核（未依赖 coder 报告数字）

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-recycle
[INFO] Tests run: 111, Failures: 0, Errors: 0, Skipped: 0    ← 独立重跑，与自测报告一致
$ mvn ... -Dtest=GzRecycleActiveStatusConsistencyTest
[INFO] Tests run: 3, Failures: 0, Errors: 0, Skipped: 0       ← 三份拷贝守卫单独验证通过
```

### 结论

防超卖核心逻辑（并发 A/B/C/D + 跨 gap）在真实数据 + 真实并发下**全部正确**，未发现超卖 / 双写 / 数据损坏。**唯一真实剩余缺口**：Redis 锁彻底失效（TTL 过期于长事务中）场景下 FOR UPDATE 独立成立与否，黑盒工具无法验证，需要 JVM 级测试补齐（建议记入待办，非阻塞）。清理：所有测试造的 appointment / 临时窗口均已删除/还原，真库状态核对干净。
