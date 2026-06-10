# GZ-BEAN-014 完工报告 — 拼豆付费核心（单笔单时段 + 双状态机 + 防超卖 + 迁移 + 激活 PINDOU）

> 纯后端，复杂度 L。ADR-0007（双状态机正交 status × pay_status，单笔单时段）+ ADR-0008（座位类型配额，按 booking 计数）落地。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（此路径非 git 仓库，主线程已替做基建部分） |
| 上游依赖 merge | ✅ `gz_bean_seat_type_config`（D11 BEAN-013，V202606190630）+ `gz_user.wechat_id`（D11 USER-005，V202606190610）均已建（dev DB 实探：config store1/single/q8/¥15，gz_user 有 wechat_id 列） |
| 关键类/表存在 | ✅ PayBusinessType.PINDOU 常量已在 gz-common；PayCallbackHandler SPI + PayCallbackDispatcher 就绪；gz_bean_booking 现有 schema 实探确认 |
| migration 最大时间戳 | ✅ 当前最大 V202606190631；本卡用 V202606200000 / V202606200001（> 已有，与 COUPON V20260620010x 不冲突） |
| 编译基线 | ✅ `mvn compile -pl ruoyi-modules/ruoyi-gz-bean -am -q` rc=0 |
| ADR 已读 | ✅ ADR-0007 全文 + ADR-0008 全文 + doc/11 §3.5/§3.6/§3.8/§3.9/附录 A.3/A.14/A.15 + doc/10 §11 全文 |
| 无 booking_unit 子表 | ✅ grep 源码 + 迁移仅出现在「绝不建」的断言注释里；DB `SHOW TABLES LIKE 'gz_bean_booking_unit'` 空 |

### 权威蓝图关键约束摘录（实施依据）
- **活跃 booking 定义（doc/11 §3.6 钉死）**：`status='pending' AND pay_status IN ('paying','paid')`。used（status≠pending）/ cancelled / no_show / pay_closed / refunded 全释放配额不计数。→ 配额 COUNT + 余量 + 用户幂等 三处 SQL 统一此口径。
- **双状态机正交（ADR-0007 §1）**：onPaid 只推 `pay_status: paying→paid`，**status 不动**（仍 pending 等核销）；核销推 `status: pending→used`，pay_status 停 paid；pay_closed 同步 `pay_status→pay_closed` + `status→cancelled`。
- **核销前置（ADR-0007 §1.2）**：仅 `pay_status='paid'` 的 pending 单可核销。
- **免费单兜底（ADR-0007 §1.4）**：price_cent=0 无券 → 实付 0 → 不建支付单，pay_status 直接 paid。
- **verify_code 签名因子（doc/11 §3.8）**：V1.2 `HmacSHA256(booking_no + sess_date + seat_type)` 截 32（不再用废弃 seat_id）。
- **旧数据迁移（ADR-0008 §5）**：旧免费单原地补 seat_type 兜底 `single` + amount_cent=0 + pay_status=paid，status 保留，无子表迁移。

## 实现摘要

### 迁移（2 文件）
- `V202606200000__GZ-BEAN-014-alter-booking-paid-columns.sql`：ALTER `gz_bean_booking` 加 8 列（seat_type / seat_type_snapshot / wechat_id_snapshot / amount_cent / discount_amount_cent / coupon_id / out_trade_no / pay_status）；MODIFY 放宽 seat_id / seat_no_snapshot / dedup_token / **verify_code**（V1.2 onPaid 才生成核销码，unpaid 单无码）为 NULL；**DROP `uk_dedup_tenant_store_dedup`**；加 `idx_quota_count(tenant_id,store_id,seat_type,sess_date,slot_start)` 配额核心索引 + `idx_pay_status` + `idx_coupon` + `uk_out_trade_no_tenant` UNIQUE。
- `V202606200001__GZ-BEAN-014-migrate-legacy-booking.sql`：旧免费单回填（WHERE seat_type IS NULL 幂等）→ seat_type='single' / snapshot='单人' / amount_cent=0 / pay_status='paid'；回填后 MODIFY seat_type NOT NULL。

### 后端代码（仅 `ruoyi-gz-bean`，未碰 gz-common 源码 — PINDOU 常量已在）
- **新增**：`GzBeanPaidBookingSubmitBo`（单笔单时段下单入参，无 units 数组）/ `GzBeanPaidSubmitVO`（下单结果 + 支付五参/免费单标记）/ `GzBeanTypeSlotAvailabilityVO`（余量）/ `PindouPayCallbackHandler`（实现 PayCallbackHandler SPI，business_type=pindou）/ `GzBeanUnpaidExpireJob`（SnailJob unpaid 超时回收薄壳）。
- **改动**：`GzBeanBooking`（+8 付费列）/ `GzBeanBookingVO`（+付费列展示）/ `QrCodeSigner`（+signByType/verifyByType seat_type 因子）/ `GzBeanBookingMapper`（+配额 COUNT FOR UPDATE / 余量 / 用户幂等 / markPaid / markPayClosed / 超时扫描）/ `IGzBeanBookingService` + impl（submitPaid 下单事务 + selectTypeSlotAvailability + onPindouPaid + closePindou + markExpiredUnpaidBatch；doVerify 加 paid 前置 + 核销签名按 seat_id/seat_type 判别）/ `GzBeanBookingMpController`（+/paid-submit +/type-slots）/ `GzBeanErrorCode`（+QUOTA_FULL/SEAT_TYPE_*/WECHAT_ID_REQUIRED/NOT_PAID）。
- **支付链路集成**：submitPaid 付费单调 `IGzPayTransactionService.createBusinessOrder`（business_type=pindou，business_order_no=booking_no），用 `ObjectProvider` 惰性注入打断构造期循环依赖（本类→PindouHandler→本类）。
- **券字段只留位**：coupon_id / discount_amount_cent 加字段 + 下单/关闭事务回滚锁券 hook 注释位（`TODO(D13-COUPON-002)`），不实现券逻辑。
- **改动文件清单**（19 个 java + 2 sql）：见上「实现摘要」。service impl 1101 行。

## AI 自测（Tier 1A）

### ① 编译 + 单测（91 全过，含 19 个 V1.2 新测）
```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-bean -am
[INFO] Tests run: 35, ... -- in GzBeanBookingServiceImplTest   (16 旧 + 19 新)
[INFO] Tests run: 12, ... -- in GzBeanSeatServiceImplTest
[INFO] Tests run: 13, ... -- in GzBeanSeatTypeConfigServiceImplTest
[INFO] Tests run: 10, ... -- in GzBeanTimeSlotTemplateServiceImplTest
[INFO] Tests run: 14, ... -- in GzBeanStoreServiceImplTest
[INFO] Tests run: 7,  ... -- in QrCodeSignerTest
[INFO] Tests run: 91, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
新增 19 测覆盖：配额满拒单 / 并发约最后名额(仅一单成功) / 付费单建支付单 / 免费单直 paid / 微信号未填 / 类型未配置·停用 / 用户幂等 / onPaid(paying→paid+核销码) / onPaid 幂等 / onPaid booking 不存在抛错 / closePindou 释放配额 / closePindou 幂等 / verify NOT_PAID 拒核销 / verify paid 可核销 / 余量计数(还剩N·已满) / 超时回收统计 / 超时回收空扫。

### ② DDL 迁移可应用 + 旧数据迁移前后 count 比对（误差 0）
```
-- PRE-MIGRATION
total = 1   (BK20260601000001, seat_id=2, status=pending；无 seat_type 列)

-- APPLY V202606200000 (ALTER) + V202606200001 (migrate) → 成功
列：seat_type NOT NULL / pay_status NOT NULL DEFAULT 'unpaid' / amount_cent NOT NULL DEFAULT 0 ... 全部加上
seat_id/dedup_token/verify_code → NULL 允许
索引：uk_dedup_tenant_store_dedup 已 DROP；新增 idx_quota_count / idx_pay_status / idx_coupon / uk_out_trade_no_tenant(UNIQUE)

-- POST-MIGRATION
total = 1   （误差 0，无丢数据）
旧单回填：BK20260601000001 | seat_type=single | seat_type_snapshot=单人 | amount_cent=0 | pay_status=paid | status=pending（保留）
unmigrated_null_seat_type = 0

-- 幂等复跑 V202606200001
rerun rc=0；total 仍 = 1；行未二次修改（WHERE seat_type IS NULL 已无匹配）
```

### ③ 配额并发压测（FOR UPDATE 串行化 — 仅一单成功，其余拒单）
```
-- quantity=1 的 (store1, quad, 2099-12-31, 10:00) 最后名额，两事务竞争：
[A] active before = 0          ← A 先拿 FOR UPDATE 锁，读到 0
[A] (持锁 SLEEP 3s) INSERTED (won last slot)  ← A 写入活跃单后 commit
[B] active before (after A commit) = 1  ← B 被 A 的 FOR UPDATE 阻塞，A commit 后读到 1
[B] count >= quantity(1) -> REJECT (quota full), no INSERT  ← B 拒单

最终：final active count for slot = 1   （无超卖，仅 A 成功）
```
FOR UPDATE 悲观锁正确串行化两个并发下单事务 → 防超卖闭环（ADR-0008 §2 / doc/11 §3.6）。

### ④ R7 校验（无子表）
```
$ grep -rni "booking_unit|total_amount_cent" ruoyi-gz-bean/src/ + 新迁移
→ 唯一匹配 = 迁移文件「绝不建 gz_bean_booking_unit；无 total_amount_cent」的断言注释（非真实表/列）
$ SHOW TABLES LIKE 'gz_bean_booking_unit';  → 空
```
一笔 = 一行 booking = 1 类型 1 时段，amount_cent = 单价 snapshot，无累加无子表 ✅

### ⑤ 收尾
- dev DB 已 **revert 回 pre-migration 状态**（删 8 列 + 4 索引、恢复 NOT NULL + uk_dedup 索引、count 仍 1、旧行 NOT NULL 值完好）→ kevin-qa Tier 1B 启动 app 时 Flyway 会 fresh 应用 V20260620000x 两文件（我用 raw SQL 验过可应用，未污染 flyway_schema_history）。
- Redis 已 FLUSHDB（schema 变更后，CLAUDE.md §5）。
- `mvn install -pl ruoyi-modules/ruoyi-gz-bean -am` 成功 → 新 jar 入 .m2，Tier 1B app 启动加载新代码（PINDOU handler / 新端点）。
- **未启动 spring-boot:run / 未占 8080**（留给主线程串行跑 kevin-qa Tier 1B）。

## 风险提示 / 已知 issue

- **R-1 旧核销码签名因子兼容**：旧免费单迁移后既有 seat_id（=2）又有 seat_type（=single），但其持久化 verify_code 当年用 seat_id 签。`doVerify`/`buildQrPayload` 以 **seat_id 是否非空** 判别：seat_id 非空→走旧 seatId 签名（兼容历史码）；seat_id NULL + seat_type 非空→走 V1.2 seatType 签名。已在代码注释钉死判别真源。
- **R-2 Flyway checksum**：本卡两迁移文件我未手动写入 flyway_schema_history（CRC32 难手算），改为 revert dev schema 让 app Flyway 自然应用。**kevin-qa Tier 1B 须用「启动 app 触发 Flyway」验证迁移**（而非手动跑 SQL），届时 flyway_schema_history 会记录 V202606200000/0001。
- **R-3 拼豆是否计 4% GMV 未定**（doc/11 §4.6 / F3.6）：本卡仅 business_type=pindou 接入支付链路，**不碰对账中心**（D15 ADMIN-105 定）。
- **券逻辑全部 D13**：discount_amount_cent 本卡恒 0，couponId 仅透传占位，submitPaid/closePindou 留 `TODO(D13-COUPON-002)` 锁券/回滚 hook 注释位。
- 待 Kevin 批量人验关注（仅 mp 端）：**N/A — 纯后端 ticket，无 mp 页**（mp 选座付费页 = D13 GZ-BEAN-015）。CLAUDE.md §8.2：Tech 段无 miniapp 路径 + AC 无微信原生能力 → AI Tier 1A+1B 全 ✅ 即终态，无人验。

## 对下游 ticket 的提示

- **GZ-BEAN-015（D13，mp 选座付费页）**：调 `POST /app/gz/bean/booking/paid-submit`（body: storeId/seatType/sessDate/slotStart/slotEnd/couponId?/dedupClientToken?）+ `GET /app/gz/bean/booking/type-slots?storeId&sessDate`（余量，每档 remaining/full）。付费单返回 `payParams`（mp wx.requestPayment 五参）+ outTradeNo；免费单 `free=true` 无 payParams 直接跳详情。**付款前须先采集 mobile + wechat_id**（未采集分别返 4001 / 4014），UI 弹 getPhoneNumber + 微信号表单。
- **GZ-COUPON-002（D13，券抵扣）**：submitPaid 内 `TODO(D13-COUPON-002)` 处接锁券（gz_user_coupon unused→locked）+ 实付重算 payAmountCent = amount_cent − 券面额（下限 0）；closePindou 内接回滚解锁（locked→unused）。booking 已有 coupon_id / discount_amount_cent 字段就绪。
- **SnailJob 控制台注册（人工）**：本卡新增 `GzBeanUnpaidExpireJob`（@JobExecutor name=`gzBeanUnpaidExpireTask`）→ 控制台建任务：名 `GZ-BEAN-UNPAID-EXPIRE` / CRON `0 0/5 * * * ?`（每 5 分钟）/ 组 ruoyi_group / jobParams 可选超时分钟数（缺省 15）。**未走 Flyway INSERT sys_job**（SnailJob 非 Quartz，hard-fail 风险，memory scheduler-is-snailjob）。
- **D15 ADMIN-105（对账）**：pindou 正向流水是否入 GMV/4% 留此卡定；本卡已接支付链路不碰对账。

## ADR 已读摘录
- **ADR-0007**：双状态机正交 7 条边 + 唯一硬前置（verified 需 paid）+ 配额 COUNT FOR UPDATE 活跃定义 + 免费单兜底 + pay_closed 同步 status→cancelled 释放配额 + 旧数据原地 ALTER 迁移。
- **ADR-0008**：gz_bean_seat 保留不 DROP 停用于预约；预约引 seat_type 不引 seat_id；可用量 = quantity − 活跃 booking 计数；改现有表胜全新表；旧单兜底 single 迁移。

## §AI 测试段（kevin-qa Tier 1B，15:04-15:20）

### Flyway 迁移验证

```
[INFO] Current version of schema `ry-vue`: 202606190631
[INFO] Migrating schema `ry-vue` to version "202606200000 - GZ-BEAN-014-alter-booking-paid-columns"
[INFO] Migrating schema `ry-vue` to version "202606200001 - GZ-BEAN-014-migrate-legacy-booking"
[INFO] Successfully applied 4 migrations to schema `ry-vue`, now at version v202606200101
```

V202606200000/0001 成功应用（checksum 验证通过，0 失败）。

DB 验证：
- gz_bean_booking 加列：seat_type NOT NULL, pay_status NOT NULL DEFAULT 'unpaid', amount_cent NOT NULL DEFAULT 0, out_trade_no NULL ✅
- 索引：idx_quota_count(tenant_id,store_id,seat_type,sess_date,slot_start) + idx_pay_status + uk_out_trade_no_tenant ✅
- 旧数据迁移：BK20260601000001 → seat_type=single, pay_status=paid, amount_cent=0（count 误差=0）✅

### 后端集成 + API 契约

```bash
# AC4: type-slots 余量查询
GET /app/gz/bean/booking/type-slots?storeId=1&sessDate=2026-06-20
# 实际：code=200，3 档（single × 3 时段），each: quantity=8 active=0 remaining=8 full=false ✅
# id 字段: N/A（type-slots 无 id）
```

```bash
# AC2/AC5: 付费下单（price_cent=1500, 实付>0）
POST /app/gz/bean/booking/paid-submit
Body: {storeId:1, seatType:"single", sessDate:"2026-06-20", slotStart:"10:00:00"...}
# 期望：pay_status=paying + payParams 五参 + outTradeNo=PINDOU-
# 实际：code=200, bookingNo=BK20260609000001, payStatus=paying, free=false
#        outTradeNo=PINDOU-20260609-000001, payParams.packageVal=prepay_id=mock_... ✅
# DB验证：gz_pay_transaction(business_type=pindou, amount_cent=1500, status=pending) ✅
# API契约：id返回string类型 ✅
```

```bash
# AC5: 免费单直 paid（price_cent=0）
# 临时改 price_cent=0 后提交
# 实际：code=200, free=true, payStatus=paid, payParams=null ✅
```

```bash
# AC5: mock onPaid 全链路（PINDOU SPI 分发）
POST /system/gz/pay/test/simulate-callback?outTradeNo=PINDOU-20260609-000001
# 实际：code=200，DB验证:
#   gz_bean_booking: pay_status=paying→paid ✅
#   verify_code=e55c39ed24c44a8f4c305eddc247baaf（32位hex，HmacSHA256+seat_type因子）✅
#   gz_bean_booking_log: operator_type=system, 支付成功+核销码生成 ✅
```

```bash
# AC5: 核销前置（paying 单核销应拒绝）
POST /system/gz/bean/booking/5/verify
# 实际：code=4015，msg="该预约尚未完成支付，不可核销（当前支付状态：paying）" ✅
```

```bash
# AC3: 防超卖配额拒单（quota=1，active=1，第三用户尝试约同时段）
# 实际：code=4011，msg="该时段座位已约满，请重选类型或时段" ✅
# 注：并发压测已由 Tier 1A 单测覆盖（FOR UPDATE 串行化，仅一单成功）
```

### 单测 raw output

```
[INFO] Tests run: 91, Failures: 0, Errors: 0, Skipped: 0  -- ruoyi-gz-bean
[INFO] BUILD SUCCESS
```

### ⚠️ 发现 Bug：D11 BEAN-013 seed 数据 del_flag 错误

**现象**：`gz_bean_seat_type_config` 表中 id=1 的 del_flag='1'（已删除），导致 `type-slots` 接口查询不到配置，返回空数组。

**根因**：D11 BEAN-013 的 seed SQL（V202606190630/0631 或手工插入）将 del_flag 设为 '1'，而 MyBatis Plus 全局 logicDeleteValue=1，查询自动过滤 del_flag='1' 的记录。

**临时修复**：kevin-qa 在测试前执行了 `UPDATE gz_bean_seat_type_config SET del_flag='0' WHERE id=1` 解锁测试。

**需要 kevin-coder 修复**：检查 D11 BEAN-013 迁移文件中 gz_bean_seat_type_config 的 del_flag 值，应改为 '0'（新建更大时间戳迁移 ALTER/UPDATE 修正）。

### 跳过 / 未跑

- 并发压测（真实 HTTP 并发）：引用 Tier 1A raw output（FOR UPDATE 串行化已验，仅一单成功）
- verify paid 单正向核销流程：非本卡新增 AC，已有旧测试覆盖

### 结论

- ✅ Flyway 迁移应用（4 个文件，success=1）
- ✅ AC1 ALTER 迁移：付费列 + 索引完整
- ✅ AC2 付费下单：一行 booking，amount_cent=单价 snapshot，无子表
- ✅ AC3 防超卖：quota 满拒单 code=4011
- ✅ AC4 余量查询：quantity-active=remaining，full 标志正确
- ✅ AC5 双状态机：paying→paid（onPaid）+ 免费单直 paid + 核销前置拒绝 code=4015
- ✅ API 契约：id 返回 string
- ❌ **Bug（非本卡新增逻辑）**：D11 BEAN-013 seed del_flag='1' 导致 type-slots 初始返回空——需 kevin-coder 在下一个 migration 修复 seed 数据

---

## §Tier 1B 闭环修复（kevin-coder 顺手补 BEAN-013 数据缺口）

### 诊断（已查实）
- kevin-qa Tier 1B：`type-slots` 余量查询初始返空/不全。
- **根因 = D11 BEAN-013 从没 seed 过 config 行**：seed 迁移 V202606190631 只 seed 字典 + 菜单，无任何 `gz_bean_seat_type_config` 行。dev DB 仅有 1 行 single（admin CRUD 测试残留），double/quad 缺失 → type-slots 只返 single（甚至 single 若被软删则全空）。本项目 `logicDeleteValue=1`，软删行被 MyBatis-Plus 过滤。
- 后果：dev DB / 全新部署 / D13 BEAN-015 mp 选座都拿不到完整余量。**非 BEAN-014 逻辑 bug**（type-slots 查询逻辑正确，是上游数据缺口）。

### 修复（durable，对齐 BEAN-001/002 seed 哲学）
- **新建 seed 迁移** `V202606200200__GZ-BEAN-013-seed-seat-type-config.sql`（时间戳 > 当前最大 V202606200101）：
  - `SET @store_id = (SELECT id FROM gz_bean_store WHERE store_no='CD001' AND tenant_id='1001' LIMIT 1)`（不写死 PK，照 BEAN-002 风格）。
  - seed CD001 三类型 demo：single q8/¥15、double q4/¥28、quad q2/¥50；enabled=1 / del_flag='0' / sort_no 升序；注释标「demo 数据，owner 可在 admin 调」。
  - **`ON DUPLICATE KEY UPDATE`**（UNIQUE = `uk_tenant_store_type(tenant_id,store_id,seat_type)` 不含 del_flag）→ 既复活残留软删行（`del_flag='0'`）又幂等；tenant_id 显式 '1001'（seed 不走自动填充）。
- **entity 注释修正**：`GzBeanSeatTypeConfig.java` delFlag 注释「0=正常 / 2=删除」改「0=正常 / 1=删除」（本项目 logicDeleteValue=1）。已应用迁移文件未动。

### 验证 raw output（直接跑 raw SQL；kevin-qa Tier 1B 启动 app 时由 Flyway 应用同一文件）
```
-- APPLY V202606200200 → seed rc=0
-- 验证 1：3 行 del_flag='0' enabled=1
id  store_id  seat_type  quantity  price_cent  enabled  sort_no  del_flag
1   1         single     8         1500        1        1        0
3   1         double     4         2800        1        2        0
4   1         quad       2         5000        1        3        0

-- 验证 2：幂等复跑 → rows_after_rerun = 3（无新增、无重复）

-- 验证 3：type-slots 余量（config enabled × slot enabled，活跃计数 vs quantity）@ 2099-12-31
seat_type  name   price  slot          quantity  active  remaining
single     单人   1500   10:00-12:00   8         0       8
single     单人   1500   14:00-17:00   8         0       8
single     单人   1500   19:00-22:00   8         0       8
double     双人   2800   10:00-12:00   4         0       4
double     双人   2800   14:00-17:00   4         0       4
double     双人   2800   19:00-22:00   4         0       4
quad       四人桌 5000   10:00-12:00   2         0       2
quad       四人桌 5000   14:00-17:00   2         0       2
quad       四人桌 5000   19:00-22:00   2         0       2
```
→ type-slots 对 CD001 返 single/double/quad 各档余量（3 类型 × 3 时段 = 9 条），空数组 bug 消除。SQL 与 service `selectTypeSlotAvailability` 逻辑一致（GREATEST(0, quantity − 活跃计数)）。

### 收尾
- compile rc=0（entity 注释改动）；**未启 app / 8080 free**（本次只跑 raw SQL，Flyway 由 Tier 1B app 启动应用）。
- **未 commit**（主线程统一）。
