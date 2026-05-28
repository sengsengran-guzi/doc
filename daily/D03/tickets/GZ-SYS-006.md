# GZ-SYS-006 — 操作日志（管理后台审计）

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M7.11 操作日志 / §用户故事 3（Kevin "所有改动可追溯"）
**关联拆解**: doc/02-需求拆解.md §2.1 第 246 行
**关联 mockup**: ⚠️ 缺口（待 designer 补 admin-log.html）— V1.0 设计冻结期 admin 走 ruoyi 自带 sys_oper_log 默认页
**关联 ADR**: —
**依赖**: GZ-ADMIN-001（admin user 上下文 + sys_oper_log 已存在）

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md — 操作日志是横切关注点，所有业务流的写操作都要打日志
- **字段表**：doc/11-字段权威表.md — 不新建表，复用 ruoyi 自带 `sys_oper_log`
- **UI 参考**（设计冻结期）：N/A（ruoyi 自带「系统监控 → 操作日志」页直接复用）

## What

复用 ruoyi 自带 `@Log` 注解 + `sys_oper_log` 表，确保业务 ticket（GZ-ADMIN-002 / GZ-BEAN-008 / GZ-NEWS-003 等）的关键写操作都打日志；落实日志保留 12 个月策略；admin 端日志页菜单挂载。

## AC（验收标准）

- [ ] **AC 1**：所有业务 Controller 写操作（POST / PUT / DELETE / 状态切换）加 `@Log(title="...", businessType=BusinessType.XXX)` 注解 — 本 ticket 在 GZ-ADMIN-002 等已存在的业务 Controller 上回填注解；后续业务 ticket 实施时由各 ticket 主人自己加（规约在本 ticket 的「对下游 ticket 的提示」段说明）
- [ ] **AC 2**：admin 端「系统监控 → 操作日志」菜单复用 ruoyi 自带（已存在，仅确认 owner / staff 权限能看 — staff 仅能看自己的操作）
- [ ] **AC 3**：日志保留策略 cron `LogRetentionJob.cleanOldLogs()` — 每月 1 号凌晨 3 点扫 sys_oper_log，删 `oper_time < NOW() - INTERVAL 12 MONTH` 的记录
- [ ] **AC 4**：staff 权限仅看自己 oper_name = 当前 user_name 的日志（ruoyi 自带 SysOperLogController.list 加 DataScope 注解 — 本 ticket 在自定义 wrapper Controller 实现，不动 ruoyi 原 Controller）
- [ ] **AC 5**：本 ticket 覆盖 6 类业务操作必打日志（doc/02 §2.1 第 250 行）：
  - 资讯发布 / 下架 → GZ-NEWS-003 实施时加 @Log
  - 用户禁用 → 复用 ruoyi `/system/user/changeStatus` 自带 @Log
  - 预约状态修改 → GZ-BEAN-008 实施时加 @Log
  - 管理员账号变更 → 复用 ruoyi `/system/user/*` 自带 @Log
  - 拼豆门店 / 座位 / 时段配置变更 → GZ-BEAN-001/002 实施时加 @Log
  - 文件上传 → GZ-SYS-005 实施时加 @Log
- [ ] **AC 6**：单测可选

## Tech（端 + 范围）

- **后端**：
  - 新建 `ruoyi-modules/ruoyi-gz-common/job/LogRetentionJob.java`（Spring `@Scheduled` cron）
  - 新建 `ruoyi-modules/ruoyi-gz-common/controller/GzOperLogController.java`（owner/staff 权限差异 wrapper，路径 `/system/gz/oper-log`；底层调 ruoyi `SysOperLogService`）
  - sys_menu 增 `谷子操作日志` 菜单（menu_id 5011，挂在 100 谷子业务下）+ perm `gz:oper-log:list`
  - 不动 ruoyi 自带 sys_oper_log schema
  - DDL `V202605291300__GZ-SYS-006-menu.sql`
- **Admin**：`views/gz-common/oper-log/index.vue`（thin wrapper，复制 ruoyi 自带 `views/monitor/operlog/index.vue` 改 API 路径到 `/system/gz/oper-log`）
- **测试**：mvn 跑 + admin 端 owner 登录看到所有日志 / staff 仅看自己 → 切到 ADMIN-002 加个 staff 账号 → 看 sys_oper_log 有新记录

## 备注

### 强约束

1. **不重写日志框架**（@Log 注解 + sys_oper_log 已是 ruoyi 范式 + AOP 自动）
2. **不在业务 Service 里手动写日志**（错误范式 — 应该在 Controller 加 @Log 注解，Service 关注业务）
3. **日志保留 12 个月**（doc/02 §2.1 第 252 行明确）— cron 自动清理，不留人工清理动作
4. **staff 权限差异化**：用 DataScope 注解 / 自定义 wrapper Controller，不要在 SQL 里 hard code
5. **不打读操作日志**（GET 不写日志 — 性能 / 噪音）

### 对下游 ticket 的提示（强约束）

本 ticket 完工后，**所有后续业务 ticket 的写操作必须加 @Log 注解**：

```java
@PostMapping("/booking/cancel")
@Log(title = "预约取消", businessType = BusinessType.UPDATE)
public R<Void> cancel(@RequestParam Long bookingId) { ... }
```

`businessType` 枚举值：INSERT / UPDATE / DELETE / GRANT / EXPORT / IMPORT / FORCE / GENCODE / CLEAN / OTHER（ruoyi 自带）

kevin-coder agent 在跑后续 ticket 时 §0 自检会卡这条（如有写操作但无 @Log → STOP）。

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | sys_oper_log 数据量大（业务上线后日均 1k-10k 行）| 12 月保留 + cron 自动清理 + ruoyi 自带异步刷盘 |
| R2 | DataScope 注解与 ruoyi 自带 SysOperLogService 冲突 | 不动 ruoyi 自带，写自定义 GzOperLogController wrapper |

---

## §revision（Kevin testing-human 后填，初始空）
