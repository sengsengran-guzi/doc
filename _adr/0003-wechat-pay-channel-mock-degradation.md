# ADR-0003 微信支付通道商户号未到位的 mock 降级与真实通道补打时机

- 日期：2026-06-01
- 状态：Accepted
- 决策人：Kevin（kevin-product 评估，kevin-coder 落地）
- 关联 ticket：GZ-PAY-001（V1.0 通道 HelloWorld）

---

## 背景

合同 §2.1 第一期要求 V1.0「微信支付 V3 商户号申请 + 通道调通」（仅链路打通，不接业务订单）。前置硬依赖是甲方公司主体的商户号下证。

时间线现实：

- 甲方商户号资料 2026-05-29（D03）才启动申请，微信侧审核 5-10 工作日。
- V1.0 收官硬期限 2026-06-15。GZ-PAY-001 落地日（D07，2026-06-01）时商户号**远未下证**。

直接后果：无法跑真实 0.01 元端到端单（拿不到真实 prepay_id / 真实回调）。AC 1（商户号主体核对）+ AC 11（真实单端到端）无法在 D07 完成。但 GZ-PAY-001 是 V1.0 必交项，不能因外部资质阻塞整个支付域代码落地。

## 决策

### 1. mock + real 双实现 + profile 切换（决策 D2）

抽象 `IWechatPayClient` 接口，两套实现：

- `MockWechatPayClient`（`@ConditionalOnProperty client-mode=mock`，matchIfMissing=true）：固定 prepay_id + 固定占位 5 参签名 + 不验签直接解析 body。dev 默认 + 单测永远走它，不依赖真实证书 → CI 稳定。
- `WechatPayV3ClientImpl`（`@ConditionalOnProperty client-mode=real`）：官方 SDK `wechatpay-java` 真实实现（RSAAutoCertificateConfig 自动证书轮换 + NotificationParser 验签 + AES-GCM 解密）。**已实现但未真实联调**，商户号下证后 staging 切 real profile 再跑。

dev profile `gz.pay.client-mode=mock`；prod profile `gz.pay.client-mode=${WECHAT_PAY_CLIENT_MODE:mock}`（下证前保持 mock，下证后改 env var 为 real）。

三表 + 验签 + 幂等（乐观锁 + transaction_id UNIQUE）+ callback_log + 超时关单逻辑**全部实现并以 mock 单测覆盖**（AC 10 共 5+1 个方法全绿）。商户号到位前 staging 也用 mock；mock 闭环靠 admin 测试工具页 + mp test.vue 的「模拟回调」按钮（调 `/system/gz/pay/test/simulate-callback` 构造回调 body 走真实 handlePaymentNotify 链路）驱动订单 paid —— 等价真实回调，验证全链路状态机 / 幂等 / 审计落库。

### 2. 真实通道补打时机（pending，待 Kevin × 甲方）

商户号下证后**当日 1 小时内**：

1. **AC 1 主体核对（STOP 闸口）**：Kevin 核对商户号挂「成都谷子宇宙贸易有限公司」主体（合同 §2.3 / CLAUDE.md §7 #12）。若显示其他主体（法人个人 / 关联公司）→ STOP，要求甲方重申，避免二清违规。核对通过后在 GZ-PAY-001 reports 追加一行「商户号主体核对 ✅，mch_id=XXXXX 挂成都谷子宇宙贸易有限公司」。
2. **注入 env var**：staging/prod 注入 `WECHAT_PAY_MCH_ID / WECHAT_PAY_API_V3_KEY / WECHAT_PAY_CERT_SERIAL / WECHAT_PAY_PRIVATE_KEY_PATH / WECHAT_PAY_CERT_PATH / WECHAT_PAY_NOTIFY_URL`（强约束 #4：明文密钥不入 DB / 不入 git）。staging 切 `WECHAT_PAY_CLIENT_MODE=real`。
3. **AC 11 真实单端到端**：staging（HTTPS，微信 V3 回调要求）跑真实 0.01 元单，验证 prepay_id → uni.requestPayment → 真回调 → 验签 → paid 全链路。截图 + DB transaction status=paid + callback_log 入 reports 追加段。
4. **不下证不上 prod**：prod 保持 mock 直到真实单在 staging 跑通。

**此 4 步是 V1.0 buffer 期（6/10-6/15）补打项，列为 pending，需 Kevin 介入（甲方资质 + 真实支付）。不阻塞 D07 ticket close。**

### 3. 官方 SDK 而非社区包（决策 D1）

用官方 `com.github.wechatpay-apiv3:wechatpay-java:0.2.17` 而非社区 `weixin-java-pay`。理由：官方维护，V3 协议跟进及时；社区包 V3 支持滞后。

依赖冲突核对（AC 3 / §0 自检 `mvn dependency:tree`）：仓库内**无任何其他 wxpay 包**（grep 全仓 pom 为空）→ 无版本冲突。wechatpay-java 0.2.17 传递引入 gson 2.13.2（runtime，SDK 内部用，与 ruoyi 主用的 jackson 隔离）/ bouncycastle bcpkix+bcprov-jdk18on 1.83 / okhttp 4.10.0 / jackson-databind 2.21.2（Spring Boot BOM 管理对齐）。这些 net-new 依赖仅 SDK 自用，ruoyi 无任何类引用 → 无硬冲突。

### 4. 调度框架 = SnailJob（不是 Quartz）

超时关单 cron（AC 8）用 SnailJob `@JobExecutor(name="gzPayExpireOrderTask")`，核心逻辑在 service，job 类仅触发壳（样板 GzBeanNoShowMarkJob）。**仓库无 `sys_job` 表**，绝不在 Flyway DDL `INSERT INTO sys_job`（会启动 hard-fail）。job 注册参数（任务名 GZ-PAY-EXPIRE-ORDER / 路由 gzPayExpireOrderTask / CRON `0 0/5 * * * ?` / 阻塞 DISCARD / 组 ruoyi_group）由 SnailJob 控制台手工注册（见 reports/GZ-PAY-001.md §SnailJob 控制台注册）。

## 后果

- ✅ V1.0 支付域代码完整落地（三表 + 验签 + 幂等 + 超时关单 + admin + mp），不被外部资质阻塞。
- ✅ 单测稳定（永远 mock，CI 不依赖真实证书）。
- ✅ 商户号到位后切 profile + 注入 env var 即可无缝切真实通道，代码零改动。
- ⚠️ 真实 0.01 元端到端单是 buffer 期 pending，依赖甲方商户号下证 + Kevin 主体核对 + 真实支付。这是 V1.0 唯一一个「代码就绪、待外部资质」的尾项。
- ⚠️ `WechatPayV3ClientImpl` 真实实现已写但未联调，buffer 期真实单可能暴露 SDK API 细节微调（如 buildPayParams 与 createJsapiOrder 的 5 参一致性）—— 届时在 staging real profile 调通，不影响 mock 单测。
