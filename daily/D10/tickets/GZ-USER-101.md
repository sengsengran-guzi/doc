# GZ-USER-101 — 订单聚合统一接口

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M5 §用户操作流程 §进入会员中心 步骤 4-5
**关联拆解**: doc/02-需求拆解.md §3.4 第 848-858 行
**关联 mockup**: design/mockup/order-list.html ⚠️ 本 ticket 为纯后端接口，无 UI 实现（mp UI 由 USER-102 接入消费）
**关联 ADR**: —（C1 跨业务订单聚合裁定见 doc/11 Changelog v0.2 / doc/10 §9）
**依赖**: GZ-ORD-104 ✅(D09) + GZ-GACHA-104 ✅(D09)

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§9 跨业务订单聚合 + 跨境物流流** §跨业务订单聚合（V1.1 GZ-USER-101/102）+ §统一订单字段（跨业务）+ §状态机 + §4 会员中心占位流 §V1.0 → V1.1 演进契约
- **字段表**：doc/11-字段权威表.md **§8.1 `gz_unified_order_view` 统一订单视图**（统一字段口径权威定义）+ §8.2 business_status → UI 统一状态映射 + §6.3 `gz_ord_order`（预购订单 schema）+ §7.4 `gz_gacha_order`（扭蛋衍生订单 schema）+ §A.7 物流字段口径（C1 简化 2 态 + 终态）
- **UI 参考**：doc/12 §MP-ORD-LIST（消费方页面，本 ticket 不实装 UI，但接口字段需对齐其消费需求）

## What

后端落统一订单聚合接口：跨 `gz_ord_order`（预购）+ `gz_gacha_order`（扭蛋）两类业务订单，按业务类型 tab 筛 + 时间倒序返回统一字段。mp 端 `/api/user/orders` 调本接口拿列表。

## AC（验收标准）

- [ ] **AC 1**：mp 端 `GET /app/gz/user/orders?bizType=&pageNum=&pageSize=` 接口（sa-token-app 权限 + `gz:user:orders:list` perm）；`bizType` 可选值 `all` / `preorder` / `gacha`，默认 `all`
- [ ] **AC 2**：返回字段严格按 doc/11 §8.1 `gz_unified_order_view` 定义：`orderNo` / `businessType` / `productSnapshot`（含 name / cover / spec 或 prizeName + machine + rarity）/ `totalAmount` / `businessStatus` / `logisticsStatus` / `cnCarrierCode`（L2 + 才有）/ `cnTrackingNo`（L2 + 才有）/ `addressSnapshot` / `createdAt` / `paidAt` / `deliveredAt`
- [ ] **AC 3**：业务类型聚合实现：service 层并发查 `gz_ord_order` + `gz_gacha_order` 两表（按 user_id + tenant_id 过滤），各自映射为统一 VO，合并后按 `createdAt DESC` 排序 + 分页（分页在合并后做，**不要**用 union all 单 SQL — 字段命名差异 + 各自 join snapshot 表更清晰）
- [ ] **AC 4**：`bizType` 筛只查对应单表（性能优化）；`bizType=all` 才并发双查
- [ ] **AC 5**：仅返回当前登录用户的订单（后端 `where user_id = ${current_user_id}`，前端 hide 不算防御）
- [ ] **AC 6**：`businessStatus` → UI 状态文案的映射**不在本接口做**，原样返回业务侧枚举字符串；mp 端按 doc/11 §8.2 映射表自行渲染 chip 文案
- [ ] **AC 7**：`logisticsStatus` 字段直接透传枚举值（`in_japan` / `in_china_dispatching` / `delivered`，C1 2 态 + 终态）；不做额外加工
- [ ] **AC 8**：分页 size 上限 50（防恶意大分页拖库）；返回标准 PageQuery 结构 `{rows: [...], total, pageNum, pageSize}`
- [ ] **AC 9**：单测 `GzUnifiedOrderServiceImplTest` 至少 3 个：(a) 仅扭蛋订单（bizType=gacha 筛）/ (b) 仅预购订单（bizType=preorder 筛）/ (c) 混合（bizType=all 时间倒序合并）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-user/`
  - `controller/applet/GzUserOrderMpController.java`（mp 路径 `/app/gz/user/orders`，新建）
  - `service/IGzUnifiedOrderService.java` + `service/impl/GzUnifiedOrderServiceImpl.java`（新建）
  - `domain/vo/UnifiedOrderVO.java`（统一字段 VO，按 doc/11 §8.1）
  - `domain/bo/UnifiedOrderQueryBo.java`（含 bizType / pageNum / pageSize）
  - **不落新 DDL**（查询服务，消费 D09 已建的 `gz_ord_order` + `gz_gacha_order` 表）
  - service impl 注入 `IGzOrdOrderService`（D09）+ `IGzGachaOrderService`（D09），调各自的 listByUser(userId, tenantId) 然后合并
- **小程序**：本 ticket 不动 mp，USER-102 才接入
- **测试**：D09 admin 端预先造 2 个扭蛋订单 + 3 个预购订单（不同时间） → mp 端 curl 调 `/app/gz/user/orders?bizType=all` 验返回 5 单 + 时间倒序；`bizType=gacha` 验返回 2 单

## 备注

### 强约束

1. **统一字段命名严格对齐 doc/11 §8.1**：任何不一致 → STOP 修 doc/11（CLAUDE.md §9.5 #1 改源头 doc）
2. **不创建 `gz_unified_order_view` 物理视图 / 物化视图**：V1.1 数据量小（千级），合并查询在 service 层做即可（doc/11 §8.1 说明字段定义是逻辑视图，不强制物理化）
3. **logisticsStatus 透传 C1 枚举值**：`in_japan` / `in_china_dispatching` / `delivered` 三选一，不要在接口层翻译为中文（mp 端按字典 `gz_logistics_status` 渲染）
4. **业务类型枚举只用 `preorder` / `gacha`**：不要出现 `bean`（拼豆预约不进订单聚合，PRD M5 §异常分支已裁定"拼豆数据不混在订单 tab"，doc/12 §MP-ORD-LIST 已删 4 tab 改 3 tab）
5. **不暴露内部字段**：`tenant_id` / `del_flag` / `session_key` 等内部字段一律过滤，VO 只含上述统一字段
6. **包名 `org.dromara.gz.user.*`**（CLAUDE.md §6 #4 业务包名规则）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | service 层并发合并（不写 union all SQL） | 两业务表字段语义差异大（预购 SKU vs 扭蛋奖品），SQL union 易出错；service 合并清晰可测 + 各自 join 各自的 snapshot 表 |
| D2 | `bizType` 单类筛走单查询 | 性能优化：避免不必要的另一表查询 |
| D3 | productSnapshot 多态 JSON | 扭蛋：`{prizeName, machine, rarity, cover}`；预购：`{name, cover, sku}`；前端按 businessType 分支渲染 |
| D4 | 分页在合并后做 | 数据量小（千级）OK；如未来上量 → V2 引入物化视图 + 分页下推（doc/11 §8.4 留底） |
| D5 | 不强制实时 join 用户表 | 用户表数据冷热分明，订单 view 内不放用户字段；前端从 token 拿 userId 即可 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | D09 两业务表字段不齐（logistics_status / cn_carrier_code / cn_tracking_no） | §0 自检：`DESC gz_ord_order` + `DESC gz_gacha_order` 验三字段存在；缺则 STOP 回 D09 收尾 |
| R2 | 合并后分页时全量扫两表，性能差 | V1.1 数据量极小（千级），不优化；V2 数据量上来后改物化视图 + 物理分页 |
| R3 | businessStatus 枚举值在两表里语义不同（如 `paid` 在预购是"已付待发"，在扭蛋是"已抽待发"）| AC 6 明确不在接口层做映射，mp 端按 doc/11 §8.2 映射表区分渲染 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
