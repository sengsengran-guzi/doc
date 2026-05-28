# GZ-PAY-103 — 退款服务（特例触发）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M2 §扭蛋 §异常分支 + M3 §预购 §异常分支 + §业务规则 4.2 退款
**关联拆解**: doc/02-需求拆解.md §3.1 第 656-668 行
**关联 mockup**: design/mockup/admin-orders.html（订单详情内"申请退款"按钮）
**关联 ADR**: —
**依赖**: GZ-PAY-101 + GZ-ADMIN-103 ✅（V1.0 已完工 admin 订单详情骨架）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md
  - §2 微信支付通道接入流（V2 退款 API 参考）
  - §6 V1.1 演进流（PAY-101 同日新增的 §6.1 业务支付统一流 + 本 ticket 实施前在 §6.2 补"退款流"段）
- **字段表**：doc/11-字段权威表.md
  - §4.1 gz_pay_order（refund_fen 字段 / status='refunding'/'refunded'）
  - §4.3 gz_pay_refund 退款明细表（id / pay_order_id / refund_no / amount_fen / reason / operator_id / status / refund_at + 公共字段）
  - §4.5 支付状态字段口径（refunding / refunded 2 态加入）
  - **§4.6 4% 分成核心计算口径**（退款必须扣除分成基数）
- **UI 参考**：admin-orders.html 订单详情底部按钮区（"申请退款"红色 outline 按钮，仅 owner 角色可见）

## What

后台运营 / 客服判断特例后从 admin 订单详情手动触发退款（**C 端无退款入口**，合同 §4.5 强约束）：

1. admin 订单详情底部增"申请退款"按钮（owner 权限校验）
2. 点击 → 弹确认框输入退款金额（默认全额）+ 退款原因（必填）
3. 后端调微信退款 API + 落 gz_pay_refund 行 status=refunding + gz_pay_order.status=refunding
4. 微信异步退款回调 `/api/wxpay/refund-notify` → 更新 gz_pay_refund.status=success + gz_pay_order.refund_fen 累计 + 当全额退完则 status=refunded
5. 触发业务方退款回调（SPI 同 PAY-101 模式，业务方更新自己的订单为 refunded / cancelled）
6. 可选订阅消息通知用户

## AC（验收标准）

- [ ] **AC 1**：DDL `V<ts>__GZ-PAY-103-create-gz_pay_refund.sql` 落 `gz_pay_refund` 表（按 doc/11 §4.3）：
  - id / pay_order_id / refund_no (UNIQUE) / amount_fen / reason VARCHAR(500) NOT NULL / operator_id BIGINT NOT NULL / status enum(`refunding`/`success`/`failed`) / refund_at / wx_refund_id / + 公共字段 + tenant_id
  - 索引 `idx_pay_order` `idx_operator_at`
  - ALTER gz_pay_order 加 `refund_fen INT NOT NULL DEFAULT 0`（如 PAY-101 DDL 已含则跳过）
- [ ] **AC 2**：admin 端 `POST /system/gz/pay/refund/apply` 接口：
  - sa-token user 校验 + 角色 owner 权限（`@SaCheckRole("owner")`）
  - 参数 payOrderId + amountFen + reason
  - 校验：原订单 status='paid' + refund_fen + amountFen <= amount_fen（不超退）
  - 生成 refund_no（格式 `R-{yyyyMMddHHmmss}-{6 位序号}`，同 PAY-101 OrderNoGenerator 复用）
  - INSERT gz_pay_refund status='refunding' + UPDATE gz_pay_order.status='refunding'
  - 调微信 `secapi/pay/refund` API（带商户证书 — 退款 API 必须 mTLS）
  - 微信返回 SUCCESS → 等异步回调；返回 FAIL → UPDATE gz_pay_refund.status='failed' + 抛业务异常给前端
- [ ] **AC 3**：微信退款回调 `/api/wxpay/refund-notify` 独立 endpoint（**不与 PAY-101 支付回调共用**）：
  - 解密回调 XML（退款回调用 MD5(api_key) 解密 req_info）
  - 签名校验 + 幂等（同 refund_id 已处理则返回 SUCCESS）
  - 成功：UPDATE gz_pay_refund.status='success' + refund_at + wx_refund_id + UPDATE gz_pay_order.refund_fen += amount_fen → 当 refund_fen == amount_fen → status='refunded'
  - 失败：UPDATE gz_pay_refund.status='failed' + reason
  - 触发业务方退款 handler（SPI `IRefundCallbackHandler` 按 BizType 路由 — 与 PAY-101 IPayCallbackHandler 平行接口）
- [ ] **AC 4** ⭐：**C 端无退款入口**（合同 §4.5 + doc/02 §3.1 强约束）：
  - mp 订单详情页**不允许**出现"申请退款"按钮
  - 仅显示文案「如需退款请联系客服」+ 客服入口（GZ-SYS-004 已实现）
  - 本 ticket 不写 mp UI（仅约束 ORD-105 + 后续 GACHA 订单详情 ticket 不要加退款入口）
- [ ] **AC 5**：admin 退款按钮 UI（订单详情底部）：
  - 仅 owner 角色可见（前端 `v-hasRole="'owner'"`）
  - 点击弹 Element Plus `<el-dialog>` 确认框 → 金额 input（默认全额）+ reason textarea（必填，≤ 500 字）
  - 提交 → loading → 接口成功 toast「退款已提交，等待微信处理」+ 关闭弹窗 + 刷新订单详情
  - 退款记录显示在订单详情下方 `<el-table>`（refund_no / 金额 / 原因 / 操作人 / 状态 / 时间）
- [ ] **AC 6**：操作日志 `@Log(title="支付退款", businessType=OTHER)` 写入 sys_oper_log
- [ ] **AC 7**：订阅消息通知（**可选** — 不阻塞 ticket 完工）：退款成功后调微信订阅消息 API 推「退款已到账」给用户；mp 端 ORD-103 下单时引导用户授权一次性订阅
- [ ] **AC 8**：单测覆盖：
  - happy path：申请退款 → mock 微信 SUCCESS → 模拟回调 → status refunded
  - 部分退款：amount < 总额 → status=refunding 仍可再退
  - 不超退校验：refund_fen + amount > amount_fen → 抛异常
  - 非 paid 订单不允许退款
  - 共 ≥ 4 个测试方法

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-common/pay/`
  - `controller/admin/PayRefundController.java`（路径 `/system/gz/pay/refund`）
  - `controller/WxPayRefundCallbackController.java`（路径 `/api/wxpay/refund-notify`，无 sa-token）
  - `service/IPayRefundService.java` + `service/impl/PayRefundServiceImpl.java`
  - `service/spi/IRefundCallbackHandler.java`（SPI 接口，业务方实现）
  - `service/internal/WxRefundReqInfoDecryptor.java`（解密退款回调专用）
  - `domain/GzPayRefund.java` + req/vo
  - `mapper/GzPayRefundMapper.java`
  - DDL × 1
- **Admin 前端**：`code/main/plus-ui/src/views/gz-pay/`（可能需新建该目录 — V1.0 暂无）
  - 复用 V1.0 已有 ADMIN-103 订单详情页（`gz-admin/order/detail.vue` 或类似路径），在底部 slot 加退款按钮 + 弹窗组件 `RefundApplyDialog.vue`
  - api 文件 `src/api/gz-pay/refund.ts`
  - **走 ruoyi/Element Plus 默认审美**（V1.1 admin 视觉规范以 6/14 风格统一为准，今日如未确定 → 默认值）
- **小程序**：N/A（本 ticket 严格禁止 mp 加退款入口）
- **测试**：mvn 单测 + Postman 模拟微信退款回调 XML

## 备注

### 强约束 ⭐

1. **C 端绝对无退款入口**（合同 §4.5 + 合同附件二客户运营约定）— mp ORD-105 + 后续所有订单详情 ticket 严禁加退款 UI
2. **owner 角色权限校验后端 + 前端双重**（不能仅靠前端隐藏按钮）— `@SaCheckRole("owner")`
3. **退款 API 必须 mTLS**（微信 V2 退款 API 强制商户证书）— staging/prod cert 由 Kevin 6/16 上午导入
4. **退款回调 endpoint 必须独立**（`/api/wxpay/refund-notify` 与 PAY-101 `/api/wxpay/pay-notify` 分离）— 路由 + 处理器 + 签名解密算法均不同
5. **refund_fen 累计字段**（doc/11 §4.6 锚定）— 支持多次部分退款；4% 分成计算公式：`分成基数 = amount_fen - refund_fen - channel_fee_fen`
6. **业务 handler SPI 不复用 PAY-101 IPayCallbackHandler** — 退款是另一回调链路（IRefundCallbackHandler）；业务方实现可以共享但接口不混
7. **operator_id 必须落库** — 审计 4% 分成异常时溯源运营人
8. **i18n**：admin 文案走 `t('pay.refund.xxx')`

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 独立退款回调 endpoint | 微信退款回调 XML 加密格式与支付回调不同（req_info AES 加密），混用易踩坑 |
| D2 | 退款 SPI 接口与支付 SPI 平行而非共用 | 业务语义不同（paid → refunded 不是 paid 的逆），分接口表达更清晰 |
| D3 | 支持部分退款 | 客服判断"商品 2 件中 1 件破损"等场景，部分退款比全退合理 |
| D4 | refund_no 格式 `R-{ts}-{seq}` 与 order_no 平行 | 复用 OrderNoGenerator 减少代码；R 前缀防止与订单号混淆 |
| D5 | 订阅消息通知可选 | 不阻塞 ticket 完工，D11 客服中心 ticket 再统一接入订阅消息 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 业务 handler 内更新业务订单状态时与原订单已完成的下游流程冲突（如预购已发货后退款） | handler 内实现需自行判断 — 已发货订单退款仅退款不撤物流；本 ticket 仅保证 PAY 层动作正确，业务侧自己决策（ORD-104 / GACHA-104 实施时自检） |
| R2 | 微信退款 API 失败（余额不足 / 网络）→ status='refunding' 永远停 | admin 端订单详情显示 status='refunding' 时给"重试退款"按钮（仅 owner，复用本 ticket 接口）+ 监控告警 |
| R3 | 多次部分退款累计超过总额（前端校验绕过） | 后端 AC 2 强校验 + DB 触发器（可选 — V1.1 不加） |
| R4 | 退款回调 req_info 解密失败 | 落 raw XML 到 gz_pay_callback_log + 监控告警 + 客服走"代退款"流程（直接联系商户后台手动退） |
| R5 | C 端 mp 后续 ticket 误加退款 UI | 本 ticket §强约束 #1 + Kevin testing-human checklist 必查 |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
