# GZ-ORD-104 完工报告 — 预购下单跨域事务

> V1.1 第一个跨域事务：扣 SKU 库存 + INSERT gz_ord_order(snapshot) + 调 PAY-101 写 gz_pay_transaction（同事务），
> 支付回调按 PREORD- 前缀 SPI 路由到下沉 gz-ord 的 preorder handler → 订单 created→paid；物流默认 in_japan。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（sensenran 项目目录非独立 git 仓库，`git rev-parse` 无 toplevel；不 commit，符合 ticket 收尾要求） |
| 上游 gz_ord_product/gz_ord_sku（ORD-101 V202606060900） | ✅ grep 确认存在 + stock_total/stock_remain 字段（NULL=无限） |
| 上游 gz_pay_transaction business_type/fee_cent/version（PAY-001 V202606041200） | ✅ grep 确认 70/77/84 行 |
| 上游 gz_user_address（USER-003 V202606031100） | ✅ migration 存在；IGzUserAddressService.getByIdForUser 非本人返回 null |
| gz_user.openid（GzUserVO.openid） | ✅ 第 36 行 |
| 当前 migration 最大版本 | V202606061301（PAY-103 menu）；本卡 DDL = V202606061400（> 1301 ✅） |
| ADR-0005 已读（C1 物流 2 态） | ✅ logistics_status 仅 3 字段 + 默认 in_japan，无 node 表 |
| 编译基线 | ✅ mvn compile gz-common+gz-ord 通过 |
| 删占位后无重复 preorder handler | ✅ gz-common spi/handler 目录已删；启动 fail-fast 校验通过（gz-common 98 单测绿，SPI 路由表 "已注册 1 个 handler：[preorder]"） |

## 架构变更说明（ticket ⭐⭐ 必做 5 步）

gz-common 不能依赖 gz-ord（反向 = 循环依赖），故真实业务 handler 下沉 gz-ord：

1. ✅ **新建** `org.dromara.gz.ord.service.callback.PreorderPayCallbackHandler`（@Component implements gz-common `PayCallbackHandler`，supportedBusinessType=preorder，onPaid 委托 `IGzOrdOrderService.onPaid` 推进 created→paid）
2. ✅ **删除** gz-common 占位 `org.dromara.gz.common.pay.service.spi.handler.PreorderPayCallbackHandler`
3. ✅ **新建** `org.dromara.gz.ord.service.callback.PreorderRefundCallbackHandler`（implements `IRefundCallbackHandler`，onRefunded → gz_ord_order paid→refunded，**SKU 库存不归还**）
4. ✅ **删除** gz-common 占位 `PreorderRefundCallbackHandler`（整个 `spi/handler/` 目录已移除）
5. ✅ **删前修引用**：`GzPayBusinessFullChainMockTest`（PAY-101）+ `PayRefundServiceImplTest`（PAY-103）原 `new PreorderXxxHandler()` → 改用**测试内联匿名 handler**（implements 接口，supportedBusinessType=preorder）。**gz-common 98 单测仍绿**（关键验证：删占位 + 内联 handler 后无重复注册、SPI 路由命中不变）。

pom：gz-ord 新增 `ruoyi-gz-user` 依赖（取地址 snapshot + 归属校验；gz-user→gz-common 单向，无循环）。

## 实现摘要

**后端 gz-ord（新增）**：
- DDL `V202606061400__GZ-ORD-104-create-gz_ord_order.sql`（逐字段对齐 doc/11 §6.3）
- entity `GzOrdOrder` / mapper `GzOrdOrderMapper`（行锁 selectByOrderNo/IdForUpdate + 状态守卫 markPaid/markCancelled/markRefunded）
- service `IGzOrdOrderService` + `GzOrdOrderServiceImpl`（submit 跨域事务 / cancel / getDetail / onPaid / onRefunded）
- 2 callback handler（下沉，见架构变更）
- enums `OrdBusinessStatusEnum`（无 closed）+ `LogisticsStatusEnum`（C1 2 态+终态）
- DTO `SubmitOrderReq` / `OrdSnapshot`（3 段 snapshot POJO）；VO `SubmitOrderVO` / `OrdOrderDetailVO`
- MP controller `GzOrdOrderMpController`（`@SaCheckLogin` /app/gz/ord/order：submit / cancel/{id} / {id}）
- 扩 `GzOrdErrorCode`（ADDRESS_INVALID 7008 / PRODUCT_OFF 7009 / ORDER_NOT_CANCELLABLE 7010 / ORDER_NOT_FOUND 7011）
- 扩 `IGzOrdSkuService.restoreStock`（取消回滚库存，无限库存跳过）

**后端 gz-common（删 + 改）**：删 2 占位 handler；改 2 测试用内联 handler。

**mp**：
- `api/gz-ord.ts` +submitOrder/cancelOrder/getOrderDetail + 类型（SubmitOrderReq/VO/OrdOrderDetailVO/snapshot）
- `composables/useOrderSubmit.ts`（submit→requestPayment→跳 pay-result；取消/失败保 created）
- `pages/ord/order-confirm.vue`（接真 submit，去占位 console.log）
- `pages/ord/pay-result.vue` + `pay-result.logic.ts`（C 系统 Biz* + var(--c-*)，3s×10 轮询）
- `locale/ord.zh-CN.ts` +`ord.payResult.*`（zh-CN + en，无 emoji）

**关键决策落地**：
- **order_no = gz_pay_transaction.business_order_no**：gz-ord 用 PayOrderNoGenerator 生成 PREORD- 号作 order_no，传 PAY-101 当 businessOrderNo；回调 SPI 据 business_order_no 反查订单。
- **pay_transaction_id（微信交易号）建单时 NULL，回调 onPaid 回填**（doc/11 §6.3；微信侧交易号下单时不存在，故 AC2 的"submit 阶段 UPDATE pay_transaction_id"落到 AC3 onPaid，已与字段语义对齐 —— 见风险段说明）。
- **金额后端重算**（不信任前端）：total = sku.price_cent × qty。
- **snapshot 用注入 ObjectMapper 序列化**（不用 JsonUtils 静态，避免 SpringUtils 静态依赖破坏单测；Spring 运行时由 JacksonConfig 提供 ObjectMapper bean）。

## AI 自测（Tier 1A）

### 编译 + install（删占位后全链路 install）
```
$ mvn -o install -DskipTests -pl ruoyi-modules/ruoyi-gz-common,ruoyi-modules/ruoyi-gz-ord -am
BUILD SUCCESS
（gz-common 删 2 占位 handler + 改 2 测试 → 编译通过；gz-ord 新增全部产物 → 编译通过）
```

### 单测 — gz-ord（GzOrdOrderServiceImplTest 9 个 + AC8 全链路 1 个 + 既有）
```
[INFO] Tests run: 9, Failures: 0, Errors: 0 -- GzOrdOrderServiceImplTest
  ① happy path：扣库存→INSERT created(snapshot+in_japan)→调 PAY(preorder)→返回 5 参
  ② onPaid：created→paid + paid_time + pay_transaction_id 回填 + 累加销量
  ③ 库存不足：tryDeductStock 抛 SKU_OUT_OF_STOCK → 不 INSERT order、不调 PAY（整事务回滚）
  ④ 商品下架 PRODUCT_OFF / ④b 截止过期 → 扣库存前拦截，不落 order
  ⑤ 地址非本人 ADDRESS_INVALID → 扣库存前拦截
  ⑥ 重复回调 onPaid markPaid affected=0 → 幂等不二次推进、不二次累加销量
  ⑦ cancel created→cancelled+回滚库存 / ⑦b cancel paid→ORDER_NOT_CANCELLABLE 不回滚库存
[INFO] Tests run: 1, Failures: 0, Errors: 0 -- PreorderFullChainMockTest（AC8）
[INFO] BUILD SUCCESS  ——  gz-ord 合计 Tests run: 36, Failures: 0, Errors: 0
```

### mock 全链路（AC8，gz.pay.client.mode=mock）— createOrder→mock V3 回调→PREORD- SPI 路由→订单 paid
```
[AC8] 建单 out_trade_no=PREORD-20260603-000001 business_order_no=PREORD-20260603-000001 订单初态=created
16:54:58 INFO GzOrdOrderServiceImpl -- [gz-ord-order] onPaid ok orderNo=PREORD-20260603-000001 ordOrderId=8001 → paid transaction_id=mock_wx_txn_PREORD-20260603-000001 paid_time=2026-06-03T16:54:58.143
[AC8] 回调后 gz_ord_order business_status=paid logistics_status=in_japan pay_transaction_id=mock_wx_txn_PREORD-20260603-000001
[AC8] 重复回调幂等 OK，销量仅累加 1 次，callback_logs=4
```
验证链路：PAY createBusinessOrder(preorder) → MockWechatPayClient.buildMockCallbackBody(AES-GCM) → handlePaymentNotify 乐观锁 pending→paid → PayCallbackDispatcher 按 business_type=preorder 路由到**真实下沉的 gz-ord PreorderPayCallbackHandler** → GzOrdOrderService.onPaid 行锁定位订单 → markPaid。
终态断言全过：`gz_ord_order.business_status='paid'` + `logistics_status='in_japan'` + `pay_transaction_id` 回填 + `gz_pay_transaction.business_type='preorder'`；重复回调双层幂等（PAY 侧 duplicated + ord 侧 markPaid affected=0），销量仅累加 1 次。

### 单测 — gz-common（删占位关键验证：仍绿）
```
[INFO] Tests run: 98, Failures: 0, Errors: 0  -- ruoyi-gz-common  BUILD SUCCESS
（含 GzPayBusinessFullChainMockTest 改内联 preorder handler 后仍绿；
  RefundCallbackDispatcher "退款回调 SPI 路由表就绪，已注册 1 个 handler：[preorder]" —— 无重复注册、无 fail-fast）
```

### mp vitest + type-check + build
```
$ pnpm test
 ✓ src/pages/ord/pay-result.logic.test.ts (11 tests)   — phase 映射 + 轮询判定
 ✓ src/composables/useOrderSubmit.test.ts (3 tests)    — 支付成功/取消/submit失败三分支
 ✓ src/pages/ord/detail.logic.test.ts (16 tests)
 Tests  1 failed | 164 passed (165)
   → 唯一失败 = src/api/gz-bean.test.ts bindMobile（code vs mobile 字段，GZ-BEAN-004 既有 case，与本卡无关，未触碰该文件）

$ pnpm type-check    （vue-tsc --noEmit）→ 0 error（pay-result.vue / useOrderSubmit.ts / order-confirm.vue / gz-ord.ts 全 clean）

$ pnpm build:mp-weixin → DONE Build complete.（尾部唤 devtools cli 已 pkill -o cli；dist 已生成）
   dist/build/mp-weixin/pages/ord/ 含 pay-result.js/.wxml/.wxss + pay-result.logic.js + order-confirm.js(4472B，含真 submit)
```

## Tier 2 可达（AC9）

现成路径全程可达，**无需新增临时入口**：
`首页 pages/index/index（预购 teaser + 网格④ → /pages/ord/list）→ 列表 list.vue（点卡 → preorder-detail?id=）→ 详情 preorder-detail.vue（立即购买 → usePurchaseGuard → order-confirm）→ 确认页 order-confirm.vue（提交订单 → useOrderSubmit submit → requestPayment → redirectTo pay-result?orderId=）→ pay-result.vue`。
确认页是 ORD-103 已建现成入口；本卡只把「提交订单」从 console.log 占位接到真跨域事务 + 支付。

## 风险提示 / 已知 issue

- **R8 真实端到端（外部前置）**：本卡 DoD 仅 mock 全链路（gz.pay.client.mode=mock）。真实微信支付商户号 / cert / apiV3Key 依赖甲方挂号 + V1.0 验收，**列外部前置风险，不当默认就绪**。
- **AC2 文案 vs AC3 字段语义对齐**：ticket AC2 写"调 PAY 拿 transaction_id → UPDATE gz_ord_order.pay_transaction_id"，但 `gz_pay_transaction.transaction_id`（微信侧交易号）在建单（createBusinessOrder）时为 NULL，仅支付回调才有值（doc/11 §4.2）。故实现按 AC3 在 **onPaid 时回填 pay_transaction_id**（与字段权威 doc/11 §6.3 "FK→transaction_id"语义一致）。submit 阶段订单与支付的关联靠 `gz_pay_transaction.business_order_no = gz_ord_order.order_no`（回调 SPI 据此反查）。无契约违背，仅 AC2 描述顺序与字段生命周期对齐说明。
- **支付超时（E7）订单自动取消未实现**：PAY-102 超时把 gz_pay_transaction 标 timeout，但本卡未实现"超时→订单 created→cancelled+回滚库存"的联动（无超时 SPI / cron）。当前行为 = 订单停 created，用户可重进继续支付或主动 cancel（R1 缓解）。**留 V1.1 后续 ticket**（建议 PAY-102 超时关单时发事件 / 加 OrdTimeoutCancelJob 扫 created+对应 timeout 交易行）。
- **gz-bean.test.ts bindMobile 既有失败**：与本卡无关（未触碰该文件 / API），D08 既有 case，不计本卡回归。
- **pages/index/index.vue 存 PAY-001 Tier2-entry-temp 临时入口**（注释 "remove when GZ-PAY-101 merged"）：本卡未触碰，属 PAY-101 清理责任。

## 对 ORD-105 的提示

- **gz_ord_order 表已建** + 全字段就绪（snapshot / 物流 / 时间）；**`getOrderDetail(id, userId)` 已建**（GET /app/gz/ord/order/{id}，snapshot 还原 + 归属校验，可直接复用为详情）。
- ORD-105 增量：① **list**（按 user_id 分页，建议 ORDER BY paid_time DESC + 软删 / 业务态过滤；snapshot 反序列化复用 `OrdSnapshot` POJO + `readJson`）；② **admin 只读列表**（business_type 分流真源仍在 gz_pay_transaction，admin 看 gz_ord_order + JOIN 语义靠 business_order_no）；③ **时间线**（C1 物流 2 态：paid → in_logistics(cn_dispatched_at) → delivered；订单时间线用 paid_time/cn_dispatched_at/delivered_time）。
- **C 端无退款入口**（合同 §2.3/§4.5）：ORD-105 订单详情仅文案「如需退款请联系客服」，禁退款按钮。
- **snapshot 即真源**：ORD-105 展示历史订单全部读 snapshot（不反查 gz_ord_product/sku/address —— 商品下架/改名/调价后仍显原貌）。
- **物流字段（cn_carrier_code/cn_tracking_no/cn_dispatched_at）本卡建表即落，未写值**：admin 推进（GZ-ADMIN-104 D10）才写；ORD-105 详情展示这几个字段（NULL 时不显物流模块）。

## §AI 测试段（kevin-qa Tier 1B）

> 本次为嵌套 subagent 调用，无法 spawn kevin-qa（嵌套限制）。Tier 1A 已做扎实（gz-ord 36 单测 + gz-common 98 单测 + AC8 mock 全链路 + mp 14 新单测 + type-check + build:mp-weixin）。
> 待主线程 / Kevin 触发 kevin-qa 跑 Tier 1B（admin 无新页 → 主要是 mp vitest 回归 + 后端集成 + 可达性确认）后追写于此。
