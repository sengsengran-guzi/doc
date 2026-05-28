# GZ-ADMIN-108 — V1.0 软删除恢复机制

**优先级**: P1
**复杂度**: S
**关联 PRD**: doc/02-prd.md M7 §异常分支 "甲方误删商品 → 软删除 30 天可恢复"
**关联拆解**: doc/02-需求拆解.md §3.5 第 1013 行
**关联 mockup**: ⚠️ 缺口（admin-recycle-bin.html 待补；设计冻结期改用 plus-ui BizTable + el-tabs（回收站 / 归档库）+ 默认操作列）
**关联 ADR**: —
**依赖**: GZ-ADMIN-101（V1.1 admin 域底座）+ GZ-NEWS-003（确认 V1.0 资讯表已用 del_flag）

---

## 必读权威文档（缺一不可）

- **字段表**：doc/11-字段权威表.md — 所有业务表 `del_flag` 字段定义（ruoyi 范式 `0`=正常 / `1`=删除 / `2`=归档）
- **业务流**：doc/10-业务流权威图.md M7 §异常分支（甲方误删商品 → 软删 30 天可恢复）
- **CLAUDE.md §6 #1**：不动 ruoyi 自带模块（本 ticket 仅扫 gz_* 业务表，sys_* 表自带回收站逻辑不动）
- **UI 参考**（设计冻结期）：admin ticket — **N/A**（plus-ui BizTable + el-tabs 默认）

## What

admin 端「系统管理 → 回收站」页 — owner 可查看 30 天内所有软删的业务记录（商品 / 文章 / 扭蛋 SKU / 拼豆座位 / 门店等），点"恢复"将 del_flag 0→1 改回 0；30 天后自动归档（del_flag 1→2），归档库 owner 单独查。

## AC（验收标准）

- [ ] **AC 1**：§0 自检阶段先扫所有 `gz_*` 业务表的 del_flag 字段（doc/11 §x.x 索引）：
  - 期望全部命名为 `del_flag` + 类型 char(1) + 默认 `'0'`（ruoyi 范式）
  - 任一表命名不一致（如 `is_deleted` / `deleted_at`）→ **STOP 报 Kevin**（CLAUDE.md §6 #10）— 先回补 doc/11 + 改 V1.0 老 DDL 再实施本 ticket
  - reports 必须含 `SHOW COLUMNS FROM gz_* LIKE 'del_flag'` raw output 所有命中表清单
- [ ] **AC 2**：admin 端 `views/gz-common/recycle-bin/index.vue`：
  - el-tabs 两 tab：「回收站」（del_flag='1'）/ 「归档库」（del_flag='2'）
  - BizTable 列：实体类型 / 实体名称 / 删除人 / 删除时间 / 距今天数（自动算 NOW − update_time）/ 操作
  - 实体类型走前端枚举（不存 DB）：商品 / 文章 / 扭蛋 SKU / 拼豆座位 / 门店 / 拼豆预约（V1.0+V1.1 涵盖）
  - 筛选：实体类型下拉 + 实体名称模糊搜 + 删除时间范围
- [ ] **AC 3**：后端聚合接口 `GET /admin/gz/common/recycle-bin/list`：
  - 参数：tab（`recycle` / `archive`）+ entity_type 筛 + 分页
  - 实现：按 entity_type UNION ALL 各业务表（gz_news_article / gz_product_sku / gz_gacha_sku / gz_bean_seat / gz_store / gz_bean_booking 等）
  - 返统一 VO `RecycleBinItemVO { entityType, entityId, entityName, deleteOperatorId, deleteTime, daysAgo }`
- [ ] **AC 4**：恢复操作 `POST /admin/gz/common/recycle-bin/restore`：
  - body: entity_type + entity_id
  - 后端按 entity_type 路由到对应 Service（如 entity_type='news' → `IGzNewsArticleService.restore(id)`）
  - 每个业务 Service 实现 `restore(id)` 方法：UPDATE table SET del_flag='0' WHERE id = ? AND del_flag = '1'
  - 写 sys_oper_log（@Log 注解，业务标题"回收站恢复 [entity_type] [entity_name]"）
  - 已归档（del_flag='2'）的项**不可恢复**，UI 上"归档库" tab 操作列只有"查看详情"，无"恢复"按钮（避免归档后又恢复引起对账漂移）
- [ ] **AC 5**：立即归档操作 `POST /admin/gz/common/recycle-bin/archive`（owner 主动归档）：
  - body: entity_type + entity_id
  - UPDATE table SET del_flag='2' + 写 sys_oper_log
- [ ] **AC 6**：定时归档 cron：
  - ruoyi `sys_job` 注册任务 `GzRecycleArchiveJob.archive()`，cron `0 0 3 * * ?`（每天凌晨 3 点）
  - 逻辑：所有 `gz_*` 业务表 UPDATE SET del_flag='2' WHERE del_flag='1' AND update_time < NOW() − INTERVAL 30 DAY
  - 各表归档语句枚举写在 Job 类常量，避免反射扫表（V1.1 简单粗暴 + 显式）
  - 归档批次 ≤ 1000 行（超过分批）
  - 归档日志写到 sys_job_log
- [ ] **AC 7**：权限：
  - 回收站 / 归档库均 **owner 角色**可见（perm `gz:recycle:bin`）
  - staff 角色访问 → 403
- [ ] **AC 8**：菜单 menu_id 11010（ADMIN V1.1 段 11000-11099），DDL `V202606191300__GZ-ADMIN-108-menu-and-job.sql` 含菜单 + sys_job 行
- [ ] **AC 9**：单测覆盖：
  - happy path：del_flag='1' 的 news 恢复 → del_flag='0'
  - 已归档（del_flag='2'）的 news 调 restore → returns 400 + 错误信息
  - cron 跑：mock update_time = 31 天前的 5 条 del_flag='1' → 执行后全部变 del_flag='2'
  - 共 3 个测试方法

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-common/`（跨域聚合，挂 common）
  - `controller/admin/GzRecycleBinAdminController.java`（admin 路径 `/admin/gz/common/recycle-bin`）+ 3 个接口
  - `service/IGzRecycleBinService.java` + impl（路由到各业务 Service 的 restore / archive）
  - `service/internal/RecycleEntityRegistry.java`（注册 6 个 entity_type + 对应 mapper 引用 + entity_name 字段提取）
  - `domain/vo/RecycleBinItemVO.java`
  - `job/GzRecycleArchiveJob.java`（ruoyi `@DisallowConcurrentExecution`）
  - DDL × 1（菜单 + sys_job 行）
  - 各业务 Service（GzNewsArticleService / GzProductSkuService / GzGachaSkuService / GzBeanSeatService / GzStoreService / GzBeanBookingService）补 `restore(id)` 方法（如已有则不动；如缺补一个 UPDATE）
- **Admin 前端**：`code/main/plus-ui/`
  - `views/gz-common/recycle-bin/index.vue` 主页
  - `api/gz-common/recycle-bin.ts` 三个 API
  - i18n：`recycleBin.*` 段
- **测试**：mvn 单测 + 浏览器实操：admin 删一篇 news → 回收站可见 → 点恢复 → mp 端可见 → mock update_time 触发 cron → 归档库可见

## 备注

### 强约束

1. **§0 自检必扫 del_flag 命名**（AC 1）— 不一致先回补 doc/11 + 改 V1.0 老 DDL，不在本 ticket 内 patch
2. **归档（del_flag='2'）不可恢复**（AC 4）— 避免归档后又恢复引起 ADMIN-105 对账数据漂移
3. **菜单挂 ADMIN V1.1 段 11010**（CLAUDE.md §6 #6）
4. **owner 权限**（财务/运营数据敏感）
5. **不动 ruoyi 自带 sys_* 表**（CLAUDE.md §6 #1）— sys_user / sys_role 等自带软删走 ruoyi 自带逻辑，本回收站不接管

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 6 个 entity_type 显式枚举 + UNION ALL，不反射扫表 | V1.1 业务表数量稳定 / 显式可读 / 性能可控；反射扫表运行时风险大 |
| D2 | 归档不可恢复 | 避免对账 / 报表数据漂移（归档后已从看板/对账中心排除，恢复后重新计入引发歧义）|
| D3 | cron 每日凌晨 3 点（避开业务高峰） | 复用 ruoyi sys_job 框架 / 单点执行 / @DisallowConcurrentExecution 防并发 |
| D4 | 归档批次 ≤ 1000 行 | 单 UPDATE 大批量锁表风险 / 分批降低 DB 压力 |
| D5 | restore/archive 路由到各业务 Service，不集中写 SQL | 业务 Service 持有领域知识（如 restore news 时是否要重发订阅消息）/ 集中 SQL 难扩展 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | gz_* 表 del_flag 命名不统一（V1.0 老 DDL 历史包袱） | AC 1 §0 自检发现就 STOP 报 Kevin，回补 doc/11 + ALTER TABLE 统一命名（不在本 ticket 内 patch）|
| R2 | UNION ALL 6 张表查询慢 | 各表 del_flag 字段已有索引（ruoyi 范式默认建）/ 单表查询 < 50ms / 总 < 300ms |
| R3 | cron 凌晨 3 点跑时间窗与 ADMIN-105 对账聚合视图查询冲突 | 视图实时查不依赖归档状态（v_gz_finance_daily 按 status='paid' 过滤而非 del_flag）/ 互不影响 |
| R4 | 恢复 news 后该 news 关联的图片 / 评论 / 浏览数据是否一致 | 软删不动关联数据（仅改 del_flag），恢复后关联数据自然回来；如有特殊清理逻辑（V1.1 暂无）走 ADR |
| R5 | sys_job 框架未启用 / cron 不跑 | reports 必须含 mock update_time 后 SELECT 验归档结果 raw output |
| R6 | entity_name 字段提取在不同表名字不一样（gz_news_article.title / gz_product_sku.sku_name 等） | RecycleEntityRegistry 注册时显式声明 nameField = "title" / "sku_name" 等，提取统一走 reflection / mapper |

### ADR 候选

- 无

---

## §revision（Kevin testing-human 后填，初始空）
