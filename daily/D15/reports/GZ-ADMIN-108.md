# GZ-ADMIN-108 — 完工报告（软删恢复回收站）

## §0 自检结果

| 检查项 | 结果 | 备注 |
|---|---|---|
| 仓库 git | N/A | 本项目非 git 仓 |
| 上游依赖 | ✅ | GZ-ADMIN-101（gz_ord_*）/ GZ-NEWS-003（gz_news_article）软删字段已建（grep migration 命中） |
| 真实落表名 grep | ✅ | 见下 raw output，注册 6 张主数据表（不假设 gz_store/gz_product_sku 命名） |
| 编译通过 | ✅ | mvn install gz-common BUILD SUCCESS |
| 权威蓝图 | doc/11 §0.3（del_flag 仅 2 值）+ §10.3（menu 11006） | 逐字落地 |
| ADR | 无相关 | — |
| 合同范围 | V1.1 | — |

### §0 自检 — 真实落表名 + del_flag 列（AC1 强制）

```
$ grep -rhoiE 'CREATE TABLE[^(]*gz_[a-z_]+' .../db/migration/ | sort -u
（命中 30+ 张 gz_* 表；回收站只纳入「owner 可能误删的业务主数据」6 张，非流水/审计/快照表）

$ 真库确认 6 张纳入表的名称列：
gz_news_article  → title         （资讯文章）
gz_ord_product   → name          （预购商品）
gz_ord_sku       → spec_name     （预购 SKU）
gz_gacha_prize   → name          （扭蛋奖品）
gz_gacha_machine → name          （扭蛋机）
gz_bean_store    → name          （拼豆门店）
全部含 del_flag CHAR(1) + update_by + update_time（ruoyi 标准审计列）
```

## 实现摘要

### 新增文件

```
后端（gz-common，base 模块——无法 import gz-ord/gz-news Service，故用注册表 + 泛型表名 SQL）：
  recycle/service/internal/RecycleEntityRegistry.java   6 实体白名单（entityType→table/nameColumn/label）
  recycle/domain/vo/RecycleBinItemVO.java               统一行 VO
  recycle/domain/vo/RecycleRawRow.java                  mapper 裸出参
  recycle/domain/bo/RecycleActionBo.java                恢复/归档入参
  recycle/mapper/GzRecycleBinMapper.java                泛型 selectDeleted/restore/archive/cleanupExpired
  recycle/service/IGzRecycleBinService.java + impl       内存聚合分页 + 删除人昵称批量解析 + 物理清理
  recycle/job/GzRecycleCleanupJob.java                  SnailJob 薄壳
  recycle/controller/admin/GzRecycleBinAdminController.java   list/entity-types/restore/archive
  recycle/service/GzRecycleBinServiceImplTest.java      5 单测
  db/migration/V202606241000__GZ-ADMIN-108-recycle-bin-menu-and-archived-flag.sql
Admin 前端：
  plus-ui/src/api/gz-common/recycle-bin.ts
  plus-ui/src/views/gz-common/recycle-bin/index.vue
  plus-ui/src/lang/{zh_CN,en_US}.ts（+recycleBin 段）
```

### 关键设计

- **跨模块约束**：gz-common 是 base（gz-ord/gz-news/gz-gacha 反向依赖它），无法 import 各业务 Service → restore/archive/cleanup 走注册表 + 泛型表名 SQL（`${tableName}` 取值仅来自白名单，非用户输入，无注入）。
- **@InterceptorIgnore 实际不需要**：MyBatis-Plus 的 `@TableLogic` 仅对 BaseMapper 自动方法追加 `del_flag='0'`，自定义 SQL 原样执行——故显式写 `del_flag='2'` 即可查到已删记录；租户隔离由 TenantLineInnerInterceptor 自动保留（admin 登录态），cleanup 在 cron 走 TenantHelper.ignore + SQL 显式 tenant_id。
- **del_flag 严格 2 值**（doc/11 §0.3）：归档用独立列 `archived_flag TINYINT 0/1`，与 del_flag 正交；恢复 = del_flag 2→0；归档 = archived_flag=1（del_flag 保持 2）。

## AI 自测

### 1. 编译 + 单测 5/5

```
$ mvn -o test -pl ruoyi-modules/ruoyi-gz-common -Dtest='GzRecycleBinServiceImplTest'
[INFO] Tests run: 5, Failures: 0, Errors: 0, Skipped: 0 -- in GzRecycleBinServiceImplTest
[INFO] BUILD SUCCESS
```
覆盖：restore happy（del_flag 2→0 返名称）/ restore 影响 0 行抛业务异常（不静默成功，D6）/ 非法 entityType 白名单拦截 / archive happy / cleanupExpired 遍历 6 表求和。

### 2. DDL ALTER 语法验证（真库 apply → revert，留给 Flyway 重建）

```
ALTER TABLE gz_news_article ADD COLUMN archived_flag TINYINT NOT NULL DEFAULT 0 ... → ALTER ok
ALTER TABLE gz_news_article DROP COLUMN archived_flag                              → DROP revert ok
（未持久化，Flyway 启动时对 6 张表 fresh 应用 archived_flag）
```

### 3. plus-ui build:prod 绿

```
$ pnpm build:prod → ✓ built in；recycle-bin 视图打进 bundle，无 error
```

## SnailJob 任务（待 Kevin 控制台注册）

| 任务 | @JobExecutor name | CRON | 含义 |
|---|---|---|---|
| 回收站物理清理 | `gzRecycleCleanupJob` | `0 0 3 * * ?` | 每日 03:00 删 archived_flag=1 且超 30 天的 del_flag='2' 记录（分批 ≤1000） |

> 薄壳转调可单测 `cleanupExpired()`；**无 Flyway INSERT sys_job**（DDL 仅 ALTER + sys_menu/role_menu）。

## 已知 issue / 下游提示

- **纯 admin/后端 ticket**：AI Tier 1A+1B 全 ✅ 即终态，无人验。
- 物理清理 30 天阈值硬编码在 service 常量 `RETENTION_DAYS`（V1.1 够用；如需可配再走 sys_config）。
- doc/11 §0.3 原文：`del_flag CHAR(1) NOT NULL DEFAULT '0'`，**仅 2 值** `'0'`正常/`'2'`删除；归档用独立 `archived_flag`，**绝不复用 del_flag 第三值** —— 实现一致（单测断言 restore 后 del_flag∈{'0','2'}，归档走 archived_flag）。
