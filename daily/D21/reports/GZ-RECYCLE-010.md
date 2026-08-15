# GZ-RECYCLE-010 — 完工报告

**Tier**: 1A（kevin-coder 自测）
**日期**：2026-08-15
**backend**：`mvn spring-boot:run -pl ruoyi-admin`，端口 8080，本次实施结束后**继续留跑**供 kevin-qa Tier 1B 复用。

---

## §0 状态自检

- `git status`：RuoYi-Vue-Plus 仓 `staging` 分支，working tree 干净（实施前）
- 上游依赖：ticket 标注「依赖：—」，无前置 ticket
- 关键类/表/API 硬检查：`gz_recycle_appointment` 表 / `GzRecycleAppointmentServiceImpl.submit()` / `countActiveHoldingSlotForUpdate` / `GzRecycleErrorCode` 均按 ADR-0021 + doc/11 §12.7 描述存在，符合预期
- ADR 已读：doc/_adr/0021-recycle-manual-slot-hold-and-reschedule.md（§1/§2 + 关键实现坑位 11 条，逐条对照见下）
- 编译健康：实施前 `mvn compile -pl ruoyi-modules/ruoyi-gz-recycle -am` 通过

---

## AC 完成情况

**A-G 组全部 28 条 AC 均已实现并验证，无遗漏、无简化范围。**

| 组 | AC | 状态 | 验证方式 |
|---|---|---|---|
| A 迁移/字典/权限 | AC1-4 | ✅ | 真库 DESC + SELECT |
| B 状态集/公共校验 | AC5-7 | ✅ | grep + 代码走查 |
| C 手动占用/释放 | AC8-11 | ✅ | 真库 curl + SQL |
| D 改期 | AC12-18 | ✅ | 真库 curl + SQL（含双线程并发） |
| E 隔离性 | AC19-23 | ✅ | 真库 curl + SQL |
| F 周看板 | AC24-26 | ✅ | 真库 curl |
| G 测试 | AC27-28 | ✅ | mvn test 74/74 绿 + 本报告 raw output |

---

## 关键实现坑位对照（ADR-0021，逐条）

1. **手动占用不走 submit()** —— 新写独立 `manualHold()`，只做时段合法性+容量校验+INSERT 三步 ✅
2. **ACTIVE_HOLD_STATUSES 两处同步加 manual_hold** —— Java 常量 + `countActiveHoldingSlotForUpdate` 两处 grep 均命中，AC5 验证见下 ✅
3. **USER_ACTIVE_STATUSES 不加 manual_hold** —— 显式验证未被顺手补齐，AC6 验证见下 ✅
4. **改期容量校验用 ExcludingForUpdate 变体** —— 新增 mapper 方法 + AC14 真库验证 ✅
5. **改期后 spill 允许显式置 NULL** —— 手写 `@Update` 无 `<if>`，`#{spillTimeSlotId}` 为 null 时 MyBatis 绑定 JDBC NULL；AC15 真库验证 spill 由 9 变 NULL ✅
6. **手动记录不得进打款** —— `receiver_openid` 恒 NULL（第二道闸）+ `verifyAndPayout` 的 `status='submitted'` 守卫不改动（第一道闸）；AC21① 验证 4105 ✅
7. **mp 店员列表加 source<>'manual' 过滤** —— `listStaffByDate` 加一行 `.ne(...)`；AC23 真库验证 ✅
8. **mp「我的回收」不受影响** —— `selectMyList` 未改动，手动记录 `user_id` 恒 NULL 天然不命中 ✅
9. **no_show cron 不扫 manual_hold** —— 未加清理任务；AC21③ 用真实 `selectExpiredSubmittedIds` 同款 SQL 对真库验证 ✅
10. **迁移 append-only** —— 两个新文件时间戳 `date +V%Y%m%d%H%M` 当下真实时间（202608150950/0951），未改动任何已应用迁移 ✅
11. **RecycleEntityRegistry 未注册本表** —— 核对确认无跨模块耦合 ✅

---

## §N 完工总结

### git diff --stat

```
$ git status --short
 M ruoyi-modules/ruoyi-gz-recycle/src/main/java/org/dromara/gz/recycle/controller/GzRecycleAppointmentController.java
 M ruoyi-modules/ruoyi-gz-recycle/src/main/java/org/dromara/gz/recycle/domain/bo/GzRecycleAppointmentQueryBo.java
 M ruoyi-modules/ruoyi-gz-recycle/src/main/java/org/dromara/gz/recycle/domain/entity/GzRecycleAppointment.java
 M ruoyi-modules/ruoyi-gz-recycle/src/main/java/org/dromara/gz/recycle/domain/vo/GzRecycleAppointmentAdminVO.java
 M ruoyi-modules/ruoyi-gz-recycle/src/main/java/org/dromara/gz/recycle/exception/GzRecycleErrorCode.java
 M ruoyi-modules/ruoyi-gz-recycle/src/main/java/org/dromara/gz/recycle/mapper/GzRecycleAppointmentMapper.java
 M ruoyi-modules/ruoyi-gz-recycle/src/main/java/org/dromara/gz/recycle/service/IGzRecycleAppointmentService.java
 M ruoyi-modules/ruoyi-gz-recycle/src/main/java/org/dromara/gz/recycle/service/impl/GzRecycleAppointmentServiceImpl.java
?? ruoyi-admin/src/main/resources/db/migration/V202608150950__GZ-RECYCLE-010-appointment-manual-hold.sql
?? ruoyi-admin/src/main/resources/db/migration/V202608150951__GZ-RECYCLE-010-menu-dict.sql
?? ruoyi-modules/ruoyi-gz-recycle/src/main/java/org/dromara/gz/recycle/domain/bo/GzRecycleManualHoldBo.java
?? ruoyi-modules/ruoyi-gz-recycle/src/main/java/org/dromara/gz/recycle/domain/bo/GzRecycleRescheduleBo.java
?? ruoyi-modules/ruoyi-gz-recycle/src/main/java/org/dromara/gz/recycle/domain/vo/GzRecycleWeekBoardVO.java
?? ruoyi-modules/ruoyi-gz-recycle/src/test/java/org/dromara/gz/recycle/service/impl/GzRecycleManualHoldRescheduleTest.java

$ git diff --stat
 .../controller/GzRecycleAppointmentController.java |  73 +++++
 .../domain/bo/GzRecycleAppointmentQueryBo.java     |  11 +-
 .../domain/entity/GzRecycleAppointment.java        |  14 +-
 .../domain/vo/GzRecycleAppointmentAdminVO.java     |  14 +
 .../gz/recycle/exception/GzRecycleErrorCode.java   |  10 +
 .../recycle/mapper/GzRecycleAppointmentMapper.java |  98 ++++++-
 .../service/IGzRecycleAppointmentService.java      |  59 ++++
 .../impl/GzRecycleAppointmentServiceImpl.java      | 307 +++++++++++++++++++--
 8 files changed, 558 insertions(+), 28 deletions(-)
```

### 新增关键产物

- `domain/bo/GzRecycleManualHoldBo.java` — 手动占用提交 BO（`@NotNull storeId/apptDate` / `@NotEmpty timeSlotIds` / `@NotBlank @Size(max=500) remark`）
- `domain/bo/GzRecycleRescheduleBo.java` — 改期提交 BO（`@NotNull apptDate/timeSlotId`，无 storeId）
- `domain/vo/GzRecycleWeekBoardVO.java` — 周看板 VO（`slots` + `cells` 内部类，`kind` 枚举 customer/manual/spill）
- `mapper` 新增 `countActiveHoldingSlotExcludingForUpdate` / `releaseHold` / `reschedule`（手写 `@Update`）
- `service` 新增 `manualHold` / `releaseHold` / `reschedule` / `selectWeekBoard` + 私有公共方法 `resolveSlotAndAssertCapacity`（`private record SlotResolution`）
- `controller` 新增 4 端点：`POST manual-hold` / `POST {id}/release-hold` / `POST {id}/reschedule` / `GET week-board`
- 两个迁移文件（DDL + 字典/菜单/权限）
- 新测试类 `GzRecycleManualHoldRescheduleTest.java`（15 条用例，happy + error path 全覆盖）

---

## AI 自测 raw output

### ① mvn compile + test（全绿，74 条，含 15 条新增）

```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-recycle -am
...
[INFO] Running org.dromara.gz.recycle.service.impl.GzRecycleManualHoldRescheduleTest
09:54:32.428 [main] INFO org.hibernate.validator.internal.util.Version -- HV000001: Hibernate Validator 8.0.3.Final
09:54:32.549 [main] INFO ...GzRecycleAppointmentServiceImpl -- [gz-recycle] releaseHold id=50 appointment_no=RCY-20260815-000010
09:54:32.557 [main] INFO ...GzRecycleAppointmentServiceImpl -- [gz-recycle] manualHold storeId=1 date=2026-08-20 slots=[10, 15, 19] count=3 operator=owner-kevin
09:54:32.560 [main] INFO ...GzRecycleAppointmentServiceImpl -- [gz-recycle] reschedule id=60 appointment_no=null → date=2026-08-21 slot=15 spill=19 operator=owner-kevin
09:54:32.597 [main] INFO ...GzRecycleAppointmentServiceImpl -- [gz-recycle] reschedule id=65 appointment_no=null → date=2026-08-21 slot=15 spill=null operator=owner-kevin
09:54:32.601 [main] INFO ...GzRecycleAppointmentServiceImpl -- [gz-recycle] reschedule id=61 appointment_no=null → date=2026-08-21 slot=19 spill=null operator=owner-kevin
[INFO] Tests run: 15, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.211 s -- in org.dromara.gz.recycle.service.impl.GzRecycleManualHoldRescheduleTest
...
[INFO] Results:
[INFO]
[INFO] Tests run: 74, Failures: 0, Errors: 0, Skipped: 0
[INFO]
[INFO] ------------------------------------------------------------------------
[INFO] Reactor Summary for RuoYi-Vue-Plus 5.6.1:
...
[INFO] ruoyi-gz-recycle ................................... SUCCESS [  1.900 s]
[INFO] ------------------------------------------------------------------------
[INFO] BUILD SUCCESS
[INFO] ------------------------------------------------------------------------
```

（`mvn clean install -DskipTests -pl ruoyi-modules/ruoyi-gz-recycle -am` 已跑，jar 重打，`ruoyi-admin` `spring-boot:run` 已重启验证真库。）

### ② AC1/AC2 — 迁移应用后 DESC + 存量数据核对（真库）

```
$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -e "DESC gz_recycle_appointment;" | grep -E "^(source|user_id|receiver_openid|product_snapshot_json|reschedule_count|last_reschedule_by|last_reschedule_time)"
user_id                 bigint unsigned   YES    NULL
product_snapshot_json   json              YES    NULL
receiver_openid         varchar(64)       YES    NULL
source                  varchar(16)       NO     mp
reschedule_count        int               NO     0
last_reschedule_by      varchar(64)       YES    NULL
last_reschedule_time    datetime(3)       YES    NULL

$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -e "SELECT COUNT(*) FROM gz_recycle_appointment WHERE source <> 'mp';"
non_mp_count
0
```

Flyway 应用记录（完整重启一次，无 checksum / out-of-order 报错）：

```
$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -e "SELECT installed_rank, version, description, success FROM flyway_schema_history ORDER BY installed_rank DESC LIMIT 2;"
installed_rank  version         description                       success
165             202608150951    GZ-RECYCLE-010-menu-dict           1
164             202608150950    GZ-RECYCLE-010-appointment-manual-hold  1
```

后端启动日志（`Successfully validated 165 migrations` / 无 ERROR）：

```
INFO  o.f.core.internal.command.DbValidate -- Successfully validated 165 migrations (execution time 00:00.080s)
WARN  o.f.core.internal.command.DbMigrate -- outOfOrder mode is active. Migration of schema `ry-vue` may not be reproducible.
INFO  o.f.core.internal.command.DbMigrate -- Schema `ry-vue` is up to date. No migration necessary.
INFO  org.dromara.DromaraApplication -- Started DromaraApplication in 10.839 seconds
(♥◠‿◠)ﾉﾞ  RuoYi-Vue-Plus启动成功   ლ(´ڡ`ﾞ)ﾞ
```

### ③ AC3/AC4 — 字典 + 菜单 + 授权面（真库）

```
$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -e "SELECT dict_code, dict_label, dict_value FROM sys_dict_data WHERE dict_type='gz_recycle_status' ORDER BY dict_sort;"
...
9264    手动占用    manual_hold

$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -e "SELECT menu_id, menu_name, parent_id, menu_type, visible, perms FROM sys_menu WHERE menu_id IN (13015,13016);"
menu_id  menu_name      parent_id  menu_type  visible  perms
13015    手动占用/释放   13002      F          0        gz:recycle:appointment:hold
13016    预约改期        13002      F          0        gz:recycle:appointment:reschedule

$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -e "SELECT menu_id, role_id FROM sys_role_menu WHERE menu_id IN (13015,13016,13021) ORDER BY menu_id, role_id;"
menu_id  role_id
13015    100
13015    101
13015    103
13016    100
13016    101
13016    103
13021    100
13021    101
13021    103
```

授权面 = 13021 持有角色（100/101/103）∪ {100}，13015/13016 与 13021 完全一致 ✅。

### ④ AC5/AC6/AC7 — 状态集/公共方法（代码走查）

```
$ grep -c "manual_hold" .../service/impl/GzRecycleAppointmentServiceImpl.java   # 5
$ grep -c "manual_hold" .../mapper/GzRecycleAppointmentMapper.java              # 8
$ grep -n "status IN ('submitted', 'confirmed_onsite', 'paying', 'paid', 'payout_failed', 'manual_hold')" mapper/GzRecycleAppointmentMapper.java
:80:  countActiveHoldingSlotForUpdate
:104: countActiveHoldingSlotExcludingForUpdate
（两处状态集元素完全一致，6 个）

$ grep -n "USER_ACTIVE_STATUSES\s*=" -A1 service/impl/GzRecycleAppointmentServiceImpl.java
    private static final List<String> USER_ACTIVE_STATUSES =
        List.of("submitted", "confirmed_onsite", "paying", "payout_failed");   # 不含 manual_hold

$ grep -n "countActiveByUserForUpdate" -A4 mapper/GzRecycleAppointmentMapper.java | grep "status IN"
    "  AND status IN ('submitted', 'confirmed_onsite', 'paying', 'payout_failed') AND del_flag = '0' "  # 不含 manual_hold

$ grep -n "resolveSlotAndAssertCapacity(" service/impl/GzRecycleAppointmentServiceImpl.java
:218:  submit() 调用
:348:  方法定义
:760:  manualHold() 调用
:844:  reschedule() 调用
（3 处调用点：submit / manualHold / reschedule）
```

### ⑤ AC8-AC11 — 手动占用 / 释放（真库 curl + SQL，含 all-or-nothing）

```
# AC8 happy：3 格全落
$ curl -X POST /system/gz/recycle/appointment/manual-hold \
  -d '{"storeId":2,"apptDate":"2026-09-01","timeSlotIds":[2,4,9],"remark":"AC8-happy-3slots"}'
{"code":200,"data":[{"id":"7",...},{"id":"8",...},{"id":"9",...}]}

$ SELECT id, source, status, time_slot_id, spill_time_slot_id, user_id, receiver_openid, product_snapshot_json
  FROM gz_recycle_appointment WHERE store_id=2 AND appt_date='2026-09-01';
id  source  status       time_slot_id  spill_time_slot_id  user_id  receiver_openid  product_snapshot_json
7   manual  manual_hold  2             NULL                 NULL     NULL             NULL
8   manual  manual_hold  4             NULL                 NULL     NULL             NULL
9   manual  manual_hold  9             NULL                 NULL     NULL             NULL

# AC9 all-or-nothing：预占 slot4，批量 [2,4,9] 应全部回滚
$ curl -X POST manual-hold -d '{"storeId":2,"apptDate":"2026-09-02","timeSlotIds":[4],"remark":"AC9-preoccupy"}'
{"code":200,"data":[{"id":"10",...}]}
$ before=1（COUNT for store=2 date=2026-09-02）

$ curl -X POST manual-hold -d '{"storeId":2,"apptDate":"2026-09-02","timeSlotIds":[2,4,9],"remark":"AC9-should-rollback"}'
{"code":4122,"msg":"该时段已被预约，请换个时段","data":null}

$ after=1（COUNT 不变，只剩预占的 id=10；slot 2 的行虽先于冲突被 INSERT，但随事务整体回滚，无残留）
$ SELECT id, time_slot_id, remark FROM gz_recycle_appointment WHERE store_id=2 AND appt_date='2026-09-02';
id  time_slot_id  remark
10  4             AC9-preoccupy

# AC10 校验
$ curl -X POST manual-hold -d '{"storeId":2,"apptDate":"2026-09-03","timeSlotIds":[2],"remark":"   "}'
{"code":500,"msg":"请填写占用备注","data":null}
$ curl -X POST manual-hold -d '{"storeId":2,"apptDate":"2026-09-03","timeSlotIds":[],"remark":"备注"}'
{"code":500,"msg":"请至少选择一个时段","data":null}
$ curl -X POST manual-hold -d '{"storeId":2,"apptDate":"2026-09-03","timeSlotIds":[99999],"remark":"备注"}'
{"code":4124,"msg":"到店时段无效或已关闭，请重新选择","data":null}
$ curl -X POST manual-hold -d '{"storeId":2,"apptDate":"2026-09-03","timeSlotIds":[1],"remark":"备注"}'  # store1 的时段传给 store2
{"code":4124,"msg":"到店时段无效或已关闭，请重新选择","data":null}
$ SELECT COUNT(*) FROM gz_recycle_appointment WHERE appt_date='2026-09-03';
0

# AC11 happy + 隔离性
$ curl -X POST /system/gz/recycle/appointment/7/release-hold
{"code":200,"data":{"status":"cancelled",...}}
$ SELECT status, cancelled_time IS NOT NULL FROM gz_recycle_appointment WHERE id=7;
cancelled  1
$ curl GET slot-availability?storeId=2&date=2026-09-01
[{"id":"2","taken":false},{"id":"4","taken":true},{"id":"9","taken":true}]   # 释放后立即可约

$ curl -X POST /system/gz/recycle/appointment/1/release-hold   # id=1 是顾客单(source=mp)
{"code":4129,"msg":"仅手动占用记录可在看板释放","data":null}
$ curl -X POST /system/gz/recycle/appointment/7/release-hold   # 对已释放的手动记录再次释放
{"code":4129,"msg":"仅手动占用记录可在看板释放","data":null}
```

### ⑥ AC12-AC18 — 改期（真库 curl + SQL，含双线程并发）

```
# 造大单：store=2 date=2026-09-10 slot=2(T1) 点数档 pts-200-plus（occupy_next_slot=1）
$ curl -X POST /app/gz/recycle/appointment/submit \
  -d '{"storeId":2,"product":{"categories":["card"],"qtyBucketCode":"pts-200-plus"},"apptDate":"2026-09-10","timeSlotId":2}'
{"code":200,"data":{"id":"12",...}}
$ SELECT time_slot_id, spill_time_slot_id FROM gz_recycle_appointment WHERE id=12;
time_slot_id  spill_time_slot_id
2             4          # T1=2, spill=T2=4（本店 enabled 序列 2/4/9）

# AC14：改期到 T2（自己 spill 占着的档）必须成功
$ curl -X POST /system/gz/recycle/appointment/12/reschedule -d '{"apptDate":"2026-09-10","timeSlotId":4}'
{"code":200,"data":{"timeSlotId":"4","spillTimeSlotId":"9","rescheduleCount":1,...}}
$ SELECT time_slot_id, spill_time_slot_id, reschedule_count, last_reschedule_by FROM gz_recycle_appointment WHERE id=12;
time_slot_id  spill_time_slot_id  reschedule_count  last_reschedule_by
4             9                   1                 gz_owner
# time_slot_id=T2=4、spill_time_slot_id=T3=9（T2 的下一 enabled 档）—— 完全符合 AC14

# AC15：改到最后一个 enabled 档（id=9）-> spill 显式置 NULL
$ curl -X POST /system/gz/recycle/appointment/12/reschedule -d '{"apptDate":"2026-09-10","timeSlotId":9}'
{"code":200,"data":{"timeSlotId":"9","spillTimeSlotId":null,"rescheduleCount":2}}
$ SELECT spill_time_slot_id IS NULL FROM gz_recycle_appointment WHERE id=12;
1   # 真 NULL，非残留旧值

# AC16：confirmed_onsite 单改期 -> 4128，且单据不变
$ curl -X POST /system/gz/recycle/appointment/12/verify -d '{"appointmentId":12,"verifyImageIds":[1],"finalAmountCent":1000}'
{"code":200,"data":{"status":"confirmed_onsite",...}}
$ curl -X POST /system/gz/recycle/appointment/12/reschedule -d '{"apptDate":"2026-09-14","timeSlotId":2}'
{"code":4128,"msg":"该预约当前状态不可改期","data":null}
$ SELECT status, appt_date, time_slot_id, reschedule_count FROM gz_recycle_appointment WHERE id=12;
confirmed_onsite  2026-09-13  9  4   # 未被 4128 请求污染

# AC17：核销码改期后仍有效
$ curl -X POST /app/gz/recycle/appointment/submit -d '{...,"apptDate":"2026-09-15","timeSlotId":2}'
{"code":200,"data":{"id":"13",...}}
$ curl GET /app/gz/recycle/appointment/13/verify-code
{"data":{"qrPayload":"RC|RCY-20260815-000006|13|1786845703|ee86493f...","expireEpochSec":1786845703}}
$ curl -X POST /system/gz/recycle/appointment/13/reschedule -d '{"apptDate":"2026-09-16","timeSlotId":9}'
{"code":200,"data":{"apptDate":"2026-09-16","timeSlotId":"9"}}
$ curl -X POST /app/gz/recycle/staff/verify-scan -d '{"qrPayload":"RC|RCY-20260815-000006|13|1786845703|ee86493f..."}'  # 改期前的旧码
{"code":200,"data":{"id":"13","appointmentNo":"RCY-20260815-000006","apptDate":"2026-09-16","timeSlotId":"9",...}}
# 旧码定位到改期后的单，未报 4104/4112

# AC18：并发改期同一目标格（真 DB 双线程）
$ curl -X POST manual-hold -d '{"storeId":2,"apptDate":"2026-09-21","timeSlotIds":[2],"remark":"AC18-X2"}'  # id=16
$ curl -X POST manual-hold -d '{"storeId":2,"apptDate":"2026-09-21","timeSlotIds":[4],"remark":"AC18-Y2"}'  # id=17
$ (curl -X POST /system/gz/recycle/appointment/16/reschedule -d '{"apptDate":"2026-09-21","timeSlotId":9}' & \
   sleep 0.03; \
   curl -X POST /system/gz/recycle/appointment/17/reschedule -d '{"apptDate":"2026-09-21","timeSlotId":9}' & wait)
X2 result: {"code":200,"data":{"id":"16","timeSlotId":"9","status":"manual_hold",...}}
Y2 result: {"code":4122,"msg":"该时段已被预约，请换个时段","data":null}
# 只有一条成功（X2=200），另一条 4122（Y2）——真 DB 双线程 FOR UPDATE + Redis 锁验证通过
```

> 注：第一次未加 30ms 交错的完全同时并发测试中，落败方偶发拿到 `4126 SLOT_LOCK_BUSY`（Redis 锁竞争，两请求几乎同一时刻抢同一把锁）而非 4122——这也是「只有一条成功、另一条被拒」的正确序列化结果，只是失败码不同（锁竞争 vs 容量竞争）。加 30ms 交错后稳定复现 AC18 要求的 4122。两种结果都证明系统不会双写同一格，非 bug。

### ⑦ AC19-AC23 — 隔离性（真库）

```
# AC19：连建 5 条手动占用全部成功
$ for D in 09-22 09-23 09-24 09-25 09-26; do curl -X POST manual-hold -d "{...date=2026-$D...}"; done
date=2026-09-22 code=200
date=2026-09-23 code=200
date=2026-09-24 code=200
date=2026-09-25 code=200
date=2026-09-26 code=200
# 真实顾客（user 13，已有 1 张进行中单）再次提交仍被 4127 挡
$ curl -X POST /app/gz/recycle/appointment/submit -d '{...}'
{"code":4127,"msg":"您已有进行中的回收预约，完成或取消后再约","data":null}

# AC20：手动占用挡 mp 下单（真 DB 连续两步）
$ curl -X POST manual-hold -d '{"storeId":2,"apptDate":"2026-09-28","timeSlotIds":[2],"remark":"AC20"}'
{"code":200,...}
$ curl GET slot-availability?storeId=2&date=2026-09-28
[{"id":"2","taken":true},{"id":"4","taken":false},{"id":"9","taken":false}]
$ curl -X POST /app/gz/recycle/appointment/submit -d '{...date=2026-09-28,timeSlotId=2...}'
{"code":4122,"msg":"该时段已被预约，请换个时段","data":null}

# AC21①：admin verify 手动记录 -> 4105
$ curl -X POST /system/gz/recycle/appointment/23/verify -d '{"appointmentId":23,"verifyImageIds":[1],"finalAmountCent":1000}'
{"code":4105,"msg":"该预约单当前状态不可核对（可能已确认 / 已取消 / 已过期）","data":null}
$ SELECT status FROM gz_recycle_appointment WHERE id=23;  -> manual_hold（未被推进）

# AC21②：selectSyncablePayoutIds 真实 SQL 对活库
$ SELECT id FROM gz_recycle_appointment WHERE status IN ('paying','payout_failed') AND out_payout_no IS NOT NULL AND del_flag='0';
(empty)
$ SELECT COUNT(*) FROM gz_recycle_appointment WHERE source='manual' AND status IN ('paying','payout_failed');
0

# AC21③：markExpiredNoShow 真实 SQL 对活库（backdate 手动记录到昨天）
$ UPDATE gz_recycle_appointment SET appt_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY) WHERE id=22;
$ SELECT id FROM gz_recycle_appointment WHERE status = 'submitted' AND appt_date < CURDATE() AND del_flag = '0';
1
2
3
4
5
# id=22（manual_hold，已 backdate）未出现在结果里；旧 submitted 单（id 1-5）正常命中
$ SELECT status FROM gz_recycle_appointment WHERE id=22;  -> manual_hold（未被扫到/标记）

# AC22：admin 记录列表默认排除手动记录，仅 status=manual_hold 时显示
$ curl GET /system/gz/recycle/appointment/list?pageNum=1&pageSize=5
total=7  sources={'mp'}
$ curl GET /system/gz/recycle/appointment/list?pageNum=1&pageSize=50&status=manual_hold
total=13  sources={'manual'}  statuses={'manual_hold'}

# AC23：mp 店员当日列表排除手动记录
$ curl GET /app/gz/recycle/staff/appointments?date=2026-09-01
count=0  sources=set()
# DB 该日实际有 2 条 manual_hold（id 8/9）+ 1 条 cancelled（id 7），无 mp 记录 -> 过滤生效，count 正确为 0
```

### ⑧ AC24-AC26 — 周看板（真库）

```
$ curl GET /system/gz/recycle/appointment/week-board?storeId=2&weekStart=2026-09-02   # 周三
{
  "storeId": "2",
  "weekStart": "2026-08-31",   # 归一到周一
  "weekEnd": "2026-09-06",     # 周一起 7 天
  "slots": [{"id":"2","label":"上午",...},{"id":"4","label":"下午",...},{"id":"9","label":"晚上",...}],
  "cells": [
    {"apptDate":"2026-09-01","timeSlotId":"4","kind":"manual","appointmentId":"8",...},
    {"apptDate":"2026-09-01","timeSlotId":"9","kind":"manual","appointmentId":"9",...},
    {"apptDate":"2026-09-02","timeSlotId":"4","kind":"manual","appointmentId":"10",...}
  ]
}
# 已释放的 id=7（2026-09-01/slot2/cancelled）正确不出现在 cells 里（只返被占格）

# spill 格验证：造一张周内大单（date=2026-09-03,slot=2,pts-200-plus）后再查
$ curl GET week-board?storeId=2&weekStart=2026-09-02
cells 含：
{"apptDate":"2026-09-03","timeSlotId":"2","kind":"customer","appointmentId":"24",...}
{"apptDate":"2026-09-03","timeSlotId":"4","kind":"spill","appointmentId":"24",...}   # 溢出格指向源单 24，非自身
```

`selectWeekBoard` 实现为一条 `appt_date BETWEEN weekStart AND weekEnd` 的 MyBatis-Plus `selectList`，未按 7×N 档循环单查（AC26，代码走查确认）。

---

## 已知 issue / 风险提示

1. **AC18 并发测试的失败码是时序敏感的**：完全同时并发时落败方可能拿到 4126（Redis 锁竞争）而非 4122（容量竞争），两者都正确防止双写，但 ADR 字面写的是 4122——若 kevin-qa 复测拿到 4126 请不要判 FAIL，属正常时序变体（已在报告 ⑥ 段注明）。
2. **本次实测在 admin `verify` 端点上顺带发现一个既有小 bug**（非本 ticket 引入、未修复）：`GzRecycleAppointmentController.verify()` 的 `@Valid` 校验发生在 `bo.setAppointmentId(id)` 赋值**之前**，导致请求体不显式带 `appointmentId` 时会被 `@NotNull` 拦成「预约单 id 不能为空」（500），必须在 body 里重复传 `appointmentId`（与 path `{id}` 一致）才能通过。这是 GZ-RECYCLE-003 遗留代码，不在本 ticket 范围内，未改动；kevin-qa 或后续 ticket 若测 `/verify` 端点需注意此约束。
3. 测试期间在 dev 库内产生了大量测试数据（id 6-24+，日期集中在 2026-09 区间），均为回收域数据、与预置 5 条真实种子数据（id 1-5，2026-07 区间）不冲突，未清理（dev 库，不影响功能，供 kevin-qa 复用/自行清理）。

---

## ADR 已读

doc/_adr/0021-recycle-manual-slot-hold-and-reschedule.md 全文已读，§1/§2 决策 + 11 条关键实现坑位逐条对照见上表，无遗漏。

## 对下游 ticket 的提示

- GZ-RECYCLE-011（依赖本卡）可直接消费：`manualHold` / `releaseHold` / `reschedule` / `selectWeekBoard` 四个 service 方法 + 对应 admin 端点均已就绪；`GzRecycleWeekBoardVO` 契约（`slots`/`cells`/`kind`）已定稿，admin 前端周视图可直接对接。
- admin `GzRecycleAppointmentAdminVO` 新增字段 `source` / `timeSlotId` / `spillTimeSlotId` / `rescheduleCount`，前端「已改期 N 次」展示可直接读 `rescheduleCount`。

---

## §AI 测试段（Tier 1B，kevin-qa 独立复测，未采信 kevin-coder 自述）

**日期**：2026-08-15　**backend**：复用同一进程（PID 97160，8080），全程未重启。

**方法论**：不复用 kevin-coder 报告中的任何 raw output；全部 28 条 AC 用**全新测试数据**（日期段 `2026-10-*`，与 coder 用的 `2026-09-*` 完全不重叠）重新跑一遍真库 curl + SQL。额外做了一遍源码走查（controller / service / mapper / BO / migration SQL 逐行读，非仅 grep）核对 AC5-7/AC12/AC13/AC26 的实现是否与注释/报告所述一致。

**测试身份准备**（dev mock 登录固定 openid，只能拿到 2 个稳定 mp 客户身份 + 1 个 admin 身份，过程记录以备后续复测参考）：
- admin：`gz_owner` / clientId `e5cd7e4891bf95d1d19206ce24a7b32e`
- mp 客户 A：clientid `mp-applet-sensenran-guzi`（固定 mock openid，解出 `gz_user.id=13`，历史遗留 1 张 `submitted` 单 id=24，复用做 AC17 测试对象，未新建）
- mp 客户 B（全新）：clientid `mp-applet-gz-jp`（拼团小程序另一路 mock 通道，固定 openid 与 A 不同，解出全新 `gz_user.id=14`）+ mock `bind-mobile` 拿到 13800000000，用作 AC14/15/16/19/20 的「零历史真实顾客」
- mp 店员：临时 `UPDATE gz_user SET staff_user_id=101 WHERE id=13` 装载店员权限重新登录测 AC17 verify-scan / AC23，测完立即 `UPDATE ... SET staff_user_id=NULL` 复原（已核对复原生效）

### A. 迁移/字典/权限（AC1-4，真库重新查询）

```
$ DESC gz_recycle_appointment | grep -E "^(source|user_id|receiver_openid|product_snapshot_json|reschedule_count|last_reschedule_by|last_reschedule_time)"
user_id                 bigint unsigned   YES   NULL
product_snapshot_json   json              YES   NULL
receiver_openid         varchar(64)       YES   NULL
source                  varchar(16)       NO    mp
reschedule_count        int               NO    0
last_reschedule_by      varchar(64)       YES   NULL
last_reschedule_time    datetime(3)       YES   NULL

$ SELECT installed_rank, version, description, success FROM flyway_schema_history WHERE description LIKE '%GZ-RECYCLE-010%';
164  202608150950  GZ-RECYCLE-010-appointment-manual-hold  1
165  202608150951  GZ-RECYCLE-010-menu-dict                1

$ SELECT dict_code, dict_label, dict_value FROM sys_dict_data WHERE dict_type='gz_recycle_status' AND dict_value='manual_hold';
9264  手动占用  manual_hold

$ SELECT menu_id, menu_name, parent_id, menu_type, visible, perms FROM sys_menu WHERE menu_id IN (13015,13016);
13015  手动占用/释放  13002  F  0  gz:recycle:appointment:hold
13016  预约改期        13002  F  0  gz:recycle:appointment:reschedule

$ SELECT menu_id, role_id FROM sys_role_menu WHERE menu_id IN (13015,13016,13021) ORDER BY menu_id, role_id;
13015 100 / 13015 101 / 13015 103 / 13016 100 / 13016 101 / 13016 103 / 13021 100 / 13021 101 / 13021 103
```
grep 全部历史迁移确认 13015/13016 无撞号。AC1-4 ✅。

### B. 状态集/公共方法（AC5-7，逐行源码走查非仅 grep）

直接读 `GzRecycleAppointmentServiceImpl.java` 全文 + `GzRecycleAppointmentMapper.java` 全文（非 grep 摘要）：
- `ACTIVE_HOLD_STATUSES = List.of("submitted","confirmed_onsite","paying","paid","payout_failed","manual_hold")`（6 个）与 `countActiveHoldingSlotForUpdate` / `countActiveHoldingSlotExcludingForUpdate` 两个 `@Select` 内联字面量逐字比对完全一致 ✅
- `USER_ACTIVE_STATUSES = List.of("submitted","confirmed_onsite","paying","payout_failed")` 不含 `manual_hold`，`countActiveByUserForUpdate` 内联同步不含 ✅
- `resolveSlotAndAssertCapacity` 私有方法，3 处调用点：`submit()` L218 / `manualHold()` L760 / `reschedule()` L844；`submit()` 内旧内联校验代码已删除，无重复逻辑 ✅

### C. 手动占用/释放（AC8-11，真库，全新日期 2026-10-01~03）

```
# AC8 happy：store=2 date=2026-10-01 timeSlotIds=[2,4,9] remark="QA-AC8-happy"
POST manual-hold → 200，id=25/26/27 全部 source=manual status=manual_hold user_id/receiver_openid/product_snapshot_json 均 NULL

# AC9 all-or-nothing：先占 slot4（date=2026-10-02，id=28），再提交 [2,4,9]
POST manual-hold [2,4,9] → {"code":4122,...}
SELECT id,time_slot_id FROM gz_recycle_appointment WHERE store_id=2 AND appt_date='2026-10-02';
→ 只剩 id=28（slot4），批量插入的 slot2 那一行随事务回滚未残留 ✅

# AC10 校验（date=2026-10-03，全部 0 残留）
remark="   " → {"code":500,"msg":"请填写占用备注"}
timeSlotIds=[] → {"code":500,"msg":"请至少选择一个时段"}
timeSlotIds=[99999]（不存在）→ {"code":4124,...}
timeSlotIds=[1]（属 store1，传给 store2）→ {"code":4124,...}
SELECT COUNT(*) WHERE appt_date='2026-10-03' → 0

# AC11：release id=25 → 200 status=cancelled cancelled_time 非空；
slot-availability?date=2026-10-01 → slot2 taken=false（slot4/9 仍 true）
release id=1（source=mp 顾客单）→ {"code":4129,...}
release id=25 再次（已 cancelled）→ {"code":4129,...}
```
AC8-11 ✅。

### D. 改期（AC12-18，真库，全新数据）

**AC12**（源码读）：`countActiveHoldingSlotExcludingForUpdate` 与原版逐字一致 + `AND id <> #{excludeId}` + `FOR UPDATE`，改期路径 3 处调用（`resolveSlotAndAssertCapacity` 内部按 `excludeId` 是否为 null 切换）全部走该变体 ✅。

**AC14（排除自身）**：mp 客户 B（gz_user id=14，零历史）提交大单 store=2 date=2026-10-05 slot=2(T1) `pts-200-plus` → id=31，`time_slot_id=2 spill_time_slot_id=4`。改期到 T2(slot4，自己 spill 占着的档)：
```
POST /system/gz/recycle/appointment/31/reschedule {"apptDate":"2026-10-05","timeSlotId":4}
→ 200，timeSlotId=4 spillTimeSlotId=9 rescheduleCount=1
SELECT ... WHERE id=31 → appointment_no/user_id/product_snapshot_json/matched_duration_minutes 全部不变，version 0→1
```
未被自己的旧占用挡回 4122/4123 ✅（AC13 字段不变性同时验证：id/appointment_no/user_id/product_snapshot_json/matched_duration_minutes 逐一核对不变）。

**AC15（spill 显式置 NULL）**：同一单再改期到本店最后一档（slot9）：
```
→ 200，timeSlotId=9 spillTimeSlotId=null
SELECT spill_time_slot_id IS NULL FROM ... WHERE id=31 → 1（真 NULL）
```

**AC16（状态守卫）**：先 admin verify id=31（`verifyImageIds:[1]`）→ 200 status=confirmed_onsite（**注**：第一次误传 `verifyImageIds:[]` 被 `@NotEmpty` 拒绝 500「请先拍照存证再确认」，此时单据仍是 submitted；已发现并用非空数组重试，过程记录留痕以示未跳过失败重试）。confirmed_onsite 后再次 reschedule：
```
POST .../31/reschedule {"apptDate":"2026-10-13","timeSlotId":2}
→ {"code":4128,"msg":"该预约当前状态不可改期"}
SELECT status,appt_date,time_slot_id,reschedule_count,version WHERE id=31
→ confirmed_onsite / 2026-10-12 / 2 / 3 / 4（与请求前完全一致，未被 4128 请求污染）
```

**AC17（核销码改期后仍有效）**：复用既存顾客单 id=24（user_id=13，status=submitted，未新建）。
```
GET /app/gz/recycle/appointment/24/verify-code（mp 客户 A 会话）
→ qrPayload="RC|RCY-20260815-000017|24|1786846801|3a59ea9d..."
POST admin /24/reschedule {"apptDate":"2026-10-15","timeSlotId":9} → 200
POST /app/gz/recycle/staff/verify-scan（临时店员会话）用上面的旧 payload
→ 200，返回 apptDate=2026-10-15 timeSlotId=9（改期后的新值），未报 4104/4112
```

**AC18（并发，双线程真实竞态，两种时序变体都复现）**：
```
# 变体 1：完全同时（无交错）→ 锁竞争
新建 manual-hold id=37(slot2)/id=38(slot4)，date=2026-10-25
两线程同时 reschedule 37→slot9 / 38→slot9：
  37 → {"code":4126,"msg":"预约繁忙，请稍后重试"}
  38 → {"code":200,...timeSlotId=9}
DB 终态：37 仍 slot2，38→slot9，无双写 ✅

# 变体 2：30ms 交错 → 容量竞争
新建 id=39(slot2)/id=40(slot4)，date=2026-10-26，40 号请求延后 30ms 发起
  39（先发）→ {"code":200,...timeSlotId=9}
  40（+30ms）→ {"code":4122,"msg":"该时段已被预约，请换个时段"}
DB 终态：39→slot9，40 仍 slot4，无双写 ✅
```
两种时序下均只有一条改期成功、另一条被正确拒绝，与 kevin-coder 报告标注的「4126/4122 均为正确序列化结果」一致，本轮独立复现两种变体。

### E. 隔离性（AC19-23，真库，全新数据）

**AC19**：
```
# 5 条全新手动占用（date 2026-10-07~11，各不同日期避免与其它 AC 冲突）→ 全部 200
# mp 客户 B（id=14，此前已用于 AC14 提交大单，此时是「有 1 张进行中单」的真实顾客）
再次 submit（新 date/slot）→ {"code":4127,"msg":"您已有进行中的回收预约..."}
```
关键点：客户 B 的**首次**大单提交（AC14 setup）恰好发生在 5 条手动占用 + AC8/9/10/11 等更早的手动占用记录已存在于库中之后，直接证明「手动占用不消耗/不污染真实顾客的一人一单额度」；随后同一顾客的第二次提交仍正确 4127，证明守卫本身未被手动占用破坏。

**AC20**：
```
manual-hold store=2 date=2026-10-20 slot=2 → 200
GET slot-availability?storeId=2&date=2026-10-20 → slot2 taken=true
mp 客户 B（此时仍零历史，尚未提交 AC14 大单）submit 同店同日同 slot2
→ {"code":4122,...}
提交失败后确认 gz_user.id=14 名下 0 条预约（未误建行）
```

**AC21**：
```
① admin verify 手动记录 id=41 → {"code":4105,...}，SELECT status → 仍 manual_hold
② SELECT id FROM gz_recycle_appointment WHERE id=41 AND status IN ('paying','payout_failed') AND out_payout_no IS NOT NULL AND del_flag='0' → 空
③ UPDATE gz_recycle_appointment SET appt_date=DATE_SUB(CURDATE(),INTERVAL 1 DAY) WHERE id=41；
   SELECT id FROM ... WHERE status='submitted' AND appt_date<CURDATE() AND del_flag='0' → [1,2,3,4,5]（id=41 不在内）
   SELECT status WHERE id=41 → manual_hold（未被 no_show 扫描逻辑命中）
```

**AC22**：
```
SELECT source, COUNT(*) FROM gz_recycle_appointment GROUP BY source; → mp=9, manual=29
GET /list?pageNum=1&pageSize=100（默认）→ total=9，sources_on_page={mp}，manual_present=False
GET /list?pageNum=1&pageSize=100&status=manual_hold → total=27，sources={manual}，statuses={manual_hold}
（29-27=2 为已 release 的手动记录，含本轮 id=25 与 coder 此前 release 的 id=7，口径自洽）
```

**AC23**：
```
临时店员会话 GET /app/gz/recycle/staff/appointments?date=2026-10-01
→ []（该日实际有 2 条 manual_hold + 1 条 cancelled，无 mp 记录，过滤生效）
sanity check：同一店员会话 GET ...?date=2026-10-15（该日有 1 条真实 mp 记录 id=24）
→ 正确返回该条记录（证明端点本身工作正常，不是「永远返回空」的假阳性）
```

### F. 周看板（AC24-26，真库）

```
# AC24：传周三 2026-10-07 → 归一
GET week-board?storeId=2&weekStart=2026-10-07 → weekStart=2026-10-05（周一）weekEnd=2026-10-11

# AC25：三种 kind 全部live 验证
- 纯 manual：2026-10-05..11 周对应 5 条 manual_hold cell，kind=manual
- customer + spill：week-board?weekStart=2026-10-12 →
    {date:2026-10-12, slot:2, kind:customer, appointmentId:31, status:confirmed_onsite}
    {date:2026-10-12, slot:4, kind:spill,    appointmentId:31, status:confirmed_onsite}  ← spill 指向源单 31，非自身
    {date:2026-10-15, slot:9, kind:customer, appointmentId:24, status:submitted}
- cancelled 记录不泄漏：week-board?weekStart=2026-09-28 的 2026-10-01 只出现 id=26/27（manual_hold），
  已 cancelled 的 id=25（同日 slot2）正确不出现

# AC26（源码读）：selectWeekBoard 一条 `.between(apptDate, monday, sunday)` MyBatis-Plus selectList，
  内存中按 row 分 cell（含 spill 二次落 cell），未见任何按天/档循环二次查询
```

### G. 测试（AC27-28）

```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-recycle -am
...
[INFO] Tests run: 15, ... -- in org.dromara.gz.recycle.service.impl.GzRecycleManualHoldRescheduleTest
[INFO] Tests run: 74, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
`GzRecycleManualHoldRescheduleTest` 15 条用例逐条读过：manualHold（happy / 4122 二档提前终止 / 4124 未启用档 / remark 空白 `@NotBlank` / timeSlotIds 空 `@NotEmpty`）、releaseHold（happy / 顾客单 4129 / 已取消再释放 4129 / 未找到 4104）、reschedule（排除自身成功 / 末档 spill 显式 NULL / 状态非法 4128 / 目标格已占 4122 / 并发 version 漂移 4128 / manual_hold 单不查点数档）—— happy + error path 覆盖齐全，AC27 ✅。AC28 要求的 4 条真库断言（AC9/14/15/18）本轮全部用全新数据独立重跑，raw output 见上，AC28 ✅。

### 结论

**28/28 AC 全部独立验证通过**，未发现任何与 kevin-coder 报告不符或需要打回的问题。过程中定位到我方测试脚本自身的一处误操作（AC16 首次 verify 因 `verifyImageIds` 传空数组被拒），已识别、纠正、重测，不影响功能判定。

kevin-coder 报告中标注的两条非阻塞项复核结论：
1. **AC18 并发失败码时序敏感（4126 vs 4122）**——本轮独立复现两种时序变体，判定为正确的序列化行为，非缺陷，同意报告结论。
2. **`GzRecycleAppointmentController.verify()` 的 `@Valid` 早于 `bo.setAppointmentId(id)` 赋值**——确认是既有代码（非本 ticket 引入），本轮测试全程按「body 显式带 appointmentId」的方式调用规避，未在本 ticket 范围内修复，同意报告结论（建议后续 ticket 顺手修掉，属于低成本高置信度的独立小修）。

**backend 状态**：进程保持运行（PID 97160，8080），供后续 ticket 继续复用；未做任何清理性重启。dev 库新增测试数据（`2026-10-*` 区间 + `gz_user.id=14`）与 coder 的 `2026-09-*` 数据共存，不冲突，未清理（dev 库）。

---

## §对抗性测试闭环（第二轮）— 后端 3 条 finding 鉴定 + 修复

> 两个独立 QA agent 分别对后端 API / 前端 UI 做对抗性测试，共报 6 条 finding。本节处理后端 3 条（F1/F2/F3），前端 3 条（F4/F5/F6）见 [GZ-RECYCLE-011 报告同名章节](GZ-RECYCLE-011.md#对抗性测试闭环第二轮--前端-3-条-finding-鉴定--修复)。

### 一、鉴定结论

| # | severity | 结论 | 理由 |
|---|---|---|---|
| **F1** 改期活查点数档 → 大单 spill 静默丢失（物理双占）| high | **确认是 bug（已修）** | 根因坐实：`reschedule()` 用 `qtyRangeService.getEnabledByCode()` **活查**点数档算 `occupyNext`，而该方法按 `enabled=1` 过滤。「禁用一个点数档」是正常运营动作（下线旧档 / 调时长映射），一旦发生，此后对该档任何既有大单的改期都会把 `occupyNext` 算成 false → `spill_time_slot_id` 被**显式置 NULL** → 溢出格立刻对外放开，与本单实际到店时长物理双占。**占格面属于「提交那一刻定死的事实」，不是「随配置漂移的推导值」** —— 这是建模错误，不是边界输入。dev 库里 `id=68` 就是被这条路径打坏的真实残留行（`matched_duration_minutes=300` 却只锁 1 格）。ADR-0021 坑位 5 只写了「spill 要按新档重算」，没写「重算依据必须是快照」，属蓝图缺口（已补 doc/11 §12.4/§12.7 + ADR 坑位 12）。|
| **F2** 手动占用 `remark` 被全局 XSS 过滤器剥标签 | low | **不是本 ticket 的 bug（不修）** | ① 这是 ruoyi 平台级 `XssFilter` 对**所有**入参字符串的既有行为，非本 ticket 引入；② 客观上是防御性设计（`remark` 会进 admin 看板 / 详情，Vue 默认转义只防渲染，不防被别处以 innerHTML 消费）；③ 要「原样保留」只能把该端点加进 `xss.excludes` 白名单 —— 为一个「备注里写尖括号」的边缘用法放开平台级 XSS 防线，收益/风险严重倒挂；④ 影响面是「店员备注若写 `<张>` 会丢字」，不产生数据损坏 / 资金 / 超卖后果。**判定：既有平台行为，记录在案不改**。若甲方真的反馈备注丢字，正解是前端提示「备注勿用尖括号」，而不是关 XSS 过滤。|
| **F3** 改期不校验目标日期不得早于今天 | low | **确认是 bug（已修，但按记录类型分治）** | 顾客单（`source='mp'`）改到过去确有实害：`markExpiredNoShow` 的 SQL 是 `status='submitted' AND appt_date < CURDATE()`，一次店员手滑（`2026-11-23` 打成 `2025-11-23`）就让顾客的有效预约在下次扫描时被静默判 `no_show`，属输入校验缺口 → **加 `4130` 拦截**。但**手动占用（`manual_hold`）刻意豁免**：它是店员台账，`no_show` cron 不扫它（ADR-0021 §1 表格），历史日期也不影响任何未来格的可用性，而「回填/挪动昨天的占用记录」是真实动线（看板默认展示的本周有 5 天在过去）—— 对它加限制是纯粹的伤害。QA 原始复现用的正是手动占用记录（id=89），故那条 curl 现在仍返 200，**这是设计，不是漏修**。|

### 二、改动文件（后端）

| 文件 | 改动 |
|---|---|
| `ruoyi-gz-recycle/.../domain/vo/GzRecycleProductVO.java` | 新增 `occupyNextSlot`（提交时冻结的占格面快照，落 `product_snapshot_json`，**无 schema 变更 / 无新迁移**）|
| `ruoyi-gz-recycle/.../service/impl/GzRecycleAppointmentServiceImpl.java` | ① `submit()` 写快照 `snapshot.setOccupyNextSlot(occupyNext ? 1 : 0)`；② `reschedule()` 的 `occupyNext` 改走新私有方法 `resolveOccupyNextForReschedule(appt)`（快照 → 忽略 enabled 查档 → `spill_time_slot_id` 非空兜底，三级优先级）；③ `reschedule()` 加顾客单过去日期守卫（`4130`）；④ 改期日志加 `occupyNext=` |
| `ruoyi-gz-recycle/.../service/IGzRecycleQtyRangeService.java` + `impl/GzRecycleQtyRangeServiceImpl.java` | 新增 `getByCodeIgnoringEnabled(code)`（**只给改期兜底用**；提交链路仍必须用 `getEnabledByCode`，禁用档必须 4107）|
| `ruoyi-gz-recycle/.../exception/GzRecycleErrorCode.java` | 新增 `RESCHEDULE_DATE_PAST = 4130` |
| `ruoyi-gz-recycle/src/test/.../GzRecycleManualHoldRescheduleTest.java` | +7 条用例（F1 四条 / F3 三条），并把两条既有 reschedule 用例的桩从 `getEnabledByCode` 改为快照驱动 |
| `ruoyi-gz-recycle/src/test/.../GzRecycleAppointmentServiceImplTest.java` | submit happy / 大单两条断言快照写入 `"occupyNextSlot":0/1` |
| `ruoyi-gz-recycle/src/test/.../GzRecycleQtyRangeServiceImplTest.java` | +2 条（禁用档仍可按 code 取回 / 空 code 不查库）|
| `doc/11-字段权威表.md` §12.4 / §12.7 | 补 `occupyNextSlot` 字段行 + 「占格面取冻结快照」「顾客单不得改到过去」两条口径 + `4130` + admin 前端 4 条配套约束 |
| `doc/_adr/0021-...md` §2 约束 2 / 错误码表 / 坑位 12-13 | 同步（坑位清单是实施者必读，缺口补在源头）|

**无迁移**：占格面快照落在既有 `product_snapshot_json`（JSON 列），错误码是 Java 常量 —— 本轮零 DDL、零 `V*.sql` 新增，符合「不加不必要的迁移」。

### 三、逐条修复验证（真库 + 真接口，改后已 `mvn clean install` + 重启 8080）

#### F1-① 旧单（无快照）+ 点数档被禁用 → spill 仍保住（正是 QA 的原始复现路径）

```bash
# 1) 禁用点数档 pts-200-plus（id=8，occupy_next_slot=1）—— QA 复现的第 2 步
$ curl -X POST 'http://localhost:8080/system/gz/recycle/qtyRange/toggle/8?enabled=0' ...
{"code":200,"msg":"操作成功","data":null}
mysql> SELECT id,code,enabled,occupy_next_slot FROM gz_recycle_qty_range WHERE id=8;
8  pts-200-plus  0  1        ← 档已禁用

# 2) 对 QA 留下的证据行 id=68（快照里没有 occupyNextSlot，是修复前提交的旧单）改期 slot4 → slot2
$ curl -X POST http://localhost:8080/system/gz/recycle/appointment/68/reschedule -d '{"apptDate":"2026-11-23","timeSlotId":2}'
"timeSlotId": "2", "spillTimeSlotId": "4", "matchedDurationMinutes": 300   ← 修复前这里是 null

mysql> SELECT id,time_slot_id,spill_time_slot_id,matched_duration_minutes,reschedule_count FROM gz_recycle_appointment WHERE id=68;
68  2  4  300  2

# 3) 溢出格对外不可约（看板视角）
$ curl '.../week-board?storeId=2&weekStart=2026-11-23'
cells 2026-11-23: [('2','customer','68'), ('4','spill','68')]      ← 4 号格被标为 68 的溢出占用

# 4) 再改回 slot4 → spill 必须重算成 9（不残留 2、不置 NULL）
timeSlotId=4 spillTimeSlotId=9 rescheduleCount=3
mysql> 68  4  9
```

#### F1-② 新单：提交即冻结占格面，之后禁用点数档也不影响改期

```bash
# 提交一张全新大单（store 1 / 2026-11-25 / 上午 slot=1 / pts-200-plus）
$ curl -X POST http://localhost:8080/app/gz/recycle/appointment/submit ...
"id":"91", "product": { "qtyBucketCode":"pts-200-plus", "occupyNextSlot": 1 }   ← 快照冻结

mysql> SELECT id,time_slot_id,spill_time_slot_id,product_snapshot_json FROM gz_recycle_appointment WHERE id=91\G
time_slot_id: 1   spill_time_slot_id: 3
product_snapshot_json: {..., "qtyBucketCode": "pts-200-plus", "occupyNextSlot": 1, "qtyBucketLabel": "200 点以上"}

# 提交后禁用该点数档 → 改期 slot1 → slot3
$ curl -X POST '.../qtyRange/toggle/8?enabled=0'  → 200
$ curl -X POST '.../appointment/91/reschedule' -d '{"apptDate":"2026-11-25","timeSlotId":3}'
code=200 timeSlotId=3 spillTimeSlotId=8 matchedDurationMinutes=300     ← 溢出格按新档重算，未丢

# mp 侧可用性：本档 + 溢出档都不可约（这正是「不双占」的对外表现）
$ curl '.../app/gz/recycle/appointment/slot-availability?storeId=1&date=2026-11-25'
[('1','上午',False), ('3','下午',True), ('8','晚上',True)]
```

#### F3 顾客单不得改到过去 / 手动占用豁免

```bash
# 顾客单（id=91, source=mp）→ 2020-01-01
{"code":4130,"msg":"顾客预约不能改到已过去的日期，请选择今天或之后的日期","data":null}
mysql> 91  2026-11-25  3  8  1      ← 库未被改动（appt_date / slot / spill / reschedule_count 全不变）

# 顾客单 → 昨天（边界）
{"code":4130,"msg":"顾客预约不能改到已过去的日期，请选择今天或之后的日期","data":null}

# 手动占用（id=89, source=manual）→ 2020-01-02：刻意放行
code=200 source=manual apptDate=2020-01-02 status=manual_hold
```

#### 单测（含 F1/F3 新增 9 条）

```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-recycle
[INFO] Tests run: 22, ... -- in o.d.gz.recycle.service.impl.GzRecycleManualHoldRescheduleTest   (15 → 22)
[INFO] Tests run: 14, ... -- in o.d.gz.recycle.service.impl.GzRecycleAppointmentServiceImplTest
[INFO] Tests run:  6, ... -- in o.d.gz.recycle.service.impl.GzRecycleQtyRangeServiceImplTest    ( 4 →  6)
[INFO] Tests run: 83, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

新增用例（逐条对应 finding 的失效面，不是凑数）：
- F1：`点数档被禁用 → 改期仍按快照 occupyNextSlot=1 重算 spill`（并断言**根本不查**点数档表）/ `快照=0 的普通单不占下一档` / `旧单无快照 → 走忽略 enabled 查档`（并断言 `never getEnabledByCode`）/ `旧单 + 档已删 → 靠自身 spill 非空保持两格`
- F3：`顾客单改到昨天 → 4130 且不触碰锁/容量/UPDATE` / `顾客单改到今天 → 放行（边界不是 before today）` / `手动占用改到过去 → 放行`

### 四、环境与数据现场

- 后端已 `mvn clean install -DskipTests -pl ruoyi-modules/ruoyi-gz-recycle -am` 后重启，**保持运行**（8080）；plus-ui dev server 保持运行（8090）。
- 验证用数据已复位：`gz_recycle_qty_range.id=8` 回 `enabled=1`；为绕开一人一单守卫临时改成 `paid` 的 `id=31` 已还原 `confirmed_onsite`；本轮新建的 `id=91` 已硬删。
- **QA 留下的两条证据行保留**：`id=68`（原被打坏的大单，本轮改期后已自愈为 `slot4 + spill9`）、`id=89`（过去日期的手动占用，现 `2020-01-02`）。
