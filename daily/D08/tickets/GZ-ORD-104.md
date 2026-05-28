# GZ-ORD-104 ★ — 预购下单 + 支付 + 订单生成

**优先级**: P1
**复杂度**: M（V1.1 首日跨域事务 ⭐ — ORD ↔ PAY 协作，业务线 A 端到端打通核心，禁止快速过 §0 自检）
**关联 PRD**: doc/02-prd.md M3 §关键字段 § PreorderOrder + §状态机
**关联拆解**: doc/02-需求拆解.md §3.2 第 715-725 行
**关联 mockup**: design/mockup/order-confirm.html + pay-result.html
**关联 ADR**: —（如本 ticket 实施时需决策"业务回调 handler 内事务边界"等可新建 ADR-V1.1-0002）
**依赖**: GZ-ORD-103 + GZ-PAY-101

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡 + ★ 重点反复读）

- **业务流**：doc/10-业务流权威图.md
  - §6 V1.1 演进流 §6.1（PAY-101 同日新增的业务支付统一流）+ §6.5（ORD-103 实施时已写的预购下单流）+ **本 ticket 实施前在 §6.6 补"预购支付回调与状态机闭环"段**
  - **§预购订单状态机**：`created → paid → in_logistics → delivered → closed`；`cancelled` 仅 `created`（未支付）态可达
- **字段表**：doc/11-字段权威表.md
  - **§6.3 gz_ord_order 预购订单主表**（完整 DDL — 含商品 + SKU + 地址 snapshot 字段，本 ticket 落 DDL 锚定）
  - §6.4 物流字段（C1 简化 — 国内单号 + 物流状态独立字段，V1.1 不接物流商 API）
  - **§6.5 商品状态字段口径**（再次确认 status='on' AND deadline 校验）
  - §4.1 gz_pay_order（与本 ticket gz_ord_order 通过 pay_order_no 关联）
- **UI 参考**：mp `order-confirm.html` 提交按钮 + `pay-result.html` 支付结果页

## What

用户在 ORD-103 确认订单页点「提交订单」→ 完整下单 + 支付 + 订单生成端到端流程：

1. **提交订单接口**（事务）：
   - 校验登录 / 商品 status / deadline / SKU 库存（与 ORD-103 校验同款，兜底）
   - 试扣 SKU 库存（ORD-101 tryDeductStock 乐观锁；失败 → 返回 SKU_OUT_OF_STOCK）
   - 落 gz_ord_order 行 status='created' + 商品 / SKU / 地址 snapshot
   - 调 PAY-101 createOrder（bizType=PREORDER）→ 拿 prepay_id + paySign 等支付参数
   - 返回支付参数给 mp 端
2. **mp 端调起微信支付**：`wx.requestPayment(paySign)` → 用户在微信付款界面确认
3. **支付回调链路**（PAY-101 handler 注册）：
   - 注册 `PreorderPayCallbackHandler implements IPayCallbackHandler`，supportedType = PREORDER
   - onPaid(payOrder) → UPDATE gz_ord_order SET status='paid' + paid_at + pay_order_no
4. **mp 端跳转支付结果页**：
   - 支付成功 → 跳 `/pages/ord/pay-result?orderId=xxx`（pull gz_ord_order 状态展示）
   - 支付取消 / 失败 → 留在确认页 + toast「支付未完成」+ 允许重新调起（订单仍 created，下单不重复落库）
5. **未支付订单取消**：用户主动 cancel（订单 status='created' 可 cancel）→ UPDATE status='cancelled' + 回滚 SKU 库存（stock_left += quantity）

## AC（验收标准）

- [ ] **AC 1**：DDL `V<ts>__GZ-ORD-104-create-gz_ord_order.sql` 落 gz_ord_order 表（按 doc/11 §6.3）：
  - id / order_no (UNIQUE) / user_id / open_id_snapshot / business_line = 'preorder'（4% 分成核算 ⭐）/
  - product_id / sku_id / quantity /
  - product_name_snapshot / product_cover_snapshot / sku_spec_snapshot / sku_price_fen_snapshot /
  - total_fen / address_snapshot JSON（含 contact / phone / province / city / district / detail）/
  - status enum(`created`/`paid`/`in_logistics`/`delivered`/`closed`/`cancelled`) /
  - pay_order_no（关联 gz_pay_order.order_no，订单创建时为空，调 PAY-101 后回填）/
  - paid_at / shipped_at / delivered_at /
  - cn_logistics_no VARCHAR(64)（国内物流单号，C1 字段，V1.1 admin 手动录入）/
  - logistics_status enum(`pending_arrival`/`arrived_warehouse`/`in_cn_logistics`/`delivered`) DEFAULT 'pending_arrival' /
  - cancel_reason VARCHAR(200) / cancelled_at /
  - 公共字段 + tenant_id
  - 索引 `idx_user_status_created` `idx_business_line_paid_at`（4% 对账用）`idx_status` `uk_order_no`
- [ ] **AC 2**：mp 端 `POST /app/gz/ord/order/submit`（事务）：
  - sa-token 校验 + 拿 user_id + open_id
  - 参数：productId + skuId + quantity + addressId
  - 校验商品 status='on' + deadline_at > NOW() → 否则 errCode=`PRODUCT_OFF`
  - 校验地址归属 user（gz_user_address.user_id 必须等于当前 user）
  - 调 `IGzOrdSkuService.tryDeductStock(skuId, quantity)` → false 时 errCode=`SKU_OUT_OF_STOCK`
  - INSERT gz_ord_order status='created'（snapshot 字段完整落库）
  - 调 PAY-101 `IPayOrderService.createOrder(BizType.PREORDER, ordOrderNo, totalFen, openId, description)` → 拿支付参数
  - UPDATE gz_ord_order SET pay_order_no = ?  WHERE id = ?
  - 返回 `{ordOrderId, ordOrderNo, payParams: {prepayId, paySign, timeStamp, nonceStr, signType, package}}` 给前端
  - 事务失败 → 库存回滚 + 不调 PAY-101（事务边界：库存 + 订单 INSERT 在同事务；PAY-101 调用在事务提交后异步 — **避免 PAY 内部失败导致订单 INSERT 回滚但库存已扣**）
  - 实施细节：`@Transactional` 事务方法落 INSERT；事务提交后用 `TransactionSynchronizationManager.registerSynchronization` 触发 PAY-101 调用；PAY-101 失败 → UPDATE gz_ord_order.status='cancelled' + 库存回滚（异步补偿）
- [ ] **AC 3**：注册 PAY-101 SPI handler：
  - `@Component class PreorderPayCallbackHandler implements IPayCallbackHandler`
  - `supportedType() = BizType.PREORDER`
  - `onPaid(payOrder)`：按 payOrder.bizOrderId 查 gz_ord_order → UPDATE status='paid' + paid_at = payOrder.paidAt
  - 异常：抛 RuntimeException 触发 PAY-101 整体回滚（PAY 仍 pending，等下次回调 / PAY-102 cron 补单）
- [ ] **AC 4**：mp 端 `pages/ord/order-confirm.vue` 提交按钮接入：
  - 点提交 → 调 submit 接口 → 成功后 `uni.requestPayment(payParams)`
  - 支付成功回调 → 跳 `/pages/ord/pay-result?orderId={ordOrderId}`
  - 支付取消 → toast「支付未完成，可在订单中心继续支付」+ 跳订单列表
  - 支付失败 → 同取消（不区分 — wx requestPayment fail 包含多种原因）
- [ ] **AC 5**：mp 端 `pages/ord/pay-result.vue` 支付结果页：
  - onLoad 拉 `GET /app/gz/ord/order/{id}` 查订单
  - status='paid' → 显示「支付成功」+ 商品信息 + 「查看订单」CTA（跳 ORD-105 详情）
  - status='created' → 显示「支付处理中」+ 自动每 3s 轮询订单状态（轮询 10 次仍 created 提示「如已扣款请稍后查看订单」+ 客服入口）
  - status='cancelled' → 显示「订单已取消」+ 跳商品详情 CTA
- [ ] **AC 6**：mp 端 `POST /app/gz/ord/order/cancel/{id}`：
  - 仅 status='created' 可 cancel
  - UPDATE status='cancelled' + cancelled_at + 回滚 SKU 库存（stock_left += quantity）
  - **注意**：已 paid 订单不允许 cancel；走 PAY-103 退款流程
- [ ] **AC 7**：单测 ⭐ 必须覆盖：
  - happy path：提交订单 → 库存扣减 → INSERT 成功 → PAY 调用成功 → 模拟回调 → status paid
  - 库存不足 → 不落 order
  - 商品过期 → 不落 order
  - PAY 调用失败 → order 状态 cancelled + 库存回滚（异步补偿）
  - 重复回调 → 仅第一次更新 status（依赖 PAY-101 幂等）
  - 取消订单 → 库存回滚
  - 共 ≥ 5 个测试方法
- [ ] **AC 8**：**reports 必须包含完整端到端 mock 跑通日志**（dev profile sandbox + Postman 模拟微信回调）

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-ord/`
  - `controller/applet/GzOrdOrderMpController.java`（路径 `/app/gz/ord/order`）：submit / cancel / getDetail
  - `service/IGzOrdOrderService.java` + `service/impl/GzOrdOrderServiceImpl.java`（事务边界 + 异步 PAY 调用 + 补偿逻辑）
  - `service/callback/PreorderPayCallbackHandler.java`（PAY-101 SPI 注册）
  - `domain/GzOrdOrder.java` + req/vo（snapshot 字段完整）
  - `mapper/GzOrdOrderMapper.java`
  - `enums/OrdOrderStatusEnum.java` + `LogisticsStatusEnum.java`
  - DDL × 1
- **小程序**：
  - `pages/ord/order-confirm.vue`（ORD-103 已建，本 ticket 接入提交逻辑）
  - `pages/ord/pay-result.vue`（新建）
  - `composables/useOrderSubmit.ts`（提交编排：submit → requestPayment → 跳转）
  - `api/gz-ord.ts` 加 submitOrder / cancelOrder / getOrderDetail
- **测试**：mvn 单测 ≥ 5 个 + 微信开发者工具走全流程 + Postman 模拟微信回调

## 备注

### 强约束 ★

1. **事务边界**（doc/10 §6.6 锚定）：
   - 事务 A（同步）：库存扣减 + INSERT gz_ord_order — 一致性强保证
   - 事务 B（异步，事务 A 提交后）：调 PAY-101 createOrder — 失败时走补偿
   - 不允许把 PAY 调用放在事务 A 内（PAY 是远程调用 + 业务方注册 handler — 嵌套事务边界混乱）
2. **business_line='preorder'**（合同 §4.1 业务线 A）— gz_ord_order 落库时 + gz_pay_order 落库时双重写入；4% 分成对账走 gz_pay_order.business_line 分流
3. **snapshot 字段必须完整**（doc/11 §6.3 锚定，与 ORD-101 同步）：商品名 / 主图 / SKU 规格名 / 单价分 / 数量 / 地址完整字段 — 至少这 6 类
4. **订单状态机严格**：created → paid → in_logistics → delivered → closed；cancelled 仅 created 可达；不允许跳态
5. **已 paid 订单不允许 cancel** — 走 PAY-103 退款
6. **轮询防永久 pending**：mp pay-result 页轮询 10 次（30s）仍未 paid → 提示用户 + 客服入口（不阻死页面）
7. **i18n 强制**
8. **menu_id 不涉及**（mp 路径）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 ⭐ | 事务 A（订单 INSERT）+ 事务 B（PAY 调用）拆分 | 远程调用不能嵌进 DB 事务；典型补偿事务范式 |
| D2 | PAY 调用失败异步补偿（订单 cancel + 库存回滚） | 用户重试时不会双重扣库存；体验：提示「支付准备失败请重试」 |
| D3 | snapshot 字段完整存（不存外键关联反查） | 商品下架 / SKU 改名后历史订单仍可展示原貌 |
| D4 | 地址 snapshot 用 JSON 字段（不分多列） | 地址字段多（contact/phone/province/city/district/detail）+ 不需要单字段查询 |
| D5 | 取消时库存回滚（不是软扣减） | 库存只扣实际成功订单，取消即释放 |
| D6 | 支付结果页轮询而非长连接 | uni-app 长连接复杂 + 流量小不必要 |

### 风险提示 ★

| # | 风险 | 缓解 |
|---|---|---|
| R1 ⭐ | 事务 A 提交后 PAY 调用前进程崩溃 → 订单 created 状态永远停 | 用户重进订单页可见 created + 「继续支付」CTA → 调 PAY-101 重新 createOrder（同 bizOrderId 幂等） |
| R2 | 用户主动 cancel 同时回调到达 → 状态竞争 | cancel 接口 `SELECT FOR UPDATE` 行锁 + 检查 status='created' 才允许 cancel |
| R3 | 库存乐观锁失败 ≥ 3 次（高并发） | V1.1 预购并发预计低，3 次重试足够；失败抛 SKU_OUT_OF_STOCK 用户重试 |
| R4 | 商品 deadline 在提交瞬间过期 | 提交时再校验 `deadline_at > NOW()` 兜底 |
| R5 | mp pay-result 页轮询过频影响后端 | 间隔 3s + 上限 10 次 + 后端读 gz_ord_order 只读查询，无压力 |
| R6 | 业务回调 handler 抛异常 → PAY-101 整体回滚 → PAY 仍 pending | 设计如此（PAY-101 §强约束 #1）；PAY-102 cron 兜底重试；handler 内 try-catch 仅吞业务无关异常 |
| R7 | open_id_snapshot 字段必要性 | 用户后续注销 / openid 关联变更，订单仍能查；snapshot 模式一致性 |
| R8 | cancelled 订单库存回滚错误（已被其他用户抢扣） | 乐观锁 / 原子 UPDATE 保证（stock_left += quantity 不依赖 version） |

### ADR 候选

- **ADR-V1.1-0002**：补偿事务实现方式（事务监听器 vs Spring 事件 vs MQ） — 默认 D1 事务监听器（TransactionSynchronizationManager）；如发现可靠性问题再考虑 MQ

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
