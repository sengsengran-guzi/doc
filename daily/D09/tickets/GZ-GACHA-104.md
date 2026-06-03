# GZ-GACHA-104 ⭐ — 扭蛋开盒事务 + 防超卖（4 表原子 + 失败重抽，必出无退款）

**优先级**: P1
**复杂度**: M（去掉退款重试/死信/报警机器后从 L 下调；并发正确性仍是 V1.1 最硬部分，**禁止快速过 §0 自检**）
**关联 PRD**: doc/02-prd.md M2 §业务本质 + §概率算法 + §并发与防超卖 + §异常分支 + §4.1 扭蛋规则（必出 1 件 / 概率公示 / 不保底 / 单品售罄从随机池剔除）
**关联拆解**: doc/02-需求拆解.md §3.3（GZ-GACHA-104 开盒事务 + 防超卖 + 失败重抽）
**关联 mockup**: design/mockup/gacha-draw.html（结果展示仅布局参考；视觉以 C 系统为准，doc/13；三段分镜出奖动画在 GACHA-105。本 ticket **纯后端 + mp api 封装**，无 mp 页面）
**关联 ADR**: 如本日实施时确需引入 MQ / 分布式锁框架解耦支付回调与开盒事务 → 新建 ADR-0003（默认不引，见备注 D8）
**依赖**: GZ-GACHA-101（`gz_gacha_machine` / `gz_gacha_prize` 已落表）+ GZ-PAY-101（微信支付 V3 统一建单 + SPI 回调，**D08 已交付** — §0 自检 grep 接口实际存在再开始）。**不依赖 PAY-103 退款**（扭蛋域无系统自动退款）

> **业务模型钉死（最高优先级，读 doc/10 §8 业务本质段）**：扭蛋 = 随机方式买东西，**付款必出 1 件实物**。**不存在"抽空 → 退款"**：缺货在付款前拦截（不收款），付款后必有货；并发扣减失败 = **从剩余有货池重抽改派其他商品（绝不退款）**。扭蛋域**无系统自动退款**（`refunded` 态仅供未来 admin 人工特例退款 ticket，本卡不写退款逻辑）。

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡 + ★ 重点反复读）

- **业务流**：doc/10-业务流权威图.md **§8 扭蛋机开盒全流程（M2）全文**（**不是 §7 = 预购**），特别是 **§8 业务本质段（钉死：必出 1 件 / 不抽空 / 缺货付款前拦截 / 失败重抽不退款）**，以及：
  - **§8.N4 付款前缺货拦截**（投币时机器无在售有货商品 → `MACHINE_EMPTY` 不收款；掏钱前拦缺货，掏钱后必有货）
  - **§8.N6 开盒事务流程**（4 表原子：`SELECT FOR UPDATE` 锁在售有货候选 → 归一化 → 随机出 1 件 → 乐观锁扣库存；**affected=0 → 移出候选 + 重新归一化重抽（有界，不退款）** → INSERT draw → INSERT/UPSERT collection → INSERT order → COMMIT）
  - **§8 状态机**（draw 仅终态记录；衍生订单 `pending_ship` → `in_logistics` → `delivered`；`refunded` 仅 admin 人工特例，开盒主流程不可达；**无系统自动退款分支**，失败是自循环重抽边）
  - **§8 并发与一致性**（E3：事务内 `SELECT FOR UPDATE` 抓快照 + 一次性归一化，事务内不重读旧权重）
  - **§8.E1 / E5 / E6 异常分支**（E1 付款前整机无货 → 不收款；**E5 并发扣减失败 → 重抽改派其他商品，不退款不回滚整单**；E6 DB 系统级故障 → ROLLBACK 后由 §6.E2 重试该开盒事务）
  - **§8 业务规则**（**必出 1 件** / **不做保底** PRD §4.1 / **单品售罄从随机池剔除 + 整机售罄防御性 `auto_off`**）
  - **§8.E3** 后台改概率瞬时（事务 SELECT FOR UPDATE 锁快照，用旧权重出，一致性优先）
- **支付回调分发**：doc/10-业务流权威图.md **§6.N6**（验签 + 幂等 + 业务回调）+ **§6.E2**（业务回调事务异常 → 重试 → 仍失败的支付层兜底）。**落地机制（D08 实证）= SPI `PayCallbackHandler` 按 `txn.business_type` 路由（`PayCallbackDispatcher`），非 out_trade_no 前缀**；幂等基于 transaction_id（§6.N6 的前缀分发是设计期表述）。注：§6.E2 是支付层通用兜底（预购也走），扭蛋开盒事务自身的库存竞争失败走重抽（§8.E5），不触发支付层退款
- **字段表**：doc/11-字段权威表.md（**DDL 完整字段来源，1:1 对齐**）
  - **§7.3 `gz_gacha_draw`**（开盒记录 — 9 字段全集 + 幂等唯一索引 `pay_transaction_id`）
  - **§7.4 `gz_gacha_order`**（衍生订单 — `business_status='pending_ship'` 默认 + `logistics_status` 并行字段 + version；`refunded` 仅 admin 人工特例可达）
  - **§7.5 `gz_user_gacha_collection`**（图鉴 — 事务内 UPSERT +1）
  - **§1 全局公共字段** + **附录 A.6（衍生订单状态）/ A.7（物流状态）/ B.3（时间字段命名 `_time` / `_at`）**
  - **§7.7 F7.3**（并发扣减失败 → 重抽不退款，draw 正常落）/ **F7.5**（公示价值单位 = 分）
- **UI 索引**：doc/12-UI-权威索引.md §MP-GACHA-DRAW（前端调用时序参考；动画 UI 在 GACHA-105）
- **支付集成（D08 PAY-101 已交付实证）**：reports/`GZ-PAY-101.md`。**建单 = `org.dromara.gz.common.pay.service.IGzPayTransactionService.createBusinessOrder(CreateOrderBo{businessType,businessOrderNo,amountCent,openid,userId,description})` → `MpPayParamsVO`**（**不是 `IGzPayService.unifiedOrder`，该接口不存在**）。回调 = **SPI `org.dromara.gz.common.pay.service.spi.PayCallbackHandler`（`supportedBusinessType()` + `onPaid(GzPayTransaction)`），`PayCallbackDispatcher` 按 `business_type` 自动路由**。复用 `IWechatPayClient`（V3，`Mock`/`V3ClientImpl`）+ V3 回调 `/api/pay/v3/notify`（AES-GCM）+ 流水 `gz_pay_transaction`/`gz_pay_callback_log` + `gz.pay.client.mode=mock`。**SPI 处理器必须下沉本模块（gz-gacha）实现接口**（gz-common 不可依赖 gz-gacha = 循环；`@Component` 由 common dispatcher 运行时收集）。**本 ticket 不用 PAY-103 退款 / `IPayRefundService` / `IRefundCallbackHandler`**（扭蛋域无系统退款）
- **mp 管理权限底座（ADR-0004）**：doc/_adr/0004-mp-admin-permission-foundation.md（如 GACHA 域后续 mp 管理动作 `@SaCheckPermission` 复用，不另造 RBAC；GACHA-104 本身无退款 mp 管理动作）

## What

落地扭蛋单抽从「投币（付款前缺货拦截）→ 支付 → 开盒事务 → 获得物锁定 / 图鉴 +1 / 衍生订单」的核心后端逻辑（doc/10 §8.N4-N6）：mp 用户在详情页（GACHA-103）点「投币开盒」→ **后端先校验机器在售且至少 1 件商品有货（整机无货 → `MACHINE_EMPTY` 不收款）** → 有货则拉起微信支付 V3 → 支付回调命中扭蛋分支 → 进开盒事务（`SELECT FOR UPDATE` 锁在售有货候选 + 归一化 + 随机出 1 件 + 乐观锁扣库存 + 写 draw + 图鉴 +1 + 建 `gz_gacha_order(pending_ship)`，**4 表原子**）→ **若某商品被并发抢空导致乐观锁扣减失败 → 把它移出候选 + 重新归一化重抽（有界重试），必出 1 件，绝不退款**。本 ticket **纯后端 + mp `api/gz-gacha.ts` 封装**（出奖动画 / 揭晓页在 GACHA-105）。**扭蛋域无系统自动退款**（不建退款 handler / service / 死信 / 报警机器）。

## AC（验收标准）

- [ ] **AC 1**：DDL `V202606171400__GZ-GACHA-104-create-gz_gacha_draw-order-collection.sql` 建 3 张表，字段 **1:1 对齐 doc/11 §7.3 / §7.4 / §7.5**（金额一律 `_cent`；snapshot 一律 `*_snapshot_json` JSON 列；图片 `image_id` 而非裸 url；`del_flag` 仅 2 值；`tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`，INSERT 不显式赋；UNIQUE 必含 `tenant_id`）：
  - **`gz_gacha_draw`**（§7.3）：`draw_no` VARCHAR(32)（`DRW-yyyyMMdd-6位序号`）/ `user_id` / `machine_id` / `prize_id` / `pay_transaction_id` VARCHAR(64) / `machine_snapshot_json` JSON / `prize_snapshot_json` JSON（名称 + 封面 image_id + 稀有度 + 公示价值 cent）/ `draw_amount_cent` BIGINT / `drawn_time` DATETIME(3) + §1 公共字段
    - UNIQUE `uk_tenant_draw_no (tenant_id, draw_no)` + **UNIQUE `uk_tenant_pay_tx (tenant_id, pay_transaction_id)`（幂等关键）**
    - IDX `(tenant_id, user_id, drawn_time DESC)`（GACHA-106 历史）/ `(tenant_id, machine_id)` / `(tenant_id, prize_id)`
  - **`gz_gacha_order`**（§7.4）：`order_no` VARCHAR(64)（**`GACHA-yyyyMMdd-6位序号`**）/ `draw_id` / `user_id` / `machine_snapshot_json` / `prize_snapshot_json` / `total_amount_cent` / `address_snapshot_json` JSON NULL / `business_status` VARCHAR(16) DEFAULT `'pending_ship'` / `logistics_status` VARCHAR(20) DEFAULT `'in_japan'` / `pay_transaction_id` / `paid_time` / `delivered_time` NULL / `cn_carrier_code` NULL / `cn_tracking_no` NULL / `cn_dispatched_at` NULL / `version` INT DEFAULT 0 + §1 公共字段
    - UNIQUE `uk_tenant_order_no (tenant_id, order_no)` + UNIQUE `uk_tenant_draw_id (tenant_id, draw_id)`（一抽一单）+ UNIQUE `uk_tenant_pay_tx (tenant_id, pay_transaction_id)`
    - IDX `(tenant_id, user_id)` / `(tenant_id, business_status)` / `(tenant_id, logistics_status)`
  - **`gz_user_gacha_collection`**（§7.5）：`user_id` / `machine_id` / `prize_id` / `first_drawn_time` DATETIME(3) / `drawn_count` INT DEFAULT 1 + §1 公共字段
    - UNIQUE `uk_tenant_user_machine_prize (tenant_id, user_id, machine_id, prize_id)`（每用户每奖品一条；UPSERT 锚点）
    - IDX `(tenant_id, user_id)` / `(tenant_id, user_id, machine_id)`
- [ ] **AC 2**：mp 端 `POST /app/gz/gacha/draw/start`（参数 `machineId`）：
  - sa-token mp-client → 拿 `user_id` + `openid`
  - 校验机器 `status='on_shelf'` 且至少 1 奖品 `stock_remain > 0`（否则返回业务错误码 `MACHINE_EMPTY`，mp 文案「该扭蛋机暂时缺货」）
  - 生成 `out_trade_no`（前缀 **`GACHA-yyyyMMdd-6位序号`**，复用 PAY-101 `PayOrderNoGenerator`，全局唯一）→ 调 `IGzPayTransactionService.createBusinessOrder(CreateOrderBo{businessType='gacha', businessOrderNo=outTradeNo, amountCent=machine.single_price_cent, openid, userId, description})`（金额**单位分**）→ 内部写 `gz_pay_transaction(business_type='gacha')` 并返回 `MpPayParamsVO`
  - 返回 `{outTradeNo, jsApiPayload}` 给前端唤起 `wx.requestPayment`
  - **本步不写 `gz_gacha_draw`**（draw 仅在开盒事务成功时落，库存抢空时不落 — doc/11 F7.3）
- [ ] **AC 3**：支付回调（PAY-101 已建 `/api/pay/v3/notify`，AES-GCM `NotificationParser`）验签 + 幂等（transaction_id）+ 乐观锁 pending→paid 后，`PayCallbackDispatcher` 按 `txn.business_type='gacha'` 路由到本域注册的 `GachaPayCallbackHandler.onPaid(txn)`（**SPI 机制，非 out_trade_no 前缀**）：
  - 置 `gz_pay_transaction.status='paid'` + `paid_time`
  - 异步触发开盒事务 `@Async("gachaExecutor") executeDrawTransaction(payTransactionId)`（回调线程不阻塞，微信要求 < 3s 响应）
  - **不引 V2 / XML / api-key / 新建 `gz_pay_order` / `amount_fen` / `/api/wxpay/pay-notify`**（PAY-101 是 V3）
- [ ] **AC 2.5** ⭐ **付款前缺货拦截**（doc/10 §8.N4 / §8.E1）：AC2 的 `draw/start` 在建支付单**之前**校验机器 `status='on_shelf'` 且至少 1 个 prize `enabled=1 AND stock_remain>0`；整机无货 → 返回业务错误码 `MACHINE_EMPTY`（mp 文案「该扭蛋机暂时缺货」），**不调 `createBusinessOrder`、不收款**。**掏钱之前拦缺货，掏钱之后必有货** —— 这是"无系统退款"成立的前提
- [ ] **AC 4** ⭐ **核心开盒事务（必出 1 件，失败重抽不退款）**：`@Transactional(rollbackFor=Exception.class)` 在 `GzGachaDrawServiceImpl.executeDrawTransaction(payTransactionId)`（doc/10 §8.N6 严格顺序）：
  1. 幂等：`gz_gacha_draw` 按 `pay_transaction_id` 已存在 → 直接 return（微信重复推送 / @Async 重入）
  2. **`SELECT * FROM gz_gacha_prize WHERE machine_id=? AND enabled=1 AND stock_remain>0 FOR UPDATE`**（锁所有在售有货候选行；锁奖品行不锁机器行，见 D1）
  3. **出 1 件（有界重抽循环，最多 N=候选数次）**：
     - `ProbabilityNormalizer.normalize(candidates)` 按当前候选 `weight` **一次性归一化**（与 GACHA-103 概率公示同一 Bean / 同一口径；事务内已 FOR UPDATE 锁快照，doc/10 §8.E3）
     - `SecureRandomDrawer` 抽取（`SecureRandom` 生成 `0~totalWeight` long，落区间定 1 件；语义保留 `draw`，UI 文案归 GACHA-105）
     - `UPDATE gz_gacha_prize SET stock_remain=stock_remain-1, version=version+1 WHERE id=? AND version=? AND stock_remain>0`（**乐观锁 version + `stock_remain>0` 双兜底**）
     - **affected=1 → 扣减成功，跳出循环**；**affected=0（被并发抢空）→ 把该商品移出候选集 + 回到循环顶重新归一化重抽（绝不退款）**
     - 候选集被取空仍未成功（理论不可达：付款前已拦缺货 + FOR UPDATE 锁内库存不会被外部抢，仅同一事务批次内竞争）→ 抛 `GachaInternalException` 走 §6.E2 支付层重试该开盒事务（**非退款**）
  4. INSERT `gz_gacha_draw`（`draw_no` + `prize_id` + `machine_snapshot_json` + `prize_snapshot_json` + `draw_amount_cent` + `pay_transaction_id` + `drawn_time`）
  5. **事务内** UPSERT `gz_user_gacha_collection`（`(user_id, machine_id, prize_id)` 命中 → `drawn_count+1`；未命中 → INSERT `drawn_count=1` + `first_drawn_time=NOW`）
  6. INSERT `gz_gacha_order`（`order_no` `GACHA-yyyyMMdd-6位序号` + `draw_id` + snapshot + `total_amount_cent` + `business_status='pending_ship'` + `logistics_status='in_japan'` + `paid_time`）
  7. COMMIT（**4 表变更原子**：prize 库存 + draw + collection + order）
  - **无"候选为空 → 退款"分支**（缺货付款前已拦，AC2.5）；**无 `gz_pay_refund` 写入**
- [ ] **AC 5** ⭐ **失败语义 = 重抽改派，不是退款**（doc/10 §8.E5 / doc/11 F7.3）：
  - 并发扣减失败（乐观锁 affected=0）→ **AC4.3 内重抽改派其他有货商品**（不回滚整单、不退款、不写 `gz_pay_refund`），最终必出 1 件 → 正常 INSERT draw / order
  - DB 系统级故障（mapper 异常 / 连接断等，非库存竞争）→ 整事务 ROLLBACK → 由 §6.E2 支付层兜底重试该开盒事务（重试仍失败的支付层处置走通用兜底，**扭蛋域本身不主动调退款**）
  - **本 ticket 不实现** `GachaRefundService` / `GachaRefundCallbackHandler` / 退款重试 / 死信队列 / 报警邮件（扭蛋域无系统退款）；`gz_gacha_order.business_status='refunded'` 仅供未来 admin 人工特例退款 ticket（合同 §4.5）使用
  - **禁止**写 `stock_empty_refunded` 状态 draw、禁止任何"奖品已抽完 → 退款"路径
- [ ] **AC 6** ⭐ **必出 1 件 + 不做保底**（doc/10 §8 业务规则 + PRD §4.1）：成功路径每次必出 1 个实物商品（不出空奖）；纯权重随机，**不在 service 加任何「保底计数器」/「N 抽必中 SR」**
- [ ] **AC 7** ⭐ **抽完即下架 `auto_off`**（doc/10 §8 + doc/11 §7.1 status 枚举）：奖品 `stock_remain` 扣到 0 时下次开盒 AC4 步骤 2 `WHERE stock_remain>0` 自然剔除；**整机所有奖品 `stock_remain=0` → 异步置 `gz_gacha_machine.status='auto_off'`**（**不用 `off_shelf` / `archived`**），GACHA-102 列表已过滤非 `on_shelf` 自然不再展示（不引 ws 推送）
- [ ] **AC 8**：单测覆盖 6 个场景（每个 raw assertion，mock `IGzPayTransactionService` + mapper FOR UPDATE）：
  - happy path：出 1 件商品 → `stock_remain-1` + version+1 + draw 落库 + collection +1 + order `pending_ship`，4 表一致
  - 付款前缺货拦截：`draw/start` 机器整机无货 → 返回 `MACHINE_EMPTY`，**不调 createBusinessOrder、不收款**
  - 并发扣减失败 → 重抽改派：mock 第 1 次 `UPDATE` affected=0、第 2 次 affected=1 → **最终出另一件有货商品 + draw / order 正常落 + 无 gz_pay_refund**（验证"失败 = 重抽，不退款"）
  - 乐观锁竞争边界：候选 2 件，mock 第 1 件 affected=0 → 移出候选 → 第 2 件 affected=1 → 出第 2 件
  - 幂等：同 `pay_transaction_id` 二次进入 → 步骤 1 直接 return（不重复扣库存 / 不重复建单）
  - 概率随机性：10000 次抽样，各商品出现频次贴近 `weight` 比，χ² 检验 P > 0.05
- [ ] **AC 9** ⭐ **reports 必含并发压测 raw output**（DoD 硬卡）：
  - 场景：单机仅剩 1 个 SSR（`stock_remain=1`）+ 其余商品有货 + N（≥ 20）并发用户同时支付回调到达
  - 期望（贴 raw SQL 验证）：DB 最终 `SSR.stock_remain=0`；**恰好 1 条 `gz_gacha_draw` 中该 SSR**；其余用户**各得 1 件其他有货商品（各 1 条 draw + 1 条 order，business_status=pending_ship）**，**无任何 `gz_pay_refund` 记录**（证伪超卖 + 证明失败走重抽非退款）；`gz_gacha_order.order_no` 全局唯一无冲突
  - reports 贴：并发驱动脚本（多线程直调 `executeDrawTransaction` 或 wrk/ab 打回调）+ raw SQL count（draw 总数 = N、refund 总数 = 0）+ 各用户获得物分布摘录（≥ 3 个代码 block）
- [ ] **AC 10**：mock 全链路自测 raw output（`gz.pay.client.mode=mock`）：统一下单 → mock 回调 → 开盒事务 → 库存扣减 / 图鉴 +1 / 衍生订单 `pending_ship` / **付款前缺货拦截 MACHINE_EMPTY 不收款**，全链路打通；**无退款分支**（验证 `gz_pay_refund` 全程无写入）；写操作加 `@Log`；handler 幂等基于 `uk_tenant_pay_tx` DB 唯一索引兜底

> 纯后端 + mp api 封装 ticket，**无 mp 页面** → 跳过 Tier 2 入口可达 AC（CLAUDE.md §8.2；mp 页面入口 / 真机 happy path 在 GACHA-105 验）。

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-gacha/`（包名 `org.dromara.gz.gacha.{controller,service,mapper,domain,dto}`）
  - `controller/applet/GzGachaDrawMpController.java`（`POST /app/gz/gacha/draw/start`）
  - `service/IGzGachaDrawService.java` + `service/impl/GzGachaDrawServiceImpl.java`（**核心事务 `executeDrawTransaction(payTransactionId)`**）
  - `service/callback/GachaPayCallbackHandler.java`（`@Component implements org.dromara.gz.common.pay.service.spi.PayCallbackHandler`，`supportedBusinessType()='gacha'`，`onPaid(txn)` 内 `@Async` 触发 `executeDrawTransaction`；下沉 gz-gacha，`PayCallbackDispatcher` 运行时自动收集）。**不建 `GachaRefundCallbackHandler` / `GachaRefundService`**（扭蛋域无系统退款）
  - `service/internal/ProbabilityNormalizer.java`（GACHA-103 已建，本 ticket **复用同 Bean**）
  - `service/internal/SecureRandomDrawer.java`（权重区间抽取，便于 mock 测试）
  - `domain/GzGachaDraw.java` / `GzGachaOrder.java` / `GzUserGachaCollection.java` + VO / BO（含 snapshot 内嵌结构）
  - `mapper/GzGachaDrawMapper.java` / `GzGachaOrderMapper.java` / `GzUserGachaCollectionMapper.java`（含 `SELECT ... FOR UPDATE` 自定义方法 + UPSERT）
  - `config/GachaExecutorConfig.java`（`@Async("gachaExecutor")` 独立线程池）
  - DDL × 1（AC1）
  - **不需要** `gz.gacha.refund-retry-intervals` / `gz.gacha.alert-email` 配置（无退款重试 / 死信 / 报警）；**不需要** `@SaCheckPermission("gz:pay:refund:apply")`（本 ticket 无退款入口）
- **小程序**：仅 `code/main/miniapp/src/api/gz-gacha.ts` 加 `startDraw(machineId)` 调用 + 唤起 `wx.requestPayment(jsApiPayload)`；**无 mp 页面**（动画 + 揭晓在 GACHA-105）
- **测试**：mvn 单测（6 场景，`-DskipTests=false -pl ruoyi-modules/ruoyi-gz-gacha -am`）+ 并发压测 raw output（draw 总数 = N、refund 总数 = 0）+ mock 全链路 raw output + DB 客户端 raw SQL 验证

## 备注

### 强约束 ★

0. **业务模型钉死 — 付款必出 1 件，扭蛋域无系统自动退款**（doc/10 §8 业务本质 / PRD M2 §业务本质）：缺货付款前拦截（`MACHINE_EMPTY` 不收款），付款后必有货；并发扣减失败走重抽改派其他商品。**全卡禁止出现任何"抽空 → 退款" / `gz_pay_refund` 写入 / 退款 handler / service / 死信 / 报警**。
1. **三层防超卖不可绕过**（doc/10 §8.N6）：DB 事务 / `SELECT FOR UPDATE` 锁奖品行 / `UPDATE stock_remain WHERE version=? AND stock_remain>0`（乐观锁）三层缺一不可。**防的是同一商品超卖；失败后果 = 改派其他商品重抽，不是退款。**
2. **并发扣减失败 = 重抽改派，draw 正常落**（doc/11 F7.3）：affected=0 → 移出候选 + 重新归一化重抽，必出 1 件后正常 INSERT draw / order；**禁止**写 `stock_empty_refunded` draw、**禁止**写 `gz_pay_refund`。
3. **幂等基于 `pay_transaction_id` 唯一索引**（doc/11 §7.3，**不是 out_trade_no 做 draw 幂等**）：微信重复推送 / @Async 重入都靠 `uk_tenant_pay_tx` 兜底。
4. **本 ticket 无退款逻辑**：不建退款 handler / service；`gz_gacha_order.business_status='refunded'` 仅供未来 admin 人工特例退款 ticket（合同 §4.5）使用；C 端无退款入口（仅文案「如需退款请联系客服」）。
5. **获得物 / 机器 snapshot 落 JSON 列**（doc/11 §7.3，`machine_snapshot_json` + `prize_snapshot_json`）— 防后台改商品名 / 改稀有度 / 删商品后历史读不到准确信息（doc/10 §8.E7）；**不散列成多列**。
6. **必出 1 件 + 不做保底**（PRD §4.1）：成功路径必出实物；纯权重随机，禁任何保底计数器。
7. **单品售罄从随机池剔除 + 整机售罄防御性 `auto_off`**（doc/11 §7.1 status）：单品 `stock_remain=0` 下次 FOR UPDATE 自然剔除；整机所有商品售罄（运营保证不发生）异步置机器 `auto_off`，**禁 `off_shelf` / `archived`**，**无用户侧退款**。
8. **支付集成走 PAY-101 V3**：复用 `IWechatPayClient`（`WechatPayV3ClientImpl` / `MockWechatPayClient`）+ apiV3Key + V3 `NotificationParser`(AES-GCM) + 回调 `/api/pay/v3/notify`；流水 `gz_pay_transaction` / `gz_pay_callback_log`。**禁 V2 / XML / api-key / 新建 `gz_pay_order` / `amount_fen` / `/api/wxpay/pay-notify`**。
9. **`@Async("gachaExecutor")` 独立线程池**：不占 ruoyi 默认 task executor；线程数 max(8, cores×2)，队列满走 RejectedExecutionHandler 入 DB 再异步消费。
10. **盲盒语义**（仅 gacha 域）：后端 enum / 字段 / 错误码可保留 `draw` 技术语义（`gz_gacha_draw` / `executeDrawTransaction`）；**用户可见 toast / 邮件 / `t('gacha.xxx')` 文案用扭蛋语义**（扭蛋 / 开盒 / 获得 / 出现概率；禁 抽奖 / 中奖 / 开奖）。引用 **doc/10 §8**（不是 §7）+ doc/12 MP-GACHA-DRAW + **doc/tokens.md §1.4 稀有度色**（四档）+ **doc/13 §3.2 三段动画**（GACHA-105；**禁引 tokens §9，不存在**）。
11. **金额 / 命名硬约束**：金额一律 `_cent`；订单号 `GACHA-yyyyMMdd-6位序号` + DB 全局唯一约束；库存 `stock_remain`（不用 init/left）+ 乐观锁 `version`；`del_flag` 仅 2 值；`tenant_id VARCHAR(20) DEFAULT '1001'`，INSERT 不显式赋，UNIQUE 必含 tenant_id；`business_type='gacha'` 落 `gz_pay_transaction`，**禁在订单表加 `business_line`/`biz_line`/A/B 列**。
12. **物流字段并行不互相覆盖**（doc/10 §9 C1）：`gz_gacha_order.logistics_status` ∈ {`in_japan`/`in_china_dispatching`/`delivered`}，独立于 `business_status`；本 ticket 建表落字段，物流推进在 ADMIN-104（**禁 7 节点 / `gz_logistics_node` / 批次推进**）。

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | `SELECT FOR UPDATE` 锁奖品行（不锁机器行）| 锁粒度小，并发抽不同奖品互不干扰；锁机器行会让所有用户串行 |
| D2 | 开盒事务异步触发（支付回调线程不阻塞）| 微信 V3 回调要求 < 3s 响应；事务 SELECT FOR UPDATE + 多步 UPDATE 可能 > 1s |
| D3 | snapshot 用 JSON 列而非冗余字段 | 灵活兼容 prize schema 变更（V2 加属性），对齐 doc/11 §7.3 `*_snapshot_json` |
| D4 | `SecureRandom` 而非 `Random` | 不可预测，防种子推测出货序列（合规） |
| D5 | 并发扣减失败走重抽改派，不退款 | 业务本质 = 付款必出 1 件（doc/10 §8）；缺货付款前已拦，付款后只是"出哪件"的竞争，改派其他有货商品即可，无须退款；省掉退款 service / 死信 / 报警整套机器（复杂度从 L 降 M） |
| D6 | `auto_off` 在事务外异步检测整机库存 | 检测全 prize stock=0 要二次 SELECT，事务内会增时长；异步秒级延迟可接受（运营保证整机不全空，此为防御性）|
| D7 | `auto_off` 后不推 mp 端 | 用户下次进列表 GACHA-102 已过滤 on_shelf 自然看不到；不引 ws |
| D8 | 不引 Redisson 分布式锁 | DB 行锁 + 乐观锁 version + UNIQUE 已足够；引 Redisson 增依赖 + 超时风险 |
| D9 | 重抽循环有界（≤ 候选数）+ 在已 FOR UPDATE 的快照内重抽 | 同一事务内候选已被锁住快照，重抽只在批次内竞争中改派，不会无限循环；理论取空候选不可达（付款前拦缺货 + 锁内库存不被外部抢）|

### 风险提示 ★

| # | 风险 | 缓解 |
|---|---|---|
| R1 ★ | 并发抢最后 1 个 SSR 超卖（2 用户同中一物） | 三层防线（事务 + FOR UPDATE + 乐观锁 version）+ **AC9 并发压测 raw output 证伪**（恰好 1 人得 SSR，其余得其他商品）|
| R2 ★ | 并发扣减失败误退款 / 误回滚整单 | **失败 = 重抽改派其他有货商品（AC4.3）**，不退款、不回滚整单、不写 `gz_pay_refund`；缺货已在付款前 AC2.5 拦截；AC9 压测验证 refund 总数 = 0 |
| R3 | 概率归一化在 GACHA-103 与本 ticket 不一致 | 抽 `ProbabilityNormalizer` Bean 两处复用，单测共用 fixture（doc/10 §8.E3 事务内锁快照口径） |
| R4 ★ | 误用不存在的 `IGzPayService.unifiedOrder` / 误按 out_trade_no 前缀分发 / 误引退款 | **§0 自检 grep 代码确认 D08 已交付契约**：`grep -rn "interface IGzPayTransactionService\|createBusinessOrder" ruoyi-modules/ruoyi-gz-common` + `grep -rn "interface PayCallbackHandler\|class PayCallbackDispatcher" ruoyi-modules/ruoyi-gz-common` + `grep -rn "IWechatPayClient" ruoyi-modules/ruoyi-gz-common` + `ls db/migration \| grep -i gz_pay_transaction` + `grep -il gz_gacha_prize db/migration/*GACHA-101*`；任一不存在 → STOP 报 Kevin。**不 grep / 不引 `IPayRefundService` / `gz_pay_refund`（扭蛋域无系统退款）** |
| R5 ★ | 真实微信商户号 / 0.01 元端到端未就绪 | **外部前置风险（非默认就绪）**：dev/staging 仅 `gz.pay.client.mode=mock` 跑全链路自测；真实端到端备注标注 + 并行催甲方验收 V1.0；不当 ticket 完工条件 |
| R6 | 支付回调延迟 > 30s → mp 等待动画超时 | GACHA-105 前端轮询 `/app/gz/gacha/draw/status`（按 out_trade_no）+ 超时 60s 弹「已支付，结果稍后到账」 |
| R7 | `@Async` 线程池打满 | max=20 + 队列 1000；满走 RejectedExecutionHandler 入 DB queue 再异步消费 |
| R8 | SecureRandom 随机性偏差 | AC8 χ² 检验（10000 抽样）保证；CI 中跑 |

### ADR 候选

- **ADR-0003**：是否引入 MQ 解耦支付回调与开盒事务 — 默认不引；若压测发现 `@Async` 线程池频繁打满再评估。

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
