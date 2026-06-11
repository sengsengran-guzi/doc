# GZ-ADMIN-106 — 完工报告（数据看板 V1.1 交易盘面）

## §0 自检结果

| 检查项 | 结果 | 备注 |
|---|---|---|
| 上游依赖 | ✅ | GZ-ADMIN-105（gz_recon_monthly + IGzReconQueryService）/ GZ-ADMIN-103（gz_ord_order/gz_gacha_order）/ gz_gacha_draw / gz_pay_transaction 真库确认存在 |
| 编译通过 | ✅ | mvn install gz-common BUILD SUCCESS |
| 权威蓝图 | doc/10 §8/§9/§10 + doc/11 §4.6/§9/§6.3/§7.3 | 复用 105 口径不重写 |
| ADR | 无相关 | — |
| 合同范围 | V1.1 | — |

## 实现摘要

### 新增文件

```
后端（gz.recon 域，与 105 同域便于复用 service）：
  recon/domain/vo/GzDashboardV11SummaryVO.java          单接口聚合返回（A/B 分流 + Top10）
  recon/mapper/GzReconDashboardMapper.java              今日订单/GMV + 扭蛋开盒/出货价值 + 待发货 + 热销 Top10
  recon/service/IGzReconDashboardService.java + impl      复用 IGzReconQueryService.monthlySummary
  recon/controller/admin/GzReconDashboardController.java  GET /v11-summary（单接口）
  recon/service/GzReconDashboardServiceImplTest.java     3 单测
  db/migration/V202606241050__GZ-ADMIN-106-dashboard-v11-perm.sql
Admin 前端：
  plus-ui/src/api/gz-recon/dashboard.ts                 getV11Summary()
  plus-ui/src/views/dashboard/components/V11SummaryRow.vue   V1.1 区块独立组件
  plus-ui/src/views/dashboard/index.vue                 追加 <V11SummaryRow v-if="showV11">（perm 门控）
  plus-ui/src/lang/{zh_CN,en_US}.ts（+dashboard.v11 段，盲盒语义）
```

### 关键设计

- **单聚合接口**（AC3）：`GET /system/gz/recon/dashboard/v11-summary` 一次返所有卡片，前端 1 次调用本地分发，不串行。
- **复用 105 口径**（AC4 / D2）：本月 GMV/退款/实际到账走 `IGzReconQueryService.monthlySummary(businessType, month, month)`，不在看板侧重算 4% 分成 —— 避免双口径漂移（CLAUDE.md §9.5 §1）。
- **盲盒语义**（强约束 #5）：扭蛋卡 i18n key = `gachaOpenCount` / `gachaAvgValue`（开盒数 / 平均出货价值），无「抽奖/中奖」；出货价值 = `SUM(prize_snapshot_json.referenceValueCent) / 开盒数`（整除取整）。
- **待发货口径**（强约束 #3）：`gz_ord_order WHERE business_status='paid' AND logistics_status='in_japan'`，用 C1 2 态字段，禁 logistics_node/7 节点。
- **业务线分流统一 business_type**（preorder/gacha，test exclude）。

### ⚠️ 与 ticket「无 DDL」的 1 处偏差（已记 DDL 注释）

ticket 原设「复用 V1.0 看板 menu、无 DDL」。但 V1.1 交易盘面含 GMV/退款/实际到账（财务敏感），需 owner-only perm `gz:recon:dashboard:v11`；该 perm 在仓库无任何 menu/role 行 → `@SaCheckPermission` 会对所有人 403。故加 1 个 **F 型按钮权限**（menu_id 302，挂现有「数据看板」menu 300 下，授 owner role_id=100），**不新增 C 型独立页菜单**（仍是同一首页区块扩展，符合「不新增独立页」本意）。无权限角色看 V1.0 老卡片，V1.1 区块 v-if 隐藏。

## AI 自测

### 1. 单测 3/3

```
$ mvn -o test -pl ruoyi-modules/ruoyi-gz-common -Dtest='GzReconDashboardServiceImplTest'
[INFO] Tests run: 3, Failures: 0, Errors: 0, Skipped: 0 -- in GzReconDashboardServiceImplTest
[INFO] BUILD SUCCESS
```
覆盖：单接口返所有卡片非空（复用 105 实际到账）/ 待发货口径 / 业务线 A·B 分流 + 扭蛋平均出货价值（40000/4=10000 整除）。

### 2. DDL 应用（真库，幂等 menu）

```
SELECT menu_id, menu_name, perms FROM sys_menu WHERE menu_id=302;
302  V1.1交易盘面  gz:recon:dashboard:v11   （owner role_id=100 已授权）
```

### 3. plus-ui build:prod 绿

```
$ pnpm build:prod
dist/assets/V11SummaryRow-*.js   4.79 kB
dist/assets/dashboard-*.js       2.80 kB
✓ built in 16.16s（无 error）
```

## 已知 issue / 下游提示

- **纯 admin/后端 ticket**：AI Tier 1A+1B 全 ✅ 即终态，无人验。无新建表、无 SnailJob。
- 待发货卡片点击 → `router.push('/gz-ord/orders')`（GZ-ADMIN-104 物流推进在订单详情操作）。
- 不做轮询/缓存（V1.1 数据量小直查，强约束 #6）。
