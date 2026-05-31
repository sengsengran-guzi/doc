# GZ-BEAN-009 完工报告 — no_show 自动标记 cron（凌晨 2 点）

> 实施：kevin-coder（后台 agent）+ 主线程收口（单测补写 + 构建验证 + 本报告）
> 日期：2026-06-02（D05）
> 状态：Tier 1A ✅ / Tier 1B 单测 ✅ / 纯后端 ticket，无人验

---

## §0 状态自检（实施前）

| 检查项 | 结论 |
|---|---|
| git 状态 | 项目当前非 git repo（`git rev-parse` fail）→ 跳过 git 步骤，本日不 commit |
| 上游 GZ-BEAN-004 | ✅ 已 merge：`gz_bean_booking` / `gz_bean_booking_log` 表 + entity + mapper + service（submit/verify/cancel）全在 |
| 调度框架硬检查 | 🔴 **卡里假设 Quartz `sys_job` 错误**：工程实为 **SnailJob（com.aizuda）**，`ruoyi-common-job` 依赖 `snail-job-client-starter`；样例在 `ruoyi-modules/ruoyi-job/.../snailjob/`。baseline 无 `sys_job`/`sj_*` 表 → job 注册走 SnailJob 控制台，不走 Flyway |
| gz-bean pom 可见性 | gz-bean 原只依赖 gz-common（不透传 `ruoyi-common-job`）→ 需显式加 `ruoyi-common-job` 依赖才能 import SnailJob 执行器类 |
| no_show 时间列名 | DDL `V202606011200` 实列名 `no_show_time`（非卡里写的 `no_show_marked_time`） |
| 编译健康 | `mvn install -pl ruoyi-modules/ruoyi-gz-bean -am -DskipTests` exit=0 |

---

## §N 完工总结

### 改了哪些文件

| 文件 | 改动 |
|---|---|
| `ruoyi-modules/ruoyi-gz-bean/pom.xml` | 加 `org.dromara:ruoyi-common-job` 依赖（已存在的内部模块，非外部新依赖，不触 CLAUDE.md §6#8） |
| `.../gz/bean/job/GzBeanNoShowMarkJob.java` | **新建** SnailJob 注解式执行器 `@JobExecutor(name="gzBeanNoShowMarkTask")`；委托 service，回写统计到执行结果；`failed>0` 或异常 → `ExecuteResult.failure` 触发告警，不吞 |
| `.../gz/bean/service/IGzBeanBookingService.java` | 加 `markNoShowBatch()` + `record NoShowMarkResult(int scanned, marked, skipped, failed)` |
| `.../gz/bean/service/impl/GzBeanBookingServiceImpl.java` | 加常量 `STATUS_NO_SHOW`/`OPERATOR_SYSTEM`；`markNoShowBatch()`（`TenantHelper.ignore` 全租户扫 + 逐条 + 单条异常隔离 + 统计）；`protected markOneNoShow()`（条件 UPDATE，affected==1 才写 booking_log） |
| `.../gz/bean/mapper/GzBeanBookingMapper.java` | 加 `selectExpiredPendingIds()`（`status='pending' AND sess_date<CURDATE() AND del_flag='0'`）+ `markNoShow(id, noShowTime)`（条件 UPDATE，`WHERE status='pending'` 守卫，天然原子幂等，dedup_token 切 booking_no 释放占位） |
| `.../test/.../GzBeanBookingServiceImplTest.java` | 加 4 个 markNoShowBatch 单测 + import `IGzBeanBookingService` |

### 关键设计：幂等 = 条件 UPDATE（非 SELECT FOR UPDATE）

卡里写 "SELECT FOR UPDATE"，实际采用更稳的 **条件 UPDATE**：

```sql
UPDATE gz_bean_booking
SET status = 'no_show', no_show_time = #{noShowTime}, dedup_token = booking_no
WHERE id = #{id} AND status = 'pending' AND del_flag = '0'
```

`WHERE status='pending'` 守卫使 UPDATE 天然原子 + 幂等（AC 5）：affected=1 = 本次标记成功；affected=0 = 已被并发/上轮 cron 改态 → service 计入 `skipped` 不写 log。无需悲观锁，避免锁表。

### Tier 1A 自测 raw output

**① install + 编译（pom 改动验证）**

```
$ mvn -q install -DskipTests -pl ruoyi-modules/ruoyi-gz-bean -am
===STEP1_EXIT=0===
```

**② 单测（11 tests，含 4 新增 BEAN-009）**

```
Tests run: 11, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.832 s -- in org.dromara.gz.bean.service.impl.GzBeanBookingServiceImplTest
Tests run: 14, Failures: 0, Errors: 0, Skipped: 0 -- in GzBeanStoreServiceImplTest
Tests run: 12, Failures: 0, Errors: 0, Skipped: 0 -- in GzBeanSeatServiceImplTest
Tests run: 10, Failures: 0, Errors: 0, Skipped: 0 -- in GzBeanTimeSlotTemplateServiceImplTest
Tests run:  7, Failures: 0, Errors: 0, Skipped: 0 -- in QrCodeSignerTest
```

**③ 异常隔离行为（single_failure 用例运行日志 — 故意抛 RuntimeException 被 catch，整批不中断）**

```
[bean-noshow] mark no_show FAILED bookingId=302, continue next  (java.lang.RuntimeException: DB 写超时（模拟）)
[bean-noshow] done. scanned=3 marked=2 skipped=0 failed=1
[bean-noshow] booking id=202 already non-pending, skip (idempotent)
[bean-noshow] done. scanned=2 marked=1 skipped=1 failed=0
```

4 个新增用例覆盖：AC6 主场景（2 标记+2 log）/ 幂等跳过（affected=0 不写 log）/ 单条异常隔离（整批不断）/ 空扫描（全 0 不触 mapper）。

### 🔴 SnailJob 控制台注册（ops 步骤，非代码 — Kevin / 运维执行一次）

baseline 无 `sys_job`/`sj_*` 表，job **不通过 Flyway DDL 注册**。需在 SnailJob 服务端控制台「定时任务」菜单手动建：

| 配置项 | 值 |
|---|---|
| 任务名称 | GZ-BEAN-NO-SHOW-MARK |
| 执行器路由（executor_info） | `gzBeanNoShowMarkTask`（= `@JobExecutor(name)`） |
| 触发类型 / 表达式 | CRON / `0 0 2 * * ?`（每日 02:00，容器时区 Asia/Shanghai） |
| 阻塞策略 | 丢弃（上次未完不叠加） |
| 组 | `ruoyi_group` |

注册后可在控制台点「执行一次」手动触发验证（见 testing-human.md）。

### 已知 issue / 风险

- SnailJob server 未起时，job 不会自动触发，但 `markNoShowBatch()` 逻辑已被单测覆盖；真机触发依赖控制台注册 + server 在线。
- Flyway 未接入（D05 BEAN-010 agent 同步发现）：与本 ticket 无关（本 ticket 无 DDL），但影响整体库初始化，主线程在日终统一核。

### 对下游提示

- 本 ticket 在 `GzBeanBookingServiceImpl` 加了 `markNoShowBatch`/`markOneNoShow` + 2 个常量 + mapper 2 方法 → **BEAN-005（VO/detail）/ BEAN-008（verifyByQrPayload）接着改同一 impl 文件时已包含这些改动**（主线程已串行化：009→005→008）。
- `no_show` 状态在 `gz_bean_booking_status` 字典需有编码（BEAN-006 列表 tab / BEAN-008 筛选共用）—— 列表渲染用 BizTag 灰款（doc/10 §3 裁定）。

### kevin-qa Tier 1B

本会话后台 agent 无 spawn kevin-qa 能力，单测（Tier 1B 机械部分）由主线程跑通验证（11/11）。纯后端 ticket，无 admin E2E / mp 真机，**AI ✅ 即终态，无人验**（CLAUDE.md §8.2 例外）。
