# GZ-ADMIN-104 — 完工报告（跨境物流 2 态推进 / mp 店员端主形态 + plus-ui owner 兜底）

## §0 自检结果

| 检查项 | 结果 | 备注 |
|---|---|---|
| 上游依赖 | ✅ | gz_ord_order/gz_gacha_order 物流字段（logistics_status/cn_carrier_code/cn_tracking_no/cn_dispatched_at/delivered_time/business_status）+ gz_logistics_audit + gz_express_carrier 字典 9 项 真库确认存在 |
| 编译通过 | ✅ | mvn install gz-common + gz-ord BUILD SUCCESS |
| 权威蓝图 | doc/10 §9（C1 2 态 + 终态 + N2/N8/N9/E2/E5/E6）+ doc/11 §6.3/§7.4/§8.3 + 附录 A.7 | 逐字落地 |
| ADR | ADR-0004（mp 店员 RBAC 底座）/ ADR-0005（物流 2 态对齐合同 §2.3） | 已读，复用底座 |
| 合同范围 | V1.1 | 合同 §2.3 #14/#15（不自动抓取，仅展示甲方录入单号） |

### §0 真库确认（不假设上游）

```
gz_ord_order   cols: business_status,logistics_status,delivered_time,cn_carrier_code,cn_tracking_no,cn_dispatched_at,order_no ✓
gz_gacha_order cols: 同上 ✓
gz_logistics_audit 存在 ✓（action_type/from_*/to_*/reason/operator_type/operator_id/operated_time）
gz_express_carrier 字典 9 项 ✓（yto/sf/zto/yunda/jd/ems/debang/jitu/other）
```

## 实现摘要

### 新增/改动文件

```
后端（gz-ord；跨业务按 business_type 分流 UPDATE，gz_gacha_order 用裸 SQL 不依赖 gz-gacha 模块）：
  enums/ExpressCarrierEnum.java（改）                    +isValid() 9 项校验
  domain/dto/{LogisticsForwardDto,LogisticsCarrierUpdateDto,LogisticsRollbackDto}.java
  domain/vo/LogisticsOrderStateVo.java                  mapper 状态出参
  mapper/GzLogisticsMapper.java                         ${table} 状态推进 + 裸 INSERT gz_logistics_audit
  service/IGzLogisticsService.java + impl                状态机 + 9 项校验 + 必录校验 + 审计集中
  controller/GzLogisticsController.java                 /system/gz/ord/logistics（owner，含 rollback）
  controller/applet/GzLogisticsMpController.java        /app/gz/staff/logistics（mp 店员，无 rollback）
  service/GzLogisticsServiceImplTest.java               11 单测
  db/migration/V202606241100__GZ-ADMIN-104-logistics-menu.sql
plus-ui（owner 兜底）：
  api/gz-ord/logistics.ts                              forward/carrier/rollback
  views/gz-ord/orders/components/OrderDetailDrawer.vue（改）  占位按钮→真操作区 + 发货/改单号/回退弹窗
  lang/{zh_CN,en_US}.ts（+gzOrdOrders.logi* 段）
mp 店员端（主形态）：
  api/gz-ord/logistics.ts                              forwardStaffLogistics/updateStaffCarrier + EXPRESS_CARRIERS
  pages/me/staff-orders/detail.vue（改）                 物流推进操作区（快递 9 选 1 chips + 单号 input，Biz* + var(--c-*)）
  locale/staff.zh-CN.ts（+push* 段）
```

### 关键设计

- **状态机**：in_japan→in_china_dispatching（必录快递+单号，9 项字典校验，service assert + mp/owner 表单 disabled，doc/10 §9.E5）→ delivered；目标态由当前态决定（forward 推进一步），不可跳态/不可逆（回退走独立 owner 接口）。
- **条件 UPDATE 保状态机安全**：`WHERE order_no AND logistics_status='<源态>'`，源态不符 → 影响 0 行 → service 报错（防并发越级）。
- **跨业务复用**：`tableOf(businessType)` 白名单映射 preorder→gz_ord_order / gacha→gz_gacha_order；gz_gacha_order 用裸 SQL（不依赖 gz-gacha 模块，无循环依赖）。
- **审计**（doc/11 §8.3）：每次写 gz_logistics_audit；action_type = status_forward（含 to_status + to_carrier + to_tracking）/ carrier_update（记 from/to 单号）/ status_rollback（记 from/to/reason）；operator_type='admin'，operator_id=LoginHelper.getUsername()。
- **下沉**（Kevin 决策 2 / ADR-0004）：mp 店员端 push（主形态，店员手机现场发货）；plus-ui owner 兜底 + 独占 rollback（reason 必填，高危隔离）。
- **退款解耦**（doc/10 §9.E3）：business_status=refunded → service 拦截推进（E6）；logistics_status 与 business_status 并行独立。

## AI 自测

### 1. 单测 11/11（AC11 ≥6 raw assertion）

```
$ mvn -o test -pl ruoyi-modules/ruoyi-gz-ord -Dtest='GzLogisticsServiceImplTest'
[INFO] Tests run: 11, Failures: 0, Errors: 0, Skipped: 0 -- in GzLogisticsServiceImplTest
[INFO] BUILD SUCCESS
```
覆盖：in_japan→dispatching happy（字段+审计）/ 漏录单号→报错 / 非法快递编码→报错 / E6 refunded 拦截 / dispatching→delivered happy / delivered 终态再推→报错 / 改单号 carrier_update 记 from/to / 改单号非派送态→报错 / owner 回退 happy（记 reason）/ 回退 in_japan→报错 / gacha 路由到 gz_gacha_order 表。
> owner-only 回退权限 = controller `@SaCheckPermission("gz:ord:logistics:rollback")`（Playwright/集成覆盖）；reason 非空 = DTO `@NotBlank`（controller `@Validated`）。

### 2. DDL 应用（真库，幂等 menu）

```
SELECT menu_id, menu_name, perms FROM sys_menu WHERE menu_id IN (11003,11034);
11003  物流推进  gz:ord:logistics:push       （owner 100 + staff 101）
11034  物流回退  gz:ord:logistics:rollback   （仅 owner 100）
```

### 3. plus-ui build:prod 绿 + mp type-check 0 错误 + mp vitest 374 全过

```
$ pnpm build:prod                     → ✓ built（OrderDetailDrawer 物流操作区打包）
$ pnpm type-check (miniapp)           → 0 error TS（staff-orders/detail.vue + api/gz-ord/logistics.ts）
$ pnpm test (miniapp vitest)          → Test Files 40 passed / Tests 374 passed
```

## SnailJob / 注意

- **无 SnailJob 任务**（物流推进是人工触发，非定时）。**无新建表**（物流字段前序日已内联）。**无 sys_job INSERT**。
- 订阅消息 hook（doc/10 §9.N7 / R6）：本卡未接 ApplicationEventPublisher（USER-103 订阅 hook 未就绪），留待 hook 就绪后接，不阻塞推进事务。

## Tier 2 可达（AC12）+ 人验项

- **mp 店员端入口 = 现成真入口**：店员账号登 mp → 个人中心「门店管理」→「订单查看」(GZ-ADMIN-201 已建) → 订单详情 → 物流推进操作区（≤4 次点击，无需临时入口）。
- **进 progress.md「人验」列**（mp 部分）：店员真机 happy path — 选订单 → 发往中国（9 选 1 快递 + 单号，漏录提交 disabled）→ 改单号一次 → 推到已签收；owner 在 plus-ui 回退（reason 必填）；停用 sys_user 后即踢、再调 401/403。
- 详见 testing-human.md。
