# GZ-PAY-001 ★ — 微信支付 V3 商户号申请 + 通道 HelloWorld

**优先级**: P0
**复杂度**: M（V1.0 收尾日复杂 ticket — 涉及外部商户号资质 + 微信 V3 SDK + 回调验签幂等三套机制，禁止快速过 §0 自检）
**关联 PRD**: doc/02-prd.md M1 §微信支付 + 合同 §2.1 第一期（一）+ §2.3 商户号主体强约束
**关联拆解**: doc/02-需求拆解.md §2.2 第 262-277 行
**关联 mockup**: design/mockup/pay-result.html（**三态并排**：成功 / 失败 / 超时 — V1.0 用于通道测试展示页；视觉参考，**设计冻结期不还原**）
**关联 ADR**: —（如商户号未到位需降级走 mock 链路，可写 ADR-0003 决策真实通道补打时机）
**依赖**: GZ-SYS-001 ✅（云服务到位）+ 甲方商户号资料 D03（5/29）已启动申请流程

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡 + ★ 重点反复读）

- **业务流**：doc/10-业务流权威图.md **§2 微信支付通道接入流（M1-B，V1.0 HelloWorld 级）全文**，特别是：
  - §合同引用（§2.1 V1.0 仅通道调通不接业务 + §2.3 商户号主体强约束）
  - §关键节点 N1-N7（统一下单 / prepay_id / wx.requestPayment / 回调 / 验签 / 幂等 / paid）
  - §异常分支 E1-E5（验签失败 / 重复回调 / 超时关单 / 商户号未到位 / 回调延迟）
  - §强约束 #12（商户号挂甲方主体）
- **字段表**：doc/11-字段权威表.md
  - **§4.1 `gz_pay_channel`**（通道配置 — V1.0 仅 `wechat_pay_v3` 一行；prod 环境 `api_v3_key` / 商户证书私钥**走密钥管理服务不入 DB**，本表存配置引用）
  - **§4.2 `gz_pay_transaction`**（支付订单统一表 — V1.0 测试单用 `business_type='test'` + `out_trade_no='TEST-yyyyMMdd-000001'`）
  - **§4.3 `gz_pay_callback_log`**（微信回调原始流水 — 永不更新的审计表，保留 12 个月）
  - 附录 A.2 支付状态枚举（`created` / `pending` / `paid` / `timeout` / `closed` / `failed` / `refunding` / `refunded`，V1.0 只用前 5 个）
- **合同**：doc/03-contract.md §2.1 V1.0 范围 + §2.3 商户号主体（**Kevin 收到商户号资料时必核对主体名**）
- **UI 参考**（设计冻结期）：doc/12-UI-权威索引.md §MP-PAY-RESULT — 支付结果页（成功 / 失败 / 超时三态）；mp 端实装走 wot-design-uni 默认；admin 端测试工具页用 plus-ui BizTable 默认

## What

V1.0 通道层 HelloWorld：打通"统一下单 → prepay_id → 小程序 wx.requestPayment → 微信回调 → 后端验签 + 幂等 + 入库 paid"完整链路，跑通 0.01 元测试单。**V1.0 仅通道调通，不接业务订单**（扭蛋 / 预购 V1.1 才接）。

降级方案：商户号未下证时仅做 SDK 集成 + 配置抽象 + mock 测试（WireMock 拦截统一下单 + 回调），真实链路在 buffer 期补打。

## AC（验收标准）

- [ ] **AC 1 商户号主体核对**：Kevin 在收到甲方资料时**必须核对**：
  - 商户号挂"成都谷子宇宙贸易有限公司"主体（合同 §2.3 + CLAUDE.md §7 #12 锚定）
  - 若资料显示其他主体（如甲方法人个人名义 / 关联公司）→ **STOP**，要求甲方重申，避免二清违规
  - 核对完成后在本 ticket reports 写一行「商户号主体核对 ✅，mch_id=XXXXX 挂成都谷子宇宙贸易有限公司」
- [ ] **AC 2 DDL**：`V202606041200__GZ-PAY-001-create-gz_pay_channel-and-transaction-and-callback_log.sql` 落三张表，**字段严格按 doc/11 §4.1/4.2/4.3**：
  - `gz_pay_channel`（channel_code / display_name / appid / mch_id / api_v3_key_ref / mch_cert_serial / notify_url / refund_notify_url / enabled + 公共字段）
  - `gz_pay_transaction`（out_trade_no / business_type / business_order_no / user_id / openid / channel_code / amount_cent / currency / fee_cent / status / prepay_id / transaction_id / paid_time / expire_time / closed_time / version + 公共字段）
  - `gz_pay_callback_log`（transaction_id / out_trade_no / callback_type / raw_body / signature / process_status / process_error + 公共字段）
  - **UNIQUE 索引含 tenant_id**（CLAUDE.md §6 #3）：`uk_tenant_out_trade_no` / `uk_tenant_transaction_id` WHERE NOT NULL
  - INSERT `gz_pay_channel` 1 行 `wechat_pay_v3` 默认配置（dev profile mch_id / api_v3_key 走环境变量 `${WECHAT_PAY_MCH_ID:placeholder}`，CLAUDE.md §6 #5 + dongjiaoshan 同款）
- [ ] **AC 3 SDK 集成**：后端 pom 引入 `com.github.wechatpay-apiv3:wechatpay-java:0.2.x`（官方 V3 SDK；如 ruoyi 已传递依赖 `wx-java-pay` 则评估是否复用，**优先官方 SDK**避免社区包停更风险）；§0 自检 `mvn dependency:tree` 确认无冲突
- [ ] **AC 4 统一下单 API**：admin 端测试工具页 `POST /system/gz/pay/test/create-order`（参数 `amount_cent`，仅 owner 权限 `gz:pay:test`）：
  - 后端生成 `out_trade_no=TEST-yyyyMMdd-000001`（每日自增序号；`gz_pay_transaction` 落 `business_type='test'` + `status='created'` + `expire_time=now+5min`）
  - 调微信 V3 `/v3/pay/transactions/jsapi` 统一下单 → 拿到 `prepay_id`
  - UPDATE transaction 写 prepay_id + status='pending'
  - 返回 mp 端可用的支付参数（`timeStamp` / `nonceStr` / `package` / `signType` / `paySign`）— 按微信文档计算 paySign（RSA SHA256 with 商户私钥）
- [ ] **AC 5 mp 端拉起支付**：mp 端 `pages/pay/test.vue`（仅测试用，dev 环境可见）+ `pages/pay/result.vue`（三态展示，doc/12 §MP-PAY-RESULT）：
  - test.vue 提供「发起 0.01 元测试支付」按钮 → 调 admin API 拿支付参数 → `uni.requestPayment(...)`
  - 成功 / 失败 / 取消三态 → 跳 result.vue 显示对应状态（成功页轮询后端 `GET /app/gz/pay/transaction/{out_trade_no}/status` 等回调到达 status=paid）
- [ ] **AC 6 回调验签**：后端 `POST /api/pay/v3/notify`（**无 sa-token**，对微信开放；doc/11 §4.1 notify_url 固定值）：
  - 用 SDK `NotificationParser.parse(...)` 验证 `Wechatpay-Signature` HTTP 头 + AES-GCM 解密 body
  - **验签失败** → 写 `gz_pay_callback_log` process_status='failed' + 返回 HTTP 401（微信会重试，但失败的不应静默 — log.error 告警）
  - **验签成功** → 写 `gz_pay_callback_log` process_status='received' + raw_body / signature 入库
- [ ] **AC 7 幂等防重**：
  - 用 `gz_pay_transaction.transaction_id` UNIQUE 约束兜底（微信侧 transaction_id 是天然幂等 key）
  - 业务层在 UPDATE transaction status='paid' 前先 SELECT 判断：若已 status='paid' → 直接返回成功（视为重复回调），写 callback_log process_status='duplicated'
  - 用乐观锁 `UPDATE ... WHERE id=? AND version=? AND status='pending'`（版本号 + 状态双重 check）
- [ ] **AC 8 异常告警**（拆解 §2.2 AC 3 强约束）：
  - 验签失败 → log.error + 写 callback_log process_status='failed'（V1.0 不接钉钉告警，仅日志 + DB 审计）
  - 超时关单 → cron 每 5 min 扫 `status='pending' AND expire_time < now()` → UPDATE status='timeout'（doc/10 §2 E5）
- [ ] **AC 9 mock 降级路径（商户号未到位）**：
  - service 层抽象接口 `IWechatPayClient`：真实实现 `WechatPayV3ClientImpl`（用官方 SDK） + mock 实现 `MockWechatPayClient`（返回固定 prepay_id + 模拟回调）
  - dev profile 默认走 mock（`gz.pay.client.mode=mock`）/ staging+prod 走 real（`gz.pay.client.mode=real`）
  - 单测用 mock；商户号到位前 staging 也用 mock；商户号到位后切 staging real profile + 跑 0.01 元
- [ ] **AC 10 单测**：`GzPayTransactionServiceImplTest` ≥ 5 个测试方法：
  - happy path（统一下单 → 回调 → paid，mock IWechatPayClient）
  - 重复回调（同一 transaction_id 第二次 → duplicated）
  - 验签失败（mock parser throw → callback_log status='failed' + 不更新 transaction）
  - 乐观锁冲突（并发两个回调 → 第二个 UPDATE 受影响行 0 → 视为已处理）
  - 超时关单（mock expire_time < now → cron 触发 UPDATE timeout）
- [ ] **AC 11 集成测试（reports 必须贴 raw output）**：
  - **商户号到位场景**：真实 0.01 元测试单端到端 — 贴 mp 端支付参数 JSON / 微信侧支付截图 / 后台回调日志 / DB transaction status=paid
  - **商户号未到位场景**：mock 链路全绿 — 贴 mock client 返回 / 模拟回调 HTTP request / DB transaction status=paid（mock 回调驱动）/ 单测全绿 raw output
  - **回调验签压测**（reports 必须）：用 `curl` + 错误签名 → 期望 401 + callback_log process_status='failed'（贴 raw output）
- [ ] **AC 12 menu_id 插入**：admin 端「支付管理」目录 menu_id **5100**（如不存在则建）；「通道配置」menu_id **5101** + perms `gz:pay:channel:list/edit`；「支付订单（测试）」menu_id **5102** + perm `gz:pay:transaction:list`；「测试工具」menu_id **5103** + perm `gz:pay:test`

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-common/`（PAY 模块跨业务线 — 扭蛋 / 预购 / 拼豆都会调；放 common 避免循环依赖；后续 V1.1 体量起来再独立 gz-pay 模块）
  - `controller/GzPayChannelController.java`（admin 通道配置 CRUD，路径 `/system/gz/pay/channel`）
  - `controller/GzPayTransactionController.java`（admin 订单列表 + 详情，路径 `/system/gz/pay/transaction`）
  - `controller/GzPayTestController.java`（admin 测试工具，路径 `/system/gz/pay/test`）
  - `controller/applet/GzPayMpController.java`（mp 端查支付状态轮询，路径 `/app/gz/pay`）
  - `controller/external/WechatPayNotifyController.java`（**对外路径 `/api/pay/v3/notify`** — 无 sa-token，仅微信 IP 白名单 + 验签鉴权）
  - `service/IGzPayTransactionService.java` + `service/impl/GzPayTransactionServiceImpl.java`
  - `service/internal/IWechatPayClient.java` + `WechatPayV3ClientImpl.java` + `MockWechatPayClient.java`（双实现）
  - `service/internal/PayOrderNoGenerator.java`（业务订单号生成 `TEST-yyyyMMdd-000001` 格式 / 后续业务复用）
  - `job/GzPayExpireOrderJob.java`（cron 5 min 扫超时关单）
  - `domain/GzPayChannel.java` / `GzPayTransaction.java` / `GzPayCallbackLog.java` + VO + BO
  - `mapper/*` 三表对应 mapper
  - DDL × 1（三表 + sys_job + sys_menu × 4 + INSERT channel 默认行）
  - `application-dev.yml` 加 `gz.pay.client.mode=mock` + `gz.pay.test.amount-cent=1`
  - `application-staging.yml` / `application-prod.yml` 加 `gz.pay.client.mode=real` + env var 占位符（`WECHAT_PAY_MCH_ID` / `WECHAT_PAY_API_V3_KEY` / `WECHAT_PAY_CERT_PATH` / `WECHAT_PAY_PRIVATE_KEY_PATH`）
- **Admin**：`plus-ui/src/views/gz-pay/`
  - `channel/index.vue`（通道配置 — V1.0 只读展示，不编辑，因为 prod 字段走环境变量）
  - `transaction/list.vue`（订单列表 — BizTable + 筛选 status / business_type）
  - `transaction/detail.vue`（订单详情 — 含回调日志展示）
  - `test/index.vue`（测试工具页 — 输入金额 + 发起测试单 + 显示二维码 / 跳转链接）
- **小程序**：`miniapp/src/pages/pay/test.vue`（dev 环境可见）+ `miniapp/src/pages/pay/result.vue`（三态，doc/12 §MP-PAY-RESULT）+ `api/gz-pay.ts`
- **测试**：mvn 单测（mock 全链路） + 商户号到位时真实 0.01 元端到端 + curl 验签压测

## 备注

### 强约束 ★

1. **商户号挂甲方主体**（合同 §2.3 / CLAUDE.md §7 #12）— Kevin 资料核对环节强制 STOP 闸口
2. **V1.0 仅通道调通**（合同 §2.1 / 拆解 §2.2 AC 4）— 不接业务订单；测试单 `business_type='test'`
3. **回调验签 + 幂等 + 异常告警三件套**（拆解 §2.2 AC 3）缺一不可
4. **prod api_v3_key / 商户证书私钥不入 DB / 不入 git**（doc/11 §4.1 锚定）— 走环境变量 + KMS（V1.0 staging+prod 用 env var，KMS V1.1+ 上）
5. **回调路径 `/api/pay/v3/notify` 不走 sa-token**（对微信开放）— 安全靠验签 + 微信 IP 白名单（V1.0 仅验签，IP 白名单 prod 上线前由运维加 nginx 层）
6. **out_trade_no 全局唯一 + 含 tenant_id UNIQUE**（CLAUDE.md §6 #3）— 业务码格式 `<域>-yyyyMMdd-6位序号`，doc/11 §4.2 锚定
7. **transaction_id（微信侧）UNIQUE WHERE NOT NULL**（doc/11 §4.2）— 幂等基础；MySQL 8 函数索引或业务层兜底
8. **超时关单 cron 必须有**（doc/10 §2 E5）— pending 订单 5 min 无回调 → status='timeout'；避免 pending 堆积
9. **callback_log 表永不 UPDATE**（除 process_status）— doc/11 §4.3 纯审计表，事后追溯依赖

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 用官方 SDK `wechatpay-java` 而非社区 `wx-java-pay` | 官方维护，V3 协议跟进及时；社区包 ruoyi 引入但 V3 支持滞后 |
| D2 | mock + real 双实现 + profile 切换 | 商户号下证前后无缝切换；单测稳定（永远 mock）；不破坏 CI |
| D3 | 通道 CRUD V1.0 只读（不允许 admin 编辑 mch_id 等）| 配置错误后果严重；prod 走环境变量；admin 只看不改 |
| D4 | 业务订单号格式 `<域>-yyyyMMdd-6位序号` | 与 doc/11 §4.2 锚定一致；可读性 + 排序友好；6 位序号每日 100 万订单上限 V1 够用 |
| D5 | 回调路径独立 `/api/pay/v3/notify`（不走 `/system` 或 `/app`）| 微信回调 URL 注册时一次性固定；与业务路径前缀解耦 |
| D6 | 验签失败也写 callback_log | 审计完整性 — 事后可追溯是不是真的有恶意请求 |
| D7 | mp 端支付结果页 result.vue 不实时等回调，而是轮询 status | 微信侧回调有延迟（典型 1-5 秒，最多 1 分钟）；mp 端用户体验上不可能挂起等；轮询 + 显示 loading 友好 |
| D8 | 测试工具页放 admin 而非 mp 端硬入口 | dev/staging 调试用 admin owner 触发更专业；mp 端 pay/test.vue 仅 dev 环境可见 |

### 风险提示 ★

| # | 风险 | 缓解 |
|---|---|---|
| R1 ★ | 商户号 6/04 未下证 | 降级 mock 链路 / buffer 期补打（特殊约束 §A）+ ADR-0003 记录补打时机；不阻塞 V1.0 收官 |
| R2 ★ | 甲方提供的商户号资料主体错误（如个人 / 关联公司）| Kevin STOP + 要求甲方重申；写在合同沟通记录里 |
| R3 | wechatpay-java SDK 版本与 ruoyi 已有依赖冲突 | §0 自检 `mvn dependency:tree`；如冲突回 ADR-0003 评估 social wx-java-pay 替代 |
| R4 | 回调验签密钥 api_v3_key 配置错误 → 全部回调验签失败 | dev 用 mock 不依赖真密钥；prod 上线前 staging 用真密钥跑 0.01 元单端到端验证 |
| R5 | 回调延迟 / 重复 / 乱序 | 幂等设计 + transaction_id UNIQUE + 乐观锁 + callback_log 审计；微信文档说明回调可能延迟最多 24h 我们等 |
| R6 | mp 端 wx.requestPayment 拒绝（用户取消 / 未授权）| 前端 catch → result.vue 显示「失败 / 已取消」；不影响后端 transaction（保持 pending → 5 min 后 cron 关单为 timeout）|
| R7 | dev 环境无 HTTPS → 微信回调 URL 注册失败（V3 要求 HTTPS）| dev 走 mock 不接真实回调；staging 必须 HTTPS（CLAUDE.md §6 nginx + Let's Encrypt，与 dongjiaoshan 同款方案）|
| R8 | 测试工具页发起 0.01 元真实付款误成本 | 接受 — 单笔 1 分钱可控；Kevin 自己测；prod 上线后此页关闭（perm `gz:pay:test` 仅 dev/staging 给 owner）|
| R9 | callback_log raw_body 体积 → 12 个月保留导致表膨胀 | V1.0 流量低（< 100 笔/月）问题不大；V1.1 起 cron 月清理 > 12 个月数据（doc/11 §4.3 锚定）|
| R10 | 与下游 V1.1 业务接入的契约（business_type=`gacha`/`preorder`）冲突 | service 层接口 `createTransaction(BusinessType, OrderNo, Amount, Openid, ...)` 抽象到位；V1.1 业务调用方提供 business_type + business_order_no 即可 |

### ADR 候选

- **ADR-0003**：商户号未到位时通道补打时机（建议方案：商户号下证当日 1 小时内 Kevin 补打 0.01 元单 + 写 reports 追加段；不下证不上 prod）— 仅在 6/04 商户号未到位时新建

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
