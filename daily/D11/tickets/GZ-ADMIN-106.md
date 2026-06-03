# GZ-ADMIN-106 — 数据看板扩展（V1.1 交易盘面：单聚合接口）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M7.9 数据看板（MVP 必看指标）
**关联拆解**: doc/02-需求拆解.md §3.5
**关联 mockup**: `design/mockup/admin-dashboard.html`（admin 概念参考；admin 走 ruoyi/Element Plus 默认审美，不套用 C 系统、不评判视觉、不逐像素还原；plus-ui el-row + el-col + el-card 默认）
**关联 ADR**: —
**依赖**: GZ-ADMIN-103（订单聚合，提供 `gz_ord_order` / `gz_gacha_order` 查询基座）+ GZ-ADMIN-105 ⭐（对账中心，本 ticket **复用其 service**，必须等 105 完工后起）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：
  - doc/10-业务流权威图.md **§10 对账中心流**（看板 GMV / 退款 / 实际到账卡片复用对账口径）
  - doc/10-业务流权威图.md **§8 扭蛋机抽奖全流程**（本月开盒数 / 平均出货价值数据源 = `gz_gacha_draw`；**盲盒语义：开盒 / 获得，禁抽奖 / 中奖**）
  - doc/10-业务流权威图.md **§9 跨境物流流（C1 2 态 + 终态）**（待发货订单数 = `logistics_status='in_japan'`，**不是 logistics_node / 不是 7 节点**）
- **字段表**：
  - doc/11-字段权威表.md **§4.6 4% 分成核心计算口径**（GMV / 退款 / 实际到账逐字口径，本 ticket 不重写，复用 ADMIN-105 service）
  - doc/11-字段权威表.md **§9.1 / §9.2 `gz_recon_daily` / `gz_recon_monthly`**（本月累计 GMV / 退款 / 实际到账卡片源）
  - doc/11-字段权威表.md **§6.3 `gz_ord_order`**（`business_status` / `logistics_status` — 待发货聚合）+ **§6.2 `gz_ord_product.sales_count`**（热销 Top10）
  - doc/11-字段权威表.md **§7.3 `gz_gacha_draw`**（开盒数 + `prize_snapshot_json` 公示价值 → 平均出货价值）
  - doc/11-字段权威表.md **§10.3 menu_id 分段**（本 ticket 复用 V1.0 已建 11001 数据看板，不新增 menu_id）
- **UI 参考**（admin 走 ruoyi/Element Plus 默认审美，不套用 C 系统）：`admin-dashboard.html`（看大致布局 + 卡片数量 + 网格列数；**不还原**圆角 / 阴影 / 渐变 / icon 套件，plus-ui 默认 el-card 即可）

## What

admin 端「首页 → 数据看板」V1.1 扩展 — 在 V1.0 已有基础看板之上叠加 V1.1 交易盘面（今日订单数 / 今日 GMV / 本月累计 GMV·退款·实际到账 / 扭蛋本月开盒数+平均出货价值 / 热销预购 Top10 / 待发货订单数），所有卡片按 `gz_pay_transaction.business_type` 分业务线 A（preorder）/ B（gacha），由**一个聚合接口一次性返回**，不前端多次串行调。

## AC（验收标准）

- [ ] **AC 1**：admin 端 `views/index.vue`（V1.0 已建首页）追加 V1.1 区块（不新建独立页，新区块加分组标题"V1.1 交易盘面"）；**复用 V1.0 已建 menu_id 11001（数据看板），不新增 menu_id**。
- [ ] **AC 2**：卡片清单（el-row gutter=20 + el-col 网格，admin 默认样式），每张交易卡片**按 business_type 分 A（preorder）/ B（gacha）两条数据并列**：
  - **今日订单数**：A / B 两条（统计当日新增订单笔数）
  - **今日 GMV**：A / B 两条（当日 `gz_pay_transaction` status=paid 的 `amount_cent` 求和，分 / 元换算后显示）
  - **本月累计 GMV**：A / B 两条
  - **本月退款**：A / B 两条
  - **本月实际到账**：A / B 两条（= GMV − 退款 − 通道费，复用 ADMIN-105 对账 service / `gz_recon_monthly`）
  - **扭蛋本月开盒数 + 平均出货价值**：开盒总数（COUNT `gz_gacha_draw` 本月）+ 平均出货价值（`SUM(prize_snapshot_json 公示价值_cent) / 开盒数`，分 / 元换算）；**盲盒语义：文案用「开盒数」「平均出货价值」，禁「抽奖次数」「中奖价值」**
  - **热销预购商品 Top10**：el-table（列：排名 / 商品名 / 销量 / GMV），数据源 `gz_ord_product.sales_count` 降序取 10 条（或本月 paid 订单聚合）
  - **待发货订单数**：聚合 `gz_ord_order WHERE business_status='paid' AND logistics_status='in_japan'`（**用 `logistics_status`，禁 `logistics_node` / 7 节点 / `gz_logistics_node`**），红色高亮提醒甲方推进物流；点卡片跳转 ADMIN-104 物流推进页
- [ ] **AC 3**：**单一聚合接口** `GET /admin/gz/recon/dashboard/v11-summary` 一次性返所有卡片字段（订单数 / GMV / 退款 / 实际到账 / 扭蛋 / 热销 Top10 / 待发货），**禁止前端多次串行调**；前端 1 个 `getV11Summary()` 拿全量数据后本地分发到各卡片。
- [ ] **AC 4**：实际到账 / 本月 GMV / 退款卡片**复用 ADMIN-105 已有对账 service**（如 `IGzReconService`），**不重写 4% 分成 / GMV / 退款 / 实际到账计算逻辑**（避免双口径漂移，CLAUDE.md §9.5 改源头不 patch 下游）。
- [ ] **AC 5**：刷新策略：页面进入调 1 次 + 右上角"刷新"按钮手动调；**不做轮询**（V1.1 数据量小 < 500ms，避免无谓 DB 压力）。
- [ ] **AC 6**：权限：V1.1 交易盘面区块 `@SaCheckPermission("gz:recon:dashboard:v11")`（owner 授权，同租户 1001）；无权限角色看 V1.0 老卡片，V1.1 区块隐藏（v-if 按 perm）。**走 `@SaCheckPermission`，不用 `@SaCheckRole`**。
- [ ] **AC 7**：单测覆盖（共 3 个测试方法）：
  - happy path：聚合接口返回所有卡片字段非空（订单数 / GMV / 退款 / 实际到账 / 扭蛋 / 热销 / 待发货）
  - 待发货聚合：插入 5 单 `business_status='paid' AND logistics_status='in_japan'` + 2 单 `logistics_status='in_china_dispatching'` → 期望待发货数 = 5
  - 业务线分流：A（preorder）/ B（gacha）订单各插 N 单 → 期望今日订单数 / GMV 按 `business_type` 正确分流，`business_type='test'` 单 exclude
- [ ] **AC 8**：i18n：所有卡片标题走 `t('dashboard.v11.xxx')` + `zh_CN.ts` / `en_US.ts`；扭蛋卡片文案走盲盒语义 key（如 `dashboard.v11.gachaOpenCount` / `gachaAvgValue`），不出"抽奖 / 中奖"。

> 纯 admin + 后端 ticket，**无 mp 改动 → 跳过 Tier 2 入口可达 AC**（CLAUDE.md §8.2）。

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/`（看板聚合放对账域 `org.dromara.gz.recon.*`，与 ADMIN-105 同域便于复用其 service）
  - `controller/GzReconDashboardController.java`（admin 路径 `/admin/gz/recon/dashboard`）
    - `GET /v11-summary` — `@SaCheckPermission("gz:recon:dashboard:v11")`，一次性返所有卡片数据
  - `service/IGzReconDashboardService.java` + impl
    - 复用 ADMIN-105 `IGzReconService`（本月 GMV / 退款 / 实际到账，A / B 分流）
    - 自有聚合：今日订单数·GMV（按 `gz_pay_transaction.business_type` + status=paid）/ 扭蛋开盒数+平均出货价值（`gz_gacha_draw`）/ 热销 Top10（`gz_ord_product.sales_count`）/ 待发货数（`gz_ord_order WHERE business_status='paid' AND logistics_status='in_japan'`）
  - `domain/vo/GzDashboardV11SummaryVO.java`（统一返回结构，含 A / B 分流子结构 + Top10 list）
  - **无 DDL**（不新建表）；**无新增 menu_id**（复用 V1.0 11001 数据看板）
- **Admin 前端**：`code/main/plus-ui/`
  - `views/index.vue` 追加 V1.1 区块（不新建文件）
  - `views/dashboard/components/V11SummaryRow.vue`（V1.1 区块独立组件，便于按 perm 整体 v-if 切换 + 后续 v2 替换）
  - `api/gz-recon/dashboard.ts` 加 `getV11Summary()`
  - 待发货卡片点击 → `router.push` 到 ADMIN-104 物流推进页（V1.1 区块内最短「看板 → 行动」路径）
- **测试**：mvn 单测（3 方法）+ Playwright E2E（kevin-qa Tier 1B：登录 owner → 进首页 → V1.1 区块 8 卡片有数据 → 待发货卡片点击跳 ADMIN-104）

## 备注

### 强约束

1. **聚合走单接口**（不前端串行调）— 性能 + 一致快照（同一时刻读，避免卡片间口径漂移）。
2. **GMV / 退款 / 实际到账复用 ADMIN-105 service** — 不重写 4% 分成 / GMV / 退款 / 通道费计算（双口径漂移 = 4% 分成兑现风险，CLAUDE.md §9.5 §1 改源头不 patch 下游）。
3. **待发货口径 = `business_status='paid' AND logistics_status='in_japan'`** — 用 C1 2 态字段 `logistics_status`，**禁 `logistics_node` / 7 节点 / `gz_logistics_node` / 批次归集 GROUP BY**。
4. **业务线分流统一走 `gz_pay_transaction.business_type`**（`preorder`=A / `gacha`=B，`test` exclude）— **禁 business_line / biz_line / A·B 列**。
5. **扭蛋卡片盲盒语义**：UI 可见文案 / i18n key 用「开盒 / 获得 / 出货价值」，**禁「抽奖 / 中奖 / 开奖」**（后端 enum / 字段可保留 draw）。
6. **不做轮询 / 不做缓存**（V1.1 数据量小直查；缓存反带 stale 风险，看板看 stale 数据让甲方质疑系统）。
7. **不动 V1.0 老看板**（仅追加 V1.1 区块）；金额统一 `_cent` 存储，前端换算元显示（**不用 `_fen`**）。
8. **权限走 `@SaCheckPermission`**（owner 授权，同租户 1001），不用 `@SaCheckRole`。

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 单聚合 API 一次返所有卡片 | 避免前端多次串行 + N+1 网络往返；后端单次读 < 500ms 可接受；同一快照口径一致 |
| D2 | 复用 ADMIN-105 `IGzReconService`（看板聚合放 `gz.recon.*` 同域）| 单一数据口径 / 避免双口径漂移 / CLAUDE.md §9.5 §1 改源头不 patch 下游 |
| D3 | 不做缓存 / 不做轮询 | V1.1 数据量小直查；缓存带 stale 风险（看板看旧数据 → 甲方质疑系统） |
| D4 | 待发货卡片点击跳 ADMIN-104 | 「看板 → 行动」最短路径（甲方看红色提醒立刻能推进物流） |
| D5 | V1.1 区块独立组件 V11SummaryRow.vue | 便于按 perm v-if 整体切换 + 后续 v2 整体替换 |
| D6 | 复用 V1.0 menu_id 11001（数据看板），不新增 menu | V1.1 是同一首页区块扩展，非独立页面（doc/11 §10.3） |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | **§0 自检假设上游表已建（实际可能为空脚手架）** | §0 自检 **grep migration 目录确认 `gz_ord_order` / `gz_gacha_order` / `gz_gacha_draw` / `gz_recon_monthly`（ADMIN-105 已建）/ `gz_pay_transaction` 实际存在**，不假设上游已建；缺则 STOP 报 Kevin（先回 ADMIN-103/105 收尾） |
| R2 | 聚合接口一次查多口径慢 | 单次走索引（`gz_ord_order (tenant_id, logistics_status)` / `gz_pay_transaction (business_type, status, paid_time)` 已存 + ADMIN-105 `gz_recon_monthly`）实测 < 500ms；如压测 > 1s 切并行查询 |
| R3 | 热销 Top10 数据稀疏（V1.1 上线初期无销量） | 卡片显示 el-empty 占位"暂无数据" |
| R4 | 待发货数与 ADMIN-104 实际数口径漂移 | 复用同一 SQL 片段口径（`business_status='paid' AND logistics_status='in_japan'`），如 ADMIN-104 已抽 count service 则直接调 |
| R5 | 实际到账 / GMV 与对账中心数对不上（双口径） | 强制复用 ADMIN-105 `IGzReconService`，不在看板侧重算（D2） |
| R6 | mockup admin-dashboard.html 视觉与 plus-ui 默认有偏差 | admin 走 ruoyi/Element Plus 默认审美（不套用 C 系统）— Kevin 不评判 admin 视觉、只评判功能（CLAUDE.md §7.5） |

### 推进姿态（Kevin 决策 1 = Mock 全链路自测）

- 看板数据源 `gz_pay_transaction` / `gz_gacha_draw` / `gz_ord_order` 在 **`gz.pay.client.mode=mock`** 下由 D08/D09 mock 全链路产生的交易/抽奖/订单数据驱动；看板聚合 + 单测在 mock 数据上闭环。
- 真实商户号 / 0.01 元端到端不影响本 ticket（看板只读聚合，不发起支付）。

### ADR 候选

- 无

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D11/GZ-ADMIN-106 revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。
-->
