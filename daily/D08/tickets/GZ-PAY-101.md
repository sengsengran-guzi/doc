# GZ-PAY-101 — 业务支付统一服务

**优先级**: P1
**复杂度**: M（V1.1 首日 ⭐ — 后续 ORD/GACHA 所有支付场景的通用底座，禁止快速过 §0 自检）
**关联 PRD**: doc/02-prd.md M1 §微信支付 / §下单支付 / §异常分支
**关联拆解**: doc/02-需求拆解.md §3.1 第 628-639 行
**关联 mockup**: design/mockup/order-confirm.html + pay-result.html（仅布局参考；mp 视觉以 C 系统为准，doc/13；本 ticket 为后端底座不写 mp UI）
**关联 ADR**: —（如本 ticket 需决策"统一支付服务抽象层是否独立成 gz-pay 模块 / 是否与 gz-common 合并"可新建 ADR）
**依赖**: GZ-PAY-001 ✅（V1.0 已通道调通 HelloWorld）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md
  - **§2 微信支付通道接入流**（V1.0 已建 HelloWorld）全文重读
  - **§6 V1.1 演进流**（如有 PAY V1.1 段；如无 → 本 ticket 实施前在 doc/10 §6 末追加"§6.1 业务支付统一服务流"，再开始写代码）
- **字段表**：doc/11-字段权威表.md
  - **§4.1 gz_pay_order 支付订单主表**（业务字段 + 状态 + 回调记录 — 完整 DDL 来源）
  - §4.2 gz_pay_callback_log 回调日志表
  - **§4.5 支付状态字段口径**（pending / paid / failed / refunded / refunding 5 态完整定义）
  - **§4.6 4% 分成核心计算口径**（business_line 字段 / GMV / 退款扣除 / 通道费扣除）
- **UI 参考**（mp 视觉走 C 日漫海报浓墨：Biz* 组件 + var(--c-*)，doc/tokens.md + doc/13；旧 mockup 仅布局参考。本 ticket 不写 mp UI）：mp `order-confirm.html` + `pay-result.html`

## What

把 V1.0 仅"通道调通"的微信支付升级为业务统一服务层，提供给 V1.1 后续 ORD（预购）/ GACHA（扭蛋）/ 未来拼豆收费等所有业务场景调用：

1. **统一订单号生成器**：`<业务前缀>-<时间戳>-<6 位序号>`，跨业务全局唯一（DB UNIQUE 约束 + Redis incr 防同毫秒重复）
2. **创建预订单服务**：业务方调 `IPayOrderService.createOrder(bizType, bizOrderId, amount, openId, description)` → 落 gz_pay_order 表 status=pending → 调微信统一下单 API → 返回 prepay_id 给 mp 端调起支付
3. **回调处理服务**：微信回调 `/api/wxpay/pay-notify` → 签名校验 → 幂等检查（同 transaction_id 已处理则直接返回 SUCCESS）→ 更新 gz_pay_order 为 paid + 调业务方注册的回调 handler（SPI 模式按 bizType 路由）→ 业务方完成自己的订单状态变更

## AC（验收标准）

- [ ] **AC 1**：DDL `V<ts>__GZ-PAY-101-create-gz_pay_order-and-callback-log.sql` 落两张表（按 doc/11 §4.1 / §4.2）：
  - `gz_pay_order`：id / order_no (UNIQUE) / business_line enum(`preorder`/`gacha`/`pindou`) / biz_type / biz_order_id / user_id / open_id / amount_fen / status enum / prepay_id / transaction_id / paid_at / channel_fee_fen / refund_fen / 公共字段 + tenant_id
  - **UNIQUE KEY** `uk_tenant_order_no (tenant_id, order_no)` ⭐ 跨业务全局唯一
  - 索引 `idx_user_status` `idx_biz (biz_type, biz_order_id)` `idx_business_line_paid_at`（对账 SQL 用）
  - `gz_pay_callback_log`：id / pay_order_id / transaction_id / raw_xml LONGTEXT / signature_valid TINYINT / processed_at / + 公共字段
- [ ] **AC 2**：订单号生成器 `OrderNoGenerator.generate(bizType)`：
  - 格式：`{bizType}-{yyyyMMddHHmmss}-{6 位 Redis 自增序号}`
  - Redis key `pay:orderno:seq:{yyyyMMddHHmmss}` TTL 60s（同秒内自增，跨秒重置）
  - 业务前缀枚举 `BizTypeEnum`：`PREORDER` / `GACHA` / `PINDOU_FUTURE`（合同 §4.1 业务线 A/B 命名锚定）
- [ ] **AC 3**：`IPayOrderService.createOrder(req)` 服务：
  - 参数：BizType + bizOrderId + amountFen + openId + description
  - 生成订单号 + INSERT gz_pay_order status='pending'
  - 调微信统一下单 API（jsapi）→ 拿 prepay_id
  - 返回 `{orderNo, prepayId, paySign, timeStamp, nonceStr, signType, package}` 给 mp 端调起 `wx.requestPayment`
  - business_line 字段写入：`PREORDER → preorder` / `GACHA → gacha` / `PINDOU_FUTURE → pindou`（合同 §4.1 锚定）
- [ ] **AC 4**：回调处理 `WxPayCallbackController.payNotify(HttpServletRequest)`（路径 `/api/wxpay/pay-notify`，无 sa-token 拦截）：
  - 读 raw XML → 写入 gz_pay_callback_log（先存 raw 防丢失）
  - 微信签名校验失败 → 返回 FAIL XML + 日志 signature_valid=0
  - 签名校验通过 → 按 transaction_id 查 gz_pay_callback_log 是否已处理过（processed_at IS NOT NULL）→ 已处理直接返回 SUCCESS XML（幂等防重 ⭐）
  - 未处理：`SELECT FOR UPDATE` gz_pay_order by order_no → 当前 status 已 paid → 直接返回 SUCCESS（双重幂等）
  - status=pending → UPDATE 为 paid + 写 transaction_id + paid_at + channel_fee_fen → 按 biz_type 路由到业务回调 handler（SPI 模式 `Map<BizType, IPayCallbackHandler>`）→ 业务 handler 失败抛异常则整体回滚（gz_pay_order 仍 pending，等下次回调重试或 PAY-102 cron 补单）
  - 业务回调成功 → UPDATE gz_pay_callback_log.processed_at = now() → 返回 SUCCESS XML
- [ ] **AC 5**：SPI 路由接口 `IPayCallbackHandler`：
  ```java
  public interface IPayCallbackHandler {
    BizType supportedType();
    void onPaid(GzPayOrder order); // 业务方自己更新自己的订单状态
  }
  ```
  本 ticket 只定义接口 + 注册中心（按 Spring Bean 类型注入 Map），不写具体业务实现（业务实现由 ORD-104 + GACHA-104 等下游 ticket 自己注册）
- [ ] **AC 6**：单测必须覆盖：
  - happy path：createOrder + 模拟回调成功 → status paid + handler 被调一次
  - 幂等：同 transaction_id 二次回调 → handler 仅被调一次
  - 签名失败：mock 签名校验返回 false → 返回 FAIL + log signature_valid=0
  - SPI 路由：注册两个 mock handler（PREORDER / GACHA）→ PREORDER 单只触发 PREORDER handler
  - 共 ≥ 4 个测试方法
- [ ] **AC 7**：dev profile 走 sandbox / mock，staging 接真实商户号（cert 由 Kevin 6/16 上午导入）

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/`（PAY 通用底座放 gz-common，业务实现各自模块）
  - `pay/` 子包独立放支付相关
  - `pay/controller/WxPayCallbackController.java`（路径 `/api/wxpay/pay-notify`）
  - `pay/service/IPayOrderService.java` + `service/impl/PayOrderServiceImpl.java`
  - `pay/service/spi/IPayCallbackHandler.java`（SPI 接口）
  - `pay/service/internal/OrderNoGenerator.java` + `WxPaySignValidator.java`
  - `pay/domain/GzPayOrder.java` + `GzPayCallbackLog.java` + req/vo
  - `pay/mapper/GzPayOrderMapper.java` + `GzPayCallbackLogMapper.java`
  - `pay/enums/BizTypeEnum.java` + `PayStatusEnum.java`
  - DDL × 1（两表一文件）
  - `application-dev.yml` + `application-staging.yml` + `application-prod.yml` 加 `gz.pay.appid` / `gz.pay.mch-id` / `gz.pay.api-key` / `gz.pay.notify-url` / `gz.pay.cert-path`（dev sandbox / staging env var）
- **小程序**：本 ticket 不涉及 mp 改动（mp 调用方在 ORD-104 实施时接入 PAY-101 服务）
- **测试**：mvn 单测 + 用 Postman 模拟微信回调 XML 验证幂等

## 备注

### 强约束 ⭐

1. **订单号格式严格 `{bizType}-{yyyyMMddHHmmss}-{6 位序号}`** — 全 V1.1 锚定，对账 SQL 按业务前缀切分
2. **回调幂等性两道防线**（doc/10 §6.1 锚定）：transaction_id 已处理 + order_no 当前 status 已 paid — 缺一不可
3. **签名校验失败必须返回 FAIL**（微信文档要求 — 防伪造）
4. **business_line 字段写入是 4% 分成核算前提**（合同 §4.1 + doc/11 §4.6），两业务线 A/B 不交叉冲抵
5. **SPI 路由用 Spring Bean Map 注入**，不要硬编码 switch-case（新业务接入零代码改动 PAY-101）
6. **回调 endpoint 不走 sa-token 拦截**（微信服务器直发，无登录态）— 在 SecurityConfig 加白名单
7. **channel_fee_fen 字段写入**（合同 §4.1 通道费扣除）— 微信回调 XML 含 `total_fee` 但不含手续费，本 ticket 暂存 0，待对账模块 D11 从微信账单异步回填
8. **i18n**：admin 端如有支付订单查询页文案走 `t('pay.xxx')`（本 ticket 暂不写 admin UI，下游 ticket 接入）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | PAY 通用底座放 ruoyi-gz-common 而非新建 ruoyi-gz-pay | V1.1 时间紧，新建模块成本高；gz-common 已承担通用底座职责（OSS / 微信登录），PAY 逻辑同质归类 |
| D2 | SPI 路由用 Spring Bean Map 注入 | 业务方接入零侵入 PAY-101 代码 |
| D3 | 订单号格式跨业务全局唯一（DB UNIQUE） | 对账 SQL 简化 + 客服查单跨业务统一入口 |
| D4 | 回调 handler 异常 → 整体回滚 + 等下次重试 / cron 补单 | 微信会重试回调 + PAY-102 cron 兜底，不强求当次成功 |
| D5 | dev sandbox / staging+prod 真实商户号走配置切换 | 标准 spring profile 范式 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 ⭐ | 业务方 handler 内部又触发支付相关 DB 操作 → 与 PAY-101 事务嵌套不清 | PAY-101 文档强约束：业务 handler 内仅更新业务订单状态，不允许再触发新支付；本事务为 REQUIRED 传播 |
| R2 | 微信回调延迟 5+ 分钟到达，期间用户重进订单页看到 pending | PAY-102 cron 兜底（每分钟扫 pending > 5min 主动查单）— 与本 ticket 同日完工 |
| R3 | sandbox 与真实环境签名算法差异（V3 vs V2 API） | V1.0 PAY-001 已锁定 V2 API，本 ticket 沿用 V2；后续如客户要求 V3 走 ADR |
| R4 | 跨毫秒并发下订单号撞车（同秒同 Redis incr） | Redis incr 原子性保证 + UNIQUE 兜底（撞车 → 重试一次） |
| R5 | 业务方注册多个 handler 同 BizType → Bean 冲突 | OrderNoGenerator 启动时校验 `Map<BizType, Handler>` 不重复，重复直接 fail-fast |

### ADR 候选

- **ADR-V1.1-0001**：是否新建独立 ruoyi-gz-pay 模块（vs gz-common）— 默认 D1 放 gz-common；如 V1.2 PAY 域膨胀再拆

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
