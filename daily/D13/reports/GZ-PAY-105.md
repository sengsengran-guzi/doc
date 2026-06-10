# GZ-PAY-105 完工报告 — 反向打款链路 + mock + payout 两表 + 查单 SnailJob

> 后端 + admin，复杂度 L，AI 终态（纯 admin/后端，无 mp 人验）。
> ADR-0006 落地：mock 双实现 / 主动查单优先 / out_payout_no+batch_id 双重幂等 / business_order_no 1:1 / transferbatch SDK 走 mock 留 hook。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git 状态（staging，ahead 4） | ✅ clean working tree（仅本卡新增） |
| 上游依赖 GZ-PAY-001 已就绪 | ✅ IWechatPayClient + Mock/V3 双实现 + WechatPayProperties(client-mode) 在位 |
| wechatpay-java 版本（transferbatch） | ✅ 0.2.17 在位；**未引入新 Maven 坐标**，real 走 hook（见 §SDK 批准状态） |
| menu 5110-5119 空闲 | ✅ grep 5100 段已用 5100-5108，5110+ 全空 |
| dict_id 9250-9255 空闲 | ✅ COUPON 用 9220-9236 / BEAN 9210-9213，9250+ 全空 |
| 编译基线 | ✅ `mvn -o compile -pl ruoyi-gz-common` BUILD SUCCESS（改动前 up-to-date） |

### §0 命令 raw output（dependency:tree 关键段）
```
[INFO] +- com.github.wechatpay-apiv3:wechatpay-java:jar:0.2.17:compile
[INFO] |  +- com.github.wechatpay-apiv3:wechatpay-java-core:jar:0.2.17:compile
```
→ transferbatch service 类（`com.wechat.pay.java.service.transferbatch`）属 0.2.17 同 artifact 子包，**理论上无新坐标**；但按铁律 #8 + ADR-0006 §2，real 不私引、留 hook，**未改 pom，未引入新 Maven 坐标**。

## ADR-0006 关键约束摘录（落地对照）

| ADR-0006 条款 | 本卡落地 |
|---|---|
| §1 IWechatPayClient 扩 2 方法（不新建平行 client） | ✅ `transferToUserWallet(TransferRequest)` + `queryTransferByOutNo(String)` + 3 record 加在现有接口 |
| §1 复用 gz.pay.client.mode 开关（不另起） | ✅ Mock/V3 沿用 `@ConditionalOnProperty(client-mode)`，无新开关 |
| §2 transferbatch SDK 待批准（铁律 8） | ✅ real 抛 UnsupportedOperationException + 注释 `// 待 transferbatch SDK 批准（ADR-0006 / 铁律 8）`，不私引依赖 |
| §3 主动查单优先（SnailJob 扫 processing） | ✅ `GzPayoutQueryJob(name=gzPayoutQueryTask)` 薄壳 + `scanAndQuery()` service；回调表存档备查不作唯一依赖 |
| §3 绝不 Flyway INSERT sys_job | ✅ migration 无 sys_job；任务名/CRON 见 §SnailJob 注册 |
| §4 独立 PayoutStatus（不复用 PayStatus） | ✅ `PayoutStatus` 常量类（created/processing/success/failed/cancelled），独立 dict `gz_payout_status` |
| §4 两表（payout 单 + 回调流水） | ✅ `gz_pay_payout_transaction` + `gz_pay_payout_callback_log` |
| §5 out_payout_no + batch_id 双重幂等 | ✅ DB UNIQUE(tenant_id,out_payout_no) + UNIQUE(tenant_id,batch_id) NULL 共存；raw SQL 已证 1062 |
| §5 business_order_no 与 payout 单 1:1 | ✅ 建单前 `selectByActiveBusinessOrderNo` 查活跃单 → 命中幂等返回，不二次转账 |
| §5 version 乐观锁状态推进 | ✅ markProcessing 含 `version=#{version} AND status='created'` 双 check |
| Consequences 独立核算不计 GMV | ✅ entity/DDL 注释标注；对账单列留 D16 ADMIN-105 |

## 实现摘要

### 后端（独占 gz-common pay 域，未碰 gz-bean/gz-coupon/gz-recycle）

**接口扩展**（在现有 `IWechatPayClient` 扩，不新建 client）：
- `pay/service/internal/IWechatPayClient.java` — 加 `transferToUserWallet` / `queryTransferByOutNo` + record `TransferRequest`(outPayoutNo/receiverOpenid/amountCent/transferRemark/businessOrderNo) / `TransferResult`(payoutId/batchId/state/rawBody) / `TransferQueryResult`(outPayoutNo/payoutId/batchId/transferState/failReason/rawBody)
- `MockWechatPayClient.java` — 扩 mock：`transferToUserWallet` 返稳定占位 payout_id+batch_id（基于 out_payout_no 派生，幂等可复算）→ ACCEPTED；`queryTransferByOutNo` 返可注入 transferState；setter `setQueryTransferState` / `setTransferAcceptFail` 驱动 created→processing→success + failed 分支
- `WechatPayV3ClientImpl.java` — real 两方法均 throw UnsupportedOperationException + hook 注释，不私引 transferbatch

**新 payout 子域**：
- enums `PayoutStatus`（独立常量，附录 A.16）
- entity `GzPayPayoutTransaction`（@Version + @TableLogic + TenantEntity）/ `GzPayPayoutCallbackLog`（纯审计）
- vo `GzPayPayoutTransactionVO`（id/userId @ToStringSerializer，amountCent 保持 Long）/ bo `GzPayPayoutQueryBo`
- mapper `GzPayPayoutTransactionMapper`（selectByOutPayoutNo / selectByActiveBusinessOrderNo / countActiveByBusinessOrderNo / selectMaxDailySeq / selectProcessingIds + 状态机条件 UPDATE：markProcessing/markSuccess/markFailed/markCreatedFailed/retryFailedToCreated）/ `GzPayPayoutCallbackLogMapper`
- service `IGzPayPayoutService` + `GzPayPayoutServiceImpl`（initiatePayout 双重幂等建单+受理 / scanAndQuery 全租户扫查单 / selectPageList / getById）
- internal `PayoutNoGenerator`（PAYOUT-yyyyMMdd-6位序号，**独立 generator 不动共享 PayOrderNoGenerator** — 避免破坏既有 PAY-103 测试构造签名）
- job `GzPayoutQueryJob`（@JobExecutor(name=gzPayoutQueryTask) 薄壳）
- controller `GzPayPayoutController`（/system/gz/pay/payout list+detail，@SaCheckPermission gz:pay:payout:list/query）

**migration（3 文件，段分配钉死）**：
- `V202606210100__GZ-PAY-105-create-payout-tables.sql` — 两表，双 UNIQUE 幂等
- `V202606210110__GZ-PAY-105-menu.sql` — menu 5110/5111/5112（挂 5100 支付管理目录）+ owner(role 100) 授权
- `V202606210120__GZ-PAY-105-seed-payout-status-dict.sql` — dict `gz_payout_status` dict_id 9250 + dict_code 9251-9255（5 态）

### Admin（plus-ui，ruoyi/Element Plus 默认，不引 mockup）
- `src/api/gz-pay/payout.ts` — listPayout/getPayout，id 全 string
- `src/views/gz-pay/payout/index.vue` — BizTable 风列表 + 详情 dialog，状态走 `<dict-tag :options="gz_payout_status">`（前端 dict-tag，避开后端 @DictPattern 系统字典坑，memory ruoyi-menu-dict-gotchas）
- i18n `zh_CN.ts` + `en_US.ts` append `gzPayPayout` block（重读尾部锚定 gzPay 块闭合后，未覆盖他人 block）

## AI 自测

### 1. 编译（后端 gz-common，131 源文件）
```
[INFO] --- compiler:3.14.0:compile (default-compile) @ ruoyi-gz-common ---
[INFO] Compiling 131 source files with javac [debug release 17] to target/classes
[INFO] BUILD SUCCESS
```

### 2. 单测（GzPayPayoutServiceImplTest 8 个 + 全 pay 域 51 个无回归）
```
[INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0 -- in GzPayPayoutServiceImplTest
...
[INFO] Tests run: 51, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
8 个 case：受理成功→processing（验 markProcessing 收非空 payout_id+batch_id）/ 受理失败→failed（验 markCreatedFailed + never markProcessing）/ 1:1 幂等返回已有单（never insert/markProcessing/generate）/ 查单 SUCCESS→success（+存档）/ 查单 FAIL→failed / 查单 PROCESSING 保持 / 已终态跳过（never 存档）/ **全链路 created→processing→success 两步推进**。

### 3. DB 迁移 + 双重幂等验证（raw SQL，对 ry-vue 真库，不污染 flyway_schema_history）
3 个 migration 用 `docker exec mysql < file.sql` 直跑（exit=0），表结构 + dict + menu 验证通过：
```
-- payout 表 UNIQUE 索引（双幂等关键）
uk_tenant_out_payout_no  (tenant_id, out_payout_no)
uk_tenant_batch_id       (tenant_id, batch_id)
-- dict gz_payout_status 5 行：created/processing/success/failed/cancelled（info/primary/success/danger/info）
-- menu 5110(C list)/5111(F list-perm)/5112(F query-perm) 挂 5100 + owner(role 100) 授权 3 行
```

**AC6 双重幂等 raw SQL 实证（同回收单不二次转账的存储层证明）**：
```
=== seed 1 行 processing（out_payout_no=PAYOUT-...099001, batch_id=mock_batch_...099001）→ OK
=== AC6-a 重复 out_payout_no INSERT：
ERROR 1062 (23000): Duplicate entry '1001-PAYOUT-20260621-099001' for key 'uk_tenant_out_payout_no'
=== AC6-b 重复 batch_id INSERT（不同 out_payout_no）：
ERROR 1062 (23000): Duplicate entry '1001-mock_batch_PAYOUT-20260621-099001' for key 'uk_tenant_batch_id'
=== AC6-c 两条 created 单 NULL batch_id 共存：null_batch_created_rows = 2（MySQL UNIQUE 多 NULL 允许）
=== cleanup：remaining = 0（测试行已清，未污染）
flyway_schema_history WHERE version LIKE '2026062101%' → 0（raw SQL 未写 flyway 历史，app 启动时 Flyway 正式应用）
```
→ DB 层证明：同一回收单（同 out_payout_no 或同 batch_id）**第二次落单即被 UNIQUE 拒绝**，配合 service 建单前 1:1 查活跃单（单测已验 never insert/transfer），**双保险防店员重复点打款导致二次转账**。

Redis 已 FLUSHDB 刷新字典缓存（dev）。

### 4. Admin 前端类型检查（vue-tsc --noEmit）
```
payout 文件 TS 错误数：0（NONE_IN_PAYOUT_FILES）
项目基线 72 个 pre-existing 错误均不在 gz-pay/payout 文件
```
→ 新增 api/gz-pay/payout.ts + views/gz-pay/payout/index.vue + i18n 两文件 append 零新增类型错误。

## §SnailJob 控制台注册（AC5，绝不 Flyway INSERT sys_job）

| 项 | 值 |
|---|---|
| 任务名称 | GZ-PAY-PAYOUT-QUERY |
| 执行器路由（executor_info） | `gzPayoutQueryTask`（= GzPayoutQueryJob @JobExecutor name） |
| 触发类型 | CRON `0 0/2 * * * ?`（每 2 分钟；商家转账到账有延迟，频率低于支付查单即可，时区 Asia/Shanghai） |
| 阻塞策略 | 丢弃（DISCARD）— 上次未跑完不叠加 |
| 组 | ruoyi_group |
| 行为 | 扫 processing 态 payout 单 → queryTransferByOutNo → SUCCESS→success(+transferred_time) / FAIL→failed(+fail_reason) / PROCESSING 保持等下轮；查单 body 入 gz_pay_payout_callback_log 存档 |

> mock 模式下查单态由 MockWechatPayClient 默认 PROCESSING；真机/单测通过 setQueryTransferState 注入 SUCCESS/FAIL。real 通道到位后切 gz.pay.client.mode=real（job 逻辑零改动）。

## §SDK 批准状态（AC9，铁律 #8）

- **未引入新 Maven 坐标**：未改任何 pom；`wechatpay-java:0.2.17` 既有依赖未升版本。
- **transferbatch 走 mock**：`com.wechat.pay.java.service.transferbatch` 虽属 0.2.17 同 artifact 子包（理论无新坐标），但按 ADR-0006 §2 + 铁律 #8，**未私引、未 import**；`WechatPayV3ClientImpl` 两反向打款方法留 hook（throw UnsupportedOperationException + `// 待 transferbatch SDK 批准（ADR-0006 / 铁律 8）`）。
- **真实上线 gate**（pending，需 Kevin × 甲方）：① 商户「商家转账到零钱」权限单独申请（非默认开通，有资质门槛）；② 确认 transferbatch 子包在 0.2.17 可用 / 是否升版本 → Kevin 批准后接 V3 `/v3/transfer/batches`。权限+依赖到位前 mock 全链路可跑通单测 + admin 演示，**不阻塞 D14 RECYCLE-003**。

## 风险提示 / 已知 issue

- **风险 1（外部资质）**：real 商家转账需甲方商户权限 + Kevin 批 transferbatch 依赖，均 pending。当前 dev/单测/演示全 mock，代码切 real 零改动（同 ADR-0003 范式）。
- **风险 2（business_order_no 无 DB 级 UNIQUE）**：doc/11 §4.8 仅给 out_payout_no/batch_id UNIQUE，business_order_no 为 IDX。1:1 由 service 建单前查活跃单兜底（单测已验）+ out_payout_no UNIQUE 兜底并发 DuplicateKey 重查返回。若未来需更强并发保证，可加 `UNIQUE(tenant_id, business_order_no) WHERE status NOT IN (failed,cancelled)`（MySQL 不支持部分唯一，需触发器/应用层，当前应用层足够）。
- **风险 3（retry 路径未走 service）**：`retryFailedToCreated`（failed→created 重试）mapper 方法已建，但本卡无 service 调用方（重试触发属 D14 RECYCLE-003 店员重新点打款时）。已留 mapper + DDL 支持，下游接入即用。
- 待 Kevin 批量人验关注（仅 mp 端）：**N/A — 本卡纯 admin/后端，无 mp、无微信原生能力，AI 全 ✅ 即终态 close**。

## 对下游 ticket 的提示

- **D14 GZ-RECYCLE-003**（店员核对触发打款）：confirmed_onsite→paying 时调 `IGzPayPayoutService.initiatePayout(InitiateBo)`，传 `businessType="recycle"` / `businessOrderNo=appointment_no` / `userId` / `receiverOpenid`(预约单快照) / `amountCent=final_amount_cent` / `transferRemark`。返回 VO 含 out_payout_no + status，回写 `gz_recycle_appointment.out_payout_no`。**幂等已内建**（重复点打款返回已有单不二次转账），RECYCLE-003 无需自己防重。失败重试调 `retryFailedToCreated` 后重新 initiate。
- **D16 ADMIN-105 对账中心**：payout 流水**单列**（不计 GMV、不参与 4% 分成，ADR-0006 Consequences），与拼豆/扭蛋正向流水隔离，查 `gz_pay_payout_transaction.status='success'` 出账口径。
- **SnailJob 部署**：staging/prod 需在 SnailJob 控制台手工注册 GZ-PAY-PAYOUT-QUERY 任务（参数见 §SnailJob 注册），dev 可手动触发 service.scanAndQuery() 验证。
- **无临时入口**（Tier 2 N/A）：纯 admin/后端，无 mp 新页。

## §AI 测试段（kevin-qa Tier 1B 完工后追加）

**Tier 1B（主线程整批集成验证 2026-06-10）** — subagent 崩溃率高 + kevin-qa 不能由子 agent spawn（[[tier1b-qa-dispatch-by-mainthread]]）+ Playwright MCP 不可用 → 主线程一次启动 app 整批验 5 卡：
- App `Started DromaraApplication in 10.958s` — **PAY-105 payout 子域 + IWechatPayClient 扩展装配无 BeanCreation 错**
- Flyway 应用 `202606210100/0110/0120 GZ-PAY-105`（payout 2 表 + 5110 menu 段 + dict gz_payout_status）；`gz_pay_payout_transaction` / `gz_pay_payout_callback_log` 建好（0 数据，待 D14 RECYCLE-003 触发）
- curl `/system/gz/pay/payout/list` → HTTP 200（Controller 装配 + 映射注册）
- ✅ 纯后端 AI Tier 1A+1B 全 ✅ 即终态，8080 已释放
