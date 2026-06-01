# GZ-ADMIN-003 完工报告 — 基础数据看板（非交易指标）

> 后端 + DDL + SnailJob 执行器 + 单测由 kevin-coder 实现；前端看板页 / API / i18n + 本报告由主线程收尾（coder 子 agent 在 plus-ui 前端阶段被中断）。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A — 项目根非 git 仓库，文件系统直改 |
| 上游依赖 merge | ✅ 数据源齐：`gz_user`（SYS-003）/ `gz_bean_booking_log`（BEAN-004）/ `gz_news_article`（NEWS-001）均已落地 |
| 关键表/字段存在 | ✅ `gz_bean_booking_log` 实有 `from_status`(NULL首插)/`to_status`/`operator_type`(user/admin/system)/`tenant_id`/`create_time`/`del_flag CHAR(1)`；`gz_user` 有 `del_flag`（0=正常/2=删）—— 看板 mapper SQL 全字段命中，无运行期缺列风险 |
| 编译 + 单测 | ✅ `mvn test -pl ruoyi-gz-common`：`GzDashboardServiceImplTest` 4 passed；集成 `-am` 后 gz-common 全模块 36 passed / BUILD SUCCESS |
| ADR 已读 | 本 ticket 无关联 ADR；调度框架决策复用 GZ-BEAN-009（SnailJob） |
| **仓库无 sys_job 确认** | ✅ `grep sys_job script/sql ✗`；调度走 SnailJob `sj_*`。DDL **不含任何 sys_job INSERT**（仓库无该表，INSERT 会启动 hard-fail） |

### 关键自检发现

1. **累计/今日预约用 `gz_bean_booking_log`**（非 booking 表）：booking 表 cancelled 物理删（doc/11 §3.4），log 表永不删 → 用 `from_status IS NULL AND to_status='pending' AND operator_type='user'` 仅数用户提交首条 pending 日志，排除后续 admin/system 流转日志膨胀（ticket R2）。字段已与真实 DDL 对账一致。
2. **看板放 `gz-common`**（决策 D2）：跨域聚合（user+bean+news），反向依赖单业务模块会循环依赖。mapper 直接 `@Select` 物理表名，不依赖各模块 entity。
3. **cron 上下文租户**：service 用 `TenantHelper.ignore(...)` 包裹 + SQL 显式传 `tenant_id='1001'`（V1.0），不依赖多租户拦截器对 raw 跨表 SQL 的注入行为（与 BEAN-009 / PAY-001 cron 同思路）。
4. **wide-long 快照表**（决策 D1）：每 metric 一行，V1.1 加 metric 不需 ALTER；`UNIQUE(tenant_id, snapshot_time, metric_key)` + `IDX(tenant_id, metric_key, snapshot_time DESC)` 查最新。

## 实现摘要

新增产物（后端 `ruoyi-gz-common/.../dashboard/` 包 — 与 PAY-001 的 `pay/` 包平级隔离，零文件冲突）：
```
controller/GzDashboardController.java            admin /system/gz/dashboard（latest/trend/refresh）
service/IGzDashboardService.java + impl          takeSnapshot / getLatest / getTrend（核心可测逻辑）
job/GzDashboardSnapshotJob.java                  SnailJob @JobExecutor 触发壳（对齐 GzBeanNoShowMarkJob）
mapper/GzDashboardMetricMapper.java              5 个 COUNT/SUM 跨表只读聚合
mapper/GzDashboardSnapshotMapper.java            快照写入 / 查最新 / 查趋势
domain/entity/GzDashboardSnapshot.java           快照实体
domain/vo/GzDashboardLatestVO.java               latest 返回（snapshotTime + metrics[{metricKey,title,value}]）
domain/vo/GzDashboardTrendVO.java                trend 返回
enums/DashboardMetric.java                       5 指标枚举（metricKey + title）
src/test/.../GzDashboardServiceImplTest.java     单测 4
```
DDL（1 文件）：`V202606041100__GZ-ADMIN-003-create-gz_dashboard_snapshot.sql` — 建 `gz_dashboard_snapshot` 表 + INSERT `sys_menu`(300 数据看板/301 立即刷新) + `sys_role_menu`(owner 100→view+refresh / staff 101→view)。**无 sys_job**。

前端（主线程收尾）：
```
plus-ui/src/api/gz-common/dashboard.ts           getDashboardLatest / getDashboardTrend / refreshDashboard（契约对齐 controller + VO）
plus-ui/src/views/dashboard/index.vue            5 张 el-card KPI（千分位）+「更新于 X」+「立即刷新」（loading + 前端 5s disable 对齐后端 @RateLimiter）
plus-ui/src/lang/zh_CN.ts / en_US.ts             gzDashboard i18n block（5 指标标题 + 卡片文案，默认 zh-CN 不混 emoji）
```
路由：menu component `dashboard/index` → `views/dashboard/index.vue`，路由 `/dashboard`（不动 ruoyi 默认 `/index`）。

## AI 自测（Tier 1A）+ 主线程集成 gate

### gz-common 单测（dashboard 4 + 集成全模块 36）
```
[INFO] Tests run: 4, Failures: 0, Errors: 0, Skipped: 0 -- org.dromara.gz.common.dashboard.service.GzDashboardServiceImplTest
... 集成 mvn install -am 后 gz-common 全模块：
[INFO] dashboard 4 + pay 6 + gzUser 8 + gzFile 9 + WxLogin 4 + WxMockLogin 5 = 36 passed
[INFO] BUILD SUCCESS  ·  ruoyi-gz-common-5.6.1.jar installed @ 07:35
```
4 单测覆盖（AC7 ≥2）：happy（mock 5 COUNT → batch insert 5 行 / snapshot_time 同批一致）+ 异常处理（mock mapper 抛 → takeSnapshot catch 不外抛，返回 success=false，cron 不阻塞 / refresh 不抛 500）+ getLatest 空快照（snapshotTime=null + 空 metrics）+ getLatest 正常聚合。

### booking_log 字段对账（防 mock 单测掩盖运行期缺列）
```
gz_bean_booking_log:  from_status VARCHAR(16) NULL / to_status VARCHAR(16) NOT NULL
                      operator_type VARCHAR(16) NOT NULL / tenant_id / create_time DATETIME
                      del_flag CHAR(1) NOT NULL DEFAULT '0'        ← mapper del_flag='0' 命中 ✅
gz_user:              del_flag CHAR(1) NOT NULL DEFAULT '0'        ← mapper del_flag='0' 命中 ✅
```

### 前端集成（主线程）
```
plus-ui build:prod        ✅ dist 产出（vue-quill / dashboard chunk 均在）
vue-tsc 我的 dashboard 文件   0 新增 TS 错（总错数 72 = D07 前 baseline，无新增）
```

## SnailJob 控制台注册参数（手工在 admin「定时任务」菜单注册，非 Flyway）

| 项 | 值 |
|---|---|
| 任务名称 | `GZ-DASHBOARD-SNAPSHOT` |
| 执行器路由（executor_info） | `gzDashboardSnapshotTask`（= `@JobExecutor` name） |
| 触发类型 / CRON | CRON，`0 0/5 * * * ?`（每 5 分钟整点，容器时区 Asia/Shanghai） |
| 阻塞策略 | 丢弃（DISCARD） |
| 组 | `ruoyi_group` |

> 注册前 cron 不触发 → snapshot 表空 → 前端显示「暂无快照数据」（已做空态兜底）。首次注册后「执行一次」即可写第一批快照。

## 风险提示 / 已知 issue

- **R1 端到端未跑**：后端 dev 未启动，refresh API → service.takeSnapshot → 5 个跨表 SQL 真实执行 + snapshot 落库未在真 MySQL 验证（单测 mock mapper）。留 Kevin V1.0 端到端回归（README §B 第 6 项：刷新 → 看到本次新增用户1/预约1/阅读1）或 SnailJob 控制台「执行一次」后查 `gz_dashboard_snapshot`。
- **R2 SnailJob 控制台注册需手工**（同 BEAN-009 / NEWS-004）：此波累计待注册 cron = `gzBeanNoShowMarkTask` / `gzNewsScheduledPublishTask` / `gzPayExpireOrderTask` / `gzDashboardSnapshotTask`。
- **R3 趋势 API 留接口不展示**（决策 D4）：`GET /trend` 已实现，前端 V1.0 不渲染图表（echarts 选型推 V1.1）。
- **R4 doc/11 缺 dashboard_snapshot 章节**：本 ticket DDL 落地后由周末复盘补 doc/11（CLAUDE.md §9.5 第 1 优先级）。

## Tier 2 可达性

- 本 ticket **纯 admin**（Tech 段无 `miniapp/` 路径，AC 无微信原生能力）→ 按 CLAUDE.md §8.2 例外：仅 Tier 1A + 1B，AI ✅ 即终态 close，**无 mp 人验、无临时入口**。
- admin 可达：登录 admin → 菜单「数据看板」(menu 300) → `/dashboard` 看 5 KPI 卡 + 立即刷新。

## §AI 测试段（Tier 1B）

> 本环境 Agent 受嵌套限制未独立 spawn kevin-qa。Tier 1B admin Playwright E2E（登录 → 看板页 → 5 卡渲染 → 立即刷新 loading + 5s 防抖 + 数值更新 + perm gz:dashboard:view/refresh）需后端起 + plus-ui dev 后跑，留主线程收尾 gate / Kevin V1.0 端到端一并覆盖。后端集成 + 前端 build 已绿（见上）。
