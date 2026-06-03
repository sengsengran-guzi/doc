# GZ-ADMIN-108 — 软删恢复回收站（del_flag 2 值 + 恢复 + SnailJob 物理清理）

**优先级**: P1
**复杂度**: S
**关联 PRD**: doc/02-prd.md M7 §异常分支 "甲方误删商品 / 文章 → 软删可恢复"
**关联拆解**: doc/02-需求拆解.md §3.5
**关联 mockup**: N/A（admin 走 ruoyi/Element Plus 默认审美，不套用 C 系统；plus-ui BizTable + 默认操作列即可）
**关联 ADR**: —
**依赖**: GZ-ADMIN-101（V1.1 预购商品 CRUD，落 `gz_ord_*` 软删字段）+ GZ-NEWS-003（资讯 CMS，`gz_news_article.del_flag` 已落）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **字段表**：doc/11-字段权威表.md **§0.3 命名规范**（`del_flag CHAR(1) NOT NULL DEFAULT '0'`，**仅 2 值** `'0'`=正常 / `'2'`=删除，对齐 ruoyi `@TableLogic`；归档另用独立列 `archived_flag`，**绝不复用 del_flag 第三值**）+ **§10.3 menu_id 分段**（11006 = 软删除回收站）
- **业务流**：doc/10-业务流权威图.md M7 §异常分支（甲方误删 → 软删可恢复）；本卡是 admin 数据治理工具，无独立状态机
- **CLAUDE.md §6 #1**：不动 ruoyi 自带模块（本卡仅扫 `gz_*` 业务表；`sys_*` 表自带软删逻辑不接管）
- **CLAUDE.md §6 #5 / Memory「调度用 SnailJob」**：定时清理走 SnailJob（`@Component + @JobExecutor` 薄壳 + 可单测 service），**禁止** Quartz / Flyway INSERT `sys_job`（仓库无 `sys_job` 表，INSERT 会启动 hard-fail）
- **UI 参考**：admin ticket — N/A（plus-ui BizTable + Element Plus 默认）

## What

admin 端「系统管理 → 回收站」页（owner 限定）：列出所有 `del_flag='2'` 的业务记录（按删除时间倒序），owner 可「恢复」（`del_flag='2' → '0'`）；可选「立即归档」走独立列 `archived_flag`（不复用 del_flag）；SnailJob 定时物理清理超期已归档记录。

## AC（验收标准）

- [ ] **AC 1**：**§0 自检 grep migration 目录确认真实落表名**（不假设命名）：
  - 命令：`grep -rhoiE 'CREATE TABLE[^(]*gz_[a-z_]+' code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/ | sort -u`
  - 实际落表为准（**不假设** `gz_store` / `gz_product_sku`；门店真实为 `gz_bean_store`，预购 SKU 为 `gz_ord_sku`，扭蛋奖品为 `gz_gacha_prize`）；只把**实际建了** `del_flag` 列的业务表纳入回收站
  - `entity_type` 注册清单以 grep 结果为准；上游表（ADMIN-101 的 `gz_ord_*` / NEWS-003 的 `gz_news_article`）未在 migration 目录出现 → **STOP 报 Kevin**（先回前序日收尾，不在本卡假设上游已建）
  - reports 必须含该 grep raw output + 每张纳入表的 `SHOW COLUMNS FROM <table> LIKE 'del_flag'` 命中清单
- [ ] **AC 2**：admin 端 `views/gz-common/recycle-bin/index.vue`（plus-ui BizTable，Element Plus 默认审美）：
  - 列：实体类型 / 实体名称 / 删除人（`update_by` 译名）/ 删除时间（`update_time`）/ 距今天数（前端算 `NOW − update_time`）/ 操作（恢复）
  - 筛选：实体类型下拉（前端枚举，不存 DB）+ 实体名称模糊搜 + 删除时间范围
  - 列表数据全部为 `del_flag='2'`，按 `update_time` 倒序
- [ ] **AC 3**：后端聚合查询接口 `GET /admin/gz/common/recycle-bin/list`：
  - 参数：`entityType`（可空 = 全部）+ 名称模糊 + 删除时间范围 + 分页
  - 实现：按 `entityType` 对各纳入业务表查 `del_flag='2'`，service 层合并后内存分页（V1.1 数据量小，不建物理 VIEW，对齐 doc/11 §9 注「不建物理 VIEW」同理由）
  - **mapper 查询方法标 `@InterceptorIgnore`**（仅放开逻辑删拦截 — 否则 ruoyi `@TableLogic` 自动 append `del_flag='0'` 查不到已删记录；`tenantLine` 保持不动，租户隔离不放开）
  - 返统一 VO `RecycleBinItemVO { entityType, entityId, entityName, deleteOperatorName, deleteTime, daysAgo }`
- [ ] **AC 4**：恢复操作 `POST /admin/gz/common/recycle-bin/restore`：
  - body：`entityType` + `entityId`
  - 按 `entityType` 路由到对应业务 Service 的 `restore(id)`：`UPDATE <table> SET del_flag='0' WHERE id=? AND del_flag='2'`（**update mapper 方法标 `@InterceptorIgnore`** 绕逻辑删拦截，否则 `@TableLogic` 拦截器会让 WHERE 条件失配 / update 被改写）
  - 影响 0 行（记录不存在或非 `'2'`）→ 返业务错误，不静默成功
  - 写 `sys_oper_log`（`@Log(title="回收站恢复 [entityType] [entityName]", businessType=UPDATE)`）
- [ ] **AC 5**：（可选）立即归档 `POST /admin/gz/common/recycle-bin/archive`：
  - body：`entityType` + `entityId`；`UPDATE <table> SET archived_flag=1 WHERE id=? AND del_flag='2'`（**独立列 `archived_flag TINYINT DEFAULT 0`**，doc/11 §0.3；**绝不写 del_flag='1'/'3' 等第三值**）
  - 归档 ≠ 删除：`del_flag` 保持 `'2'`，仅置 `archived_flag=1` 标记可被 SnailJob 清理；写 `sys_oper_log`
  - 各纳入表如未建 `archived_flag` 列 → 本卡 DDL `ALTER TABLE ... ADD archived_flag`（仅给纳入回收站的 `gz_*` 表，不动 ruoyi 自带表）
- [ ] **AC 6**：SnailJob 物理清理任务（**非 sys_job INSERT**）：
  - `job/GzRecycleCleanupJob.java`：`@Component` + `@JobExecutor(name="gzRecycleCleanupJob")` 薄壳，仅调 `IGzRecycleBinService.cleanupExpired()`
  - service 逻辑可单测：各纳入表 `DELETE FROM <table> WHERE del_flag='2' AND archived_flag=1 AND update_time < NOW() − INTERVAL 30 DAY`（物理删，分批 ≤ 1000 行）
  - **模块 pom 显式加 `ruoyi-common-job` 依赖**（gz-common 如未引则补）
  - **任务名 `gzRecycleCleanupJob` + CRON `0 0 3 * * ?` 写进 reports / testing-human**，由 Kevin 在 SnailJob 控制台注册（本卡不 INSERT 任何调度表）
- [ ] **AC 7**：权限（owner 限定）：
  - 全部接口标 `@SaCheckPermission`（如 `gz:recycle:bin:list` / `gz:recycle:bin:restore` / `gz:recycle:bin:archive`），**不用 `@SaCheckRole`**
  - 菜单 + 按钮权限仅授权 owner 角色（100），staff 访问 → 403
- [ ] **AC 8**：DDL `V202606191300__GZ-ADMIN-108-recycle-bin-menu-and-archived-flag.sql`（时间戳 > `V202606051200`）：
  - 菜单 `menu_id=11006`「回收站」（GZ-ADMIN V1.1 段 11000-11099，doc/11 §10.3）+ 按钮权限 + owner role-menu 映射
  - 各纳入回收站表 `ALTER TABLE ... ADD COLUMN archived_flag TINYINT NOT NULL DEFAULT 0`（如 AC5 采用）
  - **无任何 `INSERT INTO sys_job`**
- [ ] **AC 9**：单测覆盖（≥ 3 方法）：
  - happy path：构造 `del_flag='2'` 的 news → `restore(id)` → `del_flag='0'` 且业务列表重新可见
  - restore 影响 0 行（记录不存在 / 已是 `'0'`）→ 返业务错误，不静默成功
  - `cleanupExpired()`：mock `update_time=31 天前 + archived_flag=1 + del_flag='2'` 的 5 条 → 执行后物理删 5 条；`archived_flag=0` 或未超期的不删

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-common/`（跨域聚合，挂 common；包名 `org.dromara.gz.common.{controller,service,mapper,domain,job}`）
  - `controller/admin/GzRecycleBinAdminController.java`（admin 路径 `/admin/gz/common/recycle-bin`）+ list / restore / archive 三接口，`@SaCheckPermission`
  - `service/IGzRecycleBinService.java` + impl（list 聚合 + 路由 restore/archive 到各业务 Service + `cleanupExpired()`）
  - `service/internal/RecycleEntityRegistry.java`（显式注册纳入的 entity_type → mapper / 表名 / `nameField`，**不反射扫表**；entity_type 清单以 AC1 grep 结果为准）
  - `domain/vo/RecycleBinItemVO.java`
  - `mapper/`：各纳入表的回收站查询 / restore update 方法标 `@InterceptorIgnore`（仅放开逻辑删拦截）
  - `job/GzRecycleCleanupJob.java`（`@JobExecutor` 薄壳）
  - DDL × 1（菜单 11006 + owner 映射 + `archived_flag` 列，**无 sys_job INSERT**）
  - 各业务 Service 补 `restore(id)`（如已有则不动）
- **Admin 前端**：`code/main/plus-ui/`
  - `views/gz-common/recycle-bin/index.vue`（BizTable + 筛选 + 恢复按钮）
  - `api/gz-common/recycle-bin.ts`（list / restore / archive）
  - i18n：`recycleBin.*`（zh_CN / en_US）
- **测试**：mvn 单测（AC9 三方法）+ kevin-qa Playwright E2E（owner 登 admin → 回收站列表 → 恢复 → 业务列表重新可见）

## 备注

### 强约束

1. **del_flag 仅 2 值**（doc/11 §0.3 唯一真源）：`'0'`=正常 / `'2'`=删除，对齐 ruoyi `@TableLogic`（`logic-delete-value=2`）。**绝不引入第三值**；归档语义用独立列 `archived_flag`（0 正常 / 1 已归档），归档与逻辑删除是两个正交维度
2. **`@InterceptorIgnore` 仅放开逻辑删拦截**（AC3/AC4）：查 `del_flag='2'` + restore update 必须绕过 `@TableLogic` 自动过滤；`tenantLine` 不放开（租户隔离硬要求，CLAUDE.md §6 #2）
3. **定时清理走 SnailJob，禁止 sys_job INSERT**（AC6）：仓库无 `sys_job` 表，Flyway INSERT 会启动 hard-fail；任务名 + CRON 写 reports 由 Kevin 在控制台注册
4. **entity_type 清单 §0 自检 grep 真实落表**（AC1）：门店 = `gz_bean_store`，预购 SKU = `gz_ord_sku`，扭蛋奖品 = `gz_gacha_prize`，资讯 = `gz_news_article`；上游表未建 → STOP 报 Kevin
5. **菜单 menu_id 11006**（doc/11 §10.3，GZ-ADMIN V1.1 段），owner 角色限定
6. **owner `@SaCheckPermission`**（不用 `@SaCheckRole`），复用 ADR-0004 RBAC 底座
7. **不动 ruoyi 自带 `sys_*` 表**（CLAUDE.md §6 #1）：回收站只接管 `gz_*` 业务表

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | entity_type 显式注册（RecycleEntityRegistry），不反射扫表 | V1.1 业务表稳定 / 显式可读可单测；反射扫表运行时风险大 |
| D2 | service 层内存分页聚合，不建物理 VIEW | 物理 VIEW 绕 `@TableLogic` / `TenantLineInnerInterceptor` 易漏隔离（doc/11 §9 同理由）；V1.1 数据量小足够 |
| D3 | 归档用独立列 `archived_flag`，不复用 del_flag 第三值 | doc/11 §0.3 钉死：del_flag 仅 2 值；归档与逻辑删除正交，复用第三值破坏 `@TableLogic` 语义 |
| D4 | 物理清理走 SnailJob（`@JobExecutor` 薄壳 + 可单测 service） | Memory「调度用 SnailJob」：仓库无 sys_job，Quartz/Flyway INSERT 启动 hard-fail |
| D5 | restore/archive 路由到各业务 Service，不集中写裸 SQL | 业务 Service 持有领域知识，集中 SQL 难扩展 |
| D6 | restore 影响 0 行返业务错误，不静默成功 | 避免「点了恢复但实际没恢复」的静默失败（记录不存在 / 状态非 '2'）|

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 假设了不存在的表名（如 `gz_store` / `gz_product_sku`）| AC1 **§0 自检 grep migration 目录确认上游表实际存在**，以 grep 结果注册 entity_type；上游表未建 → STOP 报 Kevin |
| R2 | `@InterceptorIgnore` 放开范围过大（误绕租户 / SQL 注入拦截）| 仅放开逻辑删拦截（查 / 恢复 `del_flag='2'`），`tenantLine` 保持；mapper 方法级精确标注，不全局关 |
| R3 | 误用 del_flag 第三值实现归档 | 强制独立列 `archived_flag`（doc/11 §0.3）；单测断言 restore 后 del_flag 严格属 {'0','2'} |
| R4 | SnailJob 误用 Quartz / Flyway INSERT sys_job → 启动 hard-fail | `@Component + @JobExecutor` 薄壳 + 可单测 service；pom 显式加 `ruoyi-common-job`；任务名/CRON 写 reports 由人控制台注册 |
| R5 | 恢复 news 后关联图片 / 浏览数据是否一致 | 软删不动关联数据（仅改 del_flag），恢复后关联自然回来；如需特殊清理（V1.1 暂无）走 ADR |
| R6 | restore/cleanup 时序与对账 / 看板查询冲突 | 对账（ADMIN-105）按 `gz_pay_transaction.status='paid'` 过滤而非 del_flag，互不影响；回收站只治理 CRUD 主数据表 |

### ADR 候选

- 无

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!-- 问题清单写这里，然后 @coder 修 D11/GZ-ADMIN-108 revision 段 -->
