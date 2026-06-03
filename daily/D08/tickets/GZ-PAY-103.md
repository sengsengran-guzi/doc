# GZ-PAY-103 — 退款服务（仅全额 / @SaCheckPermission / V3 退款回调 / 新建 gz_pay_refund）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M1 §业务支付 §退款（仅 admin 触发）+ M3 §预购 §异常分支 E5 + M2 §扭蛋 §退款
**关联拆解**: doc/02-需求拆解.md §3.1（GZ-PAY-103 退款服务）
**关联 mockup**: N/A（admin 走 ruoyi/Element Plus 默认审美，不引用 mockup）
**关联 ADR**: —
**依赖**: GZ-PAY-101（业务统一支付 V3 / `gz_pay_transaction` 扩展 / SPI 回调路由骨架）

> **拆环说明**：本卡**只依赖 PAY-101**，**不依赖 ADMIN-103**（订单详情看板属另一域，本日不存在该骨架）。admin 端「申请退款」按钮单向调用本服务暴露的接口；ADMIN-103 / 订单详情看板未完工时，退款按钮以 `disabled` 占位，待其落地后接通——**本卡不等订单看板**。

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md
  - **§6 业务支付流（M1-业务接入，V1.1）** — 状态机 `已支付 → 退款中 → 已退款 / 退款失败回滚已支付`；N8（admin 触发退款）/ N9（调微信退款 API `POST /v3/refund/domestic/refunds`）/ N10（退款回调 `/api/pay/v3/refund-notify`）；E4（退款回调失败 → 定时主动查）/ E5（部分退款不支持，仅全额）
  - §2 微信支付通道接入流 — V3 回调验签 / AES-GCM 解析机制（退款回调复用同套 `NotificationParser`）
- **字段表**：doc/11-字段权威表.md
  - **§4.4 `gz_pay_refund` 退款单** — 字段定义权威真源（`refund_no` / `transaction_id` / `out_trade_no` / `wechat_refund_id` / `refund_amount_cent` / `reason` / `status` / `triggered_by` / `triggered_time` / `refunded_time`）
  - §4.2 `gz_pay_transaction` — 退款时不更新 `amount_cent`，写独立 `gz_pay_refund`；`status` 加 `refunding` / `refunded` 两态流转
  - §4.5 支付状态字段口径 — 支付 refunded → 业务订单也 refunded（doc/10 §6.N10 业务回滚）
  - §4.6 4% 分成核心计算口径 — 退款按 `refunded_time` 当月归属，扣减分成基数（本卡仅保证退款单字段正确，对账取数留 D10/D11）
  - §附录 A.2 `gz_pay_status` 枚举
- **D7x 权限底座（ADR-0004）**：本卡 admin/owner 触发走 `@SaCheckPermission`，复用 D7x 已交付的 ruoyi RBAC + StaffMe 底座（加一行 perm 校验 + admin 授权 + 同租户 1001）

## What

后台运营 / 客服判断特例后，由有 `gz:pay:refund:apply` 权限的运营人在 admin 触发**全额退款**（一笔对一单）：后端基于 PAY-101 的 `IWechatPayClient`（V3）调微信退款 API，落 `gz_pay_refund`，并在独立 V3 退款回调（与支付回调分流）里推进退款终态 + 触发业务方退款 handler（SPI）。**C 端无退款入口**（合同 §4.5），mp 订单详情仅展示「如需退款请联系客服」文案。

## AC（验收标准）

- [ ] **AC 1**：DDL `V<时间戳>__GZ-PAY-103-create-gz_pay_refund.sql`（时间戳 > `V202606051200`）建 `gz_pay_refund` 表，字段**严格对齐 doc/11 §4.4**：
  - `refund_no` VARCHAR(64) NOT NULL（格式 `RF-yyyyMMdd-6位序号`）/ `transaction_id` VARCHAR(64) NOT NULL（FK 微信侧）/ `out_trade_no` VARCHAR(64) NOT NULL（业务订单号）/ `wechat_refund_id` VARCHAR(64) NULL / `refund_amount_cent` BIGINT NOT NULL / `reason` VARCHAR(255) NOT NULL / `status` VARCHAR(16) NOT NULL DEFAULT `'refunding'`（枚举 `refunding`/`refunded`/`failed`）/ `triggered_by` VARCHAR(64) NOT NULL / `triggered_time` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) / `refunded_time` DATETIME(3) NULL + ruoyi 公共字段 + `tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`（INSERT 不显式赋）
  - 约束：`UNIQUE(tenant_id, refund_no)`；`UNIQUE(wechat_refund_id) WHERE wechat_refund_id IS NOT NULL`；IDX `(tenant_id, transaction_id)`、`(tenant_id, status)`
  - **金额列名 `refund_amount_cent`（分），禁止 `amount_fen` / `refund_fen`**；**禁止** `operator_id` / `pay_order_id`（用 `triggered_by` / `transaction_id`）；`del_flag` 仅 2 值对齐 `@TableLogic`
  - **不新建 `gz_pay_order`**（PAY-103 不引入旧 V2 表）；不在 `gz_pay_transaction` 加 `refund_fen` 累计列（全额退款一笔对一单，无累计）
- [ ] **AC 2**：退款申请接口 `POST` 暴露给 admin（如 `/system/gz/pay/refund/apply`，body `{ transactionId }`，**无 amountCent 入参** — 全额由系统取 `gz_pay_transaction.amount_cent`）：
  - 权限 `@SaCheckPermission("gz:pay:refund:apply")`（**禁止 `@SaCheckRole`**）；同租户 1001
  - 校验：原 `gz_pay_transaction.status='paid'`（非 paid 抛业务异常）；同 `transaction_id` 不存在 `status IN (refunding, refunded)` 的退款单（防重复退）
  - `refund_amount_cent` = 原单 `amount_cent`（系统取，不接受前端传值）
  - 生成 `refund_no`（`RF-yyyyMMdd-6位序号`，全局唯一含 tenant_id；复用 PAY-101 锚定的订单号生成器，前缀 `RF`）
  - 同事务：INSERT `gz_pay_refund` status=`refunding`（`triggered_by`=当前登录 username）+ UPDATE `gz_pay_transaction.status='refunding'`
  - 调 `IWechatPayClient` V3 退款 API（对应 `POST /v3/refund/domestic/refunds`，`refund_notify_url` = `/api/pay/v3/refund-notify`）；mock 模式（`gz.pay.client.mode=mock`）下 `MockWechatPayClient` 返回受理成功
  - 微信受理成功 → 等异步回调；受理失败 → UPDATE `gz_pay_refund.status='failed'` + `gz_pay_transaction.status` 回滚 `paid` + 抛业务异常给前端
- [ ] **AC 3**：V3 退款回调 `POST /api/pay/v3/refund-notify` 独立 endpoint（**与 PAY-101 支付回调 `/api/pay/v3/notify` 分离**，无 sa-token）：
  - 复用 PAY-101 的 V3 `NotificationParser`（**AES-GCM 解密 resource**，禁止 V2 MD5/XML/`req_info`）
  - 幂等：按 `wechat_refund_id` / `refund_no` 在 `gz_pay_callback_log`（`callback_type='refund'`）去重 + `SELECT ... FOR UPDATE` 锁退款行；已终态（`refunded`/`failed`）直接返回 success 不重复处理
  - 微信回调 `SUCCESS` → UPDATE `gz_pay_refund` status=`refunded` + `wechat_refund_id` + `refunded_time` + UPDATE `gz_pay_transaction.status='refunded'` → 触发业务方退款 SPI handler
  - 微信回调 `ABNORMAL`/`CLOSED` 等失败 → UPDATE `gz_pay_refund.status='failed'` + 落 raw body 到 `gz_pay_callback_log`（不回滚 transaction，留 admin 人工介入，对齐 doc/10 §6.E4）
  - 回调落 `gz_pay_callback_log`（`callback_type='refund'`）
- [ ] **AC 4**：业务方退款 SPI（与 PAY-101 支付回调 SPI **平行而非共用**）：
  - 定义 `IRefundCallbackHandler`（或在 PAY-101 SPI 注册表里以"退款"类型分流的独立路由 key），按 `gz_pay_transaction.business_type`（`preorder` / `gacha`）路由到对应业务 handler
  - PAY-101 SPI 路由表 review 时确保**退款回调 key 与支付回调 key 不撞**（README R2）
  - 本卡提供分发骨架 + 预购占位 handler（ORD-104 / GACHA 域实施时填实现：业务订单 → `refunded`，doc/10 §6.N10 业务回滚）
- [ ] **AC 5**：admin 退款按钮 + 弹窗（plus-ui，走 ruoyi/Element Plus 默认审美）：
  - 在订单详情底部增「申请退款」按钮，权限指令 `v-hasPermi="['gz:pay:refund:apply']"`（owner 默认授权）
  - **订单详情看板（ADMIN-103 / 订单看板）未完工时按钮 `disabled` 占位**（单向调用，本卡不依赖看板落地）
  - 点击弹 `<el-dialog>`：展示**全额退款金额（只读，= 原单 `amount_cent / 100` 元，无金额 input）** + `reason` textarea（必填，≤ 255 字）
  - 提交 → loading → 成功 toast「退款已提交，等待微信处理」+ 关闭弹窗 + 刷新订单详情
  - 退款记录 `<el-table>`（`refund_no` / 金额 / 原因 / 触发人 / 状态 / 触发时间 / 退款完成时间）
  - i18n 文案走 `t('pay.refund.xxx')` + zh_CN / en_US；不混 emoji
- [ ] **AC 6**：菜单 + 权限 seed（DDL，**menu_id 5100 段 GZ-PAY**）：`gz:pay:refund:apply`（+ 如需 `gz:pay:refund:list` 查询）按钮权限 menu，仅 owner（100）授权；INSERT 走菜单/权限表，**禁止 INSERT sys_job**（无 sys_job 表，启动 hard-fail）
- [ ] **AC 7**：操作日志 `@Log(title = "支付退款", businessType = OTHER)` 写入 sys_oper_log（溯源触发人）
- [ ] **AC 8**：**C 端无退款入口**（合同 §4.5 + doc/10 §7.E5 强约束）：
  - 本卡**不写 mp 退款 UI**；仅在 §备注约束下游（ORD-105 / GACHA 订单详情）订单详情页禁止出现「申请退款」按钮，仅展示文案「如需退款请联系客服」+ 客服入口（GZ-SYS-004 已实现）
- [ ] **AC 9**：单测覆盖 ≥ 4 个测试方法（mock client）：
  - happy path：paid 单 → apply → mock 受理成功 → 模拟 V3 退款回调 SUCCESS → `gz_pay_refund.status=refunded` + `gz_pay_transaction.status=refunded`
  - 非 paid 订单不允许退款（抛业务异常）
  - 重复退款拦截：同 transaction 已存在 refunding/refunded 退款单 → 抛异常
  - 回调幂等：同 `wechat_refund_id` 二次回调不重复变更
  - 受理失败回滚：mock 受理失败 → `gz_pay_refund.status=failed` + transaction 回 `paid`

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-common`，包 `org.dromara.gz.pay.{controller,service,mapper,domain,dto}`
  - `controller/PayRefundController.java`（admin 退款申请，`@SaCheckPermission("gz:pay:refund:apply")`）
  - `controller/PayRefundCallbackController.java`（`/api/pay/v3/refund-notify`，无 sa-token，复用 V3 `NotificationParser`）
  - `service/IPayRefundService.java` + `service/impl/PayRefundServiceImpl.java`（核心：apply / handleRefundCallback）
  - `service/spi/IRefundCallbackHandler.java`（退款 SPI，业务方实现；与 PAY-101 支付 SPI 平行）+ 预购占位 handler
  - `domain/GzPayRefund.java` + dto（`RefundApplyBo` 仅 `transactionId` + `reason`，**无 amountCent**）+ vo
  - `mapper/GzPayRefundMapper.java`
  - 复用 PAY-101：`IWechatPayClient`（`WechatPayV3ClientImpl` / `MockWechatPayClient`）、订单号生成器（前缀 `RF`）、`gz_pay_callback_log`（`callback_type='refund'`）
  - DDL × 2（建 `gz_pay_refund` 表 / 菜单+权限 seed，或合并 1 文件按时间戳顺序）
- **Admin 前端**：`code/main/plus-ui/src/views/gz-pay/`（如无则新建）
  - 退款弹窗组件 `RefundApplyDialog.vue` + api `src/api/gz-pay/refund.ts` + i18n
  - 走 ruoyi/Element Plus 默认审美，不套 C 系统
- **小程序**：N/A（本卡严禁 mp 加退款入口；仅 §备注约束下游订单详情页用「联系客服」文案）
- **测试**：mvn 单测（mock client）+ Postman / 单测模拟 V3 退款回调（AES-GCM body）

## 备注

### 强约束 ⭐

1. **仅全额退款**（doc/10 §6.E5 / Q6.2 + 字段铁律）：一笔对一单，`refund_amount_cent` = 原单 `amount_cent` 由系统取，接口无金额入参；**禁止部分退款 / `refund_fen` 累计 / 多次退款拼凑**。
2. **V3 不是 V2**：退款走 `IWechatPayClient`（`POST /v3/refund/domestic/refunds`）+ V3 回调 AES-GCM 解析；**禁止** V2 / XML / `secapi/pay/refund` / `req_info` MD5 解密 / mTLS 证书写法（V3 用 apiV3Key + 商户私钥签名，PAY-101 已封装）。
3. **权限走 `@SaCheckPermission("gz:pay:refund:apply")`**，复用 D7x ADR-0004 RBAC 底座；**禁止 `@SaCheckRole`**。后端校验为准，前端 `v-hasPermi` 仅隐藏。
4. **退款回调 endpoint 独立**（`/api/pay/v3/refund-notify` ≠ PAY-101 `/api/pay/v3/notify`）；SPI 退款 handler 与支付 handler 平行（不混 key，README R2 串行 review）。
5. **C 端绝对无退款入口**（合同 §4.5）— 下游 ORD-105 / GACHA 订单详情严禁加退款 UI，仅「如需退款请联系客服」。
6. **只依赖 PAY-101，不依赖订单看板**：admin 退款按钮单向调本服务；订单看板（ADMIN-103）未完工时按钮 `disabled` 占位。
7. **字段命名钉死**：`refund_amount_cent`（分）/ `transaction_id`（FK）/ `triggered_by`+`triggered_time`（不用 `operator_id`）/ `refund_no` = `RF-yyyyMMdd-6位序号`；`del_flag` 2 值；`tenant_id` 自动填充 + UNIQUE 含 tenant_id。
8. **退款失败处理**（doc/10 §6.E4）：受理失败回滚 transaction 到 `paid`；回调返失败 → `gz_pay_refund.status=failed` 留人工介入 + 告警（不自动撤已扣业务动作）。
9. **退款回滚业务侧**（doc/10 §6.N10 / §7.N13）：预购特例退款 SKU 库存**不归还**（已采购）；扭蛋退款由其 handler 决策。本卡只保证 PAY 层动作 + SPI 分发正确，业务 handler 实现留各业务域 ticket。

### 推进姿态（Kevin 决策 1 — Mock 全链路自测）

- 本卡 DoD 以 `gz.pay.client.mode=mock`（`MockWechatPayClient`）全链路自测为准：apply → mock 受理成功 → 模拟 V3 退款回调 → `refunded`。
- **真实商户号 / 真实退款端到端 = 【外部前置风险】**（甲方挂号 + apiV3Key + 商户私钥就绪滞后），不当默认就绪；并行催甲方完成 V1.0 验收。

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 退款回调独立 endpoint + 独立 SPI 路由 key | V3 退款回调 resource 语义与支付回调不同（退款单维度），分流避免 handler 混淆 |
| D2 | 仅全额退款，接口无金额入参 | doc/10 Q6.2 裁定 V1.1 仅全额；系统取原单 `amount_cent`，杜绝前端传错金额 |
| D3 | `refund_no` 前缀 `RF` 复用 PAY-101 订单号生成器 | 与业务订单号 `PREORD-`/`GACHA-` 平行，对账中心人肉可读；不另造序列 |
| D4 | 受理失败回滚 paid / 回调失败留 failed 人工介入 | 区分"受理失败可重试"与"回调失败需人工"，对齐 doc/10 §6.E4 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | §0 自检假设上游表已建 → 实际 `gz_pay_refund` / `gz_pay_callback_log` 不存在 | **§0 自检 grep migration 目录确认上游表实际存在**（`ls db/migration/` + grep `gz_pay_transaction` / `gz_pay_callback_log`）；PAY-101 未 merge 则 STOP 报 Kevin，不假设 |
| R2 | 退款 SPI key 与 PAY-101 支付 SPI key 撞 | PAY-101 定 SPI 路由表后，104/102/103 落地串行 review 一次（README R2）；退款用独立类型 key |
| R3 | 真实退款 API 失败（余额不足 / 网络）→ status 卡 `refunding` | admin 订单详情 `refunding` 态给「重试退款」按钮（复用本接口）+ PAY-102 主动查单可扫退款态补单（D08 内对齐）+ 告警 |
| R4 | 下游 mp ticket 误加退款 UI | 本卡 §强约束 #5 + ORD-105 / GACHA 订单详情 ticket §0 自检 grep 「联系客服」文案占位 + Kevin 批量人验必查 |
| R5 | 真实商户配置滞后 | 外部前置风险（Kevin 决策 1）；mock 全链路自测为本日 DoD，真实端到端不当默认就绪 |

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D08/GZ-PAY-103 revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。
-->
