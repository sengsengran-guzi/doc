# GZ-ADMIN-106 — 数据看板扩展（V1.1 交易盘面）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M7.9 数据看板（MVP 必看指标）
**关联拆解**: doc/02-需求拆解.md §3.5 第 983 行
**关联 mockup**: `design/mockup/admin-dashboard.html`（admin 概念参考；admin 走 ruoyi/Element Plus 默认审美，不套用 C 系统、不评判视觉、不逐像素还原；plus-ui el-row + el-col + el-card 默认）
**关联 ADR**: —
**依赖**: GZ-ADMIN-103（订单聚合）+ GZ-ADMIN-105（对账中心，本 ticket 复用其聚合 API）

---

## 必读权威文档（缺一不可）

- **字段表**：doc/11-字段权威表.md §4.6（4% 分成口径 — 本 ticket 数据源来自 ADMIN-105 聚合）
- **业务流**：doc/10-业务流权威图.md §6 物流推进流（"待发货订单数"卡片需要按 logistics_node 状态聚合，doc/10 §6 7 节点状态机）
- **UI 参考**（admin 走 ruoyi/Element Plus 默认审美，不套用 C 系统）：`admin-dashboard.html`（admin 概念参考，看大致布局 + 卡片数量 + 网格列数；**不还原**圆角 / 阴影 / 渐变 / icon 套件，plus-ui 默认 el-card 即可）

## What

admin 端「首页 → 数据看板」V1.1 扩展 — V1.0 已有的基础看板（订单数 / 用户数等）之上叠加 V1.1 交易盘面（GMV / 退款 / 实际到账 / 扭蛋指标 / 热销 Top 10 / 待发货提醒），一屏一目了然 V1.1 全业务状态。

## AC（验收标准）

- [ ] **AC 1**：admin 端 `views/index.vue`（V1.0 已建）追加 V1.1 区块（不新建独立页 — 与 V1.0 同一首页，新区块加分组标题"V1.1 交易盘面"）
- [ ] **AC 2**：新增卡片（el-row gutter=20 + el-col span=6 网格，每行 4 卡片，共 8 卡片 2 行）：
  - **今日订单数**：业务线 A（预定）+ 业务线 B（扭蛋）+ 拼豆预约（V1.0）三条数据并列展示
  - **今日 GMV**：业务线 A + B 两条数据并列展示（拼豆 V1.0 免费不计 GMV）
  - **本月累计 GMV**：业务线 A + B 两条
  - **本月退款**：业务线 A + B 两条
  - **本月实际到账**：业务线 A + B 两条（来自 ADMIN-105 对账中心聚合）
  - **扭蛋本月抽数 + 平均出货价值**：抽数总数 + 平均 SKU 中奖价值（已交付价值 / 抽数）
  - **热销预购商品 Top 10**：列表卡片（el-table mini，列：排名 / 商品名 / 销量 / GMV），跨度 span=12（占两列）
  - **待发货订单数**：聚合 `gz_order WHERE biz_line='A' AND logistics_node IN ('paid','domestic_warehouse')`，红色高亮（提醒甲方推进物流），点卡片跳转 ADMIN-104 物流推进页
- [ ] **AC 3**：数据源策略：
  - 单一聚合 API `GET /admin/gz/common/dashboard/v11-summary` 一次性返所有卡片数据（不要前端 8 次串行调）
  - 后端实现走 ADMIN-105 已有的 `IGzFinanceReconcileService.summary()` 复用 + 补少数特有聚合（扭蛋抽数 / 热销 Top 10 / 待发货数）
  - 查询不缓存（V1.1 数据量小 < 500ms 可接受）
- [ ] **AC 4**：刷新策略：
  - 页面进入时调 1 次
  - 右上角"刷新"按钮手动调
  - **不做轮询**（V1.1 不需要实时，避免无谓 DB 压力）
- [ ] **AC 5**：权限：
  - V1.1 区块所有卡片仅 **owner 可见**（perm `gz:dashboard:v11`）
  - staff 角色看 V1.0 老卡片，V1.1 区块隐藏（v-if）
- [ ] **AC 6**：单测覆盖：
  - happy path：聚合接口返回所有 8 卡片字段非空
  - 待发货订单数：插入 5 单 logistics_node='paid' + 3 单 'domestic_warehouse' → 期望返回 8
  - 热销 Top 10：mock gz_ord_item 销量数据 → 期望返回排名正确
  - 共 3 个测试方法
- [ ] **AC 7**：i18n：所有卡片标题走 `t('dashboard.v11.xxx')`

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-common/`（新建 dashboard 子包）
  - `controller/admin/GzDashboardAdminController.java`（admin 路径 `/admin/gz/common/dashboard`）
    - `GET /v11-summary` 一次性返所有卡片数据
  - `service/IGzDashboardService.java` + impl（聚合 ADMIN-105 的 FinanceReconcileService + 自有扭蛋/热销/待发货查询）
  - `domain/vo/DashboardV11SummaryVO.java`（统一返回结构）
  - 无 DDL（不新建表，菜单走 V1.0 已有的"首页"，不挂新菜单）
- **Admin 前端**：`code/main/plus-ui/`
  - `views/index.vue` 追加 V1.1 区块（不新建文件）
  - `views/dashboard/components/V11SummaryRow.vue`（8 卡片网格组件，独立组件便于 V1.1 区块整体 v-if 切换）
  - `api/gz-common/dashboard.ts` 加 `getV11Summary()`
- **测试**：mvn 单测 + 浏览器实操（看一屏 8 卡片全有数据 + 待发货卡片点击跳 ADMIN-104）

## 备注

### 强约束

1. **不做轮询**（V1.1 数据量小 + 看板不是实时屏）— 避免 DB 无谓压力
2. **聚合走单接口**（不要前端串行调 8 次）— 性能 + 用户体验
3. **数据源复用 ADMIN-105** — 不重写 4% 分成 / GMV / 退款 / 实际到账计算逻辑（避免双口径不一致风险，9.5 §1 改源头不要 patch 下游）
4. **owner 权限分流** — staff 看不到 V1.1 交易盘面（财务敏感）
5. **不动 V1.0 老看板**（仅追加 V1.1 区块）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 单聚合 API 一次返所有卡片 | 避免前端 8 次串行 + N+1 网络往返；后端单事务读 < 500ms 可接受 |
| D2 | 复用 ADMIN-105 的 FinanceReconcileService | 单一数据口径 / 避免双口径漂移 / 9.5 §1 改源头不要 patch 下游 |
| D3 | 不做缓存 | V1.1 数据量小直接查；引入缓存反而带 stale 风险（看板看 stale 数据让甲方质疑系统） |
| D4 | 待发货卡片点击跳转 ADMIN-104 | 看板 → 行动 的最短路径（甲方看到红色提醒立刻能推进物流） |
| D5 | V1.1 区块独立组件 V11SummaryRow.vue | 便于 owner / staff 权限切换 v-if + 后续 V2 整体替换 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 聚合 API 调用慢（一次查 8 个口径）| 单次查询走索引（已存 + ADMIN-105 v_gz_finance_daily 视图）实测 < 500ms 可接受；如压测发现 > 1s 切并行查询 |
| R2 | 热销 Top 10 数据稀疏（V1.1 上线初期没销量）| 卡片显示"暂无数据"占位 + el-empty 组件 |
| R3 | 待发货订单数与 ADMIN-104 实际数不一致（不同接口口径漂移）| 复用同一 SQL 片段 / 抽 `IGzLogisticsService.countByNodes(nodes)` 给两边调 |
| R4 | mockup admin-dashboard.html 视觉风格与 plus-ui 默认有偏差 | admin 走 ruoyi/Element Plus 默认审美（不套用 C 系统）— Kevin testing-human 不评判视觉、只评判功能（CLAUDE.md §7.5） |

### ADR 候选

- 无

---

## §revision（Kevin testing-human 后填，初始空）
