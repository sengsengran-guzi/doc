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
# GZ-COUPON-001 完工报告 — 优惠券地基（券模板 + 用户券 + 发放策略 SPI + admin 批量发放）

> 端：后端（新建 `ruoyi-gz-coupon` 域）+ admin（plus-ui）。复杂度 M。AI 终态（无 mp / 无人验）。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（本项目此路径非 git 仓库，§0 跳过 git） |
| 上游依赖 merge | ✅ `gz_user` 表已建 + sys_role owner(100)/staff(101) 已建（docker mysql 实测） |
| 关键表/段空闲 | ✅ `gz_coupon_template` / `gz_user_coupon` 不存在（从零建）；`ruoyi-gz-coupon` 模块不存在（新建）；menu 12000 段空闲（`MAX(menu_id) BETWEEN 12000 AND 12999 = EMPTY`） |
| 迁移时间戳 | ✅ flyway 已应用最大 = `202606190631`；本卡用 `V202606200100` / `V202606200101`（> 已有，BEAN-014 用 V20260620000x 不冲突） |
| 字典段避冲突 | ✅ 现有 max dict_id=9210 / dict_code=91309；本卡取 dict_id 9220-9233 / dict_code 9221-9236（避开 BEAN-013 9210-9213） |
| 编译通过 | ✅ `mvn -o compile -pl ruoyi-modules/ruoyi-gz-coupon` BUILD SUCCESS |
| ADR 已读 | 无相关 ADR（发放策略 SPI 设计权威 = doc/11 §11.1.a，ticket 卡明示「不另立 ADR」） |
| 权威蓝图引用 | ✅ doc/11 §11.1/§11.1.a/§11.2/§11.3/§11.4 + 附录 A.17/A.18/A.19/A.22 + §10.2 dict 映射表 + §10.3 menu 段；doc/10 §12 全读（摘录见文末） |

**§0 期间发现的 doc 偏差（按 CLAUDE.md §9.5 #1「以 doc/11 为准」处理）**：
- ticket 卡 AC 2 文字写「`gz_user_coupon_status`」，但 doc/11 §10.2 dict 映射表（line 1314）+ 附录 A.17（line 1748）权威定义 dict_type = **`gz_coupon_status`**。已按 doc/11 落地 `gz_coupon_status`（迁移注释 + 本报告记录）。**建议主线程在 doc 复盘时确认 ticket 卡此处改齐 doc/11**（源头已对，仅 ticket 文字笔误）。

## 实现摘要

### 新建模块 `ruoyi-modules/ruoyi-gz-coupon`（包名 `org.dromara.gz.coupon.*`，照 ruoyi-gz-news 结构）
- **根 pom 注册（2 处）**：`ruoyi-modules/pom.xml` 加 `<module>ruoyi-gz-coupon</module>`；`ruoyi-admin/pom.xml` 在 gacha 依赖块后加 ruoyi-gz-coupon 依赖块。
- **依赖**：仅 `ruoyi-gz-common`（传递引入 mybatis/web/tenant/security/log/json）+ spring-boot-starter-test；复用 common 的 `IGzUserService`（发券名单解析）。无新第三方依赖。
- 31 个 Java 文件（含 3 个测试），分层 entity / bo / vo / mapper / service(+impl) / strategy / event / internal / controller。

### 迁移（2 个）
- `V202606200100__GZ-COUPON-001-create-coupon-tables.sql`：`gz_coupon_template` + `gz_user_coupon`，字段/索引严格对齐 doc/11 §11.1/§11.2。业务码 UNIQUE 含 `del_flag`（跨层契约 #3 软删可复用）；`tenant_id` DEFAULT '1001'；金额 `*_cent`；`issue_config_json` JSON；`version` 乐观锁。
- `V202606200101__GZ-COUPON-001-seed-dict-menu.sql`：4 字典（discount_type/issue_strategy/coupon_status/template_status，逐字对齐附录）+ 11 个 12000 段菜单（目录/券模板/发放记录 + 按钮 perm）+ owner(100) 全授权。

### 发放策略 SPI（doc/11 §11.1.a）
- `ICouponIssuanceStrategy`（`supports()` 路由 + `issue(ctx)`）+ `CouponIssuanceContext`（模板 + 名单）。
- `ManualIssuanceStrategy`（V1.2 全链路）：乐观锁 `increaseIssuedCount`（DB 行锁内「校验配额 + 扣减 + version+1」单条 UPDATE）→ 批量 INSERT unused 券（amount_snapshot snapshot + expire = now + valid_days）。
- `RegisterWindowIssuanceStrategy` / `EventIssuanceStrategy`（预留，留位可编译，`issue()` 抛带说明的 `UnsupportedOperationException`）。
- `CouponIssuanceEvent` + `CouponIssuanceEventListener`（@EventListener 骨架，含 D14 RECYCLE-003 `recycle_paid` 钩子注释占位）。

### admin（plus-ui，ruoyi/Element Plus 默认审美，不引 mockup）
- `views/gz-coupon/template/index.vue`：模板列表 + 查询 + 新增/编辑弹窗（元↔分换算，V1.2 仅 cash/manual 可选）+ 暂停/启用/归档 + **批量发放弹窗**（选 active 模板 → 多选用户/筛关键词 → 发放 → 配额回显）。
- `views/gz-coupon/user-coupon/index.vue`：发放记录列表（回填 templateName/userNickname/userMobile）。
- `api/gz-coupon/{template,userCoupon}.ts`（id 全 string）+ `lang/{zh_CN,en_US}.ts` 加 `gzCouponTemplate` / `gzCouponUserCoupon` 块（全覆盖，默认 zh-CN 不混 emoji）。
- 菜单/路由走 DB seed（component path `gz-coupon/template/index` → 视图），无手写 route 文件。

## AI 自测（Tier 1A）

### 1. 编译 + 单测（mvn -o，未占 8080）
```
[INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0 -- GzCouponTemplateServiceImplTest
[INFO] Tests run: 7, Failures: 0, Errors: 0, Skipped: 0 -- GzCouponIssuanceServiceImplTest
[INFO] Tests run: 3, Failures: 0, Errors: 0, Skipped: 0 -- ManualIssuanceStrategyTest
[INFO] Tests run: 18, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
覆盖：manual 策略 happy path（N 用户 → N 张 unused 券 + amount_snapshot + expire = now+valid_days）、乐观锁防超发（increaseIssuedCount 返 0 → 抛异常且不 INSERT 券）、名单空拒绝、策略路由、非 active/非 manual 模板拒绝、keyword 名单解析、并发抢最后配额（仅一单成功其余拒单）、枚举校验（仅 cash/pindou/manual）、template_no 生成、状态流转边界。
`mvn -o install -DskipTests -pl ruoyi-modules/ruoyi-gz-coupon` → BUILD SUCCESS（jar 装入 ~/.m2，避免 Bean 404）。

### 2. DDL 验证（docker mysql ry-vue，迁移可应用 + 结构/索引比对）
```
create OK / seed OK  （两迁移幂等应用，未污染 flyway_schema_history → 启动时 flyway 幂等重跑）

gz_coupon_template 索引：
  PRIMARY id / uk_tenant_template_no(tenant_id,template_no,del_flag)
  idx_status_business(tenant_id,status,applicable_business) / idx_discount_type / idx_issue_strategy   ✅ 对齐 doc/11 §11.1
gz_user_coupon 索引：
  PRIMARY id / uk_tenant_coupon_no(tenant_id,coupon_no,del_flag)
  idx_user_status / idx_template / idx_status_expire / idx_related_pay   ✅ 对齐 doc/11 §11.2

字典（值逐字对齐附录）：
  gz_coupon_discount_type   3  cash,full_reduce,percent
  gz_coupon_issue_strategy  3  manual,register_window,event
  gz_coupon_status          4  unused,locked,used,expired
  gz_coupon_template_status 3  active,paused,archived

menu 12000 段 11 行（目录 12000 + 券模板 12001 + 发放记录 12002 + 8 按钮 perm）；owner(100) 授权 = 11 ✅
```

### 3. 乐观锁防超发功能验证（AC 6，DB 直跑 increaseIssuedCount 同款 SQL，total_quota=3）
```
线程 A：N=2 version=0  → affected=1  issued_count 0→2, version 0→1
线程 B：N=2 version=0  → affected=0  （version 失配，拦截，不超发）
线程 B 重试：N=2 version=1 → affected=0  （配额 2+2>3，拦截，不超发）
线程 C：N=1 version=1  → affected=1  （恰好填满 2+1<=3）
最终：issued_count=3 = total_quota，version=2  → 无超发 ✅
（测试模板已 DELETE 清理）
```

### 4. plus-ui 构建（pnpm build:prod = vue-tsc + vite，未起 dev server）
```
> vite build --mode production
vite v7.3.2 building client environment for production...
dist/assets/userCoupon-DXlYCRl_.js   0.25 kB  （发放记录视图 chunk 已出）
（template 视图打进 index-* 主 chunk）
EXIT=0   无 TS error / 无 vue-tsc error
```

## 风险提示 / 已知 issue

- R5（批量发放超发）：已用 `issued_count` 乐观锁 version + 事务内 `issued_count + N <= total_quota` 单条 UPDATE 兜死（DB 实测拦截，单测覆盖并发抢最后名额）。
- R9（新模块未注册 → 404）：已注册父 pom + ruoyi-admin pom + `mvn install`。kevin-qa Tier 1B 起 app 后请确认 `/system/gz/coupon/template/list` 不 404。
- **迁移未走 flyway 应用**（我用 docker mysql 直跑验证 SQL 可应用，未写 flyway_schema_history）：app 下次启动 flyway 会幂等重跑这两个迁移（`CREATE TABLE IF NOT EXISTS` + `DELETE...INSERT` seed 均幂等），无 checksum 问题。kevin-qa 起 app 时观察 flyway 正常应用即可。
- **doc 偏差**（dict_type `gz_coupon_status` vs ticket 卡 `gz_user_coupon_status`）：已按 doc/11 权威落地，建议 doc 复盘订正 ticket 卡文字（源头 doc 已对）。
- 待 Kevin 批量人验关注：N/A（纯 admin + 后端，无 mp 页、无微信原生能力 → AI Tier 1A+1B 全 ✅ 即终态，无人验，ticket AC 已明示跳过 Tier 2 入口可达）。

## 对下游 ticket 的提示

- **D13 GZ-COUPON-002（拼豆抵扣 + 锁定/核销/过期 SnailJob）**：
  - 券态流转 `unused→locked→used` / `locked→unused` / `unused→expired` 由你落地；本卡只产 unused，`gz_user_coupon` 已建全字段（含 `used_time` / `related_pay_out_trade_no` 占位）。
  - 抵扣依赖 BEAN-014 下单事务：拼豆下单选券 → `unused→locked` + 写 `gz_bean_booking.coupon_id`；onPaid → `locked→used` + 写 `used_time` + `related_pay_out_trade_no`。抵扣口径 doc/11 §11.3（实付下限 0，券面额不计 GMV）。
  - 过期 SnailJob（`gz.coupon.expire.cron`）扫 `unused` 且 `expire_time < NOW()` → `expired`；本模块 pom 未加 `ruoyi-common-job`（本卡无 cron），你加 SnailJob 时补该依赖。
  - 复用现成乐观锁基础设施：`GzCouponTemplateMapper.increaseIssuedCount` 已是「版本 CAS + 配额校验」单条 UPDATE 模板，过期/回滚可仿此写条件 UPDATE。
- **D13 GZ-COUPON-003（mp 我的券 / 选券）**：mp 端，新建 applet controller（`/app/gz/coupon/*`）；选券接口 `GET usable?business=pindou&total_amount`（doc/10 §12.N3）返用户 unused 未过期券。
- **D14 GZ-RECYCLE-003（回收完成发券钩子）**：回收单 paid 时 `applicationEventPublisher.publishEvent(new CouponIssuanceEvent(this, "recycle_paid", userIds))` 即可接入；`CouponIssuanceEventListener` 骨架已留位（按 issue_strategy='event' + issue_config_json.event_type 匹配模板发券的逻辑由你/甲方定策略后补，不动本模块 DDL）。
- 业务码序号空间：`CPN-` 查 template_no、`UC-` 查 coupon_no，各自独立空间；批量发券一次取基序号后内存自增（DB UNIQUE 兜底）。

## doc/11 §11 / doc/10 §12 引用摘录（实施钉死口径）

- §11.1 模板：template_no `CPN-`(UNIQUE tenant_id,template_no) / discount_type 默认 cash / amount_cent / applicable_business 默认 pindou / valid_days 默认 30 / total_quota NULL=不限 / issued_count 默认 0 / issue_strategy 默认 manual / issue_config_json JSON NULL / status 默认 active / version 乐观锁。IDX (tenant_id,status,applicable_business)/(tenant_id,discount_type)/(tenant_id,issue_strategy)。
- §11.1.a SPI：ICouponIssuanceStrategy 按 issue_strategy 路由；事务内乐观锁 `issued_count + N <= total_quota`。V1.2 仅 manual 落地；register_window 仅接口；event 留接口 + 事件钩子（RECYCLE-003 发 CouponIssuanceEvent）。后续加策略只补一个实现不动 DDL。
- §11.2 用户券：coupon_no `UC-`(UNIQUE) / template_id / user_id / amount_snapshot_cent（领券时从 template snapshot）/ status 默认 unused / gained_time / expire_time = gained_time + valid_days / used_time NULL / related_pay_out_trade_no NULL。IDX (tenant_id,user_id,status)/(tenant_id,template_id)/(tenant_id,status,expire_time)/(tenant_id,related_pay_out_trade_no)。
- §11.3 抵扣/GMV：实付 = 单笔金额 − amount_snapshot_cent（下限 0）；券面额不计 GMV；不建独立 use 流水表（status + related_pay_out_trade_no 追溯）。本卡只建表 + 发放，抵扣 = D13。
- §11.4 F11.4：manual 选用户/筛名单批量 INSERT + 乐观锁配额校验。F11.5：register_window/event 不实现逻辑，仅 SPI + 事件钩子，甲方定策略补一个实现即生效不动 DDL。
- 附录 A.17 `gz_coupon_status`(unused/locked/used/expired) / A.18 `gz_coupon_template_status`(active/paused/archived) / A.19 `gz_coupon_discount_type`(cash/full_reduce/percent) / A.22 `gz_coupon_issue_strategy`(manual/register_window/event)。
- doc/10 §12.N1 建模板 / N2 发放（策略路由 + 乐观锁配额）/ N3-N8 抵扣锁定核销过期（= D13）；E1 发放超配额乐观锁失败提示。

## §AI 测试段（kevin-qa Tier 1B，15:04-15:20）

### Flyway 迁移验证

```
[INFO] Migrating schema `ry-vue` to version "202606200100 - GZ-COUPON-001-create-coupon-tables"
[WARN] DB: Table 'gz_coupon_template' already exists (SQL State: 42S01 - Error Code: 1050)
[WARN] DB: Table 'gz_user_coupon' already exists (SQL State: 42S01 - Error Code: 1050)
[INFO] Migrating schema `ry-vue` to version "202606200101 - GZ-COUPON-001-seed-dict-menu"
[INFO] Successfully applied 4 migrations to schema `ry-vue`, now at version v202606200101
```

`CREATE TABLE IF NOT EXISTS` 幂等通过（表已存在 WARN 为预期，非 ERROR），flyway_schema_history 记录 success=1。

DB 验证：
- gz_coupon_template: PRIMARY + uk_tenant_template_no + idx_status_business + idx_discount_type + idx_issue_strategy ✅
- gz_user_coupon: PRIMARY + uk_tenant_coupon_no + idx_user_status + idx_template + idx_status_expire + idx_related_pay ✅
- 字典：gz_coupon_discount_type(3) / gz_coupon_issue_strategy(3) / gz_coupon_status(4) / gz_coupon_template_status(3) ✅
- 菜单：12000 段 11 行（目录+模板+发放记录+8按钮），owner(100) 全授权 ✅

### 后端集成 + API 契约

```bash
# AC3: 模板 CRUD
POST /system/gz/coupon/template
Body: {name:"QA测试代金券5元", discountType:"cash", amountCent:500, validDays:30, totalQuota:10, issueStrategy:"manual"}
# 实际：code=200, msg="新建成功" ✅

GET /system/gz/coupon/template/{id}
# 实际：templateNo=CPN-20260609-000001, discountType=cash, amountCent=500, issuedCount=0
#        id 返回 string 类型 ✅（API 契约）

POST /system/gz/coupon/template/pause/2   → code=200 ✅
POST /system/gz/coupon/template/archive/2 → code=200, DB status=archived ✅
```

```bash
# AC4/AC6: 批量发放（manual策略，userIds=[7,8]，共2张）
POST /system/gz/coupon/template/issue
Body: {templateId:2, userIds:[7,8]}
# 实际：code=200, msg="发放成功", issuedCount=2 ✅
# DB验证：
#   gz_user_coupon 2行: status=unused, amount_snapshot_cent=500
#   expire_time = gained_time + 30天（2026-07-09）✅
#   issuedCount: 0→2 ✅
```

```bash
# AC6: 配额耗尽拦截（totalQuota=3，尝试发5张）
# 新建模板 totalQuota=3，POST /system/gz/coupon/template/issue userIds=[1,2,3,4,5]
# 实际：code=500，msg="发放失败：配额不足或模板已被并发修改（已发 0 / 配额 3），请重试" ✅
```

```bash
# AC3/AC5: 非active模板拒绝发放（archived状态）
POST /system/gz/coupon/template/issue  Body: {templateId:2, userIds:[7]}
# 实际：code=500，msg="模板非启用状态，不可发放：archived" ✅
```

```bash
# AC3: 发放记录列表
GET /system/gz/coupon/userCoupon/list?pageNum=1&pageSize=10
# 实际：code=200, total=9, couponNo=UC-20260609-格式 ✅
```

### 单测 raw output

```
[INFO] Tests run: 8,  Failures: 0, Errors: 0, Skipped: 0 -- GzCouponTemplateServiceImplTest
[INFO] Tests run: 7,  Failures: 0, Errors: 0, Skipped: 0 -- GzCouponIssuanceServiceImplTest
[INFO] Tests run: 3,  Failures: 0, Errors: 0, Skipped: 0 -- ManualIssuanceStrategyTest
[INFO] Tests run: 18, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

### admin Playwright E2E

Playwright MCP 工具在当前环境不可用（`No such tool available: mcp__plugin_playwright_playwright__browser_navigate`）。改用 curl API 契约回归替代 admin 端 E2E 覆盖（CRUD + 发放 + 配额 + 状态切换全通过，见上）。

plus-ui 前端 AC5 视觉/表单验证（元↔分换算、dict-tag 翻译、issue_strategy 仅 manual 可选）：未通过 Playwright 验证，建议 Kevin 在 admin 页面上 spot check 以下两点：
1. dict-tag 中文渲染（`gz_coupon_status` = 未使用/已锁定/已使用/已过期）
2. issue_strategy 下拉 V1.2 是否只显示 manual（不显示 register_window/event）

### 跳过 / 未跑

- Playwright E2E（MCP 工具不可用）：改 curl API 替代，功能路径全覆盖
- dict-tag 中文渲染视觉验证：需人工 admin spot check

### 结论

- ✅ Flyway 迁移应用（V20260620010x 两文件，幂等通过）
- ✅ AC1 建表：字段/索引对齐 doc/11 §11.1/§11.2
- ✅ AC2 字典 seed：4 个字典全 seed，menu 12000 段 11 行
- ✅ AC3 模板 CRUD：list/getInfo/add/pause/archive，id 返 string
- ✅ AC4 发放策略 SPI：manual 全链路，issued_count+N，unused 券生成，expire_time 正确
- ✅ AC5 admin 功能（API层验证）：CRUD + 状态切换 + 发放页
- ✅ AC6 配额防超发：5张超过 totalQuota=3 被拒，msg 明确
- ✅ AC7 券态只产 unused：发放后 status=unused，used/expired 流转 = D13
- ✅ AC8 单测：18 tests passed (GzCouponTemplate + GzCouponIssuance + ManualIssuance)
- ⚠️ admin Playwright E2E 未执行（MCP 不可用）：dict-tag 渲染 + issue_strategy 下拉建议 Kevin spot check
