# GZ-PAY-001 完工报告 — 微信支付 V3 通道 HelloWorld

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git 状态 | N/A（项目无 git 仓库，`git rev-parse` 全层级 not a git repository）— 不阻塞 |
| 上游依赖（GZ-SYS-001 云服务 + 商户号申请） | ✅ SYS-001 已 merge；商户号 5/29 启动申请未下证 → 确定走 mock 降级（AC 9 / ADR-0003） |
| 关键类/表存在 | ✅ gz-common 现有结构已读（GzUser/wechat/job/LogRetentionJob）；gz_pay_* 三表本 ticket 新建 |
| 权威蓝图引用完整性 | ✅ 任务卡引 doc/10 §2 + doc/11 §4.1/4.2/4.3 + doc/12 §MP-PAY-RESULT，均已 Read 并摘录关键约束 |
| 编译健康（gz-common 基线） | ✅ `mvn compile -pl ruoyi-modules/ruoyi-gz-common` 通过（52 个 pay 类 + SDK 真实实现一并编译） |
| ADR 已读/已写 | ✅ 新建 doc/_adr/0003-wechat-pay-channel-mock-degradation.md |
| SnailJob（非 Quartz）| ✅ 读 GzBeanNoShowMarkJob 样板；DDL 无 sys_job INSERT；job 走控制台注册 |
| SDK 依赖冲突 | ✅ `mvn dependency:tree` 确认仓库内无其他 wxpay 包 → wechatpay-java:0.2.17 无冲突 |

**权威蓝图关键约束摘录**：
- doc/11 §4.2：`out_trade_no` 格式 `<域>-yyyyMMdd-6位序号`（test 单 `TEST-` 前缀）；`transaction_id` UNIQUE WHERE NOT NULL（MySQL 唯一索引多 NULL 并存等价此语义）；`version` 乐观锁；状态 created/pending/paid/timeout/closed/failed（V1.0 前 6 态）。
- doc/10 §2：N1 admin 触发 → N2 统一下单 → N3 prepay_id → N6 回调 → N7 验签+幂等 → N8 入流水；E2 验签失败拒收+告警；E3 重复回调幂等；E5 5min 超时 timeout。
- 合同 §2.1 V1.0 仅通道调通不接业务；§2.3 商户号挂甲方主体（Kevin 核对 STOP 闸口）。

## 实现摘要

**改动文件**（新建 31 后端 java + 1 DDL + 4 admin + 3 mp + 1 ADR；改 6 配置/i18n/入口）：

- **后端（ruoyi-gz-common，独占）** 31 个 java：
  - entity ×3 `GzPayChannel/GzPayTransaction/GzPayCallbackLog`；VO ×4；BO ×2；enums ×2（PayStatus/PayBusinessType）
  - mapper ×3（GzPayTransactionMapper 含乐观锁 markPaid / markTimeout / selectExpiredPendingIds / selectMaxDailySeq）
  - service：IGzPayTransactionService + impl（统一下单 + 回调验签幂等 + 超时关单）/ IGzPayChannelService + impl（只读脱敏）
  - internal：IWechatPayClient 抽象 + MockWechatPayClient + WechatPayV3ClientImpl（官方 SDK 真实实现）+ PayOrderNoGenerator + WechatPayVerifyException
  - config：WechatPayProperties（profile 切换）
  - controller ×5：channel（admin 只读）/ transaction（admin 列表+详情+回调日志）/ test（admin 测试工具+mock 模拟回调）/ applet/GzPayMpController（mp 轮询，@SaCheckLogin）/ external/WechatPayNotifyController（**/api/pay/v3/notify，@SaIgnore，验签失败 401+审计**）
  - job：GzPayExpireOrderJob（SnailJob @JobExecutor，触发壳）
  - test：GzPayTransactionServiceImplTest（5 AC + 1 = 6 方法）
- **DDL**：`V202606041200__GZ-PAY-001-...sql`（三表 + sys_menu 5100-5105 + INSERT wechat_pay_v3 默认行；**无 sys_job**）
- **admin（plus-ui/gz-pay）**：api/gz-pay/index.ts + channel/index.vue + transaction/list.vue（含详情 dialog + 回调日志）+ test/index.vue + i18n zh+en `gzPay` 段
- **mp（miniapp）**：api/gz-pay.ts + pages/pay/test.vue + pages/pay/result.vue（三态 + 轮询 + 回流卡片）+ pages/index/index.vue 临时入口（Tier2-entry-temp）
- **配置**：pom.xml（+ruoyi-common-job + wechatpay-java:0.2.17）/ application-dev.yml（gz.pay.client-mode=mock）/ application-prod.yml（env var 占位符 + client-mode=${...:mock}）

## AI 自测（Tier 1A）

### 1. 后端编译 + 单测（mock 全链路，AC 10）

```
[INFO] Running org.dromara.gz.common.pay.service.GzPayTransactionServiceImplTest
[gz-pay] 超时关单完成：扫描 2 / 关单 1 / 跳过 1
[gz-pay] 重复回调（已 paid）out_trade_no=TEST-20260604-000001
[gz-pay] 乐观锁冲突视为重复回调 out_trade_no=TEST-20260604-000001
[gz-pay] 回调处理成功 out_trade_no=TEST-20260604-000001 → paid transaction_id=wx_txn_1
[gz-pay] 测试单创建 out_trade_no=TEST-20260604-000001 amount=1 prepay_id=mock_prepay_TEST-20260604-000001
[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0 -- in GzPayTransactionServiceImplTest

全模块（含 login/user/file 既有测试，无回归）：
[INFO] Tests run: 32, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

5 个 AC 测试方法（+1 happy path 拆分 = 6）全绿：happy path 下单→pending / happy path 回调→paid / 重复回调 duplicated / 验签失败透传异常 / 乐观锁冲突 affected=0 视重复 / 超时关单扫描统计。

### 2. SDK 依赖树（AC 3，无冲突）

```
+- com.github.wechatpay-apiv3:wechatpay-java:jar:0.2.17:compile
|  +- com.github.wechatpay-apiv3:wechatpay-java-core:jar:0.2.17:compile
|  +- com.google.code.gson:gson:jar:2.13.2:runtime
|  +- org.bouncycastle:bcpkix-jdk18on:jar:1.83:compile
|  |  \- org.bouncycastle:bcprov-jdk18on:jar:1.83:compile
|  +- com.squareup.okhttp3:okhttp:jar:4.10.0:runtime
|  \- com.fasterxml.jackson.core:jackson-databind:jar:2.21.2:compile
```
仓库内 grep 全 pom 无任何 wxpay 包 → 无版本冲突。gson/okhttp/bouncycastle 仅 SDK 自用，ruoyi 无引用。

### 3. admin（plus-ui）gz-pay typecheck

```
$ npx vue-tsc --noEmit -p tsconfig.json | grep -E "views/gz-pay|api/gz-pay" | wc -l
0
```
（其余 ruoyi base 既有 TS 噪声 DictTag/Process/layout/store 与本 ticket 无关，未触碰）

### 4. mp（miniapp）build + typecheck

```
$ pnpm type-check | grep -E "pages/pay|api/gz-pay" | wc -l
0
$ pnpm build:mp-weixin   # exit 0
$ ls dist/build/mp-weixin/pages/pay/
result.wxml  result.wxss  result.js  test.wxml  test.wxss  test.js   # 06:57 fresh
$ grep -o "pages/pay/[a-z]*" dist/build/mp-weixin/app.json | sort -u
pages/pay/result
pages/pay/test                # definePage/<route> 宏自动注册
```

### 5. 回调验签压测（AC 11）— 离线说明

后端 dev 未在本机起（与 NEWS-003 并行，避免 install -am 撞 ~/.m2）。验签失败 → 401 + callback_log failed 的链路由 **单测「验签失败：parser throw → 透传异常」** + WechatPayNotifyController 代码路径覆盖（catch WechatPayVerifyException → writeFailedLog + ResponseEntity 401）。真实 curl 错误签名压测（期望 401 + callback_log process_status='failed' raw output）列入 **buffer 期真实通道补打**（需后端起 + 真实/mock notify endpoint）。

## SnailJob 控制台注册（AC 8，手工，无 sys_job DDL）

| 项 | 值 |
|---|---|
| 任务名称 | GZ-PAY-EXPIRE-ORDER |
| 执行器路由 executor_info | `gzPayExpireOrderTask`（= @JobExecutor name） |
| 触发类型 | CRON `0 0/5 * * * ?`（每 5 分钟，Asia/Shanghai） |
| 阻塞策略 | DISCARD（丢弃） |
| 组 | ruoyi_group |

核心逻辑在 `IGzPayTransactionService.expireTimeoutOrders()`（已单测覆盖），job 类仅触发壳。

## 风险提示 / 已知 issue

- **R1 商户号未下证（确定降级）**：走 mock + ADR-0003 记录补打时机，不阻塞 V1.0 收官。
- **WechatPayV3ClientImpl 已写未联调**：buffer 期 staging real profile 跑真实单可能暴露 SDK 5 参一致性细节（buildPayParams vs createJsapiOrder），届时调通，不影响 mock 单测。
- **回调多租户**：notify 无登录态 → TenantHelper.ignore 包裹，V1.0 单租户 '1001' 安全；多租户开放后需带 mch_id → tenant 映射。
- **待 Kevin 批量人验关注（mp 端）**：pay/test 发起测试单 → mock 模拟回调 → result 三态 + 回流卡片 happy path（临时入口从首页可达）。

## 对下游 ticket 的提示

- **ADMIN-003（Wave 2，串行在本 ticket 后，也动 gz-common）**：gz-common pom 已加好 `ruoyi-common-job`（你复用，无需再加）+ `wechatpay-java:0.2.17`。pom 留干净可用。
- **GZ-PAY-101（V1.1 业务支付接入）**：service 层 `createTransaction` 抽象已留（PayOrderNoGenerator 按 business_type 自动出前缀 PREORD/GACHA）；business_type=preorder/gacha 直接复用三表 + 验签 + 幂等 + 超时关单。**清理本 ticket 临时入口**：`pages/index/index.vue` 有 `TODO(Tier2-entry-temp): GZ-PAY-001, remove when GZ-PAY-101 merged` —— 实施时 grep `Tier2-entry-temp` 找到并清理（用业务支付真入口替换）。
- **buffer 期补打（pending，需 Kevin 介入）**：① 商户号下证当日 Kevin 核对主体（STOP 闸口，挂成都谷子宇宙贸易有限公司）；② 注入 env var + staging 切 real；③ 真实 0.01 元端到端单 + curl 验签压测 raw output 追加本 reports。详 ADR-0003 §2。

## §AI 测试段（kevin-qa Tier 1B）

**本 ticket 未在子 agent 内 spawn kevin-qa（嵌套限制，kevin-coder.md 已说明）。** Tier 1B 由主线程收尾 gate 统一调度：
- admin Playwright E2E：登录 owner → 支付管理菜单 → 通道配置（只读列表）/ 支付订单列表 / 测试工具页发起测试单 + 模拟回调 → 订单变 paid。
- 后端集成：notify endpoint 错误签名 → 401 + callback_log failed（需后端起，主线程 install -am 后跑）。
- mp vitest：pay/result 三态 + 轮询逻辑 unit（如需补 .test.ts）。
- mp 可达性：grep `pages/index/index.vue` 含 `Tier2-entry-temp: GZ-PAY-001` 临时入口 → Kevin 批量人验从首页可点到 pay/test ✅。

**close 口径**：Tier 1A 全 ✅（编译 / 6 单测 / 依赖树无冲突 / admin typecheck 0 / mp build+typecheck 0）。mp ticket → 进 progress.md 人验列待 Kevin 批量人验（happy path + 临时入口可达）。真实通道单 = buffer 期 pending（外部资质）。
