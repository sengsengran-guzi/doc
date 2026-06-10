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
# GZ-COUPON-002 完工报告 — 拼豆抵扣（券锁定/核销/回滚）+ 过期 SnailJob

纯后端 · AI 终态（无人验）· 第一波并行批次（与 PAY-105 / RECYCLE-001 同时跑，独占 gz-coupon + gz-bean(3 hook)）

---

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean（仅本卡 + 并行批次改动，无意外） | ✅ 我只碰 gz-coupon + gz-bean，gz-common 改动属 PAY-105/RECYCLE-001 并行 |
| 上游 `gz_user_coupon` 表已建（D12 V202606200100） | ✅ 9 行 seed unused 券（user 1/2/3/4/5/7/8，面额 500 分） |
| 上游 `gz_coupon_template` 已建 | ✅ 2 行 |
| 上游 `gz_bean_booking.coupon_id` / `discount_amount_cent` 列已建（D12 V202606200000） | ✅ information_schema 各 1 列 |
| 3 个 hook 位定位 | ✅ submitPaid:799(锁券) / closePindou:1015(回滚) / onPindouPaid:985 markPaid 后(核销) |
| 编译基线（gz-coupon + gz-bean，不加 -am） | ✅ EXIT=0 |
| dev infra（MySQL:3307 / Redis:6380） | ✅ Up 5 days（curl/mysql 走 docker exec 绕代理） |
| gz-coupon pom 缺 ruoyi-common-job（D12 未加） | ✅ 已确认缺失 → 本卡首引补上 |
| 关联 ADR 已读 | ADR-0007 §1.4(免费单兜底)/§1.5(超时关单+回滚 locked→unused)/§3(迁移) |

---

## 权威摘录（逐段 Read，钉死口径）

**doc/11 §11.2 券态机（钉死）** —— 4 态 4 边：
| 流转 | 触发 | 说明 |
|---|---|---|
| `unused → locked` | 拼豆下单选用 | 下单事务内锁券，防一券多用；写 booking.coupon_id |
| `locked → used` | 拼豆支付成功 onPaid | 核销，写 used_time + related_pay_out_trade_no |
| `locked → unused` | 订单取消 / 支付关闭 pay_closed | 回滚解锁，券可再用 |
| `unused → expired` | SnailJob 扫超期 | 终态；**`locked` 态不被过期扫描误伤**（已锁定即在用） |

**doc/11 §11.3 抵扣 + GMV 口径（钉死）**：
- 实付 `= gz_bean_booking.amount_cent − amount_snapshot_cent`，**下限 0**（券超额差额不退不找零）。
- 实付 > 0 才建 `gz_pay_transaction(business_type=pindou)`；实付 = 0 走免费单兜底。
- `gz_pay_transaction.amount_cent` = 实付，**券面额不计 GMV**（让利非收入）。

**doc/11 §3.8 + ADR-0007 §1.4/§1.5**：
- 免费单兜底：`price_cent=0` 且无券需求（或券全额抵扣实付=0）→ 不建支付单，`pay_status` 直接 `paid`，`out_trade_no` 留 NULL，`status=pending`，直接生成 verify_code。
- 支付关闭：`pay_status → pay_closed`，`status → cancelled`，释放配额 + 回滚锁定券（`locked → unused`）。

**doc/10 §12 券锁定核销流**：N4 下单锁券 / N5 onPaid 核销 / N6 取消解锁 / N7 支付失败回滚 / N8 SnailJob 过期扫描。

---

## 实现摘要

### 改动文件（git diff --stat，仅本卡领地 gz-coupon + gz-bean）
```
 ruoyi-gz-bean/pom.xml                                    |   8 ++  (加 gz-coupon 依赖)
 GzBeanBookingServiceImpl.java                            |  61 ++   (3 hook)
 GzBeanBookingServiceImplTest.java                        | 135 ++   (构造器 + 5 券抵扣测试)
 ruoyi-gz-coupon/pom.xml                                  |   6 +   (加 ruoyi-common-job)
 GzUserCoupon.java                                        |   2 +-  (del_flag 注释修正 2→1)
 GzUserCouponMapper.java                                  |  95 ++   (4 条件 UPDATE + 1 扫描)
 IGzUserCouponService.java                                |  75 ++   (4 方法 + 2 record)
 GzUserCouponServiceImpl.java                             |  84 ++   (4 方法实现)
 8 files changed, 449 insertions(+), 17 deletions(-)
```
新增（untracked）：
- `ruoyi-gz-coupon/.../job/GzCouponExpireJob.java`（SnailJob 薄壳，仿 GzBeanUnpaidExpireJob）
- `ruoyi-gz-coupon/.../service/impl/GzUserCouponServiceImplTest.java`（13 券态机单测）

### 关键设计决策

1. **券态防并发 = 状态值 CAS（非 version）**：`gz_user_coupon` 无 version 列，券态机天然单向。每条流转 SQL 的 `WHERE` 含「当前态」守卫（锁券 `status='unused'` / 核销 `status='locked'` / 回滚 `status='locked'`），把「读态+校验+改态」并到一条 DB 行锁内。并发两线程锁同一 unused 券只有一个 affected=1 → 杜绝一券多用。范式仿 `GzCouponTemplateMapper.increaseIssuedCount`（CAS 因子换 version→status）。

2. **submitPaid 时序重排（关键）**：原 799 hook 在 INSERT 之后，但 `discount/free/payStatus/verifyCode` 全依赖券面额 → **锁券+实付重算必须提到 INSERT 之前**。新顺序：⑥防超卖 → ⑦计费 → ⑦.5锁券(unused→locked)拿面额→实付重算 → ⑧booking_no → ⑨INSERT(discount/payStatus 已定) → ⑨.5免费单核销。锁券在 INSERT 前，下单失败/拒单回滚时锁券 UPDATE 随同一 `@Transactional` 回滚自动解锁。

3. **免费单券核销时机（doc 未明说但逻辑必然）**：付费单券在 onPaid 核销；但**券全额抵扣致 free=true 的单无支付回调**（pay_status 直接 paid，永不进 closePindou/onPaid）→ 券会永远卡 locked。故在 submitPaid 当场核销（locked→used，related = booking_no 占位，无真实支付单）。

4. **跨模块依赖**：gz-bean 新增依赖 gz-coupon（coupon 不反依赖 bean → 无模块环）。券服务用 `ObjectProvider<IGzUserCouponService>` 惰性注入（仿 payServiceProvider，对齐 BEAN-014 断构造期环纪律）。编译/单测用 `-pl gz-coupon,gz-bean`（reactor 内互引，不需 .m2 jar，不加 -am）。

5. **过期扫描薄壳**：`GzCouponExpireJob`(@JobExecutor name=`gzCouponExpireTask`) 仅触发，核心 `expireBatch()` 在 service（可单测）。`TenantHelper.ignore` 全租户扫（cron 无登录态，仿 markExpiredUnpaidBatch）。

---

## AI 自测

### ① 编译（gz-coupon + gz-bean，不加 -am）
```
$ mvn -o compile -pl ruoyi-modules/ruoyi-gz-coupon,ruoyi-modules/ruoyi-gz-bean -q
EXIT=0
（无 ERROR / 无 BUILD FAILURE）
```

### ② 单测（含新加 13 + 5 = 18 个券相关测试）
```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-coupon,ruoyi-modules/ruoyi-gz-bean -Dgroups=dev
[INFO] Tests run: 13, Failures: 0, Errors: 0, Skipped: 0 -- GzUserCouponServiceImplTest   ← 新增（券态机）
[INFO] Tests run: 31, Failures: 0, Errors: 0, Skipped: 0  (gz-coupon 全模块)
[INFO] Tests run: 40, Failures: 0, Errors: 0, Skipped: 0 -- GzBeanBookingServiceImplTest  ← 含新增 5 券抵扣测试
[INFO] Tests run: 96, Failures: 0, Errors: 0, Skipped: 0  (gz-bean 全模块)
[INFO] BUILD SUCCESS
```
新增券测试覆盖（AC6 各流转边）：
- lockForBooking：happy(返面额) / 券不存在 / 越权(非本人) / CAS 失败(已用) / null
- redeem：happy(写 used_time+related) / null 跳过 / affected=0 幂等
- unlock：happy(回滚) / null 跳过 / affected=0(已 used 不复活)
- expireBatch：有到期(unused→expired) / 无到期
- gz-bean 端：**实付=单价−券面额(3000−1000=2000)** / 券超额下限0+免费单核销 / 锁券失败回滚不INSERT / onPaid 用券核销 / closePindou 用券回滚

### ③ 券态机条件 UPDATE 端到端（raw SQL，不污染 flyway_schema_history）
```
====== ① 锁券 unused→locked ======                affected=1 ✅  status=locked
====== ② 并发再锁同券（CAS 防一券多用）======      affected=0 ✅  (已 locked 拦死)
====== ③ 核销 locked→used + used_time + related ==  affected=1 ✅  has_used_time=1 related=PINDOU-20260610-000001
====== ④ 已 used 券回滚守卫（status=locked）======   affected=0 ✅  仍 used（不复活）
====== ⑤ 回滚 locked→unused（券4）======            lock=1 unlock=1 ✅  back_to_unused
====== 复原 id 3/4 → unused ======                  ✅ 无脏数据
```

### ④ AC5 过期扫描 — locked 不被误伤（raw SQL）
```
构造：id5=过期unused / id6=过期locked
selectExpiredUnusedIds 命中 → 只 id5（不含 locked id6） ✅
expireBatch UPDATE → affected=1（仅 id5→expired） ✅
结果：id5=expired（被扫）/ id6=locked（未误伤，已锁定即在用） ✅
复原 id 5/6 → unused ✅
```

### ⑤ 收尾验证
```
flyway_schema_history 最大版本 = 202606200101（D12 的，本卡无新迁移，未污染）✅
gz_user_coupon: unused 9（全复原，无脏数据）✅
redis FLUSHDB → OK ✅
```

---

## 风险提示 / 已知 issue

1. **本卡无 DDL 变更**：券态 = `gz_user_coupon.status` 的 UPDATE，字段 D12 已建全（含 idx_status_expire 过期扫描索引）。无新 Flyway 文件，不抢 PAY-105(21010x)/RECYCLE(21020x) 时间戳。
2. **免费单券核销的 related 占位**：券全额抵扣的免费单，`related_pay_out_trade_no` 写的是 `booking_no`（非真实支付单 out_trade_no，因无支付单）。追溯时 admin 看到 `BK...` 前缀即知是免费抵扣单。对账（D15）不涉及（券面额不计 GMV + 免费单无 pindou 支付流水）。
3. **gz-bean 首次依赖 gz-coupon**：模块依赖图新增一条边（bean→coupon），无环（coupon 不反依赖 bean，已 grep 确认）。Tier 1B 起真 app 时若 Spring 报循环依赖（极不可能），ObjectProvider 已预防。
4. **券核销/回滚 affected=0 不抛异常**：onPaid/closePindou 里券态推进失败仅记 WARN 日志，不阻塞主单（支付核销 / 配额释放优先）。设计如此（券态是附属，主单状态是主线）。
5. **entity 注释顺手修**：`GzUserCoupon` del_flag 注释从「2=删除」改为「1=删除」（对齐 common-mybatis.yml logicDeleteValue=1，learnings 钉死坑），纯注释不影响 checksum/逻辑。D12 已应用的 DDL 文件未动（注释错误留存于 SQL，不可改）。

---

## SnailJob 任务（运维注册，控制台配置 — 非 Flyway INSERT）

| 项 | 值 |
|---|---|
| 任务名称 | GZ-COUPON-EXPIRE |
| 执行器路由（@JobExecutor name） | `gzCouponExpireTask` |
| 触发类型 / CRON | CRON，`0 0 3 * * ?`（每日凌晨 3 点；券过期非强实时，日级即可） |
| 任务参数 | 无（过期判定以 NOW() 为基准，service 内自取） |
| 阻塞策略 / 组 | 丢弃（默认）/ `ruoyi_group` |
| 配置键（doc/11 §11.2） | `gz.coupon.expire.cron`（控制台 CRON 真源） |
| 行为 | 扫 `status='unused' AND expire_time < NOW()` → 批量 `expired`；**locked 态不触碰**；TenantHelper.ignore 全租户 |

---

## 对下游 ticket 的提示

- **GZ-COUPON-003（mp 选券 / 我的券列表）**：选券接口 `GET /api/coupon/usable?business=pindou&total_amount` 返回该用户 unused 且未过期且面额可用券（doc/10 §12.N3）。下单传 `couponId` 到 `submitPaid`，券态机本卡已就绪。mp 下单成功 VO 已含 `discountAmountCent` / `payAmountCent`（实付）/ `free` 字段可直接展示「已抵扣 X 元 / 实付 Y 元」。
- **GZ-PAY-105（反向打款，并行批次）**：与本卡零交叉（你改 gz-common payout，我改 gz-coupon + gz-bean hook）。
- **D15 对账**：拼豆 pindou 正向流水实付口径 = `amount_cent − discount_amount_cent`（已写进 gz_pay_transaction.amount_cent）；**券面额不回补 GMV**（doc/11 §11.3 §4.6 钉死）。
- **Tier 1B（主线程统一派）**：起真 app 后建议补 ① 真实下单选券 → onPaid 回调 → 券 used 全链路；② SnailJob 控制台注册 gzCouponExpireTask 后真跑一次过期扫描确认 locked 不被扫。本卡单测 + raw SQL 已覆盖逻辑，真 app 验 Spring 装配（bean→coupon 依赖 + ObjectProvider 装配 + @JobExecutor 注册）无环启动。

---

## §AI 测试段（kevin-qa Tier 1B 完工后追加 — 留空）

主线程一次启动 app 整批验 5 卡（subagent 崩溃率高 + kevin-qa 不能子 agent spawn + Playwright 不可用）：
- App `Started DromaraApplication in 10.958s` — **gz-bean→gz-coupon 装配无环**（ObjectProvider 打断构造期循环依赖生效，否则 BeanCurrentlyInCreationException）
- 券态 service（锁定/核销/回滚）+ 过期 SnailJob 薄壳随 app 加载无错；gz-coupon pom ruoyi-common-job 依赖解析正常
- Flyway 6 迁移应用至 v202606210201（券态 = status UPDATE 无新 DDL）
- ✅ 纯后端 AI Tier 1A+1B 全 ✅ 即终态，8080 已释放
# GZ-RECYCLE-001 完工报告 — 回收价目表 + 区间不重叠校验 + 估价命中 + 字典

> 后端（新建 `ruoyi-gz-recycle` 域）+ admin（plus-ui）。复杂度 M。AI 终态（纯 admin/后端，无 mp 人验）。
> **实施方式**：后端 java（12 文件）由 background subagent 建成（编译通过后崩在写 migration 前）；**migration + admin + 注释修正 + 收尾由主线程接管**（见文末异常留痕）。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（本路径非独立 git 仓库根） |
| 上游依赖 | ✅ GZ-ADMIN-001/SYS-005 字典基础设施就绪；gz-common 稳定 jar 在 .m2 |
| 关键表/段空闲 | ✅ `gz_recycle_price_rule` 不存在（从零建）；`ruoyi-gz-recycle` 模块新建；menu 13000 段空；dict_id/code 9240-9245 空（避开 COUPON 9220-9236 + PAY-105 9250-9255） |
| 迁移时间戳 | ✅ 用 V202606210200 / V202606210201（> 已有 max 202606200200，与 PAY-105 21010x 不冲突） |
| 编译通过 | ✅ `mvn -o test-compile -pl ruoyi-modules/ruoyi-gz-recycle` BUILD SUCCESS（main + test 全部 java 完整） |
| ADR 已读 | 无相关 ADR（价目表 + 区间校验权威 = doc/11 §12.1） |
| 权威蓝图引用 | ✅ doc/11 §12.1（字段 + 区间不重叠校验末段）+ 附录 A.21（品类字典）+ doc/10 §13（估价口径） |

### 权威蓝图关键约束摘录（doc/11 §12.1）
- 字段：`category`(VARCHAR32) / `qty_min`(INT) / `qty_max`(INT NULL=无上界) / `unit_price_cent`(BIGINT) / `duration_minutes`(INT NOT NULL DEFAULT 0) / `enabled`(TINYINT DEFAULT 1) / `sort_no`(INT)。
- 索引：PK id / **UNIQUE(tenant_id, category, qty_min)** / IDX(tenant_id, category, enabled)。
- **区间不重叠 = 业务层校验**（末段钉死）：admin 保存 assert 同 category 各 [qty_min,qty_max] 不重叠；DB 不加复杂 CHECK。
- 估价命中：`qty_min <= total_qty AND (qty_max IS NULL OR total_qty <= qty_max)` 唯一；命中 0 → 无报价；命中多 → 配置有误。

## 实现摘要

### 后端 `ruoyi-modules/ruoyi-gz-recycle`（新建模块，包名 `org.dromara.gz.recycle.*`，仿 gz-coupon）
- 父 pom 注册：`ruoyi-modules/pom.xml` + `ruoyi-admin/pom.xml` 各加 ruoyi-gz-recycle。依赖仅 ruoyi-gz-common + test。
- 12 java：`GzRecyclePriceRule`(entity, TenantEntity + @TableLogic) / `GzRecyclePriceRuleBo` + `GzRecyclePriceRuleQueryBo` / `GzRecyclePriceRuleVO` + `GzRecycleEstimateVO` / `GzRecyclePriceRuleMapper`(BaseMapperPlus, LambdaQueryWrapper service 层组装无 XML) / `IGzRecyclePriceRuleService` + impl / `GzRecyclePriceRuleController`(7 端点 list/getInfo/add/edit/remove/toggle/estimate)。
- **区间不重叠校验**（service `assertNoOverlap`）：查同 category 全部规则（编辑排除自身）逐个判重叠；重叠判定 `aMin <= b2 AND bMin <= a2`（qtyMax null 视 +∞），相邻不重叠。
- **估价命中**（service `estimate`）：内存过滤命中唯一区间；命中 0 抛「无报价规则」/ 命中多抛「配置有误」；`estimated = unit_price_cent × qty`。
- 2 单测：`GzRecyclePriceRuleOverlapTest`(8) + `GzRecyclePriceRuleEstimateTest`(7)。
- **注释修正（主线程）**：entity `delFlag` + controller remove 注释 `2→1`（本项目 logicDeleteValue=1，对齐 BEAN-014/COUPON-002 实证，memory ruoyi-menu-dict-gotchas；@TableLogic 无 value 走全局功能本就正确，仅注释笔误）。

### 迁移（2 文件，主线程写）
- `V202606210200__GZ-RECYCLE-001-create-price-rule.sql`：建 `gz_recycle_price_rule`（字段/索引对齐 doc/11 §12.1；UNIQUE(tenant_id,category,qty_min)；del_flag 注释 `1=删除` 用项目真实值不抄 COUPON-001 历史笔误）。
- `V202606210201__GZ-RECYCLE-001-seed-dict-menu.sql`：字典 `gz_recycle_category`（5 demo 品类，dict_id 9240 / dict_code 9241-9245）+ menu 13000 段（13000 目录 / 13001 价目表 C / 13010-13014 按钮 F，perm 对齐 controller @SaCheckPermission）+ owner(100) 7 授权 + 4 条 demo 价目规则（card 3 区间 + goods 1，区间不重叠）。

### admin（plus-ui，ruoyi/Element Plus 默认，主线程写）
- `api/gz-recycle/priceRule.ts`（id 全 string，7 函数 + 4 interface）。
- `views/gz-recycle/price-rule/index.vue`（BizTable 风格 el-table + 查询 + 新增/编辑弹窗（元↔分换算、qtyMax 留空=无上界）+ 启停 + **估价试算弹窗**（category+qty → 实时命中显示单价/估价/时长））。
- `lang/{zh_CN,en_US}.ts` append `gzRecyclePriceRule` block（全覆盖，默认 zh-CN 不混 emoji）。

## AI 自测（Tier 1A）

### ① 单测（15 全过：区间重叠 8 + 估价 7）
```
[INFO] Running org.dromara.gz.recycle.service.impl.GzRecyclePriceRuleOverlapTest
[INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0 -- in GzRecyclePriceRuleOverlapTest
[INFO] Running org.dromara.gz.recycle.service.impl.GzRecyclePriceRuleEstimateTest
[INFO] Tests run: 7, Failures: 0, Errors: 0, Skipped: 0 -- in GzRecyclePriceRuleEstimateTest
[INFO] Tests run: 15, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
覆盖：区间重叠拒绝 / 相邻不重叠通过 / qtyMax NULL 无上界重叠 / 编辑排除自身 / 估价命中唯一 / 命中 0 抛无报价 / 命中多抛配置错 / 上界小于下界拒绝。

### ② migration raw SQL 验证（dev DB ry-vue:3307，不污染 flyway_schema_history）
```
-- demo 价目规则（4 条，区间不重叠）
category  qty_min  qty_max  unit_price_cent  duration_minutes  enabled
card      1        10       500              15                1
card      11       50       800              30                1
card      51       NULL     1200             60                1
goods     1        20       300              20                1

-- 估价命中唯一区间
card qty=5  → [1,10]   unit=500   est_cent=2500  (¥25)
card qty=55 → [51,∞]   unit=1200  est_cent=66000 (¥660)

-- 字典 + menu + owner 授权
dict_data=5  menu=7  owner_grant=7
```

### ③ UNIQUE(tenant_id, category, qty_min) 防重 + admin vue-tsc
```
-- UNIQUE 拦截重复
INSERT ('card', qty_min=1, ...) → ERROR 1062 (23000) Duplicate entry '1001-card-1'
  for key 'gz_recycle_price_rule.uk_tenant_category_qtymin'   ✅

-- plus-ui vue-tsc（gz-recycle 文件 0 TS 错；项目基线 72 pre-existing 不在我的文件）
npx vue-tsc --noEmit | grep -icE 'gz-recycle|priceRule|price-rule' = 0   ✅
```

### ④ 收尾
- dev DB 已应用 RECYCLE migration（raw SQL，未写 flyway_schema_history）→ Tier 1B 启动 app 时 Flyway 幂等应用（CREATE IF NOT EXISTS + DELETE/INSERT seed 幂等）。
- Redis 已 FLUSHDB（dict 缓存 TTL 1h，CLAUDE.md §5）。
- **未 mvn install**（留主线程统一按依赖序）；**未启 spring-boot:run / 8080 free**。

## 风险提示 / 已知 issue
- **R-1 demo 品类/价目为占位**：`gz_recycle_category` 5 品类（卡牌/玩偶/谷子/手办/其他）+ 4 demo 价目规则是 demo，甲方在 admin 字典页 + 价目表页维护实际值。
- **R-2 估价命中多兜底**：service `estimate` 命中多条时抛「配置有误」——正常配置（区间不重叠校验生效）不会命中多；此为防御性兜底（万一历史脏数据）。
- **R-3 duration_minutes DB NOT NULL DEFAULT 0**：entity Integer 可空，admin 表单必填（rules）；DB DEFAULT 0 兜底。
- 待 Kevin 批量人验关注：**N/A — 纯 admin/后端 ticket，无 mp 页、无微信原生能力 → AI Tier 1A+1B 全 ✅ 即终态，无人验**（CLAUDE.md §8.2）。

## 对下游 ticket 的提示
- **D14 GZ-RECYCLE-002（mp 填单 + 估价）**：调 `GET /system/gz/recycle/price-rule/estimate?category&qty`（或新建 applet 镜像端点）拿估价；多品类预约按 doc/11 F12.1「各品类自身命中累加」（`estimated = Σ 各品类 unit_price × 数量`）。`gz_recycle_appointment` 表（doc/11 §12.2）本卡未建 = D14 建。
- **D14 GZ-RECYCLE-003（店员核对 + 触发反向打款）**：核对后 `final_amount_cent` 触发 PAY-105 `transferToUserWallet`（business_type=recycle，business_order_no=appointment_no）；PAY-105 链路 + mock 已就绪。
- 估价命中逻辑（`estimate` service）可被 D14 mp 填单直接复用（已抽 service 方法）。

## §AI 测试段（kevin-qa Tier 1B 完工后追加）

**Tier 1B（主线程整批集成验证 2026-06-10）** — subagent 崩溃率高 + kevin-qa 不能子 agent spawn + Playwright 不可用 → 主线程一次启动 app 整批验：
- App `Started DromaraApplication in 10.958s` — **gz-recycle 新模块加载无错**（父 pom + ruoyi-admin 依赖注册生效）
- Flyway 应用 `202606210200/0201 GZ-RECYCLE-001`：`gz_recycle_price_rule` 4 demo seed + dict gz_recycle_category(5) + menu 13000 段（owner 授权 7）
- curl `/system/gz/recycle/price-rule/list` + `/estimate?category=card&qty=5` → HTTP 200（Controller 装配 + 映射注册）
- DB 实测：recycle_rule = 4 / flyway_d13 = 5
- ✅ 纯后端/admin AI Tier 1A+1B 全 ✅ 即终态，8080 已释放

---

## §异常留痕（实施过程）

- 本卡 background subagent **两次崩于 `tool call could not be parsed`**（首发 35 tool_uses / 重做 46 tool_uses，均在后端 java 建完、写 migration/admin 前崩）。
- 第二次崩前已建成后端 12 java + pom + 父 pom 注册（主线程编译验证 EXIT=0 + 15 单测过，质量合格）。
- **主线程接管补全**：migration（2）+ admin（api/vue/i18n）+ entity/controller 注释修正 + 全套自测 + 本 report。
- 根因判定：kevin-coder subagent 在本环境工具调用解析不稳定（同批 PAY-105 首发 + COUPON-003 亦崩）；可靠路径 = 主线程实施或前台 subagent（PAY-105 前台重做成功）。
# GZ-COUPON-003 完工报告 — mp 选券 + 我的券列表

> mp + be，复杂度 S，**mp 人验**（进 progress.md 人验列）。C 日漫海报浓墨。
> **实施方式**：后端 applet + mp 我的券页 + logic + 文案（9 文件）由 background subagent 建成（崩在写 BizCouponPicker 前）；**BizCouponPicker.vue + me 九宫格券入口 + 收尾由主线程接管**（见文末异常留痕）。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| 上游依赖 | ✅ GZ-COUPON-002（D13）券态 service 就绪（IGzUserCouponService.listUsableForPindou/listMyCoupons）；gz_user_coupon 全字段 |
| 关键类存在 | ✅ GzUserCouponMpController（applet）+ GzUserCouponMpVO + coupons.logic + coupon.zh-CN locale 已建 |
| 编译通过 | ✅ `mvn -o test-compile -pl ruoyi-modules/ruoyi-gz-coupon` BUILD SUCCESS（applet controller + COUPON-002 service 无回归） |
| ADR 已读 | 无相关 ADR（券态权威 doc/11 §11.2 / 选券口径 doc/10 §12.N3） |
| 权威蓝图引用 | ✅ doc/10 §12.N3（usable 接口）+ doc/11 §11.2（券态）/ §11.3（抵扣口径，实付下限 0） |

## 实现摘要

### 后端 applet（ruoyi-gz-coupon，subagent 建）
- `controller/applet/GzUserCouponMpController`（`/app/gz/coupon`）：
  - `GET /usable?business=pindou&totalAmount=` — 拼豆选券（unused + applicable + 未过期，被 BizCouponPicker 消费）。totalAmount 仅透传供前端算实付，后端不据此过滤（券超额仍可用，实付下限 0）。
  - `GET /my?status=` — 我的券分态列表（unused/used/expired；locked 瞬态后端永不返）。
  - LoginHelper.getUserId 数据归属隔离；id 全 string。
- service 扩 `listUsableForPindou` / `listMyCoupons` + `GzUserCouponMpVO`（COUPON-002 同模块，编译验证无回归）。

### mp（miniapp，C 设计系统）
- `pages/me/coupons.vue`（subagent，326 行）：我的券三 tab（未使用/已使用/已过期）+ 下拉刷新；BizScreen + view/text + var(--c-*)，不撒 wd-*。
- `pages/me/coupons.logic.ts` + `.test.ts`（subagent）：纯逻辑（couponStatusTone/filterByTab/filterUsable/calcPayAmountCent/formatAmountCent/formatExpireDate），9 vitest。
- `api/gz-coupon.ts`（subagent）：listUsableCoupons/listMyCoupons + UserCouponVO（id string，金额 _cent）。
- `locale/coupon.zh-CN.ts`（subagent）：自包含 t()，coupon.list.* + coupon.picker.* 文案（不混 emoji）。
- **`components/biz/BizCouponPicker.vue`（主线程）**：底部弹层选券（入口行 + sheet），复用 coupons.logic 的 filterUsable/formatAmountCent/formatExpireDate；C token 样式（--c-ink/red/bw/shadow-sm/shadow-sel/tint-red）；easycom `^Biz` 自动注册。
- **`pages/me/index.vue`（主线程）**：九宫格加「我的优惠券」cell（key=coupons，ROUTE_MAP → /pages/me/coupons）。
- **`locale/user.zh-CN.ts`（主线程）**：加 `entryCoupons: '我的优惠券'`。

## AI 自测（Tier 1A）

### ① 后端编译（applet controller + COUPON-002 service 无回归）
```
[INFO] BUILD SUCCESS  -- mvn -o test-compile -pl ruoyi-modules/ruoyi-gz-coupon
```

### ② mp vitest（coupons.logic 9 tests：分态 + 可用券筛选 + 实付下限 0）
```
 ✓ src/pages/me/coupons.logic.test.ts (9 tests) 3ms
 Test Files  1 passed (1)
      Tests  9 passed (9)
```
覆盖：filterByTab 分态（locked 永过滤）/ filterUsable（unused+pindou+未过期，过期券拦截）/ calcPayAmountCent（实付下限 0，券超额）/ formatAmountCent / formatExpireDate。

### ③ mp type-check（BizCouponPicker + me/index + coupons 全部 0 TS 错）
```
pnpm type-check (vue-tsc --noEmit) | grep 'BizCouponPicker|me/coupons|me/index' = 0 错误
easycom: "^Biz(.*)": "@/components/biz/Biz$1.vue"  → BizCouponPicker 自动注册 ✅
pages.json: GENERATED BY UNI-PAGES → coupons.vue definePage 构建时自动注册 ✅
```

## Tier 2 可达性（mp 硬约束，CLAUDE.md §8.3）
- **「我的券列表」**：会员中心「我的」tab（已上线）→ 九宫格「我的优惠券」cell（本卡加，ROUTE_MAP → /pages/me/coupons）→ **N=1** ✅
- **「选券模块」**：BizCouponPicker 被 GZ-BEAN-015 拼豆付款页消费（集成可达性由 BEAN-015 卡负责）。
- coupons.vue 页靠 definePage 自动注册（uni-pages）；Kevin 人验前跑一次 `pnpm build:mp-weixin`（注意 [[mp-build-devtools-hang]]）生成含 me/coupons 的 pages.json。

## 风险提示 / 已知 issue
- **R-1 BizCouponPicker 弹层为自写遮罩**（非 wd-popup，遵 C 纪律不撒 wd-*）：mp 真机需 Kevin 人验弹层层级 + 滚动穿透（mock 阶段功能为主）。
- **R-2 无券时入口行置灰不可点**（hasUsable=false）：设计为有券才可开弹层；无券显示「无可用优惠券」。
- 待 Kevin 批量人验（仅 mp）：① 我的券三 tab 切换 + 下拉刷新；② 拼豆付款页选券弹层（随 BEAN-015 一起验）；③ C 设计系统遵循度（粗墨边/朱红选中/纸底）。

## 对下游 ticket 的提示 ⭐（GZ-BEAN-015 消费 BizCouponPicker）
- **集成方式**：`<BizCouponPicker v-model="couponId" :total-amount-cent="amountCent" @change="onCouponChange" />`
  - `v-model` = `couponId: string | null`（null=不使用券）
  - props：`totalAmountCent`（单笔金额，分）+ `business?`（默认 pindou）
  - emit：`update:modelValue(couponId)` + `change(coupon: UserCouponVO | null)`
- **实付计算**：BEAN-015 用 `calcPayAmountCent(amountCent, selectedCoupon?.amountSnapshotCent ?? 0)`（from `@/pages/me/coupons.logic`，已 export）算实付展示。
- **下单透传**：提交 paid-submit 时带 `couponId`（BEAN-014 submitPaid 内 COUPON-002 锁券 + 实付重算，后端为准）。
- BizCouponPicker easycom 自动注册，BEAN-015 直接用标签无需 import。

## §AI 测试段（kevin-qa Tier 1B 完工后追加）

**Tier 1B（主线程整批集成验证 2026-06-10）** — 主线程一次启动 app 整批验：
- App `Started in 10.958s`，curl `/app/gz/coupon/usable?business=pindou` → HTTP 200（applet Controller 装配 + 注册）
- mp build dist 生成 + `pages/me/coupons` uni-pages 自动注册（Tier 2 可达：我的 tab → 九宫格券入口 N=1）
- vitest coupons.logic 9 passed + BizCouponPicker/coupons type-check 0 错 + easycom `^Biz` 注册
- ⬜ **mp 卡 → 进 progress.md 人验列**待 Kevin 批量真机验（三 tab + 选券弹层 + C 系统，见 testing-human.md）；8080 已释放

---

## §异常留痕
- COUPON-003 background subagent **崩于 `tool call could not be parsed`**（9.6 min / 49 tool_uses，崩在写第 10 个文件 BizCouponPicker.vue 前读 BizSkuSelector 时，result 暴露畸形 invoke 文本）。
- 崩前已建 9 文件（后端 applet + service + VO + mp 页 + logic + test + api + locale，gz-coupon 编译过 + 9 vitest 过，质量合格）。
- **主线程接管补全**：BizCouponPicker.vue + me 九宫格券入口 + user.zh-CN entryCoupons + 全套验证 + 本 report。
# GZ-BEAN-015 完工报告 — mp 拼豆付费页（选 1 类型 1 时段 + 显余量 + 采集 + JSAPI）

> mp + 少量 be（仅 mp api 补充），复杂度 M，**mp 人验**（进 progress.md 人验列）。C 日漫海报浓墨。
> **实施方式**：mp api（gz-bean.ts V1.2 付费段）由 background subagent 建成（崩在写 locale 前）；**locale + index.logic + index.vue 重写 + 采集 + 支付编排 + me 入口收尾由主线程接管**（见文末异常留痕）。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| 上游依赖 | ✅ BEAN-014（D12）paid-submit/type-slots 接口 + PINDOU；COUPON-003（D13）BizCouponPicker；USER-005（D11）wechat_id |
| 关键接口/组件 | ✅ getTypeSlots/submitPaidBooking（gz-bean.ts）+ BizCouponPicker（easycom `^Biz` 自动注册）+ updateProfile（gz-user，存 wechat_id）+ useOrderSubmit 支付范式 |
| 拼豆 tab 可达 | ✅ pages.json tabBar「拼豆」→ pages/bean/index（已上线 3-tab） |
| ADR 已读 | ✅ ADR-0007（双状态机 + 免费单兜底）+ ADR-0008（座位类型配额，按 booking 计数） |
| 权威蓝图引用 | ✅ doc/10 §11（N1-N10 + E1-E6 单笔单时段）+ doc/11 §3.5（座位类型配置）/§3.6（余量口径） |

### 权威蓝图关键约束摘录
- **选座（doc/10 §11.N3/N4，单笔单时段）**：选 1 类型 + 1 时段（单选非累加）；余量 = quantity − 活跃 booking；「还剩 N」/「已满」灰显。金额 = 类型单价（单笔无累加）。
- **抵扣（doc/11 §11.3）**：实付 = 单价 − 券面额（下限 0）；amount_cent = 实付，券面额不计 GMV（后端 paid-submit 重算）。
- **采集（doc/10 §11.N6，E2 拦截）**：mobile 空 → getPhoneNumber；wechat_id 空 → 手动填；两者齐才能提交（后端兜底 4001/4014）。
- **支付（§11.N7-N9）**：付费单 wx.requestPayment（JSAPI）→ onPaid 跳详情核销码；免费单（实付 0）直跳详情。

## 实现摘要

### mp api（gz-bean.ts，subagent 建 + 主线程补 id）
- `TypeSlotVO`（seatType/name/unitPriceCent/slotStart/slotEnd/quantity/remaining/full/active）+ `getTypeSlots(storeId, sessDate)`。
- `PaidBookingSubmitRequest`（storeId/seatType/sessDate/slotStart/slotEnd/couponId?/dedupClientToken?）+ `PaidSubmitVO`（**主线程补 id + amountCent/discountAmountCent/payAmountCent**）+ `submitPaidBooking` + `BEAN_PAID_ERROR_CODE`（4011/4001/4014）。

### mp 页（miniapp，C 设计系统，主线程）
- `pages/bean/index.vue`（**重写** V1.1 免费具体座位 → V1.2 付费类型配额）：报头 + 门店（单店隐藏切换）+ ① 选日期 BizDatePicker + ② 选类型（chip 显单价/全满灰显）+ ③ 选时段（chip 显余量「还剩 N」/「已满」灰显单选）+ ④ BizCouponPicker 选券 + 金额（单价−券=实付/免费）+ ⑤ 手机号 getPhoneNumber + ⑥ 微信号手动填（updateProfile）+ 到店须知 + BizFixedCta。付费提交 → submitPaidBooking → wx.requestPayment（仿 useOrderSubmit）→ 跳 detail；免费单直跳。
- `pages/bean/index.logic.ts` + `.test.ts`（主线程）：纯逻辑（groupTypes 类型聚合 / slotsOfType 时段 / unitPriceOf / calcPayCent 实付下限0 / remainLabel 余量 / slotSelectable / canSubmitPaid 采集门控 / formatYuan / shortHHmm），15 vitest。
- `locale/bean.zh-CN.ts`（主线程）：加 `beanPaidZhCN` scope（50+ key）+ t() `bean.paid.` dispatch。

## AI 自测（Tier 1A）

### ① type-check（vue-tsc，bean/index + index.logic + gz-bean + BizCouponPicker + me 全部 0 TS 错）
```
pnpm type-check | grep 'pages/bean/index|bean/index.logic|api/gz-bean|BizCoupon|me/coupons' = 0
（修 2 处：index.logic [...map.values()] → Array.from；index.vue <input maxlength="64"> → :maxlength="64"）
```

### ② vitest（bean/index.logic 15 tests：聚合 + 余量 + 实付 + 采集门控）
```
 ✓ src/pages/bean/index.logic.test.ts (15 tests) 9ms
 Test Files  1 passed (1)
      Tests  15 passed (15)
```
覆盖：groupTypes 聚合 + active 过滤 + anyAvailable / slotsOfType 过滤排序 / unitPriceOf / calcPayCent 下限 0 / remainLabel 满·余量 / slotSelectable / canSubmitPaid 各采集门控。

### ③ mp build（uni build -p mp-weixin，BizCouponPicker easycom + coupons 页 uni-pages 注册 + dist 生成）
```
DONE  Build complete.   (exit 0)
dist/build/mp-weixin/app.json 生成（1956 bytes）
coupons 页 uni-pages 自动注册：grep dist app.json → pages/me/coupons ✅
BizCouponPicker easycom `^Biz` 自动注册 + bean/index.vue 付费页整体编译 0 error
（尾部唤 devtools cli 假挂起 → pkill -o cli，dist 已生成，memory mp-build-devtools-hang）
（pre-existing 警告：pay/test.vue / pay/result.vue <route/> 废弃标签，非本卡文件）
```

## Tier 2 可达性（mp 硬约束，CLAUDE.md §8.3）
- **拼豆付费页**：Kevin 点底部「拼豆」tab（pages.json tabBar 已上线指向 pages/bean/index）→ 付费页，**N=1** ✅
- **⚠️ 纠正任务卡假设**：任务卡说「tabbar 未重构 → 加临时入口」，但实测**拼豆 tab 在 V1.0 3-tab 里早已存在**（CLAUDE.md §7.5）→ bean/index.vue 即拼豆 tab 落地页，**无需临时入口**。SYS-010（D14）是扩 5 tab，不影响现有拼豆 tab。
- 选券模块（BizCouponPicker）已集成在付费页 ④ 步。

## 风险提示 / 已知 issue
- **R-1 跳详情用 detail 页**：付费/免费成功 redirectTo `/pages/bean/detail?id=`；detail.vue（BEAN-005）展示 BookingDetailVO（含 payStatus/amountCent/seatType/qrPayload 核销码）。若 detail 未渲染 V1.2 付费字段（实付/类型）= 小 revision，留 Kevin 人验反馈。
- **R-2 支付最终态不信前端**：requestPayment success/fail 都跳详情，pay_status 以后端微信回调为准（detail 拉最新）；取消单留 paying 可在「我的预约」继续。
- **R-3 wechat_id 采集走 updateProfile**：复用 USER-002 个人资料更新接口（body.wechatId）；已填预填 input。
- 待 Kevin 批量人验（仅 mp，真机）：① 选类型/时段余量「还剩 N/已满」准确；② getPhoneNumber 原生授权；③ 微信号填写保存；④ wx.requestPayment 拉起（mock 模式）；⑤ 支付成功跳详情看核销码；⑥ 选券实付；⑦ 可再约一笔（多次预约）；⑧ C 设计系统遵循度（粗墨边/朱红选中/报头风）。

## 对下游 ticket 的提示
- **D14 GZ-SYS-010（tabbar 重构 5 tab）**：拼豆 tab 已指向 bean/index（付费页），SYS-010 扩 tab 时保留拼豆 tab 指向不变。
- 详情页 detail.vue 若需补 V1.2 付费字段展示（实付/类型/pay_status），可在 D14 或 revision 补（BookingDetailVO 字段已就绪）。

## §AI 测试段（kevin-qa Tier 1B 完工后追加）

**Tier 1B（主线程整批集成验证 2026-06-10）** — 主线程一次启动 app 整批验：
- App `Started in 10.958s`，curl `/app/gz/bean/booking/type-slots?storeId=1&sessDate=2026-06-20` → HTTP 200（BEAN-014 接口注册，BEAN-015 调用）
- mp build dist 生成（bean/index.vue 付费页 + BizCouponPicker easycom 整体编译 0 error）
- vitest index.logic 15 passed + type-check 0 错
- 可达：拼豆 tab N=1（pages.json tabBar 已上线指向 pages/bean/index）
- ⬜ **mp 卡 → 进 progress.md 人验列**待 Kevin 批量真机验（选座余量 + getPhoneNumber + 微信号 + requestPayment mock + 核销码 + C 系统，见 testing-human.md）；8080 已释放

---

## §异常留痕
- BEAN-015 background 前台 subagent **崩于 `tool call could not be parsed`**（29 tool_uses / 5min，崩在写 bean.zh-CN.ts locale 的 Edit 时，result 暴露畸形 `<invoke>` 文本）。
- 崩前已建 gz-bean.ts 的 V1.2 付费 api 段（TypeSlotVO/getTypeSlots/PaidSubmitVO/submitPaidBooking，质量合格）+ 规划好 beanPaidZhCN 文案（result 中可复用）。
- **主线程接管补全**：locale（复用规划文案）+ index.logic + test + index.vue 重写（V1.1→V1.2 付费）+ 采集/支付编排 + PaidSubmitVO.id + 全套验证 + 本 report。
- 全批次 subagent 崩溃率 5/7（仅 COUPON-002 + PAY-105 前台成功）；可靠路径 = 主线程实施。
