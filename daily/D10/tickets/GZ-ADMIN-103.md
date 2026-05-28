# GZ-ADMIN-103 — 订单管理（三类聚合）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M7.3 订单管理
**关联拆解**: doc/02-需求拆解.md §3.5 第 936-946 行
**关联 mockup**: design/mockup/admin-orders.html ⚠️ V1.0/V1.1 设计冻结期：admin 走 ruoyi 默认 + plus-ui BizTable / Element Plus 默认组件，**不参考 mockup 视觉**；mockup 仅作页面结构 / 功能项参考。**底部物流推进面板 7 节点 UI 已作废**（C1 简化），本 ticket 仅做订单列表 + 详情，**物流推进 admin 侧由 ADMIN-104 在 D11 实施**
**关联 ADR**: —
**依赖**: GZ-ORD-104 ✅(D09) + GZ-GACHA-104 ✅(D09)

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md **§9 跨业务订单聚合 + 跨境物流流** §跨业务订单聚合（V1.1 GZ-USER-101/102 + GZ-ADMIN-103 通用接口）+ §状态机
- **字段表**：doc/11-字段权威表.md **§8.1 `gz_unified_order_view` 统一订单视图**（admin 端复用同一 VO） + §8.2 business_status → UI 统一状态映射 + §6.3 `gz_ord_order` + §7.4 `gz_gacha_order` + §A.5/A.6/A.7 状态字典
- **UI 参考**（设计冻结期）：doc/12 §AD-ORD-ORDERS §页面结构（toolbar / 表格列 / 详情抽屉）+ §关键约束（业务线分别核算 / 申请退款 owner 权限 / 物流回退仅 owner）

## What

admin 端订单管理三类聚合列表 + 详情。**列表按业务类型 tab + 状态 + 用户 + 时间筛**，详情**按业务类型展示差异块**（复用 USER-102 统一 view-model 逻辑）。**详情有"申请退款"按钮（仅 owner 权限可见）触发 GZ-PAY-103**。**本 ticket 不做物流推进逻辑**（D11 ADMIN-104）。

## AC（验收标准）

- [ ] **AC 1**：admin 端 plus-ui 页 `views/gz-ord/orders/index.vue`（菜单路径 `/orders`），plus-ui BizTable + Element Plus 默认风格
- [ ] **AC 2**：列表 toolbar：业务 tab（全部 / 扭蛋 / 预购）+ 状态筛 select（全部 / 待支付 / 待发货 / 运输中 / 已完成 / 已取消）+ 用户筛（按用户昵称 / openid 模糊搜）+ 时间范围 picker + 订单号搜索框
- [ ] **AC 3**：列表表格列：勾选 / 订单号 / 业务 chip（gacha 绿 / preorder 黄）/ 用户（昵称 + openid 截短）/ 商品 snapshot（thumb + 名称 + 规格 / 中奖物）/ 金额（元）/ 业务状态 chip（按 doc/11 §8.2 映射）/ 物流状态 chip（按 doc/11 §A.7 映射 C1 三态）/ 创建时间 / 操作（详情 / 申请退款 / 推进物流）
- [ ] **AC 4**：admin 端 `GET /system/gz/ord/orders?bizType=&status=&logisticsStatus=&userKeyword=&startAt=&endAt=&orderNo=&pageNum=&pageSize=` 接口（sa-token-staff perm `gz:ord:orders:list`）；复用 USER-101 的 IGzUnifiedOrderService 但绕过 `where user_id` 限制（admin 视角全租户可见，但仍 `where tenant_id`）
- [ ] **AC 5**：详情抽屉（el-drawer）按业务类型展示差异块：
  - **统一段**：订单号 / 业务类型 / 用户信息 / 总金额 / 业务状态 / 物流状态 / 创建时间 / 支付时间 / 收货地址 snapshot
  - **扭蛋差异块**：中奖物 snapshot（prizeName + cover + rarity）+ 机器名 + 抽奖时间
  - **预购差异块**：商品 snapshot（productName + cover）+ SKU 规格 snapshot + 数量 + 截止日 / 到货日
  - **物流卡**（C1 三态简化展示，复用 USER-103 的 BizLogisticsCard 逻辑或独立 admin 版组件）
- [ ] **AC 6**：详情底部操作区：
  - "申请退款"按钮 — **仅 owner 角色（sa-token role=owner）可见**，staff 完全 hide 不显示；点击触发 `POST /system/gz/pay/refund/apply` body=`{orderNo, refundAmount, reason}` → 调 GZ-PAY-103；如 PAY-103 未完工则按钮 disabled + tooltip "PAY-103 完工后可用"（不阻塞本日交付）
  - "推进物流"按钮 — 留**占位**，跳转到 ADMIN-104 的物流推进页（路径 `/logistics?orderNo=`，D11 实施）
- [ ] **AC 7**：业务线分别核算约束（合同 §4.1）：admin 列表导出 CSV 时（如有）按 bizType 分文件；本 ticket 不做导出，但服务层接口字段定义不混淆（不要算合计行混业务线）
- [ ] **AC 8**：admin perm：list `gz:ord:orders:list` / detail `gz:ord:orders:query` / refund `gz:ord:orders:refund`（owner only）；菜单插入 menu_id **9150-9170 段**（GZ-ORD admin 共用）
- [ ] **AC 9**：i18n 全覆盖（`gz-ord.orders.*`）；状态文案走字典 `gz_preorder_order_status` / `gz_gacha_order_status` / `gz_logistics_status`
- [ ] **AC 10**：单测：admin 列表接口 happy（混合 bizType=all 时间倒序）/ refund 接口 owner 通过 / staff 403

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-ord/`（或 `ruoyi-gz-common` admin 通用层 — 跨域查询）
  - `controller/GzOrdOrdersController.java`（admin 路径 `/system/gz/ord/orders`）
  - service 复用 `IGzUnifiedOrderService`（USER-101 已建），加 `listForAdmin(queryBo)` 方法（不带 user_id 过滤，带 tenant_id 过滤）
  - `controller/GzOrdRefundController.java` 或追加在 orders controller，路径 `/system/gz/pay/refund/apply`（如 PAY-103 已落在 gz-pay 模块则跨模块调，否则本 ticket 加一个 stub controller）
  - menu SQL `V<时间戳>__GZ-ADMIN-103-menu.sql`（menu_id 9150-9170 段）
- **Admin**：`code/main/plus-ui/src/`
  - `views/gz-ord/orders/index.vue`（列表）
  - `views/gz-ord/orders/components/OrderDetailDrawer.vue`（详情抽屉，按 bizType 分支渲染）
  - `views/gz-ord/orders/components/RefundDialog.vue`（退款表单 + 校验金额 ≤ 订单金额）
  - `api/gz-ord/orders.ts` + `api/gz-ord/refund.ts`
  - `lang/zh_CN/gz-ord.ts` + `en_US/gz-ord.ts`
- **小程序**：不动
- **测试**：单测 + admin 端走全流：列表筛选 / 详情切换业务类型差异 / owner 模拟退款 / staff 验权限 hide

## 备注

### 强约束

1. **退款按钮 owner only**：sa-token role 校验 + 前端 v-if 双重；staff 完全 hide（不是 disabled）
2. **业务线分别核算**（合同 §4.1）：列表 / 详情数据按 bizType 区分；不做跨业务合计 / 不交叉冲抵
3. **物流推进按钮本 ticket 占位**：D11 ADMIN-104 实施完整推进逻辑；本 ticket 只跳转占位
4. **C1 物流 3 态展示**：详情物流卡按 doc/12 §MP-ORD-DETAIL 同样 3 态卡；不画 7 节点时间线
5. **复用 USER-101 service**：跨域订单查询逻辑同一份；admin 视角只是绕过 user_id 限制 + 多筛选维度
6. **菜单 menu_id 9150-9170 段**（GZ-ORD admin 共用）；ADMIN-101 用 9100-9120，本 ticket 9150-9170 留出 9121-9149 给 GZ-ORD 其他 ticket（如 ADMIN-105 等）
7. **包名 `org.dromara.gz.ord.*`**

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | admin 列表复用 USER-101 service | DRY；admin 只是多一层"绕过 user_id 过滤"的 boolean 参数 |
| D2 | 详情抽屉 vs 单独详情页 | 抽屉更适合 admin 快速浏览批量订单；不打断列表上下文 |
| D3 | 申请退款独立 dialog（不抽屉嵌套）| 二级 modal 减少误操作；金额校验 + 二次确认 |
| D4 | 物流推进按钮占位跳转 ADMIN-104 路由 | 解耦：本 ticket 不依赖 D11 完工 |
| D5 | refund 走 PAY-103 接口（如未完工 → disabled）| 不阻塞本日交付 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | PAY-103 D08/D09 未完工 | AC 6 明确 disabled fallback；testing-human 时如未完工 Kevin 跳过退款功能验证 |
| R2 | admin 视角订单列表性能（数据量上来）| V1.1 数据量小（千级）；service 层合并查询足够；V2 上量后考虑物化视图 |
| R3 | sa-token role owner / staff 区分未配置 | §0 自检：`SELECT * FROM sys_role WHERE role_key IN ('owner', 'staff')` 验角色存在；缺则补 SQL 落 owner / staff 角色（合同甲方运营角色定义） |
| R4 | 业务状态枚举值在两表里语义不同 | doc/11 §8.2 已映射；前端按 bizType + status 组合 key 查文案，不直接 status → 文案 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
