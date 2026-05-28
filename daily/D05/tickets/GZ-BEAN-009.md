# GZ-BEAN-009 — no_show 自动标记 cron（凌晨 2 点）

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M4 §异常分支 + §业务规则
**关联拆解**: doc/02-需求拆解.md §2.3 第 400 行
**关联 mockup**: — （后台 cron 无 UI）
**关联 ADR**: —
**依赖**: GZ-BEAN-004 ✅(D04)

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md **§3 拼豆预约全流程** §状态机 pending → no_show + §关键节点 N13（凌晨 2 点定时任务） + §异常分支 E9 / E10（任务失败告警，幂等可重跑）
- **字段表**：doc/11-字段权威表.md **§3.4 `gz_bean_booking`**（status / no_show_marked_time 字段） + §3.5 `gz_bean_booking_log`（标 no_show 写一条 log） + **doc/11 §10.3 sensenran 新增 sys_job 注册位**（cron job 配置规约）
- **UI 参考**：无（cron 任务，ruoyi `sys_job` 自带列表展示）

## What

每天凌晨 2 点扫描"昨日且 status=pending"的预约 → 批量标 no_show（写 status + no_show_marked_time + booking_log）。任务幂等（重跑只处理当前仍 pending 的）、有告警（异常走 ruoyi SnailJob 自带通道），V1.0 不影响用户后续预约（无黑名单，doc/02 §2.3 AC 2）。

## AC（验收标准）

- [ ] **AC 1**：定义 ruoyi 兼容的 Job 类 `GzBeanNoShowMarkJob`（class path `org.dromara.gz.bean.job.GzBeanNoShowMarkJob`），方法 `run()` 无参；注册到 ruoyi `sys_job` 表（INSERT 走 db migration 或 admin 启动时检查注入），job 名 `GZ-BEAN-NO-SHOW-MARK`，cron 表达式 `0 0 2 * * ?`
- [ ] **AC 2**：扫描逻辑 `SELECT * FROM gz_bean_booking WHERE tenant_id='1001' AND status='pending' AND date < CURDATE()`（即昨日及之前的 pending — 涵盖跨日补跑场景）
- [ ] **AC 3**：批量更新逻辑：对每条记录做事务 — SELECT FOR UPDATE → 二次校验 status = pending → UPDATE status='no_show', no_show_marked_time=NOW → INSERT booking_log (action=no_show_mark, from_status=pending, to_status=no_show, operator_id=NULL, operator_type='system')；批量大小用 mybatis-plus batch 模式 200 条 / 批
- [ ] **AC 4**：异常处理：任何条记录抛异常 → catch 后记 log + 继续下一条（不中断整批）；批结束后统计 `成功 X / 失败 Y` 写入 ruoyi `sys_job_log` 的 job_message 字段；如失败数 > 0 → 走 ruoyi SnailJob 告警通道（CLAUDE.md §6 + doc/10 §3 E10）
- [ ] **AC 5**：幂等性：重跑任务对已是 no_show 的预约不再处理（WHERE status=pending 过滤天然幂等）
- [ ] **AC 6**：单测：mock booking repo，2 个 pending（昨日）+ 1 个 used（昨日）+ 1 个 pending（今日，不应被标）→ 跑 job → 验仅 2 条被标 no_show + booking_log 加 2 条

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-bean/`
  - `job/GzBeanNoShowMarkJob.java`（被 ruoyi sys_job 反射调用）
  - `service/IGzBeanBookingService.java` + impl 加 `markNoShowBatch()`（被 job 调用，可独立测）
  - DDL（注册 job）：`V202606020010__GZ-BEAN-009-register-noshow-job.sql` — INSERT 到 `sys_job` 表（job 名 / cron / class path / 状态正常）
- **测试**：admin 端进「系统监控 / 定时任务」找到 `GZ-BEAN-NO-SHOW-MARK` → 点"执行一次"手动触发 → 检查 DB 中昨日 pending 是否变 no_show + sys_job_log 有执行记录

## 备注

### 强约束

1. **任务必须幂等**（WHERE status=pending 天然幂等，重跑不重复标，doc/10 §3 E10）
2. **不允许 catch 后静默吞异常**（CLAUDE.md §6 #7），失败必须写 sys_job_log + 触发告警
3. **booking_log 操作者 = system**（operator_id=NULL，operator_type='system'）— doc/11 §3.5 字段口径
4. **批处理大小 200**（避免单事务过大锁表，V1.0 单日 pending 量极小可能不到 50，但模式约束保留）
5. **DDL 注册 job 必走 Flyway**（CLAUDE.md §6 #5 文件命名规则）

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | cron 表达式时区错配（容器 UTC vs 业务北京时间）| 容器启动 `-Duser.timezone=Asia/Shanghai`（ruoyi 默认已配）；testing-human 在 admin 端手动触发验逻辑，不依赖凌晨 2 点真触发 |
| R2 | "昨日"边界定义：是按 booking.date < CURDATE 还是按时段结束 + 缓冲？| V1.0 简化为 `date < CURDATE`（即跨天的全部 pending 一律 no_show，doc/10 §3 E9 已约定"最后时段 + 1h 缓冲"在 V1.0 不实现）；v2 候选：精确到时段结束 + 1h 缓冲 |
| R3 | 任务失败告警通道未配置 → 静默失败 | ruoyi SnailJob 自带 sys_job_log + 钉钉 / 飞书 webhook（已有的环境配置项，本 ticket 不再新配） |

---

## §revision（Kevin testing-human 后填，初始空）
