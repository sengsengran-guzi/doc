# GZ-ADMIN-103 — 订单管理（三类聚合，走 gz_pay_transaction 回查）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M7.3 订单管理
**关联拆解**: doc/02-需求拆解.md §3.5（admin 订单管理 + 退款按钮 `gz:pay:refund:apply` 口径，第 664 行）
**关联 mockup**: design/mockup/admin-orders.html ⚠️ admin 走 ruoyi/Element Plus 默认审美（**不套用 C 系统**）+ plus-ui BizTable / Element Plus 默认组件，**不参考 mockup 视觉**；mockup 仅作页面结构 / 功能项参考。**底部物流推进面板 UI 已作废**（C1 简化 2 态，物流推进 admin 侧由 D11 GZ-ADMIN-104 实施并下沉 mp），本 ticket 仅做订单列表 + 详情（含申请退款）
**关联 ADR**: doc/_adr/0005-cross-border-logistics-2state.md（C1 跨境物流 2 态 + 终态裁定，订单详情物流卡按 2 态展示）
**依赖**: GZ-ORD-104（预购订单 `gz_ord_order` 表）+ GZ-GACHA-104（扭蛋衍生订单 `gz_gacha_order` 表）+ GZ-PAY-001（`gz_pay_transaction` 已落地）；GZ-PAY-103（退款接口，**单向依赖** — 未完工不阻塞，按钮 disabled 兜底）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

> 业务流 + 字段表是 ticket 实施的"蓝图"，缺引用 = AI 凭字面猜实现 = 翻车前兆。
> admin ticket UI 走 ruoyi 默认，mockup 仅页面结构参考。

- **业务流**：
  - doc/10-业务流权威图.md **§9 跨业务订单聚合 + 跨境物流流**（聚合接口口径 + 物流 2 态状态机 + §9.E6 推进时状态校验）
  - doc/10-业务流权威图.md **§7 预定货品全流程**（preorder 业务态机 + 字段语义）
  - doc/10-业务流权威图.md **§8 扭蛋机抽奖全流程**（gacha 衍生订单业务态机 + 奖品 snapshot 语义）
- **字段表**：
  - doc/11-字段权威表.md **§8.1 `gz_unified_order_view` 统一订单视图**（逻辑视图 / service 层 UNION / `GzUnifiedOrderVo` 字段对齐表 + gacha 分支 `product_snapshot_json` 合并 5 字段规则）
  - doc/11-字段权威表.md **§8.2 business_status → UI 统一状态映射**（统一 chip 映射，admin 列表/详情状态 chip 复用同一映射）
  - doc/11-字段权威表.md **§4.2 `gz_pay_transaction`**（`business_type` / `business_order_no` / `amount_cent` / `status`，聚合入口）+ **§4.4 `gz_pay_refund`**（全额退款单 / `refund_amount_cent` / `triggered_by`）
  - doc/11-字段权威表.md **§6.3 `gz_ord_order`** + **§7.4 `gz_gacha_order`**（回查明细 + snapshot 字段）
  - doc/11-字段权威表.md **附录 A.5 / A.6 / A.7 / A.9**（业务态 / 物流态 / business_type 字典 label）
- **UI 参考**（admin ticket）：`design/mockup/admin-orders.html`（仅页面结构 / 功能项参考，不逐像素、不评判视觉；admin 走 ruoyi/Element Plus 默认审美）

## What

admin 端 plus-ui 订单管理三类聚合列表 + 详情。**聚合入口走 `gz_pay_transaction` 按 `business_type`（`preorder`/`gacha`/`test`）筛 + 回查对应业务订单表（`gz_ord_order` / `gz_gacha_order`）取明细**，统一映射成 `GzUnifiedOrderVo`（复用 GZ-USER-101 的 view-model）。详情按业务类型展示差异块（复用 GZ-USER-102 统一布局逻辑）。详情含"申请退款"按钮（owner 权限 `@SaCheckPermission("gz:pay:refund:apply")`）触发 GZ-PAY-103。**本 ticket 不做物流推进写入**（D11 GZ-ADMIN-104）。

## AC（验收标准）

- [ ] **AC 1**：admin 端 plus-ui 页 `views/gz-ord/orders/index.vue`，菜单挂 GZ-ADMIN 扩展段；plus-ui BizTable + Element Plus 默认风格，不套 C 系统、不调样式
- [ ] **AC 2**：列表 toolbar 筛选项：业务 tab（**全部 / 预购 / 扭蛋 / 测试单**，对应 `business_type` ∈ `preorder`/`gacha`/`test`，"全部"= 不传）+ 业务状态筛 select（按 doc/11 §8.2 统一 chip：待支付 / 待发货 / 运输中 / 已完成 / 已取消 / 已退款）+ 物流状态筛 select（在日本 / 已发往中国 / 已签收，按附录 A.7 三态）+ 用户关键词搜（昵称 / openid 模糊）+ 时间范围 picker（按 `paid_time` 或 `create_time`）+ 订单号搜索框（`business_order_no` 精确 / 前缀）
- [ ] **AC 3**：列表表格列：勾选 / 订单号（`business_order_no`）/ 业务 chip（preorder / gacha / test，走 `gz_business_type` 字典 label）/ 用户（昵称 + openid 截短，`test` 单可空）/ 商品 snapshot（thumb + 名称 + 规格：preorder 取 `product_snapshot_json`，gacha 取合并 5 字段 `name`/`cover`/`spec`(稀有度)）/ 金额（`amount_cent / 100` 元 + `¥`）/ 业务状态 chip（按 doc/11 §8.2 统一映射，按 `business_type` + `business_status` + `logistics_status` 组合 key）/ 物流状态 chip（按附录 A.7 三态）/ 创建时间 / 操作（详情 / 申请退款 / 推进物流占位）
- [ ] **AC 4**：admin 端接口 `GET /system/gz/ord/orders?businessType=&businessStatus=&logisticsStatus=&userKeyword=&startTime=&endTime=&orderNo=&pageNum=&pageSize=`（perm `@SaCheckPermission("gz:ord:orders:list")`）：
  - 实现口径 = **以 `gz_pay_transaction` 为主表分页**（含 `test` 单），按 `business_type` 回查 `gz_ord_order`（`business_type='preorder'`）/ `gz_gacha_order`（`business_type='gacha'`）补明细；`test` 单无业务订单表（`business_order_no` 为 NULL）则仅展示支付流水字段
  - 映射成 `GzUnifiedOrderVo`（复用 GZ-USER-101 `GzUnifiedOrderService` 的映射逻辑；admin 视角**不带 `where user_id` 过滤**，仍走 ruoyi `TenantLineInnerInterceptor` 自动 `where tenant_id` + `@TableLogic` 软删过滤）
  - **禁止**新建 `gz_order` 单表 / `gz_unified_order_view` 物理 VIEW / `biz_line`/`business_line` 列 / `gz_ord_item` 旧名
- [ ] **AC 5**：详情抽屉（el-drawer）按业务类型展示差异块（复用 GZ-USER-102 统一 view-model 多态渲染）：
  - **统一段**：订单号 / 业务类型 / 用户信息（昵称 + openid）/ 金额（元）/ 业务状态 chip / 物流状态 chip / 创建时间 / 支付时间（`paid_time`）/ 签收时间（`delivered_time`）/ 收货地址（`address_snapshot_json`，gacha 未补地址时显示"用户未补地址"）
  - **预购差异块**：商品 snapshot（`product_snapshot_json`：商品名 + 主图 image_id 解析 + IP + 截止日 / 到货日）+ SKU 规格 snapshot（`sku_snapshot_json`）
  - **扭蛋差异块**：获得物 snapshot（`prize_snapshot_json`：奖品名 + 图 image_id 解析 + 稀有度 rarity）+ 来源扭蛋机名（`machine_snapshot_json.name`）+ 抽奖/支付时间。**UI 文案用扭蛋语义**（获得 / 出现概率），**禁** 抽奖/中奖/开奖
  - **测试单**：仅展示支付流水字段（无业务/物流/地址块）
  - **物流卡**：C1 三态只读展示（在日本 / 已发往中国 + `cn_carrier_code` 字典中文 + `cn_tracking_no` / 已签收）；**不画 7 节点时间线 / 不引 `gz_logistics_node`**
- [ ] **AC 6**：详情底部"申请退款"按钮：
  - 走 `@SaCheckPermission("gz:pay:refund:apply")`（**不用 `@SaCheckRole` / 不做 owner 角色字符串判断**，权限由 admin 端把该 perm 仅授给 owner 角色实现）；无该 perm 的 staff 前端按钮不渲染（`v-hasPermi="['gz:pay:refund:apply']"`）+ 后端 403 双重
  - 点击 → 二次确认 dialog（**V1.1 仅全额退款，无金额 input**，展示"退款金额 = 订单金额 ¥X.XX（全额）"+ reason 选填）→ `POST /system/gz/pay/refund/apply` body=`{businessOrderNo, reason}` → 调 GZ-PAY-103
  - **单向依赖 PAY-103**：若 PAY-103 未完工（接口/Bean 不存在）→ 按钮 `disabled` + tooltip "PAY-103 完工后可用"（不阻塞本日交付）
- [ ] **AC 7**："推进物流"操作 — 留**占位**：列表/详情按钮跳转 D11 GZ-ADMIN-104 物流推进页（路由占位 `/logistics?orderNo=`）；本 ticket 不实现任何物流写入逻辑
- [ ] **AC 8**：业务线分别核算约束（合同 §4.1）：列表/详情按 `business_type` 区分展示，**不做跨业务合计行 / 不交叉冲抵**；service 层字段定义不混淆（preorder/gacha/test 各自独立）
- [ ] **AC 9**：admin perm + 菜单：list `gz:ord:orders:list` / detail `gz:ord:orders:query`；退款复用 `gz:pay:refund:apply`（GZ-PAY-103 已建则不重复 seed）。菜单 seed 落 **GZ-ADMIN 扩展段 menu_id 11007-11019**（11003 物流 / 11004 对账 / 11005 季度 / 11006 回收站 已占，本 ticket 取 11007 起）。迁移 `V202606111000__GZ-ADMIN-103-menu.sql`
- [ ] **AC 10**：i18n 全覆盖（`gz-ord.orders.*`）；状态文案走字典 `gz_ord_business_status` / `gz_gacha_business_status` / `gz_logistics_status` / `gz_business_type` / `gz_express_carrier`（不硬编码中文）
- [ ] **AC 11**：单测：① list 接口 happy（混合 `businessType` 全部时按 `paid_time DESC` 倒序、含 test 单）；② list 按 `businessType=gacha` 仅返扭蛋单；③ refund 接口有 `gz:pay:refund:apply` perm → 通过 / 无 perm → 403

> 纯 admin + 后端 ticket，**无 Tier 2 入口可达 AC**（不下沉 mp，CLAUDE.md §8.2）。mp 店员端订单查看是独立 ticket GZ-ADMIN-201。

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-ord/`（admin 订单管理放预购域，跨域查询复用 GZ-USER-101 service）
  - `controller/GzOrdOrdersController.java`（admin 路径 `/system/gz/ord/orders`，perm `gz:ord:orders:list/query`）
  - service 复用 `GzUnifiedOrderService`（GZ-USER-101 已建）：加 `listForAdmin(GzAdminOrderQueryBo)` 方法 — 以 `gz_pay_transaction` 为分页主表（含 test）按 `business_type` 回查业务订单表补明细，映射 `GzUnifiedOrderVo`；**不带 user_id 过滤**，tenant_id / del_flag 走拦截器
  - 退款入口：`POST /system/gz/pay/refund/apply`（perm `gz:pay:refund:apply`）— GZ-PAY-103 已落 `ruoyi-gz-common`/`ruoyi-gz-pay` 则跨模块调其 service；未落则本 ticket 加 stub controller（方法体抛"PAY-103 未完工"或返回 disabled 标记，前端据此 disable）
  - DDL：`ruoyi-admin/src/main/resources/db/migration/V202606111000__GZ-ADMIN-103-menu.sql`（menu_id 11007-11019，时间戳 > V202606051200）
  - 包名 `org.dromara.gz.ord.{controller,service,mapper,domain,dto}`
- **Admin**：`code/main/plus-ui/src/`
  - `views/gz-ord/orders/index.vue`（列表 + toolbar 筛选 + BizTable）
  - `views/gz-ord/orders/components/OrderDetailDrawer.vue`（详情抽屉，按 businessType 分支渲染，复用 USER-102 view-model 逻辑）
  - `views/gz-ord/orders/components/RefundConfirmDialog.vue`（退款二次确认，仅全额，无金额 input + reason 选填）
  - `api/gz-ord/orders.ts` + `api/gz-ord/refund.ts`
  - `lang/zh_CN/gz-ord.ts` + `lang/en_US/gz-ord.ts`
- **小程序**：不动（订单查看下沉 mp 是 GZ-ADMIN-201）
- **测试**：单测（AC 11）+ kevin-qa admin Playwright E2E（列表筛选 / 详情切换 preorder/gacha/test 差异块 / 有 perm 模拟退款 / 无 perm 退款按钮不渲染）

## 备注

### 强约束

1. **聚合走 `gz_pay_transaction` 回查**（README §4）：以支付流水为分页主表（财务真源，含 `test` 单），按 `business_type` 回查 `gz_ord_order` / `gz_gacha_order` 取业务明细。**禁止** `gz_order` 单表 / `gz_unified_order_view` 物理 VIEW / `biz_line`/`business_line`/A·B 列 / `gz_ord_item` 旧名
2. **退款 perm 口径**（拆解 §664 钉死）：`@SaCheckPermission("gz:pay:refund:apply")`，**不用 `@SaCheckRole`、不做 owner 角色字符串硬判断**；"仅 owner 可退款"由 admin 端把该 perm 只授给 owner 角色实现，代码层只查 perm
3. **退款 V1.1 仅全额**：一笔对一单，无金额 input；`gz_pay_refund.refund_amount_cent = 原 amount_cent`（部分退款 v2）。C 端无退款入口（仅文案"如需退款请联系客服"）
4. **物流 = C1 2 态 + 终态**（doc/10 §9 / ADR-0005）：详情物流卡按 `in_japan` / `in_china_dispatching`（+ `cn_carrier_code` 字典中文 + `cn_tracking_no`）/ `delivered` 三态只读展示。**禁** 7 节点 / `logistics_node` / `gz_logistics_node` 表 / 批次推进 / 物流时间线。物流推进写入由 D11 GZ-ADMIN-104（下沉 mp）
5. **统一状态 chip**（doc/11 §8.2）：列表/详情业务状态 chip 走"业务态 + 物流态"组合映射的统一 chip，不直接拿单一 `business_status` 翻译；按 `businessType` + `businessStatus` + `logisticsStatus` 组合 key 查文案
6. **盲盒语义**（仅 gacha 块）：UI 可见文案 / i18n key 用"扭蛋 / 获得 / 出现概率"；**禁** 抽奖 / 中奖 / 开奖。后端 enum / 字段可保留 `draw`（不强制改库）
7. **复用 GZ-USER-101 service + GZ-USER-102 view-model**：跨域订单映射同一份（`GzUnifiedOrderVo` / gacha 分支 5 字段合并规则 doc/11 §8.1）；admin 只是多"绕过 user_id 过滤 + 以 pay_transaction 为主表 + 申请退款按钮"
8. **menu_id 11007-11019**（GZ-ADMIN 扩展段；11003 物流 / 11004 对账 / 11005 季度 / 11006 回收站 已规划占用）
9. **金额 `_cent`（分）**：DB `amount_cent` / `refund_amount_cent`，UI 一律 `/100` 元 + `¥` 前缀；**禁** `_fen`
10. **包名 `org.dromara.gz.ord.*`**；`del_flag` 仅 2 值；`tenant_id VARCHAR(20) DEFAULT '1001'`、INSERT 不显式赋值

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | admin 聚合以 `gz_pay_transaction` 为分页主表回查业务订单表 | 财务真源；天然含 `test` 单（V1.0 通道测试），口径与对账/分成一致（doc/11 §4.2）|
| D2 | service 层映射复用 GZ-USER-101 `GzUnifiedOrderVo`，不建物理 VIEW | DRY；物理 VIEW 绕过 ruoyi 租户/软删拦截器易漏隔离（doc/11 §8.4 F8.1）|
| D3 | 详情抽屉而非独立详情页 | admin 快速浏览批量订单，不打断列表上下文 |
| D4 | 申请退款独立二次确认 dialog（仅全额无 input）| 减少误操作；V1.1 不支持部分退款故无金额输入 |
| D5 | refund 走 PAY-103 接口，未完工 → disabled | 单向依赖，不阻塞本日交付 |
| D6 | 物流推进按钮占位跳 GZ-ADMIN-104 路由 | 解耦：本 ticket 不依赖 D11 完工，物流写入主形态下沉 mp |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 上游表未实际建（gz_ord_order / gz_gacha_order / gz_pay_transaction 不存在）| **§0 自检 grep migration 目录确认上游表实际存在**（不假设 D08/D09 已 merge）：`ls .../db/migration/ \| grep -E 'GZ-ORD-104\|GZ-GACHA-104\|GZ-PAY-001'` + `grep -rl 'gz_ord_order\|gz_gacha_order\|gz_pay_transaction' .../db/migration/`，缺则 STOP 报 Kevin，不开工 |
| R2 | GZ-PAY-103 未完工 | AC 6 明确 disabled fallback + tooltip；testing-human 时如未完工跳过退款验证 |
| R3 | admin 视角订单列表性能（数据量上来）| V1.1 数据量小（千级）；以 pay_transaction 分页 + 批量回查业务订单（IN 查询，非 N+1）足够；V2 上量后评估物化 |
| R4 | 两业务表 business_status 枚举语义不同（preorder 有 created/cancelled，gacha 无）| doc/11 §8.2 已映射；前端按 `businessType` + `businessStatus` + `logisticsStatus` 组合 key 查统一 chip 文案，不直接 status → 文案 |
| R5 | gacha 订单 `address_snapshot_json` 可能为 NULL（用户未补地址）| 详情地址块判空显示"用户未补地址"；不报错 |

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D10/GZ-ADMIN-103 revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。
-->
